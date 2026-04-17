from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import template_package_support as support
import validate_remotion_package as validator


class RemotionValidatorTests(unittest.TestCase):
    def make_valid_package(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        package_dir = Path(temp_dir.name) / "test_3"
        shutil.copytree(
            REPO_ROOT / "output" / "test_3",
            package_dir,
            ignore=shutil.ignore_patterns("node_modules", ".DS_Store", "renders"),
        )
        caller_context = {
            "template_type": "A-6_trend_continue",
            "source_platform": "tiktok",
            "source_trend_video_id": 909,
        }
        caller_context_echo = support.compact_caller_context(
            caller_context,
            preferred_renderer="remotion",
        )
        contract = support.build_template_contract(
            package_dir,
            renderer="remotion",
            caller_context=caller_context,
            caller_context_echo=caller_context_echo,
        )
        support.write_json(package_dir / "template_contract.json", contract)
        support.update_manifest_runtime_entries(
            package_dir,
            renderer="remotion",
            review_status="review_required",
        )
        return package_dir

    def test_canonical_remotion_package_passes_static_validation(self) -> None:
        package_dir = self.make_valid_package()
        errors, warnings = validator.validate_package(package_dir)
        self.assertEqual(errors, [])
        self.assertTrue(any("renders" in warning for warning in warnings))

    def test_missing_editable_prop_path_fails(self) -> None:
        package_dir = self.make_valid_package()
        blueprint_path = package_dir / "blueprint.json"
        blueprint = json.loads(blueprint_path.read_text())
        blueprint["remotion_package"]["editable_props"].append("cloud.missingCopy")
        blueprint_path.write_text(json.dumps(blueprint, indent=2))

        errors, _ = validator.validate_package(package_dir)
        self.assertIn(
            "Editable Remotion prop path is missing from default-props.json: cloud.missingCopy",
            errors,
        )

    def test_missing_local_media_asset_fails(self) -> None:
        package_dir = self.make_valid_package()
        (package_dir / "remotion_package" / "public" / "assets" / "scene_001_dictionary_plate.png").unlink()

        errors, _ = validator.validate_package(package_dir)
        self.assertIn(
            "Local Remotion asset is missing for mediaInputs.introBackground.src: public/assets/scene_001_dictionary_plate.png",
            errors,
        )

    def test_composition_id_mismatch_fails(self) -> None:
        package_dir = self.make_valid_package()
        root_path = package_dir / "remotion_package" / "src" / "Root.jsx"
        root_path.write_text(root_path.read_text().replace('id="Test3GlossaryTemplate"', 'id="WrongTemplate"'))

        errors, _ = validator.validate_package(package_dir)
        self.assertIn(
            "Root.jsx Composition id `WrongTemplate` does not match blueprint composition_id `Test3GlossaryTemplate`.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
