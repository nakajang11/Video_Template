from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import video_analysis_support as support


class VideoAnalysisSupportTests(unittest.TestCase):
    def test_build_frame_times_uses_even_interior_samples(self) -> None:
        self.assertEqual(
            support.build_frame_times(duration_sec=10.0, frame_count=4),
            [2.0, 4.0, 6.0, 8.0],
        )
        self.assertEqual(
            support.build_frame_times(duration_sec=9.0, frame_count=1),
            [4.5],
        )

    def test_compact_text_limits_large_transcript(self) -> None:
        text = " ".join(f"sentence {index}." for index in range(500))
        packed, stats = support.compact_text(text, max_chars=700)

        self.assertLessEqual(len(packed), 700)
        self.assertIn("omitted", packed)
        self.assertEqual(stats["strategy"], "head_tail_middle_omission")
        self.assertGreater(stats["omitted_chars"], 0)

    def test_load_json_transcript_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "transcript.json"
            path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {"start": 0, "end": 1.25, "text": "hello"},
                            {"start": 1.25, "end": 2.5, "text": "world"},
                        ]
                    }
                )
            )
            loaded = support.load_transcript(path)

        self.assertIn("[0.00-1.25] hello", loaded)
        self.assertIn("[1.25-2.50] world", loaded)

    def test_write_transcript_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "transcript.txt"
            output_path = Path(tmp_dir) / "transcript_packed.md"
            input_path.write_text("hello   world\n\nsecond line")
            payload = support.write_transcript_pack(
                input_path=input_path,
                output_path=output_path,
                job_id="job_123",
                max_chars=500,
            )

            output = output_path.read_text()
        self.assertEqual(payload["job_id"], "job_123")
        self.assertIn("# Packed Transcript", output)
        self.assertIn("hello world", output)


if __name__ == "__main__":
    unittest.main()
