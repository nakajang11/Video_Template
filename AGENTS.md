# AGENTS.md

## Repository expectations

- This repository is for planning and packaging trend short-form videos, not for paid media generation or final rendering.
- Preserve `input/` as the source area and `output/` as the deliverable area. Treat existing `sample_1` and `sample_2` as examples of the target artifact shape, not as a perfect contract.
- Before writing prompts or Shotstack JSON, separate immutable findings from creative decisions:
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
- For female-influencer videos, explicitly identify the lead identity lock, wardrobe lock, background lock, on-screen text pattern, optional supporting cast, and the global plot before turning anything into prompts.
- If the source contains editorial text that should remain changeable, such as hook text, name labels, year labels, or meme captions, remove it from the remake base media and rebuild it as editable Shotstack text overlays. Ignore platform logos, watermarks, usernames, and logo text unless the user explicitly asks to preserve them.
- For boxed labels or caption bars, measure the source text geometry and carry it into `blueprint.json` so `shotstack.json` and `shotstack.pasteable.json` can be derived from actual source rectangles rather than manual eyeballing.
- When converting measured source text into Shotstack, scale font size and box dimensions from the source viewport to the final output viewport. Do not reuse source-pixel font sizes directly in `1080x1920` packages.
- If the source scene contains picture-in-picture, inserted photos, reference cards, or any image-on-video composition, model that as a base scene clip plus overlay layers instead of flattening it into one vague prompt.
- If a parent, friend, partner, or childhood self might be required, confirm it from the full plot across scenes. If the evidence is weak, mark the package as `review_required` instead of inventing extra characters.
- If the last scene is only a social-platform end slate or branded SNS outro, omit it from the remake package by default unless the user explicitly asks to keep it.

## Model routing

- Default startframe and multi-reference composition model: `nano banana2`
- Outfit swap or clothing replacement model: `grok imagine`
- Image-to-video motion model: `kling v3`
- Reference motion transfer model: `kling v3 motion control`
- Never call provider APIs, run paid generations, or render with Shotstack unless the user explicitly asks and approves it.
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
- Match source editorial design as closely as Shotstack allows: choose the nearest supported font family, tune font size and stroke to cover the source text cleanly, and line up editable text or insert overlays against the source frame before finalizing.
- If automatic white-box detection is noisy, use a manual bbox measurement or reuse `source_geometry` from a representative frame that shares the same text design family. Record that representative frame in `source_geometry.reference_asset`.
- Convert source coordinates to Shotstack offsets using the full viewport dimensions, not half-dimensions. For `position: "center"`, use `offset.x = center_x / width - 0.5` and `offset.y = 0.5 - center_y / height`. For edge anchors such as `top`, `topRight`, or `topLeft`, convert from the corresponding source margins in the same full-dimension scale.
- For `contract_version` `1.1+`, every editable text overlay should include measured `source_geometry` in `blueprint.json`. If the text is plain stroked text with no box to mask the source, require a clean plate or keep the package `review_required`.
- For Shotstack positioning in this repo, positive `offset.y` moves overlays upward and negative `offset.y` moves them downward. Match caption and label placement against the source frame before finalizing.
- Validate every package before considering the task complete.

## Review gate

- Stop at the review gate after producing the blueprint, prompt files, schemas, and Shotstack package.
- Summarize exactly which files changed and where they were saved.
