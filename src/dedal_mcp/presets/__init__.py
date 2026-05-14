from __future__ import annotations
"""Preset registry — maps preset names to builder functions."""

from dedal_mcp.presets.primitives import PRIMITIVES
from dedal_mcp.presets.architecture import ARCHITECTURE
from dedal_mcp.presets.props import PROPS

PRESETS: dict[str, dict] = {}
PRESETS.update(PRIMITIVES)
PRESETS.update(ARCHITECTURE)
PRESETS.update(PROPS)


def get_preset(name: str) -> dict | None:
    return PRESETS.get(name.lower())


def list_all_presets() -> list[dict]:
    result = []
    for name, info in PRESETS.items():
        result.append({
            "name": name,
            "description": info["description"],
            "default_colors": info.get("default_colors", {}),
            "category": info.get("category", "other"),
        })
    return result
