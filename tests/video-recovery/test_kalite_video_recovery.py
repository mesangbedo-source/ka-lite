import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2] / "tools" / "video-recovery"
sys.path.insert(0, str(ROOT))

import kalite_video_recovery as kvr


VALID_ID = "abcdefghijk"


class ValidationTests(unittest.TestCase):
    def test_valid_video_id(self):
        self.assertTrue(kvr.valid_video_id(VALID_ID))
        self.assertTrue(kvr.valid_video_id("ABC_def-123"))

    def test_invalid_video_ids(self):
        for value in ["", "short", "abcdefghijkl", "../abcdefghijk", "abcdefghij/"]:
            self.assertFalse(kvr.valid_video_id(value), value)

    def test_youtube_url(self):
        self.assertEqual(kvr.youtube_url(VALID_ID), "https://www.youtube.com/watch?v=" + VALID_ID)
        with self.assertRaises(ValueError):
            kvr.youtube_url("bad")

    def test_video_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(kvr.video_path(root, VALID_ID), (root / (VALID_ID + ".mp4")).resolve())
            with self.assertRaises(ValueError):
                kvr.video_path(root, "../escape")


class SubtitleTests(unittest.TestCase):
    def test_srt_to_vtt(self):
        source = "1\n00:00:01,000 --> 00:00:02,500\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n"
        output = kvr.srt_to_vtt(source)
        self.assertTrue(output.startswith("WEBVTT\n"))
        self.assertIn("00:00:01.000 --> 00:00:02.500", output)
        self.assertIn("Hello", output)
        self.assertNotIn("\n1\n00:00:01,000", output)

    def test_srt_to_vtt_invalid(self):
        with self.assertRaises(ValueError):
            kvr.srt_to_vtt("")
        with self.assertRaises(ValueError):
            kvr.srt_to_vtt("not an srt")


class IndexTests(unittest.TestCase):
    def test_load_index_deduplicates_and_skips_invalid_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "index.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["youtube_id", "title", "topic_path", "duration_seconds", "remote_size_bytes"])
                writer.writerow([VALID_ID, "First title", "khan/math/", "120", "12345"])
                writer.writerow([VALID_ID, "Duplicate title", "khan/math/", "120", "12345"])
                writer.writerow(["short", "Invalid", "khan/math/", "10", "10"])
                writer.writerow(["", "Empty", "", "", ""])
            records, metadata = kvr.load_index(path)
            self.assertEqual(list(records), [VALID_ID])
            self.assertEqual(records[VALID_ID]["title"], "First title")
            self.assertEqual(records[VALID_ID]["duration_seconds"], 120)
            self.assertEqual(metadata["valid_ids"], 1)
            self.assertEqual(metadata["skipped_rows"], 2)
            self.assertEqual(metadata["duplicate_rows"], 1)


class ManifestTests(unittest.TestCase):
    def test_roundtrip_and_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            manifest = kvr.Manifest(path, {"mode": "download"})
            manifest.update(VALID_ID, {"status": "downloaded", "bytes": 42})
            manifest.save()
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], kvr.MANIFEST_SCHEMA)
            self.assertEqual(payload["summary"]["total"], 1)
            self.assertEqual(payload["summary"]["by_status"]["downloaded"], 1)
            reloaded = kvr.Manifest(path, {"mode": "download"})
            reloaded.update(VALID_ID, {"status": "verified"})
            reloaded.save()
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["videos"][VALID_ID]["status"], "verified")
            self.assertEqual(payload["videos"][VALID_ID]["bytes"], 42)


class MediaTests(unittest.TestCase):
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            check = kvr.check_media(Path(temporary) / "missing.mp4", None, None)
            self.assertIn("file_missing", check["errors"])

    def test_zero_byte_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "empty.mp4"
            path.write_bytes(b"")
            check = kvr.check_media(path, None, None)
            self.assertIn("zero_bytes", check["errors"])

    def test_nonempty_file_without_ffprobe(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "video.mp4"
            path.write_bytes(b"x" * 2048)
            check = kvr.check_media(path, None, None)
            self.assertTrue(check["readable"])
            self.assertEqual(check["bytes"], 2048)
            self.assertEqual(len(check["sha256"]), 64)
            self.assertIn("ffprobe_unavailable", check["warnings"])
            self.assertEqual(check["errors"], [])

    def test_ffprobe_stream_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "video.mp4"
            path.write_bytes(b"x" * 2048)
            payload = {
                "format": {"duration": "120.0", "size": "2048"},
                "streams": [
                    {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "avg_frame_rate": "30/1"},
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
            }
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            with patch("kalite_video_recovery.subprocess.run", return_value=completed):
                check = kvr.check_media(path, "/usr/bin/ffprobe", 120, max_height=720, prefer_mp4=True)
            self.assertEqual(check["video"]["height"], 720)
            self.assertEqual(check["video"]["codec"], "h264")
            self.assertEqual(check["audio"]["codec"], "aac")
            self.assertEqual(check["warnings"], [])

    def test_ffprobe_warns_when_quality_exceeds_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "video.mp4"
            path.write_bytes(b"x" * 2048)
            payload = {
                "format": {"duration": "120.0", "size": "2048"},
                "streams": [
                    {"codec_type": "video", "codec_name": "vp9", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"},
                    {"codec_type": "audio", "codec_name": "opus"},
                ],
            }
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            with patch("kalite_video_recovery.subprocess.run", return_value=completed):
                check = kvr.check_media(path, "/usr/bin/ffprobe", 120, max_height=720, prefer_mp4=True)
            self.assertIn("quality_exceeds_requested: 720p requested, got 1080p", check["warnings"])
            self.assertIn("video_codec_not_h264: vp9", check["warnings"])
            self.assertIn("audio_codec_not_aac: opus", check["warnings"])


class CommandTests(unittest.TestCase):
    def test_build_download_command(self):
        args = SimpleNamespace(
            format="mp4",
            quality="720",
            overwrite=False,
            retries=4,
            recode=False,
            ffmpeg_location=None,
            rate_limit="2M",
            subtitles=True,
            sub_langs="en",
        )
        with tempfile.TemporaryDirectory() as temporary:
            command = kvr.build_download_command("/usr/bin/yt-dlp", VALID_ID, Path(temporary), args)
        self.assertIn("--merge-output-format", command)
        self.assertIn("mp4", command)
        self.assertIn("height<=720", " ".join(command))
        self.assertIn("--limit-rate", command)
        self.assertIn("--write-auto-subs", command)
        self.assertEqual(command[-1], kvr.youtube_url(VALID_ID))
        self.assertNotIn("--recode-video", command)

    def test_quality_profiles(self):
        self.assertIn("height<=360", kvr.format_selector("mp4", "360"))
        self.assertIn("height<=480", kvr.format_selector("mp4", "480"))
        self.assertIn("height<=720", kvr.format_selector("mp4", "720"))
        self.assertIn("height<=1080", kvr.format_selector("mp4", "1080"))
        self.assertEqual(kvr.format_selector("best", "best"), kvr.BEST_FORMAT)
        self.assertEqual(kvr.format_selector("mp4", "best"), kvr.MP4_FORMAT)

    def test_dry_run_writes_plan_without_downloading(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "videos"
            with redirect_stdout(io.StringIO()):
                code = kvr.main(
                    ["download", "--video-id", VALID_ID, "--output", str(output), "--dry-run"]
                )
            self.assertEqual(code, 0)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["videos"][VALID_ID]["status"], "planned")
            self.assertFalse((output / (VALID_ID + ".mp4")).exists())

    def test_missing_ytdlp_fails_gracefully(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "videos"
            with patch("kalite_video_recovery.shutil.which", return_value=None):
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    code = kvr.main(["download", "--video-id", VALID_ID, "--output", str(output)])
            self.assertEqual(code, 1)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["videos"][VALID_ID]["status"], "failed")
            self.assertEqual(manifest["videos"][VALID_ID]["error"], "yt-dlp_not_found")

    def test_existing_file_is_skipped_without_ytdlp(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "videos"
            output.mkdir()
            (output / (VALID_ID + ".mp4")).write_bytes(b"x" * 2048)
            with patch("kalite_video_recovery.shutil.which", return_value=None):
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    code = kvr.main(["download", "--video-id", VALID_ID, "--output", str(output)])
            self.assertEqual(code, 0)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["videos"][VALID_ID]["status"], "skipped_existing")

    def test_import_srt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / (VALID_ID + ".en.srt")).write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8"
            )
            subtitle_root = root / "srt"
            with redirect_stdout(io.StringIO()):
                code = kvr.main(
                    ["import-srt", "--srt-dir", str(source), "--subtitle-root", str(subtitle_root)]
                )
            self.assertEqual(code, 0)
            vtt = subtitle_root / "en" / "subtitles" / (VALID_ID + ".vtt")
            self.assertTrue(vtt.is_file())
            self.assertTrue(vtt.read_text(encoding="utf-8").startswith("WEBVTT"))
            self.assertTrue((subtitle_root / "srt-import-manifest.json").is_file())

    def test_verify_manifest_detects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / (VALID_ID + ".mp4")
            video.write_bytes(b"x" * 2048)
            manifest_path = root / "manifest.json"
            manifest = kvr.Manifest(manifest_path, {"mode": "download"})
            manifest.update(
                VALID_ID,
                {
                    "status": "downloaded",
                    "file": str(video),
                    "bytes": 2048,
                    "sha256": kvr.sha256_file(video),
                },
            )
            manifest.save()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kvr.main(["verify", "--manifest", str(manifest_path)]), 0)
            video.write_bytes(b"y" * 2048)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kvr.main(["verify", "--manifest", str(manifest_path)]), 1)


if __name__ == "__main__":
    unittest.main()
