# Renderer Routing

This repository now supports two review-gated packaging targets:

- `shotstack`
- `remotion`

The choice should be explicit in `blueprint.json` via a top-level `renderer` field.

## Preferred renderer override

The backend CLI may receive `--preferred-renderer` with one of:

- `auto`
- `shotstack`
- `remotion`

Rules:

- `auto` keeps the existing routing logic in this document
- `shotstack` strongly prefers Shotstack while still allowing a review-gated
  mismatch if the source is clearly a better Remotion fit
- `remotion` strongly prefers Remotion while still allowing a review-gated
  mismatch if the source is clearly a better Shotstack fit

If the actual package renderer does not match a non-`auto` preference, the run
should stay review-gated and the result should explain the mismatch instead of
silently pretending the preference was honored.

## Recommended default

Use `shotstack` unless the source depends on motion or layout that becomes fragile,
unnatural, or excessively manual in Shotstack.

## Choose `shotstack` when

- the job is mostly scene sequencing plus editable text overlays
- overlays are simple boxes, captions, stickers, picture-in-picture cards, or
  source-audio reuse
- motion can be approximated with clip transitions and standard animations
- the goal is direct compatibility with Shotstack Studio review

## Choose `remotion` when

- the source depends on kinetic typography or many independently animated text
  elements
- the source relies on procedural graphics such as charts, bars, scales, particles,
  or custom line drawing
- the source needs mask-style reveals, split curtains, matte-like wipes, or
  code-driven timing that would be brittle in Shotstack
- the animation should be reusable by swapping JSON props rather than rebuilding
  many clip-level animations by hand

## Source-specific guidance

- `input/test_1.mp4`: prefer `remotion`
- `input/test_2.mp4`: `shotstack` can approximate the editorial reveal, but repeated
  use of split-panel or custom matte transitions is a sign to switch to `remotion`
- `input/test_3.mp4`: prefer `remotion`

## Package shape

For `renderer = "shotstack"`:

- keep the existing canonical package with `shotstack.json`,
  `cloudinary_assets.json`, and `shotstack.pasteable.json`

For `renderer = "remotion"`:

- keep the shared planning files in `output/<job_id>/`
- add `output/<job_id>/remotion_package/`
- include at minimum:
  - `package.json`
  - `README.md`
  - `src/index.jsx`
  - `src/Root.jsx`
  - `props/default-props.json`
  - `public/`

Optional but recommended:

- `props/variant-*.json`
- `renders/` preview outputs

## Important constraint

This repo is still review-gated. A Remotion package should stop at a reviewable
template package unless the user explicitly asks for rendering.
