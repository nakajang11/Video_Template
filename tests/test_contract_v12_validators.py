from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import template_package_support as support


TEMPLATE_VALIDATOR = REPO_ROOT / "scripts" / "validate_template_contract.py"
ADULT_VALIDATOR = REPO_ROOT / "scripts" / "validate_adult_ai_consumer_contract.py"
HYPERFRAMES_VALIDATOR = REPO_ROOT / "scripts" / "validate_hyperframes_package.py"


class ContractV12ValidatorTests(unittest.TestCase):
    def make_hyperframes_package(self) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, object]]:
        temp_dir = tempfile.TemporaryDirectory()
        package_dir = Path(temp_dir.name) / "hyperframes_basic"
        hyperframes_dir = package_dir / "hyperframes_package"
        (hyperframes_dir / "assets").mkdir(parents=True)
        support.write_json(
            package_dir / "analysis.json",
            {
                "source_video": "input/hyperframes_basic.mp4",
                "media": {"duration_sec": 3.0, "width": 1080, "height": 1920},
                "scenes": [{"scene_id": "scene_001", "duration_sec": 3.0}],
            },
        )
        support.write_json(package_dir / "story.json", {"global_plot": "kinetic title card"})
        support.write_json(package_dir / "variable_map.json", {"variables": []})
        support.write_json(
            package_dir / "blueprint.json",
            {
                "contract_version": "1.2",
                "job_id": "hyperframes_basic",
                "source_video": "input/hyperframes_basic.mp4",
                "renderer": "hyperframes",
                "audio": {
                    "strategy": "use_input_audio",
                    "source_file": "source_audio.mp3",
                    "shotstack_merge_key": "SOURCE_AUDIO_MP3",
                },
                "review_status": "review_required",
                "scene_order": ["scene_001"],
                "hyperframes_package": {
                    "package_dir": "hyperframes_package",
                    "entry_file": "hyperframes_package/index.html",
                    "composition_id": "HyperframesBasic",
                    "manifest_file": "hyperframes_package/meta.json",
                    "graph_file": "hyperframes_package/template-partition.json",
                    "editable_props": ["title", "background"],
                    "slot_bindings": [
                        {
                            "slot_id": "scene_001.text.title",
                            "scene_id": "scene_001",
                            "kind": "text",
                            "graph_ref": "nodes.title.text",
                            "fill_strategy": "generate_text",
                        },
                        {
                            "slot_id": "scene_001.media.background",
                            "scene_id": "scene_001",
                            "kind": "media",
                            "media_kind": "image",
                            "graph_ref": "nodes.background.src",
                            "fill_strategy": "select_existing_asset",
                        },
                    ],
                },
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "duration_sec": 3.0,
                        "story_role": "kinetic title card",
                        "cast": [],
                        "locks": [],
                        "variables": ["title"],
                        "startframe": {
                            "required": False,
                            "model": None,
                            "prompt_file": None,
                            "reference_assets": [],
                        },
                        "video": {
                            "mode": "code-driven",
                            "model": None,
                            "prompt_file": None,
                            "reference_assets": [],
                        },
                    }
                ],
            },
        )
        support.write_json(
            package_dir / "manifest.json",
            {
                "job_id": "hyperframes_basic",
                "renderer": "hyperframes",
                "review_status": "review_required",
                "artifacts": [
                    {"type": "analysis", "path": "analysis.json", "scene_id": None, "status": "created"},
                    {"type": "story", "path": "story.json", "scene_id": None, "status": "created"},
                    {"type": "variable_map", "path": "variable_map.json", "scene_id": None, "status": "created"},
                    {"type": "blueprint", "path": "blueprint.json", "scene_id": None, "status": "created"},
                    {"type": "hyperframes_package", "path": "hyperframes_package", "scene_id": None, "status": "created"},
                ],
            },
        )
        (package_dir / "source_audio.mp3").write_text("placeholder audio")
        (hyperframes_dir / "README.md").write_text("Static review package. Rendering is review-gated.\n")
        support.write_json(hyperframes_dir / "package.json", {"scripts": {"validate": "echo static"}})
        support.write_json(
            hyperframes_dir / "meta.json",
            {
                "composition_id": "HyperframesBasic",
                "width": 1080,
                "height": 1920,
                "fps": 30,
                "duration_sec": 3.0,
                "render_status": "not_rendered",
            },
        )
        support.write_json(
            hyperframes_dir / "template-partition.json",
            {
                "editable_slots": [
                    {"slot_id": "scene_001.text.title", "graph_ref": "nodes.title.text"},
                    {"slot_id": "scene_001.media.background", "graph_ref": "nodes.background.src"},
                ]
            },
        )
        (hyperframes_dir / "index.html").write_text(
            '<main data-composition-id="HyperframesBasic"><h1 data-slot="title">Title</h1></main>\n'
        )
        (hyperframes_dir / "assets" / "placeholder.txt").write_text("token placeholder\n")

        caller_context = {"template_type": "A-7_trend_single"}
        caller_context_echo = support.compact_caller_context(
            caller_context,
            preferred_renderer="hyperframes",
        )
        contract = support.build_template_contract(
            package_dir,
            renderer="hyperframes",
            caller_context=caller_context,
            caller_context_echo=caller_context_echo,
        )
        support.write_json(package_dir / "template_contract.json", contract)
        support.update_manifest_runtime_entries(
            package_dir,
            renderer="hyperframes",
            review_status="review_required",
            include_result=False,
            include_archive=True,
        )
        support.write_json(package_dir / "result.json", {"status": "ok"})
        support.create_package_archive(package_dir)
        return temp_dir, package_dir, contract

    def test_hyperframes_package_and_contract_validate(self) -> None:
        temp_dir, package_dir, contract = self.make_hyperframes_package()
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(contract["renderer"], "hyperframes")
        self.assertEqual(contract["contract_version"], "1.2")
        self.assertTrue(all("graph_ref" in slot["renderer_binding"] for slot in contract["slots"]))
        for validator in (TEMPLATE_VALIDATOR, HYPERFRAMES_VALIDATOR):
            completed = subprocess.run(
                [sys.executable, str(validator), str(package_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_template_validator_rejects_hyperframes_as_generation_model(self) -> None:
        temp_dir, package_dir, contract = self.make_hyperframes_package()
        self.addCleanup(temp_dir.cleanup)
        contract["slots"][0]["generation_policy"]["model_route"] = "hyperframes"
        support.write_json(package_dir / "template_contract.json", contract)

        completed = subprocess.run(
            [sys.executable, str(TEMPLATE_VALIDATOR), str(package_dir)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("must not use Hyperframes as a generation model", completed.stdout)

    def test_template_validator_scans_archive_payload_for_leaks(self) -> None:
        temp_dir, package_dir, _ = self.make_hyperframes_package()
        self.addCleanup(temp_dir.cleanup)
        with zipfile.ZipFile(package_dir / "package.zip", "a") as archive:
            archive.writestr(
                "notes/safe_name.json",
                '{"provider_response":{"url":"https://example.invalid/render.mp4"}}',
            )

        completed = subprocess.run(
            [sys.executable, str(TEMPLATE_VALIDATOR), str(package_dir)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("forbidden payload marker `provider_response`", completed.stdout)
        self.assertIn("resolved URL content", completed.stdout)

    def test_adult_consumer_contract_rejects_url_leak(self) -> None:
        temp_dir, package_dir, contract = self.make_hyperframes_package()
        self.addCleanup(temp_dir.cleanup)
        state = support.maybe_write_adult_ai_template_contract(
            package_dir,
            consumer_profile="adult_ai_influencer_template",
            template_contract=contract,
        )
        self.assertTrue(state["created"], state)
        payload = json.loads((package_dir / "adult_ai_influencer_template_contract.json").read_text())
        payload["slots"][0]["renderer_binding"]["resolved_url"] = "https://example.invalid/output.mp4"
        support.write_json(package_dir / "adult_ai_influencer_template_contract.json", payload)

        completed = subprocess.run(
            [sys.executable, str(ADULT_VALIDATOR), str(package_dir)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("forbidden key", completed.stdout)
        self.assertIn("resolved URL", completed.stdout)


if __name__ == "__main__":
    unittest.main()
