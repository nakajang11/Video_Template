from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import template_package_support as support


ADULT_PROFILE = "adult_ai_influencer_media_template"


class AssemblyFlowSuggestionTests(unittest.TestCase):
    def make_package(self) -> tuple[Path, dict[str, object], dict[str, object]]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        destination = Path(temp_dir.name) / "trend_con_3"
        shutil.copytree(REPO_ROOT / "output" / "trend_con_3", destination)

        caller_context = {
            "template_type": "A-6_trend_continue",
            "consumer_profile": ADULT_PROFILE,
            "assembly_contract": {
                "schema_version": "adult_ai_influencer_assembly_contract.v1"
            },
        }
        caller_context_echo = support.compact_caller_context(
            caller_context,
            preferred_renderer="shotstack",
        )
        template_contract = support.build_template_contract(
            destination,
            renderer="shotstack",
            caller_context=caller_context,
            caller_context_echo=caller_context_echo,
        )
        support.write_json(destination / "template_contract.json", template_contract)
        support.update_manifest_runtime_entries(
            destination,
            renderer="shotstack",
            review_status="review_required",
            include_result=False,
            include_archive=False,
        )
        return destination, caller_context, template_contract

    def test_default_profile_does_not_generate_suggestion(self) -> None:
        package_dir, caller_context, template_contract = self.make_package()

        state = support.maybe_write_assembly_flow_suggestion(
            package_dir,
            consumer_profile=None,
            caller_context=caller_context,
            caller_context_echo=support.compact_caller_context(caller_context),
            template_contract=template_contract,
        )

        self.assertFalse(state["requested"])
        self.assertFalse(state["created"])
        self.assertFalse((package_dir / "assembly_flow_suggestion.json").exists())

    def test_adult_profile_generates_manifest_and_archive_artifact(self) -> None:
        package_dir, caller_context, template_contract = self.make_package()
        caller_context_echo = support.compact_caller_context(caller_context)

        state = support.maybe_write_assembly_flow_suggestion(
            package_dir,
            consumer_profile=ADULT_PROFILE,
            caller_context=caller_context,
            caller_context_echo=caller_context_echo,
            template_contract=template_contract,
        )
        support.write_json(package_dir / "result.json", {"status": "ok"})
        support.update_manifest_runtime_entries(
            package_dir,
            renderer="shotstack",
            review_status="review_required",
            include_result=True,
            include_archive=True,
        )
        archive_path = support.create_package_archive(package_dir)

        self.assertTrue(state["created"], state)
        payload = json.loads((package_dir / "assembly_flow_suggestion.json").read_text())
        errors, warnings = support.validate_assembly_flow_suggestion(payload)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(payload["consumer_profile"], ADULT_PROFILE)
        self.assertEqual(payload["template_type"], "A-6_trend_continue")
        self.assertIn(
            {
                "scene_id": "scene_001",
                "source_role": "source_start_frame",
                "token": "{{source_scene_001.start_frame_url}}",
            },
            payload["source_scene_bindings"],
        )

        manifest = json.loads((package_dir / "manifest.json").read_text())
        self.assertIn(
            {
                "type": "assembly_flow_suggestion",
                "path": "assembly_flow_suggestion.json",
                "scene_id": None,
                "status": "created",
            },
            manifest["artifacts"],
        )
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("assembly_flow_suggestion.json", names)

    def test_validator_rejects_resolved_url_local_path_and_provider_results(self) -> None:
        package_dir, caller_context, template_contract = self.make_package()
        payload = support.build_assembly_flow_suggestion(
            package_dir,
            consumer_profile=ADULT_PROFILE,
            caller_context=caller_context,
            caller_context_echo=support.compact_caller_context(caller_context),
            template_contract=template_contract,
        )
        self.assertIsNotNone(payload)

        with_url = copy.deepcopy(payload)
        with_url["suggested_flow"]["steps"][1]["tool_inputs"]["image_urls"][0] = (
            "https://res.cloudinary.com/example/image/upload/source.jpg"
        )
        errors, _ = support.validate_assembly_flow_suggestion(with_url)
        self.assertTrue(any("resolved URL" in error for error in errors), errors)

        with_local_path = copy.deepcopy(payload)
        with_local_path["suggested_flow"]["steps"][1]["tool_inputs"]["image_urls"][0] = (
            "/Users/example/source.jpg"
        )
        errors, _ = support.validate_assembly_flow_suggestion(with_local_path)
        self.assertTrue(any("local absolute path" in error for error in errors), errors)

        with_provider_result = copy.deepcopy(payload)
        with_provider_result["suggested_flow"]["steps"][1]["provider_result"] = {
            "id": "generated-image-123"
        }
        errors, _ = support.validate_assembly_flow_suggestion(with_provider_result)
        self.assertTrue(any("forbidden provider/result key" in error for error in errors), errors)

        with_generated_url = copy.deepcopy(payload)
        with_generated_url["suggested_flow"]["steps"][1]["generated_url"] = (
            "{{image_generate.output.image_url}}"
        )
        errors, _ = support.validate_assembly_flow_suggestion(with_generated_url)
        self.assertTrue(any("forbidden provider/result key" in error for error in errors), errors)

    def test_validator_rejects_unsupported_step_target(self) -> None:
        package_dir, caller_context, template_contract = self.make_package()
        payload = support.build_assembly_flow_suggestion(
            package_dir,
            consumer_profile=ADULT_PROFILE,
            caller_context=caller_context,
            caller_context_echo=support.compact_caller_context(caller_context),
            template_contract=template_contract,
        )
        self.assertIsNotNone(payload)
        payload["suggested_flow"]["steps"][0]["target"] = "database_write"

        errors, _ = support.validate_assembly_flow_suggestion(payload)

        self.assertTrue(any("unsupported target" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
