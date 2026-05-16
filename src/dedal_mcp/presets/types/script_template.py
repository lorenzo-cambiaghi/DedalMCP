"""Interpreter for the ``script_template/v1`` preset type.

A script_template preset carries a literal bpy snippet with placeholders that
are substituted on the *host* before the snippet ever reaches Blender. The
substituted snippet is compiled at load time, so any syntax error blocks the
server boot with a clear file-level reference (this catches bugs of the kind
seen in the previous Python-builder approach, where errors only surfaced when
the preset was first invoked).

Placeholder syntax:
    {x}, {y}, {steps}        numeric value from size dict
    {name}                   raw mesh name (string body, no quotes)
    {name|repr}              repr(name) — safe-quoted, use this in bpy code
    {color.body}             raw color value (e.g. '#808080')
    {color.body|repr}        repr(color value) — safe-quoted

Anything that does not match this pattern is left untouched. NOTE: this means
the template MUST NOT use Python f-strings, because '{i}' inside an f-string
would also match. Use string concatenation ('foo_' + str(i)) instead.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from dedal_mcp.presets.types import register


_PLACEHOLDER = re.compile(r"\{([a-z_][\w.]*)(?:\|(\w+))?\}")


class TemplateError(ValueError):
    pass


def _normalize_script(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(line) for line in value)
    raise TemplateError(f"'script' must be string or list of strings, got {type(value).__name__}")


def _format_value(v: Any) -> str:
    if isinstance(v, bool):
        return repr(v)
    if isinstance(v, (int, float)):
        return repr(v)
    return str(v)


def _substitute(template: str, name: str, size: dict, colors: dict, preset_name: str) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        modifier = match.group(2)

        if key == "name":
            value: Any = name
        elif key.startswith("color."):
            color_key = key.split(".", 1)[1]
            if color_key not in colors:
                raise TemplateError(
                    f"preset {preset_name!r}: template references {{color.{color_key}}} "
                    f"but color zone {color_key!r} is not in default_colors {sorted(colors)}"
                )
            value = colors[color_key]
        else:
            if key not in size:
                raise TemplateError(
                    f"preset {preset_name!r}: template references {{{key}}} but it is not "
                    f"in size_defaults {sorted(size)}"
                )
            value = size[key]

        if modifier is None:
            return _format_value(value)
        if modifier == "repr":
            return repr(value)
        raise TemplateError(
            f"preset {preset_name!r}: unknown placeholder modifier {modifier!r} "
            f"in {{{key}|{modifier}}}"
        )

    return _PLACEHOLDER.sub(replace, template)


def _validate_at_load(template: str, name: str, size_defaults: dict, default_colors: dict) -> None:
    """Substitute placeholders with defaults and compile() — surfaces syntax errors now."""
    try:
        rendered = _substitute(template, name, size_defaults, default_colors, name)
    except TemplateError:
        raise
    # Wrap in a minimal preamble so undefined references at compile time are limited
    # to actual syntax issues (NameErrors would only show at runtime, which is fine).
    preamble = "import bpy\n_set_vertex_color_all = lambda *a, **k: None\n_set_vertex_color_faces = lambda *a, **k: None\n"
    try:
        compile(preamble + rendered, f"<preset:{name}>", "exec")
    except SyntaxError as e:
        raise TemplateError(
            f"preset {name!r}: rendered template has a syntax error at line {e.lineno}: {e.msg}"
        ) from e


def _make_builder(data: dict) -> Callable[[str, dict, dict], str]:
    template = _normalize_script(data["script"])
    size_defaults = dict(data.get("size_defaults", {}))
    default_colors = dict(data.get("default_colors", {}))
    preset_name = data["name"]

    # Load-time validation: render with defaults and compile.
    _validate_at_load(template, preset_name, size_defaults, default_colors)

    def builder(name: str, size: dict, colors: dict) -> str:
        merged_size = dict(size_defaults)
        merged_size.update({k: v for k, v in size.items() if v is not None})
        merged_colors = dict(default_colors)
        merged_colors.update({k: v for k, v in colors.items() if v is not None})
        return _substitute(template, name, merged_size, merged_colors, preset_name)

    return builder


def interpret(data: dict) -> dict:
    required = {"name", "type", "version", "script"}
    missing = required - set(data)
    if missing:
        raise TemplateError(f"script_template preset missing required fields: {sorted(missing)}")

    builder = _make_builder(data)
    return {
        "description": data.get("description", ""),
        "default_colors": dict(data.get("default_colors", {})),
        "category": data.get("category", "other"),
        "builder": builder,
    }


register("script_template", 1, interpret)
