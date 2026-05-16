"""Interpreter for the ``composite/v1`` preset type.

A composite preset is a list of primitive parts (cube/sphere/cylinder/...)
optionally placed, scaled, colored, and joined. All numeric fields may be
either literal numbers or short arithmetic expressions over the size dict
(evaluated by safe_eval, no eval/exec).
"""

from __future__ import annotations

from typing import Any, Callable

from dedal_mcp.presets.types import register
from dedal_mcp.presets.types.safe_eval import eval_value


# ── Shape library ────────────────────────────────────────────────────
# Each entry maps shape name -> (bpy_call_template, allowed_param_keys).
# bpy_call_template uses {name} placeholders filled with the *resolved* params.

_SHAPE_OPS: dict[str, tuple[str, set[str]]] = {
    "cube": (
        "bpy.ops.mesh.primitive_cube_add(size={size})",
        {"size"},
    ),
    "uv_sphere": (
        "bpy.ops.mesh.primitive_uv_sphere_add(radius={radius}, segments={segments}, ring_count={ring_count})",
        {"radius", "segments", "ring_count"},
    ),
    "sphere": (
        "bpy.ops.mesh.primitive_uv_sphere_add(radius={radius}, segments={segments}, ring_count={ring_count})",
        {"radius", "segments", "ring_count"},
    ),
    "icosphere": (
        "bpy.ops.mesh.primitive_ico_sphere_add(radius={radius}, subdivisions={subdivisions})",
        {"radius", "subdivisions"},
    ),
    "cylinder": (
        "bpy.ops.mesh.primitive_cylinder_add(radius={radius}, depth={depth}, vertices={vertices})",
        {"radius", "depth", "vertices"},
    ),
    "cone": (
        "bpy.ops.mesh.primitive_cone_add(radius1={radius1}, radius2={radius2}, depth={depth}, vertices={vertices})",
        {"radius1", "radius2", "depth", "vertices"},
    ),
    "plane": (
        "bpy.ops.mesh.primitive_plane_add(size={size})",
        {"size"},
    ),
    "torus": (
        "bpy.ops.mesh.primitive_torus_add(major_radius={major_radius}, minor_radius={minor_radius}, major_segments={major_segments}, minor_segments={minor_segments})",
        {"major_radius", "minor_radius", "major_segments", "minor_segments"},
    ),
}

_SHAPE_DEFAULTS: dict[str, dict[str, Any]] = {
    "cube": {"size": 1},
    "uv_sphere": {"radius": 1, "segments": 16, "ring_count": 12},
    "sphere": {"radius": 1, "segments": 16, "ring_count": 12},
    "icosphere": {"radius": 1, "subdivisions": 2},
    "cylinder": {"radius": 1, "depth": 2, "vertices": 16},
    "cone": {"radius1": 1, "radius2": 0, "depth": 2, "vertices": 16},
    "plane": {"size": 1},
    "torus": {"major_radius": 1, "minor_radius": 0.25, "major_segments": 24, "minor_segments": 12},
}


# ── Builder generator ────────────────────────────────────────────────

def _resolve_vec(value: Any, variables: dict, default: tuple) -> tuple:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"Expected 3-element list, got {value!r}")
    return tuple(eval_value(v, variables) for v in value)


def _format_num(n: Any) -> str:
    if isinstance(n, bool):
        return repr(n)
    if isinstance(n, int):
        return str(n)
    return repr(float(n))


def _build_part(part: dict, index: int, variables: dict) -> tuple[str, str]:
    """Return (code, part_var_name). Does NOT name the part; the builder
    assigns the final name once at the end (single object) or after join.
    """
    shape = part.get("shape")
    if shape not in _SHAPE_OPS:
        raise ValueError(f"Unknown shape {shape!r}. Known: {sorted(_SHAPE_OPS)}")

    op_template, allowed = _SHAPE_OPS[shape]
    raw_params = dict(_SHAPE_DEFAULTS[shape])
    user_params = part.get("params", {})
    extra = set(user_params) - allowed
    if extra:
        raise ValueError(f"Shape {shape!r} got unknown params: {sorted(extra)}")
    for k, v in user_params.items():
        raw_params[k] = eval_value(v, variables)

    op_call = op_template.format(**{k: _format_num(v) for k, v in raw_params.items()})

    scale = _resolve_vec(part.get("scale"), variables, (1.0, 1.0, 1.0))
    location = _resolve_vec(part.get("location"), variables, (0.0, 0.0, 0.0))
    color = part.get("color")

    part_var = f"p_{index}"

    lines = [
        f"{op_call}",
        f"{part_var} = bpy.context.active_object",
    ]
    if scale != (1.0, 1.0, 1.0):
        lines.append(f"{part_var}.scale = ({_format_num(scale[0])}, {_format_num(scale[1])}, {_format_num(scale[2])})")
        lines.append("bpy.ops.object.transform_apply(scale=True)")
    if location != (0.0, 0.0, 0.0):
        lines.append(f"{part_var}.location = ({_format_num(location[0])}, {_format_num(location[1])}, {_format_num(location[2])})")
    if color is not None:
        # color is a key into the resolved colors dict; resolution happens at builder time.
        lines.append(f"_set_vertex_color_all({part_var}, {color!r})")

    return "\n".join(lines), part_var


def _make_builder(data: dict) -> Callable[[str, dict, dict], str]:
    parts_def = data.get("parts", [])
    if not isinstance(parts_def, list) or not parts_def:
        raise ValueError(f"composite preset {data.get('name')!r} requires non-empty 'parts' list")

    size_defaults = data.get("size_defaults", {})
    default_colors = data.get("default_colors", {})
    do_join = bool(data.get("join", len(parts_def) > 1))

    # Validate each part schema up-front (without numeric resolution — we need size at build time).
    for i, p in enumerate(parts_def):
        if "shape" not in p:
            raise ValueError(f"parts[{i}] missing 'shape'")
        if p["shape"] not in _SHAPE_OPS:
            raise ValueError(f"parts[{i}] unknown shape {p['shape']!r}")
        if "color" in p and p["color"] not in default_colors:
            raise ValueError(
                f"parts[{i}] references color zone {p['color']!r} "
                f"not declared in default_colors {sorted(default_colors)}"
            )

    def builder(name: str, size: dict, colors: dict) -> str:
        variables = dict(size_defaults)
        variables.update({k: v for k, v in size.items() if v is not None})
        resolved_colors = dict(default_colors)
        resolved_colors.update({k: v for k, v in colors.items() if v is not None})

        code_parts: list[str] = []
        part_vars: list[str] = []
        for i, part in enumerate(parts_def):
            # Resolve the color key into the actual hex string before code-gen.
            part_for_codegen = dict(part)
            if "color" in part_for_codegen:
                part_for_codegen["color"] = resolved_colors[part_for_codegen["color"]]
            code, var = _build_part(part_for_codegen, i, variables)
            code_parts.append(code)
            part_vars.append(var)

        if do_join and len(part_vars) > 1:
            join_lines = ["bpy.ops.object.select_all(action='DESELECT')"]
            for v in part_vars:
                join_lines.append(f"{v}.select_set(True)")
            join_lines.append(f"bpy.context.view_layer.objects.active = {part_vars[0]}")
            join_lines.append("bpy.ops.object.join()")
            join_lines.append("obj = bpy.context.active_object")
            join_lines.append(f"obj.name = {name!r}")
            code_parts.append("\n".join(join_lines))
        else:
            # Single part (or join disabled): name the lone object directly.
            code_parts.append(f"{part_vars[0]}.name = {name!r}\nobj = {part_vars[0]}")

        return "\n\n".join(code_parts) + "\n"

    return builder


# ── Interpreter entry point ──────────────────────────────────────────

def interpret(data: dict) -> dict:
    required = {"name", "type", "version"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"composite preset missing required fields: {sorted(missing)}")

    builder = _make_builder(data)
    return {
        "description": data.get("description", ""),
        "default_colors": dict(data.get("default_colors", {})),
        "category": data.get("category", "other"),
        "builder": builder,
    }


register("composite", 1, interpret)
