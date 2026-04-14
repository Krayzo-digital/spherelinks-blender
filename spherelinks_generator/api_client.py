"""Thin client over the SphereLinks public API (api.spherelinks.com).

Uses only Python stdlib (urllib) so no pip dependencies are required inside Blender.
"""
import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request


class SphereLinksApiError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def _request(method: str, url: str, api_key: str, body: dict | None = None, timeout: int = 30) -> dict:
    data = None
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
            msg = parsed.get("error") or parsed.get("message") or raw
        except json.JSONDecodeError:
            msg = raw or exc.reason
        raise SphereLinksApiError(f"HTTP {exc.code}: {msg}", status=exc.code, body=raw) from exc
    except urllib.error.URLError as exc:
        raise SphereLinksApiError(f"Network error: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise SphereLinksApiError(f"Invalid JSON response: {raw[:200]}")


def submit_generation(base_url: str, api_key: str, image_path: str, options: dict) -> dict:
    """POST /generate with a base64-encoded local image. Returns {jobId, status, message}."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    content_type, _ = mimetypes.guess_type(image_path)
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        content_type = "image/jpeg"

    payload = {
        "imageBase64": base64.b64encode(image_bytes).decode(),
        "filename":    os.path.basename(image_path),
        "contentType": content_type,
        "options":     options,
    }
    return _request("POST", f"{base_url.rstrip('/')}/generate", api_key, payload, timeout=120)


def _get_upload_url(base_url: str, api_key: str, kind: str, filename: str, content_type: str) -> dict:
    """POST /upload → {uploadUrl, s3Key, contentType, expiresIn}."""
    payload = {"kind": kind, "filename": filename, "contentType": content_type}
    return _request("POST", f"{base_url.rstrip('/')}/upload", api_key, payload, timeout=30)


def _put_to_presigned_url(upload_url: str, file_path: str, content_type: str, timeout: int = 300) -> None:
    """PUT raw bytes to a presigned S3 URL. Content-Type must match what was baked into the URL."""
    with open(file_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(upload_url, data=data, method="PUT", headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status not in (200, 204):
                raise SphereLinksApiError(f"S3 PUT returned {resp.status}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        raise SphereLinksApiError(f"S3 PUT failed ({exc.code}): {raw[:200]}") from exc
    except urllib.error.URLError as exc:
        raise SphereLinksApiError(f"S3 PUT network error: {exc.reason}") from exc


def submit_texture(base_url: str, api_key: str, mesh_path: str, image_path: str, options: dict) -> dict:
    """Full three-step texture submission: two presigned uploads + POST /texture."""
    image_ct, _ = mimetypes.guess_type(image_path)
    if image_ct not in ("image/jpeg", "image/png", "image/webp"):
        image_ct = "image/jpeg"

    # 1. Request presigned URLs for mesh + image.
    mesh_slot  = _get_upload_url(base_url, api_key, "mesh",  os.path.basename(mesh_path),  "model/gltf-binary")
    image_slot = _get_upload_url(base_url, api_key, "image", os.path.basename(image_path), image_ct)

    # 2. Upload the raw bytes directly to S3.
    _put_to_presigned_url(mesh_slot["uploadUrl"],  mesh_path,  mesh_slot["contentType"])
    _put_to_presigned_url(image_slot["uploadUrl"], image_path, image_slot["contentType"])

    # 3. Kick off the texture job with only the S3 keys (tiny JSON payload).
    payload = {
        "meshS3Key":  mesh_slot["s3Key"],
        "imageS3Key": image_slot["s3Key"],
        "options":    options,
    }
    return _request("POST", f"{base_url.rstrip('/')}/texture", api_key, payload, timeout=30)


def get_status(base_url: str, api_key: str, job_id: str) -> dict:
    """GET /status/{jobId}. Returns the job status dict."""
    return _request("GET", f"{base_url.rstrip('/')}/status/{job_id}", api_key, timeout=15)


def download_glb(url: str, dest_path: str, timeout: int = 300) -> None:
    """Stream a presigned GLB URL to disk. No API key — presigned S3 URL is self-auth."""
    req = urllib.request.Request(url, headers={"User-Agent": "SphereLinks-Blender/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.URLError as exc:
        raise SphereLinksApiError(f"Failed to download GLB: {exc.reason}") from exc
