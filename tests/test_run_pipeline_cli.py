from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PIPELINE = REPO_ROOT / "scripts" / "run_pipeline.py"


class RunPipelineCliTests(unittest.TestCase):
    def run_pipeline(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUN_PIPELINE), *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_backward_compatible_dry_run(self) -> None:
        completed = self.run_pipeline(
            "--input-video",
            "input/test_3.mp4",
            "--job-id",
            "smoke_old",
            "--dry-run",
            "--result-json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "dry_run")
        self.assertEqual(payload["preferred_renderer"], "auto")
        self.assertEqual(payload["caller_context_echo"]["preferred_renderer"], "auto")
        self.assertIn("command", payload)
        self.assertIn("prompt_preview", payload)

    def test_dry_run_with_preferred_renderer_and_context(self) -> None:
        completed = self.run_pipeline(
            "--input-video",
            "input/test_3.mp4",
            "--job-id",
            "smoke_context",
            "--preferred-renderer",
            "remotion",
            "--context-inline-json",
            json.dumps(
                {
                    "template_type": "A-7_trend_single",
                    "source_platform": "tiktok",
                    "source_trend_video_id": 123,
                    "step1_json": {"hook": "bold opener", "background": "warm room"},
                    "step2_json": {"caption": "short payoff"},
                    "notes": "Operator note that should be compacted.",
                }
            ),
            "--dry-run",
            "--result-json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        echo = payload["caller_context_echo"]
        self.assertEqual(payload["preferred_renderer"], "remotion")
        self.assertEqual(echo["template_type"], "A-7_trend_single")
        self.assertEqual(echo["source_platform"], "tiktok")
        self.assertEqual(echo["source_trend_video_id"], 123)
        self.assertEqual(echo["preferred_renderer"], "remotion")
        self.assertIsInstance(echo["step1_hint_summary"], str)
        self.assertIsInstance(echo["step2_hint_summary"], str)
        self.assertIn("Preferred renderer from the caller: `remotion`.", payload["prompt_preview"])

    def test_duplicate_context_inputs_return_input_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context_path = Path(tmp_dir) / "context.json"
            context_path.write_text(json.dumps({"template_type": "A-7_trend_single"}))
            completed = self.run_pipeline(
                "--input-video",
                "input/test_3.mp4",
                "--job-id",
                "smoke_dupe_context",
                "--context-json",
                str(context_path),
                "--context-inline-json",
                json.dumps({"template_type": "A-6_trend_continue"}),
                "--result-json",
            )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "input_error")
        self.assertIn("context", payload["notes"][0].lower())
        self.assertIn("template_contract", payload["artifacts"])
        self.assertIn("package_archive", payload["artifacts"])
        self.assertIn("caller_context_echo", payload)
        self.assertIn("source_summary", payload)
        self.assertIn("package_summary", payload)


if __name__ == "__main__":
    unittest.main()
