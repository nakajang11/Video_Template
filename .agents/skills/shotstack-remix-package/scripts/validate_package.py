#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from template_package_support import validate_template_contract


PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")
SINGLE_BRACE_RE = re.compile(r"(?<!\{)\{([A-Za-z0-9_]+)\}(?!\})")
ALIAS_REF_RE = re.compile(r"alias://([A-Z0-9_]+)")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
FONT_SRC_RE = re.compile(r"\.(ttf|otf)(?:[?#].*)?$", re.IGNORECASE)
DURATION_TOLERANCE_SEC = 0.05


def parse_contract_version(raw_value: object) -> tuple[int, ...]:
    if not isinstance(raw_value, str):
        return (0,)
    parts = []
    for part in raw_value.split("."):
        if not part.isdigit():
            return (0,)
        parts.append(int(part))
    return tuple(parts) if parts else (0,)


def version_at_least(raw_value: object, target: tuple[int, ...]) -> bool:
    version = parse_contract_version(raw_value)
    padded_version = version + (0,) * (len(target) - len(version))
    padded_target = target + (0,) * (len(version) - len(target))
    return padded_version >= padded_target


def validate_bbox_object(
    scene_id: str,
    overlay_label: str,
    field_name: str,
    bbox: object,
    errors: list[str],
):
    if not isinstance(bbox, dict):
        errors.append(f"{scene_id}: {overlay_label} requires {field_name}")
        return
    for coord_key in ("x", "y", "width", "height"):
        value = bbox.get(coord_key)
        if not isinstance(value, (int, float)):
            errors.append(f"{scene_id}: {overlay_label} {field_name}.{coord_key} must be numeric")
    width = bbox.get("width")
    height = bbox.get("height")
    if isinstance(width, (int, float)) and width <= 0:
        errors.append(f"{scene_id}: {overlay_label} {field_name}.width must be positive")
    if isinstance(height, (int, float)) and height <= 0:
        errors.append(f"{scene_id}: {overlay_label} {field_name}.height must be positive")


def validate_text_geometry(
    scene_id: str,
    overlay: dict,
    package_dir: Path,
    review_status: object,
    strict_mode: bool,
    errors: list[str],
):
    overlay_label = overlay.get("text_key", "text overlay")
    source_geometry = overlay.get("source_geometry")

    if not strict_mode and not isinstance(source_geometry, dict):
        return

    if not isinstance(source_geometry, dict):
        errors.append(f"{scene_id}: {overlay_label} requires source_geometry in contract_version 1.1+")
        return

    design_role = source_geometry.get("design_role")
    if design_role not in {"boxed_label", "caption_bar", "plain_stroked_text"}:
        errors.append(
            f"{scene_id}: {overlay_label} source_geometry.design_role must be boxed_label, caption_bar, or plain_stroked_text"
        )

    reference_asset = source_geometry.get("reference_asset")
    if not isinstance(reference_asset, str) or not reference_asset:
        errors.append(f"{scene_id}: {overlay_label} source_geometry.reference_asset must be a string")
    elif not (package_dir / reference_asset).exists():
        errors.append(f"{scene_id}: {overlay_label} reference asset is missing: {reference_asset}")

    anchor = source_geometry.get("anchor")
    if not isinstance(anchor, str) or not anchor:
        errors.append(f"{scene_id}: {overlay_label} source_geometry.anchor must be a string")

    font_candidates = source_geometry.get("font_candidates")
    if not isinstance(font_candidates, list) or not font_candidates or not all(
        isinstance(candidate, str) and candidate for candidate in font_candidates
    ):
        errors.append(f"{scene_id}: {overlay_label} source_geometry.font_candidates must be a non-empty string array")

    font_size_hint = source_geometry.get("font_size_hint")
    if not isinstance(font_size_hint, (int, float)) or font_size_hint <= 0:
        errors.append(f"{scene_id}: {overlay_label} source_geometry.font_size_hint must be positive")

    stroke_px = source_geometry.get("stroke_px")
    if not isinstance(stroke_px, (int, float)) or stroke_px < 0:
        errors.append(f"{scene_id}: {overlay_label} source_geometry.stroke_px must be zero or positive")

    preview_strategy = source_geometry.get("editor_preview_strategy")
    if preview_strategy not in {
        "editable_over_box_background",
        "editable_on_clean_plate",
        "manual_review_required",
    }:
        errors.append(
            f"{scene_id}: {overlay_label} source_geometry.editor_preview_strategy must be editable_over_box_background, editable_on_clean_plate, or manual_review_required"
        )

    validate_bbox_object(scene_id, overlay_label, "text_bbox_px", source_geometry.get("text_bbox_px"), errors)

    if design_role in {"boxed_label", "caption_bar"}:
        validate_bbox_object(scene_id, overlay_label, "box_bbox_px", source_geometry.get("box_bbox_px"), errors)
        padding_px = source_geometry.get("padding_px")
        if not isinstance(padding_px, dict):
            errors.append(f"{scene_id}: {overlay_label} source_geometry.padding_px must be present for boxed text")
        else:
            for key in ("top", "right", "bottom", "left"):
                value = padding_px.get(key)
                if not isinstance(value, (int, float)) or value < 0:
                    errors.append(f"{scene_id}: {overlay_label} source_geometry.padding_px.{key} must be zero or positive")
        if preview_strategy == "editable_on_clean_plate":
            clean_plate_file = source_geometry.get("clean_plate_file")
            if not isinstance(clean_plate_file, str) or not clean_plate_file:
                errors.append(f"{scene_id}: {overlay_label} clean_plate_file is required when using editable_on_clean_plate")
            elif not (package_dir / clean_plate_file).exists():
                errors.append(f"{scene_id}: {overlay_label} clean_plate_file is missing: {clean_plate_file}")

    if design_role == "plain_stroked_text":
        if preview_strategy == "editable_over_box_background":
            errors.append(
                f"{scene_id}: {overlay_label} plain_stroked_text cannot use editable_over_box_background; use editable_on_clean_plate or manual_review_required"
            )
        if preview_strategy == "editable_on_clean_plate":
            clean_plate_file = source_geometry.get("clean_plate_file")
            if not isinstance(clean_plate_file, str) or not clean_plate_file:
                errors.append(f"{scene_id}: {overlay_label} clean_plate_file is required for plain_stroked_text on a clean plate")
            elif not (package_dir / clean_plate_file).exists():
                errors.append(f"{scene_id}: {overlay_label} clean_plate_file is missing: {clean_plate_file}")
        if preview_strategy == "manual_review_required" and review_status != "review_required":
            errors.append(f"{scene_id}: {overlay_label} manual_review_required requires blueprint.review_status to be review_required")


def load_json(path: Path, errors: list[str]):
    if not path.exists():
        errors.append(f"Missing required file: {path.name}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return None


def iter_strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from iter_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_strings(item)
    elif isinstance(node, str):
        yield node


def collect_alias_declarations(node):
    declared = set()
    if isinstance(node, dict):
        alias = node.get("alias")
        if isinstance(alias, str):
            declared.add(alias)
        for value in node.values():
            declared.update(collect_alias_declarations(value))
    elif isinstance(node, list):
        for item in node:
            declared.update(collect_alias_declarations(item))
    return declared


def iter_timeline_clips(shotstack: dict):
    timeline = shotstack.get("timeline")
    if not isinstance(timeline, dict):
        return
    tracks = timeline.get("tracks")
    if not isinstance(tracks, list):
        return
    for track_index, track in enumerate(tracks):
        if not isinstance(track, dict):
            continue
        clips = track.get("clips")
        if not isinstance(clips, list):
            continue
        for clip_index, clip in enumerate(clips):
            if isinstance(clip, dict):
                yield track_index, clip_index, clip


def _validate_color(value: object, field_path: str, errors: list[str]):
    if not isinstance(value, str) or not HEX_COLOR_RE.match(value):
        errors.append(f"{field_path} must be a hex color string")


def _validate_positive_number(value: object, field_path: str, errors: list[str]):
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append(f"{field_path} must be a positive number")


def _validate_non_negative_number(value: object, field_path: str, errors: list[str]):
    if not isinstance(value, (int, float)) or value < 0:
        errors.append(f"{field_path} must be a zero or positive number")


def validate_text_asset_schema(asset: dict, asset_path: str, errors: list[str]):
    asset_type = asset.get("type")
    if asset_type not in {"text", "rich-text"}:
        return

    if not isinstance(asset.get("text"), str) or not asset.get("text"):
        errors.append(f"{asset_path}.text must be a non-empty string")

    for unsupported_key in ("color", "size", "strokeWidth"):
        if unsupported_key in asset:
            errors.append(f"{asset_path}.{unsupported_key} is unsupported; use object-shaped font/stroke fields")

    font = asset.get("font")
    if not isinstance(font, dict):
        errors.append(f"{asset_path}.font must be an object")
    else:
        family = font.get("family")
        if not isinstance(family, str) or not family:
            errors.append(f"{asset_path}.font.family must be a non-empty string")
        _validate_positive_number(font.get("size"), f"{asset_path}.font.size", errors)
        _validate_color(font.get("color"), f"{asset_path}.font.color", errors)
        weight = font.get("weight")
        if weight is not None and not isinstance(weight, (int, str)):
            errors.append(f"{asset_path}.font.weight must be a number or string when provided")

    stroke = asset.get("stroke")
    if stroke is not None:
        if not isinstance(stroke, dict):
            errors.append(f"{asset_path}.stroke must be an object")
        else:
            _validate_color(stroke.get("color"), f"{asset_path}.stroke.color", errors)
            _validate_non_negative_number(stroke.get("width"), f"{asset_path}.stroke.width", errors)

    for object_key in ("shadow", "background", "style"):
        if object_key in asset and not isinstance(asset.get(object_key), dict):
            errors.append(f"{asset_path}.{object_key} must be an object when provided")


def validate_timeline_fonts(shotstack: dict, errors: list[str], label: str):
    timeline = shotstack.get("timeline")
    if not isinstance(timeline, dict):
        return
    fonts = timeline.get("fonts")
    if fonts is None:
        return
    if not isinstance(fonts, list):
        errors.append(f"{label} timeline.fonts must be an array")
        return
    for index, font in enumerate(fonts):
        font_path = f"{label} timeline.fonts[{index}]"
        if not isinstance(font, dict):
            errors.append(f"{font_path} must be an object")
            continue
        src = font.get("src")
        if not isinstance(src, str) or not src:
            errors.append(f"{font_path}.src must be a non-empty string")
            continue
        if "fonts.googleapis.com" in src:
            errors.append(f"{font_path}.src must point to a font file, not a Google Fonts CSS URL")
        if not src.startswith("https://"):
            errors.append(f"{font_path}.src must use https")
        if not FONT_SRC_RE.search(src):
            errors.append(f"{font_path}.src must point to a .ttf or .otf font file")


def validate_text_assets(shotstack: dict, errors: list[str], label: str):
    validate_timeline_fonts(shotstack, errors, label)
    for track_index, clip_index, clip in iter_timeline_clips(shotstack) or []:
        asset = clip.get("asset")
        if not isinstance(asset, dict):
            continue
        validate_text_asset_schema(
            asset,
            f"{label} timeline.tracks[{track_index}].clips[{clip_index}].asset",
            errors,
        )


def validate_blueprint(blueprint: dict, package_dir: Path, errors: list[str], warnings: list[str]):
    strict_text_geometry = version_at_least(blueprint.get("contract_version"), (1, 1))
    review_status = blueprint.get("review_status")
    audio = blueprint.get("audio")
    expected_audio_merge_key = None
    if not isinstance(audio, dict):
        errors.append("blueprint.json must contain an audio object")
    else:
        strategy = audio.get("strategy")
        source_file = audio.get("source_file")
        shotstack_merge_key = audio.get("shotstack_merge_key")

        if strategy != "use_input_audio":
            errors.append("blueprint.audio.strategy must be 'use_input_audio'")
        if source_file != "source_audio.mp3":
            errors.append("blueprint.audio.source_file must be 'source_audio.mp3'")
        elif not (package_dir / source_file).exists():
            errors.append("blueprint audio source file is missing: source_audio.mp3")
        if isinstance(shotstack_merge_key, str):
            expected_audio_merge_key = shotstack_merge_key
        else:
            errors.append("blueprint.audio.shotstack_merge_key must be a string")

    scenes = blueprint.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("blueprint.json must contain a non-empty scenes array")
        return set(), set(), {}

    scene_ids = []
    expected_aliases = set()
    expected_merge_keys = set()
    alias_to_duration = {}

    for scene in scenes:
        if not isinstance(scene, dict):
            errors.append("Each blueprint scene must be an object")
            continue

        scene_id = scene.get("scene_id")
        if not isinstance(scene_id, str):
            errors.append("Each blueprint scene requires a string scene_id")
            continue
        scene_ids.append(scene_id)

        duration = scene.get("duration_sec")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"{scene_id}: duration_sec must be a positive number")

        for section_name in ("startframe", "video"):
            section = scene.get(section_name)
            if not isinstance(section, dict):
                errors.append(f"{scene_id}: {section_name} must be an object")
                continue

            prompt_file = section.get("prompt_file")
            if isinstance(prompt_file, str) and prompt_file:
                prompt_path = package_dir / prompt_file
                if not prompt_path.exists():
                    errors.append(f"{scene_id}: missing prompt file {prompt_file}")

            if section_name == "startframe":
                required = section.get("required")
                if required is True and not prompt_file:
                    errors.append(f"{scene_id}: required startframe is missing prompt_file")

            if section_name == "video":
                mode = section.get("mode")
                if mode in {"generate", "motion-control"} and not prompt_file:
                    errors.append(f"{scene_id}: video mode '{mode}' requires prompt_file")
                if mode == "still-image-effect" and prompt_file:
                    warnings.append(f"{scene_id}: still-image-effect scene usually does not need a video prompt")

        shotstack = scene.get("shotstack")
        if not isinstance(shotstack, dict):
            errors.append(f"{scene_id}: shotstack must be an object")
            continue

        alias = shotstack.get("alias")
        merge_key = shotstack.get("merge_key")
        if isinstance(alias, str):
            expected_aliases.add(alias)
        else:
            errors.append(f"{scene_id}: shotstack.alias must be a string")
        if isinstance(merge_key, str):
            expected_merge_keys.add(merge_key)
        else:
            errors.append(f"{scene_id}: shotstack.merge_key must be a string")

        clip_length_sec = shotstack.get("clip_length_sec")
        if not isinstance(clip_length_sec, (int, float)) or clip_length_sec <= 0:
            errors.append(f"{scene_id}: shotstack.clip_length_sec must be a positive number")
        elif isinstance(duration, (int, float)) and abs(float(clip_length_sec) - float(duration)) > DURATION_TOLERANCE_SEC:
            errors.append(f"{scene_id}: shotstack.clip_length_sec must match duration_sec")
        elif isinstance(alias, str):
            alias_to_duration[alias] = float(clip_length_sec)

        overlay_layers = shotstack.get("overlay_layers", [])
        if isinstance(overlay_layers, list):
            for index, overlay in enumerate(overlay_layers, start=1):
                if not isinstance(overlay, dict):
                    errors.append(f"{scene_id}: overlay layer {index} must be an object")
                    continue
                merge_key = overlay.get("merge_key")
                relative_start_sec = overlay.get("relative_start_sec")
                overlay_duration_sec = overlay.get("duration_sec")
                if isinstance(merge_key, str):
                    expected_merge_keys.add(merge_key)
                else:
                    errors.append(f"{scene_id}: overlay layer {index} requires merge_key")
                if not isinstance(relative_start_sec, (int, float)) or relative_start_sec < 0:
                    errors.append(f"{scene_id}: overlay layer {index} requires non-negative relative_start_sec")
                if not isinstance(overlay_duration_sec, (int, float)) or overlay_duration_sec <= 0:
                    errors.append(f"{scene_id}: overlay layer {index} requires positive duration_sec")
                if (
                    isinstance(relative_start_sec, (int, float))
                    and isinstance(overlay_duration_sec, (int, float))
                    and isinstance(clip_length_sec, (int, float))
                    and float(relative_start_sec) + float(overlay_duration_sec) > float(clip_length_sec) + DURATION_TOLERANCE_SEC
                ):
                    errors.append(f"{scene_id}: overlay layer {index} must fit inside clip_length_sec")

        overlays = shotstack.get("text_overlays", [])
        if isinstance(overlays, list):
            for overlay in overlays:
                if isinstance(overlay, dict):
                    text_key = overlay.get("text_key")
                    if isinstance(text_key, str):
                        expected_merge_keys.add(text_key)
                    validate_text_geometry(
                        scene_id,
                        overlay,
                        package_dir,
                        review_status,
                        strict_text_geometry,
                        errors,
                    )

    if len(set(scene_ids)) != len(scene_ids):
        errors.append("blueprint.json contains duplicate scene_id values")

    scene_order = blueprint.get("scene_order")
    if isinstance(scene_order, list):
        if set(scene_order) != set(scene_ids):
            errors.append("scene_order must contain the same scene ids as scenes[]")
    else:
        errors.append("blueprint.json must contain scene_order")

    if expected_audio_merge_key:
        expected_merge_keys.add(expected_audio_merge_key)

    return expected_aliases, expected_merge_keys, alias_to_duration


def validate_analysis_against_blueprint(
    analysis: dict,
    blueprint: dict,
    errors: list[str],
):
    analysis_scenes = analysis.get("scenes")
    blueprint_scenes = blueprint.get("scenes")

    if not isinstance(analysis_scenes, list) or not isinstance(blueprint_scenes, list):
        return

    analysis_durations = {}
    for scene in analysis_scenes:
        if isinstance(scene, dict):
            scene_id = scene.get("scene_id")
            duration = scene.get("duration_sec")
            if isinstance(scene_id, str) and isinstance(duration, (int, float)):
                analysis_durations[scene_id] = float(duration)

    for scene in blueprint_scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        duration = scene.get("duration_sec")
        if not isinstance(scene_id, str) or not isinstance(duration, (int, float)):
            continue
        analysis_duration = analysis_durations.get(scene_id)
        if analysis_duration is None:
            errors.append(f"{scene_id}: missing from analysis.json")
            continue
        if abs(float(duration) - analysis_duration) > DURATION_TOLERANCE_SEC:
            errors.append(f"{scene_id}: blueprint duration_sec must match analysis.json")


def validate_manifest(manifest: dict, package_dir: Path, errors: list[str]):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest.json must contain a non-empty artifacts array")
        return

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("manifest artifacts must be objects")
            continue
        rel_path = artifact.get("path")
        if isinstance(rel_path, str) and rel_path:
            if not (package_dir / rel_path).exists():
                errors.append(f"manifest.json references missing artifact: {rel_path}")
        else:
            errors.append("manifest.json artifact entries require a path")


def validate_cloudinary_assets(cloudinary_assets: dict, errors: list[str]):
    if not isinstance(cloudinary_assets.get("cloud_name"), str) or not cloudinary_assets.get("cloud_name"):
        errors.append("cloudinary_assets.json must contain cloud_name")

    if not isinstance(cloudinary_assets.get("uploaded_at"), str) or not cloudinary_assets.get("uploaded_at"):
        errors.append("cloudinary_assets.json must contain uploaded_at")

    assets = cloudinary_assets.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("cloudinary_assets.json must contain a non-empty assets array")
        return

    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            errors.append(f"cloudinary_assets.json asset {index} must be an object")
            continue
        for key in ("type", "public_id", "secure_url"):
            value = asset.get(key)
            if not isinstance(value, str) or not value:
                errors.append(f"cloudinary_assets.json asset {index} requires {key}")
        secure_url = asset.get("secure_url")
        if isinstance(secure_url, str) and not secure_url.startswith("https://"):
            errors.append(f"cloudinary_assets.json asset {index} secure_url must use https")


def validate_pasteable_shotstack(shotstack: dict, errors: list[str]):
    validate_text_assets(shotstack, errors, "shotstack.pasteable.json")

    strings = list(iter_strings(shotstack))
    placeholders = set()
    for value in strings:
        placeholders.update(PLACEHOLDER_RE.findall(value))

    if placeholders:
        errors.append("shotstack.pasteable.json must not contain merge placeholders")

    if "merge" in shotstack:
        errors.append("shotstack.pasteable.json must not contain a merge array")

    timeline = shotstack.get("timeline")
    if not isinstance(timeline, dict):
        errors.append("shotstack.pasteable.json must contain a timeline object")
        return

    tracks = timeline.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("shotstack.pasteable.json must contain timeline.tracks")
        return

    audio_clip_found = False
    for track in tracks:
        if not isinstance(track, dict):
            continue
        clips = track.get("clips")
        if not isinstance(clips, list):
            continue
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            asset = clip.get("asset")
            asset_type = asset.get("type") if isinstance(asset, dict) else None
            if asset_type == "image":
                if "width" in clip or "height" in clip:
                    errors.append("shotstack.pasteable.json image clips must not use clip width or height; use scale instead")
                if isinstance(asset, dict) and ("width" in asset or "height" in asset):
                    errors.append("shotstack.pasteable.json image assets must not use width or height; use scale instead")
            if isinstance(asset, dict) and asset.get("type") == "audio":
                audio_clip_found = True
                src = asset.get("src")
                if not isinstance(src, str) or not src.startswith("https://"):
                    errors.append("shotstack.pasteable.json audio clip must use a direct https URL")
                if not isinstance(asset.get("volume"), (int, float)):
                    errors.append("shotstack.pasteable.json audio clip asset.volume must be numeric")
                if not isinstance(clip.get("start"), (int, float)):
                    errors.append("shotstack.pasteable.json audio clip start must be numeric")
                if not isinstance(clip.get("length"), (int, float)):
                    errors.append("shotstack.pasteable.json audio clip length must be numeric")

    if not audio_clip_found:
        errors.append("shotstack.pasteable.json must contain a dedicated audio clip track")


def validate_shotstack(
    shotstack: dict,
    expected_aliases: set[str],
    expected_merge_keys: set[str],
    alias_to_duration: dict[str, float],
    errors: list[str],
    warnings: list[str],
):
    validate_text_assets(shotstack, errors, "shotstack.json")

    strings = list(iter_strings(shotstack))
    placeholders = set()
    suspicious_single_braces = []
    alias_refs = set()

    for value in strings:
        placeholders.update(PLACEHOLDER_RE.findall(value))
        suspicious_single_braces.extend(SINGLE_BRACE_RE.findall(value))
        alias_refs.update(ALIAS_REF_RE.findall(value))

    if suspicious_single_braces:
        errors.append(
            "Shotstack strings contain single-brace placeholders: "
            + ", ".join(sorted(set(suspicious_single_braces)))
        )

    declared_aliases = collect_alias_declarations(shotstack)
    missing_aliases = alias_refs - declared_aliases
    if missing_aliases:
        errors.append("Unresolved alias references: " + ", ".join(sorted(missing_aliases)))

    declared_scene_clips = {}
    timeline = shotstack.get("timeline")
    audio_clip_found = False
    if isinstance(timeline, dict):
        if "soundtrack" in timeline:
            errors.append("Use a dedicated audio clip track instead of timeline.soundtrack")
        tracks = timeline.get("tracks")
        if isinstance(tracks, list):
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                clips = track.get("clips")
                if not isinstance(clips, list):
                    continue
                for clip in clips:
                    if not isinstance(clip, dict):
                        continue
                    asset = clip.get("asset")
                    if isinstance(asset, dict) and asset.get("type") == "audio":
                        audio_clip_found = True
                        if "volume" in clip:
                            errors.append("Audio clip volume must be nested inside asset")
                        if not isinstance(asset.get("volume"), (int, float)):
                            errors.append("Audio clip asset.volume must be numeric")
                        if not isinstance(clip.get("start"), (int, float)):
                            errors.append("Audio clip start must be numeric")
                        if not isinstance(clip.get("length"), (int, float)):
                            errors.append("Audio clip length must be numeric")
                    alias = clip.get("alias")
                    if not isinstance(alias, str) or alias not in alias_to_duration:
                        continue
                    declared_scene_clips[alias] = clip.get("length")

    if not audio_clip_found:
        errors.append("shotstack.json must contain a dedicated audio clip track for SOURCE_AUDIO_MP3")

    for alias, expected_length in alias_to_duration.items():
        if alias not in declared_scene_clips:
            errors.append(f"Blueprint alias missing base Shotstack clip: {alias}")
            continue
        actual_length = declared_scene_clips[alias]
        if not isinstance(actual_length, (int, float)):
            errors.append(f"Scene clip {alias} must use a numeric length")
            continue
        if abs(float(actual_length) - expected_length) > DURATION_TOLERANCE_SEC:
            errors.append(f"Scene clip {alias} length must match analyzed scene duration")

    merge = shotstack.get("merge")
    if not isinstance(merge, list):
        errors.append("shotstack.json must contain a merge array")
        merge_keys = set()
    else:
        merge_keys = set()
        for item in merge:
            if not isinstance(item, dict):
                errors.append("Each merge entry must be an object")
                continue
            find = item.get("find")
            if not isinstance(find, str) or not find:
                errors.append("Each merge entry requires a non-empty string find value")
                continue
            if "{" in find or "}" in find:
                errors.append(f"merge.find must not include braces: {find}")
            if find != find.upper():
                warnings.append(f"merge.find should be uppercase and scene-scoped: {find}")
            if find in merge_keys:
                errors.append(f"Duplicate merge key: {find}")
            merge_keys.add(find)

    missing_merge = placeholders - merge_keys
    if missing_merge:
        errors.append("Placeholders without merge keys: " + ", ".join(sorted(missing_merge)))

    unused_merge = merge_keys - placeholders
    if unused_merge:
        errors.append("Merge keys not used in template strings: " + ", ".join(sorted(unused_merge)))

    missing_expected_aliases = expected_aliases - declared_aliases
    if missing_expected_aliases:
        errors.append(
            "Blueprint aliases missing from shotstack.json: "
            + ", ".join(sorted(missing_expected_aliases))
        )

    missing_expected_merge = expected_merge_keys - merge_keys
    if missing_expected_merge:
        errors.append(
            "Blueprint merge keys missing from shotstack.json: "
            + ", ".join(sorted(missing_expected_merge))
        )


def main():
    if len(sys.argv) != 2:
        print("Usage: validate_package.py <output/job_id>", file=sys.stderr)
        return 2

    package_dir = Path(sys.argv[1]).expanduser()
    if not package_dir.is_absolute():
        package_dir = (Path.cwd() / package_dir)
    if not package_dir.exists() or not package_dir.is_dir():
        print(f"Package directory not found: {package_dir}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    required = {
      "analysis": package_dir / "analysis.json",
      "story": package_dir / "story.json",
      "variable_map": package_dir / "variable_map.json",
      "blueprint": package_dir / "blueprint.json",
      "manifest": package_dir / "manifest.json",
      "shotstack": package_dir / "shotstack.json",
      "cloudinary_assets": package_dir / "cloudinary_assets.json",
      "shotstack_pasteable": package_dir / "shotstack.pasteable.json",
    }

    source_audio = package_dir / "source_audio.mp3"
    if not source_audio.exists():
        errors.append("Missing required file: source_audio.mp3")

    loaded = {name: load_json(path, errors) for name, path in required.items()}

    expected_aliases = set()
    expected_merge_keys = set()
    alias_to_duration = {}

    analysis = loaded["analysis"]
    blueprint = loaded["blueprint"]
    if isinstance(analysis, dict) and isinstance(blueprint, dict):
        validate_analysis_against_blueprint(
            analysis,
            blueprint,
            errors,
        )
    if isinstance(blueprint, dict):
        expected_aliases, expected_merge_keys, alias_to_duration = validate_blueprint(
            blueprint,
            package_dir,
            errors,
            warnings,
        )

    manifest = loaded["manifest"]
    if isinstance(manifest, dict):
        validate_manifest(manifest, package_dir, errors)

    cloudinary_assets = loaded["cloudinary_assets"]
    if isinstance(cloudinary_assets, dict):
        validate_cloudinary_assets(cloudinary_assets, errors)

    shotstack = loaded["shotstack"]
    if isinstance(shotstack, dict):
        validate_shotstack(
            shotstack,
            expected_aliases,
            expected_merge_keys,
            alias_to_duration,
            errors,
            warnings,
        )

    shotstack_pasteable = loaded["shotstack_pasteable"]
    if isinstance(shotstack_pasteable, dict):
        validate_pasteable_shotstack(shotstack_pasteable, errors)

    contract_errors, contract_warnings, _ = validate_template_contract(
        package_dir,
        expected_renderer="shotstack",
    )
    errors.extend(contract_errors)
    warnings.extend(contract_warnings)

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
