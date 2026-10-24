# KA Lite Video Recovery (optional companion tool)

This is an **optional** command-line helper for administrators who need to
recover missing video files for an existing KA Lite 0.17.5 installation. It is
not part of KA Lite, is not required for the frontend repair, and does not
modify KA Lite source code, the content database, or existing media files.

The tool uses [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) to download a
specific public YouTube video by its 11-character ID, validates the resulting
file, computes SHA-256 checksums, and writes a local manifest. An existing
`.srt` file can be imported and converted to the VTT form used by KA Lite.

**The user is responsible for confirming that they have the right to download,
store, and redistribute any video or subtitle.** KA Lite's MIT software license
does not grant rights to Khan Academy or third-party educational content. YouTube
terms, content licenses, and local law still apply. This tool does not attempt
to enforce copyright or licensing automatically.

## Requirements

- Python 3.10 or newer (the current `yt-dlp` release requires 3.10+).
- `yt-dlp` on `PATH`, or passed with `--yt-dlp`.
- `ffmpeg` for MP4 merging; optional `ffprobe` for duration, resolution, and codec checks.
- No Python packages are required by this tool itself.

Install the external tools as appropriate for your system, for example:

```bash
python3 -m pip install --user yt-dlp
# ffmpeg/ffprobe: use your distribution package manager or an existing build
```

## Safety and file policy

- Only 11-character YouTube IDs are accepted; arbitrary URLs are not passed to
  `yt-dlp`.
- Output filenames are always `<id>.mp4`; titles are never used as paths.
- Existing files are never deleted. The default behavior is to skip an existing
  non-empty file. Re-downloading requires the explicit `--overwrite` flag.
- Partial `.part` files left by `yt-dlp` are left in place so a later run can
  resume.
- The tool writes a manifest atomically after each item so progress survives an
  interruption.
- It does not update KA Lite's content database or rebuild the video index. Run
  the existing KA Lite annotation/scan procedure when you are satisfied with the
  recovered files.

## Related helper

`tools/video-index/build_video_index.py` reads a compatible KA Lite content
database in read-only mode and produces `khan-video-index.csv`, the input
expected by this tool. See `tools/video-index/README.md`.

## Usage

Start with a dry run. This writes the plan and the exact `yt-dlp` command but
does not contact YouTube:

```bash
python3 kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --video-id O-6q-siuMik \
  --output deploy/content/recovered \
  --dry-run
```

Download one video in the default MP4/H.264/AAC-preferred format at 720p:

```bash
python3 kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --video-id O-6q-siuMik \
  --output deploy/content/recovered \
  --quality 720
```

Use `--quality 360`, `480`, `720`, `1080`, or `best`. The default is 720p. The
tool prefers H.264/AAC MP4 and records the actual resolution and codecs from
`ffprobe`.

Download the first ten missing videos from the KA Lite index, with English
subtitles (where available), placing subtitles under
`deploy/content/srt/<lang>/subtitles/`:

```bash
python3 kalite_video_recovery.py download \
  --index-csv /path/to/khan-video-index.csv \
  --output deploy/content/recovered \
  --limit 10 \
  --subtitles \
  --content-root deploy/content
```

Use `--quality best` with `--format best` for the highest available quality
instead of the default resolution cap. Use `--recode` only when a strict MP4
output is required; it invokes `ffmpeg` and can be slow and lossy. The default
360p/480p/720p/1080p selectors all fall back to a lower resolution if the
requested one is unavailable.

Import existing SRT files without downloading anything:

```bash
python3 kalite_video_recovery.py import-srt \
  --srt-dir ./captions \
  --subtitle-root deploy/content/srt
```

`ID.en.srt` is treated as English; `ID.srt` uses `--lang en` by default. Both
`.srt` and `.vtt` are written under
`<subtitle-root>/<lang>/subtitles/`. Verify that this matches the subtitle path
used by your KA Lite installation; 0.17.5 builds the URL as
`/content/srt/<lang>/subtitles/<id>.vtt`.

Verify a manifest and checksum report against the files on disk:

```bash
python3 kalite_video_recovery.py verify \
  --manifest deploy/content/recovered/manifest.json \
  --report deploy/content/recovered/verify-report.json
```

## Manifest

The default manifest is `<output>/manifest.json`. It contains:

- schema and tool versions, creation/update timestamps;
- the source index path and SHA-256;
- per-video YouTube ID, title, topic path, source URL, status, local path,
  byte size, SHA-256, media-duration check, subtitle paths and hashes;
- a summary count by status and total recovered bytes.

Status values include `planned`, `downloaded`, `skipped_existing`, `failed`,
`imported`, and verification results. A failed item does not stop the remaining
items; the process exit code is non-zero if any item failed.

## Integrity checks

- File exists, is readable, and is larger than `--min-bytes` (default 1024).
- SHA-256 is computed for every file.
- If `ffprobe` is available, duration must be greater than zero and is compared
  with the index duration when present (5-second or 2% tolerance).
- `ffprobe` records the video codec, width, height and frame rate, plus the
  audio codec. A resolution above the requested quality cap, or a non-H.264/AAC
  stream in the default MP4 mode, is reported as a warning.
- A missing `ffprobe` produces a warning, not a false failure.
- A checksum mismatch during `verify` is a failure.

## Tests

```bash
cd /path/to/ka-lite
python3 -m unittest discover -s tests/video-recovery -v
```

The tests use temporary directories and mocks; they do not contact YouTube or
download content.

## Validated environment and limitations

Validated on the environment recorded in
`docs/validation/README.md`: Linux Mint 22.3, kernel
`7.3.0-ryzen5950x`, Python 3.12, `yt-dlp` present, `ffprobe` 6.1.1, KA Lite
0.17.5. Only dry-run, subtitle import, manifest, and verification paths were
executed against the real environment; no video content was downloaded during
validation. The unit tests cover command construction, URL/ID validation,
filename safety, SRT conversion, manifest writing, checksum verification, and
graceful failure when `yt-dlp` is unavailable.

This tool has not been validated on Windows, macOS, other Python versions, or
other KA Lite releases. YouTube availability, `yt-dlp` behavior, and content
licensing can change independently of this tool. It does not guarantee that any
particular video is available, complete, correctly licensed, or suitable for a
given deployment.

## AI assistance disclosure

This utility was developed with the assistance of an AI coding agent (Crush)
under the human contributor's direction. The generated code was reviewed,
tested locally, and limited to the scope described above. The human contributor
is responsible for the decision to use it and for compliance with content
licenses and platform terms. Broader compatibility has not been established.

## License

This tool is offered under the same MIT terms as the KA Lite software. That
license does not cover downloaded videos, thumbnails, subtitles, or other
third-party content.
