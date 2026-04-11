#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


TEMPLATE_CONTRACT_VERSION = "1.0"
TEMPLATE_TYPE_BY_CATEGORY = {
    "single": "A-7_trend_single",
    "continue": "A-6_trend_continue",
}
CONTENT_FILL_STRATEGIES = {
    "keep_locked",
    "reuse_template_asset",
    "select_existing_asset",
    "generate_text",
    "generate_media",
    "reuse_source_trend_video",
}
SUPPORTED_SLOT_KINDS = {"media", "text", "color", "number", "audio", "overlay"}
TECHNICAL_PROP_ROOTS = {"palette", "transitions", "textStyle"}
TECHNICAL_PROP_SUFFIXES = {
    "accent",
    "accentGlow",
    "background",
    "color",
    "durationFrames",
    "fontSize",
    "introGlow",
    "introHighlight",
    "kind",
    "rotate",
    "shadowColor",
    "startFrame",
    "subtitle",
    "titleGlow",
    "titleStroke",
    "x",
    "y",
}
INTERESTING_CONTEXT_KEYWORDS = {
    "angle",
    "background",
    "brand",
    "caption",
    "category",
    "character",
    "concept",
    "constraint",
    "content",
    "copy",
    "cta",
    "flow",
    "goal",
    "headline",
    "hook",
    "language",
    "location",
    "mood",
    "note",
    "notes",
    "platform",
    "product",
    "renderer",
    "scene",
    "style",
    "template",
    "theme",
    "title",
    "tone",
    "trend",
    "wardrobe",
}
PROP_TOKEN_RE = re.compile(r"([^\.\[\]]+)|\[(\d+)\]")
CONTENT_TYPE_RE = re.compile(r"^(A-\\d+)")
CAMEL_BOUNDARY_RE = re.compile(r"(?<!^)(?=[A-Z])")
ARCHIVE_EXCLUDE_PARTS = {"__pycache__", "node_modules", "renders"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def make_empty_caller_context_echo(preferred_renderer: str = "auto") -> dict[str, Any]:
    return {
        "template_type": None,
        "source_platform": None,
        "source_trend_video_id": None,
        "preferred_renderer": preferred_renderer,
        "step1_hint_summary": None,
        "step2_hint_summary": None,
        "operator_notes_summary": None,
    }


def make_empty_source_summary(source_video: str | None = None) -> dict[str, Any]:
    return {
        "source_video": source_video,
        "duration_sec": None,
        "width": None,
        "height": None,
        "scene_count": 0,
    }


def make_empty_package_summary(renderer: str = "unknown") -> dict[str, Any]:
    return {
        "scene_count": 0,
        "slot_count": 0,
        "text_slot_count": 0,
        "media_slot_count": 0,
        "renderer": renderer,
    }


def _stringify_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        collapsed = " ".join(value.split())
        return collapsed or None
    return None


def _truncate_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _flatten_context_items(node: Any, prefix: str = "", depth: int = 0) -> list[tuple[str, str]]:
    if depth > 2:
        return []

    flattened: list[tuple[str, str]] = []
    scalar = _stringify_scalar(node)
    if scalar is not None and prefix:
        flattened.append((prefix, scalar))
        return flattened

    if isinstance(node, dict):
        for key in sorted(node):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.extend(_flatten_context_items(node[key], child_prefix, depth + 1))
    elif isinstance(node, list):
        for index, item in enumerate(node[:5]):
            child_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            flattened.extend(_flatten_context_items(item, child_prefix, depth + 1))
    return flattened


def summarize_context_block(node: Any, *, max_items: int = 6, max_chars: int = 240) -> str | None:
    scalar = _stringify_scalar(node)
    if scalar is not None:
        return _truncate_text(scalar, max_chars)

    flattened = _flatten_context_items(node)
    if not flattened:
        return None

    preferred: list[tuple[str, str]] = []
    fallback: list[tuple[str, str]] = []
    for path, value in flattened:
        path_lower = path.lower()
        if any(keyword in path_lower for keyword in INTERESTING_CONTEXT_KEYWORDS):
            preferred.append((path, value))
        else:
            fallback.append((path, value))

    selected = preferred[:max_items]
    if len(selected) < max_items:
        selected.extend(fallback[: max_items - len(selected)])

    rendered = ", ".join(f"{path}={value}" for path, value in selected)
    return _truncate_text(rendered, max_chars)


def compact_caller_context(
    raw_context: Any,
    *,
    preferred_renderer: str = "auto",
) -> dict[str, Any]:
    echo = make_empty_caller_context_echo(preferred_renderer=preferred_renderer)
    if not isinstance(raw_context, dict):
        return echo

    echo["template_type"] = _stringify_scalar(raw_context.get("template_type"))
    echo["source_platform"] = _stringify_scalar(raw_context.get("source_platform"))
    source_trend_video_id = raw_context.get("source_trend_video_id")
    if isinstance(source_trend_video_id, (int, float, str)):
        echo["source_trend_video_id"] = source_trend_video_id
    echo["step1_hint_summary"] = summarize_context_block(raw_context.get("step1_json"))
    echo["step2_hint_summary"] = summarize_context_block(raw_context.get("step2_json"))
    echo["operator_notes_summary"] = summarize_context_block(
        raw_context.get("notes") or raw_context.get("operator_notes")
    )
    return echo


def render_caller_context_prompt_block(summary: dict[str, Any]) -> str:
    filtered = {key: value for key, value in summary.items() if value not in (None, "", [], {})}
    if not filtered:
        return "none"
    return json.dumps(filtered, ensure_ascii=False, indent=2, sort_keys=True)


def infer_template_type(
    caller_context: Any,
    caller_context_echo: dict[str, Any] | None = None,
) -> str | None:
    if isinstance(caller_context_echo, dict):
        template_type = caller_context_echo.get("template_type")
        if isinstance(template_type, str) and template_type:
            return template_type

    if isinstance(caller_context, dict):
        template_type = caller_context.get("template_type")
        if isinstance(template_type, str) and template_type:
            return template_type

        category = caller_context.get("trend_video_category")
        if isinstance(category, str):
            return TEMPLATE_TYPE_BY_CATEGORY.get(category.strip().lower())

    return None


def infer_supported_content_types(template_type: str | None) -> list[str]:
    if not isinstance(template_type, str):
        return []
    match = CONTENT_TYPE_RE.match(template_type)
    return [match.group(1)] if match else []


def _tokenize_prop_path(path: str) -> list[str]:
    tokens: list[str] = []
    for name, index in PROP_TOKEN_RE.findall(path):
        if name:
            tokens.append(name)
        elif index:
            tokens.append(index)
    return tokens


def _camel_to_snake(value: str) -> str:
    return CAMEL_BOUNDARY_RE.sub("_", value).replace("-", "_").lower()


def _merge_key_suffix(scene_id: str | None, merge_key: str, fallback: str) -> str:
    key = merge_key
    if scene_id:
        scene_prefix = scene_id.upper()
        if key.startswith(scene_prefix + "_"):
            key = key[len(scene_prefix) + 1 :]
    return _camel_to_snake(key) or fallback


def _build_slot_id(scene_id: str | None, kind: str, suffix: str) -> str:
    normalized_suffix = re.sub(r"[^a-z0-9_]+", "_", suffix.lower()).strip("_") or "slot"
    if scene_id:
        return f"{scene_id}.{kind}.{normalized_suffix}"
    return f"global.{kind}.{normalized_suffix}"


def _safe_scene_id(scene_ids: list[str]) -> str | None:
    return scene_ids[0] if len(scene_ids) == 1 else None


def _set_scene_ids(slot: dict[str, Any], scene_ids: list[str]) -> None:
    if len(scene_ids) > 1:
        slot["scene_ids"] = scene_ids


def _get_value_by_path(data: Any, path: str) -> Any:
    current = data
    for token in _tokenize_prop_path(path):
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
            continue
        if isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _find_partition_entry(partition: Any, prop_path: str) -> dict[str, Any] | None:
    if isinstance(partition, dict):
        for entry in partition.get("input_media", []):
            if not isinstance(entry, dict):
                continue
            slot = entry.get("slot")
            if isinstance(slot, str) and prop_path.startswith(slot):
                return entry
        for value in partition.values():
            if isinstance(value, dict):
                nested = _find_partition_entry(value, prop_path)
                if nested is not None:
                    return nested
    return None


def _kind_from_remotion_prop_path(prop_path: str, default_value: Any) -> str | None:
    if prop_path == "audioFile":
        return "audio"
    if prop_path.startswith("mediaInputs.") and prop_path.endswith(".src"):
        return "overlay" if "overlay" in prop_path.lower() else "media"

    tokens = _tokenize_prop_path(prop_path)
    if not tokens:
        return None
    root = tokens[0]
    last = tokens[-1]
    if root in TECHNICAL_PROP_ROOTS:
        return None
    if last in TECHNICAL_PROP_SUFFIXES or last.lower().endswith("color"):
        return None
    if isinstance(default_value, (int, float, bool)) and last not in {"memoryScore"}:
        return None
    if isinstance(default_value, (str, list, dict)):
        return "text"
    return None


def _slot_suffix_from_prop_path(prop_path: str, kind: str) -> str:
    tokens = _tokenize_prop_path(prop_path)
    if not tokens:
        return "slot"
    if kind in {"media", "overlay"} and tokens[-1] == "src":
        tokens = tokens[:-1]
    if kind == "text" and tokens[-1] in {"text", "value"}:
        tokens = tokens[:-1]
    if tokens and tokens[0] in {"mediaInputs", "intro", "cloud", "finale"}:
        tokens = tokens[1:]
    return "_".join(_camel_to_snake(token) for token in tokens if token)


def _style_constraints_from_text_overlay(overlay: dict[str, Any]) -> dict[str, Any] | None:
    constraints: dict[str, Any] = {}
    placement = overlay.get("placement")
    if isinstance(placement, str):
        constraints["placement"] = placement
    style = overlay.get("style")
    if isinstance(style, str):
        constraints["style_hint"] = style
    source_geometry = overlay.get("source_geometry")
    if isinstance(source_geometry, dict):
        preview_strategy = source_geometry.get("editor_preview_strategy")
        if isinstance(preview_strategy, str):
            constraints["editor_preview_strategy"] = preview_strategy
        font_candidates = source_geometry.get("font_candidates")
        if isinstance(font_candidates, list) and font_candidates:
            constraints["font_candidates"] = font_candidates
        font_size_hint = source_geometry.get("font_size_hint")
        if isinstance(font_size_hint, (int, float)):
            constraints["font_size_hint"] = font_size_hint
    return constraints or None


def _derive_shotstack_media_fill_strategy(scene: dict[str, Any]) -> str:
    video = scene.get("video")
    startframe = scene.get("startframe")
    video_mode = video.get("mode") if isinstance(video, dict) else None
    startframe_required = startframe.get("required") if isinstance(startframe, dict) else False

    if video_mode == "input-extract":
        return "reuse_source_trend_video"
    if video_mode in {"generate", "motion-control", "reuse-generated"} or startframe_required is True:
        return "generate_media"
    if video_mode == "still-image-effect":
        return "select_existing_asset"
    return "select_existing_asset"


def derive_shotstack_slots(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    audio = blueprint.get("audio")
    if isinstance(audio, dict):
        merge_key = audio.get("shotstack_merge_key")
        if isinstance(merge_key, str) and merge_key:
            slots.append(
                {
                    "slot_id": _build_slot_id(None, "audio", "source"),
                    "scene_id": None,
                    "kind": "audio",
                    "required": True,
                    "fill_strategy": "reuse_source_trend_video",
                    "renderer_binding": {
                        "merge_key": merge_key,
                        "source_file": audio.get("source_file"),
                    },
                }
            )

    for scene in blueprint.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        shotstack = scene.get("shotstack")
        if not isinstance(scene_id, str) or not isinstance(shotstack, dict):
            continue

        merge_key = shotstack.get("merge_key")
        if isinstance(merge_key, str) and merge_key:
            media_kind = shotstack.get("asset_type")
            suffix = "main"
            slots.append(
                {
                    "slot_id": _build_slot_id(scene_id, "media", suffix),
                    "scene_id": scene_id,
                    "kind": "media",
                    "media_kind": media_kind if isinstance(media_kind, str) else None,
                    "required": True,
                    "fill_strategy": _derive_shotstack_media_fill_strategy(scene),
                    "renderer_binding": {
                        "merge_key": merge_key,
                        "alias": shotstack.get("alias"),
                    },
                }
            )

        for overlay in shotstack.get("text_overlays", []):
            if not isinstance(overlay, dict):
                continue
            text_key = overlay.get("text_key")
            if not isinstance(text_key, str) or not text_key:
                continue
            slot: dict[str, Any] = {
                "slot_id": _build_slot_id(
                    scene_id,
                    "text",
                    _merge_key_suffix(scene_id, text_key, "text"),
                ),
                "scene_id": scene_id,
                "kind": "text",
                "required": True,
                "fill_strategy": "generate_text",
                "renderer_binding": {
                    "merge_key": text_key,
                    "placement": overlay.get("placement"),
                },
            }
            constraints = _style_constraints_from_text_overlay(overlay)
            if constraints is not None:
                slot["style_constraints"] = constraints
            slots.append(slot)

        for overlay_index, overlay in enumerate(shotstack.get("overlay_layers", []), start=1):
            if not isinstance(overlay, dict):
                continue
            overlay_merge_key = overlay.get("merge_key")
            if not isinstance(overlay_merge_key, str) or not overlay_merge_key:
                continue
            slots.append(
                {
                    "slot_id": _build_slot_id(
                        scene_id,
                        "overlay",
                        _merge_key_suffix(
                            scene_id,
                            overlay_merge_key,
                            f"overlay_{overlay_index:03d}",
                        ),
                    ),
                    "scene_id": scene_id,
                    "kind": "overlay",
                    "media_kind": overlay.get("asset_type"),
                    "required": True,
                    "fill_strategy": "select_existing_asset",
                    "renderer_binding": {
                        "merge_key": overlay_merge_key,
                        "placement": overlay.get("placement") or overlay.get("position"),
                    },
                }
            )
    return slots


def derive_remotion_slots(
    blueprint: dict[str, Any],
    default_props: Any,
    template_partition: Any,
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    prop_scene_ids: dict[str, set[str]] = defaultdict(set)
    for scene in blueprint.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        remotion_sequence = scene.get("remotion_sequence")
        if not isinstance(scene_id, str) or not isinstance(remotion_sequence, dict):
            continue
        for prop_path in remotion_sequence.get("editable_props", []):
            if isinstance(prop_path, str) and prop_path:
                prop_scene_ids[prop_path].add(scene_id)

    top_level_editable_props = []
    remotion_package = blueprint.get("remotion_package")
    if isinstance(remotion_package, dict):
        top_level_editable_props = [
            prop_path
            for prop_path in remotion_package.get("editable_props", [])
            if isinstance(prop_path, str) and prop_path and "[]" not in prop_path
        ]

    seen_slot_ids: set[str] = set()
    for prop_path in sorted(set(prop_scene_ids) | set(top_level_editable_props)):
        scene_ids = sorted(prop_scene_ids.get(prop_path, set()))
        default_value = _get_value_by_path(default_props, prop_path)
        kind = _kind_from_remotion_prop_path(prop_path, default_value)
        if kind is None:
            continue

        slot_scene_id = _safe_scene_id(scene_ids)
        slot_suffix = _slot_suffix_from_prop_path(prop_path, kind)
        slot_id = _build_slot_id(slot_scene_id, kind, slot_suffix)
        if slot_id in seen_slot_ids:
            continue
        seen_slot_ids.add(slot_id)

        fill_strategy = "generate_text"
        if kind in {"media", "overlay"}:
            fill_strategy = "select_existing_asset"
        elif kind == "audio":
            fill_strategy = (
                "reuse_source_trend_video"
                if default_value == "source_audio.mp3"
                else "select_existing_asset"
            )

        slot: dict[str, Any] = {
            "slot_id": slot_id,
            "scene_id": slot_scene_id,
            "kind": kind,
            "required": True,
            "fill_strategy": fill_strategy,
            "renderer_binding": {
                "prop_path": prop_path,
            },
        }
        if isinstance(default_value, str) and kind in {"media", "overlay", "audio"}:
            slot["renderer_binding"]["default_value"] = default_value
        if kind in {"media", "overlay"}:
            slot["media_kind"] = "image"

        partition_entry = _find_partition_entry(template_partition, prop_path)
        if partition_entry is not None:
            partition_slot = partition_entry.get("slot")
            if isinstance(partition_slot, str):
                slot["renderer_binding"]["partition_slot"] = partition_slot
            role = partition_entry.get("role")
            if isinstance(role, str):
                slot["renderer_binding"]["partition_role"] = role
        if kind == "text":
            if isinstance(default_value, str):
                slot["renderer_binding"]["default_value"] = default_value
            elif isinstance(default_value, list):
                slot["renderer_binding"]["default_item_count"] = len(default_value)
            elif isinstance(default_value, dict):
                slot["renderer_binding"]["default_keys"] = sorted(default_value.keys())

        _set_scene_ids(slot, scene_ids)
        slots.append(slot)

    audio_file = default_props.get("audioFile") if isinstance(default_props, dict) else None
    if isinstance(audio_file, str):
        slots.append(
            {
                "slot_id": _build_slot_id(None, "audio", "source"),
                "scene_id": None,
                "kind": "audio",
                "required": True,
                "fill_strategy": (
                    "reuse_source_trend_video"
                    if audio_file == "source_audio.mp3"
                    else "select_existing_asset"
                ),
                "renderer_binding": {
                    "prop_path": "audioFile",
                    "default_value": audio_file,
                },
            }
        )

    return slots


def build_package_summary_from_slots(
    *,
    renderer: str,
    scene_count: int,
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    text_slot_count = sum(1 for slot in slots if slot.get("kind") == "text")
    media_slot_count = sum(
        1
        for slot in slots
        if slot.get("kind") in {"media", "overlay", "audio"}
    )
    return {
        "scene_count": scene_count,
        "slot_count": len(slots),
        "text_slot_count": text_slot_count,
        "media_slot_count": media_slot_count,
        "renderer": renderer,
    }


def build_source_summary(
    package_dir: Path,
    *,
    default_source_video: str | None = None,
) -> dict[str, Any]:
    summary = make_empty_source_summary(source_video=default_source_video)
    analysis_path = package_dir / "analysis.json"
    blueprint_path = package_dir / "blueprint.json"

    analysis = load_json(analysis_path) if analysis_path.exists() else None
    blueprint = load_json(blueprint_path) if blueprint_path.exists() else None

    if isinstance(blueprint, dict):
        source_video = blueprint.get("source_video")
        if isinstance(source_video, str) and source_video:
            summary["source_video"] = source_video
        scene_order = blueprint.get("scene_order")
        if isinstance(scene_order, list):
            summary["scene_count"] = len(scene_order)

    if isinstance(analysis, dict):
        source_video = analysis.get("source_video")
        if isinstance(source_video, str) and source_video:
            summary["source_video"] = source_video
        media = analysis.get("media")
        if isinstance(media, dict):
            for key in ("duration_sec", "width", "height"):
                value = media.get(key)
                if isinstance(value, (int, float)):
                    summary[key] = value
        scenes = analysis.get("scenes")
        if isinstance(scenes, list):
            summary["scene_count"] = len(scenes)

    return summary


def build_template_contract(
    package_dir: Path,
    *,
    renderer: str,
    caller_context: Any = None,
    caller_context_echo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = load_json(package_dir / "blueprint.json")
    default_props = None
    template_partition = None
    if renderer == "remotion":
        remotion_package = blueprint.get("remotion_package", {})
        props_file = remotion_package.get("props_file")
        if isinstance(props_file, str) and (package_dir / props_file).exists():
            default_props = load_json(package_dir / props_file)
        partition_file = remotion_package.get("partition_file")
        if isinstance(partition_file, str) and (package_dir / partition_file).exists():
            template_partition = load_json(package_dir / partition_file)

    slots = (
        derive_shotstack_slots(blueprint)
        if renderer == "shotstack"
        else derive_remotion_slots(blueprint, default_props, template_partition)
    )

    scene_count = len(blueprint.get("scene_order", [])) if isinstance(blueprint.get("scene_order"), list) else len(blueprint.get("scenes", []))
    template_type = infer_template_type(caller_context, caller_context_echo)
    package_summary = build_package_summary_from_slots(
        renderer=renderer,
        scene_count=scene_count,
        slots=slots,
    )
    fill_requirements = {
        "requires_generated_media": any(
            slot.get("fill_strategy") == "generate_media" for slot in slots
        ),
        "requires_generated_text": any(
            slot.get("fill_strategy") == "generate_text" for slot in slots
        ),
        "requires_motion_reference": any(
            isinstance(scene, dict)
            and isinstance(scene.get("video"), dict)
            and scene["video"].get("mode") == "motion-control"
            for scene in blueprint.get("scenes", [])
        ),
    }

    contract = {
        "contract_version": TEMPLATE_CONTRACT_VERSION,
        "job_id": blueprint.get("job_id"),
        "renderer": renderer,
        "template_type": template_type,
        "supported_content_types": infer_supported_content_types(template_type),
        "fill_requirements": fill_requirements,
        "package_summary": package_summary,
        "slots": slots,
    }
    if template_type is None:
        contract["notes"] = [
            "template_type could not be inferred from caller context or category mapping."
        ]
    return contract


def resolve_review_status(
    *,
    initial_review_status: str | None,
    blueprint: Any,
    manifest: Any,
    preferred_renderer: str,
    actual_renderer: str,
) -> str:
    candidates = []
    if isinstance(initial_review_status, str) and initial_review_status:
        candidates.append(initial_review_status)
    if isinstance(manifest, dict):
        review_status = manifest.get("review_status")
        if isinstance(review_status, str) and review_status:
            candidates.append(review_status)
    if isinstance(blueprint, dict):
        review_status = blueprint.get("review_status")
        if isinstance(review_status, str) and review_status:
            candidates.append(review_status)

    resolved = candidates[0] if candidates else "not_started"
    if preferred_renderer in {"shotstack", "remotion"} and actual_renderer != preferred_renderer:
        return "review_required"
    return resolved


def _upsert_manifest_artifact(
    artifacts: list[dict[str, Any]],
    *,
    artifact_type: str,
    path: str,
    status: str = "created",
    scene_id: str | None = None,
) -> None:
    for artifact in artifacts:
        if artifact.get("path") == path:
            artifact["type"] = artifact_type
            artifact["status"] = status
            artifact["scene_id"] = scene_id
            return
    artifacts.append(
        {
            "type": artifact_type,
            "path": path,
            "scene_id": scene_id,
            "status": status,
        }
    )


def update_manifest_runtime_entries(
    package_dir: Path,
    *,
    renderer: str,
    review_status: str,
    include_result: bool = False,
    include_archive: bool = False,
) -> dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    manifest["job_id"] = manifest.get("job_id") or package_dir.name
    manifest["renderer"] = renderer
    manifest["review_status"] = review_status
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        manifest["artifacts"] = artifacts

    _upsert_manifest_artifact(
        artifacts,
        artifact_type="template_contract",
        path="template_contract.json",
    )
    if include_result:
        _upsert_manifest_artifact(
            artifacts,
            artifact_type="result",
            path="result.json",
        )
    if include_archive:
        _upsert_manifest_artifact(
            artifacts,
            artifact_type="package_archive",
            path="package.zip",
        )

    write_json(manifest_path, manifest)
    return manifest


def _iter_archive_paths_from_manifest(package_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    collected: set[Path] = set()
    for required_name in ("manifest.json", "template_contract.json", "result.json"):
        required_path = package_dir / required_name
        if required_path.exists():
            collected.add(required_path)
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        rel_path = artifact.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        target = package_dir / rel_path
        if not target.exists():
            continue
        if target.is_dir():
            for child in target.rglob("*"):
                if child.is_dir():
                    continue
                if any(part in ARCHIVE_EXCLUDE_PARTS for part in child.parts):
                    continue
                collected.add(child)
            continue
        if any(part in ARCHIVE_EXCLUDE_PARTS for part in target.parts):
            continue
        collected.add(target)
    return sorted(collected)


def create_package_archive(package_dir: Path) -> Path:
    manifest = load_json(package_dir / "manifest.json")
    archive_path = package_dir / "package.zip"
    paths_to_add = _iter_archive_paths_from_manifest(package_dir, manifest)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in paths_to_add:
            if file_path == archive_path:
                continue
            archive.write(file_path, arcname=str(file_path.relative_to(package_dir)))
    return archive_path


def validate_template_contract(
    package_dir: Path,
    *,
    expected_renderer: str,
) -> tuple[list[str], list[str], dict[str, Any] | None]:
    errors: list[str] = []
    warnings: list[str] = []
    contract_path = package_dir / "template_contract.json"
    if not contract_path.exists():
        errors.append("template_contract.json is missing.")
        return errors, warnings, None

    try:
        contract = load_json(contract_path)
    except json.JSONDecodeError as exc:
        errors.append(f"template_contract.json is invalid JSON: {exc}")
        return errors, warnings, None

    renderer = contract.get("renderer")
    if renderer != expected_renderer:
        errors.append(
            f"template_contract.json renderer must be `{expected_renderer}`, found `{renderer}`."
        )

    package_summary = contract.get("package_summary")
    slots = contract.get("slots")
    if not isinstance(package_summary, dict):
        errors.append("template_contract.json must contain package_summary.")
    if not isinstance(slots, list):
        errors.append("template_contract.json must contain slots[].")
        return errors, warnings, contract

    slot_ids: set[str] = set()
    text_slot_count = 0
    media_slot_count = 0
    for index, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            errors.append(f"template_contract slot {index} must be an object.")
            continue
        slot_id = slot.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id:
            errors.append(f"template_contract slot {index} requires slot_id.")
            continue
        if slot_id in slot_ids:
            errors.append(f"template_contract duplicate slot_id: {slot_id}")
        slot_ids.add(slot_id)

        kind = slot.get("kind")
        if kind not in SUPPORTED_SLOT_KINDS:
            errors.append(f"template_contract slot {slot_id} has unsupported kind `{kind}`.")
        fill_strategy = slot.get("fill_strategy")
        if fill_strategy not in CONTENT_FILL_STRATEGIES:
            errors.append(
                f"template_contract slot {slot_id} has unsupported fill_strategy `{fill_strategy}`."
            )
        renderer_binding = slot.get("renderer_binding")
        if not isinstance(renderer_binding, dict):
            errors.append(f"template_contract slot {slot_id} requires renderer_binding.")
        elif expected_renderer == "shotstack":
            merge_key = renderer_binding.get("merge_key")
            if not isinstance(merge_key, str) or not merge_key:
                errors.append(
                    f"template_contract slot {slot_id} requires renderer_binding.merge_key."
                )
        elif expected_renderer == "remotion":
            prop_path = renderer_binding.get("prop_path")
            if not isinstance(prop_path, str) or not prop_path:
                errors.append(
                    f"template_contract slot {slot_id} requires renderer_binding.prop_path."
                )

        if kind == "text":
            text_slot_count += 1
        if kind in {"media", "overlay", "audio"}:
            media_slot_count += 1

    if isinstance(package_summary, dict):
        expected_slot_count = package_summary.get("slot_count")
        expected_text_slot_count = package_summary.get("text_slot_count")
        expected_media_slot_count = package_summary.get("media_slot_count")
        summary_renderer = package_summary.get("renderer")
        if expected_slot_count != len(slots):
            errors.append("template_contract package_summary.slot_count does not match slots[].")
        if expected_text_slot_count != text_slot_count:
            errors.append(
                "template_contract package_summary.text_slot_count does not match text slots."
            )
        if expected_media_slot_count != media_slot_count:
            errors.append(
                "template_contract package_summary.media_slot_count does not match media slots."
            )
        if summary_renderer != expected_renderer:
            errors.append(
                "template_contract package_summary.renderer does not match package renderer."
            )

    return errors, warnings, contract
