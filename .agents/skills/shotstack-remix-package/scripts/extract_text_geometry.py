#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


FONT_SIZE_BOX_COEFFICIENTS = {
    "Montserrat ExtraBold": 0.84,
    "Montserrat Bold": 0.82,
    "OpenSans Bold": 0.8,
}

FONT_SIZE_PLAIN_COEFFICIENTS = {
    "Montserrat ExtraBold": 1.45,
    "Montserrat Bold": 1.4,
    "OpenSans Bold": 1.35,
}


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def as_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract source text geometry from a reference frame and convert it "
            "into Shotstack-friendly layout hints."
        )
    )
    parser.add_argument("--image", required=True, help="Reference image path.")
    parser.add_argument(
        "--design-role",
        required=True,
        choices=("boxed_label", "caption_bar", "plain_stroked_text"),
        help="Source text design pattern.",
    )
    parser.add_argument(
        "--anchor",
        default="center",
        choices=(
            "center",
            "top",
            "bottom",
            "left",
            "right",
            "topLeft",
            "topRight",
            "bottomLeft",
            "bottomRight",
        ),
        help="Shotstack anchor to use for the resulting hint.",
    )
    parser.add_argument(
        "--select",
        type=int,
        help="Select a detected white box by index for boxed-label mode.",
    )
    parser.add_argument(
        "--bbox",
        help="Manual bbox for plain text mode as x,y,width,height.",
    )
    parser.add_argument(
        "--box-bbox",
        help="Manual box bbox for boxed text as x,y,width,height.",
    )
    parser.add_argument(
        "--text-bbox",
        help="Manual text bbox for boxed text as x,y,width,height.",
    )
    parser.add_argument(
        "--padding",
        help="Manual padding for boxed text as top,right,bottom,left.",
    )
    parser.add_argument(
        "--reference-asset",
        help="Override the reference asset recorded in source_geometry.",
    )
    parser.add_argument(
        "--text-key",
        help="Optional text merge key. If supplied, emit a blueprint-ready overlay object.",
    )
    parser.add_argument(
        "--default-text",
        help="Optional default text for blueprint-ready overlay output.",
    )
    parser.add_argument(
        "--font-candidate",
        action="append",
        default=[],
        help="Shotstack font family candidate. Repeat to provide multiple choices.",
    )
    parser.add_argument(
        "--editor-preview-strategy",
        default=None,
        choices=(
            "editable_over_box_background",
            "editable_on_clean_plate",
            "manual_review_required",
        ),
        help="Preview strategy hint to embed in source_geometry.",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=235,
        help="Minimum RGB value for white-box detection.",
    )
    parser.add_argument(
        "--dark-threshold",
        type=int,
        default=120,
        help="Maximum average RGB value for dark-text detection.",
    )
    parser.add_argument(
        "--min-box-area",
        type=int,
        default=200,
        help="Minimum connected-component area for white-box detection.",
    )
    parser.add_argument(
        "--output-width",
        type=int,
        help="Shotstack output width in pixels. Defaults to the source image width.",
    )
    parser.add_argument(
        "--output-height",
        type=int,
        help="Shotstack output height in pixels. Defaults to the source image height.",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def load_rgb24(path: Path) -> tuple[int, int, bytes]:
    dimensions = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ]
    ).strip()
    width, height = [int(value) for value in dimensions.split("x")]
    frame = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-frames:v",
            "1",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    expected_size = width * height * 3
    if len(frame) != expected_size:
        raise RuntimeError(
            f"Expected {expected_size} RGB bytes for {path.name}, received {len(frame)}"
        )
    return width, height, frame


def parse_bbox(raw: str) -> BBox:
    x, y, width, height = [int(part) for part in raw.split(",")]
    return BBox(x=x, y=y, width=width, height=height)


def parse_padding(raw: str) -> dict[str, int]:
    top, right, bottom, left = [int(part) for part in raw.split(",")]
    return {
        "top": top,
        "right": right,
        "bottom": bottom,
        "left": left,
    }


def pixel_offset(width: int, x: int, y: int) -> int:
    return (y * width + x) * 3


def rgb_at(frame: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    offset = pixel_offset(width, x, y)
    return frame[offset], frame[offset + 1], frame[offset + 2]


def brightness(rgb: tuple[int, int, int]) -> int:
    return (rgb[0] + rgb[1] + rgb[2]) // 3


def find_connected_components(
    width: int,
    height: int,
    predicate,
    *,
    min_area: int = 1,
    bounds: BBox | None = None,
) -> list[BBox]:
    if bounds is None:
        x_min = 0
        y_min = 0
        x_max = width
        y_max = height
    else:
        x_min = max(0, bounds.x)
        y_min = max(0, bounds.y)
        x_max = min(width, bounds.right)
        y_max = min(height, bounds.bottom)

    visited = bytearray(width * height)
    components: list[BBox] = []

    for y in range(y_min, y_max):
        for x in range(x_min, x_max):
            idx = y * width + x
            if visited[idx]:
                continue
            visited[idx] = 1
            if not predicate(x, y):
                continue

            stack = [idx]
            area = 0
            x0 = x1 = x
            y0 = y1 = y

            while stack:
                current = stack.pop()
                cy, cx = divmod(current, width)
                area += 1
                if cx < x0:
                    x0 = cx
                if cx > x1:
                    x1 = cx
                if cy < y0:
                    y0 = cy
                if cy > y1:
                    y1 = cy

                for nx, ny in (
                    (cx + 1, cy),
                    (cx - 1, cy),
                    (cx, cy + 1),
                    (cx, cy - 1),
                ):
                    if not (x_min <= nx < x_max and y_min <= ny < y_max):
                        continue
                    nidx = ny * width + nx
                    if visited[nidx]:
                        continue
                    visited[nidx] = 1
                    if predicate(nx, ny):
                        stack.append(nidx)

            if area >= min_area:
                components.append(BBox(x=x0, y=y0, width=x1 - x0 + 1, height=y1 - y0 + 1))

    components.sort(key=lambda box: (box.y, box.x))
    return components


def detect_white_boxes(
    frame: bytes,
    width: int,
    height: int,
    *,
    white_threshold: int,
    min_area: int,
) -> list[BBox]:
    def predicate(x: int, y: int) -> bool:
        red, green, blue = rgb_at(frame, width, x, y)
        return red >= white_threshold and green >= white_threshold and blue >= white_threshold

    return find_connected_components(width, height, predicate, min_area=min_area)


def detect_dark_text_bbox(
    frame: bytes,
    width: int,
    height: int,
    box: BBox,
    *,
    dark_threshold: int,
) -> BBox | None:
    inner = BBox(
        x=max(0, box.x + 1),
        y=max(0, box.y + 1),
        width=max(1, box.width - 2),
        height=max(1, box.height - 2),
    )

    def predicate(x: int, y: int) -> bool:
        return brightness(rgb_at(frame, width, x, y)) <= dark_threshold

    components = find_connected_components(width, height, predicate, min_area=4, bounds=inner)
    if not components:
        return None

    x0 = min(component.x for component in components)
    y0 = min(component.y for component in components)
    x1 = max(component.right for component in components)
    y1 = max(component.bottom for component in components)
    return BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0)


def compute_padding(box: BBox, text: BBox | None) -> dict[str, int] | None:
    if text is None:
        return None
    return {
        "top": max(0, text.y - box.y),
        "right": max(0, box.right - text.right),
        "bottom": max(0, box.bottom - text.bottom),
        "left": max(0, text.x - box.x),
    }


def resolve_font_family(candidates: list[str]) -> str:
    if candidates:
        return candidates[0]
    return "Montserrat ExtraBold"


def font_size_hint(design_role: str, family: str, box: BBox | None, text: BBox | None) -> int | None:
    if design_role in {"boxed_label", "caption_bar"} and box is not None:
        coefficient = FONT_SIZE_BOX_COEFFICIENTS.get(family, 0.82)
        return max(12, round(box.height * coefficient))
    if design_role == "plain_stroked_text" and text is not None:
        coefficient = FONT_SIZE_PLAIN_COEFFICIENTS.get(family, 1.4)
        return max(12, round(text.height * coefficient))
    return None


def shotstack_offset(anchor: str, target: BBox, viewport_width: int, viewport_height: int) -> dict[str, float]:
    if anchor == "center":
        offset_x = target.center_x / viewport_width - 0.5
        offset_y = 0.5 - target.center_y / viewport_height
    elif anchor == "top":
        offset_x = target.center_x / viewport_width - 0.5
        offset_y = -(target.y / viewport_height)
    elif anchor == "bottom":
        offset_x = target.center_x / viewport_width - 0.5
        offset_y = (viewport_height - target.bottom) / viewport_height
    elif anchor == "left":
        offset_x = target.x / viewport_width
        offset_y = 0.5 - target.center_y / viewport_height
    elif anchor == "right":
        offset_x = -((viewport_width - target.right) / viewport_width)
        offset_y = 0.5 - target.center_y / viewport_height
    elif anchor == "topLeft":
        offset_x = target.x / viewport_width
        offset_y = -(target.y / viewport_height)
    elif anchor == "topRight":
        offset_x = -((viewport_width - target.right) / viewport_width)
        offset_y = -(target.y / viewport_height)
    elif anchor == "bottomLeft":
        offset_x = target.x / viewport_width
        offset_y = (viewport_height - target.bottom) / viewport_height
    elif anchor == "bottomRight":
        offset_x = -((viewport_width - target.right) / viewport_width)
        offset_y = (viewport_height - target.bottom) / viewport_height
    else:
        raise ValueError(f"Unsupported anchor: {anchor}")

    return {
        "x": round(offset_x, 6),
        "y": round(offset_y, 6),
    }


def detection_output(
    *,
    image_path: Path,
    reference_asset: str | None,
    design_role: str,
    anchor: str,
    font_candidates: list[str],
    editor_preview_strategy: str | None,
    box_bbox: BBox | None,
    text_bbox: BBox | None,
    padding_override: dict[str, int] | None,
    viewport_width: int,
    viewport_height: int,
    output_width: int,
    output_height: int,
    text_key: str | None,
    default_text: str | None,
) -> dict[str, object]:
    family = resolve_font_family(font_candidates)
    target_bbox = box_bbox or text_bbox
    if target_bbox is None:
        raise ValueError("Target bbox is required")

    source_geometry: dict[str, object] = {
        "design_role": design_role,
        "reference_asset": reference_asset or image_path.name,
        "anchor": anchor,
        "font_candidates": font_candidates or [family],
        "editor_preview_strategy": editor_preview_strategy
        or (
            "editable_over_box_background"
            if design_role in {"boxed_label", "caption_bar"}
            else "editable_on_clean_plate"
        ),
        "font_size_hint": font_size_hint(design_role, family, box_bbox, text_bbox),
        "stroke_px": 0 if design_role in {"boxed_label", "caption_bar"} else 4,
    }

    if box_bbox is not None:
        source_geometry["box_bbox_px"] = box_bbox.as_dict()

    if text_bbox is not None:
        source_geometry["text_bbox_px"] = text_bbox.as_dict()

    padding = padding_override
    if padding is None and box_bbox is not None:
        padding = compute_padding(box_bbox, text_bbox)
    if padding is not None:
        source_geometry["padding_px"] = padding

    scale_x = output_width / viewport_width
    scale_y = output_height / viewport_height
    source_font_size = source_geometry["font_size_hint"]
    shotstack_font_size = (
        round(float(source_font_size) * scale_y) if isinstance(source_font_size, (int, float)) else None
    )

    shotstack_hint = {
        "position": anchor,
        "offset": shotstack_offset(anchor, target_bbox, viewport_width, viewport_height),
        "width": round(target_bbox.width * scale_x),
        "height": round(target_bbox.height * scale_y),
        "font_family": family,
        "font_size_hint": shotstack_font_size,
        "source_font_size_hint": source_font_size,
        "stroke_px_hint": round(float(source_geometry["stroke_px"]) * scale_y),
        "source_viewport": {
            "width": viewport_width,
            "height": viewport_height,
        },
        "output_viewport": {
            "width": output_width,
            "height": output_height,
        },
    }

    output: dict[str, object] = {
        "source_geometry": source_geometry,
        "shotstack_hint": shotstack_hint,
    }
    if text_key:
        output["text_key"] = text_key
    if default_text is not None:
        output["default_text"] = default_text
    return output


def main() -> int:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Missing image: {image_path}", file=sys.stderr)
        return 1

    viewport_width, viewport_height, frame = load_rgb24(image_path)
    output_width = args.output_width or viewport_width
    output_height = args.output_height or viewport_height
    manual_box_bbox = parse_bbox(args.box_bbox) if args.box_bbox else None
    manual_text_bbox = parse_bbox(args.text_bbox) if args.text_bbox else None
    manual_padding = parse_padding(args.padding) if args.padding else None

    if args.design_role in {"boxed_label", "caption_bar"}:
        if manual_box_bbox is not None or manual_text_bbox is not None:
            if manual_box_bbox is None or manual_text_bbox is None:
                print("--box-bbox and --text-bbox must be supplied together", file=sys.stderr)
                return 1

            output = detection_output(
                image_path=image_path,
                reference_asset=args.reference_asset,
                design_role=args.design_role,
                anchor=args.anchor,
                font_candidates=args.font_candidate,
                editor_preview_strategy=args.editor_preview_strategy,
                box_bbox=manual_box_bbox,
                text_bbox=manual_text_bbox,
                padding_override=manual_padding,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                output_width=output_width,
                output_height=output_height,
                text_key=args.text_key,
                default_text=args.default_text,
            )
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        boxes = detect_white_boxes(
            frame,
            viewport_width,
            viewport_height,
            white_threshold=args.white_threshold,
            min_area=args.min_box_area,
        )

        if args.select is None:
            detections = []
            for index, box in enumerate(boxes):
                text_bbox = detect_dark_text_bbox(
                    frame,
                    viewport_width,
                    viewport_height,
                    box,
                    dark_threshold=args.dark_threshold,
                )
                detections.append(
                    {
                        "index": index,
                        "box_bbox_px": box.as_dict(),
                        "text_bbox_px": text_bbox.as_dict() if text_bbox else None,
                        "padding_px": compute_padding(box, text_bbox),
                    }
                )
            print(json.dumps({"image": image_path.name, "detections": detections}, ensure_ascii=False, indent=2))
            return 0

        if args.select < 0 or args.select >= len(boxes):
            print(
                f"Selected box index {args.select} is out of range for {len(boxes)} detections",
                file=sys.stderr,
            )
            return 1

        box = boxes[args.select]
        text_bbox = detect_dark_text_bbox(
            frame,
            viewport_width,
            viewport_height,
            box,
            dark_threshold=args.dark_threshold,
        )
        output = detection_output(
            image_path=image_path,
            reference_asset=args.reference_asset,
            design_role=args.design_role,
            anchor=args.anchor,
            font_candidates=args.font_candidate,
            editor_preview_strategy=args.editor_preview_strategy,
            box_bbox=box,
            text_bbox=text_bbox,
            padding_override=manual_padding,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            output_width=output_width,
            output_height=output_height,
            text_key=args.text_key,
            default_text=args.default_text,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    if args.design_role == "plain_stroked_text":
        if not args.bbox:
            print("--bbox is required for plain_stroked_text mode", file=sys.stderr)
            return 1
        text_bbox = parse_bbox(args.bbox)
        output = detection_output(
            image_path=image_path,
            reference_asset=args.reference_asset,
            design_role=args.design_role,
            anchor=args.anchor,
            font_candidates=args.font_candidate,
            editor_preview_strategy=args.editor_preview_strategy,
            box_bbox=None,
            text_bbox=text_bbox,
            padding_override=None,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            output_width=output_width,
            output_height=output_height,
            text_key=args.text_key,
            default_text=args.default_text,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    print(f"Unsupported design role: {args.design_role}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
