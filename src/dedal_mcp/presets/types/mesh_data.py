"""Interpreter for the ``mesh_data/v1`` preset type.

Raw geometry exported from Blender by the companion plugin. Carries vertices,
face indices, and optional per-vertex colors directly in the JSON. Used when
the user has edited a mesh beyond what the ``composite`` declarative type can
express (vertex edits in edit mode, applied modifiers, etc.).

The ``size`` and ``colors`` parameters of ``create_mesh`` are intentionally
**not respected** for this type — the geometry is baked at export time. To
change anything, re-edit and re-export from Blender.
"""

from __future__ import annotations

from typing import Any, Callable

from dedal_mcp.presets.types import register


class MeshDataError(ValueError):
    pass


def _validate_geometry(data: dict) -> tuple[list, list, list | None]:
    verts = data.get("vertices")
    faces = data.get("faces")
    vcolors = data.get("vertex_colors")

    if not isinstance(verts, list) or not verts:
        raise MeshDataError("'vertices' must be a non-empty list of [x,y,z] arrays")
    for i, v in enumerate(verts):
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise MeshDataError(f"vertices[{i}] must be a 3-element list, got {v!r}")
        for c in v:
            if not isinstance(c, (int, float)):
                raise MeshDataError(f"vertices[{i}] contains non-numeric {c!r}")

    if not isinstance(faces, list) or not faces:
        raise MeshDataError("'faces' must be a non-empty list of index arrays")
    nv = len(verts)
    for i, f in enumerate(faces):
        if not isinstance(f, (list, tuple)) or len(f) < 3:
            raise MeshDataError(f"faces[{i}] must have at least 3 indices, got {f!r}")
        for idx in f:
            if not isinstance(idx, int) or idx < 0 or idx >= nv:
                raise MeshDataError(
                    f"faces[{i}] index {idx!r} out of range [0,{nv})"
                )

    if vcolors is not None:
        if not isinstance(vcolors, list) or len(vcolors) != nv:
            raise MeshDataError(
                f"'vertex_colors' (if present) must have one entry per vertex "
                f"({nv}), got {len(vcolors) if isinstance(vcolors, list) else type(vcolors).__name__}"
            )
        for i, c in enumerate(vcolors):
            if not isinstance(c, (list, tuple)) or len(c) not in (3, 4):
                raise MeshDataError(
                    f"vertex_colors[{i}] must be [r,g,b] or [r,g,b,a], got {c!r}"
                )

    return verts, faces, vcolors


def _make_builder(data: dict) -> Callable[[str, dict, dict], str]:
    verts, faces, vcolors = _validate_geometry(data)

    # Normalize vertex colors to 4-component, clamp to [0,1].
    norm_colors: list[tuple] | None = None
    if vcolors is not None:
        norm_colors = []
        for c in vcolors:
            r, g, b = float(c[0]), float(c[1]), float(c[2])
            a = float(c[3]) if len(c) == 4 else 1.0
            norm_colors.append((
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            ))

    # Pre-format the geometry as Python literals so the generated script is
    # self-contained (no eval of the JSON at runtime in Blender).
    verts_lit = "[" + ", ".join(f"({v[0]!r}, {v[1]!r}, {v[2]!r})" for v in verts) + "]"
    faces_lit = "[" + ", ".join("(" + ", ".join(str(i) for i in f) + ")" for f in faces) + "]"

    def builder(name: str, size: dict, colors: dict) -> str:
        # size/colors deliberately ignored — see module docstring.
        lines = [
            f"mesh = bpy.data.meshes.new({name!r})",
            f"verts = {verts_lit}",
            f"faces = {faces_lit}",
            "mesh.from_pydata(verts, [], faces)",
            "mesh.update(calc_edges=True)",
            f"obj = bpy.data.objects.new({name!r}, mesh)",
            "bpy.context.collection.objects.link(obj)",
            "bpy.context.view_layer.objects.active = obj",
            "obj.select_set(True)",
        ]
        if norm_colors is not None:
            colors_lit = "[" + ", ".join(repr(c) for c in norm_colors) + "]"
            lines.extend([
                f"_per_vertex = {colors_lit}",
                "if not mesh.color_attributes:",
                "    mesh.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')",
                "_col = mesh.color_attributes.active_color",
                "for poly in mesh.polygons:",
                "    for loop_idx in poly.loop_indices:",
                "        v_idx = mesh.loops[loop_idx].vertex_index",
                "        _col.data[loop_idx].color = _per_vertex[v_idx]",
            ])
        return "\n".join(lines) + "\n"

    return builder


def interpret(data: dict) -> dict:
    required = {"name", "type", "version", "vertices", "faces"}
    missing = required - set(data)
    if missing:
        raise MeshDataError(f"mesh_data preset missing required fields: {sorted(missing)}")

    builder = _make_builder(data)
    return {
        "description": data.get("description", ""),
        "default_colors": dict(data.get("default_colors", {})),
        "category": data.get("category", "custom"),
        "builder": builder,
    }


register("mesh_data", 1, interpret)
