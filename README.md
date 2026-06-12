# DedalMCP

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/blender-4.2%2B-orange.svg)
![MCP](https://img.shields.io/badge/mcp-compatible-green.svg)

> **AI-generated placeholder assets for your game engine — powered by Blender, delivered as engine-ready FBX/GLB.**

Ask your AI for *"a small village: four houses, a watchtower, some pine trees"* and get correctly-oriented, vertex-colored FBX files in `Assets/Models/Placeholders/` seconds later — without opening Blender, without downloading asset packs, without UV maps or materials to configure.

<!-- TODO: demo GIF here — prompt → meshes appear in Unity. This is the single highest-impact thing this README can show. -->

DedalMCP is a Python [MCP](https://modelcontextprotocol.io) server with two channels:

- **Headless Mode** *(the main event)* — The AI generates meshes from 19 built-in presets (or your own JSON presets, including Geometry Nodes trees) and batch-exports them straight into your project folder, with per-engine export profiles for **Unity, Godot, Unreal, Stride, and Flax** — correct axis orientation, scale, format, and output path for each.
- **Live Mode** — The AI opens Blender's GUI and sends raw `bpy` Python code in real-time over an authenticated local RPC channel. You watch meshes appear while the AI works. No addon to install.

```text
                                                          
                               ↖                           
                            ↓↑↑↑↑                          
                           ↑↑↑↑↑↑                          
                           ↑↑↑↑↑↑  →↑↑↑↑↑↑↑↑↑↑↑↑↗          
                           ↑↑↑↑↑↑                          
                           ↑↑↑↑↑↑                          
                      ↗→   ↓↓↓↓↓↓   ↗→                         Daedalus (Greek: Δαίδαλος) was the
                  ←↗↗↓                ↘↗↑                     mythical master craftsman who built
                                                               the Labyrinth for King Minos and
            ↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗↗→               crafted wings of wax and feathers.
               ↖↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑                    DedalMCP channels that craft: it
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑               lets your AI sculpt placeholder
           ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑               meshes in Blender and deliver them
              ↙→↗↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↗→↙                 straight to your game engine.
                    →↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↘                    
                      ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↗                      
                       ↑↑↑↑↑↑↑↑↑↑↑↑↑                                                   
                      →↗↗↗↗↗↗↗↗↗↘                                                       
                      ↓↑↑↑↑↑↑↑↑↑↑↑↑↑↙                      
                     ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↗                     
                   →↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↓                   
                   ←←←←←←←←←←←←←←←←←←←←←              
```

## Quickstart

```bash
git clone https://github.com/lorenzo-cambiaghi/DedalMCP.git
cd DedalMCP
pip install -e .
```

Add to your MCP client config (Claude Code shown; [other clients below](#connecting-an-ai-client)):

```bash
claude mcp add dedal-mcp -- dedal-mcp
```

Set two environment variables and you're done:

```bash
export BLENDER_PATH="/path/to/blender"      # if blender isn't in PATH
export PROJECT_PATH="/path/to/your/project" # where exported files land
export DEDAL_ENGINE="unity"                 # unity | godot | unreal | stride | flax | generic
```

Then ask your AI:

```
"Create a house preset mesh, 6x4x8 meters, gray walls and a red roof"
```

```
→ create_mesh {"name": "house", "preset": "house", "size": {"x":6, "y":4, "z":8},
               "colors": {"walls": "#D0D0D0", "roof": "#993333", "door": "#5C3A1E"}}
← Exported 1 file(s):
    Assets/Models/Placeholders/house.fbx (14280 bytes)
```

## How is this different from blender-mcp?

[blender-mcp](https://github.com/ahujasid/blender-mcp) is great at interactive "AI talks to Blender" sessions. DedalMCP overlaps there (Live Mode) but is built for a different job — **game prototyping pipelines**:

| | DedalMCP | blender-mcp |
|---|---|---|
| Headless batch generation (no GUI) | ✅ one CLI run per batch | ❌ needs Blender open |
| Engine export profiles (Unity/Godot/Unreal/Stride/Flax axis, scale, paths) | ✅ | ❌ manual |
| Extensible JSON preset system (composite, script, baked mesh, Geometry Nodes) | ✅ | ❌ |
| Vertex-color placeholder workflow + engine shaders included | ✅ | ❌ |
| Live GUI scripting via RPC | ✅ no addon, auto-injected | ✅ via addon |
| Asset library integrations (Poly Haven, …) | ❌ | ✅ |

If you want to chat with Blender, use either. If you want your AI to *stock your game project with placeholder assets*, that's what DedalMCP is for.

## Table of Contents

- [Installation](#installation)
- [Engine Profiles](#engine-profiles)
- [Connecting an AI Client](#connecting-an-ai-client)
- [MCP Tools](#mcp-tools)
- [Available Presets](#available-presets)
- [Writing Custom Presets](#writing-custom-presets) → full guide in [docs/PRESETS.md](docs/PRESETS.md)
- [Live Mode](#live-mode)
- [Vertex Color Shaders](#vertex-color-shaders)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| **Python** | 3.10+ | `python --version` |
| **Blender** | 4.2 LTS+ | `blender --version` |

Blender never needs to be open for headless mode — DedalMCP runs it in background mode. For live mode, DedalMCP launches the GUI itself.

## Installation

```bash
git clone https://github.com/lorenzo-cambiaghi/DedalMCP.git
cd DedalMCP
pip install -e .
```

This installs the `dedal-mcp` command used in the client configs below. *(A PyPI release is planned — at that point this becomes a single `pip install dedal-mcp`.)*

If `blender` is not in your system PATH, set `BLENDER_PATH`:

```bash
# macOS
export BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/Blender"
# Windows (PowerShell)
$env:BLENDER_PATH="C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
# Linux
export BLENDER_PATH="/usr/bin/blender"
```

## Engine Profiles

DedalMCP adjusts export settings — axis orientation, scale, default format, and output path — based on your target engine. Set it once via `DEDAL_ENGINE`, or override per tool call with the `engine` parameter.

| Profile | Default Format | Output Subdir | Axis |
|---------|---------------|---------------|------|
| `generic` | fbx | `models/placeholders` | Y-up, -Z forward |
| `unity` | fbx | `Assets/Models/Placeholders` | Y-up, -Z forward |
| `godot` | glb | `models/placeholders` | Y-up, -Z forward |
| `unreal` | fbx | `Content/Meshes/Placeholders` | Z-up, X forward |
| `stride` | fbx | `Assets/Models/Placeholders` | Y-up, -Z forward |
| `flax` | fbx | `Content/Placeholders` | Y-up, -Z forward |

Adding a new engine is a single `register_profile(...)` call in `src/dedal_mcp/engine_profiles.py` — no other code changes.

## Connecting an AI Client

The MCP server is launched by the AI client via stdio. All clients use the same three env vars: `BLENDER_PATH`, `PROJECT_PATH`, `DEDAL_ENGINE`.

### Claude Code (CLI)

```bash
claude mcp add dedal-mcp -- dedal-mcp
```

<details>
<summary><b>Claude Desktop</b></summary>

Open **Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "dedal-mcp",
      "env": {
        "BLENDER_PATH": "/path/to/blender",
        "PROJECT_PATH": "/path/to/your/project",
        "DEDAL_ENGINE": "unity"
      }
    }
  }
}
```

Config file location:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop after saving.
</details>

<details>
<summary><b>Cursor</b></summary>

Open **Settings → MCP**, click **+ Add new MCP server** (command type), or add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "dedal-mcp",
      "env": {
        "BLENDER_PATH": "/path/to/blender",
        "PROJECT_PATH": "/path/to/your/project",
        "DEDAL_ENGINE": "godot"
      }
    }
  }
}
```
</details>

<details>
<summary><b>Windsurf</b></summary>

Open **Settings → MCP** and add the same JSON block as Cursor above.
</details>

<details>
<summary><b>Google Antigravity</b></summary>

Antigravity reads `mcp_config.json` from `~/.gemini/antigravity/` (`%USERPROFILE%\.gemini\antigravity\` on Windows):

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "dedal-mcp",
      "type": "stdio",
      "env": {
        "BLENDER_PATH": "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
        "PROJECT_PATH": "C:/Users/you/UnityProject",
        "DEDAL_ENGINE": "unity"
      }
    }
  }
}
```

Restart Antigravity. The new tools appear automatically.
</details>

<details>
<summary><b>VS Code + Copilot</b></summary>

Add to `.vscode/settings.json` or use the **MCP: Add Server** command:

```json
{
  "mcp": {
    "servers": {
      "dedal-mcp": {
        "command": "dedal-mcp",
        "env": {
          "BLENDER_PATH": "/path/to/blender",
          "PROJECT_PATH": "/path/to/your/project",
          "DEDAL_ENGINE": "unity"
        }
      }
    }
  }
}
```
</details>

> **`PROJECT_PATH`** tells DedalMCP where to write exported files. Output paths are resolved relative to this directory; the default subdirectory depends on the engine profile. **Windows users:** use forward slashes or double backslashes in JSON paths.

**Verify the connection** by asking the AI: *"List the available mesh presets"* — `list_presets` runs locally, no Blender needed.

## MCP Tools

### Headless (Presets)

| Tool | Description |
|------|-------------|
| `create_mesh` | Create a mesh from a preset with custom size, colors, and engine profile |
| `create_from_script` | Run a custom bpy (Blender Python) script to create any mesh |
| `batch_create` | Create multiple meshes in one Blender session (faster) |
| `list_presets` | List all presets, parameters, default colors, and engine profiles |

### Live (RPC)

| Tool | Description |
|------|-------------|
| `start_blender` | Launch Blender GUI with the RPC server auto-injected. Idempotent. |
| `execute_blender_python` | Execute raw `bpy` code in the live session. Full API access, variables persist between calls. |

### Render

| Tool | Description |
|------|-------------|
| `render_blender_scene` | Render a `.blend` (or the live session) producing pass images (combined, depth, normal, mist, AO, position, object_id) — ControlNet-ready inputs. Pair with [MorpheusMCP](https://github.com/lorenzo-cambiaghi/MorpheusMCP) for diffusion. |

### When to use which

| Scenario | Tool |
|----------|------|
| Quick batch of placeholder FBX files | `batch_create` |
| Standard preset with custom colors | `create_mesh` |
| Complex custom modeling, boolean cuts, modifiers, iterating on a shape | `execute_blender_python` |
| Inspecting/exporting from an existing `.blend` | `execute_blender_python` |
| Depth/normal passes for ControlNet | `render_blender_scene` |

## Available Presets

**Primitives:** `cube` `sphere` `cylinder` `capsule` `cone` `plane` `torus`
**Architecture:** `house` `wall` `stairs` `ramp` `pillar`
**Props:** `crate` `barrel` `table` `chair` `tree_pine` `tree_round` `rock`

Each preset accepts a **`size`** (meters; meaning per-preset, see `list_presets`) and **`colors`** (vertex colors per zone, hex strings — e.g. `{"walls": "#C0C0C0", "roof": "#CC4444"}`).

## Writing Custom Presets

Presets are plain JSON files dropped in `~/.dedal/presets/` (or `./dedal_presets/`, or `DEDAL_PRESETS_PATH`) — discovered automatically, no code, no rebuild. Four types:

| Type | For |
|---|---|
| `composite` | Declarative primitive composition with arithmetic expressions (`"radius": "x/2"`) — no Python |
| `script_template` | Full bpy scripts with safe placeholder substitution — loops, bmesh, modifiers, randomness |
| `mesh_data` | Hand-modeled geometry baked into JSON — produced by the included Blender add-on |
| `geometry_nodes` | A Geometry Nodes tree from a `.blend`, parameterized by the AI through input sockets |

A user preset with the same `name` as a built-in overrides it. The repo also ships a **Blender add-on** (`extras/blender_plugin/`) for authoring presets visually in the viewport and round-tripping them to JSON.

**→ Full guide with tutorials for every type: [docs/PRESETS.md](docs/PRESETS.md)**

## Live Mode

```
→ start_blender {}
← Blender GUI started, RPC server ready on 127.0.0.1:52731.

→ execute_blender_python {"script": "
import bpy
bpy.ops.mesh.primitive_cylinder_add(radius=2, depth=6, location=(0,0,3))
base = bpy.context.active_object
base.name = 'Tower_Base'
bpy.ops.mesh.primitive_cone_add(radius1=2.5, radius2=0, depth=2, location=(0,0,7))
roof = bpy.context.active_object
roof.name = 'Tower_Roof'
print(f'Created {base.name} and {roof.name}')
"}
← OUTPUT:
Created Tower_Base and Tower_Roof
```

How it works:

1. `start_blender` picks a **free localhost port**, generates a **session token**, and launches Blender with a lightweight RPC server injected via `blender --python` — no addon installation, zero Blender-side configuration. The call returns when the RPC server is actually ready.
2. `execute_blender_python` sends authenticated code over TCP (`127.0.0.1`, token required); the code runs on Blender's main thread (thread-safe via `bpy.app.timers`), stdout and errors come back to the AI.
3. The `exec` context persists between calls — variables, imports, and functions survive, so the AI builds scenes incrementally.

The session (port + token) is persisted in `~/.dedal/rpc_session.json`, so a restarted MCP server reconnects to a still-running Blender. Only processes that know the token can execute code.

## Vertex Color Shaders

Most engines don't display vertex colors by default. Copy the appropriate shader from `extras/`:

| Engine | Setup |
|--------|-------|
| **Unity (Built-in RP)** | `extras/unity/VertexColor.shader` → `Assets/Shaders/`, material with **Placeholder/VertexColor** |
| **Unity (URP)** | Shader Graph: **Vertex Color** node → **Base Color** |
| **Godot** | `extras/godot/vertex_color.gdshader` as ShaderMaterial |
| **Unreal** | Material: **Vertex Color** node → **Base Color** |
| **Stride** | `VertexColorFeature` in material |

## The Perfect Combo: DedalMCP + AkerMCP

DedalMCP creates the assets; [**AkerMCP**](https://github.com/lorenzo-cambiaghi/AkerMCP) (our MCP bridge for C# game engines) places them in the scene:

```
1. DedalMCP → batch_create [...placeholders...]        ← FBX files land in Assets/
2. AkerMCP  → execute "AssetDatabase.Refresh()"        ← Unity imports them
3. AkerMCP  → execute "place everything in the scene"  ← objects appear in editor
```

## Architecture

```
LLM (Claude, Cursor, Copilot, Antigravity)
    │ JSON-RPC 2.0 / stdio
    ▼
┌───────────────────────────────────┐
│         DedalMCP Server           │  Python MCP server
│   7 tools, 19 presets             │
│   6 engine profiles               │
│                                   │
│  ┌─────────────┐ ┌─────────────┐ │
│  │  Headless   │ │    Live     │ │
│  │   Channel   │ │   Channel   │ │
│  └──────┬──────┘ └──────┬──────┘ │
└─────────┼───────────────┼────────┘
          │               │
          │ subprocess    │ TCP 127.0.0.1:<session port>
          │ blender -b    │ (token-authenticated)
          ▼               ▼
┌──────────────┐  ┌──────────────────┐
│ Blender CLI  │  │  Blender GUI     │
│ (headless)   │  │  + RPC server    │
│ generates →  │  │  (auto-injected) │
│ exports →    │  │  bpy.app.timers  │
│ exits        │  │  main thread     │
└──────┬───────┘  └──────────────────┘
       │
       │ file written to disk
       ▼
┌──────────────────────────┐
│    Your Game Project     │  Any engine: Unity, Godot,
│  (auto-import on refresh)│  Unreal, Stride, Flax, ...
└──────────────────────────┘
```

### Project structure

```
DedalMCP/
├── pyproject.toml
├── docs/PRESETS.md                Custom preset authoring guide
├── src/dedal_mcp/
│   ├── server.py                  MCP server — 7 tools, routing only
│   ├── blender_runner.py          Headless: subprocess blender --background --python
│   ├── blender_rpc.py             Injected into Blender: TCP server + main thread dispatcher
│   ├── blender_rpc_client.py      Live: TCP client, session/token management
│   ├── script_builder.py          Generates bpy scripts from preset + profile
│   ├── engine_profiles.py         Export profiles (axis, scale, format, paths)
│   ├── vertex_colors.py           Vertex color bpy code generation
│   ├── presets/
│   │   ├── loader.py              Discovery: built-in JSONs + user dirs + blend search
│   │   ├── types/                 Typed-preset interpreters (composite, script_template,
│   │   │                          mesh_data, geometry_nodes + shared safe_eval)
│   │   └── data/                  19 built-in preset JSON files
│   └── render/                    render_config/v1 schema + multi-pass render scripts
└── extras/
    ├── blender_plugin/dedal_preset_editor.py   Visual preset authoring add-on
    ├── unity/VertexColor.shader
    └── godot/vertex_color.gdshader
```

### How the two channels work

| | Headless Channel | Live Channel |
|---|---|---|
| **Blender process** | Started and killed per tool call | Started once, stays open |
| **Communication** | Subprocess stdin/stdout | TCP `127.0.0.1:<session port>`, token auth |
| **Thread safety** | N/A (separate process) | `bpy.app.timers` dispatches to main thread |
| **State** | Stateless — fresh scene each time | Persistent — variables survive between calls |
| **Used by** | `create_mesh`, `create_from_script`, `batch_create` | `start_blender`, `execute_blender_python` |
| **Blender addon required** | No | No (auto-injected via `--python`) |

## Troubleshooting

**"Blender not found"** — Set `BLENDER_PATH` to the full path of your Blender executable.

**Meshes have no color in my engine** — Most engines don't render vertex colors by default; see [Vertex Color Shaders](#vertex-color-shaders).

**Export axis is wrong / mesh is rotated** — Set the correct engine profile (`DEDAL_ENGINE` or the `engine` parameter). Unreal is Z-up, Unity/Godot are Y-up.

**Blender is slow / times out on first run** — First launch builds addon caches. Bump `DEDAL_BLENDER_TIMEOUT` (seconds, default 120) and use `batch_create` for multiple meshes.

**`list_presets` works but `create_mesh` fails** — `list_presets` runs locally; `create_mesh` needs a working `blender --version`.

**`execute_blender_python` says no session found** — Call `start_blender` first. It now blocks until the RPC server is ready (configurable via `DEDAL_BLENDER_START_TIMEOUT`, default 60s), so no manual waiting is needed.

**"RPC token rejected"** — The running Blender belongs to a previous session. Close it and call `start_blender` again.

**Calling `start_blender` twice** — Safe: if the session's RPC server still answers the handshake, it's a no-op.

**Live mode scripts share variables** — By design: the exec context persists between calls so scenes can be built incrementally.

**I need a fixed RPC port** (e.g. firewall rules) — Set `DEDAL_RPC_PORT`; otherwise a free port is chosen per session.

## License

[Apache 2.0](LICENSE)
