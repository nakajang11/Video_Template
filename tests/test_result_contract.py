from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_pipeline


class ResultContractTests(unittest.TestCase):
    def test_schema_contains_v3_fields(self) -> None:
        schema = json.loads((REPO_ROOT / "schemas" / "run_result.schema.json").read_text())
        self.assertIn("caller_context_echo", schema["required"])
        self.assertIn("source_summary", schema["required"])
        self.assertIn("package_summary", schema["required"])
        artifact_properties = schema["properties"]["artifacts"]["properties"]
        self.assertIn("template_contract", artifact_properties)
        self.assertIn("package_archive", artifact_properties)
        self.assertIn("shotstack_smoke_result", artifact_properties)
        self.assertIn("shotstack_smoke", schema["properties"])
        self.assertFalse(schema["properties"]["caller_context_echo"]["additionalProperties"])

    def test_fallback_result_includes_v3_fields(self) -> None:
        payload = run_pipeline.build_fallback_result(
            status="input_error",
            job_id="job_123",
            renderer="unknown",
            package_dir=REPO_ROOT / "output" / "job_123",
            notes=["failure"],
            preferred_renderer="shotstack",
        )
        self.assertIn("caller_context_echo", payload)
        self.assertIn("source_summary", payload)
        self.assertIn("package_summary", payload)
        self.assertEqual(payload["caller_context_echo"]["preferred_renderer"], "shotstack")
        self.assertIn("template_contract", payload["artifacts"])
        self.assertIn("package_archive", payload["artifacts"])
        self.assertIn("shotstack_smoke_result", payload["artifacts"])
        self.assertEqual(payload["shotstack_smoke"]["status"], "not_requested")


if __name__ == "__main__":
    unittest.main()
