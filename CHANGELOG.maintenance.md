# Maintenance Changelog

## kalite-0.17.5-working.1 — 2026-10-24

Fork-specific version. This is not an official KA Lite release.

### Added

- Reproducible Docker deployment under `deploy/` with localhost-only binding,
  read-only root filesystem, non-root UID, health check, and pinned base image.
- `deploy/scripts/fetch-static-wheel.sh` for the official
  `ka-lite-static` 0.17.5 wheel with SHA-256 verification.
- `deploy/scripts/bootstrap.sh`, environment template, asset checker, and
  offline/installation documentation.
- Optional `tools/video-recovery/` yt-dlp helper with manifest/checksum output,
  360p/480p/720p/1080p quality profiles, ffprobe resolution/codec validation,
  SRT/VTT import, and 20 passing tests.
- `tools/video-index/` read-only content-database index builder.
- Fork maintenance README, troubleshooting guide, video-library roadmap, and
  validation evidence.

### Fixed

- Restored the original frontend by installing the official compiled static
  bundles instead of relying on the incomplete GitHub source archive.
- Added static collection for existing data volumes when `bundle_common.js` is
  missing.
- Corrected a Python 2.7 SQLite helper incompatibility that caused unnecessary
  re-seeding and setup on every container start.
- Made the deployment build independent of the BuildKit frontend pull by
  removing the unpinned syntax directive.

### Preserved

- Original KA Lite 0.17.5 interface, branding, templates, navigation, and
  coloring.
- Existing compatibility fixes for read-only content roots, content database
  discovery, and ifconfig-less startup.
- Original `LICENSE` and copyright notices.
- Content database compatibility and local video playback.

### Known limitations

- No videos, torrents, content databases, or credentials are included.
- Assessment image coverage depends on the local content source.
- The facility map, Google Analytics, and language-pack catalogue are external.
- Only the documented Linux/Docker environment was tested.
