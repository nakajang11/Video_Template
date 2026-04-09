# Output Contract

## Canonical Package

Every analyzed job should converge on this package:

```text
output/<job_id>/
  analysis.json
  story.json
  variable_map.json
  blueprint.json
  source_audio.mp3
  scene_001_startframe_image_prompt.md
  scene_001_video_prompt.md
  scene_002_startframe_image_prompt.md
  scene_002_video_prompt.md
  manifest.json
```

Prompt files are scene-scoped. If a scene uses an image-only Shotstack effect,
is rebuilt as a code-driven Remotion sequence, or otherwise avoids standalone
generated media, the scene may omit the corresponding prompt file, but the
omission must be explicit in `blueprint.json`.

Renderer-specific artifacts are conditional.

For `blueprint.renderer = "shotstack"`:

```text
output/<job_id>/
  shotstack.json
  cloudinary_assets.json
  shotstack.pasteable.json
```

For `blueprint.renderer = "remotion"`:

```text
output/<job_id>/
  remotion_package/
    package.json
    README.md
    src/index.jsx
    src/Root.jsx
    props/default-props.json
    public/
```

## `analysis.json`

Purpose:

- record immutable observations from the source video

Minimum fields:

- `job_id`
- `source_video`
- `media.duration_sec`
- `media.width`
- `media.height`
- `analysis_confidence`
- `scenes[]`

Each scene entry should include:

- `scene_id`
- `start_sec`
- `end_sec`
- `duration_sec`
- `summary`
- `characters`
- `camera`
- `evidence_confidence`

`analysis.json` is the source of truth for scene timing.

## `story.json`

Purpose:

- record the full narrative and cast logic before prompt writing

Minimum fields:

- `job_id`
- `premise`
- `plot_type`
- `cast[]`
- `continuity_rules[]`
- `supporting_character_policy`

Use this file to decide whether parent, friend, partner, or age-shift variants are actually required.

## `variable_map.json`

Purpose:

- separate locked elements from changeable elements

Minimum fields:

- `job_id`
- `locks.identity`
- `locks.background`
- `locks.composition`
- `variables.wardrobe`
- `variables.text`
- `variables.motion`
- `model_routing`

Suggested `model_routing` fields:

- `startframe_default`
- `wardrobe_edit`
- `video_default`
- `motion_transfer`

## `blueprint.json`

Purpose:

- convert findings into a machine-readable per-scene execution plan
- `contract_version` `1.1` and later add measured text geometry for editable overlays

Required top-level fields:

- `contract_version`
- `job_id`
- `source_video`
- `renderer`
- `audio`
- `review_status`
- `scene_order`
- `scenes`

`renderer` should be one of:

- `shotstack`
- `remotion`

Use `shotstack` by default. Switch to `remotion` when the source depends on
kinetic typography, procedural graphics, matte-like reveals, or other animation
that would be brittle in Shotstack.

`audio` should include:

- `strategy`
- `source_file`
- `shotstack_merge_key`

Each scene must define:

- `scene_id`
- `duration_sec`
- `story_role`
- `cast`
- `locks`
- `variables`
- `startframe`
- `video`

Renderer-specific fields:

- `shotstack` when `renderer = "shotstack"`
- `remotion_sequence` when `renderer = "remotion"`

`startframe` should include:

- `required`
- `model`
- `prompt_file`
- `reference_assets`

`video` should include:

- `mode`
- `model`
- `prompt_file`
- `reference_assets`

`video.mode` may be `code-driven` when the scene will be rebuilt as a Remotion
sequence rather than generated as standalone media.

`shotstack` should include:

- `asset_type`
- `alias`
- `merge_key`
- `clip_length_sec`
- `text_overlays`
- `overlay_layers`

`blueprint.scenes[].duration_sec` must match `analysis.scenes[].duration_sec` for the same `scene_id`.
When `renderer = "shotstack"`, `blueprint.scenes[].shotstack.clip_length_sec` must match that same duration.

`remotion_sequence` should include:

- `sequence_id`
- `start_frame`
- `duration_frames`
- `editable_props`

Use `editable_props` to declare which JSON props are expected to change without
rewriting the composition logic.

When `renderer = "remotion"`, `blueprint.json` should also include a top-level
`remotion_package` object with:

- `package_dir`
- `entry_file`
- `composition_id`
- `props_file`
- `editable_props`

Each `overlay_layers[]` entry should include:

- `asset_type`
- `merge_key`
- `relative_start_sec`
- `duration_sec`
- `position`
- `width`
- `height`

Use `overlay_layers` for image-on-video and video-on-video compositions such as picture-in-picture cards, inset photos, or reference panels.
Use `text_overlays` for editable hook text, name labels, year labels, meme captions, or other source text that should remain user-editable in Shotstack rather than baked into remake media.

For `contract_version` `1.1` and later, each editable `text_overlays[]` entry should also include `source_geometry` with:

- `design_role`
- `reference_asset`
- `anchor`
- `editor_preview_strategy`
- `font_candidates`
- `font_size_hint`
- `stroke_px`
- `text_bbox_px`

`reference_asset` may point to a representative frame from the same label or caption design family when the scene-specific frame is too noisy for reliable automatic detection.

For boxed labels or caption bars, also include:

- `box_bbox_px`
- `padding_px`

If `editor_preview_strategy = "editable_on_clean_plate"`, also include:

- `clean_plate_file`

Recommended strategies:

- `editable_over_box_background` for white-box labels or caption bars that can hide the source text cleanly
- `editable_on_clean_plate` for plain text or other layouts that need a clean remake plate or explicit clean plate
- `manual_review_required` when the package cannot yet provide a faithful editable Studio preview

When deriving Shotstack text clips from `source_geometry`, scale source-pixel font sizes and box dimensions to the target output viewport. For example, a `font_size_hint` measured on a `576x1024` reference frame should be scaled before use in a `1080x1920` package rather than copied verbatim.

## Prompt File Naming

Use deterministic scene ids and filenames:

- `scene_001_startframe_image_prompt.md`
- `scene_001_video_prompt.md`
- `scene_002_startframe_image_prompt.md`
- `scene_002_video_prompt.md`

Do not mix `scene_1` and `scene_001`.

## `shotstack.json`

Only required when `renderer = "shotstack"`.

Rules:

- use the extracted `source_audio.mp3` as the default audio source
- represent the source audio as an `asset.type = "audio"` clip on its own track for Shotstack editor compatibility; avoid `timeline.soundtrack`
- when using an audio clip, place `volume` inside `asset` and use numeric `start` and `length`
- remove editable source text from remake base media and rebuild it as Shotstack `asset.type = "text"` clips with merge keys such as `SCENE_001_TITLE` or `SCENE_001_CAPTION`
- ignore platform logos, watermarks, usernames, and logo text by default unless the user explicitly wants them preserved
- omit a terminal social-platform end slate by default when it is purely branded SNS UI rather than creative story content
- place higher-priority visual layers earlier in `timeline.tracks`: text first, source-authentic text backdrops next when they exist, base visuals below them
- Use double-brace placeholders in template strings, for example `{{ SCENE_001_MEDIA }}`
- Use uppercase merge keys
- Keep `merge[].find` values brace-free
- Prefer Shotstack `alias` and `alias://...` references for overlay timing
- You may use `start: "auto"` for sequential ordering, but each base scene clip must set a numeric `length` equal to the analyzed source-scene duration

## `cloudinary_assets.json`

Only required when `renderer = "shotstack"`.

Purpose:

- record the uploaded Cloudinary assets used for editor-ready testing

Minimum fields:

- `cloud_name`
- `uploaded_at`
- `assets[]`

Each asset entry should include:

- `type`
- `scene_id`
- `public_id`
- `secure_url`

Include `duration_sec` for uploaded scene clips when applicable.

## `shotstack.pasteable.json`

Only required when `renderer = "shotstack"`.

Rules:

- embed Cloudinary `secure_url` values directly and do not use merge placeholders
- keep the editor-compatible dedicated audio clip track pattern
- prefer explicit numeric `start` values for base clips and overlays to reduce editor ambiguity
- if the source uses a translucent caption bar or other text box, preserve that design in the paste-ready Studio clip alongside the direct editable text overlay
- if the source uses plain stroked text with no backdrop, keep the paste-ready text overlay plain and do not invent a new box
- align caption and label offsets against the source frame, remembering that positive `offset.y` moves upward and negative `offset.y` moves downward
- convert source pixel positions to Shotstack offsets using the full viewport dimensions. For center-anchored overlays, use `offset.x = center_x / viewport_width - 0.5` and `offset.y = 0.5 - center_y / viewport_height`. For `top`, `topLeft`, or `topRight` anchors, convert from source margins on the same full-dimension basis
- do not use `width` or `height` on image overlay clips, because Shotstack Studio rejects them there; use `fit`, `scale`, `position`, and `offset` for image overlay sizing instead
- do use text-box `width` and `height` when needed to match the source label or caption card dimensions
- choose the closest supported Shotstack font family and tune font size, stroke, box size, and offsets so editable text sits directly over the source design
- derive font size and box size from `source_geometry` in output-space pixels, not source-space pixels
- if automatic box detection fails on a noisy frame, use a manual bbox or reuse geometry from a representative frame with the same label design
- omit the `merge` array
- keep `output` minimal so the JSON can be pasted directly into the Shotstack editor

Recommended placeholder style:

- `SOURCE_AUDIO_MP3`
- `SCENE_001_MEDIA`
- `SCENE_001_TITLE`
- `SCENE_002_IMAGE`

Avoid:

- `{age1}`
- `{{age2}}`
- `VIDEO_SRC` when the clip actually references `MEDIA_2`

## `remotion_package/`

Purpose:

- provide a reviewable Remotion template package when Shotstack is not the best
  fit for the source motion design

Minimum structure:

- `package.json`
- `README.md`
- `src/index.jsx`
- `src/Root.jsx`
- `props/default-props.json`
- `public/`

Recommended additions:

- `props/variant-*.json`
- `renders/`

## `manifest.json`

Purpose:

- provide a single index of artifacts and review state

Minimum fields:

- `job_id`
- `renderer`
- `review_status`
- `artifacts[]`
- `notes`

Each artifact entry should include:

- `type`
- `path`
- `scene_id`
- `status`

## Validation Checklist

Before a package is considered ready:

- `source_audio.mp3` exists
- `renderer` is explicit in `blueprint.json` and `manifest.json`
- every scene id is unique
- every `analysis.json` scene duration matches the corresponding `blueprint.json` scene duration
- every referenced prompt file exists
- every overlay layer in the blueprint fits inside its parent scene duration
- review status is explicit

For `renderer = "shotstack"`:

- the extracted source audio is represented as a Shotstack audio clip track instead of `timeline.soundtrack`
- every base Shotstack scene clip uses a numeric `length`
- every base Shotstack scene clip length matches the corresponding analyzed scene duration
- `cloudinary_assets.json` exists and every listed asset has a `secure_url`
- `shotstack.pasteable.json` exists and uses direct URLs instead of merge placeholders
- every Shotstack placeholder has a matching merge key
- every merge key is actually used
- every alias reference resolves to a declared alias

For `renderer = "remotion"`:

- `remotion_package/` exists with the required files
- the blueprint includes `remotion_package` metadata
- normal content changes can be made by swapping JSON props instead of rewriting the composition source
