"""Generate bpy code snippets for vertex color assignment."""


def hex_to_rgb_code() -> str:
    return """
def _hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
"""


def set_vertex_color_code() -> str:
    return """
def _set_vertex_color_all(obj, color_hex):
    mesh = obj.data
    if not mesh.color_attributes:
        mesh.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')
    color_attr = mesh.color_attributes.active_color
    r, g, b = _hex_to_rgb(color_hex)
    for i in range(len(color_attr.data)):
        color_attr.data[i].color = (r, g, b, 1.0)

def _set_vertex_color_faces(obj, face_indices, color_hex):
    mesh = obj.data
    if not mesh.color_attributes:
        mesh.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')
    color_attr = mesh.color_attributes.active_color
    r, g, b = _hex_to_rgb(color_hex)
    for poly_idx in face_indices:
        if poly_idx < len(mesh.polygons):
            poly = mesh.polygons[poly_idx]
            for loop_idx in poly.loop_indices:
                color_attr.data[loop_idx].color = (r, g, b, 1.0)
"""


def color_utilities_code() -> str:
    return hex_to_rgb_code() + set_vertex_color_code()
