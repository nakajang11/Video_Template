# AGENTS.md

## Repository expectations

- This repository is for planning and packaging trend short-form videos, not for paid media generation or final rendering.
- This repository is a shared backend. Do not execute downstream project logic such
  as Adult AI Influencer DB lookups, Cloudinary URL resolution, wardrobe
  randomization, provider calls, paid media generation, or final rendering.
- Downstream handoff suggestions may be generated only when an explicit
  `consumer_profile` requests them. Keep those suggestions optional,
  tokenized, review-gated, and outside the canonical default artifact contract.
- Preserve `input/` as the source area and `output/` as the deliverable area. Treat existing `sample_1` and `sample_2` as examples of the target artifact shape, not as a perfect contract.
- Before writing prompts, Shotstack JSON, or Remotion code, separate immutable findings from creative decisions:
  1. `analysis.json`
  2. `story.json`
  3. `variable_map.json`
  4. `blueprint.json`
  5. `source_audio.mp3`
  6. scene prompt files
  7. `shotstack.json`
  8. `cloudinary_assets.json`
  9. `shotstack.pasteable.json`
  10. `manifest.json`
- For Remotion jobs, replace Shotstack-specific artifacts with `remotion_package/`,
  including `package.json`, `src/`, `props/default-props.json`, `public/`, and
  `template-partition.json`.
- Optional source-inspection evidence from `.agents/skills/video-analysis-support/`
  may be saved as `timeline_view/` or `transcript_packed.md`, but it must not
  replace the canonical planning artifacts or trigger final video editing.
- For female-influencer videos, explicitly identify the lead identity lock, wardrobe lock, background lock, on-screen text pattern, optional supporting cast, and the global plot before turning anything into prompts.
- If the source contains editorial text that should remain changeable, such as hook text, name labels, year labels, or meme captions, remove it from the remake base media and rebuild it as editable Shotstack text overlays. Ignore platform logos, watermarks, usernames, and logo text unless the user explicitly asks to preserve them.
- For boxed labels or caption bars, measure the source text geometry and carry it into `blueprint.json` so `shotstack.json` and `shotstack.pasteable.json` can be derived from actual source rectangles rather than manual eyeballing.
- When converting measured source text into Shotstack, scale font size and box dimensions from the source viewport to the final output viewport. Do not reuse source-pixel font sizes directly in `1080x1920` packages.
- If the source scene contains picture-in-picture, inserted photos, reference cards, or any image-on-video composition, model that as a base scene clip plus overlay layers instead of flattening it into one vague prompt.
- If a parent, friend, partner, or childhood self might be required, confirm it from the full plot across scenes. If the evidence is weak, mark the package as `review_required` instead of inventing extra characters.
- If the last scene is only a social-platform end slate or branded SNS outro, omit it from the remake package by default unless the user explicitly asks to keep it.
- If transcript, OCR, or timeline contact sheets are used, keep them compact and
  evidence-scoped. Do not pass raw oversized transcript content into prompts.

## Model routing

- Default startframe and multi-reference composition model: `nano banana2`
- Outfit swap or clothing replacement model: `grok imagine`
- Image-to-video motion model: `kling v3`
- Reference motion transfer model: `kling v3 motion control`
- Never call provider APIs, run paid generations, or render with Shotstack unless the user explicitly asks and approves it. The only allowed exception is the review-only Shotstack smoke path triggered by `--shotstack-smoke-render`, capped at one attempt with no retry loop.
- Always extract the input video's audio into `output/<job_id>/source_audio.mp3` and use that audio as the default Shotstack audio source unless the user explicitly overrides it.

## Shotstack guardrails

- Prefer Shotstack `alias` plus `start: "auto"` for sequencing and overlay sync, while keeping base scene clip lengths as explicit numeric values.
- Shotstack renders higher-priority visual tracks earlier in the `tracks` array. Put editable text first, any caption/name backdrop directly beneath it only when the source design actually uses one, and the base video or image track below those.
- For editor-compatible packages, model the extracted source audio as a dedicated audio clip on its own track instead of `timeline.soundtrack`.
- When using an audio clip, put `volume` inside `asset`, not on the clip object, and set explicit numeric `start` and `length`.
- Create `cloudinary_assets.json` and `shotstack.pasteable.json` for every packaged job so the Shotstack editor can load a direct-URL version without merge placeholders.
- `shotstack.pasteable.json` targets Shotstack Studio compatibility. Avoid `width` and `height` on image overlay clips there; use `fit`, `scale`, `position`, and `offset` for image sizing instead. Text boxes may still use `width` and `height` when needed to match the source design.
- Use merge placeholders with double braces inside template strings, for example `{{ SCENE_001_MEDIA }}`.
- Keep `merge[].find` values brace-free, for example `SCENE_001_MEDIA`.
- Keep merge keys scene-scoped, uppercase, and consistent across `blueprint.json`, prompt files, and `shotstack.json`.
- Scene durations must be analyzed from the source video and written numerically. For each base scene clip in `shotstack.json`, set `length` to the analyzed source-scene duration instead of relying on `length: "auto"`.
- `analysis.json` is the timing source of truth. `blueprint.json` must copy the same per-scene `duration_sec`, and the Shotstack scene clip must match that value.
- In canonical `shotstack.json`, use editable text clips for user-changeable source text. In `shotstack.pasteable.json`, keep text styling faithful to the source and only include backdrop overlays when the source itself uses a caption bar or similar mat, or when the user explicitly asks for a redesign.
- Prefer Shotstack `rich-text` assets for editable text overlays. If using legacy `text`, `asset.font` and `asset.stroke` must be objects, for example `font.family`, `font.size`, `font.color`, `stroke.color`, and `stroke.width`; do not use top-level `asset.font` strings, `asset.color`, `asset.size`, or `asset.strokeWidth`.
- Use built-in font families by default, such as `Montserrat`, `Open Sans`, `Roboto`, or `Work Sans`. If a custom font is required, provide a public HTTPS `.ttf` or `.otf` file through `timeline.fonts[].src`; do not use a Google Fonts CSS URL.
- Match source editorial design as closely as Shotstack allows: choose the nearest supported font family, tune font size and stroke to cover the source text cleanly, and line up editable text or insert overlays against the source frame before finalizing.
- If automatic white-box detection is noisy, use a manual bbox measurement or reuse `source_geometry` from a representative frame that shares the same text design family. Record that representative frame in `source_geometry.reference_asset`.
- Convert source coordinates to Shotstack offsets using the full viewport dimensions, not half-dimensions. For `position: "center"`, use `offset.x = center_x / width - 0.5` and `offset.y = 0.5 - center_y / height`. For edge anchors such as `top`, `topRight`, or `topLeft`, convert from the corresponding source margins in the same full-dimension scale.
- For `contract_version` `1.1+`, every editable text overlay should include measured `source_geometry` in `blueprint.json`. If the text is plain stroked text with no box to mask the source, require a clean plate or keep the package `review_required`.
- For Shotstack positioning in this repo, positive `offset.y` moves overlays upward and negative `offset.y` moves them downward. Match caption and label placement against the source frame before finalizing.
- Validate every package before considering the task complete.

## Remotion guardrails

- Use `.agents/skills/remotion-package/SKILL.md` when `blueprint.renderer = "remotion"`.
- Keep Remotion packages review-gated by default. Do not run final renders unless the user explicitly asks for rendering.
- Keep reusable content in JSON props and declare content-facing prop paths in `blueprint.remotion_package.editable_props`.
- Put local Remotion media and audio under `remotion_package/public/` and reference them via `staticFile()` from code.
- Keep `src/index.jsx` minimal with `registerRoot`, and define the composition in `src/Root.jsx` with explicit `id`, `durationInFrames`, `fps`, `width`, `height`, and `defaultProps`.
- Scene timing in `blueprint.scenes[].remotion_sequence` should align with the Remotion composition frame count.
- Run `scripts/validate_remotion_package.py` for every Remotion package before considering it complete.

## Review gate

- Stop at the review gate after producing the blueprint, prompt files, schemas, and Shotstack package.
- If `--shotstack-smoke-render` is explicitly set, one Shotstack smoke render may be used after local validation to confirm the package can render and to compare against the source. Do not call AI media generation providers, do not retry, and keep the result as review evidence rather than a production render.
- Summarize exactly which files changed and where they were saved.
