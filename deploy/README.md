# Deploying the KA Lite 0.17.5 Maintenance Fork

This directory contains a reproducible, localhost-only Docker deployment of the
maintenance branch. It is not an official Learning Equality installer.

## Prerequisites

- Linux with Docker and Docker Compose.
- Python 3 on the host for the one-time static-wheel download.
- Roughly 1 GB free for the application image and static wheel, plus space for
  videos if you recover them.
- Network access for the first build (PyPI, Debian archive). The running
  application does not need Internet access.

## First installation

```bash
git clone https://github.com/mesangbedo-source/ka-lite.git
cd ka-lite
git switch maintenance/kalite-0.17.5-working
cd deploy
./scripts/bootstrap.sh
```

`bootstrap.sh` creates the runtime directories, copies
`kalite.env.example` to `kalite.env` with mode 0600, and downloads the official
compiled frontend wheel.

Edit `kalite.env` before the first start:

```bash
chmod 600 kalite.env
$EDITOR kalite.env
```

At minimum, change `KA_LITE_ADMIN_PASSWORD`. Do not commit `kalite.env`.

Build and start:

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open <http://127.0.0.1:8008/>. The first start initializes the application
database; it can take a minute. The health check should become `healthy`.

## Static frontend assets

The compiled bundles are not in Git. The build requires:

```text
deploy/vendor/ka_lite_static-0.17.5-py2-none-any.whl
sha256 0d6ffe5518a542107fd08ffe0669f77d3f622f4e7fd465e9a8b60e0f8aae6b04
```

`scripts/fetch-static-wheel.sh` downloads it from PyPI and verifies the hash;
see [`STATIC-WHEEL.md`](STATIC-WHEEL.md). If the download fails, fetch the same
official wheel from
<https://pypi.org/project/ka-lite-static/0.17.5/> and place it at that path.

Do not use the GitHub "Source code" archive as a deployment source; it omits
these compiled bundles. See
[`docs/troubleshooting/frontend-assets.md`](../docs/troubleshooting/frontend-assets.md).

Verify after startup:

```bash
python3 scripts/check-frontend-assets.py
```

## Content database

The repository does not include a content database or videos.

Options:

1. Use a compatible recovered `content_khan_en.sqlite` that you already have.
   Place it at `deploy/database/staging/content_khan_en.sqlite`. The entrypoint
   copies it into `/data/database/` on first start. If you set
   `SEED_CONTENT_DB_SHA256` in `kalite.env`, the copy is verified.
2. Use the official 0.17 English content pack from the Learning Equality
   archive:
   <https://pantry.learningequality.org/downloads/ka-lite/0.17/content/contentpacks/en.zip>
   Follow the upstream KA Lite content-pack installation procedure for that
   archive. Do not assume the recovered database and the content pack contain
   the same content.

The known historical recovered English database used during the original
restoration has SHA-256:

```text
bb2959bbe00f6d81ed76898d7ade36e42aa0bbbbe93d00d919e71e1629899a26
```

That file is not distributed here.

## Videos and subtitles

`deploy/content/` is mounted at `/content` and is writable by the container's
UID 10001. Keep video payloads out of Git.

Use the optional recovery tool:

```bash
cd ..
python3 tools/video-recovery/kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --output deploy/content/recovered \
  --content-root deploy/content \
  --subtitles \
  --limit 10
```

Read [`tools/video-recovery/README.md`](../tools/video-recovery/README.md)
before downloading. Only download content you are permitted to use.

After adding videos, set `KA_LITE_REANNOTATE=1` in `kalite.env`, restart once,
and set it back to `0`:

```bash
docker compose restart ka-lite
```

## Offline operation

After the image is built and content is present, no Internet connection is
required for the original frontend, local videos, exercises, or administrative
pages. The optional Google Maps script on the facility form, the upstream
Google Analytics snippet, and the language-pack catalogue are external. The
facility form remains usable without the map; language-pack installation
requires Internet.

## Security

- The compose file binds only to `127.0.0.1:8008`.
- The container runs as UID/GID 10001 with a read-only root filesystem, all
  capabilities dropped, and `no-new-privileges`.
- `kalite.env` contains the initial admin credential; keep it mode 0600.
- Do not expose the port to an untrusted network without an access-controlled
  reverse proxy.
- Change the admin password after first login.

## Updating the deployment

```bash
git switch maintenance/kalite-0.17.5-working
git pull --ff-only
cd deploy
./scripts/fetch-static-wheel.sh
docker compose build
docker compose up -d --force-recreate
```

Do not run a broad `git reset --hard` or delete `deploy/data`, `deploy/content`,
or `deploy/database`.

## Tests

```bash
cd ..
python3 -m unittest discover -s tests/video-recovery -v
cd deploy
python3 scripts/check-frontend-assets.py
```

Browser validation results are in
[`docs/validation/README.md`](../docs/validation/README.md).

## Stop and rollback

```bash
cd deploy
docker compose down
```

The application data remains in `deploy/data`, `deploy/content`, and
`deploy/database`. Removing the container/image does not remove it.

If you need to remove the deployment entirely, first back up those directories;
do not delete a content collection you cannot recreate.

## Troubleshooting

- **Unstyled page / 404 for `bundle_common.js`:** the static wheel was not
  fetched or the image was built without it. Run
  `./scripts/fetch-static-wheel.sh`, rebuild, and check the asset script.
- **Container unhealthy:** inspect `docker compose logs ka-lite`. The first
  start can take longer than the health-check start period on slow storage.
- **Seed checksum mismatch:** update or clear `SEED_CONTENT_DB_SHA256` if you
  are intentionally using a different seed database.
- **No topics after setup:** the application database exists but no content
  database/content pack is installed. Install a compatible content source.
- **Permission errors:** `/data` and `/content` must be writable by UID 10001.
