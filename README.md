# DedalMCP

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Blender%203.6%2B-orange.svg)
![MCP](https://img.shields.io/badge/mcp-compatible-green.svg)

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

> **Give your AI the power to control Blender — live or headless — for any game engine.**

DedalMCP is a Python MCP server that gives AI assistants two ways to work with Blender:

- **Live Mode** — The AI opens Blender's GUI and sends raw `bpy` Python code in real-time. You watch meshes appear, get modified, and exported while the AI works. No addon to install — the RPC server is injected automatically at launch.
- **Headless Mode** — The AI generates meshes from built-in presets without ever opening a window. Fast batch export of vertex-colored placeholders straight into your project folder.

### 🏛️ The "Wow" Factor: Talk to Blender

Imagine asking your AI:
> *"Open Blender, model a watchtower with a cylindrical base and a cone roof, then export it to my Unity project."*

- **Without DedalMCP:** The AI tells you to download assets from a store, or model them yourself, or use Unity primitives that look awful.
- **With DedalMCP:** The AI opens Blender, writes the `bpy` code itself, you watch the tower appear in the viewport, and the FBX lands in your project folder.

**Live Mode Example:**
```
→ start_blender {}
← Blender GUI started with RPC server on localhost:8081.

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

**Headless Mode Example:**
```
→ create_mesh {"name": "house", "preset": "house", "size": {"x":6, "y":4, "z":8},
               "colors": {"walls": "#D0D0D0", "roof": "#993333", "door": "#5C3A1E"}}
← Exported 1 file(s):
    Assets/Models/Placeholders/house.fbx (14280 bytes)
```

*(Curious about the internal architecture? Jump to the [Architecture](#architecture) section.)*

---

## 🔨 How it Works (Under the Hood)

### Live Mode (RPC)

DedalMCP can launch Blender with a lightweight RPC server auto-injected via `blender --python`. No addon installation required — zero configuration on the Blender side.

1. The AI calls `start_blender` → Blender opens with the GUI visible
2. A TCP server starts on `localhost:8081` inside the Blender process
3. The AI sends Python code via `execute_blender_python`
4. The code executes on Blender's main thread (thread-safe via `bpy.app.timers`)
5. Results (stdout + errors) are sent back to the AI

```
AI: "Add a cube, scale it to 3x1x3, and name it 'Floor'"

→ execute_blender_python {"script": "
import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0))
obj = bpy.context.active_object
obj.name = 'Floor'
obj.scale = (3, 1, 3)
bpy.ops.object.transform_apply(scale=True)
print('Floor created')
"}
← OUTPUT:
Floor created
```

The AI has full `bpy` access — it can model, apply modifiers, set up materials, export, or do anything Blender's Python API supports.

### Headless Mode (Presets)

For quick batch generation, DedalMCP runs Blender in background mode (`--background --python`) without a GUI:

1. Receives a tool call from the AI (e.g. `create_mesh` with preset and colors)
2. Generates a complete `bpy` Python script from the preset template
3. Runs `blender --background --python script.py`
4. Blender creates the mesh, assigns vertex colors, and exports FBX/GLB
5. The file lands in your project folder, ready for import

Both modes coexist in the same MCP server and can be used in the same session.

---

## Features

- **Live Blender Control**: Open Blender's GUI and execute arbitrary `bpy` code in real-time via RPC. Zero addon installation — auto-injected at launch.
- **19 Built-in Presets**: Primitives, architecture, props, and vegetation — all parameterized by size and color for headless generation.
- **Vertex Colors Only**: No textures, no UVs, no material setup. Minimal complexity for maximum prototyping speed.
- **Engine-Agnostic**: Built-in export profiles for **Unity**, **Godot**, **Unreal**, **Stride**, and **Flax** — correct axis orientation, scale, format, and output paths per engine.
- **Dual Mode**: Use headless mode for fast batch export, live mode for interactive modeling — or mix both in the same session.
- **Persistent State**: In live mode, variables defined in one `execute_blender_python` call persist to the next. Build complex scenes incrementally.

---

## The Perfect Combo: DedalMCP + AkerMCP

DedalMCP gives your AI the ability to **create 3D assets from scratch**. But to actually *place* them in a game scene, the AI also needs hands inside the engine.

We recommend running DedalMCP alongside [**AkerMCP**](https://github.com/lorenzo-cambiaghi/AkerMCP), our MCP bridge for C# game engines.

When combined, the AI gets a **complete prototyping pipeline**:
- **DedalMCP** generates placeholder FBX/GLB meshes via Blender.
- **AkerMCP** imports them into the engine and places them in the scene via `execute`.

```
1. DedalMCP → start_blender                                ← opens Blender
2. DedalMCP → execute_blender_python "model + export FBX"  ← AI models and exports
3. AkerMCP  → execute "AssetDatabase.Refresh()"            ← Unity imports the FBX
4. AkerMCP  → execute "place everything in the scene"      ← objects appear in editor
```

---

## Table of Contents

- [The Perfect Combo: DedalMCP + AkerMCP](#the-perfect-combo-dedalmcp--akermcp)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Engine Profiles](#engine-profiles)
- [Connecting an AI Client](#connecting-an-ai-client)
  - [Claude Code (CLI)](#claude-code-cli)
  - [Claude Desktop](#claude-desktop)
  - [Cursor](#cursor)
  - [Windsurf](#windsurf)
  - [Google Antigravity](#google-antigravity)
  - [VS Code + Copilot](#vs-code--copilot)
- [Verifying the Connection](#verifying-the-connection)
- [MCP Tools](#mcp-tools)
- [Available Presets](#available-presets)
- [Vertex Color Shaders](#vertex-color-shaders)
- [Example Session](#example-session)
- [Architecture](#architecture)
- [Adding a New Engine Profile](#adding-a-new-engine-profile)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Prerequisites

| Requirement | Version | Check | Install |
|-------------|---------|-------|---------|
| **Python** | 3.9+ | `python --version` | [python.org](https://python.org) |
| **Blender** | 3.6+ | `blender --version` | [blender.org/download](https://blender.org/download) |

> **Note:** For headless mode, Blender does not need to be open — DedalMCP runs it in background mode via the command line. For live mode, DedalMCP launches Blender's GUI automatically.

---

## Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/lorenzo-cambiaghi/DedalMCP.git
cd DedalMCP
```

### Step 2 — Install

```bash
pip install -e .
```

### Step 3 — Set the Blender path

If `blender` is not in your system PATH:

```bash
# macOS
export BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/Blender"

# Windows (PowerShell)
$env:BLENDER_PATH="C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

# Linux
export BLENDER_PATH="/usr/bin/blender"
```

That's it. The server is ready to run.

---

## Engine Profiles

DedalMCP adjusts export settings — axis orientation, scale, default format, and output path — based on your target engine. Set it once via environment variable, or override per tool call.

| Profile | Default Format | Output Subdir | Axis |
|---------|---------------|---------------|------|
| `generic` | fbx | `models/placeholders` | Y-up, -Z forward |
| `unity` | fbx | `Assets/Models/Placeholders` | Y-up, -Z forward |
| `godot` | glb | `models/placeholders` | Y-up, -Z forward |
| `unreal` | fbx | `Content/Meshes/Placeholders` | Z-up, X forward |
| `stride` | fbx | `Assets/Models/Placeholders` | Y-up, -Z forward |
| `flax` | fbx | `Content/Placeholders` | Y-up, -Z forward |

Set your engine globally:

```bash
export DEDAL_ENGINE="unity"
export PROJECT_PATH="/path/to/your/project"
```

Or override per tool call:
```json
{"name": "house", "preset": "house", "engine": "godot"}
```

---

## Connecting an AI Client

The MCP server is launched by the AI client via stdio. Configure it once.

### Claude Code (CLI)

```bash
claude mcp add dedal-mcp -- python -m dedal_mcp
```

Or add it manually to your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "python",
      "args": ["-m", "dedal_mcp"],
      "env": {
        "BLENDER_PATH": "/path/to/blender",
        "PROJECT_PATH": "/path/to/your/project",
        "DEDAL_ENGINE": "unity"
      }
    }
  }
}
```

Verify it's registered:

```bash
claude mcp list
```

### Claude Desktop

Open **Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "python",
      "args": ["-m", "dedal_mcp"],
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

### Cursor

Open **Settings → MCP** and click **+ Add new MCP server**, then choose **command** type:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "python",
      "args": ["-m", "dedal_mcp"],
      "env": {
        "BLENDER_PATH": "/path/to/blender",
        "PROJECT_PATH": "/path/to/your/project",
        "DEDAL_ENGINE": "godot"
      }
    }
  }
}
```

Or add it directly to `.cursor/mcp.json` in your project root.

### Windsurf

Open **Settings → MCP** and add:

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "python",
      "args": ["-m", "dedal_mcp"],
      "env": {
        "BLENDER_PATH": "/path/to/blender",
        "PROJECT_PATH": "/path/to/your/project",
        "DEDAL_ENGINE": "unity"
      }
    }
  }
}
```

### Google Antigravity

Antigravity reads `mcp_config.json` from its user-data directory:

- **Windows:** `%USERPROFILE%\.gemini\antigravity\mcp_config.json`
- **macOS:** `~/.gemini/antigravity/mcp_config.json`
- **Linux:** `~/.gemini/antigravity/mcp_config.json`

```json
{
  "mcpServers": {
    "dedal-mcp": {
      "command": "python",
      "args": ["-m", "dedal_mcp"],
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

### VS Code + Copilot

Add to your `.vscode/settings.json` or use the **MCP: Add Server** command:

```json
{
  "mcp": {
    "servers": {
      "dedal-mcp": {
        "command": "python",
        "args": ["-m", "dedal_mcp"],
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

> **`PROJECT_PATH`** tells DedalMCP where to write exported files. Output paths are resolved relative to this directory. The default output subdirectory depends on the engine profile.

> **Windows users:** Use forward slashes or double backslashes in JSON paths.

---

## Verifying the Connection

Once the AI client is connected, ask it:

```
"List the available mesh presets"
```

You should see:

```
## Primitive
  cube            — Simple box. Size: x=width, y=height, z=depth
  sphere          — UV sphere. Size: x=diameter
  cylinder        — Cylinder. Size: x=diameter, y=height
  ...

## Architecture
  house           — Simple house: box walls + peaked roof + door
  wall            — Rectangular wall segment
  stairs          — Staircase
  ...

## Prop
  crate           — Wooden crate with beveled edges
  barrel          — Barrel with slight bulge
  tree_pine       — Pine tree (cone on cylinder)
  ...
```

If you see this, everything is working. `list_presets` does not require Blender — it runs locally.

To test live mode:

```
"Start Blender and create a sphere"
```

Blender should open, and a sphere should appear in the viewport.

---

## MCP Tools

### Live Mode (RPC)

| Tool | Description |
|------|-------------|
| `start_blender` | Launch Blender GUI with the RPC server auto-injected. Idempotent — if Blender is already running, this is a no-op. |
| `execute_blender_python` | Execute raw `bpy` Python code in the live Blender session. Full API access, persistent state between calls. |

### Headless Mode (Presets)

| Tool | Description |
|------|-------------|
| `create_mesh` | Create a mesh from a preset with custom size, colors, and engine profile |
| `create_from_script` | Run a custom bpy (Blender Python) script to create any mesh |
| `batch_create` | Create multiple meshes in one Blender session (faster) |
| `list_presets` | List all presets, parameters, default colors, and engine profiles |

Headless tools accept an optional `engine` parameter to override the default export profile.

### When to Use Which

| Scenario | Tool | Mode |
|----------|------|------|
| Quick batch of placeholder FBX files | `batch_create` | Headless |
| Standard preset with custom colors | `create_mesh` | Headless |
| Complex custom modeling, iterating on a shape | `execute_blender_python` | Live |
| Boolean cuts, modifiers, procedural geometry | `execute_blender_python` | Live |
| Inspecting/modifying an existing `.blend` file | `execute_blender_python` | Live |
| Exporting from a live scene you've been building | `execute_blender_python` | Live |

---

## Available Presets

### Primitives
`cube` `sphere` `cylinder` `capsule` `cone` `plane` `torus`

### Architecture
`house` `wall` `stairs` `ramp` `pillar`

### Props
`crate` `barrel` `table` `chair` `tree_pine` `tree_round` `rock`

Each preset accepts:
- **`size`** — dimensions in meters (meaning varies by preset, see `list_presets` for details)
- **`colors`** — vertex colors per zone as hex strings (e.g. `{"walls": "#C0C0C0", "roof": "#CC4444"}`)

---

## Vertex Color Shaders

Most engines don't display vertex colors by default. Copy the appropriate shader from `extras/` into your project:

| Engine | File | Setup |
|--------|------|-------|
| **Unity (Built-in RP)** | `extras/unity/VertexColor.shader` | Copy to `Assets/Shaders/`, create material with **Placeholder/VertexColor** shader |
| **Unity (URP)** | — | Create Shader Graph: **Vertex Color** node → **Base Color** |
| **Godot** | `extras/godot/vertex_color.gdshader` | Assign as ShaderMaterial on mesh |
| **Unreal** | — | Create Material: **Vertex Color** node → **Base Color** |
| **Stride** | — | Use `VertexColorFeature` in material |

---

## Example Session

### Headless — Batch placeholder generation

```
→ list_presets {}
← 6 engine profiles, 19 presets available...

→ create_mesh {"name": "village_house", "preset": "house",
               "size": {"x": 6, "y": 4, "z": 8},
               "colors": {"walls": "#D0D0D0", "roof": "#993333", "door": "#5C3A1E"},
               "engine": "unity"}
← Exported 1 file(s):
    Assets/Models/Placeholders/village_house.fbx (14280 bytes)

→ batch_create {"meshes": [
    {"name": "pine_1", "preset": "tree_pine", "size": {"y": 4}},
    {"name": "pine_2", "preset": "tree_pine", "size": {"y": 5.5}},
    {"name": "pine_3", "preset": "tree_pine", "size": {"y": 3}},
    {"name": "wall_section", "preset": "wall", "size": {"x": 10, "y": 3, "z": 0.4}},
    {"name": "barrel_1", "preset": "barrel", "colors": {"body": "#5C3A1E"}}
  ], "engine": "unity"}
← Exported 5 file(s):
    Assets/Models/Placeholders/pine_1.fbx (4120 bytes)
    Assets/Models/Placeholders/pine_2.fbx (4120 bytes)
    Assets/Models/Placeholders/pine_3.fbx (4120 bytes)
    Assets/Models/Placeholders/wall_section.fbx (2840 bytes)
    Assets/Models/Placeholders/barrel_1.fbx (8640 bytes)
```

### Live — Interactive modeling session

```
→ start_blender {}
← Blender GUI started with RPC server on localhost:8081.

→ execute_blender_python {"script": "
import bpy
# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
print('Scene cleared')
"}
← OUTPUT:
Scene cleared

→ execute_blender_python {"script": "
import bpy
# Create a watchtower base
bpy.ops.mesh.primitive_cylinder_add(radius=2, depth=6, location=(0,0,3))
tower = bpy.context.active_object
tower.name = 'Watchtower_Base'

# Add a cone roof
bpy.ops.mesh.primitive_cone_add(radius1=2.5, radius2=0, depth=2, location=(0,0,7))
roof = bpy.context.active_object
roof.name = 'Watchtower_Roof'

# Join them
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = tower
bpy.ops.object.join()
tower.name = 'Watchtower'

print(f'Watchtower created: {len(tower.data.vertices)} vertices')
"}
← OUTPUT:
Watchtower created: 128 vertices

→ execute_blender_python {"script": "
import bpy
# Export directly from the live session
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.fbx(
    filepath=r'C:/MyProject/Assets/Models/Placeholders/watchtower.fbx',
    use_selection=True,
    axis_forward='-Z',
    axis_up='Y',
)
print('Exported watchtower.fbx')
"}
← OUTPUT:
Exported watchtower.fbx
```

---

## Architecture

```
LLM (Claude, Cursor, Copilot, Antigravity)
    │ JSON-RPC 2.0 / stdio
    ▼
┌───────────────────────────────────┐
│         DedalMCP Server           │  Python MCP server
│   6 tools, 19 presets             │
│   6 engine profiles               │
│                                   │
│  ┌─────────────┐ ┌─────────────┐ │
│  │  Headless   │ │    Live     │ │
│  │   Channel   │ │   Channel   │ │
│  └──────┬──────┘ └──────┬──────┘ │
└─────────┼───────────────┼────────┘
          │               │
          │ subprocess    │ TCP socket
          │ blender -b    │ localhost:8081
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
├── src/dedal_mcp/
│   ├── server.py                  MCP server — 6 tools, routing only
│   ├── blender_runner.py          Headless: subprocess blender --background --python
│   ├── blender_rpc.py             Injected into Blender: TCP server + main thread dispatcher
│   ├── blender_rpc_client.py      Live: TCP client, launch_blender(), execute_python()
│   ├── script_builder.py          Generates bpy scripts from preset + profile
│   ├── engine_profiles.py         Export profiles (axis, scale, format, paths)
│   ├── vertex_colors.py           Vertex color bpy code generation
│   └── presets/
│       ├── primitives.py          cube, sphere, cylinder, capsule, cone, plane, torus
│       ├── architecture.py        house, wall, stairs, ramp, pillar
│       └── props.py               crate, barrel, table, chair, tree_pine, tree_round, rock
└── extras/
    ├── unity/VertexColor.shader
    └── godot/vertex_color.gdshader
```

### How the two channels work

| | Headless Channel | Live Channel |
|---|---|---|
| **Blender process** | Started and killed per tool call | Started once, stays open |
| **Communication** | Subprocess stdin/stdout | TCP socket `localhost:8081` |
| **Thread safety** | N/A (separate process) | `bpy.app.timers` dispatches to main thread |
| **State** | Stateless — fresh scene each time | Persistent — variables survive between calls |
| **Used by** | `create_mesh`, `create_from_script`, `batch_create` | `start_blender`, `execute_blender_python` |
| **Blender addon required** | No | No (auto-injected via `--python`) |

---

## Adding a New Engine Profile

Register a new profile in `src/dedal_mcp/engine_profiles.py`:

```python
register_profile(EngineProfile(
    name="myengine",
    display_name="My Engine",
    axis_forward="-Z",
    axis_up="Y",
    default_format="fbx",
    default_output_subdir="Resources/Meshes",
))
```

The profile is immediately available via `DEDAL_ENGINE=myengine` or the `engine` parameter on any tool call. No other code changes needed.

---

## Troubleshooting

**"Blender not found"**

Set the `BLENDER_PATH` environment variable to the full path of your Blender executable. The default is just `blender`, which requires it to be in your system PATH.

**Meshes have no color in my engine**

Most engines don't render vertex colors by default. Copy the appropriate shader from `extras/` into your project. See [Vertex Color Shaders](#vertex-color-shaders).

**Export axis is wrong / mesh is rotated**

Set the correct engine profile via `DEDAL_ENGINE` or the `engine` parameter. Unreal uses Z-up while Unity/Godot use Y-up — the profile handles this automatically.

**Blender takes a long time to start**

Blender's first launch loads add-ons and caches. Subsequent runs are faster. For multiple meshes, use `batch_create` instead of individual `create_mesh` calls — it runs one Blender session for all meshes.

**`list_presets` works but `create_mesh` fails**

`list_presets` runs locally (no Blender needed). `create_mesh` requires Blender to be installed and accessible. Check that `BLENDER_PATH` is correct and that `blender --version` works from your terminal.

**`execute_blender_python` says "Connection refused"**

Blender must be running with the RPC server. Call `start_blender` first and wait a few seconds for Blender to finish loading before sending commands.

**Calling `start_blender` twice**

This is safe. If the RPC server is already listening on port 8081, `start_blender` detects it and returns without launching a second instance.

**Live mode scripts seem to share variables**

This is by design. The `exec()` context persists between calls, so variables, functions, and imports from one `execute_blender_python` call are available in subsequent calls. This lets you build complex scenes incrementally.

---

## License

Apache 2.0
