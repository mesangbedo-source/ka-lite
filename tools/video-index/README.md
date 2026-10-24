# KA Lite Video Index Builder

This helper reads a compatible KA Lite content database
(`content_khan_en.sqlite`, 0.16.x/0.17.x schema) in read-only mode and writes:

- `khan-video-index.csv` — one row per video with `youtube_id`, title, topic
  path, duration, remote size, and availability fields;
- `khan-video-filenames.txt` — unique YouTube IDs as `<id>.mp4`;
- `khan-video-index-meta.json` — counts, hashes, and integrity check.

Usage:

```bash
python3 tools/video-index/build_video_index.py \
  --database /path/to/content_khan_en.sqlite \
  --outdir deploy/content
```

The database is opened with SQLite read-only/immutable flags. The script does
not modify the database. Verify the generated counts against your own database
before using them for a download plan.

The historical recovered English database used during the original restoration
reported 11,235 video rows, 8,033 unique valid YouTube IDs, 2,379 duplicated
IDs, and 0 invalid IDs. Those figures apply to that database only.
