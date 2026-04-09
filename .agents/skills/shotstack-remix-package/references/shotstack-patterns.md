# Shotstack Patterns

## Core principles

- Keep timing logic inside Shotstack whenever possible.
- Use scene aliases instead of copying raw numbers into overlay clips.
- Use merge fields only for values that truly change per package.

## Merge field rules

Correct style:

- template string: `{{ SCENE_001_MEDIA }}`
- merge key: `SCENE_001_MEDIA`

Do not mix styles like:

- `{age1}`
- `{{age2}}`
- `video_src`

## Alias rules

For scene-scoped overlays:

- declare an alias on the base clip, for example `SCENE_001`
- reference it with `alias://SCENE_001` for overlay `start` or `length`

This avoids manual synchronization drift.

## Track strategy

Recommended default order:

- Track 0: text overlays that must sit on top
- Track 1: caption backdrops or other visual mats that sit behind text when the source design includes them
- Track 2: base visuals
- Track 3: extracted source audio from `output/<job_id>/source_audio.mp3`
- Track 4: optional additional overlays that intentionally sit below top text

Use a scene-independent merge key for audio:

- `{{ SOURCE_AUDIO_MP3 }}`

For Shotstack editor compatibility:

- keep the source audio as a normal `asset.type = "audio"` clip on Track 0
- put `volume` inside the `asset` object
- use `start: 0` and a numeric `length` that matches the source media duration
- avoid `timeline.soundtrack` in repo templates and paste-ready variants
- upload the testable local assets to Cloudinary and record them in `cloudinary_assets.json`
- build a separate `shotstack.pasteable.json` that swaps placeholders for direct `secure_url` values and removes the `merge` array
- avoid `width` and `height` on image overlay clips in `shotstack.pasteable.json`, because Shotstack Studio rejects them there; use `fit: "contain"` plus `scale` for image overlay sizing instead
- Shotstack uses the earlier entries in `timeline.tracks` as the visually higher layers, so keep text before backdrop and backdrop before base video
- for this repository's positioning workflow, positive `offset.y` moves overlays upward and negative `offset.y` moves them downward
- convert source pixel geometry to Shotstack offsets using the full viewport dimensions. Do not double the normalized values. For a center-anchored clip, `offset.x = center_x / viewport_width - 0.5` and `offset.y = 0.5 - center_y / viewport_height`
- for source-faithful editable text, record `source_geometry` in the blueprint rather than only prose like `placement` or `style`

## Scene asset strategy

When the scene uses a generated video clip:

- `asset.type = "video"`
- `src = "{{ SCENE_001_MEDIA }}"`

When the scene uses a generated still image with Shotstack motion:

- `asset.type = "image"`
- `src = "{{ SCENE_001_IMAGE }}"`
- add a Shotstack effect such as `zoomInSlow` or `zoomOut`

When the scene contains an inset image or picture-in-picture element:

- keep the main scene clip on the base visual track
- place the inset asset on a higher track
- use a dedicated merge key such as `SCENE_001_OVERLAY_001_IMAGE`
- store overlay timing in the blueprint as `relative_start_sec` and `duration_sec`
- store overlay placement in the blueprint as `position`, `width`, `height`, and optional `offset`

When the source includes editable editorial text:

- remove that text from the remake base image or video prompt whenever possible
- recreate it as a dedicated Shotstack text clip with a scene-scoped merge key such as `SCENE_001_TITLE`, `SCENE_002_LABEL`, or `SCENE_001_CAPTION`
- choose the closest supported Shotstack font family and tune `size`, `stroke`, text-box dimensions, and `offset` so the editable layer sits directly over the source design
- when the source uses a clean white label box or caption bar, measure the source `box_bbox_px`, `text_bbox_px`, and `padding_px` and derive Shotstack width, height, position, and offset from those values
- scale the resulting Shotstack font size and box dimensions to the output viewport; do not reuse source-space font sizes directly in a larger render size
- if a scene-specific frame is too noisy for reliable white-box detection, reuse `source_geometry` from a representative frame with the same label design or supply a manual bbox
- ignore platform watermarks, usernames, logos, and logo text unless the user explicitly asks to keep them
- if the source uses a translucent caption bar or similar text mat, preserve that design in the paste-ready Studio preview behind the editable text clip
- if the source text is plain stroked or shadowed text with no backdrop, keep the paste-ready overlay plain as well instead of inventing a new box
- if the source text is plain stroked or shadowed text with no backdrop, do not depend on a source-derived clip for editable Studio preview unless a clean plate is provided

When the final source scene is only a branded platform end slate:

- keep it in `analysis.json` as an immutable source observation
- omit it from `blueprint.json`, `shotstack.json`, and `shotstack.pasteable.json` by default unless the user explicitly asks to preserve it

## Timing strategy

Preferred:

- `start: "auto"`
- explicit numeric `length` for each base scene clip, copied from the analyzed source scene duration in `analysis.json` and `blueprint.json`

Use numeric timing only when the effect requires an exact editorial cut.

For this repository, each declared scene alias should belong to a base clip with a numeric `length` equal to the source scene's `duration_sec`.

## Safety checks

Before finalizing:

- verify every alias reference exists
- verify every merge key is used
- verify every placeholder is uppercase and scene-scoped
- verify the blueprint and Shotstack package refer to the same scene ids
