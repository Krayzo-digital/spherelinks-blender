# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-04-14

### Added

- Initial release.
- Mesh generation from a reference image via `POST /generate`.
- Texture baking on arbitrary scene meshes via presigned S3 uploads
  (`POST /upload` → direct PUT to S3 → `POST /texture`).
- Shared job-status panel with live polling and progress reporting.
- Addon preferences for API key and custom base URL.
