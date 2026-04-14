import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty


class SphereLinksPreferences(AddonPreferences):
    bl_idname = __package__

    api_key: StringProperty(
        name="API Key",
        description="Your SphereLinks API key (sk_live_...). Create one at spherelinks.io under account settings.",
        default="",
        subtype="PASSWORD",
    )

    base_url: StringProperty(
        name="API Base URL",
        description="SphereLinks public API base URL.",
        default="https://api.spherelinks.io/v1",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key")
        layout.prop(self, "base_url")
        layout.label(text="Get an API key at spherelinks.io → Account → API Keys.", icon="INFO")


def get_prefs(context) -> SphereLinksPreferences:
    return context.preferences.addons[__package__].preferences
