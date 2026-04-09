#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def build_codex_prompt(job_id: str) -> str:
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
        - If `blueprint.renderer = "shotstack"`, use the packaging workflow from
          `.agents/skills/shotstack-remix-package/SKILL.md`.
        - If `blueprint.renderer = "remotion"`, do not force Shotstack outputs. Instead create
          `output/{job_id}/remotion_package/` with a reviewable Remotion package including
          `package.json`, `src/`, `props/`, `public/`, and `README.md`, then update `manifest.json`.
        - Keep context usage tight. Only inspect the minimum repository files needed to do the job:
          `AGENTS.md`, `docs/output-contract.md`, `docs/project-plan.md`, `docs/renderer-routing.md`,
          the relevant skill files, and any directly referenced schema/template/validator files needed
          for execution.
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
            f"shell_environment_policy.inherit=[\"PATH\"]",
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
    return json.loads(path.read_text())


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


def build_fallback_result(
    *,
    status: str,
    job_id: str,
    renderer: str = "unknown",
    package_dir: Path,
    notes: list[str],
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "job_id": job_id,
        "renderer": renderer,
        "review_status": "not_started",
        "package_dir": repo_relative_string(package_dir),
        "artifacts": {
            "analysis": None,
            "story": None,
            "variable_map": None,
            "blueprint": None,
            "manifest": None,
            "shotstack": None,
            "remotion_package": None,
            "source_audio": None,
            "prompt_files": [],
        },
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
        "artifacts",
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
    try:
        paths = build_job_paths(args)
        source_path = paths["source_path"]
        staged_input = paths["staged_input"]
        package_dir = paths["package_dir"]
        job_id = paths["job_id"]
    except Exception as exc:
        result = build_fallback_result(
            status="input_error",
            job_id=slugify_job_id(args.job_id or Path(args.input_video).stem),
            package_dir=Path(args.output_root).expanduser() / slugify_job_id(args.job_id or Path(args.input_video).stem),
            notes=[str(exc)],
        )
        if args.result_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2

    prompt = build_codex_prompt(job_id)
    codex_command = build_codex_command(
        codex_result_path=package_dir / "codex_result.json",
        model=args.codex_model,
    )

    if args.dry_run:
        dry_run_result = {
            "status": "dry_run",
            "job_id": job_id,
            "renderer": "unknown",
            "input_video": str(source_path),
            "staged_input": str(staged_input.relative_to(REPO_ROOT)),
            "package_dir": str(package_dir.relative_to(REPO_ROOT)),
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
        )
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
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
        )

    result.setdefault("notes", [])
    result.setdefault("renderer", infer_renderer(package_dir))
    result["notes"].insert(
        0,
        f"staging_mode={stage_info['mode']}, transcoded={stage_info['transcoded']}",
    )
    result["artifacts"] = collect_artifacts(package_dir)

    if package_dir.exists():
        validation = run_validator(package_dir)
        result["validation"] = {
            "passed": validation["passed"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }
        result["renderer"] = validation["renderer"]
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

    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
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
