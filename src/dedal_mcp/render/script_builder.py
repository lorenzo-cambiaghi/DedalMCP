"""Generate bpy scripts that render N passes from a scene.

The generated script:
1. Applies optional render setting overrides (resolution, samples, engine, denoise, camera, frame)
2. Enables the requested passes on the active view layer
3. Builds a compositor tree: RenderLayers → File Output node per pass
4. Triggers `bpy.ops.render.render()`
5. Prints `DEDAL_RENDER_SUCCESS:<path>` for each output file
"""

from __future__ import annotations

import re
from pathlib import Path

from dedal_mcp.render.config import RenderConfig


# Must start with alphanumeric/underscore (no leading dot or dash) and contain
# only safe chars. This rejects '', '.', '..', '.hidden', '-foo', 'a/b', 'a\\b'.
_NAME_PREFIX_RE = re.compile(r"^[A-Za-z0-9_][\w.\-]*$")


def _validate_name_prefix(prefix: str) -> str:
    """Reject prefixes that could escape output_dir via path traversal."""
    if not isinstance(prefix, str) or not _NAME_PREFIX_RE.match(prefix) or ".." in prefix:
        raise ValueError(
            f"name_prefix {prefix!r} must start with a letter/digit/underscore and contain "
            f"only word chars, dots and dashes (no '..', path separators, or leading dot/dash)"
        )
    return prefix


# (pass_name in our config) → (view_layer attr to enable, compositor output socket name)
_PASS_MAP: dict[str, tuple[str, str]] = {
    "combined":  ("use_pass_combined",           "Image"),
    "depth":     ("use_pass_z",                  "Depth"),
    "normal":    ("use_pass_normal",             "Normal"),
    "mist":      ("use_pass_mist",               "Mist"),
    "ao":        ("use_pass_ambient_occlusion",  "AO"),
    "position":  ("use_pass_position",           "Position"),
    "object_id": ("use_pass_object_index",       "IndexOB"),
}

# `edges` requires freestyle setup — not generated automatically yet.
_UNSUPPORTED_AUTO = {"edges"}


def build_render_script(
    cfg: RenderConfig,
    name_prefix: str,
    output_abs_dir: str,
) -> tuple[str, list[str]]:
    """Generate the bpy render script.

    Returns:
        (script_source, expected_output_paths)
    """
    _validate_name_prefix(name_prefix)
    out_dir = Path(output_abs_dir)
    frame = cfg.frame if cfg.frame is not None else 1

    expected: list[str] = []
    for p in cfg.passes:
        if p in _UNSUPPORTED_AUTO:
            continue
        # Blender's File Output node appends the current frame, zero-padded to 4 digits.
        expected.append(str(out_dir / f"{name_prefix}_{p}_{frame:04d}.png"))

    lines: list[str] = [
        "import bpy",
        "import os",
        "",
        "scene = bpy.context.scene",
        f"_out_dir = {str(out_dir)!r}",
        "os.makedirs(_out_dir, exist_ok=True)",
        "",
        "# --- override render settings (only fields present in config) ---",
    ]

    if cfg.resolution is not None:
        w, h = cfg.resolution
        lines.append(f"scene.render.resolution_x = {int(w)}")
        lines.append(f"scene.render.resolution_y = {int(h)}")
        lines.append("scene.render.resolution_percentage = 100")
    if cfg.engine is not None:
        lines.append(f"scene.render.engine = {cfg.engine!r}")
    if cfg.samples is not None:
        # Engine-specific path; we set both, ignoring AttributeError if not applicable.
        lines.append("try:")
        lines.append(f"    scene.cycles.samples = {int(cfg.samples)}")
        lines.append("except AttributeError: pass")
        lines.append("try:")
        lines.append(f"    scene.eevee.taa_render_samples = {int(cfg.samples)}")
        lines.append("except AttributeError: pass")
    if cfg.denoise is not None:
        lines.append("try:")
        lines.append(f"    scene.cycles.use_denoising = {bool(cfg.denoise)!r}")
        lines.append("except AttributeError: pass")
    if cfg.camera is not None:
        lines.append(f"_cam_name = {cfg.camera!r}")
        lines.append("if _cam_name in bpy.data.objects and bpy.data.objects[_cam_name].type == 'CAMERA':")
        lines.append("    scene.camera = bpy.data.objects[_cam_name]")
        lines.append("else:")
        lines.append("    raise RuntimeError('Camera ' + _cam_name + ' not found in scene')")
    if cfg.frame is not None:
        lines.append(f"scene.frame_set({int(cfg.frame)})")

    lines.append("")
    lines.append("# --- enable passes on the active view layer ---")
    lines.append("vl = scene.view_layers[0]")
    for p in cfg.passes:
        if p in _UNSUPPORTED_AUTO:
            lines.append(f"# Pass {p!r} not auto-enabled (requires manual setup in .blend)")
            continue
        attr, _ = _PASS_MAP[p]
        lines.append(f"try:")
        lines.append(f"    vl.{attr} = True")
        lines.append(f"except AttributeError:")
        lines.append(f"    print('DEDAL_RENDER_WARNING: view layer has no attr {attr}')")
    if "mist" in cfg.passes:
        lines.append("if scene.world and hasattr(scene.world, 'mist_settings'):")
        lines.append("    scene.world.mist_settings.use_mist = True")

    lines.append("")
    lines.append("# --- compositor: RenderLayers -> N File Output nodes ---")
    lines.append("scene.use_nodes = True")
    lines.append("tree = scene.node_tree")
    lines.append("for n in list(tree.nodes):")
    lines.append("    tree.nodes.remove(n)")
    lines.append("rl = tree.nodes.new('CompositorNodeRLayers')")
    for p in cfg.passes:
        if p in _UNSUPPORTED_AUTO:
            continue
        _, socket = _PASS_MAP[p]
        slot_path = f"{name_prefix}_{p}_"
        lines.append(f"")
        lines.append(f"# pass: {p}")
        lines.append(f"_fo = tree.nodes.new('CompositorNodeOutputFile')")
        lines.append(f"_fo.base_path = _out_dir")
        lines.append(f"_fo.file_slots[0].path = {slot_path!r}")
        lines.append(f"_fo.format.file_format = 'PNG'")
        lines.append(f"_fo.format.color_mode = 'RGB' if {p!r} != 'combined' else 'RGBA'")
        lines.append(f"if {socket!r} in rl.outputs:")
        if p == "depth":
            # Normalize depth so the PNG is meaningful (Cycles outputs world-units).
            lines.append(f"    _norm = tree.nodes.new('CompositorNodeNormalize')")
            lines.append(f"    tree.links.new(rl.outputs[{socket!r}], _norm.inputs[0])")
            lines.append(f"    tree.links.new(_norm.outputs[0], _fo.inputs[0])")
        else:
            lines.append(f"    tree.links.new(rl.outputs[{socket!r}], _fo.inputs[0])")
        lines.append(f"else:")
        lines.append(f"    print('DEDAL_RENDER_WARNING: RenderLayers has no output {socket}')")

    lines.append("")
    lines.append("# --- render ---")
    lines.append("bpy.ops.render.render(write_still=False)")
    lines.append("")
    lines.append("# --- emit success markers for the runner to collect ---")
    for path in expected:
        lines.append(f"print('DEDAL_RENDER_SUCCESS:' + {path!r})")

    return "\n".join(lines) + "\n", expected
