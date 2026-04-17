from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import template_package_support as support


SHOTSTACK_VALIDATOR = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "shotstack-remix-package"
    / "scripts"
    / "validate_package.py"
)
REMOTION_VALIDATOR = REPO_ROOT / "scripts" / "validate_remotion_package.py"


def build_result_payload(
    package_dir: Path,
    *,
    renderer: str,
    caller_context_echo: dict[str, object],
    source_summary: dict[str, object],
    package_summary: dict[str, object],
) -> dict[str, object]:
    prompt_files = sorted(
        path.name
        for path in package_dir.iterdir()
        if path.is_file()
        and (
            path.name.endswith("_prompt.md")
            or path.name.endswith("_image_prompt.md")
            or path.name.endswith("_video_prompt.md")
        )
    )
    return {
        "status": "ok",
        "job_id": package_dir.name,
        "renderer": renderer,
        "review_status": "review_required",
        "package_dir": str(package_dir),
        "caller_context_echo": caller_context_echo,
        "source_summary": source_summary,
        "package_summary": package_summary,
        "artifacts": {
            "analysis": "analysis.json" if (package_dir / "analysis.json").exists() else None,
            "story": "story.json" if (package_dir / "story.json").exists() else None,
            "variable_map": "variable_map.json"
            if (package_dir / "variable_map.json").exists()
            else None,
            "blueprint": "blueprint.json" if (package_dir / "blueprint.json").exists() else None,
            "manifest": "manifest.json" if (package_dir / "manifest.json").exists() else None,
            "shotstack": "shotstack.json" if (package_dir / "shotstack.json").exists() else None,
            "remotion_package": "remotion_package"
            if (package_dir / "remotion_package").exists()
            else None,
            "source_audio": "source_audio.mp3"
            if (package_dir / "source_audio.mp3").exists()
            else None,
            "template_contract": "template_contract.json",
            "package_archive": "package.zip",
            "prompt_files": prompt_files,
        },
        "validation": {
            "passed": True,
            "errors": [],
            "warnings": [],
        },
        "notes": [],
    }


class TemplateContractTests(unittest.TestCase):
    def finalize_fixture(
        self,
        fixture_name: str,
        *,
        renderer: str,
        caller_context: dict[str, object],
    ) -> tuple[Path, dict[str, object], dict[str, object]]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        destination = Path(temp_dir.name) / fixture_name
        shutil.copytree(REPO_ROOT / "output" / fixture_name, destination)

        caller_context_echo = support.compact_caller_context(
            caller_context,
            preferred_renderer=renderer,
        )
        contract = support.build_template_contract(
            destination,
            renderer=renderer,
            caller_context=caller_context,
            caller_context_echo=caller_context_echo,
        )
        support.write_json(destination / "template_contract.json", contract)
        support.update_manifest_runtime_entries(
            destination,
            renderer=renderer,
            review_status="review_required",
            include_result=False,
            include_archive=False,
        )
        source_summary = support.build_source_summary(destination)
        result = build_result_payload(
            destination,
            renderer=renderer,
            caller_context_echo=caller_context_echo,
            source_summary=source_summary,
            package_summary=contract["package_summary"],
        )
        return destination, contract, result

    def test_shotstack_fixture_generates_contract_and_archive(self) -> None:
        package_dir, contract, result = self.finalize_fixture(
            "trend_con_3",
            renderer="shotstack",
            caller_context={
                "template_type": "A-7_trend_single",
                "source_platform": "tiktok",
                "source_trend_video_id": 321,
            },
        )
        validation = subprocess.run(
            [sys.executable, str(SHOTSTACK_VALIDATOR), str(package_dir)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.assertEqual(contract["renderer"], "shotstack")
        self.assertGreater(contract["package_summary"]["slot_count"], 0)
        self.assertEqual(contract["package_summary"], result["package_summary"])

        support.update_manifest_runtime_entries(
            package_dir,
            renderer="shotstack",
            review_status="review_required",
            include_result=True,
            include_archive=True,
        )
        support.write_json(package_dir / "result.json", result)
        archive_path = support.create_package_archive(package_dir)

        self.assertTrue(archive_path.exists())
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("template_contract.json", names)
        self.assertIn("result.json", names)
        self.assertIn("manifest.json", names)
        self.assertNotIn("package.zip", names)

    def test_remotion_fixture_generates_contract_and_archive(self) -> None:
        package_dir, contract, result = self.finalize_fixture(
            "test_3",
            renderer="remotion",
            caller_context={
                "template_type": "A-6_trend_continue",
                "source_platform": "tiktok",
                "source_trend_video_id": 909,
            },
        )
        validation = subprocess.run(
            [sys.executable, str(REMOTION_VALIDATOR), str(package_dir)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.assertEqual(contract["renderer"], "remotion")
        self.assertGreater(contract["package_summary"]["text_slot_count"], 0)
        self.assertEqual(contract["package_summary"], result["package_summary"])

        support.update_manifest_runtime_entries(
            package_dir,
            renderer="remotion",
            review_status="review_required",
            include_result=True,
            include_archive=True,
        )
        support.write_json(package_dir / "result.json", result)
        archive_path = support.create_package_archive(package_dir)

        self.assertTrue(archive_path.exists())
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("template_contract.json", names)
        self.assertIn("result.json", names)
        self.assertIn("remotion_package/src/Test3GlossaryTemplate.jsx", names)
        self.assertNotIn("remotion_package/renders/test_3_review.mp4", names)


if __name__ == "__main__":
    unittest.main()
