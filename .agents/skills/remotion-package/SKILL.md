---
name: remotion-package
description: Build a review-gated Remotion package from an approved blueprint when Shotstack is not the right renderer. Use for code-driven typography, procedural graphics, matte-like transitions, reusable JSON-prop templates, and Remotion package validation.
---

# Remotion Package

Use this skill after `analysis.json`, `story.json`, `variable_map.json`,
`blueprint.json`, and `manifest.json` exist and `blueprint.renderer = "remotion"`.

Do not use this skill for Shotstack packages. Route `blueprint.renderer = "shotstack"`
jobs to `$shotstack-remix-package`.

This repo may also have the global Remotion Codex plugin installed. Treat it as
reference material, but keep this local skill and repo validators as the source
of truth for deliverable package shape.

## Required Inputs

Load these files from `output/<job_id>/`:

- `analysis.json`
- `story.json`
- `variable_map.json`
- `blueprint.json`
- `manifest.json`

Also load the staged source video from `input/<job_id>.mp4`.

## Required Workflow

1. Read `docs/output-contract.md` and `docs/renderer-routing.md`.
2. Confirm `blueprint.renderer = "remotion"` and `blueprint.remotion_package`
   has `composition_id`, `entry_file`, `props_file`, and `editable_props`.
3. Create or update `output/<job_id>/remotion_package/` with:
   - `package.json`
   - `README.md`
   - `src/index.jsx`
   - `src/Root.jsx`
   - a composition implementation file in `src/`
   - `props/default-props.json`
   - `public/`
   - `template-partition.json`
4. Copy `source_audio.mp3` into both `output/<job_id>/source_audio.mp3` and
   `remotion_package/public/source_audio.mp3`.
5. Put local media assets under `remotion_package/public/` and reference them
   from props without the `public/` prefix, for example
   `assets/scene_001_plate.png`.
6. Use `staticFile()` for local assets and audio inside Remotion code.
7. Define the renderable composition in `src/Root.jsx` with explicit
   `id`, `durationInFrames`, `fps`, `width`, `height`, and `defaultProps`.
8. Keep content-facing editable values in `props/default-props.json`; avoid
   hard-coding reusable text, media paths, palette values, or durations in the
   component when those values are declared editable in the blueprint.
9. Update `template-partition.json` so downstream systems can see which parts
   are input media, editable text, colors, timing, and locked animation logic.
10. Update `manifest.json`.
11. Run `python3 scripts/validate_remotion_package.py output/<job_id>`.
12. Stop at the review gate unless the user explicitly asks for a render or
   validator CLI smoke.

## Remotion Rules

- Use React + Remotion primitives such as `Composition`, `Sequence`,
  `AbsoluteFill`, `Audio`, `Img`, `OffthreadVideo`, `interpolate`, `spring`,
  `staticFile`, `useCurrentFrame`, and `useVideoConfig`.
- Keep `src/index.jsx` small and limited to `registerRoot`.
- Keep `src/Root.jsx` responsible for registering compositions and loading
  `defaultProps`.
- Use a stable composition id that matches `blueprint.remotion_package.composition_id`.
- Store props as JSON-serializable data. Do not put functions, dates, local
  absolute paths, `file://` URLs, or machine-specific paths in props.
- Use `Sequence` for scene timing. Scene frame ranges should match
  `blueprint.scenes[].remotion_sequence`.
- For code-driven source audio, use the extracted `source_audio.mp3`.
- Use `staticFile()` for any local asset from `public/`; remote HTTPS URLs may
  be used directly.
- If text can overflow, design with measured or bounded text layouts. Prefer
  dynamic fitting or conservative line-height/width constraints for long words
  and bilingual captions.
- If custom fonts are needed, load them explicitly and keep font files or
  package dependencies in the Remotion package.
- Do not leave final production renders as required artifacts. Preview renders
  are optional review evidence and must not be required by default.

## Validation Goal

A package is not ready until the validator confirms:

- required package files exist
- `blueprint.json` and `manifest.json` both declare `renderer = "remotion"`
- `source_audio.mp3` exists in the package root
- Remotion public audio exists when `props/default-props.json` references it
- `package.json` contains Remotion, React, and script entries for review
- `src/index.jsx` calls `registerRoot`
- `src/Root.jsx` defines a `Composition` whose id matches the blueprint
- `durationInFrames`, `fps`, `width`, and `height` are explicit or intentionally
  handled by metadata
- blueprint editable prop paths exist in `props/default-props.json`
- local media prop paths resolve under `remotion_package/public/`
- scene sequence start/duration frames are positive and align with composition
  duration
- `template_contract.json` exists and renderer bindings expose `prop_path`

## Optional CLI Smoke

Default validation is local and static. If explicitly requested, the validator
may run a lightweight Remotion CLI smoke:

```bash
python3 scripts/validate_remotion_package.py output/<job_id> --run-cli-smoke
```

This runs `npx remotion compositions <entry>` inside `remotion_package/`. It is
not a final render and should be used only after the static validator passes.
