"""Modal operators for the two public API flows.

Shared flow (via _JobOperatorMixin):
    SUBMITTING  → threaded POST to the API                 (UI stays responsive)
    POLLING     → GET /status/{jobId} every POLL_INTERVAL  seconds
    DOWNLOADING → threaded GET presigned GLB URL → temp file
    IMPORTING   → bpy.ops.import_scene.gltf on main thread
"""
import os
import tempfile
import threading

import bpy

from . import api_client
from .preferences import get_prefs


POLL_INTERVAL = 3.0          # seconds between status polls
MAX_POLL_SECONDS = 15 * 60   # hard cap — 15 minutes


def _tag_redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ── Mixin: shared polling / download / import machinery ──────────────────────

class _JobOperatorMixin:
    """Abstract lifecycle that concrete operators specialize at SUBMITTING.

    Subclasses must override `_begin_submission(context)` to kick off the
    initial threaded POST (populating `self._thread` and, on success,
    `self._thread_result` containing `{"jobId": ..., ...}`).
    """

    _timer = None
    _thread: threading.Thread | None = None
    _thread_result = None
    _thread_error: str | None = None
    _phase = "SUBMITTING"
    _elapsed = 0.0
    _poll_countdown = 0.0
    _glb_path: str | None = None

    # Subclass hook — must be overridden.
    def _begin_submission(self, context):
        raise NotImplementedError

    # ── threaded helpers ──────────────────────────────────────────────────

    def _run_download(self, url, dest):
        try:
            api_client.download_glb(url, dest)
            self._thread_result = dest
        except Exception as exc:
            self._thread_error = str(exc)

    def _start_thread(self, target, args):
        self._thread_result = None
        self._thread_error = None
        self._thread = threading.Thread(target=target, args=args, daemon=True)
        self._thread.start()

    # ── operator lifecycle ────────────────────────────────────────────────

    def _start_modal(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        _tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        st = context.scene.spherelinks

        if event.type == "ESC":
            self.report({"WARNING"}, "Cancelled — the job may still run on the server.")
            return self._finish(context, "CANCELLED")

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        self._elapsed += 0.5
        if self._elapsed > MAX_POLL_SECONDS:
            st.job_error = "Timed out waiting for job to complete."
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        try:
            if self._phase == "SUBMITTING":
                return self._tick_submitting(context)
            if self._phase == "POLLING":
                return self._tick_polling(context)
            if self._phase == "DOWNLOADING":
                return self._tick_downloading(context)
        except Exception as exc:
            st.job_error = f"Unexpected error: {exc}"
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        return {"PASS_THROUGH"}

    def _tick_submitting(self, context):
        st = context.scene.spherelinks
        if self._thread and self._thread.is_alive():
            return {"PASS_THROUGH"}

        if self._thread_error:
            st.job_error = self._thread_error
            self.report({"ERROR"}, f"Submission failed: {self._thread_error}")
            return self._finish(context, "CANCELLED")

        result = self._thread_result or {}
        job_id = result.get("jobId")
        if not job_id:
            st.job_error = "Server did not return a jobId."
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        st.job_id = job_id
        st.job_status = result.get("status", "PROCESSING")
        st.job_stage = "Running on GPU…"
        st.job_progress = 5
        self._phase = "POLLING"
        self._poll_countdown = 0.0
        _tag_redraw()
        return {"PASS_THROUGH"}

    def _tick_polling(self, context):
        st = context.scene.spherelinks
        self._poll_countdown -= 0.5
        if self._poll_countdown > 0:
            return {"PASS_THROUGH"}
        self._poll_countdown = POLL_INTERVAL

        prefs = get_prefs(context)
        try:
            resp = api_client.get_status(prefs.base_url, prefs.api_key, st.job_id)
        except api_client.SphereLinksApiError as exc:
            # Transient — keep polling.
            st.job_stage = f"Status check failed: {exc}"
            _tag_redraw()
            return {"PASS_THROUGH"}

        st.job_status = resp.get("status", st.job_status or "PROCESSING")
        st.job_stage = resp.get("description") or resp.get("stageMessage") or "Working…"
        st.job_progress = int(resp.get("progress", st.job_progress))
        _tag_redraw()

        if st.job_status == "FAILED":
            st.job_error = resp.get("errorMsg", "Job failed.")
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        if st.job_status == "COMPLETED":
            download_url = resp.get("downloadUrl")
            if not download_url:
                st.job_error = "Job completed but no download URL was returned."
                self.report({"ERROR"}, st.job_error)
                return self._finish(context, "CANCELLED")

            st.job_stage = "Downloading GLB…"
            st.job_progress = 95
            self._glb_path = os.path.join(
                tempfile.gettempdir(), f"spherelinks_{st.job_id[:8]}.glb"
            )
            self._phase = "DOWNLOADING"
            self._start_thread(self._run_download, (download_url, self._glb_path))

        return {"PASS_THROUGH"}

    def _tick_downloading(self, context):
        st = context.scene.spherelinks
        if self._thread and self._thread.is_alive():
            return {"PASS_THROUGH"}

        if self._thread_error:
            st.job_error = self._thread_error
            self.report({"ERROR"}, f"Download failed: {self._thread_error}")
            return self._finish(context, "CANCELLED")

        glb_path = self._thread_result
        if not glb_path or not os.path.isfile(glb_path):
            st.job_error = "GLB file missing after download."
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        st.job_stage = "Importing into scene…"
        st.job_progress = 99
        _tag_redraw()

        try:
            bpy.ops.import_scene.gltf(filepath=glb_path)
        except Exception as exc:
            st.job_error = f"GLTF import failed: {exc}"
            self.report({"ERROR"}, st.job_error)
            return self._finish(context, "CANCELLED")

        st.job_stage = "Done."
        st.job_progress = 100
        self.report({"INFO"}, f"Imported result for job {st.job_id[:8]}.")
        return self._finish(context, "FINISHED")

    def _finish(self, context, result: str):
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        context.scene.spherelinks.is_running = False
        _tag_redraw()
        return {result}


# ── Concrete operators ───────────────────────────────────────────────────────

class SPHERELINKS_OT_generate_mesh(_JobOperatorMixin, bpy.types.Operator):
    bl_idname = "spherelinks.generate_mesh"
    bl_label = "Generate 3D Mesh"
    bl_description = "Submit the reference image to SphereLinks and import the resulting GLB."
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        st = context.scene.spherelinks
        return bool(st.image_path) and not st.is_running

    def _run_mesh_submit(self, base_url, api_key, image_path, options):
        try:
            self._thread_result = api_client.submit_generation(base_url, api_key, image_path, options)
        except Exception as exc:
            self._thread_error = str(exc)

    def _begin_submission(self, context):
        prefs = get_prefs(context)
        st = context.scene.spherelinks
        image_path = bpy.path.abspath(st.image_path)

        options = {
            "seed":          st.seed,
            "steps":         st.steps,
            "slatSteps":     st.slat_steps,
            "textureSize":   int(st.texture_size),
            "simplifyRatio": st.simplify_ratio,
        }
        self._start_thread(self._run_mesh_submit, (prefs.base_url, prefs.api_key, image_path, options))

    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs.api_key:
            self.report({"ERROR"}, "Set your API key in Preferences → Add-ons → SphereLinks.")
            return {"CANCELLED"}

        st = context.scene.spherelinks
        image_path = bpy.path.abspath(st.image_path)
        if not os.path.isfile(image_path):
            self.report({"ERROR"}, f"Reference image not found: {image_path}")
            return {"CANCELLED"}

        st.is_running = True
        st.job_id = ""
        st.job_status = "SUBMITTING"
        st.job_stage = "Uploading image…"
        st.job_progress = 0
        st.job_error = ""
        self._phase = "SUBMITTING"
        self._elapsed = 0.0
        self._glb_path = None

        self._begin_submission(context)
        return self._start_modal(context)


class SPHERELINKS_OT_generate_texture(_JobOperatorMixin, bpy.types.Operator):
    bl_idname = "spherelinks.generate_texture"
    bl_label = "Generate Texture"
    bl_description = (
        "Bake a texture onto the selected mesh using a reference image. "
        "The active object must be a mesh."
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        st = context.scene.spherelinks
        obj = context.active_object
        return (
            bool(st.texture_image_path)
            and obj is not None
            and obj.type == "MESH"
            and not st.is_running
        )

    def _run_texture_submit(self, base_url, api_key, mesh_path, image_path, options):
        try:
            self._thread_result = api_client.submit_texture(base_url, api_key, mesh_path, image_path, options)
        except Exception as exc:
            self._thread_error = str(exc)

    def _export_selected_to_glb(self, context) -> str:
        """Export the active mesh (and any selected children) to a temp GLB. Returns the path."""
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"spherelinks_source_{os.getpid()}.glb")

        # Isolate the active object as the only selection so the export is predictable.
        original_selection = [o for o in context.selected_objects]
        original_active = context.view_layer.objects.active
        try:
            bpy.ops.object.select_all(action="DESELECT")
            context.active_object.select_set(True)
            context.view_layer.objects.active = context.active_object

            bpy.ops.export_scene.gltf(
                filepath=path,
                export_format="GLB",
                use_selection=True,
                export_apply=True,        # bake modifiers
                export_materials="NONE",  # strip existing materials — we're replacing them
                export_animations=False,
                export_cameras=False,
                export_lights=False,
            )
        finally:
            bpy.ops.object.select_all(action="DESELECT")
            for o in original_selection:
                try:
                    o.select_set(True)
                except ReferenceError:
                    pass
            if original_active is not None:
                context.view_layer.objects.active = original_active
        return path

    def _begin_submission(self, context):
        prefs = get_prefs(context)
        st = context.scene.spherelinks
        image_path = bpy.path.abspath(st.texture_image_path)

        options = {"textureSize": int(st.texture_size)}
        self._start_thread(
            self._run_texture_submit,
            (prefs.base_url, prefs.api_key, self._mesh_path, image_path, options),
        )

    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs.api_key:
            self.report({"ERROR"}, "Set your API key in Preferences → Add-ons → SphereLinks.")
            return {"CANCELLED"}

        st = context.scene.spherelinks
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object before running Generate Texture.")
            return {"CANCELLED"}

        image_path = bpy.path.abspath(st.texture_image_path)
        if not os.path.isfile(image_path):
            self.report({"ERROR"}, f"Reference image not found: {image_path}")
            return {"CANCELLED"}

        # Export the selected mesh to a temp GLB on the main thread
        # (bpy.ops MUST run on the main thread).
        try:
            self._mesh_path = self._export_selected_to_glb(context)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to export mesh: {exc}")
            return {"CANCELLED"}

        mesh_size = os.path.getsize(self._mesh_path)
        if mesh_size > 7 * 1024 * 1024:
            self.report({"ERROR"}, f"Exported mesh is {mesh_size // (1024*1024)} MB — exceeds 7 MB limit. Decimate first.")
            return {"CANCELLED"}

        st.is_running = True
        st.job_id = ""
        st.job_status = "SUBMITTING"
        st.job_stage = f"Uploading mesh ({mesh_size // 1024} KB) + image…"
        st.job_progress = 0
        st.job_error = ""
        self._phase = "SUBMITTING"
        self._elapsed = 0.0
        self._glb_path = None

        self._begin_submission(context)
        return self._start_modal(context)


class SPHERELINKS_OT_cancel_job(bpy.types.Operator):
    bl_idname = "spherelinks.cancel_job"
    bl_label = "Reset Job State"
    bl_description = "Clear the current job state. Does not cancel server-side processing."
    bl_options = {"REGISTER"}

    def execute(self, context):
        st = context.scene.spherelinks
        st.is_running = False
        st.job_id = ""
        st.job_status = ""
        st.job_stage = ""
        st.job_progress = 0
        st.job_error = ""
        _tag_redraw()
        return {"FINISHED"}
