from __future__ import annotations
"""Preset registry — backed by JSON files discovered at import time.

Public API preserved from the previous Python-based implementation:
- ``PRESETS``: dict[name -> entry]
- ``get_preset(name)``: lookup by name (case-insensitive)
- ``list_all_presets()``: summary list for tooling/list_presets tool
"""

from dedal_mcp.presets.loader import load_all

PRESETS: dict[str, dict] = load_all()


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
