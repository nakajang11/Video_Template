from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import template_package_support as support


def make_hybrid_blueprint(
    *,
    inner_renderer: str = "remotion",
    duration_sec: float = 3.0,
    precompose_duration_sec: float = 3.0,
    audio_policy: str = "mute",
    include_shotstack: bool = True,
) -> dict[str, object]:
    scene: dict[str, object] = {
        "scene_id": "scene_001",
        "duration_sec": duration_sec,
        "story_role": "code-driven opener",
        "cast": [],
        "locks": [],
        "variables": [],
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
        "precompose": {
            "renderer": inner_renderer,
            "output_merge_key": "SCENE_001_PRECOMP_VIDEO",
            "package_dir": f"precompose/scene_001/{inner_renderer}",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "duration_sec": precompose_duration_sec,
            "audio_policy": audio_policy,
            "status": "package_created",
        },
    }
    if include_shotstack:
        scene["shotstack"] = {
            "asset_type": "video",
            "alias": "SCENE_001",
            "merge_key": "SCENE_001_PRECOMP_VIDEO",
            "clip_length_sec": duration_sec,
            "text_overlays": [],
            "overlay_layers": [],
        }

    return {
        "contract_version": "1.1",
        "job_id": "hybrid_demo",
        "source_video": "input/hybrid_demo.mp4",
        "renderer": "hybrid",
        "audio": {
            "strategy": "use_input_audio",
            "source_file": "source_audio.mp3",
            "shotstack_merge_key": "SOURCE_AUDIO_MP3",
        },
        "review_status": "review_required",
        "scene_order": ["scene_001"],
        "scenes": [scene],
    }


class HybridContractTests(unittest.TestCase):
    def test_blueprint_schema_declares_hybrid_precompose_shape(self) -> None:
        schema = json.loads(
            (REPO_ROOT / ".agents/skills/trend-short-blueprint/assets/blueprint.schema.json").read_text()
        )
        self.assertIn("hybrid", schema["properties"]["renderer"]["enum"])
        self.assertIn("hyperframes", schema["properties"]["renderer"]["enum"])
        scene_properties = schema["properties"]["scenes"]["items"]["properties"]
        self.assertIn("precompose", scene_properties)
        precompose = scene_properties["precompose"]
        self.assertEqual(precompose["properties"]["renderer"]["enum"], ["remotion", "hyperframes"])
        self.assertIn("output_merge_key", precompose["required"])
        self.assertIn("audio_policy", precompose["required"])
        self.assertIn("blocked", precompose["properties"]["status"]["enum"])

    def test_validates_remotion_and_hyperframes_precompose(self) -> None:
        for inner_renderer in ("remotion", "hyperframes"):
            with self.subTest(inner_renderer=inner_renderer):
                blueprint = make_hybrid_blueprint(inner_renderer=inner_renderer)
                errors, warnings = support.validate_hybrid_precompose_blueprint(blueprint)
                self.assertEqual(errors, [])
                self.assertEqual(warnings, [])

    def test_rejects_hybrid_scene_without_shotstack_binding(self) -> None:
        blueprint = make_hybrid_blueprint(include_shotstack=False)
        errors, _ = support.validate_hybrid_precompose_blueprint(blueprint)
        self.assertIn("scene_001: hybrid scenes require shotstack final assembly binding", errors)

    def test_rejects_precompose_duration_mismatch(self) -> None:
        blueprint = make_hybrid_blueprint(precompose_duration_sec=4.0)
        errors, _ = support.validate_hybrid_precompose_blueprint(blueprint)
        self.assertIn("scene_001: precompose.duration_sec must match duration_sec", errors)

    def test_rejects_invalid_precompose_audio_policy(self) -> None:
        blueprint = make_hybrid_blueprint(audio_policy="preserve")
        errors, _ = support.validate_hybrid_precompose_blueprint(blueprint)
        self.assertIn("scene_001: precompose.audio_policy must be `mute` or `strip`", errors)

    def test_hybrid_template_contract_uses_shotstack_merge_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            support.write_json(package_dir / "blueprint.json", make_hybrid_blueprint())
            contract = support.build_template_contract(
                package_dir,
                renderer="hybrid",
                caller_context={"template_type": "A-7_trend_single"},
                caller_context_echo=support.compact_caller_context(
                    {"template_type": "A-7_trend_single"},
                    preferred_renderer="hybrid",
                ),
            )
            support.write_json(package_dir / "template_contract.json", contract)
            contract_errors, contract_warnings, _ = support.validate_template_contract(
                package_dir,
                expected_renderer="hybrid",
            )
        self.assertEqual(contract["renderer"], "hybrid")
        self.assertEqual(contract["contract_version"], "1.2")
        self.assertEqual(contract_errors, [])
        self.assertEqual(contract_warnings, [])
        self.assertTrue(contract["precompose_required"])
        self.assertEqual(contract["precompose_plan"]["steps"][0]["status"], "package_created")
        self.assertTrue(contract["precompose_plan"]["steps"][0]["blockers"])
        media_slots = [slot for slot in contract["slots"] if slot["kind"] == "media"]
        self.assertEqual(len(media_slots), 1)
        media_slot = media_slots[0]
        self.assertEqual(media_slot["fill_strategy"], "precompose_video")
        self.assertEqual(
            media_slot["renderer_binding"]["merge_key"],
            "SCENE_001_PRECOMP_VIDEO",
        )
        self.assertEqual(
            media_slot["renderer_binding"]["precompose"]["renderer"],
            "remotion",
        )


if __name__ == "__main__":
    unittest.main()
