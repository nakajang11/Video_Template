#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from template_package_support import validate_template_contract


LOCAL_PATH_PREFIXES = ("/Users/", "/home/", "/var/", "/tmp/", "file://")
HTTP_RE = re.compile(r"^https?://", re.IGNORECASE)
PROP_PART_RE = re.compile(r"^([^\[\]]+)(?:\[(\d*)\])?$")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def get_prop_path(payload: Any, prop_path: str) -> tuple[bool, Any]:
    def walk(current: Any, parts: list[str]) -> tuple[bool, Any]:
        if not parts:
            return True, current
        part = parts[0]
        match = PROP_PART_RE.match(part)
        if not match:
            return False, None
        key = match.group(1)
        index = match.group(2)
        if isinstance(current, dict) and part in current:
            return walk(current[part], parts[1:])
        if not isinstance(current, dict) or key not in current:
            return False, None
        next_value = current[key]
        if index is None:
            return walk(next_value, parts[1:])
        if not isinstance(next_value, list):
            return False, None
        if index == "":
            if not next_value:
                return False, None
            values = []
            for item in next_value:
                exists, value = walk(item, parts[1:])
                if not exists:
                    return False, None
                values.append(value)
            return True, values
        try:
            list_index = int(index)
        except ValueError:
            return False, None
        if 0 <= list_index < len(next_value):
            return walk(next_value[list_index], parts[1:])
        return False, None

    return walk(payload, prop_path.split("."))


def wildcard_prop_path(prop_path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", prop_path)


def parse_js_number(source: str, prop_name: str) -> int | None:
    match = re.search(rf"\b{re.escape(prop_name)}\s*=\s*{{?\s*(\d+)\s*}}?", source)
    if not match:
        return None
    return int(match.group(1))


def parse_composition_id(source: str) -> str | None:
    match = re.search(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", source)
    return match.group(1) if match else None


def is_remote_url(value: str) -> bool:
    return bool(HTTP_RE.match(value))


def is_machine_local_path(value: str) -> bool:
    return value.startswith(LOCAL_PATH_PREFIXES)


def validate_package_json(
    package_json: dict[str, Any],
    *,
    entry_file: str | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    dependencies = package_json.get("dependencies", {})
    dev_dependencies = package_json.get("devDependencies", {})
    if not isinstance(dependencies, dict):
        errors.append("remotion_package/package.json dependencies must be an object.")
        dependencies = {}
    if not isinstance(dev_dependencies, dict):
        dev_dependencies = {}
    all_dependencies = {**dependencies, **dev_dependencies}
    for dependency in ["remotion", "@remotion/cli", "react", "react-dom"]:
        if dependency not in all_dependencies:
            errors.append(
                f"remotion_package/package.json is missing dependency `{dependency}`."
            )

    scripts = package_json.get("scripts")
    if not isinstance(scripts, dict):
        errors.append("remotion_package/package.json scripts must be an object.")
        return

    studio_script = scripts.get("studio")
    if not isinstance(studio_script, str) or "remotion studio" not in studio_script:
        warnings.append("remotion_package/package.json should include a `studio` script using `remotion studio`.")
    elif entry_file and Path(entry_file).name not in studio_script and entry_file not in studio_script:
        warnings.append("remotion_package/package.json studio script does not appear to reference the blueprint entry file.")

    render_or_still_scripts = [
        name
        for name, value in scripts.items()
        if isinstance(value, str) and ("remotion render" in value or "remotion still" in value)
    ]
    if not render_or_still_scripts:
        warnings.append("remotion_package/package.json should include at least one review render or still script.")


def validate_source_files(
    *,
    remotion_dir: Path,
    entry_file_path: Path,
    root_file_path: Path,
    composition_id: str | None,
    default_props: dict[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> dict[str, int | None]:
    metadata = {
        "durationInFrames": None,
        "fps": None,
        "width": None,
        "height": None,
    }

    if entry_file_path.exists():
        entry_source = entry_file_path.read_text()
        if "registerRoot(" not in entry_source:
            errors.append("remotion_package/src/index.jsx must call registerRoot().")
    if root_file_path.exists():
        root_source = root_file_path.read_text()
        if "<Composition" not in root_source and "Composition(" not in root_source:
            errors.append("remotion_package/src/Root.jsx must define a Remotion Composition.")
        actual_id = parse_composition_id(root_source)
        if composition_id and actual_id and actual_id != composition_id:
            errors.append(
                f"Root.jsx Composition id `{actual_id}` does not match blueprint composition_id `{composition_id}`."
            )
        elif composition_id and not actual_id:
            errors.append("Root.jsx Composition id could not be detected.")
        if default_props is not None and "defaultProps" not in root_source:
            warnings.append("Root.jsx should pass props/default-props.json as Composition defaultProps.")
        if "calculateMetadata" in root_source:
            warnings.append("Root.jsx uses calculateMetadata; static duration/dimension checks are advisory.")
        for key in metadata:
            metadata[key] = parse_js_number(root_source, key)
        for key, value in metadata.items():
            if value is None and "calculateMetadata" not in root_source:
                errors.append(f"Root.jsx Composition must define numeric {key}.")

        if default_props is not None and contains_local_media_reference(default_props) and "staticFile(" not in root_source:
            implementation_sources = "\n".join(
                path.read_text()
                for path in (remotion_dir / "src").glob("*.jsx")
                if path.exists()
            )
            if "staticFile(" not in implementation_sources:
                errors.append("Local Remotion assets must be referenced with staticFile().")

    return metadata


def contains_local_media_reference(node: Any) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"src", "audioFile"} and isinstance(value, str) and not is_remote_url(value):
                return True
            if contains_local_media_reference(value):
                return True
    elif isinstance(node, list):
        return any(contains_local_media_reference(item) for item in node)
    return False


def iter_media_input_refs(default_props: dict[str, Any]):
    def walk_media(value: Any, path: str, inherited_kind: Any = None):
        if isinstance(value, dict):
            kind = value.get("kind", inherited_kind)
            src = value.get("src")
            if isinstance(src, str) or "src" in value:
                yield f"{path}.src", src, kind
            for key, child in value.items():
                if key in {"src", "kind"}:
                    continue
                yield from walk_media(child, f"{path}.{key}", kind)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk_media(child, f"{path}[{index}]", inherited_kind)

    media_inputs = default_props.get("mediaInputs")
    if isinstance(media_inputs, dict):
        for name, media_input in media_inputs.items():
            yield from walk_media(media_input, f"mediaInputs.{name}")
    audio_file = default_props.get("audioFile")
    if isinstance(audio_file, str):
        yield "audioFile", audio_file, "audio"


def validate_default_props(
    *,
    default_props: Any,
    remotion_dir: Path,
    blueprint: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any] | None:
    if not isinstance(default_props, dict):
        errors.append("remotion_package/props/default-props.json must contain a JSON object.")
        return None

    for prop_path, src, kind in iter_media_input_refs(default_props):
        if src is None:
            errors.append(f"props/default-props.json {prop_path}.src is missing.")
            continue
        if not isinstance(src, str) or not src:
            errors.append(f"props/default-props.json {prop_path}.src must be a non-empty string.")
            continue
        if is_machine_local_path(src):
            errors.append(f"props/default-props.json {prop_path}.src must not use a machine-local path.")
            continue
        if is_remote_url(src):
            continue
        public_path = remotion_dir / "public" / src
        if not public_path.exists():
            errors.append(f"Local Remotion asset is missing for {prop_path}: public/{src}")
        if kind == "audio" and public_path.exists() and public_path.suffix.lower() not in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
            warnings.append(f"Audio prop {prop_path} points to an unusual audio extension: {src}")

    editable_props = []
    remotion_meta = blueprint.get("remotion_package")
    if isinstance(remotion_meta, dict):
        editable_props = remotion_meta.get("editable_props", [])
    if isinstance(editable_props, list):
        for prop_path in editable_props:
            if not isinstance(prop_path, str) or not prop_path:
                errors.append("blueprint.remotion_package.editable_props must contain non-empty strings.")
                continue
            exists, _ = get_prop_path(default_props, prop_path)
            if not exists:
                errors.append(f"Editable Remotion prop path is missing from default-props.json: {prop_path}")
    elif editable_props is not None:
        errors.append("blueprint.remotion_package.editable_props must be an array.")

    for scene in blueprint.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id", "unknown_scene")
        remotion_sequence = scene.get("remotion_sequence")
        if not isinstance(remotion_sequence, dict):
            continue
        for prop_path in remotion_sequence.get("editable_props", []):
            if not isinstance(prop_path, str):
                errors.append(f"{scene_id}: remotion_sequence.editable_props must contain strings.")
                continue
            exists, _ = get_prop_path(default_props, prop_path)
            if not exists:
                errors.append(f"{scene_id}: editable prop is missing from default-props.json: {prop_path}")
            if (
                isinstance(editable_props, list)
                and prop_path not in editable_props
                and wildcard_prop_path(prop_path) not in editable_props
            ):
                warnings.append(
                    f"{scene_id}: `{prop_path}` is editable at scene level but missing from blueprint.remotion_package.editable_props."
                )

    return default_props


def validate_template_partition(
    *,
    partition: Any,
    default_props: dict[str, Any] | None,
    package_dir: Path,
    remotion_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    if partition is None:
        warnings.append("remotion_package/template-partition.json is missing; downstream partition metadata will be weaker.")
        return
    if not isinstance(partition, dict):
        errors.append("remotion_package/template-partition.json must contain a JSON object.")
        return
    if not isinstance(partition.get("template_goal"), str) or not partition.get("template_goal"):
        warnings.append("template-partition.json should include template_goal.")

    scene_sections = [key for key in partition if re.match(r"scene_\d+", key)]
    if not scene_sections:
        warnings.append("template-partition.json should contain scene_* sections.")

    for scene_key in scene_sections:
        scene_partition = partition.get(scene_key)
        if not isinstance(scene_partition, dict):
            errors.append(f"template-partition.json {scene_key} must be an object.")
            continue
        input_media = scene_partition.get("input_media", [])
        if not isinstance(input_media, list):
            errors.append(f"template-partition.json {scene_key}.input_media must be an array.")
            continue
        for index, item in enumerate(input_media, start=1):
            if not isinstance(item, dict):
                errors.append(f"template-partition.json {scene_key}.input_media[{index}] must be an object.")
                continue
            slot = item.get("slot")
            if isinstance(slot, str) and default_props is not None:
                exists, _ = get_prop_path(default_props, slot)
                if not exists:
                    errors.append(f"template-partition.json {scene_key}.input_media[{index}] slot is missing from default props: {slot}")
            rel_path = item.get("path")
            if isinstance(rel_path, str):
                candidate = remotion_dir / rel_path
                if not candidate.exists():
                    candidate = package_dir / rel_path
                if not candidate.exists():
                    warnings.append(f"template-partition.json {scene_key}.input_media[{index}] path does not exist: {rel_path}")


def validate_sequences(
    *,
    blueprint: dict[str, Any],
    composition_metadata: dict[str, int | None],
    errors: list[str],
    warnings: list[str],
) -> None:
    scenes = blueprint.get("scenes")
    if not isinstance(scenes, list):
        errors.append("blueprint.scenes must be an array.")
        return

    fps = composition_metadata.get("fps")
    duration_in_frames = composition_metadata.get("durationInFrames")
    sequence_ranges: list[tuple[str, int, int]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            errors.append("Each blueprint scene must be an object.")
            continue
        scene_id = scene.get("scene_id", "unknown_scene")
        sequence = scene.get("remotion_sequence")
        if not isinstance(sequence, dict):
            errors.append(f"{scene_id}: remotion_sequence is required for Remotion scenes.")
            continue
        start_frame = sequence.get("start_frame")
        duration_frames = sequence.get("duration_frames")
        if not isinstance(start_frame, int) or start_frame < 0:
            errors.append(f"{scene_id}: remotion_sequence.start_frame must be a non-negative integer.")
            continue
        if not isinstance(duration_frames, int) or duration_frames <= 0:
            errors.append(f"{scene_id}: remotion_sequence.duration_frames must be a positive integer.")
            continue
        sequence_ranges.append((str(scene_id), start_frame, start_frame + duration_frames))

        duration_sec = scene.get("duration_sec")
        if isinstance(duration_sec, (int, float)) and isinstance(fps, int) and fps > 0:
            expected_frames = round(float(duration_sec) * fps)
            if abs(expected_frames - duration_frames) > 1:
                warnings.append(
                    f"{scene_id}: remotion_sequence.duration_frames differs from duration_sec * fps by more than 1 frame."
                )

    ordered_ranges = sorted(sequence_ranges, key=lambda item: item[1])
    previous_end = 0
    for scene_id, start_frame, end_frame in ordered_ranges:
        if start_frame < previous_end:
            errors.append(f"{scene_id}: remotion_sequence overlaps a previous scene.")
        if start_frame > previous_end:
            warnings.append(f"{scene_id}: remotion_sequence leaves a gap before this scene.")
        previous_end = max(previous_end, end_frame)
    if isinstance(duration_in_frames, int) and ordered_ranges:
        if abs(previous_end - duration_in_frames) > 1:
            warnings.append(
                f"Root.jsx durationInFrames ({duration_in_frames}) differs from final remotion_sequence end frame ({previous_end})."
            )


def run_cli_smoke(remotion_dir: Path, entry_file: str | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    entry = Path(entry_file).name if entry_file else "src/index.jsx"
    if entry_file and "src/" in entry_file:
        entry = str(Path(entry_file).relative_to("remotion_package"))
    completed = subprocess.run(
        ["npx", "remotion", "compositions", entry],
        cwd=remotion_dir,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        errors.append(
            "Remotion CLI smoke failed: "
            + (completed.stderr.strip() or completed.stdout.strip() or f"returncode={completed.returncode}")
        )
    elif completed.stdout.strip():
        warnings.append("Remotion CLI smoke completed.")
    return errors, warnings


def validate_package(package_dir: Path, *, run_smoke: bool = False) -> tuple[list[str], list[str]]:
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
    package_json = None
    if package_json_path.exists():
        package_json = load_json(package_json_path)

    remotion_meta = blueprint.get("remotion_package")
    composition_id = None
    props_file = None
    entry_file = None
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

    if isinstance(package_json, dict):
        validate_package_json(
            package_json,
            entry_file=entry_file if isinstance(entry_file, str) else None,
            errors=errors,
            warnings=warnings,
        )

    default_props = None
    default_props_path = remotion_dir / "props" / "default-props.json"
    if default_props_path.exists():
        default_props = validate_default_props(
            default_props=load_json(default_props_path),
            remotion_dir=remotion_dir,
            blueprint=blueprint,
            errors=errors,
            warnings=warnings,
        )

    root_file_path = remotion_dir / "src" / "Root.jsx"
    entry_file_path = remotion_dir / "src" / "index.jsx"
    if isinstance(entry_file, str) and (package_dir / entry_file).exists():
        entry_file_path = package_dir / entry_file

    composition_metadata = validate_source_files(
        remotion_dir=remotion_dir,
        entry_file_path=entry_file_path,
        root_file_path=root_file_path,
        composition_id=composition_id if isinstance(composition_id, str) else None,
        default_props=default_props,
        errors=errors,
        warnings=warnings,
    )
    validate_sequences(
        blueprint=blueprint,
        composition_metadata=composition_metadata,
        errors=errors,
        warnings=warnings,
    )

    partition_path = remotion_dir / "template-partition.json"
    partition = load_json(partition_path) if partition_path.exists() else None
    validate_template_partition(
        partition=partition,
        default_props=default_props,
        package_dir=package_dir,
        remotion_dir=remotion_dir,
        errors=errors,
        warnings=warnings,
    )

    rendered_outputs = list((remotion_dir / "renders").glob("*"))
    if not rendered_outputs:
        warnings.append(
            "remotion_package/renders/ is missing or empty. This is acceptable at the review gate, "
            "but add preview outputs when practical."
        )

    contract_errors, contract_warnings, _ = validate_template_contract(
        package_dir,
        expected_renderer="remotion",
    )
    errors.extend(contract_errors)
    warnings.extend(contract_warnings)

    if run_smoke and not errors:
        smoke_errors, smoke_warnings = run_cli_smoke(
            remotion_dir,
            entry_file if isinstance(entry_file, str) else None,
        )
        errors.extend(smoke_errors)
        warnings.extend(smoke_warnings)

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a review-gated Remotion template package."
    )
    parser.add_argument("package_dir", help="Path to output/<job_id>.")
    parser.add_argument(
        "--run-cli-smoke",
        action="store_true",
        help="Run `npx remotion compositions` after static validation passes.",
    )
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    if not package_dir.exists():
        print(f"Package directory does not exist: {package_dir}", file=sys.stderr)
        return 2

    errors, warnings = validate_package(package_dir, run_smoke=args.run_cli_smoke)
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
