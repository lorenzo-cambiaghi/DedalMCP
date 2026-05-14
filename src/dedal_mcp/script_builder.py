from __future__ import annotations
"""Builds complete bpy scripts from preset + parameters."""

import os

from dedal_mcp.presets import get_preset
from dedal_mcp.vertex_colors import color_utilities_code
from dedal_mcp.engine_profiles import EngineProfile, get_profile


SCENE_PREAMBLE = """
import bpy

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for c in bpy.data.collections:
    if c.name != 'Scene Collection':
        bpy.data.collections.remove(c)
"""


def build_preset_script(
    preset_name: str,
    mesh_name: str,
    output_path: str,
    size: dict | None = None,
    colors: dict | None = None,
    fmt: str = "fbx",
    profile: EngineProfile | None = None,
) -> str:
    preset = get_preset(preset_name)
    if preset is None:
        raise ValueError(f"Unknown preset: {preset_name}")

    if profile is None:
        profile = get_profile("generic")

    size = size or {}
    merged_colors = dict(preset.get("default_colors", {}))
    if colors:
        merged_colors.update(colors)

    builder = preset["builder"]
    mesh_code = builder(mesh_name, size, merged_colors)
    export_code = profile.get_export_code(mesh_name, output_path, fmt)

    return SCENE_PREAMBLE + color_utilities_code() + mesh_code + export_code


def build_custom_script(
    mesh_name: str,
    custom_code: str,
    output_path: str,
    fmt: str = "fbx",
    profile: EngineProfile | None = None,
) -> str:
    if profile is None:
        profile = get_profile("generic")

    export_code = profile.get_export_code(mesh_name, output_path, fmt)
    return SCENE_PREAMBLE + color_utilities_code() + custom_code + export_code


def build_batch_script(
    meshes: list[dict],
    output_dir: str,
    fmt: str = "fbx",
    profile: EngineProfile | None = None,
) -> str:
    if profile is None:
        profile = get_profile("generic")

    parts = [SCENE_PREAMBLE, color_utilities_code()]

    for i, mesh_def in enumerate(meshes):
        name = mesh_def.get("name", f"mesh_{i}")
        preset_name = mesh_def.get("preset", "cube")
        size = mesh_def.get("size", {})
        colors = mesh_def.get("colors", {})

        preset = get_preset(preset_name)
        if preset is None:
            parts.append(f'\nprint("DEDAL_ERROR: Unknown preset {preset_name}")\n')
            continue

        merged_colors = dict(preset.get("default_colors", {}))
        merged_colors.update(colors)

        builder = preset["builder"]
        parts.append(f"\n# --- {name} ---")
        parts.append(builder(name, size, merged_colors))

        output_path = os.path.join(output_dir, f"{name}.{fmt}")
        parts.append(profile.get_export_code(name, output_path, fmt))

        parts.append("""
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
""")

    return "\n".join(parts)
