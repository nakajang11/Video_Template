#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from template_package_support import (
    load_json,
    validate_adult_ai_template_contract,
    validate_template_contract,
)


def resolve_contract_path(path: Path) -> Path:
    if path.is_dir():
        return path / "adult_ai_influencer_template_contract.json"
    return path


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
        description="Validate adult_ai_influencer_template_contract.json without Adult AI runtime access."
    )
    parser.add_argument("path", help="Package directory or adult_ai_influencer_template_contract.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    try:
        contract_path = resolve_contract_path(Path(args.path).expanduser())
        if not contract_path.exists():
            raise FileNotFoundError(f"adult_ai_influencer_template_contract.json is missing: {contract_path}")
        payload = load_json(contract_path)
        contract_errors, contract_warnings = validate_adult_ai_template_contract(payload)
        errors.extend(contract_errors)
        warnings.extend(contract_warnings)

        template_contract_path = contract_path.parent / "template_contract.json"
        if template_contract_path.exists():
            template_contract = load_json(template_contract_path)
            expected_renderer = template_contract.get("renderer") if isinstance(template_contract, dict) else None
            if isinstance(expected_renderer, str):
                template_errors, template_warnings, _ = validate_template_contract(
                    contract_path.parent,
                    expected_renderer=expected_renderer,
                )
                errors.extend(template_errors)
                warnings.extend(template_warnings)
        else:
            warnings.append("template_contract.json was not found next to the Adult AI consumer contract.")
    except Exception as exc:
        errors.append(str(exc))

    print_report(errors, warnings, json_output=args.json)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
