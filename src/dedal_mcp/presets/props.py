"""Prop presets — furniture, vegetation, rocks, containers."""


def _build_crate(name: str, size: dict, colors: dict) -> str:
    s = size.get("x", 1)
    c = colors.get("body", "#8B6914")
    return f"""
bpy.ops.mesh.primitive_cube_add(size={s})
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {s/2})
mod = obj.modifiers.new(name="Bevel", type='BEVEL')
mod.width = {s * 0.03}
mod.segments = 1
bpy.ops.object.modifier_apply(modifier="Bevel")
_set_vertex_color_all(obj, "{c}")
"""


def _build_barrel(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 0.5) / 2
    h = size.get("y", 1)
    bc = colors.get("body", "#8B6914")
    band = colors.get("bands", "#444444")
    return f"""
bpy.ops.mesh.primitive_cylinder_add(radius={r}, depth={h}, vertices=16)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {h/2})

# Slight barrel bulge via proportional edit on middle loop
import bmesh
bm = bmesh.new()
bm.from_mesh(obj.data)
for v in bm.verts:
    frac = abs(v.co.z) / ({h/2})
    bulge = 1.0 + 0.08 * (1.0 - frac * frac)
    v.co.x *= bulge
    v.co.y *= bulge
bm.to_mesh(obj.data)
bm.free()
_set_vertex_color_all(obj, "{bc}")
"""


def _build_table(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 1.2)
    h = size.get("y", 0.75)
    d = size.get("z", 0.8)
    top_t = 0.05
    leg_r = 0.03
    tc = colors.get("top", "#A0784C")
    lc = colors.get("legs", "#6B4226")
    return f"""
# Table top
bpy.ops.mesh.primitive_cube_add(size=1)
top = bpy.context.active_object
top.name = "{name}_top"
top.scale = ({w/2}, {d/2}, {top_t/2})
top.location = (0, 0, {h})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(top, "{tc}")

# Legs
leg_h = {h - top_t}
offsets = [({w/2 - leg_r*2}, {d/2 - leg_r*2}), ({-w/2 + leg_r*2}, {d/2 - leg_r*2}),
           ({w/2 - leg_r*2}, {-d/2 + leg_r*2}), ({-w/2 + leg_r*2}, {-d/2 + leg_r*2})]
legs = []
for i, (lx, ly) in enumerate(offsets):
    bpy.ops.mesh.primitive_cube_add(size=1)
    leg = bpy.context.active_object
    leg.name = f"{name}_leg_{{i}}"
    leg.scale = ({leg_r}, {leg_r}, leg_h / 2)
    leg.location = (lx, ly, leg_h / 2)
    bpy.ops.object.transform_apply(scale=True)
    _set_vertex_color_all(leg, "{lc}")
    legs.append(leg)

# Join
for o in [top] + legs:
    o.select_set(True)
bpy.context.view_layer.objects.active = top
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


def _build_chair(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 0.45)
    seat_h = size.get("y", 0.45)
    d = size.get("z", 0.45)
    back_h = seat_h * 0.8
    sc = colors.get("seat", "#A0784C")
    lc = colors.get("legs", "#6B4226")
    return f"""
# Seat
bpy.ops.mesh.primitive_cube_add(size=1)
seat = bpy.context.active_object
seat.name = "{name}_seat"
seat.scale = ({w/2}, {d/2}, 0.02)
seat.location = (0, 0, {seat_h})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(seat, "{sc}")

# Back
bpy.ops.mesh.primitive_cube_add(size=1)
back = bpy.context.active_object
back.name = "{name}_back"
back.scale = ({w/2}, 0.02, {back_h/2})
back.location = (0, {-d/2 + 0.02}, {seat_h + back_h/2})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(back, "{sc}")

# Legs
leg_t = 0.025
legs = []
for i, (lx, ly) in enumerate([({w/2-leg_t},{d/2-leg_t}),({-w/2+leg_t},{d/2-leg_t}),
                               ({w/2-leg_t},{-d/2+leg_t}),({-w/2+leg_t},{-d/2+leg_t})]):
    bpy.ops.mesh.primitive_cube_add(size=1)
    leg = bpy.context.active_object
    leg.name = f"{name}_leg_{{i}}"
    leg.scale = (leg_t, leg_t, {seat_h/2})
    leg.location = (lx, ly, {seat_h/2})
    bpy.ops.object.transform_apply(scale=True)
    _set_vertex_color_all(leg, "{lc}")
    legs.append(leg)

for o in [seat, back] + legs:
    o.select_set(True)
bpy.context.view_layer.objects.active = seat
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


def _build_tree_pine(name: str, size: dict, colors: dict) -> str:
    h = size.get("y", 4)
    trunk_h = h * 0.3
    crown_h = h * 0.7
    trunk_r = h * 0.04
    crown_r = h * 0.2
    tc = colors.get("trunk", "#6B4226")
    cc = colors.get("crown", "#2D6B2D")
    return f"""
# Trunk
bpy.ops.mesh.primitive_cylinder_add(radius={trunk_r}, depth={trunk_h}, vertices=8)
trunk = bpy.context.active_object
trunk.name = "{name}_trunk"
trunk.location = (0, 0, {trunk_h/2})
_set_vertex_color_all(trunk, "{tc}")

# Crown
bpy.ops.mesh.primitive_cone_add(radius1={crown_r}, radius2=0, depth={crown_h}, vertices=8)
crown = bpy.context.active_object
crown.name = "{name}_crown"
crown.location = (0, 0, {trunk_h + crown_h/2})
_set_vertex_color_all(crown, "{cc}")

trunk.select_set(True)
crown.select_set(True)
bpy.context.view_layer.objects.active = trunk
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


def _build_tree_round(name: str, size: dict, colors: dict) -> str:
    h = size.get("y", 4)
    trunk_h = h * 0.4
    crown_r = h * 0.25
    trunk_r = h * 0.04
    tc = colors.get("trunk", "#6B4226")
    cc = colors.get("crown", "#2D8B2D")
    return f"""
bpy.ops.mesh.primitive_cylinder_add(radius={trunk_r}, depth={trunk_h}, vertices=8)
trunk = bpy.context.active_object
trunk.name = "{name}_trunk"
trunk.location = (0, 0, {trunk_h/2})
_set_vertex_color_all(trunk, "{tc}")

bpy.ops.mesh.primitive_uv_sphere_add(radius={crown_r}, segments=12, ring_count=8)
crown = bpy.context.active_object
crown.name = "{name}_crown"
crown.location = (0, 0, {trunk_h + crown_r * 0.7})
_set_vertex_color_all(crown, "{cc}")

trunk.select_set(True)
crown.select_set(True)
bpy.context.view_layer.objects.active = trunk
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
"""


def _build_rock(name: str, size: dict, colors: dict) -> str:
    s = size.get("x", 1)
    c = colors.get("body", "#777777")
    return f"""
import random
bpy.ops.mesh.primitive_ico_sphere_add(radius={s/2}, subdivisions=2)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {s * 0.3})
obj.scale = (1, 0.8, 0.6)
bpy.ops.object.transform_apply(scale=True)

import bmesh
bm = bmesh.new()
bm.from_mesh(obj.data)
random.seed(hash("{name}"))
for v in bm.verts:
    v.co.x += random.uniform(-{s*0.08}, {s*0.08})
    v.co.y += random.uniform(-{s*0.08}, {s*0.08})
    v.co.z += random.uniform(-{s*0.05}, {s*0.05})
bm.to_mesh(obj.data)
bm.free()
_set_vertex_color_all(obj, "{c}")
"""


PROPS = {
    "crate": {
        "description": "Wooden crate with beveled edges. Size: x=side length",
        "builder": _build_crate,
        "default_colors": {"body": "#8B6914"},
        "category": "prop",
    },
    "barrel": {
        "description": "Barrel with slight bulge. Size: x=diameter, y=height",
        "builder": _build_barrel,
        "default_colors": {"body": "#8B6914", "bands": "#444444"},
        "category": "prop",
    },
    "table": {
        "description": "Simple table. Size: x=width, y=height, z=depth. Colors: top, legs",
        "builder": _build_table,
        "default_colors": {"top": "#A0784C", "legs": "#6B4226"},
        "category": "prop",
    },
    "chair": {
        "description": "Simple chair with back. Size: x=width, y=seat height, z=depth. Colors: seat, legs",
        "builder": _build_chair,
        "default_colors": {"seat": "#A0784C", "legs": "#6B4226"},
        "category": "prop",
    },
    "tree_pine": {
        "description": "Pine tree (cone on cylinder). Size: y=total height. Colors: trunk, crown",
        "builder": _build_tree_pine,
        "default_colors": {"trunk": "#6B4226", "crown": "#2D6B2D"},
        "category": "prop",
    },
    "tree_round": {
        "description": "Round tree (sphere on cylinder). Size: y=total height. Colors: trunk, crown",
        "builder": _build_tree_round,
        "default_colors": {"trunk": "#6B4226", "crown": "#2D8B2D"},
        "category": "prop",
    },
    "rock": {
        "description": "Irregular rock (displaced icosphere). Size: x=approximate diameter",
        "builder": _build_rock,
        "default_colors": {"body": "#777777"},
        "category": "prop",
    },
}
