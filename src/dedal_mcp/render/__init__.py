"""Render configuration & script generation for Blender→image pipelines.

A ``render_config/v1`` JSON describes a render job: which .blend scene (or
live RPC session), which camera, what passes to produce, where to write the
output. The interpreter generates a bpy script that sets up the compositor
to write each requested pass as a separate PNG.
"""

from dedal_mcp.render.config import (
    RenderConfig,
    RenderConfigError,
    load_render_config,
    list_render_configs,
)
from dedal_mcp.render.script_builder import build_render_script

__all__ = [
    "RenderConfig",
    "RenderConfigError",
    "load_render_config",
    "list_render_configs",
    "build_render_script",
]
