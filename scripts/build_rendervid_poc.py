#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Rendervid proof-of-concept template from an existing "
            "review-gated package."
        )
    )
    parser.add_argument(
        "--job-id",
        required=True,
        help="Existing output/<job_id>/ package to convert.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        help=(
            "Override output fps. Defaults to the analyzed source fps so scene "
            "cuts stay aligned to the original media."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Override the Rendervid PoC directory. Defaults to "
            "output/<job_id>/rendervid_poc."
        ),
    )
    parser.add_argument(
        "--asset-base-url",
        default="http://127.0.0.1:8765",
        help=(
            "Base URL used to build template.localhost.json for local HTTP-served "
            "asset loading."
        ),
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def seconds_to_frame(seconds: float, fps: int) -> int:
    return int(round(seconds * fps))


def extract_scene_clip(
    source_video_path: Path,
    clip_path: Path,
    start_sec: float,
    duration_sec: float,
) -> None:
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(source_video_path),
        "-t",
        f"{duration_sec:.3f}",
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
        str(clip_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to extract clip {clip_path.name}:\n{completed.stderr}".strip()
        )


def make_video_layer(
    scene_id: str,
    source_video_uri: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    return {
        "id": f"{scene_id}_video",
        "type": "video",
        "name": f"{scene_id} source clip",
        "position": {"x": 0, "y": 0},
        "size": {"width": width, "height": height},
        "props": {
            "src": source_video_uri,
            "fit": "cover",
            "volume": 1,
        },
    }


def convert_template_asset_urls(
    template: dict[str, Any],
    asset_base_url: str,
) -> dict[str, Any]:
    converted = json.loads(json.dumps(template))
    normalized_base_url = asset_base_url.rstrip("/")

    for scene in converted.get("composition", {}).get("scenes", []):
        for layer in scene.get("layers", []):
            props = layer.get("props", {})
            src = props.get("src")
            if not isinstance(src, str) or not src.startswith("file://"):
                continue

            clip_path = Path(unquote(urlparse(src).path))
            repo_relative_path = clip_path.relative_to(REPO_ROOT)
            props["src"] = f"{normalized_base_url}/{repo_relative_path.as_posix()}"

    return converted


def build_template(
    job_id: str,
    analysis: dict[str, Any],
    blueprint: dict[str, Any],
    shotstack: dict[str, Any],
    source_video_path: Path,
    output_dir: Path,
    fps: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    shotstack_output = shotstack.get("output", {})
    output_size = shotstack_output.get("size", {})
    width = int(output_size.get("width", analysis["media"]["width"]))
    height = int(output_size.get("height", analysis["media"]["height"]))

    assets_dir = output_dir / "assets"

    analysis_scene_map = {
        scene["scene_id"]: scene for scene in analysis.get("scenes", []) if isinstance(scene, dict)
    }

    scenes = []
    scene_frames = []

    for scene_id in blueprint.get("scene_order", []):
        blueprint_scene = next(
            scene
            for scene in blueprint["scenes"]
            if isinstance(scene, dict) and scene.get("scene_id") == scene_id
        )
        analysis_scene = analysis_scene_map[scene_id]

        start_frame = seconds_to_frame(float(analysis_scene["start_sec"]), fps)
        end_frame = seconds_to_frame(float(analysis_scene["end_sec"]), fps)
        if end_frame <= start_frame:
            raise ValueError(f"{scene_id} produced an empty Rendervid frame range")

        clip_path = assets_dir / f"{scene_id}_source_clip.mp4"
        extract_scene_clip(
            source_video_path=source_video_path,
            clip_path=clip_path,
            start_sec=float(analysis_scene["start_sec"]),
            duration_sec=float(analysis_scene["duration_sec"]),
        )

        scenes.append(
            {
                "id": scene_id,
                "name": blueprint_scene.get("story_role", scene_id),
                "startFrame": start_frame,
                "endFrame": end_frame,
                "backgroundColor": "#000000",
                "layers": [
                    make_video_layer(
                        scene_id=scene_id,
                        source_video_uri=clip_path.resolve().as_uri(),
                        width=width,
                        height=height,
                    )
                ],
            }
        )
        scene_frames.append(
            {
                "scene_id": scene_id,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "duration_frames": end_frame - start_frame,
                "source_start_sec": analysis_scene["start_sec"],
                "source_end_sec": analysis_scene["end_sec"],
                "clip_file": str(clip_path.relative_to(REPO_ROOT)),
            }
        )

    total_frames = max(scene["endFrame"] for scene in scenes)
    output_duration_sec = total_frames / fps

    template = {
        "name": f"{job_id}-rendervid-poc",
        "description": (
            "Local Rendervid proof-of-concept built from the existing "
            f"{job_id} analysis/blueprint package."
        ),
        "version": "0.1.0",
        "tags": ["poc", "rendervid", "trend-short", "portrait"],
        "output": {
            "type": "video",
            "width": width,
            "height": height,
            "fps": fps,
            "duration": output_duration_sec,
            "backgroundColor": "#000000",
        },
        "inputs": [],
        "composition": {"scenes": scenes},
    }

    metadata = {
        "job_id": job_id,
        "source_video": str(source_video_path.relative_to(REPO_ROOT)),
        "assumptions": [
            "PoC uses locally extracted source-video scene clips as Rendervid media assets.",
            "Each Rendervid scene maps one source-derived clip to one video layer.",
            "Audio is carried by the extracted clip files in each video layer.",
        ],
        "frame_quantization": {
            "fps": fps,
            "analysis_duration_sec": analysis["media"]["duration_sec"],
            "template_duration_sec": output_duration_sec,
            "duration_delta_sec": round(output_duration_sec - float(analysis["media"]["duration_sec"]), 6),
        },
        "scene_frames": scene_frames,
    }

    return template, metadata


def build_readme(job_id: str, asset_base_url: str) -> str:
    return (
        f"# Rendervid PoC for {job_id}\n\n"
        "Artifacts in this folder are intentionally isolated from the canonical "
        "`shotstack.json` package.\n\n"
        "Files:\n"
        "- `template.json`: Rendervid template built from the existing analysis and blueprint.\n"
        "- `template.localhost.json`: same template, but asset URLs are rewritten for a local HTTP server.\n"
        "- `metadata.json`: frame math and PoC assumptions.\n"
        "- `validation.json`: optional validation result captured during this test run.\n"
        "- `render.mp4`: file-URI render attempt captured during this test run.\n"
        "- `render.localhost.mp4`: localhost-served render output captured during this test run.\n"
        "- `render.localhost.result.json`: renderer result metadata for the localhost render.\n\n"
        "Notes:\n"
        "- `template.json` is the canonical PoC artifact and uses local `file://` asset URIs.\n"
        "- `template.localhost.json` assumes the repository root is served over HTTP, for example with `python3 -m http.server 8765`.\n"
        f"- The localhost template targets `{asset_base_url.rstrip('/')}/...` asset URLs.\n"
        "- In this test, `@rendervid/core` validation passed for the template structure.\n"
        "- In this test, `@rendervid/renderer-node@0.1.0` timed out under `networkidle0` and produced black frames from `file://` video assets, while localhost-served assets rendered visible frames after a temporary throwaway patch switched that wait condition to `domcontentloaded`.\n"
        "- In this test, the extracted scene clips contained AAC audio, but the final Rendervid MP4s were video-only, so audio carry-through remains unresolved.\n"
    )


def main() -> int:
    args = parse_args()

    package_dir = require_file(REPO_ROOT / "output" / args.job_id)
    analysis = load_json(require_file(package_dir / "analysis.json"))
    blueprint = load_json(require_file(package_dir / "blueprint.json"))
    shotstack = load_json(require_file(package_dir / "shotstack.json"))

    source_video_path = require_file(REPO_ROOT / blueprint["source_video"])
    detected_fps = int(round(float(analysis["media"].get("fps", 30))))
    fps = args.fps or max(detected_fps, 1)

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else package_dir / "rendervid_poc"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    template, metadata = build_template(
        job_id=args.job_id,
        analysis=analysis,
        blueprint=blueprint,
        shotstack=shotstack,
        source_video_path=source_video_path,
        output_dir=output_dir,
        fps=fps,
    )
    localhost_template = convert_template_asset_urls(
        template=template,
        asset_base_url=args.asset_base_url,
    )
    metadata["localhost_asset_base_url"] = args.asset_base_url.rstrip("/")

    (output_dir / "template.json").write_text(json.dumps(template, indent=2) + "\n")
    (output_dir / "template.localhost.json").write_text(
        json.dumps(localhost_template, indent=2) + "\n"
    )
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output_dir / "README.md").write_text(
        build_readme(args.job_id, args.asset_base_url)
    )

    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
