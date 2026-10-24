# Offline Installation Notes

This fork is designed for local, offline-first deployments. The build has
one-time online requirements; the running application does not.

## Build-time network access

- Debian archive packages (`net-tools`) for the Python 2.7 image.
- Python packages from the package index for the pinned KA Lite requirements.
- The official `ka-lite-static` 0.17.5 wheel from PyPI.

The static wheel is not committed. Fetch it with
`deploy/scripts/fetch-static-wheel.sh`; the SHA-256 is pinned in the script and
in `deploy/Dockerfile`.

## Runtime network access

Not required for:

- the KA Lite frontend (CSS, JavaScript, fonts, images);
- local videos and subtitles;
- exercises and administrative pages;
- login and learner accounts.

External and optional:

- the Google Maps script on the Add/Edit Facility form;
- the upstream Google Analytics snippet on the updates page;
- the language-pack catalogue at `pantry.learningequality.org`;
- downloading new content.

The facility form is usable without the map. Language-pack installation
requires network access. The English language-pack warning is upstream
behavior when no 0.17 English pack is installed; it is not hidden.

## Storage layout

```text
deploy/data/        application database, logs, collected static
deploy/content/     videos and subtitles (not committed)
deploy/database/    optional read-only seed content database
deploy/vendor/      fetched static wheel (not committed)
deploy/kalite.env   local credentials (not committed)
```

Back up `data`, `content`, and `database` together. A restored application
database without the matching content database will not show the same topic
tree.

## Content database options

- Use the recovered `content_khan_en.sqlite` from an existing KA Lite 0.16/0.17
  installation, if you have the rights to use it.
- Use the official 0.17 English content pack from the Learning Equality
  archive, following the upstream content-pack procedure.
- Start with no content database to verify the frontend and login, then add
  content later.

The historical recovered English database is not included in this fork. Its
known SHA-256 is recorded in `deploy/kalite.env.example` for optional
verification.

## Offline verification

1. Build the image and start the container.
2. Open the homepage and confirm the original layout, logo, navigation, and
   login modal.
3. Stop external network access, or use browser developer tools to block
   non-loopback requests.
4. Reload the homepage; CSS and JavaScript should still load from the local
   server.
5. Play a local video and open an exercise.
6. Expect the facility map and language catalogue to be unavailable; the
   facility form itself should remain usable.

The original frontend validation used Chromium at 1280x900; see
[`docs/validation/README.md`](../validation/README.md).
