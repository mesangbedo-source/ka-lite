# Validation

**Date:** 2026-10-24
**Branch:** `maintenance/kalite-0.17.5-working`
**Fork revision:** `working.1`

## Environment

- Linux Mint 22.3 (Zena), kernel `7.3.0-ryzen5950x`, x86_64.
- Docker 29.1.3, Docker Compose 2.40.3.
- KA Lite 0.17.5, Python 2.7.18, Django 1.5.12, CherryPy 3.3.0.
- Chromium 156.0.8078.47 at 1280x900.
- Python 3.12 host; yt-dlp 2026.08.30; ffprobe 6.1.1.
- The test deployment used a copy of the historical data/content directories on
  an isolated port (`127.0.0.1:8012`) so the working installation on port 8008
  was not modified.

## Build

Detailed build transcript summary: `build.txt`.

- `docker compose build` from `deploy/` succeeded.
- Test image: `ka-lite:0.17.5-working`
  (`sha256:3164fda64dd3ba1a7f7ee5a49bfb8702b90644016f7cdce1f2dd970aa6e9b9dc`).
- The build verified the official `ka-lite-static` wheel SHA-256 and found
  `bundle_common.js` in the installed package.
- The isolated test container started healthy.

## Frontend static assets

`deploy/scripts/check-frontend-assets.py --base http://127.0.0.1:8012`
reported **17/17 PASS**. Full output: `frontend-assets.txt`.

The test copied the data directory without its old `STATIC_ROOT`, so the
entrypoint exercised the repair path:

```text
[ka-lite-init] Frontend bundles missing from /data/httpsrv/static; running collectstatic
2310 static files copied.
```

## Browser checks

Results: `fork-browser.json`.

| Page | Local static errors | Console errors | Page errors |
|---|---|---|---|
| Homepage | 0 | 0 | 0 |
| Login modal | 0 | 0 | 0 |
| Management console | 0 | 0 | 0 |
| Django admin | 0 | 0 | 0 |
| Learner topic tree | 0 | 0 | 0 |
| Video page | 0 | 0 | 0 |
| Exercise page | 0 | 2 content 404s | 0 |

Metrics:

- `body` font `"Helvetica Neue", Helvetica, Arial, sans-serif`;
- navbar background `rgb(196, 215, 227)`;
- logo natural size **138 x 33**;
- jQuery and `sessionModel` present;
- ~316 KB inline Bootstrap/LESS CSS.

Video page: local MP4 `O-6q-siuMik.mp4` loaded with `readyState=4`,
1280x720; a range request returned HTTP **206** and `video/mp4`.

Exercise page: the exercise engine rendered the question and answer controls.
Two assessment images returned 404 because the copied local content directory
does not contain those assessment image files. This is a content-data
limitation, not a frontend asset error; the exercise text and controls work.

Screenshots: `docs/images/before-home.png`, `after-home.png`,
`after-login-modal.png`, `after-manage.png`, `after-admin.png`,
`after-learn.png`, `after-video.png`, `after-exercise.png`,
`offline-facility-new.png`.

## Video index builder

`tools/video-index/build_video_index.py` was run against the copied historical
database. It reported:

```text
integrity     : ok
video rows    : 11235
unique ids    : 8033
duplicates    : 2379 ids (3202 extra rows)
invalid ids   : 0
```

This verifies the 8,033 unique-ID figure against the actual database. It does
not verify that every video is still available or legally downloadable.

## Existing upstream compatibility tests

The three local compatibility test modules were run from the maintenance branch
with the existing `ka-lite:0.17.5-test-min` harness:

```text
kalite.contentload.tests.settings_tests
kalite.topic_tools.tests.content_db_discovery_tests
kalite.distributed.tests.cli_tests
```

Result: **12/13 passed**. The single failure is `cli_tests.test_manage`
(`videoscan`), which fails because the ad-hoc in-memory test database does not
have the South-migrated `updates_updateprogresslog` table. This is the known
harness limitation documented in the original installation report, not a
frontend or maintenance-branch regression. Full log:
`upstream-tests.txt`.

## Recovery utility tests

`python3 -m unittest discover -s tests/video-recovery -v` ran **20 tests**,
all passing. Output: `video-recovery-tests.txt`.

The tests cover ID/URL validation, safe paths, SRT conversion, index
deduplication, manifest output, checksum verification, quality selectors,
`ffprobe` stream parsing, quality/codec warnings, and graceful failure when
`yt-dlp` is unavailable. No video content was downloaded during validation.

## Known limitations

- The deployment test used an existing recovered content database and 27
  historical videos copied from the working installation; a fresh install needs
  its own compatible content source.
- Assessment images are not present for every exercise in the recovered local
  content; those 404s are content-data gaps, not missing frontend bundles.
- The facility map, Google Analytics, and language-pack catalogue require
  Internet. The facility form works without the map.
- The English language-pack warning is upstream behavior; no 0.17 English pack
  is bundled.
- Only this environment was tested. Other distributions, kernels, browsers,
  Python versions, and content databases were not validated.
