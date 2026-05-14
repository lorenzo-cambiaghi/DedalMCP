# DedalMCP

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Blender%203.6%2B-orange.svg)
![MCP](https://img.shields.io/badge/mcp-compatible-green.svg)

```text
    Daedalus (Greek: Δαίδαλος) was the
    mythical master craftsman who built
    the Labyrinth for King Minos and
    crafted wings of wax and feathers.

    DedalMCP channels that craft: it
    lets your AI sculpt placeholder
    meshes in Blender and deliver them
    straight to your game engine.
```

> **Give your AI the power to generate 3D placeholder meshes on demand — for any game engine.**

Traditionally, when your AI needs a placeholder mesh for prototyping, it can only describe what you should model. With **DedalMCP**, the AI generates the mesh itself — vertex-colored, correctly oriented, and exported directly into your project folder. No Blender GUI, no modeling skills, no copy-paste.

### 🏛️ The "Wow" Factor: Talk to Blender

Imagine asking your AI:
> *"Create a placeholder village — a house with red roof, five pine trees, a stone wall around it, and some barrels near the entrance."*

- **Without DedalMCP:** The AI tells you to download assets from a store, or model them yourself, or use Unity primitives that look awful.
- **With DedalMCP:** The AI generates every mesh in seconds. Vertex-colored, correctly scaled in meters, exported as FBX/GLB, ready to drop into your scene.

**Example:** *"Generate a house placeholder"*
```
→ create_mesh {"name": "house", "preset": "house", "size": {"x":6, "y":4, "z":8},
               "colors": {"walls": "#D0D0D0", "roof": "#993333", "door": "#5C3A1E"}}
← Exported 1 file(s):
    Assets/Models/Placeholders/house.fbx (14280 bytes)
```

*(Curious about the internal architecture? Jump to the [Architecture](#architecture) section.)*

---

## 🔨 How it Works (Under the Hood)

DedalMCP is a Python [MCP](https://modelcontextprotocol.io/) server that runs **Blender in headless mode** (`--background --python`) to generate meshes. No Blender GUI ever opens. The server:

1. Receives a tool call from the AI (e.g. `create_mesh` with preset and colors)
2. Generates a complete `bpy` Python script from the preset template
3. Runs `blender --background --python script.py`
4. Blender creates the mesh, assigns vertex colors, and exports FBX/GLB
5. The file lands in your project folder, ready for import

```
AI: "Create a barrel, make it dark brown"

→ create_mesh {"name": "barrel", "preset": "barrel", "colors": {"body": "#5C3A1E"}}
← Exported 1 file(s):
    models/placeholders/barrel.fbx (8640 bytes)
```

No addon to install. No Blender window. Just meshes.

---

## Features

- **19 Built-in Presets**: Primitives, architecture, props, and vegetation — all parameterized by size and color.
- **Vertex Colors Only**: No textures, no UVs, no material setup. Minimal complexity for maximum prototyping speed.
- **Engine-Agnostic**: Built-in export profiles for **Unity**, **Godot**, **Unreal**, **Stride**, and **Flax** — correct axis orientation, scale, format, and output paths per engine.
- **Blender CLI**: Runs fully headless. No addon, no GUI, no interaction required.
- **Custom bpy Scripts**: When presets aren't enough, the AI can write raw Blender Python code.
- **Batch Generation**: Create dozens of meshes in a single Blender session for speed.

---

## The Perfect Combo: DedalMCP + AkerMCP

DedalMCP gives your AI the ability to **create 3D assets from scratch**. But to actually *place* them in a game scene, the AI also needs hands inside the engine.

We recommend running DedalMCP alongside [**AkerMCP**](https://github.com/lorenzo-cambiaghi/AkerMCP), our MCP bridge for C# game engines.

When combined, the AI gets a **complete prototyping pipeline**:
- **DedalMCP** generates placeholder FBX/GLB meshes via Blender.
- **AkerMCP** imports them into the engine and places them in the scene via `execute`.

```
1. DedalMCP → batch_create [house, tree x5, wall, barrel x3]  ← generates 10 FBX files
2. AkerMCP  → execute "AssetDatabase.Refresh()"               ← Unity imports them
3. AkerMCP  → execute "place everything in the scene"         ← objects appear in editor
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

> **Note:** Blender does not need to be open. DedalMCP runs it in headless mode via the command line.

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

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `create_mesh` | Create a mesh from a preset with custom size, colors, and engine profile |
| `create_from_script` | Run a custom bpy (Blender Python) script to create any mesh |
| `batch_create` | Create multiple meshes in one Blender session (faster) |
| `list_presets` | List all presets, parameters, default colors, and engine profiles |

Every tool accepts an optional `engine` parameter to override the default export profile.

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

→ create_from_script {"name": "spiral_staircase", "script": "
import math
bpy.ops.mesh.primitive_cube_add(size=0.5)
step = bpy.context.active_object
step.name = 'spiral_staircase'
# ... (custom bpy code for a spiral staircase)
"}
← Exported 1 file(s):
    models/placeholders/spiral_staircase.fbx (18400 bytes)
```

---

## Architecture

```
LLM (Claude, Cursor, Copilot, Antigravity)
    │ JSON-RPC 2.0 / stdio
    ▼
┌──────────────────────────┐
│     DedalMCP Server      │  Python MCP server
│   4 tools, 19 presets    │
│   6 engine profiles      │
└──────────┬───────────────┘
           │ subprocess: blender --background --python
           ▼
┌──────────────────────────┐
│      Blender CLI         │  Headless, no GUI
│  bpy script generates    │
│  mesh + vertex colors    │
│  → exports FBX / GLB     │
└──────────┬───────────────┘
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
│   ├── server.py                  MCP server — 4 tools
│   ├── blender_runner.py          Subprocess: blender --background --python
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

---

## License

Apache 2.0
