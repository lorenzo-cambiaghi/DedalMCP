"""Interpreter for the ``geometry_nodes/v1`` preset type.

Invokes a Geometry Nodes tree from a user-authored .blend file. The preset
JSON declares which blend + node group to use, what base geometry to host the
modifier on, and which inputs the AI can pass via ``create_mesh``. Inputs may
be scalars (float/int/bool/string/vector/color), constructed geometries
(curve/points/mesh) or per-element attributes on the base geometry.

Validation is **lazy** for the blend file itself — the loader registers the
preset without opening the .blend, and any missing-blend or missing-socket
error surfaces at first invocation with a clear MCP-level message. Schema is
validated at load time so malformed JSON fails fast.

For security, ``use_scripts_auto_execute`` is force-disabled in the emitted
script before any ``libraries.load`` call.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from dedal_mcp.presets.types import register
from dedal_mcp.presets.types.composite import _SHAPE_OPS, _SHAPE_DEFAULTS, _format_num


# ─── Constants ───────────────────────────────────────────────────────

_SCALAR_TYPES = {"float", "int", "bool", "string", "vector", "color"}
_ARRAY_TYPES = {"curve", "points", "mesh"}
_ATTRIBUTE_TYPE = "attribute"

_ATTR_DATA_TYPES = {"FLOAT", "INT", "BOOLEAN", "FLOAT_VECTOR", "FLOAT_COLOR", "BYTE_COLOR"}
_ATTR_DOMAINS = {"POINT", "EDGE", "FACE", "CORNER"}
_PER_ELEMENT_ATTR_TYPES = {"float", "int", "bool", "vector", "color"}

_BASE_GEOMETRY_RE = re.compile(r"^(?:primitive:(?P<prim>\w+)|preset:(?P<preset>[\w-]+))$")
_BLEND_FILENAME_RE = re.compile(r"^[\w.\-]+\.blend$")

_MAX_DEPTH = 5

# Module-level recursion stack for base_geometry preset references (single-threaded server).
_BUILDING_STACK: list[str] = []


class GNError(ValueError):
    """Raised on geometry_nodes/v1 schema or build-time errors."""


# ─── Schema validation (load time) ───────────────────────────────────

def _validate_schema(data: dict) -> None:
    name = data.get("name", "<unnamed>")
    for f in ("blend", "node_group"):
        if f not in data or not isinstance(data[f], str) or not data[f].strip():
            raise GNError(f"preset {name!r}: missing/empty required field {f!r}")

    blend = data["blend"]
    if not _BLEND_FILENAME_RE.match(blend):
        raise GNError(
            f"preset {name!r}: 'blend' must be a bare filename ending in .blend "
            f"(no path separators, no '..'), got {blend!r}"
        )

    base = data.get("base_geometry", "primitive:empty")
    if not isinstance(base, str) or not _BASE_GEOMETRY_RE.match(base):
        raise GNError(
            f"preset {name!r}: 'base_geometry' must be 'primitive:<shape>' or "
            f"'preset:<name>', got {base!r}"
        )
    m = _BASE_GEOMETRY_RE.match(base)
    if m.group("prim") and m.group("prim") not in (set(_SHAPE_OPS) | {"empty"}):
        raise GNError(
            f"preset {name!r}: unknown primitive {m.group('prim')!r}. "
            f"Known: {sorted(set(_SHAPE_OPS) | {'empty'})}"
        )

    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        raise GNError(f"preset {name!r}: 'inputs' must be a dict")
    for socket_name, spec in inputs.items():
        if not isinstance(spec, dict) or "type" not in spec:
            raise GNError(f"preset {name!r}: input {socket_name!r} must be a dict with 'type'")
        _validate_input_spec(name, socket_name, spec)


def _validate_input_spec(preset_name: str, socket_name: str, spec: dict) -> None:
    t = spec["type"]
    if t in _SCALAR_TYPES:
        if "default" not in spec:
            raise GNError(f"preset {preset_name!r}: scalar input {socket_name!r} missing 'default'")
        _check_scalar_value(preset_name, socket_name, t, spec["default"])
    elif t in _ARRAY_TYPES:
        attrs = spec.get("attributes", {})
        if not isinstance(attrs, dict):
            raise GNError(f"preset {preset_name!r}: {socket_name!r}.attributes must be a dict")
        for an, at in attrs.items():
            if at not in _PER_ELEMENT_ATTR_TYPES:
                raise GNError(
                    f"preset {preset_name!r}: {socket_name!r}.attributes[{an!r}] type "
                    f"{at!r} not in {sorted(_PER_ELEMENT_ATTR_TYPES)}"
                )
    elif t == _ATTRIBUTE_TYPE:
        dt = spec.get("data_type")
        dom = spec.get("domain")
        if dt not in _ATTR_DATA_TYPES:
            raise GNError(
                f"preset {preset_name!r}: attribute {socket_name!r}.data_type {dt!r} "
                f"not in {sorted(_ATTR_DATA_TYPES)}"
            )
        if dom not in _ATTR_DOMAINS:
            raise GNError(
                f"preset {preset_name!r}: attribute {socket_name!r}.domain {dom!r} "
                f"not in {sorted(_ATTR_DOMAINS)}"
            )
        if "default" not in spec:
            raise GNError(f"preset {preset_name!r}: attribute {socket_name!r} missing 'default'")
    else:
        known = sorted(_SCALAR_TYPES | _ARRAY_TYPES | {_ATTRIBUTE_TYPE})
        raise GNError(
            f"preset {preset_name!r}: input {socket_name!r} unknown type {t!r}. Known: {known}"
        )


def _check_scalar_value(preset_name: str, socket_name: str, t: str, v: Any) -> None:
    if t == "float" and not isinstance(v, (int, float)):
        raise GNError(f"preset {preset_name!r}: {socket_name!r} default must be number, got {v!r}")
    if t == "int" and not isinstance(v, int):
        raise GNError(f"preset {preset_name!r}: {socket_name!r} default must be int, got {v!r}")
    if t == "bool" and not isinstance(v, bool):
        raise GNError(f"preset {preset_name!r}: {socket_name!r} default must be bool, got {v!r}")
    if t == "string" and not isinstance(v, str):
        raise GNError(f"preset {preset_name!r}: {socket_name!r} default must be string, got {v!r}")
    if t == "vector":
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise GNError(f"preset {preset_name!r}: {socket_name!r} default must be [x,y,z], got {v!r}")
    if t == "color":
        if not isinstance(v, str) or not v.startswith("#") or len(v) not in (4, 7, 9):
            raise GNError(
                f"preset {preset_name!r}: {socket_name!r} default must be hex color "
                f"(#RGB/#RRGGBB/#RRGGBBAA), got {v!r}"
            )


# ─── Helper bpy code (emitted inline in every generated script) ──────

_HELPER_FUNCTIONS = r'''
def _gn_hex_to_rgba(hex_str):
    h = hex_str.lstrip('#')
    if len(h) == 3:
        r, g, b = (int(h[i]*2, 16)/255.0 for i in range(3))
        return (r, g, b, 1.0)
    if len(h) == 6:
        return (int(h[0:2],16)/255.0, int(h[2:4],16)/255.0, int(h[4:6],16)/255.0, 1.0)
    return (int(h[0:2],16)/255.0, int(h[2:4],16)/255.0, int(h[4:6],16)/255.0, int(h[6:8],16)/255.0)


def _gn_set_input_by_name(modifier, node_group, socket_name, value):
    for item in node_group.interface.items_tree:
        if getattr(item, 'item_type', None) == 'SOCKET' and getattr(item, 'in_out', None) == 'INPUT' and item.name == socket_name:
            modifier[item.identifier] = value
            return
    raise RuntimeError("GN input socket %r not found in node group %r" % (socket_name, node_group.name))


def _gn_build_curve_object(name, positions, tangents=None, attributes=None):
    if not positions:
        raise RuntimeError("curve input %r got empty 'positions'" % name)
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(positions) - 1)
    for i, pos in enumerate(positions):
        bp = spline.bezier_points[i]
        bp.co = tuple(pos)
        if tangents and i < len(tangents):
            t = tangents[i]
            bp.handle_right = (pos[0]+t[0], pos[1]+t[1], pos[2]+t[2])
            bp.handle_left  = (pos[0]-t[0], pos[1]-t[1], pos[2]-t[2])
            bp.handle_right_type = 'FREE'
            bp.handle_left_type = 'FREE'
        else:
            bp.handle_right_type = 'AUTO'
            bp.handle_left_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    if attributes:
        _gn_write_attributes(obj.data, attributes, len(positions))
    return obj


def _gn_build_point_cloud(name, positions, attributes=None):
    if not positions:
        raise RuntimeError("points input %r got empty 'positions'" % name)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(p) for p in positions], [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if attributes:
        _gn_write_attributes(mesh, attributes, len(positions))
    return obj


def _gn_build_mesh_input(name, verts, faces, attributes=None):
    if not verts:
        raise RuntimeError("mesh input %r got empty 'vertices'" % name)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in (faces or [])])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if attributes:
        _gn_write_attributes(mesh, attributes, len(verts))
    return obj


_GN_ATTR_TYPE_MAP = {
    'float':  ('FLOAT',         'value'),
    'int':    ('INT',           'value'),
    'bool':   ('BOOLEAN',       'value'),
    'vector': ('FLOAT_VECTOR',  'vector'),
    'color':  ('FLOAT_COLOR',   'color'),
}


def _gn_write_attributes(geom_data, type_to_values, n_elements):
    """type_to_values maps attr_name -> (type_str, values_list)."""
    for attr_name, (type_str, values) in type_to_values.items():
        bl_type, prop = _GN_ATTR_TYPE_MAP[type_str]
        attr = geom_data.attributes.new(name=attr_name, type=bl_type, domain='POINT')
        if len(values) != n_elements:
            raise RuntimeError(
                "attribute %r got %d values but geometry has %d points" % (attr_name, len(values), n_elements)
            )
        for i, v in enumerate(values):
            if prop == 'vector':
                attr.data[i].vector = tuple(v)
            elif prop == 'color':
                attr.data[i].color = tuple(v) if len(v) == 4 else (v[0], v[1], v[2], 1.0)
            else:
                attr.data[i].value = v


def _gn_write_named_attribute(obj, name, data_type, domain, values):
    """Write a Named Attribute on *obj*'s mesh data. *values* may be a scalar
    (broadcast to all elements) or a list (must match domain length)."""
    attr = obj.data.attributes.get(name)
    if attr is None:
        attr = obj.data.attributes.new(name=name, type=data_type, domain=domain)
    n = len(attr.data)
    if isinstance(values, list):
        if len(values) != n:
            raise RuntimeError(
                "named attribute %r expected %d values for domain %s, got %d" % (name, n, domain, len(values))
            )
        for i, v in enumerate(values):
            d = attr.data[i]
            if hasattr(d, 'value'):
                d.value = v
            elif hasattr(d, 'vector'):
                d.vector = tuple(v)
            elif hasattr(d, 'color'):
                d.color = tuple(v) if len(v) == 4 else (v[0], v[1], v[2], 1.0)
    else:
        for i in range(n):
            d = attr.data[i]
            if hasattr(d, 'value'):
                d.value = values
            elif hasattr(d, 'vector'):
                d.vector = tuple(values) if isinstance(values, (list, tuple)) else (values, values, values)
            elif hasattr(d, 'color'):
                d.color = tuple(values) if isinstance(values, (list, tuple)) and len(values) >= 3 else (0.5, 0.5, 0.5, 1.0)
'''


# ─── Code emitters ───────────────────────────────────────────────────

def _emit_primitive(shape: str, host_name: str) -> str:
    """Emit bpy code that creates a primitive of *shape*, assigns it to ``host``.

    'empty' creates an empty MESH object (not a Blender Empty) so that
    `modifier_apply` works — Empty objects have no mesh data and cannot be the
    target of a modifier apply operation.
    """
    if shape == "empty":
        return (
            f"_empty_mesh = bpy.data.meshes.new({host_name!r})\n"
            f"host = bpy.data.objects.new({host_name!r}, _empty_mesh)\n"
            f"bpy.context.collection.objects.link(host)\n"
        )
    op_template, _ = _SHAPE_OPS[shape]
    defaults = {k: _format_num(v) for k, v in _SHAPE_DEFAULTS[shape].items()}
    op_call = op_template.format(**defaults)
    return (
        f"{op_call}\n"
        f"host = bpy.context.active_object\n"
        f"host.name = {host_name!r}\n"
    )


def _emit_base_geometry(spec: str, host_name: str, current_preset: str) -> str:
    """Emit bpy code for the base_geometry, recursing into other presets if needed."""
    m = _BASE_GEOMETRY_RE.match(spec)
    if m.group("prim"):
        return _emit_primitive(m.group("prim"), host_name)

    # preset: recursion
    target_name = m.group("preset").lower()
    if target_name in _BUILDING_STACK:
        chain = " -> ".join(_BUILDING_STACK + [target_name])
        raise GNError(f"Cycle detected in base_geometry: {chain}")
    if len(_BUILDING_STACK) >= _MAX_DEPTH:
        raise GNError(
            f"base_geometry recursion exceeded max depth ({_MAX_DEPTH}): "
            f"{' -> '.join(_BUILDING_STACK + [target_name])}"
        )

    # Lazy import — PRESETS is populated by loader before any builder runs
    from dedal_mcp.presets import get_preset
    target = get_preset(target_name)
    if target is None:
        raise GNError(
            f"preset {current_preset!r}: base_geometry references unknown preset "
            f"'preset:{target_name}'"
        )

    # Push & recurse; the target builder may also push/pop if it's also GN.
    _BUILDING_STACK.append(current_preset)
    try:
        nested_code = target["builder"](host_name, {}, {})
    finally:
        _BUILDING_STACK.pop()

    # The other interpreters bind the final object to `obj`; we want `host`.
    return nested_code + "\nhost = obj\n"


def _emit_scalar_assignment(socket_name: str, t: str, value: Any) -> str:
    if t == "color":
        # Emit a function call so the conversion happens at runtime
        return f"_gn_set_input_by_name(mod, ng, {socket_name!r}, _gn_hex_to_rgba({value!r}))"
    if t == "vector":
        v = tuple(float(x) for x in value)
        return f"_gn_set_input_by_name(mod, ng, {socket_name!r}, {v!r})"
    return f"_gn_set_input_by_name(mod, ng, {socket_name!r}, {value!r})"


def _emit_curve_input(host_name: str, socket_name: str, payload: dict, spec: dict) -> str:
    positions = payload.get("positions", [])
    tangents = payload.get("tangents")
    attrs_decl = spec.get("attributes", {})
    attrs_payload: dict[str, tuple[str, list]] = {}
    for an, at in attrs_decl.items():
        if an in payload:
            attrs_payload[an] = (at, payload[an])
    tmp_name = f"{host_name}__{socket_name}"
    return (
        f"_tmp = _gn_build_curve_object({tmp_name!r}, {positions!r}, "
        f"tangents={tangents!r}, attributes={attrs_payload!r})\n"
        f"_temp_objects.append({tmp_name!r})\n"
        f"_gn_set_input_by_name(mod, ng, {socket_name!r}, _tmp)\n"
    )


def _emit_points_input(host_name: str, socket_name: str, payload: dict, spec: dict) -> str:
    positions = payload.get("positions", [])
    attrs_decl = spec.get("attributes", {})
    attrs_payload: dict[str, tuple[str, list]] = {}
    for an, at in attrs_decl.items():
        if an in payload:
            attrs_payload[an] = (at, payload[an])
    tmp_name = f"{host_name}__{socket_name}"
    return (
        f"_tmp = _gn_build_point_cloud({tmp_name!r}, {positions!r}, "
        f"attributes={attrs_payload!r})\n"
        f"_temp_objects.append({tmp_name!r})\n"
        f"_gn_set_input_by_name(mod, ng, {socket_name!r}, _tmp)\n"
    )


def _emit_mesh_input(host_name: str, socket_name: str, payload: dict, spec: dict) -> str:
    verts = payload.get("vertices", [])
    faces = payload.get("faces", [])
    attrs_decl = spec.get("attributes", {})
    attrs_payload: dict[str, tuple[str, list]] = {}
    for an, at in attrs_decl.items():
        if an in payload:
            attrs_payload[an] = (at, payload[an])
    tmp_name = f"{host_name}__{socket_name}"
    return (
        f"_tmp = _gn_build_mesh_input({tmp_name!r}, {verts!r}, {faces!r}, "
        f"attributes={attrs_payload!r})\n"
        f"_temp_objects.append({tmp_name!r})\n"
        f"_gn_set_input_by_name(mod, ng, {socket_name!r}, _tmp)\n"
    )


def _emit_attribute_assignment(socket_name: str, spec: dict, value: Any) -> str:
    return (
        f"_gn_write_named_attribute(host, {socket_name!r}, "
        f"{spec['data_type']!r}, {spec['domain']!r}, {value!r})\n"
    )


# ─── Builder factory ─────────────────────────────────────────────────

def _make_builder(data: dict) -> Callable[[str, dict, dict], str]:
    _validate_schema(data)
    preset_name = data["name"]
    blend_filename = data["blend"]
    node_group_name = data["node_group"]
    base_geom = data.get("base_geometry", "primitive:empty")
    inputs = data.get("inputs", {})

    def builder(name: str, size: dict, colors: dict) -> str:
        # size carries all user inputs; colors is unused (GN colors come via 'color' input type).
        size = size or {}

        # Resolve blend path lazily; FileNotFoundError propagates with clear message.
        from dedal_mcp.presets.loader import resolve_blend_path
        blend_path = resolve_blend_path(blend_filename)

        parts: list[str] = []
        parts.append(_HELPER_FUNCTIONS)
        parts.append("")
        parts.append("# 1. Disable script auto-exec for security before loading external blend")
        parts.append("bpy.context.preferences.filepaths.use_scripts_auto_execute = False")
        parts.append("")
        parts.append("# 2. Append node group from the .blend file")
        parts.append(f"with bpy.data.libraries.load({str(blend_path)!r}, link=False) as (_src, _dst):")
        parts.append(f"    if {node_group_name!r} not in _src.node_groups:")
        parts.append(
            f"        raise RuntimeError("
            f"'Node group ' + {node_group_name!r} + ' not found in ' + {blend_filename!r})"
        )
        parts.append(f"    _dst.node_groups = [{node_group_name!r}]")
        parts.append(f"ng = bpy.data.node_groups[{node_group_name!r}]")
        parts.append("")
        parts.append("# 3. Build base_geometry as `host`")
        parts.append(_emit_base_geometry(base_geom, name, preset_name))
        parts.append("")
        parts.append("# 4. Attach Geometry Nodes modifier")
        parts.append("mod = host.modifiers.new(name='GN', type='NODES')")
        parts.append("mod.node_group = ng")
        parts.append("")
        parts.append("# 5. Track temp objects for cleanup before export")
        parts.append("_temp_objects = []")
        parts.append("")
        parts.append("# 6. Apply inputs")
        for socket_name, spec in inputs.items():
            t = spec["type"]
            if t in _SCALAR_TYPES:
                value = size.get(socket_name, spec["default"])
                parts.append(_emit_scalar_assignment(socket_name, t, value))
            elif t == "curve":
                if socket_name not in size:
                    continue  # curve inputs are optional; if absent, GN tree uses its own default
                payload = size[socket_name]
                if not isinstance(payload, dict):
                    raise GNError(
                        f"input {socket_name!r} (curve) expects a dict with 'positions' "
                        f"and optional 'tangents'/attribute arrays, got {type(payload).__name__}"
                    )
                parts.append(_emit_curve_input(name, socket_name, payload, spec))
            elif t == "points":
                if socket_name not in size:
                    continue
                payload = size[socket_name]
                if not isinstance(payload, dict):
                    raise GNError(
                        f"input {socket_name!r} (points) expects a dict with 'positions' "
                        f"and optional attribute arrays, got {type(payload).__name__}"
                    )
                parts.append(_emit_points_input(name, socket_name, payload, spec))
            elif t == "mesh":
                if socket_name not in size:
                    continue
                payload = size[socket_name]
                if not isinstance(payload, dict):
                    raise GNError(
                        f"input {socket_name!r} (mesh) expects a dict with 'vertices', "
                        f"'faces' and optional attribute arrays, got {type(payload).__name__}"
                    )
                parts.append(_emit_mesh_input(name, socket_name, payload, spec))
            elif t == _ATTRIBUTE_TYPE:
                value = size.get(socket_name, spec["default"])
                parts.append(_emit_attribute_assignment(socket_name, spec, value))

        parts.append("")
        parts.append("# 7. Apply the modifier (bake to mesh)")
        parts.append("bpy.ops.object.select_all(action='DESELECT')")
        parts.append("host.select_set(True)")
        parts.append("bpy.context.view_layer.objects.active = host")
        parts.append("bpy.ops.object.modifier_apply(modifier='GN')")
        parts.append("")
        parts.append("# 8. Cleanup temporary input objects")
        parts.append("for _tn in _temp_objects:")
        parts.append("    _to = bpy.data.objects.get(_tn)")
        parts.append("    if _to is not None:")
        parts.append("        bpy.data.objects.remove(_to, do_unlink=True)")
        parts.append("")
        parts.append("# 9. Expose final object for the export code")
        parts.append("obj = host")
        parts.append(f"obj.name = {name!r}")

        return "\n".join(parts) + "\n"

    return builder


# ─── Entry point ─────────────────────────────────────────────────────

def interpret(data: dict) -> dict:
    required = {"name", "type", "version", "blend", "node_group"}
    missing = required - set(data)
    if missing:
        raise GNError(f"geometry_nodes preset missing required fields: {sorted(missing)}")

    builder = _make_builder(data)
    return {
        "description": data.get("description", ""),
        "default_colors": dict(data.get("default_colors", {})),
        "category": data.get("category", "custom"),
        "builder": builder,
    }


register("geometry_nodes", 1, interpret)
