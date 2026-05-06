#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from template_package_support import load_json, validate_hybrid_precompose_blueprint, validate_template_contract


def resolve_package_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    return path.parent


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
        description="Validate hybrid blueprint precompose metadata and v1.2 precompose_plan."
    )
    parser.add_argument("path", help="Hybrid package directory, blueprint.json, or template_contract.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    try:
        package_dir = resolve_package_dir(Path(args.path).expanduser())
        blueprint_path = package_dir / "blueprint.json"
        if blueprint_path.exists():
            blueprint = load_json(blueprint_path)
            blueprint_errors, blueprint_warnings = validate_hybrid_precompose_blueprint(blueprint)
            errors.extend(blueprint_errors)
            warnings.extend(blueprint_warnings)
        else:
            errors.append("blueprint.json is missing.")
        if (package_dir / "template_contract.json").exists():
            contract_errors, contract_warnings, _ = validate_template_contract(
                package_dir,
                expected_renderer="hybrid",
            )
            errors.extend(contract_errors)
            warnings.extend(contract_warnings)
        else:
            errors.append("template_contract.json is missing.")
    except Exception as exc:
        errors.append(str(exc))

    print_report(errors, warnings, json_output=args.json)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
