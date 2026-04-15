from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "shotstack-remix-package"
    / "scripts"
    / "validate_package.py"
)

spec = importlib.util.spec_from_file_location("shotstack_validate_package", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


def make_payload(asset: dict, fonts: list[dict] | None = None) -> dict:
    timeline: dict = {
        "tracks": [
            {
                "clips": [
                    {
                        "asset": asset,
                        "start": 0,
                        "length": 1,
                    }
                ]
            }
        ]
    }
    if fonts is not None:
        timeline["fonts"] = fonts
    return {"timeline": timeline}


class ShotstackTextValidationTests(unittest.TestCase):
    def collect_errors(self, payload: dict) -> list[str]:
        errors: list[str] = []
        validator.validate_text_assets(payload, errors, "shotstack.json")
        return errors

    def test_24019_style_text_asset_fails_before_render(self) -> None:
        errors = self.collect_errors(
            make_payload(
                {
                    "type": "text",
                    "text": "{{ SCENE_001_HOOK_TEXT }}",
                    "font": "Montserrat ExtraBold",
                    "color": "#ffffff",
                    "size": 90,
                    "stroke": "#222222",
                    "strokeWidth": 8,
                }
            )
        )
        joined = "\n".join(errors)
        self.assertIn("asset.font must be an object", joined)
        self.assertIn("asset.stroke must be an object", joined)
        self.assertIn("asset.strokeWidth is unsupported", joined)
        self.assertIn("asset.size is unsupported", joined)
        self.assertIn("asset.color is unsupported", joined)

    def test_corrected_legacy_text_asset_passes(self) -> None:
        errors = self.collect_errors(
            make_payload(
                {
                    "type": "text",
                    "text": "{{ SCENE_001_HOOK_TEXT }}",
                    "font": {
                        "family": "Montserrat",
                        "size": 90,
                        "color": "#ffffff",
                        "weight": 900,
                    },
                    "stroke": {
                        "color": "#222222",
                        "width": 8,
                    },
                }
            )
        )
        self.assertEqual(errors, [])

    def test_preferred_rich_text_asset_passes(self) -> None:
        errors = self.collect_errors(
            make_payload(
                {
                    "type": "rich-text",
                    "text": "{{ SCENE_001_HOOK_TEXT }}",
                    "font": {
                        "family": "Montserrat",
                        "size": 90,
                        "color": "#ffffff",
                        "weight": 900,
                    },
                    "stroke": {
                        "color": "#222222",
                        "width": 8,
                    },
                    "style": {},
                }
            )
        )
        self.assertEqual(errors, [])

    def test_custom_font_file_url_validation(self) -> None:
        valid_errors = self.collect_errors(
            make_payload(
                {
                    "type": "rich-text",
                    "text": "Hello",
                    "font": {
                        "family": "Custom",
                        "size": 48,
                        "color": "#ffffff",
                    },
                },
                fonts=[{"src": "https://cdn.example.com/fonts/custom.otf?v=1"}],
            )
        )
        self.assertEqual(valid_errors, [])

        invalid_errors = self.collect_errors(
            make_payload(
                {
                    "type": "rich-text",
                    "text": "Hello",
                    "font": {
                        "family": "Custom",
                        "size": 48,
                        "color": "#ffffff",
                    },
                },
                fonts=[{"src": "https://fonts.googleapis.com/css2?family=Montserrat"}],
            )
        )
        joined = "\n".join(invalid_errors)
        self.assertIn("not a Google Fonts CSS URL", joined)
        self.assertIn(".ttf or .otf", joined)


if __name__ == "__main__":
    unittest.main()
