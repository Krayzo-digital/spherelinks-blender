# SphereLinks 3D Generator — Blender Addon

Generate 3D meshes and bake textures directly inside Blender using the
[SphereLinks](https://spherelinks.io) public API.

Two flows in one sidebar panel:

- **Generate Mesh from Image** — feed a reference photo, get back a textured GLB.
- **Texture Selected Mesh** — bake a new PBR texture onto any mesh in your scene
  using a reference image.

Both flows are asynchronous: the addon submits the job, polls its status, then
downloads and imports the resulting GLB as soon as it's ready.

## Install

### Blender 4.2 or newer (recommended — new Extensions system)

1. Download the latest `spherelinks_generator.zip` from the
   [Releases page](https://github.com/spherelinks/spherelinks-blender/releases).
2. In Blender: **Edit → Preferences → Add-ons → ⌄ (top-right) → Install from Disk…**
3. Pick the zip. Enable the checkbox next to "SphereLinks 3D Generator".
4. Expand the entry, paste your API key, leave the Base URL at
   `https://api.spherelinks.io/v1`.

### Blender 4.0 and 4.1 (legacy add-on)

Same as above — the addon ships with both `bl_info` and `blender_manifest.toml`,
so older Blender versions that still use the legacy add-on loader can install it.

## Getting an API key

1. Sign up at [spherelinks.io](https://spherelinks.io).
2. Go to **Account → API Keys → Create New Key**.
3. Copy the `sk_live_…` key and paste it into the addon preferences.

API keys are rate-limited and tied to your account's credit balance. Each
completed generation deducts one credit; failed jobs are refunded automatically.

## Usage

Open the **N-panel** in the 3D Viewport (press **N**) and click the
**SphereLinks** tab.

### Mesh generation

1. Pick a reference image (JPEG, PNG, or WEBP — the plugin handles upload).
2. Tweak the sliders if you like (seed, steps, texture size, simplify ratio).
3. Click **Generate 3D Mesh**. Progress updates live.
4. When complete, the GLB is automatically imported.

### Texture baking

1. Select the mesh you want to texture in the viewport.
2. In the **Texture Selected Mesh** box, pick a reference image.
3. Click **Generate Texture**. The addon exports your mesh to a temporary GLB,
   uploads it and the reference image to S3 via presigned URLs, kicks off the
   texture-bake job, then imports the result when done.

The texturing pipeline on the server auto-decimates meshes denser than ~30 000
faces, so for best results decimate your mesh to that density in Blender before
submitting.

## Requirements

- Blender 4.0+ (legacy) or 4.2+ (Extensions system).
- An active SphereLinks account with credits.
- Internet access to `api.spherelinks.io`.

No pip dependencies — the addon uses only Blender's bundled Python stdlib.

## Development

```sh
# Clone
git clone https://github.com/spherelinks/spherelinks-blender
cd spherelinks-blender

# Build the installable zip
make build

# Install into your local Blender (macOS paths; adjust for Linux / Windows)
make install-local
```

A Blender restart is required after overwriting the installed addon — Blender's
Python caches imported modules for the lifetime of the process.

## License

GPL-3.0-or-later. See [LICENSE](./LICENSE).

The SphereLinks service this addon talks to is proprietary, but the addon itself
is free and open source. Forks, patches, and derivative work are welcome —
please file issues and PRs on this repository.
