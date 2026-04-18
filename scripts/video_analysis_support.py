#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WHITESPACE_RE = re.compile(r"[ \t]+")
SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?。！？])\s+")


def normalize_transcript_text(text: str) -> str:
    lines = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = WHITESPACE_RE.sub(" ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _stringify_json_transcript(payload: Any) -> str:
    if isinstance(payload, dict):
        segments = payload.get("segments")
        if isinstance(segments, list):
            return "\n".join(_stringify_json_transcript(segment) for segment in segments)
        text = payload.get("text")
        if isinstance(text, str):
            start = payload.get("start") if "start" in payload else payload.get("start_sec")
            end = payload.get("end") if "end" in payload else payload.get("end_sec")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                return f"[{float(start):.2f}-{float(end):.2f}] {text}"
            return text
        return "\n".join(
            _stringify_json_transcript(value)
            for value in payload.values()
            if isinstance(value, (dict, list, str))
        )
    if isinstance(payload, list):
        return "\n".join(_stringify_json_transcript(item) for item in payload)
    if isinstance(payload, str):
        return payload
    return ""


def load_transcript(path: Path) -> str:
    raw_text = path.read_text()
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return normalize_transcript_text(raw_text)
        return normalize_transcript_text(_stringify_json_transcript(payload))
    return normalize_transcript_text(raw_text)


def compact_text(text: str, *, max_chars: int) -> tuple[str, dict[str, Any]]:
    normalized = normalize_transcript_text(text)
    original_chars = len(normalized)
    if original_chars <= max_chars:
        return normalized, {
            "original_chars": original_chars,
            "packed_chars": original_chars,
            "omitted_chars": 0,
            "strategy": "unchanged",
        }

    marker = f"\n\n[... omitted {original_chars - max_chars} chars from middle ...]\n\n"
    available = max(max_chars - len(marker), 0)
    head_chars = math.ceil(available * 0.62)
    tail_chars = available - head_chars

    head = normalized[:head_chars].rstrip()
    tail = normalized[-tail_chars:].lstrip() if tail_chars else ""

    head_sentences = SENTENCE_BREAK_RE.split(head)
    if len(head_sentences) > 1:
        head = " ".join(head_sentences[:-1]).strip() or head
    tail_sentences = SENTENCE_BREAK_RE.split(tail)
    if len(tail_sentences) > 1:
        tail = " ".join(tail_sentences[1:]).strip() or tail

    packed = f"{head}{marker}{tail}".strip()
    return packed, {
        "original_chars": original_chars,
        "packed_chars": len(packed),
        "omitted_chars": original_chars - len(packed),
        "strategy": "head_tail_middle_omission",
    }


def write_transcript_pack(
    *,
    input_path: Path,
    output_path: Path,
    job_id: str | None,
    max_chars: int,
) -> dict[str, Any]:
    transcript = load_transcript(input_path)
    packed, stats = compact_text(transcript, max_chars=max_chars)
    payload = {
        "job_id": job_id,
        "input": str(input_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "max_chars": max_chars,
        **stats,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Packed Transcript",
                "",
                "```json",
                json.dumps(payload, indent=2, ensure_ascii=False),
                "```",
                "",
                "## Transcript",
                "",
                packed,
                "",
            ]
        )
    )
    return payload


def parse_fps(value: object) -> float | None:
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


def ffprobe_video(input_video: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            str(input_video),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    payload = json.loads(completed.stdout)
    video_stream = None
    for stream in payload.get("streams", []):
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            video_stream = stream
            break
    duration_sec = None
    try:
        duration_sec = float(payload.get("format", {}).get("duration"))
    except (TypeError, ValueError, AttributeError):
        duration_sec = None
    return {
        "duration_sec": duration_sec,
        "width": video_stream.get("width") if isinstance(video_stream, dict) else None,
        "height": video_stream.get("height") if isinstance(video_stream, dict) else None,
        "fps": parse_fps(video_stream.get("avg_frame_rate") if isinstance(video_stream, dict) else None)
        or parse_fps(video_stream.get("r_frame_rate") if isinstance(video_stream, dict) else None),
    }


def build_frame_times(duration_sec: float, frame_count: int) -> list[float]:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    if frame_count == 1:
        return [round(duration_sec / 2, 3)]
    return [
        round(duration_sec * (index + 1) / (frame_count + 1), 3)
        for index in range(frame_count)
    ]


def create_timeline_view(
    *,
    input_video: Path,
    output_dir: Path,
    frame_count: int,
    thumb_width: int,
) -> dict[str, Any]:
    metadata = ffprobe_video(input_video)
    duration_sec = metadata.get("duration_sec")
    if not isinstance(duration_sec, (int, float)) or duration_sec <= 0:
        raise RuntimeError("Could not determine video duration")

    output_dir.mkdir(parents=True, exist_ok=True)
    frame_times = build_frame_times(float(duration_sec), frame_count)
    frame_paths = []
    for index, timestamp in enumerate(frame_times, start=1):
        frame_path = output_dir / f"frame_{index:03d}.jpg"
        completed = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(input_video),
                "-frames:v",
                "1",
                str(frame_path),
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "ffmpeg frame extraction failed")
        frame_paths.append(frame_path)

    cols = min(4, frame_count)
    rows = math.ceil(frame_count / cols)
    contact_sheet_path = output_dir / "contact_sheet.jpg"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "1",
            "-i",
            str(output_dir / "frame_%03d.jpg"),
            "-vf",
            f"scale={thumb_width}:-1,tile={cols}x{rows}:padding=8:margin=8",
            "-frames:v",
            "1",
            str(contact_sheet_path),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg contact sheet creation failed")

    payload = {
        "input_video": str(input_video),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "media": metadata,
        "frame_count": frame_count,
        "frame_times_sec": frame_times,
        "frames": [path.name for path in frame_paths],
        "contact_sheet": contact_sheet_path.name,
        "review_purpose": [
            "scene boundary evidence",
            "on-screen text placement",
            "overlay timing",
            "plot confidence review",
        ],
    }
    (output_dir / "metadata.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create optional source-video analysis evidence artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcript_parser = subparsers.add_parser(
        "compact-transcript",
        help="Create transcript_packed.md from plain text or JSON transcript input.",
    )
    transcript_parser.add_argument("--input", required=True, help="Transcript text or JSON file.")
    transcript_parser.add_argument("--output", required=True, help="Output markdown path.")
    transcript_parser.add_argument("--job-id", help="Optional job id for metadata.")
    transcript_parser.add_argument("--max-chars", type=int, default=5000)

    timeline_parser = subparsers.add_parser(
        "timeline-view",
        help="Create a timeline contact sheet and metadata with ffprobe/ffmpeg.",
    )
    timeline_parser.add_argument("--input-video", required=True, help="Source video path.")
    timeline_parser.add_argument("--output-dir", required=True, help="Output timeline_view directory.")
    timeline_parser.add_argument("--frame-count", type=int, default=8)
    timeline_parser.add_argument("--thumb-width", type=int, default=320)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "compact-transcript":
        if args.max_chars < 500:
            parser.error("--max-chars must be at least 500")
        payload = write_transcript_pack(
            input_path=Path(args.input).expanduser().resolve(),
            output_path=Path(args.output).expanduser(),
            job_id=args.job_id,
            max_chars=args.max_chars,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "timeline-view":
        payload = create_timeline_view(
            input_video=Path(args.input_video).expanduser().resolve(),
            output_dir=Path(args.output_dir).expanduser(),
            frame_count=args.frame_count,
            thumb_width=args.thumb_width,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
