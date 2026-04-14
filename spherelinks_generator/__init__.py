bl_info = {
    "name": "SphereLinks 3D Generator",
    "author": "SphereLinks",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SphereLinks",
    "description": "Generate 3D meshes from reference images via the SphereLinks public API.",
    "category": "Import-Export",
}

import bpy

from . import preferences, properties, operators, panel


_classes = (
    preferences.SphereLinksPreferences,
    properties.SphereLinksJobProperties,
    operators.SPHERELINKS_OT_generate_mesh,
    operators.SPHERELINKS_OT_generate_texture,
    operators.SPHERELINKS_OT_cancel_job,
    panel.SPHERELINKS_PT_main_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.spherelinks = bpy.props.PointerProperty(type=properties.SphereLinksJobProperties)


def unregister():
    del bpy.types.Scene.spherelinks
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
