from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_pipeline


class ShotstackSmokeTests(unittest.TestCase):
    def test_smoke_render_without_adapter_does_not_call_external_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            with mock.patch.dict(os.environ, {"SHOTSTACK_MCP_RENDER_COMMAND": ""}):
                state = run_pipeline.run_shotstack_smoke_render(
                    package_dir=package_dir,
                    source_video=REPO_ROOT / "input" / "test_3.mp4",
                    renderer="shotstack",
                    smoke_config={
                        "enabled": True,
                        "mode": "render-once",
                        "limit": 1,
                    },
                )

            self.assertFalse(state["attempted"])
            self.assertEqual(state["status"], "configuration_required")
            self.assertTrue((package_dir / "shotstack_smoke_result.json").exists())
            self.assertTrue((package_dir / "shotstack_smoke_compare.json").exists())


if __name__ == "__main__":
    unittest.main()
