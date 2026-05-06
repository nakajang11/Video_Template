#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from template_package_support import load_json, validate_template_contract


REQUIRED_PACKAGE_FILES = [
    "package.json",
    "README.md",
    "meta.json",
    "index.html",
    "template-partition.json",
]


def resolve_package_dir(path: Path) -> Path:
    if path.is_file():
        return path.parent
    if (path / "hyperframes_package").exists():
        return path / "hyperframes_package"
    return path


def validate_meta(meta: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(meta, dict):
        return ["hyperframes_package/meta.json must contain an object."]
    for key in ("composition_id", "width", "height", "fps", "duration_sec"):
        value = meta.get(key)
        if key == "composition_id":
            if not isinstance(value, str) or not value:
                errors.append("hyperframes_package/meta.json requires composition_id.")
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            errors.append(f"hyperframes_package/meta.json requires positive numeric {key}.")
    if meta.get("render_status") == "rendered":
        errors.append("hyperframes_package/meta.json must not mark render_status as rendered by default.")
    return errors


def validate_partition(partition: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(partition, dict):
        return ["hyperframes_package/template-partition.json must contain an object."]
    editable = partition.get("editable_slots") or partition.get("slots")
    if not isinstance(editable, list) or not editable:
        errors.append("hyperframes_package/template-partition.json requires editable_slots[].")
    else:
        for index, slot in enumerate(editable, start=1):
            if not isinstance(slot, dict):
                errors.append(f"editable_slots[{index}] must be an object.")
                continue
            if not isinstance(slot.get("slot_id"), str) or not slot.get("slot_id"):
                errors.append(f"editable_slots[{index}] requires slot_id.")
            if not isinstance(slot.get("graph_ref"), str) or not slot.get("graph_ref"):
                errors.append(f"editable_slots[{index}] requires graph_ref.")
    return errors


def validate_html(html: str) -> list[str]:
    errors: list[str] = []
    lower = html.lower()
    if "data-composition-id" not in lower:
        errors.append("hyperframes_package/index.html requires data-composition-id.")
    if "http://" in lower or "https://" in lower:
        errors.append("hyperframes_package/index.html must not contain resolved remote URLs.")
    if "npx hyperframes render" in lower or "hyperframes render" in lower:
        errors.append("hyperframes_package/index.html must not imply a default render command.")
    return errors


def print_report(errors: list[str], warnings: list[str], *, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                {"passed": not errors, "errors": errors, "warnings": warnings},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Validation passed.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically validate a Hyperframes package without rendering."
    )
    parser.add_argument("path", help="Package directory, hyperframes_package directory, or package file")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    try:
        package_dir = resolve_package_dir(Path(args.path).expanduser())
        for rel_path in REQUIRED_PACKAGE_FILES:
            if not (package_dir / rel_path).exists():
                errors.append(f"hyperframes_package/{rel_path} is missing.")
        assets_dir = package_dir / "assets"
        if not assets_dir.exists():
            warnings.append("hyperframes_package/assets/ is not present; package has no local media placeholders.")
        if (package_dir / "meta.json").exists():
            errors.extend(validate_meta(load_json(package_dir / "meta.json")))
        if (package_dir / "template-partition.json").exists():
            errors.extend(validate_partition(load_json(package_dir / "template-partition.json")))
        if (package_dir / "index.html").exists():
            errors.extend(validate_html((package_dir / "index.html").read_text()))

        root_dir = package_dir.parent if package_dir.name == "hyperframes_package" else package_dir
        if (root_dir / "template_contract.json").exists():
            contract_errors, contract_warnings, _ = validate_template_contract(
                root_dir,
                expected_renderer="hyperframes",
            )
            errors.extend(contract_errors)
            warnings.extend(contract_warnings)
    except Exception as exc:
        errors.append(str(exc))

    print_report(errors, warnings, json_output=args.json)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
