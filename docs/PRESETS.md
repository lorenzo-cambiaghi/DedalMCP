# Writing Custom Presets

> This guide moved here from the README. It covers everything about authoring preset JSON files: the four preset types, worked tutorials, the Blender companion plugin, and a troubleshooting table.

Presets are plain JSON files. DedalMCP discovers them automatically at startup — **no code to write, no rebuild, no restart of Blender**. If you know how to add a cube to a Blender scene and tweak its scale, you already have enough Blender skill to write a preset.

This guide walks you through:
1. Where to put your JSON file
2. The fields every preset has (common to all types)
3. The two preset types — when to use each
4. A worked example for each type, line by line
5. How to test your preset
6. Overriding a built-in
7. Common mistakes and how to debug them

---

### 1. Where do I put my JSON file?

DedalMCP looks in four places, in this order. **Later locations win** if two files share the same `"name"`:

| # | Location | When to use it |
|---|----------|----------------|
| 1 | `src/dedal_mcp/presets/data/` (inside the installed package) | Built-in presets only. Don't put your own files here — they'd be lost on reinstall. |
| 2 | Directories listed in the `DEDAL_PRESETS_PATH` environment variable | When you want a specific folder, e.g. a shared team library. Multiple folders allowed (separator: `:` on macOS/Linux, `;` on Windows). |
| 3 | `~/.dedal/presets/` (your home folder) | **Recommended for personal presets**. Always available, no matter which project you're working in. |
| 4 | `./dedal_presets/` (next to wherever you launch the MCP server from) | **Recommended for project-specific presets**. Lives in the project's git repo, shared with your team. |

#### Step-by-step: create your first preset folder

**macOS / Linux:**
```bash
mkdir -p ~/.dedal/presets
```

**Windows (PowerShell):**
```powershell
mkdir $HOME\.dedal\presets
```

Now drop any `.json` file in there. The next time the MCP server starts, your preset is available. Verify with:

```
"list the available mesh presets"
```

Your custom preset should appear in the output, marked by its category.

> **No restart of Blender needed** — presets are read by the MCP server (Python process), not by Blender. Just restart your AI client (Claude Code, Cursor, etc.) so it reloads the server.

---

### 2. Fields every preset must have

Regardless of the type (`composite`, `script_template`, `mesh_data`, or `geometry_nodes`), every preset declares the same handful of identification fields. Type-specific fields are documented in each tutorial below.

```json
{
  "type": "composite",
  "version": 1,
  "name": "mything",
  "category": "prop",
  "description": "What this preset makes and which size/color keys it accepts",
  "default_colors": {"body": "#808080"},
  "size_defaults": {"x": 1, "y": 1, "z": 1}
}
```

| Field | Meaning |
|---|---|
| `type` | Which **interpreter** parses the rest of the file. One of `"composite"`, `"script_template"`, `"mesh_data"`, `"geometry_nodes"` (more types can be added by registering a new interpreter in `src/dedal_mcp/presets/types/`). |
| `version` | Schema version of the type. Currently `1` for all built-in types. Future-proofs your JSON: if a `composite v2` ever ships, your `v1` files keep working unchanged. |
| `name` | The name the AI uses to request your preset: `create_mesh {"preset": "mything", ...}`. Lowercase, no spaces. Must be unique (or it overrides a built-in by the same name). |
| `category` | Free-text label used only to group presets in `list_presets` output. Common values: `primitive`, `architecture`, `prop`, `vegetation`, `custom`. |
| `description` | Shown to the AI when it lists presets. **Be explicit about what `size.x`, `size.y`, `size.z` and each color zone mean** — the AI uses this to set sensible defaults. |
| `default_colors` | A dict of *zone-name → hex color*. Each "zone" is a logical region of the mesh (e.g. `"trunk"`, `"crown"`, `"walls"`, `"roof"`). The user can override any zone per-call by passing `colors: {"zone": "#XXYYZZ"}`. The hex string is converted to vertex colors on the mesh. Not used by `mesh_data` (colors baked) or `geometry_nodes` (colors come through input sockets). |
| `size_defaults` | Default numeric parameters used when the user omits `size`. **Convention**: `x` = width, `y` = height, `z` = depth, all in **meters**. You can also define custom keys (e.g. `"steps"` for stairs). The user can override any key per-call by passing `size: {"x": 5}`. Not used by `mesh_data` (geometry is baked); for `geometry_nodes` the `size` dict carries input socket values instead. |

> **Vertex colors, not textures.** DedalMCP paints the mesh with colors stored directly on the vertices — there are no image files, no UV maps, no materials. Most engines need a small shader to display them; see the [Vertex Color Shaders](../README.md#vertex-color-shaders) section.

---

### 3. Which type should I pick?

| If your preset is… | Use this type |
|---|---|
| A handful of standard primitives (cube, sphere, cylinder, …) placed and joined together | **`composite`** — declarative, no Python, safest |
| Anything that needs **loops** (e.g. 8 steps in a staircase), **bmesh** (custom vertex displacement), **modifiers** (bevel, mirror), or **randomness** | **`script_template`** — you write the bpy code, with placeholders |
| A **hand-modeled mesh** with custom vertex positions and colors — anything you can't reach with primitives alone | **`mesh_data`** — raw geometry baked into the JSON, typically produced by the Blender plugin |
| A **procedural Geometry Nodes tree** authored in Blender that the AI parameterises (scatter, road generators, fractals, anything driven by GN inputs) | **`geometry_nodes`** — invokes a node group from a `.blend` file, AI passes input sockets via `size` |

When in doubt, start with `composite`. If you find yourself unable to express the shape, switch to `script_template`. If you want to model the shape *visually in Blender* and export, use `mesh_data` via the [companion plugin](#blender-plugin-for-visual-preset-editing). If you want **procedural parametric generation** driven by a Geometry Nodes tree, use [`geometry_nodes`](#4e-the-geometry_nodesv1-type).

---

### 4a. Tutorial — building a `composite` preset

Let's build a **watchtower**: a cylindrical base with a cone roof. Save this as `~/.dedal/presets/watchtower.json`:

```json
{
  "type": "composite",
  "version": 1,
  "name": "watchtower",
  "category": "architecture",
  "description": "Watchtower with cylindrical base and conical roof. Size: x=diameter, y=total height. Colors: base, roof",
  "default_colors": {"base": "#A0A0A0", "roof": "#993333"},
  "size_defaults": {"x": 4, "y": 8},
  "parts": [
    {
      "shape": "cylinder",
      "params": {"radius": "x/2", "depth": "y*0.7", "vertices": 16},
      "location": [0, 0, "y*0.35"],
      "color": "base"
    },
    {
      "shape": "cone",
      "params": {"radius1": "x*0.6", "radius2": 0, "depth": "y*0.3"},
      "location": [0, 0, "y*0.85"],
      "rotation": [0, 0, 0],
      "color": "roof"
    }
  ],
  "join": true
}
```

#### Walk-through

- **`parts`** is the list of primitives the preset builds. Each part becomes one Blender object that is later joined into the final mesh.
- **`shape`** picks which Blender primitive operator to call. See the [shape reference](#composite-shape-reference) below for the full list and their parameters.
- **`params`** are the arguments to the primitive's `bpy.ops.mesh.primitive_*_add(...)` call. Values can be **literal numbers** (`16`) or **expressions** (`"x/2"`) that reference keys from `size_defaults` / the user's `size` override.
- **`location`** is the part's position in world coordinates as `[x, y, z]` in meters. Blender is **Z-up by default**: `z` = vertical. Each element can be a number or an expression. Default is `[0, 0, 0]`.
- **`rotation`** is the part's rotation as `[rx, ry, rz]` in **degrees** (more readable than radians; conversion happens automatically). Each element can be a number or an expression. Default is `[0, 0, 0]`. When non-zero, `transform_apply(rotation=True)` is emitted to bake the rotation into the mesh data — same idea as scale.
- **`scale`** (not used here) is `[sx, sy, sz]`, multiplier on each axis. Default is `[1, 1, 1]`. When you scale a part, `transform_apply(scale=True)` is emitted right after, baking the scale into the mesh data. The object's `scale` is then back to 1 and the `location` you specify still refers to world coordinates — scaling never affects where you place things.
- **`color`** is the **name of a zone** declared in `default_colors`. Not a hex string — a key. This lets the user re-tint the part by passing `colors: {"base": "#0000FF"}` without editing the JSON.
- **`join: true`** joins all parts into one Blender object at the end, using the preset's `name`. Default is `true` when there are 2+ parts.

#### Expressions you can use in `params`, `scale`, `location`

The values inside strings are evaluated **safely** — there is no `eval`, no Python imports, no attribute access. Only:

- Arithmetic: `+ - * / % **`
- Unary: `-x`, `+x`
- Comparisons: `<`, `<=`, `>`, `>=`, `==`, `!=`
- Conditional: `a if cond else b`
- Calls to: `min`, `max`, `abs`, `int`, `float`, `round`
- Names: any key from `size_defaults` (so `x`, `y`, `z`, plus anything you've added like `steps`, `bevel_width`, …)

Anything else (attribute access like `x.something`, function definitions, imports) is rejected by the safe evaluator with a clear error.

> **What is checked when:** The JSON schema (`type`, `version`, `shape` names, color zones, allowed shape params) is validated at server boot. Expressions inside `params`/`scale`/`location` are evaluated *lazily* — only when the preset is invoked. A typo in an expression won't fail at boot, it'll fail the first time someone calls `create_mesh` with that preset.

#### Composite shape reference

| `shape` | Parameters (defaults in parens) | Notes |
|---|---|---|
| `cube` | `size` (1) | A unit cube. Use `scale` to stretch into a box. |
| `sphere` / `uv_sphere` | `radius` (1), `segments` (16), `ring_count` (12) | Smooth sphere. Lower segments = blockier, faster. |
| `icosphere` | `radius` (1), `subdivisions` (2) | More uniform vertex distribution — best base for displaced shapes (rocks). |
| `cylinder` | `radius` (1), `depth` (2), `vertices` (16) | `depth` is the height along Z. |
| `cone` | `radius1` (1, base), `radius2` (0, tip), `depth` (2), `vertices` (16) | Set `radius2 > 0` for a truncated cone. |
| `plane` | `size` (1) | Flat 1×1 quad on the XY plane. |
| `torus` | `major_radius` (1), `minor_radius` (0.25), `major_segments` (24), `minor_segments` (12) | Donut shape. |

Only the parameters listed above are accepted per shape. Passing an unknown one (e.g. `"depth"` on a cube) fails at load time with a clear error.

---

### 4b. Tutorial — building a `script_template` preset

Use `script_template` when you need full Blender Python: loops, `bmesh`, modifiers, randomness. The JSON contains a **list of code lines** that DedalMCP fills in with the user's `size` and `colors` values, then runs inside Blender.

Save this as `~/.dedal/presets/spiral_stairs.json`:

```json
{
  "type": "script_template",
  "version": 1,
  "name": "spiral_stairs",
  "category": "architecture",
  "description": "Spiral staircase. Size: x=step width, y=total height, z=radius from center, steps=count (default 12)",
  "default_colors": {"body": "#B0B0B0"},
  "size_defaults": {"x": 0.8, "y": 3, "z": 1.5, "steps": 12},
  "script": [
    "import math",
    "step_w = {x}",
    "total_h = {y}",
    "radius = {z}",
    "steps = int({steps})",
    "mesh_name = {name|repr}",
    "step_color = {color.body|repr}",
    "step_h = total_h / steps",
    "angle_step = (math.pi * 2) / steps",
    "",
    "for i in range(steps):",
    "    angle = i * angle_step",
    "    cx = radius * math.cos(angle)",
    "    cy = radius * math.sin(angle)",
    "    bpy.ops.mesh.primitive_cube_add(size=1)",
    "    s = bpy.context.active_object",
    "    s.name = mesh_name + '_step_' + str(i)",
    "    s.scale = (step_w / 2, 0.4, step_h / 2)",
    "    s.location = (cx, cy, step_h / 2 + i * step_h)",
    "    s.rotation_euler = (0, 0, angle)",
    "    bpy.ops.object.transform_apply(scale=True, rotation=True)",
    "    _set_vertex_color_all(s, step_color)",
    "",
    "bpy.ops.object.select_all(action='SELECT')",
    "bpy.context.view_layer.objects.active = bpy.data.objects[mesh_name + '_step_0']",
    "bpy.ops.object.join()",
    "obj = bpy.context.active_object",
    "obj.name = mesh_name"
  ]
}
```

#### Walk-through

- **`script`** is a list of strings, joined with newlines into a Python program. Writing as a list (vs one giant string) keeps the JSON readable.
- The script runs **inside Blender** as Python code. Before your script runs, DedalMCP automatically:
  - Imports `bpy`
  - Clears the scene (deletes any default objects)
  - Defines helper functions `_set_vertex_color_all` and `_set_vertex_color_faces`
- The `{...}` markers are **placeholders**. DedalMCP replaces them on the Python side *before* the code reaches Blender. Then it `compile()`-checks the rendered script. **Only Python syntax errors are caught at startup** — typos in a `bpy.ops.something_that_does_not_exist(...)`, missing variables, or wrong API usage only show up when Blender actually runs the script (the error comes back in the MCP response).

#### Placeholder reference

| Placeholder | Replaced with | Example output |
|---|---|---|
| `{x}`, `{y}`, `{z}`, `{steps}`, `{my_custom_key}` | the numeric value from `size_defaults` (or the user's override) | `1.5` |
| `{name}` | the raw mesh name (no quotes) | `mychair` |
| `{name\|repr}` | a properly quoted Python string literal | `'mychair'` |
| `{color.body}` | the raw color string | `#808080` |
| `{color.<zone>}` | same, for any zone declared in `default_colors` | `#993333` |
| `{color.body\|repr}` | the color as a quoted string literal | `'#808080'` |

> **Always use `|repr` when embedding the value in Python source code as a string.** Without it, a value like `it's red` would break your script when used as `'{name}'` → `'it's red'` (syntax error). With `|repr` you get `'it\'s red'` automatically, and it's also impossible for a malicious value to inject extra code.

#### What you can use in the script

- The full `bpy` API (operators, data access, anything Blender's Python supports)
- `import bmesh`, `import math`, `import random`, etc. — standard library is available
- The helpers `_set_vertex_color_all(obj, "#RRGGBB")` and `_set_vertex_color_faces(obj, [face_indices], "#RRGGBB")`

#### Things you **cannot** do

The placeholder syntax `{name}` collides with two Python constructs. Avoid both inside templates:

1. **f-strings** — `f"step_{i}"` would have its `{i}` substituted by DedalMCP:

   ```python
   # BAD — DedalMCP will try to resolve {i} as a size key and fail at load time
   s.name = f"{mesh_name}_step_{i}"

   # GOOD
   s.name = mesh_name + "_step_" + str(i)
   ```

2. **Set literals with a single name** — `{x}` looks like a set containing the variable `x` but will be silently replaced by the numeric value of `x`:

   ```python
   # BAD — becomes "unique = 5.0" at substitution, not a set
   unique = {x}

   # GOOD — set() avoids the placeholder pattern
   unique = set([x])
   ```

Multi-element set literals like `{x, y}` are safe (the comma stops the placeholder regex).

---

### 4c. The `mesh_data/v1` type

When `composite` and `script_template` are both too restrictive — typically because you've modeled the shape by hand in Blender — use `mesh_data`. It carries the **raw geometry** (vertex positions, face indices, optional per-vertex colors) directly in the JSON.

```json
{
  "type": "mesh_data",
  "version": 1,
  "name": "carved_pillar",
  "category": "custom",
  "description": "Pillar with hand-sculpted top",
  "vertices": [[0,0,0], [1,0,0], [0,1,0], [0,0,1], ...],
  "faces": [[0,1,2], [0,2,3], ...],
  "vertex_colors": [[0.8,0.6,0.4,1.0], [0.8,0.6,0.4,1.0], ...]
}
```

| Field | Meaning |
|---|---|
| `vertices` | Array of `[x, y, z]` in meters, **world coordinates** at export time (transforms already baked). |
| `faces` | Array of vertex-index arrays. Triangles (`[i,j,k]`) or quads (`[i,j,k,l]`) — n-gons supported. Indices must be `0 ≤ i < len(vertices)`. |
| `vertex_colors` | *Optional*. One `[r, g, b]` or `[r, g, b, a]` per vertex, values `0–1`. If omitted, the mesh is uncolored. |

> **`mesh_data` ignores `size` and `colors` overrides** from `create_mesh`. The geometry is baked at export time. To change anything, re-edit in Blender and re-export.

You almost never write a `mesh_data` JSON by hand — the file would be huge and unreadable. Instead, use the **Blender plugin** described next, which generates these files for you and can also re-open them for editing.

---

### 4d. Blender plugin for visual preset editing

For users who'd rather model in Blender's viewport than write JSON, the repo ships a single-file Blender addon at `extras/blender_plugin/dedal_preset_editor.py`. It produces and consumes `composite/v1` and `mesh_data/v1` files, with **intelligent type detection**: if you only translate/rotate/scale a primitive, it stays parametric; if you edit its vertices or add modifiers, it becomes mesh data.

#### Installation

1. Open Blender → **Edit > Preferences > Add-ons > Install...**
2. Pick `extras/blender_plugin/dedal_preset_editor.py` from this repo.
3. Enable the checkbox next to "Import-Export: DedalMCP Preset Editor".
4. Press **N** in the 3D viewport. A "DedalMCP" tab appears in the sidebar.

#### Workflow

**Authoring a new composite preset** (e.g. a treehouse):

1. In the **Add Primitive** section, pick a color and click "Cube" — a tagged cube appears in the scene.
2. Move/rotate/scale it however you want. A tagged primitive stays parametric as long as you don't edit its vertices.
3. Add more primitives (cube for trunk, cylinder for branches, …). Each one is independently tagged.
4. In the **Export Preset** section, set the name/category/description, click **Export Selection as Preset**.
5. The plugin checks each selected object:
   - All still primitives? → exports as `composite/v1` (parts with their TRS preserved).
   - Any have edited vertices or modifiers? → exports as `mesh_data/v1` (everything joined and baked).
6. The JSON lands in `~/.dedal/presets/<name>.json` by default. It's immediately discoverable by the MCP server on next restart.

**Re-editing an existing preset**:

1. Click **Import Preset** and pick the JSON.
   - `composite` files: each part becomes a separate primitive in the scene, re-tagged so you can keep editing parametrically.
   - `mesh_data` files: a single mesh appears, with vertex colors restored.
   - `script_template` files: cannot be edited visually — the plugin shows an error message, you must edit the JSON by hand.
2. Make your changes. The N-panel header shows the current object's state (`✓ cube (parametric)` or `⚠ cube (geometry edited)`).
3. Re-export. If you only adjusted transforms, you get back a clean `composite`. If you edited geometry, it becomes `mesh_data`.

#### Marking an existing object

If you have an object that wasn't created via the plugin's "Add" buttons (e.g. you used Blender's standard menu), select it, pick the matching shape in the **Tag Existing Object** section, and click **Mark**. You're attesting that the object is still pristine geometry — the plugin trusts you and tags it accordingly.

#### What the plugin does NOT do

- It does not preview presets that use `size`/`colors` parameters (`composite` expressions like `"x/2"` are not evaluated on import — defaults are used). Editing a built-in like `house` will reproduce its geometry roughly, but re-exporting won't preserve the parametric size relationships.
- It does not communicate with the running MCP server. You must restart the AI client after export for the new preset to appear in `list_presets`.

---

### 4e. The `geometry_nodes/v1` type

For procedural assets driven by a **Geometry Nodes tree** you authored in Blender. The JSON points to a `.blend` file and a node group inside it, declares which input sockets the AI can drive, and the server appends the tree, sets the inputs, bakes the modifier, exports.

This unlocks the full procedural power of Blender from a single JSON descriptor: scatterers, spline-based road/wall/path generators, fractal trees, tessellators, anything the GN system can model.

#### Where the `.blend` files live

Drop them in one of these directories (DedalMCP searches in order, first match wins):

1. Any directory in the `DEDAL_BLENDS_PATH` environment variable (OS-pathsep separated)
2. `~/.dedal/blends/` *(recommended for personal trees)*
3. `./dedal_blends/` next to where you launch the server *(for project-specific trees)*

The JSON references the blend by **basename only** — `"blend": "road.blend"`, no path. Path separators or `..` are rejected at load time. The filename allowlist accepts letters, digits, underscores, dots, and dashes — no spaces.

#### Schema overview

```json
{
  "type": "geometry_nodes",
  "version": 1,
  "name": "road",
  "category": "infrastructure",
  "description": "Procedural road. Inputs: Width, Asphalt, Path (curve), Density (attribute)",
  "blend": "road.blend",
  "node_group": "RoadGenerator",
  "base_geometry": "primitive:empty",
  "inputs": {
    "Width":   {"type": "float", "default": 4.0},
    "Lanes":   {"type": "int",   "default": 2},
    "Asphalt": {"type": "color", "default": "#3A3A3A"},
    "Path":    {"type": "curve", "attributes": {"banking": "float"}},
    "Markers": {"type": "points", "attributes": {"rotation": "vector", "scale": "float"}},
    "Density": {"type": "attribute", "data_type": "FLOAT", "domain": "POINT", "default": 1.0}
  }
}
```

| Field | Meaning |
|---|---|
| `blend` | Filename of the `.blend` file. Basename only. |
| `node_group` | Name of the Geometry Nodes tree inside the `.blend` (the tree appears in `bpy.data.node_groups`). |
| `base_geometry` | What hosts the GN modifier: `"primitive:<shape>"` for cube/sphere/cylinder/cone/plane/torus/icosphere/empty, or `"preset:<name>"` to recursively use another preset's output. Default `"primitive:empty"`. |
| `inputs` | Dict: socket name → spec. Names must match the GN tree's input socket names **exactly** (case-sensitive, spaces preserved). |

#### Input types

**Scalar** — directly fed to the GN socket:

| `type` | AI passes | Notes |
|---|---|---|
| `float` | number | `"default": 4.0` |
| `int` | int | `"default": 2` |
| `bool` | true/false | `"default": true` |
| `string` | string | `"default": "main"` |
| `vector` | `[x, y, z]` | `"default": [10, 10, 0]` |
| `color` | hex string | `"default": "#3A3A3A"` — converted to RGBA at runtime |

**Array (constructed geometry)** — DedalMCP builds a temporary Curve/Mesh/Point cloud object and plugs it as the socket's Geometry input. Each can declare `attributes` with per-element values (rotation per spline point for road banking, scale per scatter marker, etc.).

| `type` | AI passes | What gets built |
|---|---|---|
| `curve` | `{"positions": [...], "tangents": [...], <attr>: [...]}` | Bezier curve object; tangents are optional (auto handles if omitted). |
| `points` | `{"positions": [...], <attr>: [...]}` | Point cloud (mesh with vertices only). |
| `mesh` | `{"vertices": [...], "faces": [...], <attr>: [...]}` | Full mesh. |

Per-element attribute declaration in JSON: `"attributes": {"banking": "float", "rotation": "vector"}`. The AI then includes those keys in the payload as arrays the same length as `positions`/`vertices`. Inside the GN tree you read them via a **Named Attribute** node.

**Per-base-geometry attribute** — does NOT construct geometry. Writes a Named Attribute directly on the `base_geometry`. Used when the GN tree reads custom per-vertex/per-face data on its input geometry.

```json
"Density": {
  "type": "attribute",
  "data_type": "FLOAT",
  "domain": "POINT",
  "default": 1.0
}
```

`data_type` ∈ `FLOAT | INT | BOOLEAN | FLOAT_VECTOR | FLOAT_COLOR | BYTE_COLOR`. `domain` ∈ `POINT | EDGE | FACE | CORNER`. The AI can pass a scalar (broadcast to all elements) or an array.

#### Example invocation

```
create_mesh {
  "preset": "road",
  "name": "test_road",
  "size": {
    "Width": 6,
    "Asphalt": "#2A2A2A",
    "Path": {
      "positions": [[0,0,0], [10,0,0], [20,5,0]],
      "tangents":  [[1,0,0], [1,0,0], [1,1,0]],
      "banking":   [0, 0, 15]
    },
    "Density": [1.0, 2.0, 0.5]
  }
}
```

#### Validation, security, and lifecycle

- **Schema validation at boot**: type fields, input types, hex colors, base_geometry syntax. The blend file itself is *not* opened at boot.
- **Lazy blend resolution**: missing `.blend` file or wrong `node_group` name surfaces at first invocation with a clear error listing where DedalMCP searched.
- **Security**: `use_scripts_auto_execute = False` is force-set in the generated script before any `libraries.load`. Auto-running Python inside user `.blend` files is disabled by default.
- **Modifier baked**: after setting inputs, `bpy.ops.object.modifier_apply()` bakes the result into mesh data. The exported FBX/GLB contains static geometry, not a GN modifier.
- **Cleanup**: temporary curve/points/mesh objects built for input sockets are removed before export, so they don't end up in the final file.

#### Workflow

1. Open Blender, build a Geometry Nodes tree on a test object, expose the inputs you want to parametrize. Note the **exact** socket names.
2. Save the .blend to `~/.dedal/blends/<your_name>.blend`.
3. Write a JSON in `~/.dedal/presets/<your_name>.json` declaring the inputs.
4. Restart your AI client. Verify with `list_presets`. Call `create_mesh`.

If a socket name in the JSON doesn't exist in the tree, you'll see `GN input socket 'X' not found in node group 'Y'` at invocation. Edit the JSON to match and retry.

---

### 5. Testing your preset

Once you've written the JSON, **restart your AI client** so the MCP server reloads. Then ask the AI:

```
"List the available mesh presets"
```

Your preset should appear with its description.

To actually generate the mesh:

```
"Create a mesh called my_test using my new preset"
```

If anything's wrong with the JSON:

- **Schema or syntax error** in your file → the server logs a warning on stderr but keeps running with the other presets. Look at the MCP server log.
- **Runtime error** in a `script_template` → the bpy code fails inside Blender; the error comes back in the MCP response.

You can also validate without an AI client by running the loader directly:

```bash
python3 -c "from dedal_mcp.presets import PRESETS; print(sorted(PRESETS))"
```

---

### 6. Overriding a built-in preset

Want a darker default house, or a `cube` that's beveled by default? Drop a JSON file with the **same `name`** as a built-in into one of your user directories. It wins. A warning is logged so you know an override is active.

Example: `~/.dedal/presets/cube.json` overrides the built-in cube for your entire user account, in every project.

---

### 7. Common mistakes

| Symptom | Likely cause |
|---|---|
| `Preset 'foo' from /your/path overrides /built-in/path` warning | Your file's `name` matches a built-in. Either rename, or intentionally override. |
| `Unknown preset type 'xyz' v1. Known: composite/v1, geometry_nodes/v1, mesh_data/v1, script_template/v1` | Typo in `"type"`, or you meant one of the four known types. |
| `mesh_data preset missing required fields: ['faces']` | The `mesh_data` JSON must declare `vertices` AND `faces`. Re-export from the plugin. |
| `faces[N] index X out of range [0,Y)` | Face indices reference vertices that don't exist. Usually means hand-edited JSON or a corrupted export. |
| `'blend' must be a bare filename ending in .blend` | A `geometry_nodes` preset declared `"blend": "path/to/file.blend"` or used `..`. Use basename only and put the file in `~/.dedal/blends/`. |
| `Blend file 'X.blend' not found. Searched: ...` | At invocation, DedalMCP couldn't find the .blend in any blend dir. Copy it to `~/.dedal/blends/` or set `DEDAL_BLENDS_PATH`. |
| `GN input socket 'X' not found in node group 'Y'` | The JSON declares an input that doesn't exist in the GN tree (rename in JSON or in the tree). |
| `Node group 'X' not found in Y.blend` | The `node_group` name in the JSON doesn't match any tree inside the .blend. |
| `Cycle detected in base_geometry: A -> B -> A` | A `geometry_nodes` preset references itself (directly or via chain) through `base_geometry: "preset:..."`. Break the cycle. |
| `parts[N] unknown shape 'cubed'` | Typo in `shape`. See the shape reference table. |
| `parts[N] references color zone 'walls' not declared in default_colors` | You wrote `"color": "walls"` but never declared `"walls"` in `default_colors`. Add it. |
| `Unknown name 'width' in expression 'width/2'` | You used a variable in an expression that isn't in `size_defaults`. Either rename to `x`, or add `"width": 1` to `size_defaults`. |
| `Only calls to ['abs', 'float', 'int', 'max', 'min', 'round'] allowed` | You tried to use something like `math.sin(x)` in an expression. Expressions don't have access to `math`. Either precompute a constant, or switch to a `script_template` where you can `import math`. |
| `rendered template has a syntax error at line N` | Python syntax error in your `script` after placeholder substitution. The line number refers to the rendered (substituted) script — most often a missing colon, a stray `{...}` not meant as a placeholder, or an f-string. |
| Preset works but a Python set literal `{x}` becomes a number | DedalMCP substituted the placeholder. See *Things you cannot do* — wrap in `set([...])`. |
| Preset fails inside Blender with `NameError`/`AttributeError` | Load-time validation only catches syntax errors, not undefined names or wrong bpy API calls. Fix the script and retry. |
