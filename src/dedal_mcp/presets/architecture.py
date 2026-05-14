"""Architecture presets — buildings, walls, stairs, etc."""


def _build_house(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 4)
    h = size.get("y", 3)
    d = size.get("z", 5)
    roof_h = h * 0.5
    wc = colors.get("walls", "#C0C0C0")
    rc = colors.get("roof", "#CC4444")
    dc = colors.get("door", "#664422")
    return f"""
import bmesh

# Walls
bpy.ops.mesh.primitive_cube_add(size=1)
walls = bpy.context.active_object
walls.scale = ({w/2}, {d/2}, {h/2})
walls.location = (0, 0, {h/2})
walls.name = "{name}_walls"
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(walls, "{wc}")

# Roof prism
bpy.ops.mesh.primitive_cube_add(size=1)
roof = bpy.context.active_object
roof.scale = ({w/2 + 0.2}, {d/2 + 0.2}, {roof_h/2})
roof.location = (0, 0, {h + roof_h/2})
roof.name = "{name}_roof"
bpy.ops.object.transform_apply(scale=True)
bm = bmesh.new()
bm.from_mesh(roof.data)
for v in bm.verts:
    if v.co.z > 0.01:
        v.co.x *= 0.01
bm.to_mesh(roof.data)
bm.free()
_set_vertex_color_all(roof, "{rc}")

# Door
bpy.ops.mesh.primitive_cube_add(size=1)
door = bpy.context.active_object
door.scale = (0.4, 0.05, {h*0.55/2})
door.location = (0, -{d/2 + 0.01}, {h*0.55/2})
door.name = "{name}_door"
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(door, "{dc}")

# Join
for o in [walls, roof, door]:
    o.select_set(True)
bpy.context.view_layer.objects.active = walls
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


def _build_wall(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 5)
    h = size.get("y", 3)
    t = size.get("z", 0.3)
    c = colors.get("body", "#A0A0A0")
    return f"""
bpy.ops.mesh.primitive_cube_add(size=1)
obj = bpy.context.active_object
obj.name = "{name}"
obj.scale = ({w/2}, {t/2}, {h/2})
obj.location = (0, 0, {h/2})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(obj, "{c}")
"""


def _build_stairs(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 2)
    h = size.get("y", 3)
    d = size.get("z", 4)
    steps = int(size.get("steps", 8))
    c = colors.get("body", "#B0B0B0")
    step_h = h / steps
    step_d = d / steps
    lines = []
    for i in range(steps):
        lines.append(f"""
bpy.ops.mesh.primitive_cube_add(size=1)
s = bpy.context.active_object
s.name = "{name}_step_{i}"
s.scale = ({w/2}, {step_d/2}, {step_h/2})
s.location = (0, {-d/2 + step_d/2 + i * step_d}, {step_h/2 + i * step_h})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(s, "{c}")
""")
    lines.append(f"""
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = bpy.data.objects["{name}_step_0"]
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
""")
    return "\n".join(lines)


def _build_ramp(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 2)
    h = size.get("y", 2)
    d = size.get("z", 4)
    c = colors.get("body", "#B0B0B0")
    return f"""
import bmesh

bpy.ops.mesh.primitive_cube_add(size=1)
obj = bpy.context.active_object
obj.name = "{name}"
obj.scale = ({w/2}, {d/2}, {h/2})
obj.location = (0, 0, {h/2})
bpy.ops.object.transform_apply(scale=True)

bm = bmesh.new()
bm.from_mesh(obj.data)
for v in bm.verts:
    if v.co.y < 0 and v.co.z > 0:
        v.co.z = 0
bm.to_mesh(obj.data)
bm.free()
_set_vertex_color_all(obj, "{c}")
"""


def _build_pillar(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 0.4) / 2
    h = size.get("y", 3)
    bc = colors.get("base", "#999999")
    sc = colors.get("shaft", "#C0C0C0")
    return f"""
# Base
bpy.ops.mesh.primitive_cylinder_add(radius={r*1.3}, depth=0.15, vertices=16)
base = bpy.context.active_object
base.name = "{name}_base"
base.location = (0, 0, 0.075)
_set_vertex_color_all(base, "{bc}")

# Shaft
bpy.ops.mesh.primitive_cylinder_add(radius={r}, depth={h - 0.3}, vertices=16)
shaft = bpy.context.active_object
shaft.name = "{name}_shaft"
shaft.location = (0, 0, {h/2})
_set_vertex_color_all(shaft, "{sc}")

# Capital
bpy.ops.mesh.primitive_cylinder_add(radius={r*1.3}, depth=0.15, vertices=16)
cap = bpy.context.active_object
cap.name = "{name}_cap"
cap.location = (0, 0, {h - 0.075})
_set_vertex_color_all(cap, "{bc}")

for o in [base, shaft, cap]:
    o.select_set(True)
bpy.context.view_layer.objects.active = base
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


ARCHITECTURE = {
    "house": {
        "description": "Simple house: box walls + peaked roof + door. Colors: walls, roof, door",
        "builder": _build_house,
        "default_colors": {"walls": "#C0C0C0", "roof": "#CC4444", "door": "#664422"},
        "category": "architecture",
    },
    "wall": {
        "description": "Rectangular wall segment. Size: x=length, y=height, z=thickness",
        "builder": _build_wall,
        "default_colors": {"body": "#A0A0A0"},
        "category": "architecture",
    },
    "stairs": {
        "description": "Staircase. Size: x=width, y=height, z=depth, steps=count (default 8)",
        "builder": _build_stairs,
        "default_colors": {"body": "#B0B0B0"},
        "category": "architecture",
    },
    "ramp": {
        "description": "Sloped ramp. Size: x=width, y=height, z=depth",
        "builder": _build_ramp,
        "default_colors": {"body": "#B0B0B0"},
        "category": "architecture",
    },
    "pillar": {
        "description": "Column with base and capital. Size: x=diameter, y=height. Colors: base, shaft",
        "builder": _build_pillar,
        "default_colors": {"base": "#999999", "shaft": "#C0C0C0"},
        "category": "architecture",
    },
}
