#!/usr/bin/env python3
"""
build-video-index.py -- extract the Khan Academy video index from a legacy
KA Lite content database (``content_khan_en.sqlite``, KA Lite 0.16.x/0.17.x
schema: tables ``item`` and ``assessmentitem``).

The database is opened strictly READ-ONLY (SQLite URI ``mode=ro&immutable=1``);
nothing in this script writes to the source file.

Outputs (default directory /opt/ka-lite/data):
  khan-video-index.csv        one row per video record from the DB
  khan-video-filenames.txt    unique YouTube IDs / expected MP4 basenames
  khan-video-index-meta.json  machine-readable extraction summary

No metadata is invented: every field is either read from the database or
derived deterministically from it (filename = <youtube_id>.mp4).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone

DEFAULT_DB = "/opt/ka-lite/database/staging/content_khan_en.sqlite"
DEFAULT_OUTDIR = "/opt/ka-lite/data"

# A YouTube video id is 11 characters from [A-Za-z0-9_-].
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

CSV_COLUMNS = [
    "youtube_id",
    "mp4_filename",
    "title",
    "topic_path",
    "language",
    "ka_slug",
    "duration_seconds",
    "remote_size_bytes",
    "available",
    "files_complete",
    "total_files",
    "size_on_disk",
    "yt_id_valid",
    "duplicate_id",
]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect_ro(path: str) -> sqlite3.Connection:
    if not os.path.isfile(path):
        sys.exit(f"error: database not found: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def extra_fields(raw) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build(db_path: str, outdir: str, language: str) -> dict:
    conn = connect_ro(db_path)

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        sys.exit(f"error: PRAGMA integrity_check failed: {integrity}")

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "item" not in tables:
        sys.exit("error: expected table 'item' not found -- not a KA Lite content DB")

    kinds = dict(conn.execute(
        "SELECT kind, COUNT(*) FROM item GROUP BY kind").fetchall())
    if kinds.get("Video", 0) == 0:
        sys.exit("error: no rows with kind='Video' -- nothing to index")

    rows = conn.execute(
        """
        SELECT pk, id, youtube_id, title, description, kind, path, slug,
               available, files_complete, total_files, size_on_disk,
               remote_size, extra_fields
        FROM item
        WHERE kind = 'Video'
        ORDER BY path
        """
    ).fetchall()

    # Duplicate detection is over youtube_id (the DB's 'id' column holds the
    # YouTube id for video rows; it is identical to youtube_id in this release).
    id_counts = Counter(r["youtube_id"] for r in rows if r["youtube_id"])

    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "khan-video-index.csv")
    txt_path = os.path.join(outdir, "khan-video-filenames.txt")

    invalid_ids = []
    empty_ids = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            yt_id = (r["youtube_id"] or "").strip()
            if not yt_id:
                empty_ids += 1
                valid = "no"
            else:
                valid = "yes" if YT_ID_RE.match(yt_id) else "no"
                if valid == "no":
                    invalid_ids.append(yt_id)
            extra = extra_fields(r["extra_fields"])
            writer.writerow({
                "youtube_id": yt_id,
                "mp4_filename": f"{yt_id}.mp4" if yt_id else "",
                "title": (r["title"] or "").strip(),
                "topic_path": (r["path"] or "").strip(),
                "language": language,
                "ka_slug": (r["slug"] or "").strip(),
                "duration_seconds": extra.get("duration", ""),
                "remote_size_bytes": r["remote_size"] if r["remote_size"] else "",
                "available": r["available"],
                "files_complete": r["files_complete"],
                "total_files": r["total_files"],
                "size_on_disk": r["size_on_disk"],
                "yt_id_valid": valid,
                "duplicate_id": "yes" if id_counts.get(yt_id, 0) > 1 else "no",
            })

    # Unique filenames, sorted for reproducibility.
    unique_ids = sorted({r["youtube_id"] for r in rows if r["youtube_id"]})
    with open(txt_path, "w", encoding="utf-8") as fh:
        for yt_id in unique_ids:
            fh.write(f"{yt_id}.mp4\n")

    local_videos = sum(1 for r in rows if r["available"] or r["size_on_disk"])
    total_remote = sum(r["remote_size"] or 0 for r in rows)

    meta = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_database": os.path.abspath(db_path),
        "source_database_size_bytes": os.path.getsize(db_path),
        "source_database_sha256": sha256_of(db_path),
        "integrity_check": integrity,
        "schema_tables": sorted(tables),
        "language": language,
        "counts": {
            "item_rows_total": sum(kinds.values()),
            "by_kind": kinds,
            "video_rows": len(rows),
            "unique_youtube_ids": len(unique_ids),
            "duplicate_youtube_ids": sum(1 for k, v in id_counts.items() if v > 1),
            "extra_rows_from_duplicates": len(rows) - len(unique_ids),
            "rows_with_empty_youtube_id": empty_ids,
            "rows_with_invalid_youtube_id": len(invalid_ids),
            "videos_with_local_file_flagged": local_videos,
            "videos_with_remote_size": sum(1 for r in rows if r["remote_size"]),
            "total_remote_bytes": total_remote,
            "total_remote_gib": round(total_remote / 1024 ** 3, 2),
        },
        "invalid_youtube_ids": invalid_ids[:50],
        "most_duplicated_ids": [
            {"youtube_id": k, "occurrences": v}
            for k, v in id_counts.most_common(10) if v > 1
        ],
        "outputs": {"csv": csv_path, "filenames_txt": txt_path},
    }
    meta_path = os.path.join(outdir, "khan-video-index-meta.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return meta, meta_path, csv_path, txt_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database", default=DEFAULT_DB)
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    ap.add_argument("--language", default="en")
    args = ap.parse_args()

    meta, meta_path, csv_path, txt_path = build(
        args.database, args.outdir, args.language)

    c = meta["counts"]
    print(f"database      : {meta['source_database']}")
    print(f"sha256        : {meta['source_database_sha256']}")
    print(f"integrity     : {meta['integrity_check']}")
    print(f"video rows    : {c['video_rows']}")
    print(f"unique ids    : {c['unique_youtube_ids']}")
    print(f"duplicates    : {c['duplicate_youtube_ids']} ids "
          f"({c['extra_rows_from_duplicates']} extra rows)")
    print(f"invalid ids   : {c['rows_with_invalid_youtube_id']}")
    print(f"local files   : {c['videos_with_local_file_flagged']}")
    print(f"CSV           : {csv_path}")
    print(f"filenames     : {txt_path}")
    print(f"metadata      : {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
