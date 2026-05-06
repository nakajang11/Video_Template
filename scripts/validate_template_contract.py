#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from template_package_support import (
    HYBRID_PRECOMPOSE_STATUSES,
    PRECOMPOSE_BLOCKER_CODES,
    SUPPORTED_RENDERERS,
    load_json,
    validate_template_contract,
)


FORBIDDEN_ARCHIVE_PARTS = {
    ".env",
    "__pycache__",
    "node_modules",
    "provider_response",
    "provider_result",
    "renders",
}
ARCHIVE_URL_ALLOWED_FILES = {
    "cloudinary_assets.json",
    "shotstack.pasteable.json",
    "shotstack_smoke_result.json",
    "shotstack_smoke_compare.json",
}
ARCHIVE_TEXT_SCAN_LIMIT_BYTES = 1_000_000
ARCHIVE_FORBIDDEN_PAYLOAD_MARKERS = {
    "api_key",
    "generated_media_url",
    "generated_url",
    "provider_response",
    "provider_result",
    "secret",
    "secure_url",
}


def resolve_package_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.name == "template_contract.json":
        return path.parent
    raise ValueError("Path must be a package directory or template_contract.json")


def infer_expected_renderer(package_dir: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    contract = load_json(package_dir / "template_contract.json")
    renderer = contract.get("renderer") if isinstance(contract, dict) else None
    if isinstance(renderer, str):
        return renderer
    return "unknown"


def scan_archive(package_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    archive_path = package_dir / "package.zip"
    if not archive_path.exists():
        warnings.append("package.zip is not present; archive content was not checked.")
        return errors, warnings
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        errors.append(f"package.zip is not a readable zip archive: {exc}")
        return errors, warnings

    for info in infos:
        name = info.filename
        parts = set(Path(name).parts)
        lower_name = name.lower()
        if parts & FORBIDDEN_ARCHIVE_PARTS:
            errors.append(f"package.zip contains forbidden archive part: {name}")
        if any(part in lower_name for part in ("provider_response", "provider_result")):
            errors.append(f"package.zip contains provider execution artifact: {name}")
        if lower_name.startswith("/") or ".." in Path(name).parts:
            errors.append(f"package.zip contains unsafe path: {name}")
        if info.is_dir():
            continue
        if info.file_size > ARCHIVE_TEXT_SCAN_LIMIT_BYTES:
            warnings.append(f"package.zip member was too large for text leak scan: {name}")
            continue
        suffix = Path(name).suffix.lower()
        if suffix not in {".json", ".md", ".txt", ".html", ".js", ".jsx", ".css"}:
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                text = archive.read(info).decode("utf-8", errors="ignore")
        except Exception as exc:
            warnings.append(f"package.zip member could not be text-scanned: {name}: {exc}")
            continue
        lower_text = text.lower()
        for marker in ARCHIVE_FORBIDDEN_PAYLOAD_MARKERS:
            if marker in lower_text:
                if marker == "secure_url" and Path(name).name in ARCHIVE_URL_ALLOWED_FILES:
                    warnings.append(f"package.zip member contains review-sidecar secure_url content: {name}")
                    continue
                errors.append(f"package.zip member contains forbidden payload marker `{marker}`: {name}")
        if "http://" in lower_text or "https://" in lower_text:
            if Path(name).name in ARCHIVE_URL_ALLOWED_FILES:
                warnings.append(f"package.zip member contains review-sidecar URL content: {name}")
            else:
                errors.append(f"package.zip member contains resolved URL content: {name}")
    return errors, warnings


def validate_contract_semantics(package_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    contract = load_json(package_dir / "template_contract.json")
    if not isinstance(contract, dict):
        return ["template_contract.json must contain an object."], warnings

    renderer = contract.get("renderer")
    if renderer not in SUPPORTED_RENDERERS:
        errors.append(f"template_contract.json renderer is not supported: {renderer}")

    slots = contract.get("slots")
    if isinstance(slots, list):
        slot_ids = [slot.get("slot_id") for slot in slots if isinstance(slot, dict)]
        if len(slot_ids) != len(set(slot_ids)):
            errors.append("template_contract.json slots contain duplicate slot_id values.")
    else:
        slot_ids = []

    precompose_plan = contract.get("precompose_plan")
    if isinstance(precompose_plan, dict):
        for index, step in enumerate(precompose_plan.get("steps", []), start=1):
            if not isinstance(step, dict):
                continue
            status = step.get("status")
            if status not in HYBRID_PRECOMPOSE_STATUSES:
                errors.append(f"precompose_plan step {index} has invalid status: {status}")
            for blocker in step.get("blockers", []):
                if not isinstance(blocker, dict) or blocker.get("code") not in PRECOMPOSE_BLOCKER_CODES:
                    errors.append(f"precompose_plan step {index} has invalid blocker.")
            if status != "rendered" and not step.get("blockers"):
                errors.append(f"precompose_plan step {index} must carry blockers until rendered.")
            if step.get("output_slot") not in slot_ids:
                errors.append(f"precompose_plan step {index} output_slot does not resolve to a slot.")

    validation = contract.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    if validation.get("paid_generation_performed") is True:
        errors.append("template_contract.json implies paid generation was performed.")
    if validation.get("rendering_performed") is True:
        errors.append("template_contract.json implies rendering was performed.")
    return errors, warnings


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
    parser = argparse.ArgumentParser(description="Validate a Video_Template v1.2 template contract.")
    parser.add_argument("path", help="Package directory or template_contract.json")
    parser.add_argument("--expected-renderer", choices=sorted(SUPPORTED_RENDERERS))
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    args = parser.parse_args()

    try:
        package_dir = resolve_package_dir(Path(args.path).expanduser())
        expected_renderer = infer_expected_renderer(package_dir, args.expected_renderer)
        errors, warnings, _ = validate_template_contract(
            package_dir,
            expected_renderer=expected_renderer,
        )
        semantic_errors, semantic_warnings = validate_contract_semantics(package_dir)
        archive_errors, archive_warnings = scan_archive(package_dir)
        errors.extend(semantic_errors)
        errors.extend(archive_errors)
        warnings.extend(semantic_warnings)
        warnings.extend(archive_warnings)
    except Exception as exc:
        errors = [str(exc)]
        warnings = []

    print_report(errors, warnings, json_output=args.json)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
