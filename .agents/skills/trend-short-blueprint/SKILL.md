---
name: trend-short-blueprint
description: Analyze a short vertical trend video, break down scenes, cuts, plot, cast, and lock-vs-variable decisions, then write analysis.json, story.json, variable_map.json, and blueprint.json for a female-influencer remake workflow. Do not use this skill when the task is only to render media or only to finalize an existing Shotstack template.
---

# Trend Short Blueprint

Use this skill when the task starts from a reference short video and the real work is understanding the structure before generating prompts.

## Output target

Write these planning artifacts into `output/<job_id>/`:

- `analysis.json`
- `story.json`
- `variable_map.json`
- `blueprint.json`
- `manifest.json`

Do not generate final media. Stop at the review gate if plot or cast confidence is low.

## Required workflow

1. Inspect `input/<job_id>.mp4` and any existing files in `output/<job_id>/`.
2. Read the contract in [`docs/output-contract.md`](../../../docs/output-contract.md).
3. Read the architecture notes in [`docs/project-plan.md`](../../../docs/project-plan.md).
4. Read provider guidance in [`references/provider-guidance.md`](references/provider-guidance.md).
5. Write `analysis.json` first.
6. Write `story.json` next so the full plot is explicit before prompt writing.
7. Write `variable_map.json` to separate locks from variables.
8. Choose `blueprint.renderer` using `docs/renderer-routing.md`. Use `shotstack` by default and switch to `remotion` when the source depends on kinetic typography, procedural graphics, matte-like reveals, or other code-driven animation.
9. Write `blueprint.json` with deterministic scene ids, expected prompt filenames, an `audio` block that points to `source_audio.mp3`, and any renderer-specific metadata needed for packaging.
10. Update `manifest.json` with every artifact path, renderer choice, and review state.

## What to analyze

For each source video, capture:

- scene boundaries and durations
- shot scale, framing, camera stability, and pacing
- on-screen text pattern
- image-on-video or video-on-video overlays
- whether the motion design is simple overlay sequencing or needs code-driven animation
- transformation structure such as timeline jump, outfit reveal, or identity-preserving remix
- cast continuity across scenes
- whether parent, friend, partner, or childhood self must be generated

## Lock versus variable logic

Always separate these categories:

- identity locks
- wardrobe locks
- background and room locks
- composition locks
- text variables
- motion variables
- supporting-cast requirements
- overlay-layer requirements

If the full plot is needed to know whether extra characters appear, keep that decision in `story.json` and surface it in `variable_map.json`.

## Timing rules

- Derive each scene's `start_sec`, `end_sec`, and `duration_sec` from the source video, not from a guessed remake plan.
- Copy the same `duration_sec` into `blueprint.json` for the matching `scene_id`.
- In each scene's `shotstack` block, set `clip_length_sec` to the same analyzed duration so the packaging step can write it directly into `shotstack.json`.
- If a source scene includes a card image, inset portrait, or any picture-in-picture composition, add `overlay_layers` to the scene's `shotstack` block with relative timing and placement.
- If a source scene includes editable editorial text, plan how it will be rebuilt: boxed labels should carry measured `source_geometry` in `text_overlays`, while plain stroked text should be marked as needing a clean plate or `review_required` Studio handling.
- If a scene-specific frame is too noisy to measure boxed text reliably, reuse a representative frame from the same text-design family or record a manual bbox instead of guessing.

## Model routing rules

- Default startframe composition: `nano banana2`
- Outfit replacement: `grok imagine`
- Motion generation: `kling v3`
- Reference motion transfer: `kling v3 motion control`

Do not turn model routing into prompt text until the blueprint is stable.

## Review-required cases

Mark `review_status` or `analysis_confidence` conservatively when:

- the video cannot be visually inspected end to end
- the plot depends on off-screen context
- supporting cast is implied but not explicit
- a scene could be either source extraction or generated replacement

## References

Read only what you need:

- contract: [`docs/output-contract.md`](../../../docs/output-contract.md)
- project notes: [`docs/project-plan.md`](../../../docs/project-plan.md)
- provider guidance: [`references/provider-guidance.md`](references/provider-guidance.md)
- starter schema: [`assets/analysis.schema.json`](assets/analysis.schema.json)
- starter schema: [`assets/blueprint.schema.json`](assets/blueprint.schema.json)
