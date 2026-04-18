---
name: video-analysis-support
description: Optional source-video inspection support for trend-template planning. Use for transcript packing, timeline contact sheets, scene-boundary evidence, and review-only visual/audio diagnostics. Do not use for final video editing or rendering.
---

# Video Analysis Support

Use this skill only to support `$trend-short-blueprint` analysis. It borrows the
useful parts of `browser-use/video-use` such as transcript-first inspection and
timeline evidence, but it does not adopt that project's editing or render loop.

## Purpose

This skill helps create deterministic evidence artifacts before writing:

- `analysis.json`
- `story.json`
- `variable_map.json`
- `blueprint.json`

It must not replace the canonical package contract, renderer routing, or review
gate.

## Allowed Artifacts

Save optional evidence under `output/<job_id>/`:

- `timeline_view/metadata.json`
- `timeline_view/contact_sheet.jpg`
- `timeline_view/frame_*.jpg`
- `transcript_packed.md`

Add these to `manifest.json` only as review evidence, not as required package
artifacts.

## Required Rules

- Do not create `final.mp4`.
- Do not run paid transcription, media generation, or final rendering unless the
  caller explicitly opts into a configured provider.
- Do not use a self-repair rerender loop.
- Do not route output into `/edit/`.
- Keep transcript content compact before using it in prompts.
- Treat transcript and contact sheets as evidence for timing, text, cuts, and
  plot confidence; the final source of truth remains `analysis.json` and
  `blueprint.json`.
- If transcript and visual evidence disagree, prefer visual evidence and mark the
  relevant scene confidence lower.

## Helper Commands

Create a visual contact sheet:

```bash
python3 scripts/video_analysis_support.py timeline-view \
  --input-video input/<job_id>.mp4 \
  --output-dir output/<job_id>/timeline_view \
  --frame-count 8
```

Pack a transcript without sending raw oversized text into prompts:

```bash
python3 scripts/video_analysis_support.py compact-transcript \
  --input transcript.txt \
  --output output/<job_id>/transcript_packed.md \
  --job-id <job_id>
```

## How To Use With `$trend-short-blueprint`

1. Generate `timeline_view/` when the scene boundaries, overlay timing, or text
   layout are hard to infer from a single pass.
2. Generate `transcript_packed.md` only if transcript or OCR text is available.
3. Reference the evidence paths in `analysis.json` under additional properties
   such as `evidence_artifacts`.
4. Use the evidence to improve scene durations, on-screen text extraction, and
   confidence labels.
5. Continue with the normal blueprint and renderer routing workflow.
