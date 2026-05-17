"""DedalMCP Preset Editor — Blender add-on.

A single-file Blender addon that lets you author and re-edit DedalMCP preset
files visually. Workflow:

1. Add primitives via the panel (they get tagged so the plugin remembers
   what they are).
2. Move/rotate/scale them in the viewport. As long as you don't edit
   vertices or add modifiers, they stay parametric.
3. Click "Export Selection" — primitives become a `composite/v1` preset,
   anything edited beyond recognition becomes `mesh_data/v1`.
4. To revisit a preset, click "Import Preset" — the JSON is rebuilt as
   editable objects in the scene.

Install: Edit > Preferences > Add-ons > Install... > pick this file.
Then press N in the 3D viewport and look for the "DedalMCP" tab.
"""

bl_info = {
    "name": "DedalMCP Preset Editor",
    "author": "DedalMCP",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > DedalMCP",
    "description": "Author and re-edit DedalMCP preset JSON files visually",
    "category": "Import-Export",
}

import ast
import bpy
import bmesh
import hashlib
import json
import math
import operator
import os
from pathlib import Path

from bpy.props import (
    StringProperty, FloatVectorProperty, EnumProperty, IntProperty,
)
from bpy.types import Operator, Panel, PropertyGroup


# ─── Shape registry ──────────────────────────────────────────────────
# Maps the DedalMCP composite shape name to (bpy op, default params, vertex_count_hint).

SHAPES = {
    "cube":      ("primitive_cube_add",       {"size": 1.0}),
    "sphere":    ("primitive_uv_sphere_add",  {"radius": 0.5, "segments": 16, "ring_count": 12}),
    "icosphere": ("primitive_ico_sphere_add", {"radius": 0.5, "subdivisions": 2}),
    "cylinder":  ("primitive_cylinder_add",   {"radius": 0.5, "depth": 1.0, "vertices": 16}),
    "cone":      ("primitive_cone_add",       {"radius1": 0.5, "radius2": 0.0, "depth": 1.0, "vertices": 16}),
    "plane":     ("primitive_plane_add",      {"size": 1.0}),
    "torus":     ("primitive_torus_add",      {"major_radius": 1.0, "minor_radius": 0.25,
                                                "major_segments": 24, "minor_segments": 12}),
}

SHAPE_ITEMS = [(k, k.capitalize(), "") for k in SHAPES]


# ─── Safe expression evaluator (mirrors src/dedal_mcp/presets/types/safe_eval.py) ──
# Used during composite import to evaluate string expressions like "x/2" against
# the preset's size_defaults. Plugin runs inside Blender and can't import the
# server's safe_eval module, so we duplicate the logic here.

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_ALLOWED_CALLS = {"min": min, "max": max, "abs": abs, "int": int, "float": float, "round": round}


def _safe_eval(expr: str, variables: dict):
    tree = ast.parse(expr, mode="eval")
    return _eval_ast(tree.body, variables)


def _eval_ast(node, variables):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        if node.id in _ALLOWED_CALLS:
            return _ALLOWED_CALLS[node.id]
        raise ValueError(f"unknown name {node.id!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_ast(node.left, variables), _eval_ast(node.right, variables))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_ast(node.operand, variables))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_CALLS:
        return _ALLOWED_CALLS[node.func.id](*[_eval_ast(a, variables) for a in node.args])
    raise ValueError(f"disallowed expression node {type(node).__name__}")


def _eval_value(v, variables, fallback):
    """Evaluate a JSON value that may be a number or expression string.
    Returns *fallback* if evaluation fails (unknown name, etc.) so import is best-effort."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return _safe_eval(v, variables)
        except Exception:
            return fallback
    return fallback


# ─── Helpers ─────────────────────────────────────────────────────────

def _mesh_hash(mesh) -> str:
    """Stable hash of vertex positions (rounded to 6 decimal places)."""
    h = hashlib.sha1()
    for v in mesh.vertices:
        h.update(f"{round(v.co.x, 6)},{round(v.co.y, 6)},{round(v.co.z, 6)};".encode())
    return h.hexdigest()


def _tag_primitive(obj, shape: str, params: dict, color: tuple) -> None:
    """Mark *obj* as a parametric primitive of the given shape."""
    obj["dedal_primitive"] = shape
    obj["dedal_primitive_params"] = json.dumps(params)
    obj["dedal_mesh_hash"] = _mesh_hash(obj.data)
    obj["dedal_color"] = "#{:02X}{:02X}{:02X}".format(
        int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
    )


def _is_still_primitive(obj) -> bool:
    """True iff obj is tagged AND geometry is untouched AND no modifiers."""
    if "dedal_primitive" not in obj:
        return False
    if obj.modifiers:
        return False
    return obj.get("dedal_mesh_hash") == _mesh_hash(obj.data)


def _hex_from_rgba(rgba) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(max(0, min(1, rgba[0])) * 255),
        int(max(0, min(1, rgba[1])) * 255),
        int(max(0, min(1, rgba[2])) * 255),
    )


def _rgba_from_hex(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0, 1.0)


# ─── Operators: add tagged primitives ────────────────────────────────

class DEDAL_OT_add_primitive(Operator):
    """Add a primitive and tag it so DedalMCP can export it as a composite part."""
    bl_idname = "dedal.add_primitive"
    bl_label = "Add Tagged Primitive"
    bl_options = {"REGISTER", "UNDO"}

    shape: EnumProperty(items=SHAPE_ITEMS, name="Shape", default="cube")

    def execute(self, context):
        op_name, params = SHAPES[self.shape]
        op = getattr(bpy.ops.mesh, op_name)
        op(**params)
        obj = context.active_object
        color = context.scene.dedal_props.add_color
        _tag_primitive(obj, self.shape, params, color)
        # Apply vertex color immediately so user sees it
        _paint_vertex_color(obj.data, _hex_from_rgba(color))
        return {"FINISHED"}


def _paint_vertex_color(mesh, hex_color: str) -> None:
    if not mesh.color_attributes:
        mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
    attr = mesh.color_attributes.active_color
    rgba = _rgba_from_hex(hex_color)
    for i in range(len(attr.data)):
        attr.data[i].color = rgba


class DEDAL_OT_mark_primitive(Operator):
    """Tag the active object as a primitive of the chosen shape (user attests it's still pristine)."""
    bl_idname = "dedal.mark_primitive"
    bl_label = "Mark Active as Primitive"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == "MESH"

    def execute(self, context):
        obj = context.active_object
        shape = context.scene.dedal_props.mark_shape
        _, params = SHAPES[shape]
        color = context.scene.dedal_props.add_color
        _tag_primitive(obj, shape, params, color)
        self.report({"INFO"}, f"Marked '{obj.name}' as {shape}")
        return {"FINISHED"}


class DEDAL_OT_clear_tag(Operator):
    """Remove DedalMCP tags from the active object — it will export as mesh_data."""
    bl_idname = "dedal.clear_tag"
    bl_label = "Clear Primitive Tag"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and "dedal_primitive" in context.active_object

    def execute(self, context):
        obj = context.active_object
        for key in ("dedal_primitive", "dedal_primitive_params", "dedal_mesh_hash", "dedal_color"):
            if key in obj:
                del obj[key]
        return {"FINISHED"}


# ─── Export ──────────────────────────────────────────────────────────

def _read_vertex_colors(mesh) -> list[tuple] | None:
    """Return per-vertex (r,g,b,a) by averaging the corner colors at each vertex.
    Returns None if the mesh has no color attribute.
    """
    if not mesh.color_attributes:
        return None
    attr = mesh.color_attributes.active_color
    if attr is None:
        return None

    nv = len(mesh.vertices)
    sums = [[0.0, 0.0, 0.0, 0.0] for _ in range(nv)]
    counts = [0] * nv

    if attr.domain == "POINT":
        for i in range(nv):
            c = attr.data[i].color
            sums[i] = [c[0], c[1], c[2], c[3]]
            counts[i] = 1
    else:  # CORNER
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                v_idx = mesh.loops[loop_idx].vertex_index
                c = attr.data[loop_idx].color
                for k in range(4):
                    sums[v_idx][k] += c[k]
                counts[v_idx] += 1

    result = []
    for i in range(nv):
        if counts[i] == 0:
            result.append((0.5, 0.5, 0.5, 1.0))
        else:
            result.append(tuple(s / counts[i] for s in sums[i]))
    return result


def _evaluated_mesh(obj):
    """Return mesh with modifiers applied (caller must mesh.free() when done)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    return obj_eval.to_mesh()


def _read_active_vertex_hex(obj) -> str:
    """Read the current vertex color from the mesh (handles user vertex-paint edits).
    Falls back to the stored dedal_color custom property, then to gray."""
    mesh = obj.data
    if mesh.color_attributes:
        attr = mesh.color_attributes.active_color
        if attr is not None and len(attr.data) > 0:
            c = attr.data[0].color
            return "#{:02X}{:02X}{:02X}".format(
                int(max(0, min(1, c[0])) * 255),
                int(max(0, min(1, c[1])) * 255),
                int(max(0, min(1, c[2])) * 255),
            )
    return obj.get("dedal_color", "#808080")


def _build_composite_part(obj) -> tuple[dict, str]:
    shape = obj["dedal_primitive"]
    params = json.loads(obj["dedal_primitive_params"])
    color_hex = _read_active_vertex_hex(obj)

    loc = tuple(round(c, 6) for c in obj.location)
    rot_deg = tuple(round(math.degrees(a), 4) for a in obj.rotation_euler)
    scl = tuple(round(c, 6) for c in obj.scale)

    part = {
        "shape": shape,
        "params": params,
    }
    if loc != (0.0, 0.0, 0.0):
        part["location"] = list(loc)
    if rot_deg != (0.0, 0.0, 0.0):
        part["rotation"] = list(rot_deg)
    if scl != (1.0, 1.0, 1.0):
        part["scale"] = list(scl)
    # 'color' is filled in by the caller after zone assignment.
    return part, color_hex


def _build_mesh_data(objs) -> dict:
    """Bake all selected objects into a single mesh_data dict (modifiers applied,
    transforms baked into world coords)."""
    all_verts = []
    all_faces = []
    all_colors = []
    offset = 0

    for obj in objs:
        mesh = _evaluated_mesh(obj)
        matrix = obj.matrix_world

        # Vertices in world coordinates
        for v in mesh.vertices:
            world_co = matrix @ v.co
            all_verts.append((round(world_co.x, 6), round(world_co.y, 6), round(world_co.z, 6)))

        # Faces with offset indices
        for poly in mesh.polygons:
            all_faces.append([offset + i for i in poly.vertices])

        # Vertex colors (may be None)
        vc = _read_vertex_colors(mesh)
        if vc is None:
            vc = [(0.5, 0.5, 0.5, 1.0)] * len(mesh.vertices)
        all_colors.extend(vc)

        offset += len(mesh.vertices)
        obj.to_mesh_clear()

    out = {
        "vertices": all_verts,
        "faces": all_faces,
    }
    # Only include colors if any non-default were present
    if any(c != (0.5, 0.5, 0.5, 1.0) for c in all_colors):
        out["vertex_colors"] = [list(c) for c in all_colors]
    return out


class DEDAL_OT_export_preset(Operator):
    """Export the selected objects as a DedalMCP preset JSON."""
    bl_idname = "dedal.export_preset"
    bl_label = "Export Selection as Preset"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return any(o.type == "MESH" for o in context.selected_objects)

    def invoke(self, context, event):
        props = context.scene.dedal_props
        default_dir = Path.home() / ".dedal" / "presets"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = str(default_dir / f"{props.preset_name or 'untitled'}.json")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        props = context.scene.dedal_props
        name = props.preset_name or Path(self.filepath).stem
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not objs:
            self.report({"ERROR"}, "No mesh objects selected")
            return {"CANCELLED"}

        all_primitives = all(_is_still_primitive(o) for o in objs)

        if all_primitives:
            parts = []
            zone_by_hex: dict[str, str] = {}
            for o in objs:
                part, hex_c = _build_composite_part(o)
                # Assign a zone name per unique color: first → "body", rest → "c1", "c2", …
                if hex_c not in zone_by_hex:
                    zone_by_hex[hex_c] = "body" if not zone_by_hex else f"c{len(zone_by_hex)}"
                part["color"] = zone_by_hex[hex_c]
                parts.append(part)
            default_colors = {zone: hex_c for hex_c, zone in zone_by_hex.items()}
            data = {
                "type": "composite",
                "version": 1,
                "name": name,
                "category": props.preset_category or "custom",
                "description": props.preset_description or f"Composite preset with {len(parts)} part(s)",
                "default_colors": default_colors,
                "size_defaults": {},
                "parts": parts,
                "join": len(parts) > 1,
            }
            kind_msg = f"composite ({len(parts)} parts, {len(default_colors)} color zones)"
        else:
            geom = _build_mesh_data(objs)
            data = {
                "type": "mesh_data",
                "version": 1,
                "name": name,
                "category": props.preset_category or "custom",
                "description": props.preset_description or f"Mesh data ({len(geom['vertices'])} verts)",
                "default_colors": {},
                **geom,
            }
            kind_msg = f"mesh_data ({len(geom['vertices'])} verts, {len(geom['faces'])} faces)"

        Path(self.filepath).write_text(json.dumps(data, indent=2))
        self.report({"INFO"}, f"Exported {kind_msg} to {self.filepath}")
        return {"FINISHED"}


# ─── Import ──────────────────────────────────────────────────────────

class DEDAL_OT_import_preset(Operator):
    """Import a DedalMCP preset JSON into the scene as editable objects."""
    bl_idname = "dedal.import_preset"
    bl_label = "Import Preset"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        default_dir = Path.home() / ".dedal" / "presets"
        self.filepath = str(default_dir) + os.sep
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            data = json.loads(Path(self.filepath).read_text())
        except Exception as e:
            self.report({"ERROR"}, f"Failed to read JSON: {e}")
            return {"CANCELLED"}

        t = data.get("type")
        try:
            if t == "composite":
                n = self._import_composite(context, data)
                self.report({"INFO"}, f"Imported composite with {n} parts")
            elif t == "mesh_data":
                n = self._import_mesh_data(context, data)
                self.report({"INFO"}, f"Imported mesh_data: {n} verts")
            elif t == "script_template":
                self.report({"ERROR"}, "script_template presets cannot be imported visually — edit the JSON directly")
                return {"CANCELLED"}
            else:
                self.report({"ERROR"}, f"Unknown preset type: {t!r}")
                return {"CANCELLED"}
        except (KeyError, ValueError, TypeError) as e:
            self.report({"ERROR"}, f"Failed to import {t}: {type(e).__name__}: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}

    def _import_composite(self, context, data) -> int:
        default_colors = data.get("default_colors", {})
        size_defaults = data.get("size_defaults", {})
        name = data.get("name", "imported")
        # Variables available to expressions: the preset's size_defaults
        variables = dict(size_defaults)

        for i, part in enumerate(data.get("parts", [])):
            shape = part.get("shape")
            if shape not in SHAPES:
                continue
            op_name, default_params = SHAPES[shape]
            # Evaluate each user param against size_defaults; fall back to shape default on error.
            params = dict(default_params)
            for k, v in part.get("params", {}).items():
                params[k] = _eval_value(v, variables, default_params.get(k, 0))
            getattr(bpy.ops.mesh, op_name)(**params)
            obj = context.active_object
            obj.name = f"{name}_part_{i}"

            loc_raw = part.get("location", [0, 0, 0])
            rot_raw = part.get("rotation", [0, 0, 0])
            scl_raw = part.get("scale", [1, 1, 1])
            obj.location = [_eval_value(v, variables, 0.0) for v in loc_raw]
            obj.rotation_euler = [math.radians(_eval_value(v, variables, 0.0)) for v in rot_raw]
            obj.scale = [_eval_value(v, variables, 1.0) for v in scl_raw]

            zone = part.get("color")
            hex_c = default_colors.get(zone, "#808080") if zone else "#808080"
            _paint_vertex_color(obj.data, hex_c)
            _tag_primitive(obj, shape, params, _rgba_from_hex(hex_c))
        return len(data.get("parts", []))

    def _import_mesh_data(self, context, data) -> int:
        if "vertices" not in data or "faces" not in data:
            raise KeyError("mesh_data missing 'vertices' or 'faces'")
        verts = [tuple(v) for v in data["vertices"]]
        faces = [tuple(f) for f in data["faces"]]
        name = data.get("name", "imported")
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)

        vcolors = data.get("vertex_colors")
        if vcolors:
            if len(vcolors) != len(verts):
                raise ValueError(f"vertex_colors length {len(vcolors)} != vertices {len(verts)}")
            if not mesh.color_attributes:
                mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
            attr = mesh.color_attributes.active_color
            for poly in mesh.polygons:
                for loop_idx in poly.loop_indices:
                    v_idx = mesh.loops[loop_idx].vertex_index
                    c = vcolors[v_idx]
                    rgba = tuple(c) if len(c) == 4 else (c[0], c[1], c[2], 1.0)
                    attr.data[loop_idx].color = rgba
        return len(verts)


# ─── Properties + Panel ──────────────────────────────────────────────

class DedalProps(PropertyGroup):
    add_color: FloatVectorProperty(
        name="Color", subtype="COLOR", default=(0.5, 0.5, 0.5),
        min=0.0, max=1.0, size=3,
        description="Vertex color applied to newly added primitives",
    )
    mark_shape: EnumProperty(items=SHAPE_ITEMS, name="Mark as", default="cube")
    preset_name: StringProperty(name="Name", default="my_preset")
    preset_category: StringProperty(name="Category", default="custom")
    preset_description: StringProperty(name="Description", default="")


class DEDAL_PT_main(Panel):
    bl_label = "DedalMCP Preset Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DedalMCP"

    def draw(self, context):
        layout = self.layout
        props = context.scene.dedal_props

        # — Add primitive —
        box = layout.box()
        box.label(text="Add Primitive", icon="MESH_CUBE")
        box.prop(props, "add_color")
        grid = box.grid_flow(columns=2, even_columns=True)
        for shape in SHAPES:
            op = grid.operator("dedal.add_primitive", text=shape.capitalize())
            op.shape = shape

        # — Mark / clear tag —
        box = layout.box()
        box.label(text="Tag Existing Object", icon="OUTLINER_DATA_MESH")
        box.prop(props, "mark_shape")
        row = box.row(align=True)
        row.operator("dedal.mark_primitive", text="Mark", icon="CHECKMARK")
        row.operator("dedal.clear_tag", text="Clear", icon="X")

        obj = context.active_object
        if obj is not None and "dedal_primitive" in obj:
            status_box = box.box()
            shape = obj["dedal_primitive"]
            if _is_still_primitive(obj):
                status_box.label(text=f"✓ {shape} (parametric)", icon="CHECKMARK")
            else:
                reason = "modifiers" if obj.modifiers else "geometry edited"
                status_box.label(text=f"⚠ {shape} ({reason})", icon="ERROR")
                status_box.label(text="Will export as mesh_data")

        # — Export —
        box = layout.box()
        box.label(text="Export Preset", icon="EXPORT")
        box.prop(props, "preset_name")
        box.prop(props, "preset_category")
        box.prop(props, "preset_description")
        box.operator("dedal.export_preset", icon="FILE_TICK")

        # — Import —
        box = layout.box()
        box.label(text="Import Preset", icon="IMPORT")
        box.operator("dedal.import_preset", icon="FILEBROWSER")


# ─── Registration ────────────────────────────────────────────────────

_CLASSES = (
    DedalProps,
    DEDAL_OT_add_primitive,
    DEDAL_OT_mark_primitive,
    DEDAL_OT_clear_tag,
    DEDAL_OT_export_preset,
    DEDAL_OT_import_preset,
    DEDAL_PT_main,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.dedal_props = bpy.props.PointerProperty(type=DedalProps)


def unregister():
    del bpy.types.Scene.dedal_props
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
