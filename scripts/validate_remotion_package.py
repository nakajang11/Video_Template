#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_package(package_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    blueprint_path = package_dir / "blueprint.json"
    manifest_path = package_dir / "manifest.json"
    source_audio_path = package_dir / "source_audio.mp3"
    remotion_dir = package_dir / "remotion_package"

    if not blueprint_path.exists():
        errors.append("blueprint.json is missing.")
        return errors, warnings

    manifest = None
    if not manifest_path.exists():
        errors.append("manifest.json is missing.")
    else:
        manifest = load_json(manifest_path)
    blueprint = load_json(blueprint_path)
    renderer = blueprint.get("renderer", "shotstack")
    if renderer != "remotion":
        errors.append(
            f"blueprint.json renderer must be `remotion` for this validator, found `{renderer}`."
        )
    if isinstance(manifest, dict):
        manifest_renderer = manifest.get("renderer")
        if manifest_renderer != "remotion":
            errors.append(
                f"manifest.json renderer must be `remotion`, found `{manifest_renderer}`."
            )
    if not source_audio_path.exists():
        errors.append("source_audio.mp3 is missing.")
    if not remotion_dir.exists():
        errors.append("remotion_package/ is missing.")
        return errors, warnings

    required_paths = [
        remotion_dir / "package.json",
        remotion_dir / "README.md",
        remotion_dir / "src" / "index.jsx",
        remotion_dir / "src" / "Root.jsx",
        remotion_dir / "props" / "default-props.json",
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(f"Required Remotion file is missing: {path.relative_to(package_dir)}")

    package_json_path = remotion_dir / "package.json"
    if package_json_path.exists():
        package_json = load_json(package_json_path)
        dependencies = package_json.get("dependencies", {})
        for dependency in ["remotion", "@remotion/cli", "react", "react-dom"]:
            if dependency not in dependencies:
                errors.append(
                    f"remotion_package/package.json is missing dependency `{dependency}`."
                )

    remotion_meta = blueprint.get("remotion_package")
    if isinstance(remotion_meta, dict):
        composition_id = remotion_meta.get("composition_id")
        props_file = remotion_meta.get("props_file")
        entry_file = remotion_meta.get("entry_file")
        package_subdir = remotion_meta.get("package_dir")

        if not composition_id:
            errors.append("blueprint.remotion_package.composition_id is missing.")
        if package_subdir and package_subdir != "remotion_package":
            warnings.append(
                "blueprint.remotion_package.package_dir is not `remotion_package`; "
                "make sure tooling agrees on the folder name."
            )
        if props_file and not (package_dir / props_file).exists():
            errors.append(
                f"blueprint.remotion_package.props_file does not exist: {props_file}"
            )
        if entry_file and not (package_dir / entry_file).exists():
            errors.append(
                f"blueprint.remotion_package.entry_file does not exist: {entry_file}"
            )
    else:
        warnings.append(
            "blueprint.remotion_package metadata is missing; package structure exists, "
            "but the blueprint does not yet describe the Remotion entry points."
        )

    rendered_outputs = list((remotion_dir / "renders").glob("*"))
    if not rendered_outputs:
        warnings.append(
            "remotion_package/renders/ is missing or empty. This is acceptable at the review gate, "
            "but add preview outputs when practical."
        )

    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_remotion_package.py <package_dir>", file=sys.stderr)
        return 2

    package_dir = Path(sys.argv[1]).expanduser().resolve()
    if not package_dir.exists():
        print(f"Package directory does not exist: {package_dir}", file=sys.stderr)
        return 2

    errors, warnings = validate_package(package_dir)
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Validation passed.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
