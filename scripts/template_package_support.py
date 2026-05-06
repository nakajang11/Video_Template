#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


TEMPLATE_CONTRACT_VERSION = "1.2"
SUPPORTED_RENDERERS = {"shotstack", "remotion", "hyperframes", "hybrid"}
TEMPLATE_TYPE_BY_CATEGORY = {
    "single": "A-7_trend_single",
    "continue": "A-6_trend_continue",
}
CONTENT_FILL_STRATEGIES = {
    "keep_locked",
    "reuse_template_asset",
    "select_existing_asset",
    "generate_startframe",
    "generate_image_slot",
    "generate_video_slot",
    "generate_text",
    "precompose_video",
    "reuse_source_trend_video",
}
SUPPORTED_SLOT_KINDS = {"media", "text", "color", "number", "audio", "overlay"}
HYPERFRAMES_FORBIDDEN_GENERATION_VALUES = {"hyperframes", "hyperframes_package", "hyperframes_renderer"}
HYBRID_INNER_RENDERERS = {"remotion", "hyperframes"}
HYBRID_PRECOMPOSE_AUDIO_POLICIES = {"mute", "strip"}
HYBRID_PRECOMPOSE_STATUSES = {
    "planned",
    "package_created",
    "pending_render",
    "blocked",
    "rendered",
}
PRECOMPOSE_BLOCKER_CODES = {
    "missing_precompose_output",
    "pending_adult_ai_materialization",
    "missing_input_slot",
    "missing_output_slot",
    "invalid_renderer_binding",
    "render_output_not_approved",
}
HYBRID_FORBIDDEN_RENDER_KEYS = {
    "final_video",
    "output_file",
    "output_path",
    "provider_response",
    "render_url",
    "rendered_file",
    "rendered_url",
}
HYBRID_DURATION_TOLERANCE_SEC = 0.05
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
ADULT_AI_TEMPLATE_CONSUMER_PROFILE = "adult_ai_influencer_template"
ADULT_AI_INFLUENCER_CONSUMER_PROFILE = "adult_ai_influencer_media_template"
ADULT_AI_INFLUENCER_CONSUMER_PROFILES = {
    ADULT_AI_TEMPLATE_CONSUMER_PROFILE,
    ADULT_AI_INFLUENCER_CONSUMER_PROFILE,
}
ADULT_AI_TEMPLATE_CONTRACT_SCHEMA_VERSION = "adult_ai_influencer_template_contract.v1"
ASSEMBLY_FLOW_SUGGESTION_SCHEMA_VERSION = "media_template_assembly_suggestion.v1"
ASSEMBLY_FLOW_SCHEMA_VERSION = "media_template_assembly.v1"
ADULT_ASSEMBLY_CONTRACT_SCHEMA_VERSION = "adult_ai_influencer_assembly_contract.v1"
ADULT_ASSEMBLY_REQUIRED_SOURCE_INPUTS = [
    "b_wardrobe_image",
    "room_asset",
    "base_image",
    "source_audio",
]
ADULT_ASSEMBLY_ALLOWED_STEP_TARGETS = [
    "asset_select",
    "image_prompt",
    "image_generate",
    "video_prompt",
    "video_generate",
    "assemble",
    "validate",
]
ADULT_ASSEMBLY_ALLOWED_TOKENS = [
    "{{b_wardrobe_image.front_url}}",
    "{{room_asset.url}}",
    "{{base_image.url}}",
    "{{identity_pack.base_upscaled_url}}",
    "{{source_scene_001.start_frame_url}}",
    "{{source_audio.url}}",
]
SENSITIVE_CONTEXT_PATH_PARTS = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
}
URL_VALUE_RE = re.compile(r"https?://", re.IGNORECASE)
LOCAL_ABSOLUTE_PATH_RE = re.compile(r"^(?:/|[A-Za-z]:[\\/])")
TOKEN_ONLY_RE = re.compile(r"^\{\{\s*[A-Za-z0-9_.\[\] -]+\s*\}\}$")
MERGE_KEY_RE = re.compile(r"^[A-Z0-9_]+$")
FORBIDDEN_SUGGESTION_KEYS = {
    "api_key",
    "adult_db_id",
    "cloudinary_url",
    "database_id",
    "db_id",
    "generated_media_url",
    "generated_url",
    "output_artifacts",
    "output_url",
    "provider_response",
    "provider_result",
    "provider_url",
    "resolved_url",
    "resolved_urls",
    "resolved_tool_inputs",
    "secret",
    "secure_url",
}
FORBIDDEN_SUGGESTION_KEY_PARTS = {
    "cloudinary",
    "generated_media_url",
    "generated_url",
    "output_artifact",
    "output_url",
    "provider_response",
    "provider_result",
    "resolved_tool_input",
}


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
        if URL_VALUE_RE.search(collapsed):
            return "[redacted-url]"
        if re.search(r"\b(?:sk-|api[_-]?key|secret|password)\b", collapsed, re.IGNORECASE):
            return "[redacted-secret]"
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
    selected = [
        (path, value)
        for path, value in selected
        if not any(part in path.lower() for part in SENSITIVE_CONTEXT_PATH_PARTS)
    ]

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


def resolve_consumer_profile(
    raw_context: Any,
    *,
    cli_consumer_profile: str | None = None,
) -> str | None:
    cli_profile = _stringify_scalar(cli_consumer_profile)
    context_profile = None
    if isinstance(raw_context, dict):
        context_profile = _stringify_scalar(raw_context.get("consumer_profile"))

    if cli_profile and context_profile and cli_profile != context_profile:
        raise ValueError(
            f"consumer_profile mismatch: CLI `{cli_profile}` does not match context `{context_profile}`."
        )

    profile = cli_profile or context_profile
    if profile and profile not in ADULT_AI_INFLUENCER_CONSUMER_PROFILES:
        raise ValueError(f"Unsupported consumer_profile: {profile}")
    return profile


def _safe_token(value: Any) -> str | None:
    token = _stringify_scalar(value)
    if not isinstance(token, str) or not TOKEN_ONLY_RE.match(token):
        return None
    if URL_VALUE_RE.search(token) or LOCAL_ABSOLUTE_PATH_RE.match(token):
        return None
    return token


def _safe_token_list(values: Any, *, max_items: int = 24) -> list[str]:
    if not isinstance(values, list):
        return []
    tokens: list[str] = []
    for value in values:
        token = _safe_token(value)
        if token is not None and token not in tokens:
            tokens.append(token)
        if len(tokens) >= max_items:
            break
    return tokens


def _safe_string_list(values: Any, *, allowed: set[str], max_items: int = 32) -> list[str]:
    if not isinstance(values, list):
        return []
    selected: list[str] = []
    for value in values:
        item = _stringify_scalar(value)
        if isinstance(item, str) and item in allowed and item not in selected:
            selected.append(item)
        if len(selected) >= max_items:
            break
    return selected


def _safe_source_scene_binding_hints(raw_context: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_context, dict):
        return []
    hints = raw_context.get("source_scene_binding_hints")
    if not isinstance(hints, list):
        return []
    safe_hints: list[dict[str, Any]] = []
    for item in hints[:12]:
        if not isinstance(item, dict):
            continue
        scene_id = _stringify_scalar(item.get("scene_id"))
        source_role = _stringify_scalar(item.get("source_role"))
        token = _safe_token(item.get("token"))
        if not scene_id or not source_role or not token:
            continue
        safe_hints.append(
            {
                "scene_id": scene_id,
                "source_role": source_role,
                "token": token,
            }
        )
    return safe_hints


def build_consumer_profile_prompt_context(
    raw_context: Any,
    *,
    consumer_profile: str | None,
    caller_context_echo: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if consumer_profile == ADULT_AI_TEMPLATE_CONSUMER_PROFILE:
        return {
            "consumer_profile": consumer_profile,
            "expected_artifact": "adult_ai_influencer_template_contract.json",
            "source_contract": "template_contract.json",
            "contract_version": TEMPLATE_CONTRACT_VERSION,
            "tokenized_refs_only": True,
            "runtime_boundary": {
                "adult_db_lookup": False,
                "cloudinary_resolution": False,
                "provider_calls": False,
                "paid_generation": False,
                "rendering": False,
            },
            "known_template_type": infer_template_type(raw_context, caller_context_echo),
        }

    if consumer_profile != ADULT_AI_INFLUENCER_CONSUMER_PROFILE:
        return None

    assembly_contract = raw_context.get("assembly_contract") if isinstance(raw_context, dict) else None
    assembly_contract_summary: dict[str, Any] = {}
    if isinstance(assembly_contract, dict):
        schema_version = _stringify_scalar(assembly_contract.get("schema_version"))
        if schema_version:
            assembly_contract_summary["schema_version"] = schema_version

    template_type = infer_template_type(raw_context, caller_context_echo)
    allowed_tokens = list(ADULT_ASSEMBLY_ALLOWED_TOKENS)
    if isinstance(raw_context, dict):
        for token in _safe_token_list(raw_context.get("allowed_tokens")):
            if token not in allowed_tokens:
                allowed_tokens.append(token)

    allowed_targets = list(ADULT_ASSEMBLY_ALLOWED_STEP_TARGETS)
    if isinstance(raw_context, dict):
        requested_targets = _safe_string_list(
            raw_context.get("allowed_target_step_types"),
            allowed=set(ADULT_ASSEMBLY_ALLOWED_STEP_TARGETS),
        )
        if requested_targets:
            allowed_targets = requested_targets

    return {
        "consumer_profile": consumer_profile,
        "assembly_contract": assembly_contract_summary,
        "allowed_tokens": allowed_tokens,
        "allowed_target_step_types": allowed_targets,
        "required_source_input_roles": list(ADULT_ASSEMBLY_REQUIRED_SOURCE_INPUTS),
        "known_template_type": template_type,
        "source_scene_binding_hints": _safe_source_scene_binding_hints(raw_context),
    }


def render_consumer_profile_prompt_block(context: dict[str, Any] | None) -> str:
    if not context:
        return "none"
    return json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)


def _tokenize_prop_path(path: str) -> list[str]:
    tokens: list[str] = []
    for name, index in PROP_TOKEN_RE.findall(path):
        if name:
            tokens.append(name)
        elif index:
            tokens.append(index)
    return tokens


def _camel_to_snake(value: str) -> str:
    if value.upper() == value:
        return value.lower()
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


def _slot_media_kind(kind: str, media_kind: Any = None) -> str | None:
    if kind == "audio":
        return "audio"
    if kind in {"text", "color", "number"}:
        return None
    if isinstance(media_kind, str) and media_kind in {"image", "video", "audio", "thumbnail"}:
        return media_kind
    if kind in {"media", "overlay"}:
        return "image"
    return None


def _slot_generation_policy(
    *,
    model_route: Any = None,
    prompt_file: Any = None,
    reference_assets: Any = None,
    renderer_use: str | None = None,
) -> dict[str, Any]:
    if isinstance(model_route, str) and model_route in HYPERFRAMES_FORBIDDEN_GENERATION_VALUES:
        model_route = None
    return {
        "model_route": model_route if isinstance(model_route, str) and model_route else None,
        "prompt_file": prompt_file if isinstance(prompt_file, str) and prompt_file else None,
        "reference_assets": reference_assets if isinstance(reference_assets, list) else [],
        "renderer_use": renderer_use,
    }


def _slot_approval_policy(fill_strategy: str, *, required: bool = True) -> dict[str, Any]:
    requires_slot_approval = fill_strategy not in {
        "keep_locked",
        "reuse_template_asset",
        "reuse_source_trend_video",
    }
    return {
        "requires_slot_approval": bool(required and requires_slot_approval),
        "approval_type": "post_template_slot" if requires_slot_approval else "not_required",
    }


def _slot_validation(*, warnings: list[str] | None = None, blocking: list[str] | None = None) -> dict[str, Any]:
    return {
        "warnings": warnings or [],
        "blocking": blocking or [],
    }


def _enrich_slot_v12(slot: dict[str, Any], *, renderer_use: str | None = None) -> dict[str, Any]:
    kind = str(slot.get("kind") or "")
    fill_strategy = str(slot.get("fill_strategy") or "")
    slot["media_kind"] = _slot_media_kind(kind, slot.get("media_kind"))
    slot.setdefault(
        "generation_policy",
        _slot_generation_policy(renderer_use=renderer_use),
    )
    slot.setdefault(
        "approval_policy",
        _slot_approval_policy(fill_strategy, required=bool(slot.get("required", True))),
    )
    slot.setdefault("validation", _slot_validation())
    return slot


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


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _compact_precompose_binding(precompose: dict[str, Any]) -> dict[str, Any]:
    binding: dict[str, Any] = {}
    for key in (
        "renderer",
        "package_dir",
        "output_merge_key",
        "width",
        "height",
        "fps",
        "duration_sec",
        "audio_policy",
        "status",
    ):
        if key in precompose:
            binding[key] = precompose[key]
    return binding


def validate_hybrid_precompose_blueprint(
    blueprint: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if blueprint.get("renderer") != "hybrid":
        return errors, warnings

    scenes = blueprint.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("hybrid blueprint requires a non-empty scenes array")
        return errors, warnings

    precompose_count = 0
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            errors.append(f"hybrid scene {index} must be an object")
            continue
        scene_id = scene.get("scene_id")
        scene_label = scene_id if isinstance(scene_id, str) and scene_id else f"scene {index}"
        shotstack = scene.get("shotstack")
        if not isinstance(shotstack, dict):
            errors.append(f"{scene_label}: hybrid scenes require shotstack final assembly binding")
            continue

        precompose = scene.get("precompose")
        if precompose is None:
            continue
        if not isinstance(precompose, dict):
            errors.append(f"{scene_label}: precompose must be an object")
            continue
        precompose_count += 1

        inner_renderer = precompose.get("renderer")
        if inner_renderer not in HYBRID_INNER_RENDERERS:
            errors.append(f"{scene_label}: precompose.renderer must be `remotion` or `hyperframes`")

        output_merge_key = precompose.get("output_merge_key")
        if not isinstance(output_merge_key, str) or not MERGE_KEY_RE.match(output_merge_key):
            errors.append(f"{scene_label}: precompose.output_merge_key must be uppercase snake case")
        elif shotstack.get("merge_key") != output_merge_key:
            errors.append(f"{scene_label}: precompose.output_merge_key must match shotstack.merge_key")

        package_dir = precompose.get("package_dir")
        if not isinstance(package_dir, str) or not package_dir:
            errors.append(f"{scene_label}: precompose.package_dir must be a non-empty relative path")
        elif LOCAL_ABSOLUTE_PATH_RE.match(package_dir) or ".." in Path(package_dir).parts:
            errors.append(f"{scene_label}: precompose.package_dir must stay inside the package")
        elif not package_dir.startswith("precompose/"):
            warnings.append(f"{scene_label}: precompose.package_dir should live under precompose/")

        for numeric_key in ("width", "height", "fps", "duration_sec"):
            if not _is_positive_number(precompose.get(numeric_key)):
                errors.append(f"{scene_label}: precompose.{numeric_key} must be a positive number")

        duration = scene.get("duration_sec")
        precompose_duration = precompose.get("duration_sec")
        if _is_positive_number(duration) and _is_positive_number(precompose_duration):
            if abs(float(duration) - float(precompose_duration)) > HYBRID_DURATION_TOLERANCE_SEC:
                errors.append(f"{scene_label}: precompose.duration_sec must match duration_sec")

        audio_policy = precompose.get("audio_policy")
        if audio_policy not in HYBRID_PRECOMPOSE_AUDIO_POLICIES:
            errors.append(f"{scene_label}: precompose.audio_policy must be `mute` or `strip`")

        status = precompose.get("status")
        if status not in HYBRID_PRECOMPOSE_STATUSES:
            errors.append(
                f"{scene_label}: precompose.status must be planned, package_created, pending_render, blocked, or rendered"
            )
        elif status == "rendered":
            errors.append(f"{scene_label}: precompose.status cannot be rendered without explicit render approval")

        forbidden_keys = sorted(
            key for key in HYBRID_FORBIDDEN_RENDER_KEYS if precompose.get(key) not in (None, "")
        )
        if forbidden_keys:
            errors.append(
                f"{scene_label}: precompose metadata implies rendered output without approval: {', '.join(forbidden_keys)}"
            )

    if precompose_count == 0:
        errors.append("hybrid blueprint requires at least one scene.precompose object")
    return errors, warnings


def _derive_shotstack_media_fill_strategy(scene: dict[str, Any]) -> str:
    if isinstance(scene.get("precompose"), dict):
        return "precompose_video"

    video = scene.get("video")
    startframe = scene.get("startframe")
    video_mode = video.get("mode") if isinstance(video, dict) else None
    startframe_required = startframe.get("required") if isinstance(startframe, dict) else False

    if video_mode == "input-extract":
        return "reuse_source_trend_video"
    if video_mode in {"generate", "motion-control", "reuse-generated"}:
        return "generate_video_slot"
    if startframe_required is True:
        return "generate_startframe"
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
                _enrich_slot_v12(
                    {
                    "slot_id": _build_slot_id(None, "audio", "source"),
                    "scene_id": None,
                    "kind": "audio",
                    "media_kind": "audio",
                    "required": True,
                    "fill_strategy": "reuse_source_trend_video",
                    "generation_policy": _slot_generation_policy(
                        renderer_use="source_audio",
                    ),
                    "renderer_binding": {
                        "merge_key": merge_key,
                        "source_file": audio.get("source_file"),
                    },
                    },
                    renderer_use="shotstack",
                )
            )

    for scene in blueprint.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        shotstack = scene.get("shotstack")
        if not isinstance(scene_id, str) or not isinstance(shotstack, dict):
            continue

        startframe = scene.get("startframe")
        if isinstance(startframe, dict) and startframe.get("required") is True:
            slots.append(
                _enrich_slot_v12(
                    {
                        "slot_id": _build_slot_id(scene_id, "media", "startframe"),
                        "scene_id": scene_id,
                        "kind": "media",
                        "media_kind": "image",
                        "required": True,
                        "fill_strategy": "generate_startframe",
                        "generation_policy": _slot_generation_policy(
                            model_route=startframe.get("model"),
                            prompt_file=startframe.get("prompt_file"),
                            reference_assets=startframe.get("reference_assets"),
                            renderer_use="startframe_generation",
                        ),
                        "renderer_binding": {
                            "role": "startframe_input",
                            "prompt_file": startframe.get("prompt_file"),
                        },
                    },
                    renderer_use="shotstack",
                )
            )

        merge_key = shotstack.get("merge_key")
        if isinstance(merge_key, str) and merge_key:
            media_kind = shotstack.get("asset_type")
            suffix = "main"
            renderer_binding = {
                "merge_key": merge_key,
                "alias": shotstack.get("alias"),
            }
            precompose = scene.get("precompose")
            if isinstance(precompose, dict):
                renderer_binding["precompose"] = _compact_precompose_binding(precompose)
            video = scene.get("video") if isinstance(scene.get("video"), dict) else {}
            slots.append(
                _enrich_slot_v12(
                    {
                    "slot_id": _build_slot_id(scene_id, "media", suffix),
                    "scene_id": scene_id,
                    "kind": "media",
                    "media_kind": media_kind if isinstance(media_kind, str) else None,
                    "required": True,
                    "fill_strategy": _derive_shotstack_media_fill_strategy(scene),
                    "generation_policy": _slot_generation_policy(
                        model_route=video.get("model") if isinstance(video, dict) else None,
                        prompt_file=video.get("prompt_file") if isinstance(video, dict) else None,
                        reference_assets=video.get("reference_assets") if isinstance(video, dict) else None,
                        renderer_use="shotstack_final_media",
                    ),
                    "renderer_binding": renderer_binding,
                    },
                    renderer_use="shotstack",
                )
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
                "media_kind": None,
                "required": True,
                "fill_strategy": "generate_text",
                "generation_policy": _slot_generation_policy(
                    renderer_use="editable_text",
                ),
                "renderer_binding": {
                    "merge_key": text_key,
                    "placement": overlay.get("placement"),
                },
            }
            constraints = _style_constraints_from_text_overlay(overlay)
            if constraints is not None:
                slot["style_constraints"] = constraints
            slots.append(_enrich_slot_v12(slot, renderer_use="shotstack"))

        for overlay_index, overlay in enumerate(shotstack.get("overlay_layers", []), start=1):
            if not isinstance(overlay, dict):
                continue
            overlay_merge_key = overlay.get("merge_key")
            if not isinstance(overlay_merge_key, str) or not overlay_merge_key:
                continue
            slots.append(
                _enrich_slot_v12(
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
                    },
                    renderer_use="shotstack",
                )
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
            "media_kind": _slot_media_kind(kind),
            "required": True,
            "fill_strategy": fill_strategy,
            "generation_policy": _slot_generation_policy(renderer_use="remotion_props"),
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
        slots.append(_enrich_slot_v12(slot, renderer_use="remotion"))

    audio_file = default_props.get("audioFile") if isinstance(default_props, dict) else None
    if isinstance(audio_file, str):
        slots.append(
            _enrich_slot_v12(
                {
                "slot_id": _build_slot_id(None, "audio", "source"),
                "scene_id": None,
                "kind": "audio",
                "media_kind": "audio",
                "required": True,
                "fill_strategy": (
                    "reuse_source_trend_video"
                    if audio_file == "source_audio.mp3"
                    else "select_existing_asset"
                ),
                "generation_policy": _slot_generation_policy(renderer_use="remotion_audio"),
                "renderer_binding": {
                    "prop_path": "audioFile",
                    "default_value": audio_file,
                },
                },
                renderer_use="remotion",
            )
        )

    return slots


def derive_hyperframes_slots(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    hyperframes_package = blueprint.get("hyperframes_package")
    if not isinstance(hyperframes_package, dict):
        hyperframes_package = {}

    raw_bindings = hyperframes_package.get("slot_bindings")
    if isinstance(raw_bindings, dict):
        binding_items = [
            {"slot_id": slot_id, "graph_ref": graph_ref}
            for slot_id, graph_ref in raw_bindings.items()
        ]
    elif isinstance(raw_bindings, list):
        binding_items = [item for item in raw_bindings if isinstance(item, dict)]
    else:
        binding_items = []

    for index, binding in enumerate(binding_items, start=1):
        slot_id = binding.get("slot_id")
        kind = binding.get("kind", "media")
        if kind not in SUPPORTED_SLOT_KINDS:
            kind = "media"
        if not isinstance(slot_id, str) or not slot_id:
            scene_id = binding.get("scene_id")
            suffix = binding.get("role") or f"slot_{index:03d}"
            slot_id = _build_slot_id(scene_id if isinstance(scene_id, str) else None, str(kind), str(suffix))
        fill_strategy = binding.get("fill_strategy")
        if fill_strategy not in CONTENT_FILL_STRATEGIES:
            fill_strategy = "select_existing_asset" if kind in {"media", "overlay", "audio"} else "generate_text"
        slot = {
            "slot_id": slot_id,
            "scene_id": binding.get("scene_id") if isinstance(binding.get("scene_id"), str) else None,
            "kind": kind,
            "media_kind": _slot_media_kind(str(kind), binding.get("media_kind")),
            "required": bool(binding.get("required", True)),
            "fill_strategy": fill_strategy,
            "generation_policy": _slot_generation_policy(
                model_route=binding.get("model_route"),
                prompt_file=binding.get("prompt_file"),
                reference_assets=binding.get("reference_assets"),
                renderer_use="hyperframes_input",
            ),
            "renderer_binding": {
                "graph_ref": binding.get("graph_ref") or binding.get("node_ref"),
                "node_id": binding.get("node_id"),
                "input_path": binding.get("input_path"),
                "package_dir": hyperframes_package.get("package_dir", "hyperframes_package"),
            },
        }
        slots.append(_enrich_slot_v12(slot, renderer_use="hyperframes"))

    if not slots:
        for scene in blueprint.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = scene.get("scene_id")
            if not isinstance(scene_id, str):
                continue
            slots.append(
                _enrich_slot_v12(
                    {
                        "slot_id": _build_slot_id(scene_id, "media", "main"),
                        "scene_id": scene_id,
                        "kind": "media",
                        "media_kind": "image",
                        "required": True,
                        "fill_strategy": "select_existing_asset",
                        "generation_policy": _slot_generation_policy(
                            renderer_use="hyperframes_input",
                        ),
                        "renderer_binding": {
                            "graph_ref": f"nodes.{scene_id}.asset",
                            "package_dir": hyperframes_package.get("package_dir", "hyperframes_package"),
                        },
                    },
                    renderer_use="hyperframes",
                )
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


def _infer_duration_seconds(blueprint: dict[str, Any]) -> float | None:
    total = 0.0
    seen = False
    for scene in blueprint.get("scenes", []):
        if isinstance(scene, dict) and isinstance(scene.get("duration_sec"), (int, float)):
            total += float(scene["duration_sec"])
            seen = True
    return round(total, 3) if seen else None


def _infer_aspect_ratio(blueprint: dict[str, Any]) -> str:
    for key in ("aspect_ratio", "aspectRatio"):
        value = blueprint.get(key)
        if isinstance(value, str) and value:
            return value
    for package_key in ("remotion_package", "hyperframes_package"):
        package = blueprint.get(package_key)
        if isinstance(package, dict):
            value = package.get("aspect_ratio") or package.get("aspectRatio")
            if isinstance(value, str) and value:
                return value
    return "9:16"


def _build_renderer_bindings(renderer: str, slots: list[dict[str, Any]]) -> dict[str, Any]:
    bindings: dict[str, Any] = {
        "renderer": renderer,
        "slot_bindings": {},
    }
    for slot in slots:
        slot_id = slot.get("slot_id")
        binding = slot.get("renderer_binding")
        if not isinstance(slot_id, str) or not isinstance(binding, dict):
            continue
        if renderer in {"shotstack", "hybrid"} and isinstance(binding.get("merge_key"), str):
            bindings["slot_bindings"][slot_id] = {"merge_key": binding["merge_key"]}
        elif renderer == "remotion" and isinstance(binding.get("prop_path"), str):
            bindings["slot_bindings"][slot_id] = {"prop_path": binding["prop_path"]}
        elif renderer == "hyperframes":
            bindings["slot_bindings"][slot_id] = {
                key: value
                for key, value in {
                    "graph_ref": binding.get("graph_ref"),
                    "node_id": binding.get("node_id"),
                    "input_path": binding.get("input_path"),
                }.items()
                if value not in (None, "")
            }
    return bindings


def _build_precompose_plan(blueprint: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    slot_ids = {slot.get("slot_id") for slot in slots if isinstance(slot.get("slot_id"), str)}
    slots_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slot in slots:
        scene_id = slot.get("scene_id")
        if isinstance(scene_id, str):
            slots_by_scene[scene_id].append(slot)

    steps: list[dict[str, Any]] = []
    for scene in blueprint.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        precompose = scene.get("precompose")
        if not isinstance(scene_id, str) or not isinstance(precompose, dict):
            continue
        output_slot = _build_slot_id(scene_id, "media", "main")
        input_slots = [
            slot["slot_id"]
            for slot in slots_by_scene.get(scene_id, [])
            if slot.get("slot_id") != output_slot
            and slot.get("fill_strategy") != "precompose_video"
        ]
        blockers: list[dict[str, str]] = []
        status = precompose.get("status") if isinstance(precompose.get("status"), str) else "planned"
        if output_slot not in slot_ids:
            blockers.append({"code": "missing_output_slot", "message": f"Missing output slot {output_slot}."})
        if status != "rendered":
            blockers.append(
                {
                    "code": "missing_precompose_output",
                    "message": "Precompose output is not rendered in this review-gated package.",
                }
            )
            blockers.append(
                {
                    "code": "pending_adult_ai_materialization",
                    "message": "Adult AI must materialize and approve the precompose output before final render.",
                }
            )
        steps.append(
            {
                "step_id": f"precompose_{scene_id}",
                "renderer": precompose.get("renderer"),
                "input_slots": input_slots,
                "output_slot": output_slot,
                "package_dir": precompose.get("package_dir"),
                "required": True,
                "status": status,
                "blockers": blockers,
            }
        )
    return {"steps": steps}


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

    if renderer == "remotion":
        slots = derive_remotion_slots(blueprint, default_props, template_partition)
    elif renderer == "hyperframes":
        slots = derive_hyperframes_slots(blueprint)
    else:
        slots = derive_shotstack_slots(blueprint)

    scene_count = len(blueprint.get("scene_order", [])) if isinstance(blueprint.get("scene_order"), list) else len(blueprint.get("scenes", []))
    template_type = infer_template_type(caller_context, caller_context_echo)
    package_summary = build_package_summary_from_slots(
        renderer=renderer,
        scene_count=scene_count,
        slots=slots,
    )
    precompose_plan = _build_precompose_plan(blueprint, slots)
    precompose_required = bool(precompose_plan["steps"]) or any(
        slot.get("fill_strategy") == "precompose_video" for slot in slots
    )
    fill_requirements = {
        "requires_generated_media": any(
            slot.get("fill_strategy") in {"generate_startframe", "generate_image_slot", "generate_video_slot"}
            for slot in slots
        ),
        "requires_precompose_video": any(
            slot.get("fill_strategy") == "precompose_video" for slot in slots
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

    preferred_renderer = (
        caller_context_echo.get("preferred_renderer")
        if isinstance(caller_context_echo, dict)
        else renderer
    )
    if preferred_renderer not in SUPPORTED_RENDERERS:
        preferred_renderer = renderer

    contract = {
        "contract_version": TEMPLATE_CONTRACT_VERSION,
        "job_id": blueprint.get("job_id"),
        "template_id": blueprint.get("template_id") or f"{template_type or 'template'}:{blueprint.get('job_id')}",
        "renderer": renderer,
        "preferred_renderer": preferred_renderer,
        "fallback_renderers": blueprint.get("fallback_renderers", []),
        "template_type": template_type,
        "aspect_ratio": _infer_aspect_ratio(blueprint),
        "duration_seconds": _infer_duration_seconds(blueprint),
        "precompose_required": precompose_required,
        "supported_content_types": infer_supported_content_types(template_type),
        "fill_requirements": fill_requirements,
        "renderer_bindings": _build_renderer_bindings(renderer, slots),
        "precompose_plan": precompose_plan,
        "consumer_profiles": {},
        "validation": _slot_validation(),
        "package_summary": package_summary,
        "slots": slots,
    }
    if template_type is None:
        contract["notes"] = [
            "template_type could not be inferred from caller context or category mapping."
        ]
    return contract


def _source_scene_token_for_scene(scene_id: str, index: int) -> tuple[str, str]:
    match = re.search(r"(\d+)$", scene_id)
    suffix = match.group(1).zfill(3) if match else f"{index:03d}"
    source_scene_key = f"source_scene_{suffix}"
    return source_scene_key, f"{{{{{source_scene_key}.start_frame_url}}}}"


def _scene_ids_from_package(package_dir: Path) -> list[str]:
    scene_ids: list[str] = []
    blueprint_path = package_dir / "blueprint.json"
    analysis_path = package_dir / "analysis.json"

    blueprint = load_json(blueprint_path) if blueprint_path.exists() else None
    if isinstance(blueprint, dict):
        scene_order = blueprint.get("scene_order")
        if isinstance(scene_order, list):
            scene_ids.extend(
                scene_id
                for scene_id in scene_order
                if isinstance(scene_id, str) and scene_id
            )
        if not scene_ids:
            scenes = blueprint.get("scenes")
            if isinstance(scenes, list):
                scene_ids.extend(
                    scene.get("scene_id")
                    for scene in scenes
                    if isinstance(scene, dict)
                    and isinstance(scene.get("scene_id"), str)
                    and scene.get("scene_id")
                )

    if not scene_ids:
        analysis = load_json(analysis_path) if analysis_path.exists() else None
        scenes = analysis.get("scenes") if isinstance(analysis, dict) else None
        if isinstance(scenes, list):
            scene_ids.extend(
                scene.get("scene_id")
                for scene in scenes
                if isinstance(scene, dict)
                and isinstance(scene.get("scene_id"), str)
                and scene.get("scene_id")
            )

    if not scene_ids:
        scene_ids = ["scene_001"]

    unique_scene_ids: list[str] = []
    for scene_id in scene_ids:
        if scene_id not in unique_scene_ids:
            unique_scene_ids.append(scene_id)
    return unique_scene_ids


def _build_scene_assembly_steps(scene_id: str, index: int) -> list[dict[str, Any]]:
    source_scene_key, source_scene_token = _source_scene_token_for_scene(scene_id, index)
    image_prompt_key = f"{scene_id}_image_prompt"
    image_generate_key = f"{scene_id}_image_generate"
    video_prompt_key = f"{scene_id}_video_prompt"
    video_generate_key = f"{scene_id}_video_generate"
    reference_tokens = [
        source_scene_token,
        "{{b_wardrobe_image.front_url}}",
        "{{room_asset.url}}" if index == 1 else "{{base_image.url}}",
        "{{identity_pack.base_upscaled_url}}",
    ]

    return [
        {
            "step_key": image_prompt_key,
            "target": "image_prompt",
            "label": f"{scene_id} start-frame image prompt",
            "tool": "openrouter",
            "model": "google/gemini-3.1-flash-lite-preview",
            "inputs": [source_scene_key, "b_wardrobe_image", "room_asset", "base_image"],
            "prompt_role": (
                "Write an editable start-frame image prompt using only tokenized source "
                "references and the analyzed trend scene structure."
            ),
            "tool_inputs": {
                "image_urls": reference_tokens,
                "provider_params": {},
            },
            "editable": True,
            "execution": "handoff_only",
        },
        {
            "step_key": image_generate_key,
            "target": "image_generate",
            "label": f"{scene_id} start-frame image plan",
            "tool": "fal.ai",
            "model": "nano banana 2",
            "inputs": [image_prompt_key, source_scene_key, "b_wardrobe_image"],
            "tool_inputs": {
                "prompt": f"{{{{{image_prompt_key}.output.prompt}}}}",
                "image_urls": reference_tokens,
                "provider_params": {},
            },
            "execution": "handoff_only",
        },
        {
            "step_key": video_prompt_key,
            "target": "video_prompt",
            "label": f"{scene_id} motion prompt",
            "tool": "openrouter",
            "model": "google/gemini-3.1-flash-lite-preview",
            "inputs": [image_generate_key, source_scene_key],
            "prompt_role": (
                "Write a motion prompt that preserves the source scene rhythm and "
                "keeps generated media execution in the downstream system."
            ),
            "tool_inputs": {
                "image_url": f"{{{{{image_generate_key}.output.image_url}}}}",
                "provider_params": {},
            },
            "editable": True,
            "execution": "handoff_only",
        },
        {
            "step_key": video_generate_key,
            "target": "video_generate",
            "label": f"{scene_id} video generation plan",
            "tool": "fal.ai",
            "model": "kling v3",
            "inputs": [video_prompt_key, image_generate_key],
            "tool_inputs": {
                "prompt": f"{{{{{video_prompt_key}.output.prompt}}}}",
                "image_url": f"{{{{{image_generate_key}.output.image_url}}}}",
                "provider_params": {},
            },
            "execution": "handoff_only",
        },
    ]


def build_assembly_flow_suggestion(
    package_dir: Path,
    *,
    consumer_profile: str | None,
    caller_context: Any = None,
    caller_context_echo: dict[str, Any] | None = None,
    template_contract: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if consumer_profile != ADULT_AI_INFLUENCER_CONSUMER_PROFILE:
        return None

    review_flags: list[str] = []
    template_type = None
    if isinstance(template_contract, dict):
        template_type = _stringify_scalar(template_contract.get("template_type"))
    template_type = template_type or infer_template_type(caller_context, caller_context_echo)
    if not template_type:
        template_type = "A-6_trend_continue"
        review_flags.append("template_type_defaulted")
    elif template_type != "A-6_trend_continue":
        review_flags.append("template_type_not_a6_v1")

    scene_ids = _scene_ids_from_package(package_dir)
    source_scene_bindings = []
    for index, scene_id in enumerate(scene_ids, start=1):
        _, token = _source_scene_token_for_scene(scene_id, index)
        source_scene_bindings.append(
            {
                "scene_id": scene_id,
                "source_role": "source_start_frame",
                "token": token,
            }
        )

    steps: list[dict[str, Any]] = [
        {
            "step_key": "select_assets",
            "target": "asset_select",
            "label": "Select Adult-side source assets",
            "tool": "manual",
            "asset_source": "wardrobe",
            "wardrobe_type": "B",
            "selection_mode": "random",
            "unused_only": True,
            "bind_as": "b_wardrobe_image",
            "selection_policy": {
                "asset_source": "wardrobe",
                "wardrobe_type": "B",
                "selection_mode": "random",
                "unused_only": True,
                "bind_as": "b_wardrobe_image",
            },
            "outputs": list(ADULT_ASSEMBLY_REQUIRED_SOURCE_INPUTS),
            "execution": "downstream_only",
        }
    ]
    for index, scene_id in enumerate(scene_ids, start=1):
        steps.extend(_build_scene_assembly_steps(scene_id, index))
    steps.extend(
        [
            {
                "step_key": "assemble_video",
                "target": "assemble",
                "label": "Assemble renderer package",
                "tool": "manual",
                "renderer": "shotstack",
                "inputs": [
                    *[f"{scene_id}_video_generate" for scene_id in scene_ids],
                    "source_audio",
                ],
                "tool_inputs": {
                    "audio_url": "{{source_audio.url}}",
                },
                "execution": "review_gate",
            },
            {
                "step_key": "validate_package",
                "target": "validate",
                "label": "Validate before downstream handoff",
                "tool": "manual",
                "checks": [
                    "required_inputs",
                    "renderer_bindings",
                    "no_paid_generation",
                    "no_resolved_urls",
                ],
                "execution": "review_gate",
            },
        ]
    )

    return {
        "schema_version": ASSEMBLY_FLOW_SUGGESTION_SCHEMA_VERSION,
        "consumer_profile": ADULT_AI_INFLUENCER_CONSUMER_PROFILE,
        "template_type": template_type,
        "source_scene_bindings": source_scene_bindings,
        "required_source_inputs": list(ADULT_ASSEMBLY_REQUIRED_SOURCE_INPUTS),
        "suggested_flow": {
            "schema_version": ASSEMBLY_FLOW_SCHEMA_VERSION,
            "template_type": template_type,
            "renderer": "shotstack",
            "review_gate": True,
            "paid_generation": False,
            "steps": steps,
        },
        "safety": {
            "paid_generation": False,
            "provider_execution": False,
            "resolved_urls_allowed": False,
            "review_gate": True,
        },
        "review_flags": review_flags,
    }


def _iter_json_items(node: Any, path: str = "$"):
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            yield child_path, key, value
            yield from _iter_json_items(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}[{index}]"
            yield child_path, str(index), value
            yield from _iter_json_items(value, child_path)


def validate_assembly_flow_suggestion(payload: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["assembly_flow_suggestion.json must contain a JSON object."], warnings

    if payload.get("schema_version") != ASSEMBLY_FLOW_SUGGESTION_SCHEMA_VERSION:
        errors.append(
            "assembly_flow_suggestion.schema_version must be "
            f"`{ASSEMBLY_FLOW_SUGGESTION_SCHEMA_VERSION}`."
        )
    if payload.get("consumer_profile") != ADULT_AI_INFLUENCER_CONSUMER_PROFILE:
        errors.append(
            "assembly_flow_suggestion.consumer_profile must be "
            f"`{ADULT_AI_INFLUENCER_CONSUMER_PROFILE}`."
        )

    safety = payload.get("safety")
    if not isinstance(safety, dict):
        errors.append("assembly_flow_suggestion.safety must be an object.")
    else:
        expected_safety = {
            "paid_generation": False,
            "provider_execution": False,
            "resolved_urls_allowed": False,
            "review_gate": True,
        }
        for key, expected in expected_safety.items():
            if safety.get(key) is not expected:
                errors.append(f"assembly_flow_suggestion.safety.{key} must be {expected}.")

    suggested_flow = payload.get("suggested_flow")
    if not isinstance(suggested_flow, dict):
        errors.append("assembly_flow_suggestion.suggested_flow must be an object.")
    else:
        if suggested_flow.get("schema_version") != ASSEMBLY_FLOW_SCHEMA_VERSION:
            errors.append(
                "assembly_flow_suggestion.suggested_flow.schema_version must be "
                f"`{ASSEMBLY_FLOW_SCHEMA_VERSION}`."
            )
        if suggested_flow.get("paid_generation") is not False:
            errors.append("assembly_flow_suggestion.suggested_flow.paid_generation must be false.")
        if suggested_flow.get("review_gate") is not True:
            errors.append("assembly_flow_suggestion.suggested_flow.review_gate must be true.")
        steps = suggested_flow.get("steps")
        if not isinstance(steps, list):
            errors.append("assembly_flow_suggestion.suggested_flow.steps must be an array.")
        else:
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    errors.append(f"assembly_flow_suggestion step {index} must be an object.")
                    continue
                target = step.get("target")
                if target not in ADULT_ASSEMBLY_ALLOWED_STEP_TARGETS:
                    errors.append(
                        f"assembly_flow_suggestion step {index} has unsupported target `{target}`."
                    )

    for path, key, value in _iter_json_items(payload):
        normalized_key = key.lower()
        if normalized_key in FORBIDDEN_SUGGESTION_KEYS or any(
            part in normalized_key for part in FORBIDDEN_SUGGESTION_KEY_PARTS
        ):
            errors.append(f"assembly_flow_suggestion contains forbidden provider/result key at {path}.")
        if isinstance(value, str):
            if URL_VALUE_RE.search(value):
                errors.append(f"assembly_flow_suggestion contains a resolved URL at {path}.")
            if LOCAL_ABSOLUTE_PATH_RE.match(value) and not TOKEN_ONLY_RE.match(value):
                errors.append(f"assembly_flow_suggestion contains a local absolute path at {path}.")

    if not errors and payload.get("template_type") != "A-6_trend_continue":
        warnings.append("assembly_flow_suggestion v1 is optimized for A-6_trend_continue.")
    return errors, warnings


def _git_head_sha(package_dir: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _token_ref_for_slot(slot_id: str) -> str:
    token_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", slot_id)
    return f"{{{{slot.{token_id}}}}}"


def build_adult_ai_template_contract(
    package_dir: Path,
    *,
    template_contract: dict[str, Any],
) -> dict[str, Any]:
    slots = []
    for slot in template_contract.get("slots", []):
        if not isinstance(slot, dict):
            continue
        slot_id = slot.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id:
            continue
        generation_policy = slot.get("generation_policy") if isinstance(slot.get("generation_policy"), dict) else {}
        prompt_file = generation_policy.get("prompt_file")
        slots.append(
            {
                "slot_id": slot_id,
                "scene_id": slot.get("scene_id"),
                "kind": slot.get("kind"),
                "media_kind": slot.get("media_kind"),
                "required": slot.get("required", True),
                "fill_strategy": slot.get("fill_strategy"),
                "token_ref": _token_ref_for_slot(slot_id),
                "prompt_file": Path(prompt_file).name if isinstance(prompt_file, str) and prompt_file else None,
                "generation_policy": {
                    "model_route": generation_policy.get("model_route"),
                    "prompt_file": Path(prompt_file).name if isinstance(prompt_file, str) and prompt_file else None,
                    "renderer_use": generation_policy.get("renderer_use"),
                },
                "approval_policy": slot.get("approval_policy"),
                "renderer_binding": slot.get("renderer_binding"),
                "validation": slot.get("validation"),
            }
        )

    return {
        "consumer_profile": ADULT_AI_TEMPLATE_CONSUMER_PROFILE,
        "schema_version": ADULT_AI_TEMPLATE_CONTRACT_SCHEMA_VERSION,
        "contract_version": template_contract.get("contract_version"),
        "source": {
            "repo": "nakajang11/Video_Template",
            "commit": _git_head_sha(package_dir),
            "job_id": template_contract.get("job_id"),
        },
        "template": {
            "template_id": template_contract.get("template_id"),
            "template_type": template_contract.get("template_type"),
            "supported_content_types": template_contract.get("supported_content_types", []),
            "renderer": template_contract.get("renderer"),
            "aspect_ratio": template_contract.get("aspect_ratio"),
            "duration_seconds": template_contract.get("duration_seconds"),
            "precompose_required": template_contract.get("precompose_required", False),
        },
        "slots": slots,
        "renderer": {
            "name": template_contract.get("renderer"),
            "renderer_bindings": template_contract.get("renderer_bindings", {}),
            "precompose_plan": template_contract.get("precompose_plan", {"steps": []}),
        },
        "validation": {
            "source_contract_validation": template_contract.get("validation", {}),
            "tokenized_refs_only": True,
            "paid_generation_performed": False,
            "provider_calls_performed": False,
            "adult_runtime_mutation_performed": False,
        },
    }


def validate_adult_ai_template_contract(payload: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["adult_ai_influencer_template_contract.json must contain a JSON object."], warnings
    if payload.get("consumer_profile") != ADULT_AI_TEMPLATE_CONSUMER_PROFILE:
        errors.append(
            "adult_ai_influencer_template_contract.consumer_profile must be "
            f"`{ADULT_AI_TEMPLATE_CONSUMER_PROFILE}`."
        )
    if payload.get("schema_version") != ADULT_AI_TEMPLATE_CONTRACT_SCHEMA_VERSION:
        errors.append(
            "adult_ai_influencer_template_contract.schema_version must be "
            f"`{ADULT_AI_TEMPLATE_CONTRACT_SCHEMA_VERSION}`."
        )
    if payload.get("contract_version") != TEMPLATE_CONTRACT_VERSION:
        errors.append(
            f"adult_ai_influencer_template_contract.contract_version must be `{TEMPLATE_CONTRACT_VERSION}`."
        )
    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        errors.append("adult_ai_influencer_template_contract.slots must be a non-empty array.")
    else:
        seen: set[str] = set()
        for index, slot in enumerate(slots, start=1):
            if not isinstance(slot, dict):
                errors.append(f"adult consumer slot {index} must be an object.")
                continue
            slot_id = slot.get("slot_id")
            if not isinstance(slot_id, str) or not slot_id:
                errors.append(f"adult consumer slot {index} requires slot_id.")
                continue
            if slot_id in seen:
                errors.append(f"adult consumer duplicate slot_id: {slot_id}")
            seen.add(slot_id)
            token_ref = slot.get("token_ref")
            if not isinstance(token_ref, str) or not TOKEN_ONLY_RE.match(token_ref):
                errors.append(f"adult consumer slot {slot_id} requires tokenized token_ref.")

    for path, key, value in _iter_json_items(payload):
        normalized_key = key.lower()
        if normalized_key in FORBIDDEN_SUGGESTION_KEYS or any(
            part in normalized_key for part in FORBIDDEN_SUGGESTION_KEY_PARTS
        ):
            errors.append(f"adult consumer contract contains forbidden key at {path}.")
        if isinstance(value, str):
            if URL_VALUE_RE.search(value):
                errors.append(f"adult consumer contract contains a resolved URL at {path}.")
            if LOCAL_ABSOLUTE_PATH_RE.match(value) and not TOKEN_ONLY_RE.match(value):
                errors.append(f"adult consumer contract contains a local absolute path at {path}.")
            if re.search(r"\b(?:sk-|api[_-]?key|secret|password|adult_db_id|database_id|db_id)\b", value, re.IGNORECASE):
                errors.append(f"adult consumer contract contains secret or runtime id text at {path}.")
    return errors, warnings


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
    if preferred_renderer in SUPPORTED_RENDERERS and actual_renderer != preferred_renderer:
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


def _remove_manifest_artifact(
    artifacts: list[dict[str, Any]],
    *,
    path: str,
) -> bool:
    original_len = len(artifacts)
    artifacts[:] = [
        artifact
        for artifact in artifacts
        if not (isinstance(artifact, dict) and artifact.get("path") == path)
    ]
    return len(artifacts) != original_len


def maybe_write_assembly_flow_suggestion(
    package_dir: Path,
    *,
    consumer_profile: str | None,
    caller_context: Any = None,
    caller_context_echo: dict[str, Any] | None = None,
    template_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the Adult AI Influencer handoff suggestion only when requested."""

    if consumer_profile != ADULT_AI_INFLUENCER_CONSUMER_PROFILE:
        return {
            "requested": False,
            "created": False,
            "path": None,
            "errors": [],
            "warnings": [],
        }

    rel_path = "assembly_flow_suggestion.json"
    suggestion = build_assembly_flow_suggestion(
        package_dir,
        consumer_profile=consumer_profile,
        caller_context=caller_context,
        caller_context_echo=caller_context_echo,
        template_contract=template_contract,
    )
    errors, warnings = validate_assembly_flow_suggestion(suggestion)

    manifest_path = package_dir / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        manifest["artifacts"] = artifacts

    if errors:
        removed = _remove_manifest_artifact(artifacts, path=rel_path)
        if removed:
            write_json(manifest_path, manifest)
        return {
            "requested": True,
            "created": False,
            "path": None,
            "errors": errors,
            "warnings": warnings,
        }

    write_json(package_dir / rel_path, suggestion)
    manifest["job_id"] = manifest.get("job_id") or package_dir.name
    _upsert_manifest_artifact(
        artifacts,
        artifact_type="assembly_flow_suggestion",
        path=rel_path,
        scene_id=None,
        status="created",
    )
    write_json(manifest_path, manifest)
    return {
        "requested": True,
        "created": True,
        "path": rel_path,
        "errors": [],
        "warnings": warnings,
    }


def maybe_write_adult_ai_template_contract(
    package_dir: Path,
    *,
    consumer_profile: str | None,
    template_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if consumer_profile != ADULT_AI_TEMPLATE_CONSUMER_PROFILE:
        return {
            "requested": False,
            "created": False,
            "path": None,
            "errors": [],
            "warnings": [],
        }
    if not isinstance(template_contract, dict):
        return {
            "requested": True,
            "created": False,
            "path": None,
            "errors": ["template_contract is required before adult consumer contract generation."],
            "warnings": [],
        }

    rel_path = "adult_ai_influencer_template_contract.json"
    payload = build_adult_ai_template_contract(
        package_dir,
        template_contract=template_contract,
    )
    errors, warnings = validate_adult_ai_template_contract(payload)

    manifest_path = package_dir / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        manifest["artifacts"] = artifacts

    if errors:
        removed = _remove_manifest_artifact(artifacts, path=rel_path)
        if removed:
            write_json(manifest_path, manifest)
        return {
            "requested": True,
            "created": False,
            "path": None,
            "errors": errors,
            "warnings": warnings,
        }

    write_json(package_dir / rel_path, payload)
    manifest["job_id"] = manifest.get("job_id") or package_dir.name
    _upsert_manifest_artifact(
        artifacts,
        artifact_type="adult_ai_consumer_contract",
        path=rel_path,
        scene_id=None,
        status="created",
    )
    write_json(manifest_path, manifest)
    return {
        "requested": True,
        "created": True,
        "path": rel_path,
        "errors": [],
        "warnings": warnings,
    }


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
    if renderer not in SUPPORTED_RENDERERS:
        errors.append(f"template_contract.json has unsupported renderer `{renderer}`.")
    if contract.get("contract_version") != TEMPLATE_CONTRACT_VERSION:
        errors.append(
            f"template_contract.json contract_version must be `{TEMPLATE_CONTRACT_VERSION}`."
        )

    package_summary = contract.get("package_summary")
    slots = contract.get("slots")
    if not isinstance(package_summary, dict):
        errors.append("template_contract.json must contain package_summary.")
    if not isinstance(contract.get("renderer_bindings"), dict):
        errors.append("template_contract.json must contain renderer_bindings.")
    if "precompose_required" not in contract:
        errors.append("template_contract.json must contain precompose_required.")
    if not isinstance(contract.get("precompose_plan"), dict):
        errors.append("template_contract.json must contain precompose_plan.")
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
        media_kind = slot.get("media_kind")
        if kind in {"text", "color", "number"} and media_kind is not None:
            errors.append(f"template_contract slot {slot_id} media_kind must be null for {kind}.")
        if kind == "audio" and media_kind != "audio":
            errors.append(f"template_contract slot {slot_id} media_kind must be audio.")
        if kind in {"media", "overlay"} and media_kind not in {"image", "video", "audio", "thumbnail"}:
            errors.append(f"template_contract slot {slot_id} requires media_kind for {kind}.")
        fill_strategy = slot.get("fill_strategy")
        if fill_strategy not in CONTENT_FILL_STRATEGIES:
            errors.append(
                f"template_contract slot {slot_id} has unsupported fill_strategy `{fill_strategy}`."
            )
        if fill_strategy == "generate_media":
            errors.append(f"template_contract slot {slot_id} must not use legacy generate_media in v1.2.")
        generation_policy = slot.get("generation_policy")
        if not isinstance(generation_policy, dict):
            errors.append(f"template_contract slot {slot_id} requires generation_policy.")
        else:
            model_route = generation_policy.get("model_route")
            if isinstance(model_route, str) and model_route.lower() in HYPERFRAMES_FORBIDDEN_GENERATION_VALUES:
                errors.append(
                    f"template_contract slot {slot_id} must not use Hyperframes as a generation model."
                )
        approval_policy = slot.get("approval_policy")
        if not isinstance(approval_policy, dict):
            errors.append(f"template_contract slot {slot_id} requires approval_policy.")
        validation = slot.get("validation")
        if not isinstance(validation, dict):
            errors.append(f"template_contract slot {slot_id} requires validation.")
        renderer_binding = slot.get("renderer_binding")
        if not isinstance(renderer_binding, dict):
            errors.append(f"template_contract slot {slot_id} requires renderer_binding.")
        elif expected_renderer in {"shotstack", "hybrid"}:
            merge_key = renderer_binding.get("merge_key")
            needs_merge_key = fill_strategy not in {"generate_startframe", "select_existing_asset"}
            if needs_merge_key and (not isinstance(merge_key, str) or not merge_key):
                errors.append(
                    f"template_contract slot {slot_id} requires renderer_binding.merge_key."
                )
        elif expected_renderer == "remotion":
            prop_path = renderer_binding.get("prop_path")
            if not isinstance(prop_path, str) or not prop_path:
                errors.append(
                    f"template_contract slot {slot_id} requires renderer_binding.prop_path."
                )
        elif expected_renderer == "hyperframes":
            graph_ref = renderer_binding.get("graph_ref")
            if not isinstance(graph_ref, str) or not graph_ref:
                errors.append(
                    f"template_contract slot {slot_id} requires renderer_binding.graph_ref."
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

    precompose_required = contract.get("precompose_required")
    precompose_plan = contract.get("precompose_plan")
    if precompose_required is True:
        steps = precompose_plan.get("steps") if isinstance(precompose_plan, dict) else None
        if not isinstance(steps, list) or not steps:
            errors.append("template_contract precompose_required requires precompose_plan.steps[].")
        else:
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    errors.append(f"precompose_plan step {index} must be an object.")
                    continue
                output_slot = step.get("output_slot")
                if output_slot not in slot_ids:
                    errors.append(f"precompose_plan step {index} output_slot does not exist.")
                else:
                    output = next((slot for slot in slots if slot.get("slot_id") == output_slot), {})
                    if output.get("fill_strategy") != "precompose_video":
                        errors.append(
                            f"precompose_plan step {index} output_slot must use precompose_video."
                        )
                for input_slot in step.get("input_slots", []):
                    if input_slot not in slot_ids:
                        errors.append(f"precompose_plan step {index} input_slot `{input_slot}` does not exist.")
                status = step.get("status")
                if status not in HYBRID_PRECOMPOSE_STATUSES:
                    errors.append(f"precompose_plan step {index} has unsupported status `{status}`.")
                blockers = step.get("blockers")
                if status != "rendered" and not blockers:
                    errors.append(f"precompose_plan step {index} requires blockers until rendered.")
                if isinstance(blockers, list):
                    for blocker in blockers:
                        code = blocker.get("code") if isinstance(blocker, dict) else None
                        if code not in PRECOMPOSE_BLOCKER_CODES:
                            errors.append(f"precompose_plan step {index} has unsupported blocker code `{code}`.")

    return errors, warnings, contract
