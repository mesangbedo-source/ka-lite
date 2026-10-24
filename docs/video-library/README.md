# Video Library Roadmap

**Status:** tooling ready; no video collection is included or claimed complete.

This fork does not ship Khan Academy videos, thumbnails, torrents, or a content
database. The optional recovery tool can populate a local library from public,
permitted sources.

## Historical index

The original restored content database (`content_khan_en.sqlite`, KA Lite
0.16.x/0.17.x schema) contained 11,235 video rows and **8,033 unique valid
YouTube IDs** according to `scripts/build-video-index.py`. Re-run the index
builder against your own database before relying on those counts; do not assume
the fork's historical count applies to a different content source.

The index builder is included at `tools/video-index/build_video_index.py`. It
opens the content database read-only and writes the CSV/TXT/JSON index. See
`tools/video-index/README.md`. The recovery tool accepts any CSV with a
`youtube_id` column and optional `title`, `topic_path`, `duration_seconds`, and
`remote_size_bytes` columns.

## Recovery tool

Location: `tools/video-recovery/`
Tests: `tests/video-recovery/`
Usage: `tools/video-recovery/README.md`

Key behavior:

- 11-character YouTube IDs only; arbitrary URLs are rejected.
- Output filenames preserve the YouTube ID (`<id>.mp4`).
- Quality profiles: `--quality 360`, `480`, `720`, `1080`, or `best`
  (default 720).
- Default `--format mp4` prefers H.264 video and AAC audio with an MP4
  container; `--format best` selects the highest available streams within the
  quality cap.
- `--recode` is explicit and optional; the default does not re-encode.
- Resumable `.part` downloads; existing non-empty files are skipped unless
  `--overwrite` is given.
- `ffprobe` records duration, resolution, frame rate, video codec, and audio
  codec; it warns on quality-cap or codec mismatches.
- SHA-256 checksums and a JSON manifest are written after every item.
- Optional English subtitles are downloaded as SRT and converted to VTT under
  the KA Lite `srt/<lang>/subtitles/` layout.
- `import-srt` imports existing SRT files without downloading video.

Example dry run:

```bash
python3 tools/video-recovery/kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --video-id O-6q-siuMik \
  --output deploy/content/recovered \
  --quality 720 \
  --dry-run
```

Real download of one video:

```bash
python3 tools/video-recovery/kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --video-id O-6q-siuMik \
  --output deploy/content/recovered \
  --content-root deploy/content \
  --quality 720 \
  --subtitles
```

Use `--limit N` for a small batch. Read the utility README before running a
large batch; disk space and source availability are the main constraints.

## Manifest and verification

The default manifest is `deploy/content/recovered/manifest.json`. It records:

- YouTube ID, title, topic path, source URL;
- status (`planned`, `downloaded`, `skipped_existing`, `failed`);
- local file path, byte size, SHA-256;
- requested quality and actual `ffprobe` resolution/codecs;
- optional subtitle paths and hashes;
- timestamps and summary counts.

Verify later:

```bash
python3 tools/video-recovery/kalite_video_recovery.py verify \
  --manifest deploy/content/recovered/manifest.json \
  --report deploy/content/recovered/verify-report.json
```

## Integrating with KA Lite

The container mounts `deploy/content` at `/content`. Put the downloaded MP4s
where KA Lite expects them, or point `--output` at the content root. Set
`KA_LITE_REANNOTATE=1` in `deploy/kalite.env`, restart once so KA Lite scans the
content directory, confirm the videos appear, then set it back to `0`.

Do not edit the content database by hand. Do not modify the original KA Lite
interface. Test representative videos in the original frontend before declaring
the library usable.

## Quality and compatibility

- Prefer H.264/AAC MP4 for legacy browser and device compatibility.
- Do not claim a resolution or codec without `ffprobe` evidence.
- Preserve the original aspect ratio; the default path does not re-encode.
- Record unavailable, private, removed, and region-restricted videos in the
  manifest/error report. Do not attempt to bypass access controls or DRM.
- A 1080p profile does not guarantee that a given source has 1080p; the selector
  falls back and `ffprobe` records the actual result.

## Licensing and redistribution

The user is responsible for confirming that each video may be downloaded,
stored, and redistributed. KA Lite's MIT license covers the software, not Khan
Academy or third-party content. Do not create or seed a torrent until the
content licenses and redistribution permissions have been verified.

A historical torrent existing does not establish that a newly downloaded
higher-resolution copy may be redistributed.

## Later torrent phase

Only after the library is downloaded, verified, and licensed for distribution:

1. create an authorized distribution manifest with IDs, titles, resolutions,
   codecs, sizes, and checksums;
2. preserve attribution and license files;
3. divide very large collections into manageable torrents if useful;
4. support community seeding and optional web seeds;
5. verify torrent metadata and data integrity;
6. document import into KA Lite;
7. obtain explicit owner approval before publishing or seeding.

Video payloads and torrent data must stay outside the Git repository.
