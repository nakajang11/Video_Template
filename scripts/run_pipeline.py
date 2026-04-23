#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from template_package_support import (
    build_consumer_profile_prompt_context,
    build_source_summary,
    build_template_contract,
    compact_caller_context,
    create_package_archive,
    load_json as load_json_file,
    make_empty_caller_context_echo,
    make_empty_package_summary,
    make_empty_source_summary,
    maybe_write_assembly_flow_suggestion,
    render_caller_context_prompt_block,
    render_consumer_profile_prompt_block,
    resolve_consumer_profile,
    resolve_review_status,
    update_manifest_runtime_entries,
    validate_template_contract,
    write_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output"
DEFAULT_INPUT_ROOT = REPO_ROOT / "input"
SCHEMA_PATH = REPO_ROOT / "schemas" / "run_result.schema.json"
VALIDATOR_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "shotstack-remix-package"
    / "scripts"
    / "validate_package.py"
)
REMOTION_VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_remotion_package.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage an input video into this repository and invoke Codex as a "
            "backend pipeline that produces a review-gated template package."
        )
    )
    parser.add_argument(
        "--input-video",
        required=True,
        help="Path to the source video file that should be analyzed.",
    )
    parser.add_argument(
        "--job-id",
        help=(
            "Stable job identifier. Defaults to a slug derived from the source "
            "filename."
        ),
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help="Directory where the staged input video should be placed.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where output/<job_id>/ package artifacts should be written.",
    )
    parser.add_argument(
        "--stage-mode",
        choices=("copy", "symlink"),
        default="copy",
        help=(
            "How to stage an mp4 source into input/<job_id>.mp4. Non-mp4 sources "
            "are always transcoded to mp4."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing staged input video and overwrite existing logs/results.",
    )
    parser.add_argument(
        "--codex-model",
        help="Optional Codex model override passed through to `codex exec`.",
    )
    parser.add_argument(
        "--preferred-renderer",
        choices=("auto", "shotstack", "remotion"),
        default="auto",
        help=(
            "Preferred renderer override. `auto` keeps the existing routing rules, "
            "while `shotstack` and `remotion` strongly prefer that target."
        ),
    )
    parser.add_argument(
        "--context-json",
        help="Optional path to a caller context JSON file.",
    )
    parser.add_argument(
        "--context-inline-json",
        help="Optional inline caller context JSON string.",
    )
    parser.add_argument(
        "--consumer-profile",
        help=(
            "Optional downstream consumer profile. Currently supports "
            "`adult_ai_influencer_media_template` for an optional handoff suggestion."
        ),
    )
    parser.add_argument(
        "--result-json",
        action="store_true",
        help="Print the final structured result JSON to stdout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Do not invoke Codex or modify repository files. Print the command "
            "shape and prompt metadata only."
        ),
    )
    parser.add_argument(
        "--shotstack-smoke-render",
        action="store_true",
        help=(
            "After local Shotstack validation, attempt at most one external Shotstack "
            "smoke render for review-only verification."
        ),
    )
    parser.add_argument(
        "--shotstack-smoke-limit",
        type=int,
        default=1,
        help="Maximum Shotstack smoke render attempts. Only 1 is supported.",
    )
    parser.add_argument(
        "--shotstack-mcp-mode",
        choices=("off", "render-once"),
        default="off",
        help="Shotstack MCP side-effect mode. Default `off`; `render-once` allows one smoke render.",
    )
    return parser.parse_args()


def slugify_job_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("._-")
    slug = re.sub(r"_+", "_", slug)
    return slug.lower() or "job"


def ensure_within_repo(path: Path) -> None:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Path must stay within repository: {path}") from exc


def repo_relative_string(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def build_job_paths(args: argparse.Namespace) -> dict[str, Any]:
    source_path = Path(args.input_video).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Input video not found: {source_path}")
    if not source_path.is_file():
        raise FileNotFoundError(f"Input video is not a file: {source_path}")

    job_id = slugify_job_id(args.job_id or source_path.stem)
    input_root = Path(args.input_root).expanduser()
    output_root = Path(args.output_root).expanduser()
    if not input_root.is_absolute():
        input_root = (REPO_ROOT / input_root).resolve()
    else:
        input_root = input_root.resolve()
    if not output_root.is_absolute():
        output_root = (REPO_ROOT / output_root).resolve()
    else:
        output_root = output_root.resolve()

    staged_input = input_root / f"{job_id}.mp4"
    package_dir = output_root / job_id

    ensure_within_repo(staged_input)
    ensure_within_repo(package_dir)

    return {
        "source_path": source_path,
        "input_root": input_root,
        "output_root": output_root,
        "staged_input": staged_input,
        "package_dir": package_dir,
        "job_id": job_id,
    }


def stage_video(
    source_path: Path,
    staged_input: Path,
    stage_mode: str,
    force: bool,
) -> dict[str, Any]:
    staged_input.parent.mkdir(parents=True, exist_ok=True)
    if staged_input.exists() or staged_input.is_symlink():
        same_target = False
        try:
            same_target = staged_input.resolve() == source_path.resolve()
        except FileNotFoundError:
            same_target = False
        if same_target:
            return {"mode": "reused", "transcoded": False, "path": str(staged_input)}
        if not force:
            raise FileExistsError(
                f"Staged input already exists: {staged_input}. Use --force to replace it."
            )
        if staged_input.is_dir():
            raise IsADirectoryError(f"Expected a file path but found a directory: {staged_input}")
        staged_input.unlink()

    if source_path.suffix.lower() == ".mp4":
        if stage_mode == "symlink":
            staged_input.symlink_to(source_path)
            return {"mode": "symlink", "transcoded": False, "path": str(staged_input)}
        shutil.copy2(source_path, staged_input)
        return {"mode": "copy", "transcoded": False, "path": str(staged_input)}

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(staged_input),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to transcode input video to mp4:\n"
            f"{completed.stdout}\n{completed.stderr}".strip()
        )
    return {"mode": "transcode", "transcoded": True, "path": str(staged_input)}


def load_caller_context(
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    if args.context_json and args.context_inline_json:
        raise ValueError("Use either --context-json or --context-inline-json, not both.")

    raw_context: dict[str, Any] | None = None
    if args.context_json:
        context_path = Path(args.context_json).expanduser().resolve()
        if not context_path.exists():
            raise FileNotFoundError(f"Caller context file not found: {context_path}")
        if not context_path.is_file():
            raise FileNotFoundError(f"Caller context path is not a file: {context_path}")
        loaded = json.loads(context_path.read_text())
        if not isinstance(loaded, dict):
            raise ValueError("Caller context JSON must decode to an object.")
        raw_context = loaded
    elif args.context_inline_json:
        loaded = json.loads(args.context_inline_json)
        if not isinstance(loaded, dict):
            raise ValueError("Caller context JSON must decode to an object.")
        raw_context = loaded

    consumer_profile = resolve_consumer_profile(
        raw_context,
        cli_consumer_profile=args.consumer_profile,
    )
    return raw_context, compact_caller_context(
        raw_context,
        preferred_renderer=args.preferred_renderer,
    ), consumer_profile


def build_codex_prompt(
    job_id: str,
    *,
    preferred_renderer: str,
    caller_context_echo: dict[str, Any],
    consumer_profile_context: dict[str, Any] | None = None,
) -> str:
    consumer_profile_prompt = ""
    if consumer_profile_context:
        consumer_profile_prompt = textwrap.dedent(
            f"""

            Consumer profile handoff:
            - The caller requested a downstream-only optional artifact named
              `assembly_flow_suggestion.json`.
            - Generate it only as a tokenized proposal for the downstream consumer. Do not
              execute provider calls, resolve Cloudinary/DB URLs, store secrets, or include local
              absolute paths.
            - Keep all source/media values as whitelisted token references and keep every step
              review-gated for downstream execution.

            Sanitized consumer profile context:
            {render_consumer_profile_prompt_block(consumer_profile_context)}
            """
        ).rstrip()
    return textwrap.dedent(
        f"""
        You are operating as the backend template-packaging agent for this repository.

        Build the review-gated package for job_id `{job_id}` using the staged source video
        `input/{job_id}.mp4`.

        Follow these instructions:
        - Use this repository's `AGENTS.md` as the source of truth.
        - Use the planning workflow from `.agents/skills/trend-short-blueprint/SKILL.md`.
        - Read `docs/renderer-routing.md` before deciding whether this job should stay on Shotstack
          or switch to Remotion.
        - Preferred renderer from the caller: `{preferred_renderer}`.
          - If `{preferred_renderer}` is `auto`, keep the existing routing rules.
          - If `{preferred_renderer}` is `shotstack` or `remotion`, strongly prefer it.
          - If you cannot safely honor the preference, keep the package review-gated and explain why.
        - If `blueprint.renderer = "shotstack"`, use the packaging workflow from
          `.agents/skills/shotstack-remix-package/SKILL.md`.
        - If `blueprint.renderer = "remotion"`, do not force Shotstack outputs. Instead create
          `output/{job_id}/remotion_package/` using the packaging workflow from
          `.agents/skills/remotion-package/SKILL.md`, including `package.json`, `src/`,
          `props/`, `public/`, `template-partition.json`, and `README.md`, then update `manifest.json`.
        - Keep context usage tight. Only inspect the minimum repository files needed to do the job:
          `AGENTS.md`, `docs/output-contract.md`, `docs/project-plan.md`, `docs/renderer-routing.md`,
          the relevant skill files, and any directly referenced schema/template/validator files needed
          for execution.
        - If source scene boundaries, on-screen text, or cut timing are hard to inspect,
          you may use `.agents/skills/video-analysis-support/SKILL.md` to create optional
          evidence artifacts such as `timeline_view/` or `transcript_packed.md`. Do not
          use it to edit or render a final video.
        - Do not inspect unrelated prior output folders unless required to resolve a concrete format
          ambiguity for this specific job.
        - Produce the canonical package in `output/{job_id}/`.
        - Always extract `source_audio.mp3`, write the planning artifacts, and update `manifest.json`.
        - For Shotstack jobs, write scene prompt files plus `shotstack.json`,
          `cloudinary_assets.json`, and `shotstack.pasteable.json`.
        - For Remotion jobs, keep editable content in props files so the same template can be reused
          by swapping JSON data instead of rewriting the animation logic.
        - Set the structured result `renderer` field to either `shotstack` or `remotion`.
        - Stop at the review gate. Do not perform paid generation or final rendering.
        - If plot confidence or cast confidence is low, mark the package as review required instead
          of inventing unsupported details.
        - Run the renderer-appropriate package validator before you finish.
        - Keep the caller context compact. Do not dump raw operator metadata into prompts or artifacts.
        - In your structured result, include `caller_context_echo`, `source_summary`,
          `package_summary`, and artifact keys for `template_contract` and `package_archive`.
          If the local wrapper will generate one of those later, return `null` rather than omitting it.

        Caller context summary:
        {render_caller_context_prompt_block(caller_context_echo)}
        {consumer_profile_prompt}

        Your final answer must be a JSON object matching the provided schema.
        Report artifact paths relative to the repository root.
        """
    ).strip()


def build_codex_command(
    codex_result_path: Path,
    model: str | None,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "-",
        "--skip-git-repo-check",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(REPO_ROOT),
        "--ephemeral",
        "--output-schema",
        str(SCHEMA_PATH),
        "--output-last-message",
        str(codex_result_path),
    ]
    if model:
        command.extend(["--model", model])
    command.extend(
        [
            "--config",
            "shell_environment_policy.inherit=all",
        ]
    )
    return command


def run_codex(
    command: list[str],
    prompt: str,
    run_log_path: Path,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=prompt,
        capture_output=True,
        text=True,
    )
    run_log_path.write_text(
        textwrap.dedent(
            f"""\
            # run_pipeline.py Codex Invocation

            ## Command
            {' '.join(command)}

            ## Exit Code
            {completed.returncode}

            ## Stdout
            {completed.stdout}

            ## Stderr
            {completed.stderr}
            """
        )
    )
    return completed


def load_json(path: Path) -> Any:
    return load_json_file(path)


def parse_validator_output(stdout: str) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    section = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "Validation passed.":
            section = "passed"
            continue
        if line == "Validation failed:":
            section = "errors"
            continue
        if line == "Warnings:":
            section = "warnings"
            continue
        if line.startswith("- "):
            if section == "warnings":
                warnings.append(line[2:])
            else:
                errors.append(line[2:])
    return (not errors), errors, warnings


def infer_renderer(package_dir: Path) -> str:
    blueprint_path = package_dir / "blueprint.json"
    if blueprint_path.exists():
        try:
            blueprint = load_json(blueprint_path)
        except Exception:
            blueprint = None
        if isinstance(blueprint, dict):
            renderer = blueprint.get("renderer")
            if renderer in {"shotstack", "remotion"}:
                return renderer

    if (package_dir / "remotion_package").exists():
        return "remotion"
    if (package_dir / "shotstack.json").exists():
        return "shotstack"
    return "unknown"


def run_validator(package_dir: Path) -> dict[str, Any]:
    renderer = infer_renderer(package_dir)
    validator_path = REMOTION_VALIDATOR_PATH if renderer == "remotion" else VALIDATOR_PATH
    completed = subprocess.run(
        [sys.executable, str(validator_path), str(package_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    passed, errors, warnings = parse_validator_output(combined)
    return {
        "renderer": renderer,
        "passed": passed and completed.returncode == 0,
        "errors": errors,
        "warnings": warnings,
        "raw_output": combined,
        "returncode": completed.returncode,
    }


def resolve_shotstack_smoke_config(args: argparse.Namespace) -> dict[str, Any]:
    enabled = bool(args.shotstack_smoke_render or args.shotstack_mcp_mode == "render-once")
    mode = "render-once" if enabled else "off"
    limit = int(args.shotstack_smoke_limit)
    if enabled and limit != 1:
        raise ValueError("--shotstack-smoke-limit must be 1; automatic render loops are not allowed.")
    return {
        "enabled": enabled,
        "mode": mode,
        "limit": limit,
    }


def make_shotstack_smoke_state(
    *,
    enabled: bool = False,
    mode: str = "off",
    limit: int = 1,
    attempted: bool = False,
    status: str | None = None,
    render_url: str | None = None,
    render_path: str | None = None,
    improvement_notes: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if status is None:
        status = "pending" if enabled else "not_requested"
    return {
        "enabled": enabled,
        "mode": mode,
        "limit": limit,
        "attempted": attempted,
        "status": status,
        "render_url": render_url,
        "render_path": render_path,
        "improvement_notes": improvement_notes or [],
        "error": error,
    }


def _parse_fps(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def probe_media(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    payload = json.loads(completed.stdout)
    streams = payload.get("streams") if isinstance(payload, dict) else None
    video_stream = None
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == "video":
                video_stream = stream
                break
    duration = None
    try:
        duration = float(payload.get("format", {}).get("duration"))
    except (TypeError, ValueError, AttributeError):
        duration = None
    return {
        "duration_sec": duration,
        "width": video_stream.get("width") if isinstance(video_stream, dict) else None,
        "height": video_stream.get("height") if isinstance(video_stream, dict) else None,
        "fps": _parse_fps(video_stream.get("avg_frame_rate") if isinstance(video_stream, dict) else None)
        or _parse_fps(video_stream.get("r_frame_rate") if isinstance(video_stream, dict) else None),
    }


def build_shotstack_smoke_compare(
    *,
    source_video: Path,
    render_path: Path,
    package_dir: Path,
) -> tuple[dict[str, Any], list[str]]:
    compare_path = package_dir / "shotstack_smoke_compare.json"
    contact_sheet_path = package_dir / "shotstack_smoke_contact_sheet.jpg"
    work_dir = package_dir / "_shotstack_smoke"
    work_dir.mkdir(parents=True, exist_ok=True)
    source_frame = work_dir / "source_midpoint.jpg"
    render_frame = work_dir / "render_midpoint.jpg"
    notes: list[str] = [
        "Review the contact sheet for text placement, crop, and timing. No automatic second render was attempted."
    ]
    compare: dict[str, Any] = {
        "status": "created",
        "source_video": repo_relative_string(source_video),
        "render_path": repo_relative_string(render_path) if render_path.exists() else str(render_path),
        "source": None,
        "render": None,
        "duration_delta_sec": None,
        "resolution_matches": None,
        "fps_delta": None,
        "contact_sheet": None,
        "text_placement_review": {
            "method": "manual_contact_sheet_review",
            "notes": "Compare expected text boxes from blueprint source_geometry with the rendered midpoint frames.",
        },
        "warnings": [],
    }

    try:
        source_probe = probe_media(source_video)
        render_probe = probe_media(render_path)
        compare["source"] = source_probe
        compare["render"] = render_probe
        if source_probe.get("duration_sec") is not None and render_probe.get("duration_sec") is not None:
            compare["duration_delta_sec"] = round(
                float(render_probe["duration_sec"]) - float(source_probe["duration_sec"]),
                3,
            )
        compare["resolution_matches"] = (
            source_probe.get("width") == render_probe.get("width")
            and source_probe.get("height") == render_probe.get("height")
        )
        if source_probe.get("fps") is not None and render_probe.get("fps") is not None:
            compare["fps_delta"] = round(float(render_probe["fps"]) - float(source_probe["fps"]), 3)

        source_midpoint = max(float(source_probe.get("duration_sec") or 0) / 2, 0.1)
        render_midpoint = max(float(render_probe.get("duration_sec") or 0) / 2, 0.1)
        for input_path, midpoint, output_path in (
            (source_video, source_midpoint, source_frame),
            (render_path, render_midpoint, render_frame),
        ):
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{midpoint:.3f}",
                    "-i",
                    str(input_path),
                    "-frames:v",
                    "1",
                    str(output_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "ffmpeg frame extraction failed")

        filter_graph = (
            "[0:v]scale=540:960:force_original_aspect_ratio=decrease,"
            "pad=540:960:(ow-iw)/2:(oh-ih)/2[left];"
            "[1:v]scale=540:960:force_original_aspect_ratio=decrease,"
            "pad=540:960:(ow-iw)/2:(oh-ih)/2[right];"
            "[left][right]hstack=inputs=2"
        )
        completed = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_frame),
                "-i",
                str(render_frame),
                "-filter_complex",
                filter_graph,
                str(contact_sheet_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "ffmpeg contact sheet creation failed")
        compare["contact_sheet"] = repo_relative_string(contact_sheet_path)
    except Exception as exc:
        compare["status"] = "compare_failed"
        compare["warnings"].append(str(exc))
        notes.append(f"Shotstack smoke comparison could not create all local artifacts: {exc}")

    write_json(compare_path, compare)
    return compare, notes


def run_shotstack_smoke_render(
    *,
    package_dir: Path,
    source_video: Path,
    renderer: str,
    smoke_config: dict[str, Any],
) -> dict[str, Any]:
    state = make_shotstack_smoke_state(
        enabled=bool(smoke_config.get("enabled")),
        mode=str(smoke_config.get("mode", "off")),
        limit=int(smoke_config.get("limit", 1)),
    )
    if not state["enabled"]:
        return state

    result_path = package_dir / "shotstack_smoke_result.json"
    compare_path = package_dir / "shotstack_smoke_compare.json"
    if renderer != "shotstack":
        state["status"] = "skipped"
        state["error"] = "Shotstack smoke render only applies to shotstack packages."
        write_json(result_path, state)
        write_json(
            compare_path,
            {
                "status": "skipped",
                "reason": state["error"],
            },
        )
        return state

    if state["limit"] != 1:
        state["status"] = "configuration_error"
        state["error"] = "Shotstack smoke limit must be exactly 1."
        write_json(result_path, state)
        return state

    render_command = os.environ.get("SHOTSTACK_MCP_RENDER_COMMAND")
    if not render_command:
        state["status"] = "configuration_required"
        state["error"] = (
            "SHOTSTACK_MCP_RENDER_COMMAND is not configured; no Shotstack MCP render was attempted."
        )
        state["improvement_notes"].append(
            "Local validation passed, but external Shotstack smoke could not run without an MCP command adapter."
        )
        write_json(result_path, state)
        write_json(
            compare_path,
            {
                "status": "skipped",
                "reason": state["error"],
            },
        )
        return state

    shotstack_json_path = (
        package_dir / "shotstack.pasteable.json"
        if (package_dir / "shotstack.pasteable.json").exists()
        else package_dir / "shotstack.json"
    )
    request = {
        "package_dir": str(package_dir),
        "shotstack_json": str(shotstack_json_path),
        "source_video": str(source_video),
        "limit": 1,
        "purpose": "review_only_smoke_render",
    }
    state["attempted"] = True
    raw_result: dict[str, Any] = {}
    try:
        completed = subprocess.run(
            shlex.split(render_command),
            cwd=REPO_ROOT,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=900,
        )
        raw_result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        parsed_stdout = None
        try:
            parsed_stdout = json.loads(completed.stdout) if completed.stdout.strip() else None
        except json.JSONDecodeError:
            parsed_stdout = None
        raw_result["parsed_stdout"] = parsed_stdout

        if completed.returncode != 0:
            state["status"] = "failed"
            state["error"] = completed.stderr.strip() or completed.stdout.strip() or "Shotstack smoke render failed."
        else:
            state["status"] = "success"
            if isinstance(parsed_stdout, dict):
                render_url = parsed_stdout.get("render_url") or parsed_stdout.get("url")
                render_path = parsed_stdout.get("render_path") or parsed_stdout.get("file")
                if isinstance(render_url, str):
                    state["render_url"] = render_url
                if isinstance(render_path, str):
                    state["render_path"] = render_path
            if not state.get("render_url") and not state.get("render_path"):
                state["status"] = "failed"
                state["error"] = "Shotstack smoke adapter did not return render_url or render_path."
            else:
                state["improvement_notes"].append(
                    "Shotstack smoke render completed once. Use the saved compare artifacts for manual improvement planning."
                )
    except Exception as exc:
        raw_result = {"error": str(exc)}
        state["status"] = "failed"
        state["error"] = str(exc)

    result_payload = dict(state)
    result_payload["adapter_result"] = raw_result
    write_json(result_path, result_payload)

    render_path_value = state.get("render_path")
    if state["status"] == "success" and isinstance(render_path_value, str):
        local_render_path = Path(render_path_value).expanduser()
        if not local_render_path.is_absolute():
            local_render_path = (REPO_ROOT / local_render_path).resolve()
        if local_render_path.exists():
            compare, notes = build_shotstack_smoke_compare(
                source_video=source_video,
                render_path=local_render_path,
                package_dir=package_dir,
            )
            state["improvement_notes"].extend(notes)
            if compare.get("contact_sheet"):
                state["improvement_notes"].append(
                    f"Contact sheet saved at {compare['contact_sheet']}."
                )
        else:
            write_json(
                compare_path,
                {
                    "status": "skipped",
                    "reason": f"Render path does not exist locally: {render_path_value}",
                },
            )
    elif state["status"] == "success" and state.get("render_url"):
        write_json(
            compare_path,
            {
                "status": "skipped",
                "reason": "Render URL was returned, but no local render file was available for ffprobe comparison.",
                "render_url": state.get("render_url"),
            },
        )
    elif not compare_path.exists():
        write_json(
            compare_path,
            {
                "status": "skipped",
                "reason": state.get("error") or "Shotstack smoke render did not produce a local render.",
            },
        )

    result_payload = dict(state)
    result_payload["adapter_result"] = raw_result
    write_json(result_path, result_payload)
    return state


def upsert_manifest_artifact(
    package_dir: Path,
    *,
    artifact_type: str,
    path: str,
    status: str = "created",
) -> None:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        manifest["artifacts"] = artifacts
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("path") == path:
            artifact["type"] = artifact_type
            artifact["status"] = status
            artifact["scene_id"] = None
            write_json(manifest_path, manifest)
            return
    artifacts.append(
        {
            "type": artifact_type,
            "path": path,
            "scene_id": None,
            "status": status,
        }
    )
    write_json(manifest_path, manifest)


def build_fallback_result(
    *,
    status: str,
    job_id: str,
    renderer: str = "unknown",
    package_dir: Path,
    notes: list[str],
    preferred_renderer: str = "auto",
    caller_context_echo: dict[str, Any] | None = None,
    source_summary: dict[str, Any] | None = None,
    package_summary: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    shotstack_smoke: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "job_id": job_id,
        "renderer": renderer,
        "review_status": "not_started",
        "package_dir": repo_relative_string(package_dir),
        "caller_context_echo": caller_context_echo
        or make_empty_caller_context_echo(preferred_renderer=preferred_renderer),
        "source_summary": source_summary or make_empty_source_summary(),
        "package_summary": package_summary or make_empty_package_summary(renderer=renderer),
        "artifacts": {
            "analysis": None,
            "story": None,
            "variable_map": None,
            "blueprint": None,
            "manifest": None,
            "shotstack": None,
            "remotion_package": None,
            "source_audio": None,
            "template_contract": None,
            "package_archive": None,
            "shotstack_smoke_result": None,
            "shotstack_smoke_compare": None,
            "shotstack_smoke_contact_sheet": None,
            "shotstack_smoke_render": None,
            "prompt_files": [],
        },
        "shotstack_smoke": shotstack_smoke or make_shotstack_smoke_state(),
        "validation": validation
        or {
            "passed": False,
            "errors": [],
            "warnings": [],
        },
        "notes": notes,
    }


def collect_artifacts(package_dir: Path) -> dict[str, Any]:
    known_files = {
        "analysis": package_dir / "analysis.json",
        "story": package_dir / "story.json",
        "variable_map": package_dir / "variable_map.json",
        "blueprint": package_dir / "blueprint.json",
        "manifest": package_dir / "manifest.json",
        "shotstack": package_dir / "shotstack.json",
        "source_audio": package_dir / "source_audio.mp3",
        "template_contract": package_dir / "template_contract.json",
        "package_archive": package_dir / "package.zip",
        "shotstack_smoke_result": package_dir / "shotstack_smoke_result.json",
        "shotstack_smoke_compare": package_dir / "shotstack_smoke_compare.json",
        "shotstack_smoke_contact_sheet": package_dir / "shotstack_smoke_contact_sheet.jpg",
        "shotstack_smoke_render": package_dir / "shotstack_smoke_render.mp4",
    }
    artifacts: dict[str, Any] = {
        key: repo_relative_string(path) if path.exists() else None
        for key, path in known_files.items()
    }
    remotion_package_dir = package_dir / "remotion_package"
    artifacts["remotion_package"] = (
        repo_relative_string(remotion_package_dir) if remotion_package_dir.exists() else None
    )
    artifacts["prompt_files"] = [
        repo_relative_string(path)
        for path in sorted(package_dir.glob("scene_*_prompt.md"))
    ]
    artifacts["prompt_files"].extend(
        repo_relative_string(path)
        for path in sorted(package_dir.glob("scene_*_image_prompt.md"))
        if repo_relative_string(path) not in artifacts["prompt_files"]
    )
    return artifacts


def validate_result_shape(result: dict[str, Any]) -> None:
    required_top = [
        "status",
        "job_id",
        "renderer",
        "review_status",
        "package_dir",
        "caller_context_echo",
        "source_summary",
        "package_summary",
        "artifacts",
        "shotstack_smoke",
        "validation",
        "notes",
    ]
    for key in required_top:
        if key not in result:
            raise ValueError(f"Missing required result key: {key}")
    if not isinstance(result["artifacts"], dict):
        raise ValueError("Result artifacts must be an object")
    if not isinstance(result["validation"], dict):
        raise ValueError("Result validation must be an object")
    if not isinstance(result["notes"], list):
        raise ValueError("Result notes must be an array")


def main() -> int:
    args = parse_args()
    smoke_config = {
        "enabled": False,
        "mode": "off",
        "limit": 1,
    }
    caller_context_echo = make_empty_caller_context_echo(
        preferred_renderer=args.preferred_renderer
    )
    raw_caller_context: dict[str, Any] | None = None
    consumer_profile: str | None = None
    consumer_profile_context: dict[str, Any] | None = None
    try:
        smoke_config = resolve_shotstack_smoke_config(args)
        raw_caller_context, caller_context_echo, consumer_profile = load_caller_context(args)
        consumer_profile_context = build_consumer_profile_prompt_context(
            raw_caller_context,
            consumer_profile=consumer_profile,
            caller_context_echo=caller_context_echo,
        )
        paths = build_job_paths(args)
        source_path = paths["source_path"]
        staged_input = paths["staged_input"]
        package_dir = paths["package_dir"]
        job_id = paths["job_id"]
    except Exception as exc:
        fallback_job_id = slugify_job_id(args.job_id or Path(args.input_video).stem)
        smoke_error = str(exc) if "--shotstack-smoke" in str(exc) else None
        result = build_fallback_result(
            status="input_error",
            job_id=fallback_job_id,
            package_dir=Path(args.output_root).expanduser() / fallback_job_id,
            notes=[str(exc)],
            preferred_renderer=args.preferred_renderer,
            caller_context_echo=caller_context_echo,
            shotstack_smoke=make_shotstack_smoke_state(
                enabled=bool(smoke_error) or bool(smoke_config.get("enabled")),
                mode="render-once" if smoke_error else str(smoke_config.get("mode", "off")),
                limit=int(smoke_config.get("limit", 1)),
                status="configuration_error" if smoke_error else None,
                error=smoke_error,
            ),
        )
        if args.result_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2

    prompt = build_codex_prompt(
        job_id,
        preferred_renderer=args.preferred_renderer,
        caller_context_echo=caller_context_echo,
        consumer_profile_context=consumer_profile_context,
    )
    codex_command = build_codex_command(
        codex_result_path=package_dir / "codex_result.json",
        model=args.codex_model,
    )

    if args.dry_run:
        dry_run_result = {
            "status": "dry_run",
            "job_id": job_id,
            "renderer": "unknown",
            "preferred_renderer": args.preferred_renderer,
            "input_video": str(source_path),
            "staged_input": str(staged_input.relative_to(REPO_ROOT)),
            "package_dir": str(package_dir.relative_to(REPO_ROOT)),
            "caller_context_echo": caller_context_echo,
            "consumer_profile": consumer_profile,
            "consumer_profile_context": consumer_profile_context,
            "shotstack_smoke": make_shotstack_smoke_state(
                enabled=bool(smoke_config.get("enabled")),
                mode=str(smoke_config.get("mode", "off")),
                limit=int(smoke_config.get("limit", 1)),
            ),
            "command": codex_command,
            "prompt_preview": prompt,
            "notes": [
                "No files were modified.",
                "No Codex execution was performed.",
            ],
        }
        print(json.dumps(dry_run_result, indent=2, ensure_ascii=False))
        return 0

    package_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = package_dir / "codex_prompt.txt"
    codex_result_path = package_dir / "codex_result.json"
    result_path = package_dir / "result.json"
    request_path = package_dir / "request.json"
    run_log_path = package_dir / "run.log"

    request_payload = {
        "job_id": job_id,
        "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_video": str(source_path),
        "staged_input": str(staged_input.relative_to(REPO_ROOT)),
        "stage_mode": args.stage_mode,
        "codex_model": args.codex_model,
        "preferred_renderer": args.preferred_renderer,
        "shotstack_smoke": smoke_config,
        "caller_context": raw_caller_context,
        "caller_context_echo": caller_context_echo,
        "consumer_profile": consumer_profile,
    }
    request_path.write_text(json.dumps(request_payload, indent=2, ensure_ascii=False))
    prompt_path.write_text(prompt)

    try:
        stage_info = stage_video(
            source_path=source_path,
            staged_input=staged_input,
            stage_mode=args.stage_mode,
            force=args.force,
        )
    except Exception as exc:
        result = build_fallback_result(
            status="input_error",
            job_id=job_id,
            package_dir=package_dir,
            notes=[str(exc)],
            preferred_renderer=args.preferred_renderer,
            caller_context_echo=caller_context_echo,
            source_summary=make_empty_source_summary(
                source_video=str(source_path)
            ),
            shotstack_smoke=make_shotstack_smoke_state(
                enabled=bool(smoke_config.get("enabled")),
                mode=str(smoke_config.get("mode", "off")),
                limit=int(smoke_config.get("limit", 1)),
            ),
        )
        write_json(result_path, result)
        if args.result_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2

    completed = run_codex(codex_command, prompt, run_log_path)

    if codex_result_path.exists():
        try:
            result = load_json(codex_result_path)
            result.setdefault("renderer", infer_renderer(package_dir))
            result.setdefault("shotstack_smoke", make_shotstack_smoke_state())
            if isinstance(result.get("artifacts"), dict):
                result["artifacts"].setdefault(
                    "remotion_package",
                    collect_artifacts(package_dir).get("remotion_package"),
                )
            validate_result_shape(result)
        except Exception as exc:
            result = build_fallback_result(
                status="internal_error",
                job_id=job_id,
                renderer=infer_renderer(package_dir),
                package_dir=package_dir,
                notes=[
                    "Codex returned an unreadable structured result.",
                    str(exc),
                ],
                preferred_renderer=args.preferred_renderer,
                caller_context_echo=caller_context_echo,
            )
    else:
        result = build_fallback_result(
            status="internal_error" if completed.returncode else "validation_failed",
            job_id=job_id,
            renderer=infer_renderer(package_dir),
            package_dir=package_dir,
            notes=[
                "Codex did not produce a structured result file.",
                f"codex_exit_code={completed.returncode}",
            ],
            preferred_renderer=args.preferred_renderer,
            caller_context_echo=caller_context_echo,
        )

    result.setdefault("notes", [])
    result.setdefault("renderer", infer_renderer(package_dir))
    result["notes"].insert(
        0,
        f"staging_mode={stage_info['mode']}, transcoded={stage_info['transcoded']}",
    )
    result["shotstack_smoke"] = make_shotstack_smoke_state(
        enabled=bool(smoke_config.get("enabled")),
        mode=str(smoke_config.get("mode", "off")),
        limit=int(smoke_config.get("limit", 1)),
    )
    result["artifacts"] = collect_artifacts(package_dir)

    blueprint = load_json(package_dir / "blueprint.json") if (package_dir / "blueprint.json").exists() else None
    manifest = load_json(package_dir / "manifest.json") if (package_dir / "manifest.json").exists() else None
    source_summary = build_source_summary(
        package_dir,
        default_source_video=str(staged_input.relative_to(REPO_ROOT)),
    )
    result["caller_context_echo"] = caller_context_echo
    result["source_summary"] = source_summary
    result["package_summary"] = make_empty_package_summary(renderer=result["renderer"])
    assembly_suggestion_errors: list[str] = []
    assembly_suggestion_warnings: list[str] = []

    if package_dir.exists() and (package_dir / "blueprint.json").exists():
        try:
            runtime_renderer = infer_renderer(package_dir)
            template_contract = build_template_contract(
                package_dir,
                renderer=runtime_renderer,
                caller_context=raw_caller_context,
                caller_context_echo=caller_context_echo,
            )
            template_contract_path = package_dir / "template_contract.json"
            write_json(template_contract_path, template_contract)
            result["package_summary"] = template_contract.get(
                "package_summary",
                make_empty_package_summary(renderer=runtime_renderer),
            )
            result["artifacts"]["template_contract"] = repo_relative_string(template_contract_path)

            resolved_review_status = resolve_review_status(
                initial_review_status=result.get("review_status"),
                blueprint=blueprint,
                manifest=manifest,
                preferred_renderer=args.preferred_renderer,
                actual_renderer=runtime_renderer,
            )
            result["review_status"] = resolved_review_status
            update_manifest_runtime_entries(
                package_dir,
                renderer=runtime_renderer,
                review_status=resolved_review_status,
            )
            suggestion_state = maybe_write_assembly_flow_suggestion(
                package_dir,
                consumer_profile=consumer_profile,
                caller_context=raw_caller_context,
                caller_context_echo=caller_context_echo,
                template_contract=template_contract,
            )
            assembly_suggestion_errors = [
                f"assembly_flow_suggestion: {message}"
                for message in suggestion_state.get("errors", [])
            ]
            assembly_suggestion_warnings = [
                f"assembly_flow_suggestion: {message}"
                for message in suggestion_state.get("warnings", [])
            ]
            if suggestion_state.get("created"):
                result["notes"].append(
                    "assembly_flow_suggestion.json created for consumer_profile="
                    f"{consumer_profile}."
                )
            elif suggestion_state.get("requested") and assembly_suggestion_errors:
                result["review_status"] = "review_required"
                if result.get("status") == "ok":
                    result["status"] = "review_required"
                result["notes"].append(
                    "assembly_flow_suggestion.json was not packaged because validation required review."
                )

            if (
                args.preferred_renderer in {"shotstack", "remotion"}
                and runtime_renderer != args.preferred_renderer
            ):
                if result.get("status") == "ok":
                    result["status"] = "review_required"
                result["notes"].append(
                    "Preferred renderer could not be honored automatically; package remains review-gated."
                )
                result["notes"].append(
                    f"preferred_renderer={args.preferred_renderer}, actual_renderer={runtime_renderer}"
                )
        except Exception as exc:
            result["notes"].append(f"Template contract post-processing failed: {exc}")

    if package_dir.exists():
        validation = run_validator(package_dir)
        contract_errors, contract_warnings, _ = validate_template_contract(
            package_dir,
            expected_renderer=validation["renderer"],
        )
        validation["errors"].extend(contract_errors)
        validation["warnings"].extend(contract_warnings)
        validation["warnings"].extend(assembly_suggestion_warnings)
        validation["warnings"].extend(assembly_suggestion_errors)
        validation["passed"] = validation["passed"] and not contract_errors
        result["validation"] = {
            "passed": validation["passed"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }
        result["renderer"] = validation["renderer"]
        result["package_summary"]["renderer"] = validation["renderer"]
        if not validation["passed"]:
            result["status"] = "validation_failed"
            result["notes"].append("Local validator failed after Codex execution.")
        elif result.get("status") == "internal_error":
            result["notes"].append(
                "Codex execution was not fully successful, but the local validator passed."
            )
        result["notes"].append(
            f"validator_returncode={validation['returncode']}"
        )
        if validation["raw_output"]:
            (package_dir / "validator.log").write_text(validation["raw_output"])

    if result["validation"]["passed"]:
        if smoke_config.get("enabled"):
            smoke_state = run_shotstack_smoke_render(
                package_dir=package_dir,
                source_video=staged_input,
                renderer=result["renderer"],
                smoke_config=smoke_config,
            )
            result["shotstack_smoke"] = smoke_state
            for artifact_type, rel_path in (
                ("shotstack_smoke_result", "shotstack_smoke_result.json"),
                ("shotstack_smoke_compare", "shotstack_smoke_compare.json"),
                ("shotstack_smoke_contact_sheet", "shotstack_smoke_contact_sheet.jpg"),
                ("shotstack_smoke_render", "shotstack_smoke_render.mp4"),
            ):
                if (package_dir / rel_path).exists():
                    upsert_manifest_artifact(
                        package_dir,
                        artifact_type=artifact_type,
                        path=rel_path,
                    )
            result["artifacts"] = collect_artifacts(package_dir)
            result["notes"].extend(smoke_state.get("improvement_notes", []))
            if smoke_state.get("status") != "success":
                if result.get("status") == "ok":
                    result["status"] = "review_required"
                result["review_status"] = "review_required"
                if smoke_state.get("error"):
                    result["notes"].append(f"Shotstack smoke render did not complete: {smoke_state['error']}")
                update_manifest_runtime_entries(
                    package_dir,
                    renderer=result["renderer"],
                    review_status=result.get("review_status", "review_required"),
                    include_result=False,
                    include_archive=False,
                )

        result["artifacts"]["package_archive"] = repo_relative_string(package_dir / "package.zip")
        update_manifest_runtime_entries(
            package_dir,
            renderer=result["renderer"],
            review_status=result.get("review_status", "not_started"),
            include_result=True,
            include_archive=True,
        )
        write_json(result_path, result)
        try:
            create_package_archive(package_dir)
        except Exception as exc:
            result["artifacts"]["package_archive"] = None
            result["notes"].append(f"Failed to create package.zip: {exc}")
            update_manifest_runtime_entries(
                package_dir,
                renderer=result["renderer"],
                review_status=result.get("review_status", "not_started"),
                include_result=True,
                include_archive=False,
            )
    else:
        if smoke_config.get("enabled"):
            result["shotstack_smoke"] = make_shotstack_smoke_state(
                enabled=True,
                mode=str(smoke_config.get("mode", "render-once")),
                limit=int(smoke_config.get("limit", 1)),
                status="skipped",
                error="Local validation failed; Shotstack smoke render was not attempted.",
            )
        update_manifest_runtime_entries(
            package_dir,
            renderer=result["renderer"],
            review_status=result.get("review_status", "not_started"),
            include_result=True,
            include_archive=False,
        )

    write_json(result_path, result)
    if args.result_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"status={result.get('status')} job_id={job_id} package_dir={result.get('package_dir')}"
        )

    if result.get("status") in {"input_error", "internal_error", "validation_failed"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
