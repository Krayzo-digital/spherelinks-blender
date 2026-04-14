import bpy


class SPHERELINKS_PT_main_panel(bpy.types.Panel):
    bl_label = "SphereLinks"
    bl_idname = "SPHERELINKS_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SphereLinks"

    def draw(self, context):
        layout = self.layout
        st = context.scene.spherelinks

        # ── Mesh generation ──────────────────────────────────────────────
        mesh_box = layout.box()
        mesh_box.label(text="Generate Mesh from Image", icon="MESH_DATA")
        mesh_box.prop(st, "image_path", text="")

        col = mesh_box.column(align=True)
        col.prop(st, "seed")
        col.prop(st, "steps")
        col.prop(st, "slat_steps")
        col.prop(st, "texture_size")
        col.prop(st, "simplify_ratio", slider=True)

        row = mesh_box.row(align=True)
        row.scale_y = 1.3
        row.enabled = not st.is_running
        row.operator("spherelinks.generate_mesh", icon="PLAY")

        # ── Texture existing mesh ────────────────────────────────────────
        tex_box = layout.box()
        tex_box.label(text="Texture Selected Mesh", icon="TEXTURE")

        obj = context.active_object
        if obj is not None and obj.type == "MESH":
            tex_box.label(text=f"Source: {obj.name}", icon="OBJECT_DATA")
        else:
            warn = tex_box.row()
            warn.alert = True
            warn.label(text="Select a mesh object first.", icon="ERROR")

        tex_box.prop(st, "texture_image_path", text="")
        tex_box.prop(st, "texture_size")

        row = tex_box.row(align=True)
        row.scale_y = 1.3
        row.enabled = not st.is_running
        row.operator("spherelinks.generate_texture", icon="BRUSH_DATA")

        # ── Shared job status panel ──────────────────────────────────────
        if st.is_running or st.job_id or st.job_error:
            status = layout.box()
            status.label(text="Job Status", icon="INFO")
            if st.job_id:
                status.label(text=f"ID: {st.job_id[:8]}…")
            if st.job_status:
                status.label(text=f"Status: {st.job_status}")
            if st.job_stage:
                status.label(text=st.job_stage)
            if st.is_running:
                if hasattr(status, "progress"):
                    status.progress(factor=st.job_progress / 100.0, text=f"{st.job_progress}%")
                else:
                    status.label(text=f"Progress: {st.job_progress}%")
            if st.job_error:
                err = status.column()
                err.alert = True
                err.label(text=st.job_error, icon="ERROR")
            if not st.is_running:
                status.operator("spherelinks.cancel_job", text="Clear", icon="X")
