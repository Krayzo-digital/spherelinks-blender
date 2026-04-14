import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, EnumProperty


class SphereLinksJobProperties(PropertyGroup):
    image_path: StringProperty(
        name="Reference Image",
        description="Path to the reference image (JPEG, PNG, or WEBP; max 10 MB).",
        default="",
        subtype="FILE_PATH",
    )

    seed: IntProperty(
        name="Seed",
        description="Random seed for reproducible generation.",
        default=42,
        min=0,
        max=2**31 - 1,
    )

    steps: IntProperty(
        name="Steps",
        description="Inference steps for geometry generation.",
        default=50,
        min=10,
        max=100,
    )

    slat_steps: IntProperty(
        name="SLAT Steps",
        description="Steps for structured latent refinement.",
        default=50,
        min=10,
        max=100,
    )

    texture_size: EnumProperty(
        name="Texture Size",
        description="Resolution of the baked texture.",
        items=[
            ("512",  "512 px",  "Low detail"),
            ("1024", "1024 px", "Default"),
            ("2048", "2048 px", "High detail"),
        ],
        default="1024",
    )

    simplify_ratio: FloatProperty(
        name="Simplify Ratio",
        description="Face reduction target (1.0 = full detail, 0.5 = half faces).",
        default=0.95,
        min=0.5,
        max=1.0,
        precision=2,
    )

    # Texture-op inputs — reference image whose style/color gets baked onto the selected mesh.
    texture_image_path: StringProperty(
        name="Reference Image",
        description="Reference image whose style/color will be baked onto the selected mesh.",
        default="",
        subtype="FILE_PATH",
    )

    # Runtime status (populated by the operator)
    job_id: StringProperty(default="")
    job_status: StringProperty(default="")
    job_stage: StringProperty(default="")
    job_progress: IntProperty(default=0, min=0, max=100)
    job_error: StringProperty(default="")
    is_running: bpy.props.BoolProperty(default=False)
