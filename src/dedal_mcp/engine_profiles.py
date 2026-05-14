from __future__ import annotations
"""Engine-specific export profiles. Add new engines here."""

import os
from typing import Dict


class EngineProfile:
    def __init__(
        self,
        name: str,
        display_name: str,
        axis_forward: str = "-Z",
        axis_up: str = "Y",
        scale_option: str = "FBX_SCALE_ALL",
        default_format: str = "fbx",
        default_output_subdir: str = "models/placeholders",
        fbx_extra_args: dict | None = None,
    ):
        self.name = name
        self.display_name = display_name
        self.axis_forward = axis_forward
        self.axis_up = axis_up
        self.scale_option = scale_option
        self.default_format = default_format
        self.default_output_subdir = default_output_subdir
        self.fbx_extra_args = fbx_extra_args or {}

    def get_fbx_export_code(self, name: str, output_path: str) -> str:
        extra = ", ".join(
            f"{k}={repr(v)}" for k, v in self.fbx_extra_args.items()
        )
        extra_str = f",\n    {extra}" if extra else ""
        return f"""
bpy.ops.object.select_all(action='DESELECT')
obj = bpy.data.objects["{name}"]
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

bpy.ops.export_scene.fbx(
    filepath=r"{output_path}",
    use_selection=True,
    apply_scale_options='{self.scale_option}',
    axis_forward='{self.axis_forward}',
    axis_up='{self.axis_up}',
    mesh_smooth_type='OFF',
    use_mesh_modifiers=True,
    colors_type='SRGB',
    add_leaf_bones=False,
    bake_anim=False{extra_str},
)
print("DEDAL_EXPORT_SUCCESS:" + r"{output_path}")
"""

    def get_glb_export_code(self, name: str, output_path: str) -> str:
        return f"""
bpy.ops.object.select_all(action='DESELECT')
obj = bpy.data.objects["{name}"]
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

bpy.ops.export_scene.gltf(
    filepath=r"{output_path}",
    use_selection=True,
    export_format='GLB',
    export_colors=True,
    export_apply=True,
)
print("DEDAL_EXPORT_SUCCESS:" + r"{output_path}")
"""

    def get_export_code(self, name: str, output_path: str, fmt: str = "fbx") -> str:
        if fmt == "glb":
            return self.get_glb_export_code(name, output_path)
        return self.get_fbx_export_code(name, output_path)


# --- Built-in profiles ---

PROFILES: Dict[str, EngineProfile] = {}


def register_profile(profile: EngineProfile) -> None:
    PROFILES[profile.name.lower()] = profile


def get_profile(name: str) -> EngineProfile:
    profile = PROFILES.get(name.lower())
    if profile is None:
        return PROFILES["generic"]
    return profile


def list_profiles() -> list[dict]:
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "default_format": p.default_format,
            "default_output_subdir": p.default_output_subdir,
            "axis": f"forward={p.axis_forward}, up={p.axis_up}",
        }
        for p in PROFILES.values()
    ]


# Generic — safe defaults, Y-up, meters
register_profile(EngineProfile(
    name="generic",
    display_name="Generic (Y-up)",
    axis_forward="-Z",
    axis_up="Y",
    default_output_subdir="models/placeholders",
))

# Unity — Y-up, FBX preferred, Assets/ convention
register_profile(EngineProfile(
    name="unity",
    display_name="Unity",
    axis_forward="-Z",
    axis_up="Y",
    default_output_subdir="Assets/Models/Placeholders",
))

# Godot — Y-up but uses glTF natively, res:// convention
register_profile(EngineProfile(
    name="godot",
    display_name="Godot",
    axis_forward="-Z",
    axis_up="Y",
    default_format="glb",
    default_output_subdir="models/placeholders",
))

# Unreal — Z-up, FBX preferred, Content/ convention
register_profile(EngineProfile(
    name="unreal",
    display_name="Unreal Engine",
    axis_forward="X",
    axis_up="Z",
    scale_option="FBX_SCALE_ALL",
    default_output_subdir="Content/Meshes/Placeholders",
))

# Stride — Y-up, FBX
register_profile(EngineProfile(
    name="stride",
    display_name="Stride",
    axis_forward="-Z",
    axis_up="Y",
    default_output_subdir="Assets/Models/Placeholders",
))

# Flax — Y-up, FBX, Content/ convention
register_profile(EngineProfile(
    name="flax",
    display_name="Flax Engine",
    axis_forward="-Z",
    axis_up="Y",
    default_output_subdir="Content/Placeholders",
))
