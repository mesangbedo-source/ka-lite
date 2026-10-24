#!/usr/bin/env python3
"""Optional recovery helper for missing KA Lite video files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

TOOL_NAME = "kalite-video-recovery"
TOOL_VERSION = "0.1.0"
MANIFEST_SCHEMA = 1

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
RATE_LIMIT_RE = re.compile(r"^\d+(?:\.\d+)?[KMG]?$")
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")
SUBTITLE_RE = re.compile(r"^(?P<id>[A-Za-z0-9_-]{11})(?:\.(?P<lang>[A-Za-z0-9_-]+))?\.srt$")

MP4_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]"
    "/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
)
BEST_FORMAT = "bestvideo+bestaudio/best"
QUALITY_HEIGHTS = {"360": 360, "480": 480, "720": 720, "1080": 1080}


class RecoveryError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid_video_id(value: str) -> bool:
    return bool(VIDEO_ID_RE.match((value or "").strip()))


def youtube_url(video_id: str) -> str:
    if not valid_video_id(video_id):
        raise ValueError("invalid YouTube video id: %r" % (video_id,))
    return "https://www.youtube.com/watch?v=%s" % video_id


def video_path(output_dir: Path, video_id: str) -> Path:
    if not valid_video_id(video_id):
        raise ValueError("invalid YouTube video id: %r" % (video_id,))
    base = output_dir.resolve()
    target = (base / (video_id + ".mp4")).resolve()
    if target.parent != base:
        raise ValueError("unsafe output path for video id: %r" % (video_id,))
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def srt_to_vtt(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("empty SRT content")
    blocks = re.split(r"\n{2,}", normalized)
    output: List[str] = ["WEBVTT", ""]
    seen = 0
    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].strip().isdigit():
            lines = lines[1:]
        if not lines:
            continue
        if "-->" not in lines[0]:
            continue
        timing = lines[0].replace(",", ".")
        output.append(str(seen + 1))
        output.append(timing)
        output.extend(lines[1:])
        output.append("")
        seen += 1
    if seen == 0:
        raise ValueError("no SRT cues found")
    return "\n".join(output).rstrip() + "\n"


def load_index(path: Path) -> Tuple[Dict[str, dict], dict]:
    records: Dict[str, dict] = {}
    skipped = 0
    duplicates = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "youtube_id" not in reader.fieldnames:
            raise RecoveryError("index CSV is missing the youtube_id column")
        for row in reader:
            video_id = (row.get("youtube_id") or "").strip()
            if not valid_video_id(video_id):
                skipped += 1
                continue
            if video_id in records:
                duplicates += 1
                continue
            records[video_id] = {
                "youtube_id": video_id,
                "title": (row.get("title") or "").strip(),
                "topic_path": (row.get("topic_path") or "").strip(),
                "duration_seconds": parse_int(row.get("duration_seconds")),
                "remote_size_bytes": parse_int(row.get("remote_size_bytes")),
            }
    metadata = {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "valid_ids": len(records),
        "skipped_rows": skipped,
        "duplicate_rows": duplicates,
    }
    return records, metadata


def parse_int(value: object) -> Optional[int]:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def check_media(
    path: Path,
    ffprobe: Optional[str],
    expected_duration: Optional[int],
    max_height: Optional[int] = None,
    prefer_mp4: bool = False,
) -> dict:
    result = {
        "exists": path.is_file(),
        "readable": False,
        "bytes": 0,
        "sha256": None,
        "ffprobe": None,
        "duration_seconds": None,
        "video": None,
        "audio": None,
        "warnings": [],
        "errors": [],
    }
    if not result["exists"]:
        result["errors"].append("file_missing")
        return result
    try:
        with path.open("rb") as handle:
            handle.read(1)
        result["readable"] = True
    except OSError as error:
        result["errors"].append("file_unreadable: %s" % error)
        return result
    result["bytes"] = path.stat().st_size
    if result["bytes"] == 0:
        result["errors"].append("zero_bytes")
        return result
    result["sha256"] = sha256_file(path)
    if not ffprobe:
        result["warnings"].append("ffprobe_unavailable")
        return result
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        result["warnings"].append("ffprobe_failed: %s" % error)
        return result
    if completed.returncode != 0:
        result["warnings"].append("ffprobe_failed: %s" % (completed.stderr or "").strip()[:300])
        return result
    try:
        payload = json.loads(completed.stdout or "{}")
        duration = float(payload.get("format", {}).get("duration"))
    except (ValueError, TypeError):
        result["warnings"].append("ffprobe_invalid_output")
        return result
    result["ffprobe"] = "ok"
    result["duration_seconds"] = round(duration, 3)
    if duration <= 0:
        result["errors"].append("zero_duration")
    if expected_duration and duration > 0:
        tolerance = max(5.0, expected_duration * 0.02)
        if abs(duration - expected_duration) > tolerance:
            result["warnings"].append(
                "duration_mismatch: expected %ss, got %.1fs" % (expected_duration, duration)
            )
    streams = payload.get("streams", []) if isinstance(payload, dict) else []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream:
        result["video"] = {
            "codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "avg_frame_rate": video_stream.get("avg_frame_rate"),
        }
        if max_height and video_stream.get("height") and video_stream["height"] > max_height + 1:
            result["warnings"].append(
                "quality_exceeds_requested: %sp requested, got %sp"
                % (max_height, video_stream["height"])
            )
        if prefer_mp4 and video_stream.get("codec_name") not in ("h264",):
            result["warnings"].append(
                "video_codec_not_h264: %s" % video_stream.get("codec_name")
            )
    if audio_stream:
        result["audio"] = {"codec": audio_stream.get("codec_name")}
        if prefer_mp4 and audio_stream.get("codec_name") not in ("aac",):
            result["warnings"].append(
                "audio_codec_not_aac: %s" % audio_stream.get("codec_name")
            )
    return result


class Manifest:
    def __init__(self, path: Path, context: dict):
        self.path = path
        self.context = context
        self.payload = {
            "schema_version": MANIFEST_SCHEMA,
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
            "created_utc": utc_now(),
            "updated_utc": utc_now(),
            "context": context,
            "videos": {},
        }
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = None
            if isinstance(existing, dict) and isinstance(existing.get("videos"), (dict, list)):
                videos = existing.get("videos")
                if isinstance(videos, list):
                    videos = {item.get("youtube_id"): item for item in videos if isinstance(item, dict)}
                self.payload["videos"] = videos
                self.payload["created_utc"] = existing.get("created_utc", self.payload["created_utc"])
                self.payload["schema_version"] = existing.get("schema_version", MANIFEST_SCHEMA)

    def update(self, video_id: str, entry: dict) -> None:
        current = self.payload["videos"].get(video_id, {})
        current.update(entry)
        current["youtube_id"] = video_id
        self.payload["videos"][video_id] = current

    def save(self) -> None:
        self.payload["updated_utc"] = utc_now()
        self.payload["summary"] = summarize(self.payload["videos"])
        atomic_write_json(self.path, self.payload)


def summarize(videos: Dict[str, dict]) -> dict:
    counts: Dict[str, int] = {}
    for entry in videos.values():
        status = entry.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(videos),
        "by_status": counts,
        "bytes": sum(int(entry.get("bytes") or 0) for entry in videos.values()),
    }


def resolve_tool(explicit: Optional[str], name: str) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    return shutil.which(name)


def quality_height(quality: str) -> Optional[int]:
    return QUALITY_HEIGHTS.get(str(quality))


def format_selector(fmt: str, quality: str) -> str:
    height = quality_height(quality)
    if height is None:
        return MP4_FORMAT if fmt == "mp4" else BEST_FORMAT
    if fmt == "mp4":
        return (
            "bestvideo[height<=%d][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]"
            "/bestvideo[height<=%d][ext=mp4]+bestaudio[ext=m4a]"
            "/best[height<=%d][ext=mp4]"
            "/bestvideo[height<=%d]+bestaudio"
            "/best[height<=%d]/best"
        ) % (height, height, height, height, height)
    return "bestvideo[height<=%d]+bestaudio/best[height<=%d]/best" % (height, height)


def build_download_command(
    yt_dlp: str,
    video_id: str,
    output_dir: Path,
    args: argparse.Namespace,
) -> List[str]:
    selector = format_selector(args.format, args.quality)
    command = [
        yt_dlp,
        "--no-playlist",
        "--continue",
        "--no-overwrites" if not args.overwrite else "--force-overwrites",
        "--format",
        selector,
        "--merge-output-format",
        "mp4",
        "--output",
        str(output_dir / "%(id)s.%(ext)s"),
        "--retries",
        str(args.retries),
        "--fragment-retries",
        str(args.retries),
        "--socket-timeout",
        "30",
        "--newline",
        "--no-progress",
    ]
    if args.recode:
        command.extend(["--recode-video", "mp4"])
    if args.ffmpeg_location:
        command.extend(["--ffmpeg-location", args.ffmpeg_location])
    if args.rate_limit:
        command.extend(["--limit-rate", args.rate_limit])
    if args.subtitles:
        command.extend(
            [
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                args.sub_langs,
                "--convert-subs",
                "srt",
            ]
        )
    command.append(youtube_url(video_id))
    return command


def locate_video(output_dir: Path, video_id: str) -> Optional[Path]:
    preferred = video_path(output_dir, video_id)
    if preferred.is_file():
        return preferred
    for extension in VIDEO_EXTENSIONS:
        candidate = output_dir / (video_id + extension)
        if candidate.is_file():
            return candidate
    return None


def subtitle_root(args: argparse.Namespace, output_dir: Path) -> Path:
    if args.subtitle_root:
        return Path(args.subtitle_root).expanduser().resolve()
    if args.content_root:
        return (Path(args.content_root).expanduser().resolve() / "srt")
    return (output_dir / "srt").resolve()


def import_subtitles_for_video(
    output_dir: Path,
    video_id: str,
    lang: str,
    subtitle_base: Path,
) -> List[dict]:
    imported: List[dict] = []
    for source in sorted(output_dir.glob(video_id + ".*.srt")):
        match = SUBTITLE_RE.match(source.name)
        if not match:
            continue
        source_lang = match.group("lang") or lang
        destination_dir = subtitle_base / source_lang / "subtitles"
        destination_dir.mkdir(parents=True, exist_ok=True)
        srt_target = destination_dir / (video_id + ".srt")
        vtt_target = destination_dir / (video_id + ".vtt")
        text = source.read_text(encoding="utf-8", errors="replace")
        vtt_text = srt_to_vtt(text)
        srt_target.write_text(text, encoding="utf-8")
        vtt_target.write_text(vtt_text, encoding="utf-8")
        imported.append(
            {
                "language": source_lang,
                "srt": str(srt_target),
                "vtt": str(vtt_target),
                "srt_sha256": sha256_file(srt_target),
                "vtt_sha256": sha256_file(vtt_target),
                "bytes": srt_target.stat().st_size,
            }
        )
    return imported


def download_one(
    video_id: str,
    metadata: dict,
    output_dir: Path,
    manifest: Manifest,
    args: argparse.Namespace,
    yt_dlp: Optional[str],
) -> bool:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = locate_video(output_dir, video_id) if not args.overwrite else None
    if target and target.stat().st_size >= args.min_bytes:
        check = check_media(
            target,
            resolve_tool(args.ffprobe, "ffprobe"),
            metadata.get("duration_seconds"),
            max_height=quality_height(args.quality),
            prefer_mp4=(args.format == "mp4"),
        )
        manifest.update(
            video_id,
            {
                "title": metadata.get("title", ""),
                "topic_path": metadata.get("topic_path", ""),
                "source_url": youtube_url(video_id),
                "status": "skipped_existing" if not check["errors"] else "failed_existing",
                "file": str(target),
                "bytes": check["bytes"],
                "sha256": check["sha256"],
                "media": check,
                "quality": args.quality,
                "requested_max_height": quality_height(args.quality),
                "format": args.format,
                "timestamp_utc": utc_now(),
            },
        )
        manifest.save()
        return not check["errors"]

    command = build_download_command(yt_dlp or "yt-dlp", video_id, output_dir, args)
    entry = {
        "title": metadata.get("title", ""),
        "topic_path": metadata.get("topic_path", ""),
        "source_url": youtube_url(video_id),
        "status": "planned",
        "file": str(video_path(output_dir, video_id)),
        "command": command,
        "quality": args.quality,
        "requested_max_height": quality_height(args.quality),
        "format": args.format,
        "timestamp_utc": utc_now(),
    }
    if args.dry_run:
        manifest.update(video_id, entry)
        manifest.save()
        return True
    if not yt_dlp:
        entry["status"] = "failed"
        entry["error"] = "yt-dlp_not_found"
        manifest.update(video_id, entry)
        manifest.save()
        return False
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        entry["status"] = "failed"
        entry["error"] = "timeout"
        manifest.update(video_id, entry)
        manifest.save()
        return False
    except OSError as error:
        entry["status"] = "failed"
        entry["error"] = "yt-dlp_exec_failed: %s" % error
        manifest.update(video_id, entry)
        manifest.save()
        return False

    entry["yt_dlp_returncode"] = completed.returncode
    if completed.returncode != 0:
        entry["status"] = "failed"
        entry["error"] = "yt-dlp_exit_%d" % completed.returncode
        entry["stderr_tail"] = (completed.stderr or "").strip()[-2000:]
        manifest.update(video_id, entry)
        manifest.save()
        return False

    target = locate_video(output_dir, video_id)
    if not target:
        entry["status"] = "failed"
        entry["error"] = "output_file_missing"
        entry["stdout_tail"] = (completed.stdout or "").strip()[-2000:]
        manifest.update(video_id, entry)
        manifest.save()
        return False

    check = check_media(
        target,
        resolve_tool(args.ffprobe, "ffprobe"),
        metadata.get("duration_seconds"),
        max_height=quality_height(args.quality),
        prefer_mp4=(args.format == "mp4"),
    )
    entry.update(
        {
            "status": "downloaded" if not check["errors"] else "failed",
            "file": str(target),
            "bytes": check["bytes"],
            "sha256": check["sha256"],
            "media": check,
            "quality": args.quality,
            "requested_max_height": quality_height(args.quality),
            "format": args.format,
        }
    )
    if check["errors"]:
        entry["error"] = ",".join(check["errors"])
    if args.subtitles:
        try:
            subtitles = import_subtitles_for_video(
                output_dir, video_id, args.sub_langs.split(",")[0].strip() or "en", subtitle_root(args, output_dir)
            )
        except (OSError, ValueError) as error:
            subtitles = []
            entry["subtitle_error"] = str(error)
        entry["subtitles"] = subtitles
        if not subtitles:
            entry.setdefault("warnings", []).append("no_subtitles_found")
    manifest.update(video_id, entry)
    manifest.save()
    return entry["status"] == "downloaded"


def collect_video_ids(args: argparse.Namespace, index: Dict[str, dict]) -> List[str]:
    requested: List[str] = []
    for value in args.video_id or []:
        if not valid_video_id(value):
            raise RecoveryError("invalid video id: %r" % (value,))
        if value not in requested:
            requested.append(value)
    if not requested:
        requested = list(index.keys())
    if args.limit is not None:
        requested = requested[: args.limit]
    if not requested:
        raise RecoveryError("no valid video ids were selected")
    return requested


def command_download(args: argparse.Namespace) -> int:
    index: Dict[str, dict] = {}
    index_meta = {}
    if args.index_csv:
        index, index_meta = load_index(Path(args.index_csv).expanduser())
    video_ids = collect_video_ids(args, index)
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest).expanduser() if args.manifest else output_dir / "manifest.json"
    manifest = Manifest(
        manifest_path,
        {
            "mode": "download",
            "output_dir": str(output_dir),
            "index": index_meta,
            "format": args.format,
            "quality": args.quality,
            "subtitles": bool(args.subtitles),
            "subtitle_root": str(subtitle_root(args, output_dir)) if args.subtitles else None,
        },
    )
    yt_dlp = resolve_tool(args.yt_dlp, "yt-dlp")
    failures = 0
    for position, video_id in enumerate(video_ids, 1):
        metadata = index.get(video_id, {})
        print("[%d/%d] %s" % (position, len(video_ids), video_id), flush=True)
        if not download_one(video_id, metadata, output_dir, manifest, args, yt_dlp):
            failures += 1
        if args.sleep and position < len(video_ids):
            time.sleep(args.sleep)
    manifest.save()
    summary = summarize(manifest.payload["videos"])
    print("manifest: %s" % manifest_path)
    print("summary: %s" % json.dumps(summary, sort_keys=True))
    return 1 if failures else 0


def iter_srt_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.srt")):
        if path.is_file():
            yield path


def command_import_srt(args: argparse.Namespace) -> int:
    source_root = Path(args.srt_dir).expanduser().resolve()
    if not source_root.is_dir():
        print("error: SRT directory not found: %s" % source_root, file=sys.stderr)
        return 2
    subtitle_base = Path(args.subtitle_root).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser() if args.manifest else subtitle_base / "srt-import-manifest.json"
    manifest = Manifest(
        manifest_path,
        {"mode": "import-srt", "source_dir": str(source_root), "subtitle_root": str(subtitle_base)},
    )
    imported = 0
    skipped = 0
    for source in iter_srt_files(source_root):
        match = SUBTITLE_RE.match(source.name)
        if not match:
            skipped += 1
            continue
        video_id = match.group("id")
        lang = match.group("lang") or args.lang
        if args.video_id and video_id not in args.video_id:
            continue
        destination_dir = subtitle_base / lang / "subtitles"
        destination_dir.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="replace")
        try:
            vtt_text = srt_to_vtt(text)
        except ValueError as error:
            manifest.update(
                video_id,
                {
                    "status": "failed",
                    "source": str(source),
                    "language": lang,
                    "error": str(error),
                    "timestamp_utc": utc_now(),
                },
            )
            continue
        srt_target = destination_dir / (video_id + ".srt")
        vtt_target = destination_dir / (video_id + ".vtt")
        srt_target.write_text(text, encoding="utf-8")
        vtt_target.write_text(vtt_text, encoding="utf-8")
        manifest.update(
            video_id,
            {
                "status": "imported",
                "source": str(source),
                "language": lang,
                "srt": str(srt_target),
                "vtt": str(vtt_target),
                "srt_sha256": sha256_file(srt_target),
                "vtt_sha256": sha256_file(vtt_target),
                "bytes": srt_target.stat().st_size,
                "timestamp_utc": utc_now(),
            },
        )
        imported += 1
    manifest.save()
    print("imported: %d" % imported)
    print("skipped: %d" % skipped)
    print("manifest: %s" % manifest_path)
    return 0 if imported or not skipped else 1


def command_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).expanduser().resolve()
    if not manifest_path.is_file():
        print("error: manifest not found: %s" % manifest_path, file=sys.stderr)
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print("error: invalid manifest: %s" % error, file=sys.stderr)
        return 2
    videos = manifest.get("videos", {})
    if isinstance(videos, list):
        videos = {entry.get("youtube_id"): entry for entry in videos if isinstance(entry, dict)}
    if not isinstance(videos, dict):
        print("error: manifest has no videos map", file=sys.stderr)
        return 2
    ffprobe = resolve_tool(args.ffprobe, "ffprobe")
    failures = 0
    report = {"checked_utc": utc_now(), "manifest": str(manifest_path), "videos": {}}
    for video_id, entry in sorted(videos.items()):
        file_value = entry.get("file")
        if not file_value:
            continue
        path = Path(file_value).expanduser()
        check = check_media(
            path,
            ffprobe,
            parse_int(entry.get("duration_seconds")),
            max_height=parse_int(entry.get("requested_max_height")),
            prefer_mp4=(entry.get("format") != "best"),
        )
        expected = entry.get("sha256")
        if expected and check.get("sha256") and expected != check["sha256"]:
            check["errors"].append("sha256_mismatch")
        status = "ok" if not check["errors"] else "failed"
        if status == "failed":
            failures += 1
        report["videos"][video_id] = {"status": status, "check": check}
        print("%-12s %-6s %s" % (video_id, status, path))
    report["summary"] = summarize(
        {video_id: {"status": item["status"]} for video_id, item in report["videos"].items()}
    )
    if args.report:
        atomic_write_json(Path(args.report).expanduser().resolve(), report)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=TOOL_NAME, description=__doc__)
    parser.add_argument("--version", action="version", version="%(prog)s " + TOOL_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download missing MP4 videos with yt-dlp")
    download.add_argument("--index-csv", help="KA Lite khan-video-index.csv")
    download.add_argument("--video-id", action="append", help="specific 11-character video id; may be repeated")
    download.add_argument("--output", required=True, help="directory for downloaded MP4 files")
    download.add_argument("--manifest", help="manifest JSON path (default: OUTPUT/manifest.json)")
    download.add_argument("--yt-dlp", help="yt-dlp executable (default: search PATH)")
    download.add_argument("--ffprobe", help="ffprobe executable (default: search PATH)")
    download.add_argument("--ffmpeg-location", help="directory containing ffmpeg")
    download.add_argument("--format", choices=("mp4", "best"), default="mp4")
    download.add_argument("--quality", choices=("360", "480", "720", "1080", "best"), default="720")
    download.add_argument("--recode", action="store_true", help="force yt-dlp to remux/recode to MP4")
    download.add_argument("--subtitles", action="store_true", help="download English subtitles when available")
    download.add_argument("--sub-langs", default="en", help="comma-separated subtitle languages")
    download.add_argument("--subtitle-root", help="KA Lite srt directory; writes LANG/subtitles/ID.vtt")
    download.add_argument("--content-root", help="KA Lite CONTENT_ROOT; subtitle root defaults to CONTENT_ROOT/srt")
    download.add_argument("--limit", type=int, help="maximum number of videos to process")
    download.add_argument("--dry-run", action="store_true", help="write the plan and commands without downloading")
    download.add_argument("--overwrite", action="store_true", help="re-download existing files (never deletes)")
    download.add_argument("--min-bytes", type=int, default=1024)
    download.add_argument("--timeout", type=int, default=3600, help="per-video yt-dlp timeout in seconds")
    download.add_argument("--retries", type=int, default=3)
    download.add_argument("--sleep", type=float, default=0.0)
    download.add_argument("--rate-limit", help="yt-dlp rate limit, e.g. 2M")
    download.set_defaults(func=command_download)

    import_srt = subparsers.add_parser("import-srt", help="copy and convert existing SRT files for KA Lite")
    import_srt.add_argument("--srt-dir", required=True, help="directory searched recursively for *.srt")
    import_srt.add_argument("--subtitle-root", required=True, help="KA Lite srt directory")
    import_srt.add_argument("--manifest", help="manifest JSON path")
    import_srt.add_argument("--lang", default="en", help="language used for ID.srt files")
    import_srt.add_argument("--video-id", action="append", help="only import these ids")
    import_srt.set_defaults(func=command_import_srt)

    verify = subparsers.add_parser("verify", help="verify files and checksums from a manifest")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--ffprobe", help="ffprobe executable (default: search PATH)")
    verify.add_argument("--report", help="write a verification report JSON")
    verify.set_defaults(func=command_verify)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "rate_limit", None) and not RATE_LIMIT_RE.match(args.rate_limit):
        parser.error("--rate-limit must look like 500K or 2M")
    try:
        return args.func(args)
    except RecoveryError as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
