"""Primitive shape presets."""


def _build_cube(name: str, size: dict, colors: dict) -> str:
    w, h, d = size.get("x", 1), size.get("y", 1), size.get("z", 1)
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_cube_add(size=1)
obj = bpy.context.active_object
obj.name = "{name}"
obj.scale = ({w/2}, {d/2}, {h/2})
obj.location = (0, 0, {h/2})
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(obj, "{c}")
"""


def _build_sphere(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 1) / 2
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_uv_sphere_add(radius={r}, segments=16, ring_count=12)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {r})
_set_vertex_color_all(obj, "{c}")
"""


def _build_cylinder(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 1) / 2
    h = size.get("y", 2)
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_cylinder_add(radius={r}, depth={h}, vertices=16)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {h/2})
_set_vertex_color_all(obj, "{c}")
"""


def _build_capsule(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 0.5) / 2
    h = size.get("y", 2)
    body_h = max(0.01, h - 2 * r)
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_cylinder_add(radius={r}, depth={body_h}, vertices=16)
body = bpy.context.active_object
body.name = "{name}_body"
body.location = (0, 0, {h/2})

bpy.ops.mesh.primitive_uv_sphere_add(radius={r}, segments=12, ring_count=8)
top = bpy.context.active_object
top.name = "{name}_top"
top.location = (0, 0, {h/2 + body_h/2})

bpy.ops.mesh.primitive_uv_sphere_add(radius={r}, segments=12, ring_count=8)
bot = bpy.context.active_object
bot.name = "{name}_bot"
bot.location = (0, 0, {h/2 - body_h/2})

bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "{name}"
_set_vertex_color_all(obj, "{c}")
"""


def _build_cone(name: str, size: dict, colors: dict) -> str:
    r = size.get("x", 1) / 2
    h = size.get("y", 2)
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_cone_add(radius1={r}, radius2=0, depth={h}, vertices=16)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {h/2})
_set_vertex_color_all(obj, "{c}")
"""


def _build_plane(name: str, size: dict, colors: dict) -> str:
    w = size.get("x", 10)
    d = size.get("z", 10)
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_plane_add(size=1)
obj = bpy.context.active_object
obj.name = "{name}"
obj.scale = ({w/2}, {d/2}, 1)
bpy.ops.object.transform_apply(scale=True)
_set_vertex_color_all(obj, "{c}")
"""


def _build_torus(name: str, size: dict, colors: dict) -> str:
    major_r = size.get("x", 2) / 2
    minor_r = size.get("y", 0.5) / 2
    c = colors.get("body", "#808080")
    return f"""
bpy.ops.mesh.primitive_torus_add(major_radius={major_r}, minor_radius={minor_r},
    major_segments=24, minor_segments=12)
obj = bpy.context.active_object
obj.name = "{name}"
obj.location = (0, 0, {major_r})
_set_vertex_color_all(obj, "{c}")
"""


PRIMITIVES = {
    "cube": {
        "description": "Simple box. Size: x=width, y=height, z=depth",
        "builder": _build_cube,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "sphere": {
        "description": "UV sphere. Size: x=diameter",
        "builder": _build_sphere,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "cylinder": {
        "description": "Cylinder. Size: x=diameter, y=height",
        "builder": _build_cylinder,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "capsule": {
        "description": "Capsule (cylinder + hemisphere caps). Size: x=diameter, y=total height",
        "builder": _build_capsule,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "cone": {
        "description": "Cone. Size: x=base diameter, y=height",
        "builder": _build_cone,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "plane": {
        "description": "Flat plane. Size: x=width, z=depth",
        "builder": _build_plane,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
    "torus": {
        "description": "Torus/donut. Size: x=outer diameter, y=tube diameter",
        "builder": _build_torus,
        "default_colors": {"body": "#808080"},
        "category": "primitive",
    },
}
