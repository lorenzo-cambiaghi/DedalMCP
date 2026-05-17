from __future__ import annotations
"""DedalMCP — MCP server for placeholder mesh generation via Blender."""

import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from dedal_mcp.blender_runner import run_script, run_render, BlenderError
from dedal_mcp.blender_rpc_client import (
    launch_blender,
    execute_python,
    is_blender_listening,
    BlenderRpcError,
)
from dedal_mcp.script_builder import (
    build_preset_script,
    build_custom_script,
    build_batch_script,
)
from dedal_mcp.presets import list_all_presets
from dedal_mcp.presets.loader import resolve_blend_path
from dedal_mcp.engine_profiles import get_profile, list_profiles
from dedal_mcp.render import (
    RenderConfigError,
    load_render_config,
    list_render_configs,
    build_render_script,
)
from dedal_mcp.comfyui import (
    ComfyError,
    WorkflowError,
    load_workflow,
    inject_inputs,
    find_output_nodes,
    submit_prompt,
    poll_history,
    upload_image,
    fetch_output,
)

app = Server("dedal-mcp")

PROJECT_PATH = os.environ.get("PROJECT_PATH", ".")
ENGINE = os.environ.get("DEDAL_ENGINE", "generic")


# ── Tool definitions ─────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_mesh",
            description=(
                "Create a placeholder mesh using a preset and export it as FBX/GLB. "
                "Presets: cube, sphere, cylinder, capsule, cone, plane, torus, "
                "house, wall, stairs, ramp, pillar, "
                "crate, barrel, table, chair, tree_pine, tree_round, rock. "
                "Uses vertex colors (no textures). Sizes in meters. "
                "Set 'engine' to adjust export settings (unity, godot, unreal, stride, flax, generic)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Mesh/file name (no extension)",
                    },
                    "preset": {
                        "type": "string",
                        "description": "Preset name (default: cube)",
                    },
                    "size": {
                        "type": "object",
                        "description": "Dimensions in meters: {x, y, z}. Meaning varies by preset.",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                        },
                    },
                    "colors": {
                        "type": "object",
                        "description": "Vertex colors by zone as hex strings. E.g. {\"walls\": \"#C0C0C0\", \"roof\": \"#CC4444\"}",
                        "additionalProperties": {"type": "string"},
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output directory (absolute or relative to PROJECT_PATH)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["fbx", "glb"],
                        "description": "Export format. Default depends on engine profile.",
                    },
                    "engine": {
                        "type": "string",
                        "description": "Engine profile: unity, godot, unreal, stride, flax, generic. Overrides DEDAL_ENGINE env var.",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="create_from_script",
            description=(
                "Create a mesh by running a custom bpy (Blender Python) script. "
                "The script must create objects and leave the final result named as specified. "
                "Helper functions available: _hex_to_rgb(hex), _set_vertex_color_all(obj, hex), "
                "_set_vertex_color_faces(obj, face_indices, hex). "
                "Imported: bpy. Scene is cleared before your script runs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the final object (must match an object in the scene)",
                    },
                    "script": {
                        "type": "string",
                        "description": "Complete bpy Python script",
                    },
                    "output_path": {"type": "string"},
                    "format": {"type": "string", "enum": ["fbx", "glb"]},
                    "engine": {"type": "string"},
                },
                "required": ["name", "script"],
            },
        ),
        Tool(
            name="batch_create",
            description=(
                "Create multiple placeholder meshes in a single Blender session. "
                "Faster than individual create_mesh calls."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "meshes": {
                        "type": "array",
                        "description": "List of mesh definitions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "preset": {"type": "string"},
                                "size": {"type": "object"},
                                "colors": {"type": "object"},
                            },
                            "required": ["name"],
                        },
                    },
                    "output_path": {"type": "string"},
                    "format": {"type": "string", "enum": ["fbx", "glb"]},
                    "engine": {"type": "string"},
                },
                "required": ["meshes"],
            },
        ),
        Tool(
            name="start_blender",
            description=(
                "Start the Blender GUI with the RPC channel injected. "
                "Required before using execute_blender_python. "
                "If Blender is already running with the RPC server, this is a no-op."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="execute_blender_python",
            description=(
                "Execute raw bpy (Blender Python) code in the live Blender session. "
                "Blender MUST be running first (call start_blender). "
                "The code runs on Blender's main thread with full access to the "
                "bpy API and can manipulate the open scene in real-time. "
                "Variables defined in one call persist to the next. "
                "Use print() to return output to the AI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Python code to execute inside Blender (bpy is available)",
                    },
                },
                "required": ["script"],
            },
        ),
        Tool(
            name="list_presets",
            description="List all available mesh presets with descriptions and default colors. Also shows supported engine profiles.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="render_blender_scene",
            description=(
                "Render an image (or N pass images) from a Blender scene. "
                "Use a saved render_config from ~/.dedal/renders/ by name, "
                "or pass an inline config dict. Supports multi-pass output "
                "(combined, depth, normal, mist, ao, position, object_id) saved as "
                "separate PNGs — ideal for ControlNet pipelines via comfyui_run_workflow. "
                "If config.scene is missing the live RPC Blender session is used."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "config": {
                        "description": "Render config name (from ~/.dedal/renders/) OR an inline dict",
                    },
                    "name_prefix": {
                        "type": "string",
                        "description": "Filename prefix for outputs (default: config name)",
                    },
                    "overrides": {
                        "type": "object",
                        "description": "Optional override for any config field (samples, resolution, camera, …)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max seconds to wait for render (default 600)",
                    },
                },
                "required": ["config"],
            },
        ),
        Tool(
            name="comfyui_run_workflow",
            description=(
                "Submit a ComfyUI API-format workflow, inject inputs into nodes "
                "identified by DEDAL_* titles, wait for completion, download outputs. "
                "Convention: rename target nodes in ComfyUI before exporting — "
                "LoadImage→DEDAL_INPUT_IMAGE, CLIPTextEncode→DEDAL_PROMPT, "
                "KSampler→DEDAL_SEED, SaveImage→DEDAL_OUTPUT. "
                "Workflows live in ~/.dedal/workflows/ or DEDAL_WORKFLOWS_PATH."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow": {
                        "description": "Workflow name (from ~/.dedal/workflows/) OR an inline dict",
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Map of DEDAL_* node title → value (image path, prompt text, seed, …)",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for downloaded outputs (relative to PROJECT_PATH; default comfy_outputs/)",
                    },
                    "server": {
                        "type": "string",
                        "description": "ComfyUI server URL (default DEDAL_COMFYUI_URL or http://localhost:8188)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max seconds to wait for completion (default 1800)",
                    },
                },
                "required": ["workflow"],
            },
        ),
    ]


# ── Tool dispatch ────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "list_presets":
            return _handle_list_presets()
        elif name == "create_mesh":
            return _handle_create_mesh(arguments)
        elif name == "create_from_script":
            return _handle_create_from_script(arguments)
        elif name == "batch_create":
            return _handle_batch_create(arguments)
        elif name == "start_blender":
            return _handle_start_blender()
        elif name == "execute_blender_python":
            return _handle_execute_blender_python(arguments)
        elif name == "render_blender_scene":
            return _handle_render_blender_scene(arguments)
        elif name == "comfyui_run_workflow":
            return _handle_comfyui_run_workflow(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except BlenderError as e:
        return [TextContent(type="text", text=f"Blender error: {e}")]
    except BlenderRpcError as e:
        return [TextContent(type="text", text=f"Blender RPC error: {e}")]
    except RenderConfigError as e:
        return [TextContent(type="text", text=f"Render config error: {e}")]
    except WorkflowError as e:
        return [TextContent(type="text", text=f"Workflow error: {e}")]
    except ComfyError as e:
        return [TextContent(type="text", text=f"ComfyUI error: {e}")]
    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"File not found: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


# ── Handlers ─────────────────────────────────────────────────────────

def _get_profile(args: dict):
    engine_name = args.get("engine", ENGINE)
    return get_profile(engine_name)


def _resolve_output_dir(path: str | None, profile) -> str:
    if path:
        if os.path.isabs(path):
            return path
        return os.path.join(PROJECT_PATH, path)
    return os.path.join(PROJECT_PATH, profile.default_output_subdir)


def _handle_list_presets() -> list[TextContent]:
    presets = list_all_presets()
    lines = [f"Active engine profile: {ENGINE}"]

    lines.append("\n## Engine Profiles")
    for p in list_profiles():
        marker = " (active)" if p["name"] == ENGINE else ""
        lines.append(f"  {p['name']:10s} — {p['display_name']}, format={p['default_format']}, output={p['default_output_subdir']}{marker}")

    lines.append("\n## Presets")
    current_cat = ""
    for p in sorted(presets, key=lambda x: (x["category"], x["name"])):
        if p["category"] != current_cat:
            current_cat = p["category"]
            lines.append(f"\n### {current_cat.title()}")
        colors_str = ", ".join(f"{k}={v}" for k, v in p["default_colors"].items())
        lines.append(f"  {p['name']:15s} — {p['description']}")
        if colors_str:
            lines.append(f"  {'':15s}   Colors: {colors_str}")
    return [TextContent(type="text", text="\n".join(lines))]


def _handle_create_mesh(args: dict) -> list[TextContent]:
    profile = _get_profile(args)
    mesh_name = args["name"]
    preset = args.get("preset", "cube")
    size = args.get("size", {})
    colors = args.get("colors", {})
    fmt = args.get("format", profile.default_format)
    output_dir = _resolve_output_dir(args.get("output_path"), profile)

    output_file = os.path.join(output_dir, f"{mesh_name}.{fmt}")
    os.makedirs(output_dir, exist_ok=True)

    script = build_preset_script(preset, mesh_name, output_file, size, colors, fmt, profile)
    result = run_script(script)
    return [TextContent(type="text", text=result)]


def _handle_create_from_script(args: dict) -> list[TextContent]:
    profile = _get_profile(args)
    mesh_name = args["name"]
    custom_code = args["script"]
    fmt = args.get("format", profile.default_format)
    output_dir = _resolve_output_dir(args.get("output_path"), profile)

    output_file = os.path.join(output_dir, f"{mesh_name}.{fmt}")
    os.makedirs(output_dir, exist_ok=True)

    script = build_custom_script(mesh_name, custom_code, output_file, fmt, profile)
    result = run_script(script)
    return [TextContent(type="text", text=result)]


def _handle_batch_create(args: dict) -> list[TextContent]:
    profile = _get_profile(args)
    meshes = args["meshes"]
    fmt = args.get("format", profile.default_format)
    output_dir = _resolve_output_dir(args.get("output_path"), profile)
    os.makedirs(output_dir, exist_ok=True)

    script = build_batch_script(meshes, output_dir, fmt, profile)
    result = run_script(script, timeout=120)
    return [TextContent(type="text", text=result)]


def _handle_start_blender() -> list[TextContent]:
    message = launch_blender()
    return [TextContent(type="text", text=message)]


def _handle_execute_blender_python(args: dict) -> list[TextContent]:
    result = execute_python(args["script"])

    parts = []
    if result.error:
        parts.append(f"ERROR:\n{result.error}")
    if result.output:
        parts.append(f"OUTPUT:\n{result.output}")

    text = "\n\n".join(parts) if parts else "Script executed successfully (no output)."
    return [TextContent(type="text", text=text)]


def _handle_render_blender_scene(args: dict) -> list[TextContent]:
    cfg = load_render_config(args["config"])
    if args.get("overrides"):
        cfg = cfg.merged_with(args["overrides"])

    name_prefix = args.get("name_prefix", cfg.name)
    timeout = int(args.get("timeout", 600))

    output_dir = cfg.output_dir
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(PROJECT_PATH, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    script, expected_paths = build_render_script(cfg, name_prefix, output_dir)

    if cfg.scene is not None:
        # Headless path: open the .blend, run the render script
        scene_path = str(resolve_blend_path(cfg.scene))
        rendered, warnings, errors = run_render(script, scene_path=scene_path, timeout=timeout)
        mode = f"headless ({cfg.scene})"
    else:
        # Live path: send the script to the running RPC session
        if not is_blender_listening():
            return [TextContent(
                type="text",
                text="Render config has no 'scene' (live mode), but no Blender RPC is "
                     "running. Call start_blender first, or set a 'scene' in the config.",
            )]
        result = execute_python(script)
        if result.error:
            return [TextContent(type="text", text=f"Live render error:\n{result.error}")]
        # Reuse the same marker parsing as headless mode
        out = result.output or ""
        rendered = [l.split("DEDAL_RENDER_SUCCESS:", 1)[1].strip()
                    for l in out.split("\n") if "DEDAL_RENDER_SUCCESS:" in l]
        warnings = [l.split("DEDAL_RENDER_WARNING:", 1)[1].strip()
                    for l in out.split("\n") if "DEDAL_RENDER_WARNING:" in l]
        errors = []
        mode = "live RPC"

    parts = [f"Render mode: {mode}", f"Output dir: {output_dir}"]
    if rendered:
        parts.append(f"\nRendered {len(rendered)} pass(es):")
        for p in rendered:
            size = ""
            try:
                size = f" ({os.path.getsize(p)} bytes)"
            except OSError:
                pass
            parts.append(f"  {p}{size}")
    if warnings:
        parts.append(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            parts.append(f"  {w}")
    if errors:
        parts.append(f"\nErrors ({len(errors)}):")
        for e in errors:
            parts.append(f"  {e}")
    return [TextContent(type="text", text="\n".join(parts))]


def _handle_comfyui_run_workflow(args: dict) -> list[TextContent]:
    server = args.get("server") or os.environ.get("DEDAL_COMFYUI_URL", "http://localhost:8188")
    timeout = int(args.get("timeout", 1800))
    wf = load_workflow(args["workflow"])

    # Translate inputs: for image-valued entries, upload the file to ComfyUI first
    raw_inputs = args.get("inputs", {})
    prepared: dict[str, object] = {}
    upload_log: list[str] = []
    for title, value in raw_inputs.items():
        # Heuristic: any string value pointing to an existing image file → upload
        if isinstance(value, str) and os.path.isfile(value) and value.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")
        ):
            uploaded = upload_image(value, server=server)
            prepared[title] = uploaded
            upload_log.append(f"  uploaded {value} → {uploaded['name']}")
        else:
            prepared[title] = value

    warnings = inject_inputs(wf, prepared)

    output_nodes = find_output_nodes(wf)
    prompt_id = submit_prompt(wf, server=server)
    history = poll_history(prompt_id, server=server, timeout=timeout)

    # Download outputs for every output node
    output_dir = args.get("output_dir", "comfy_outputs/")
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(PROJECT_PATH, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    outputs_by_node = history.get("outputs", {})
    downloaded: list[str] = []
    for nid, _node in output_nodes:
        node_out = outputs_by_node.get(nid, {})
        images = node_out.get("images", [])
        for img in images:
            fn = img.get("filename")
            sub = img.get("subfolder", "")
            t = img.get("type", "output")
            if not fn:
                continue
            dest = os.path.join(output_dir, fn)
            fetch_output(fn, sub, t, dest, server=server)
            downloaded.append(dest)

    parts = [f"ComfyUI prompt: {prompt_id}", f"Output dir: {output_dir}"]
    if upload_log:
        parts.append("\nImage uploads:")
        parts.extend(upload_log)
    if downloaded:
        parts.append(f"\nDownloaded {len(downloaded)} output(s):")
        for p in downloaded:
            parts.append(f"  {p}")
    else:
        parts.append("\nNo outputs downloaded (no DEDAL_OUTPUT* / SaveImage nodes produced images).")
    if warnings:
        parts.append(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            parts.append(f"  {w}")
    return [TextContent(type="text", text="\n".join(parts))]


# ── Entry point ──────────────────────────────────────────────────────

def main():
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
