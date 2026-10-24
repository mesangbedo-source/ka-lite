# KA Lite 0.17.5 Working Maintenance Fork

**Fork:** <https://github.com/mesangbedo-source/ka-lite>
**Maintenance branch:** `maintenance/kalite-0.17.5-working`
**Fork revision:** `working.1` (not an official KA Lite release)
**Upstream:** <https://github.com/learningequality/ka-lite>

This is a community maintenance fork created by Dr. Moses Olabhele Esangbedo.
It preserves KA Lite 0.17.5's original interface and educational functionality,
repairs the frontend static-asset packaging, keeps the existing compatibility
patches, and adds an optional video-recovery tool and offline deployment
documentation.

**This fork is not maintained, sponsored, or endorsed by Learning Equality.**
Learning Equality's official successor project is Kolibri:
<https://learningequality.org/kolibri/>.

## What KA Lite is

KA Lite is a lightweight Django web application for serving Khan Academy
videos and exercises from a local server without Internet connectivity. It was
developed by Learning Equality and reached its final upstream release,
0.17.5, on 2018-07-11. The upstream project is effectively dormant.

## Why this fork exists

A legacy KA Lite installation was restored on a local Linux workstation. The
frontend was broken because the Docker image had been built from the GitHub
"Source code" archive, which contains frontend sources but not the compiled
Browserify bundles. The official PyPI artifacts include the compiled bundles.

This fork:

- keeps the original KA Lite 0.17.5 interface and branding;
- makes the static-asset requirement explicit and reproducible;
- preserves the existing compatibility fixes for read-only content roots,
  content-database discovery, and headless/ifconfig-less startup;
- provides a Docker-based installation that other users can reproduce;
- adds an optional, documented video-recovery utility;
- does not include videos, torrents, content databases, credentials, or
  third-party content.

## Branch provenance

The maintenance branch is based on upstream tag `v0.17.5` (`4cd3306`) plus the
local compatibility commits:

```text
1c6ce7b Fix content database discovery: glob() was given a directory
69e9552 Do not fail on import when CONTENT_ROOT is read-only
9cae9ba Do not abort startup when network interfaces cannot be enumerated
0006b62 Document read-only content roots and ifconfig-less startup
```

The fork retains the upstream Git history and attribution. These compatibility
commits are maintenance work, not official Learning Equality changes.

## What was repaired

### 1. Static frontend assets

The upstream GitHub source archive does not contain compiled
`kalite/**/static/**/bundles/bundle_*.js` files. The official
`ka-lite-static` 0.17.5 wheel does. The deployment downloads that wheel with a
pinned SHA-256 and overlays only its static trees, preserving the source
patches.

A missing `bundle_common.js` makes the page load without Bootstrap/LESS CSS,
jQuery, or `sessionModel`, producing unstyled HTML. The repair restores the
original layout, logo sizing, navigation, login modal, and administrative
pages.

### 2. Compatibility patches

The branch is based on the local `v0.17.5` compatibility work at commit
`0006b62`, which includes:

- read-only `CONTENT_ROOT` handling;
- content-database discovery fix;
- `ifconfig`-less startup handling;
- documentation and tests for those changes.

These are documented as maintenance fixes, not official Learning Equality
changes.

### 3. Existing data-volume repair

The container entrypoint collects static files when the bundle is missing from
`STATIC_ROOT`, so an existing `/data` volume is repaired on restart instead of
requiring a manual `collectstatic` command.

### 4. Python 2.7 SQLite helper fix

The entrypoint helpers open existing SQLite files without the Python 3-only
`uri=True` argument, so a healthy content database is recognized and the
seed/setup step is not repeated unnecessarily on every restart.

## Installation

See [`deploy/README.md`](deploy/README.md) for the complete procedure.

Short version:

```bash
git clone https://github.com/mesangbedo-source/ka-lite.git
cd ka-lite
git remote add upstream https://github.com/learningequality/ka-lite.git
git fetch upstream
git switch maintenance/kalite-0.17.5-working
cd deploy
./scripts/bootstrap.sh
# edit kalite.env and set KA_LITE_ADMIN_PASSWORD
docker compose build
docker compose up -d
```

`origin` is the maintenance fork; `upstream` is Learning Equality's original
repository. Do not push maintenance changes to `upstream`.

The service binds to `127.0.0.1:8008` only. Change the default admin password
before exposing it to any user.

## Static frontend asset requirement

Do **not** deploy directly from the GitHub "Source code" archive. Use the
PyPI `ka-lite`/`ka-lite-static` artifacts, or run:

```bash
cd deploy
./scripts/fetch-static-wheel.sh
```

The script downloads the official
`ka_lite_static-0.17.5-py2-none-any.whl` and verifies:

```text
sha256 0d6ffe5518a542107fd08ffe0669f77d3f622f4e7fd465e9a8b60e0f8aae6b04
```

The wheel is ignored by Git and is not committed. A build requires one-time
network access to PyPI and the Python package index; the running application
does not require Internet access. Diagnosis details are in
[`docs/troubleshooting/frontend-assets.md`](docs/troubleshooting/frontend-assets.md).

## Video storage

The deployment mounts `deploy/content` at `/content` in the container. The
optional `tools/video-index/` helper extracts video IDs from a compatible
content database, and `tools/video-recovery/` can populate the directory using
public, permitted YouTube sources. It preserves YouTube IDs as filenames, prefers
H.264/AAC MP4, verifies media with `ffprobe` when available, writes a manifest
with SHA-256 checksums, and can import SRT subtitles as VTT.

Video files are not included in this repository. The user is responsible for
content licensing and platform terms. See
[`docs/video-library/README.md`](docs/video-library/README.md).

After adding videos, set `KA_LITE_REANNOTATE=1` in `deploy/kalite.env` and
restart once, then set it back to `0`.

## Offline playback

Once built and populated, the application serves its CSS, JavaScript, fonts,
images, videos, and exercises locally. The optional Google Maps script on the
facility form, the upstream Google Analytics snippet, and the language-pack
catalogue are external and are not required for the restored frontend or local
playback. Language-pack installation and the facility map require Internet.

The original English language-pack warning is upstream behavior; no 0.17
English language pack is bundled. Do not hide it with CSS or JavaScript.

## Supported and tested environment

Validated locally on:

- Linux Mint 22.3 (Zena), kernel `7.3.0-ryzen5950x`, x86_64;
- Docker 29.1.3 and Docker Compose 2.40.3;
- KA Lite 0.17.5, Python 2.7.18, Django 1.5.12, CherryPy 3.3.0;
- Chromium 156.0.8078.47 at 1280x900 for browser checks;
- Python 3.12 and `yt-dlp` 2026.08.30 for the optional recovery tool.

This fork has **not** been validated across all Linux distributions, kernels,
KA Lite installations, browsers, Python versions, or deployment
configurations. Do not claim universal compatibility.

See [`docs/validation/README.md`](docs/validation/README.md) for the test
evidence and known limitations.

## What is not included

- No Khan Academy videos or thumbnails.
- No torrent files or seed data.
- No recovered content database.
- No admin credentials, cookies, user databases, or private configuration.
- No compiled `ka-lite-static` wheel (fetched by script, checksum-pinned).
- No claim that any video may be redistributed.

## Roadmap

1. **Current branch:** working KA Lite 0.17.5 deployment with restored frontend
   and compatibility fixes.
2. **Video recovery:** use `tools/video-recovery/` to build a verified,
   checksummed local library at a chosen resolution.
3. **Library validation:** test representative lessons in KA Lite, record
   codecs/quality/aspect ratio, and document unavailable videos.
4. **Authorized torrent publication:** only after verifying content licenses
   and redistribution permissions, and only with owner approval.
5. **Upstream contribution:** separate documentation/tooling proposals, after
   checking current policy and obtaining any required issue assignment. No
   upstream PR is open now.

## Upstream attribution and license

KA Lite is copyright the Foundation for Learning Equality, Inc. and
contributors. The original `LICENSE` and copyright notices are preserved. The
software is MIT licensed. Khan Academy content, Perseus exercises, and other
third-party educational assets have separate terms; the MIT license does not
grant rights to them.

This fork is not an official Learning Equality release and must not be
presented as one. Fork-specific version labels use the `working.N` suffix to
avoid impersonating upstream releases.

## AI-assisted development disclosure

This maintenance fork was developed with the assistance of AI coding agents
under the human contributor's direction. Earlier installation and compatibility
work was assisted by Pi; the frontend investigation, deployment packaging,
browser validation, documentation, and optional recovery utility were produced
with Crush. The human contributor reviewed the results and is responsible for
the publication decision.

AI involvement is disclosed explicitly in accordance with Learning Equality's
contribution guidance, including the DEEP expectations: disclose, engage
critically, edit, and share the process. The validation results are limited to
the environment documented above; broader compatibility has not been
established unless separately demonstrated.
