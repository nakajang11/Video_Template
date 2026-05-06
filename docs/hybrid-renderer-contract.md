# Hybrid Renderer Contract

## Purpose

`renderer: "hybrid"` is a review-gated package type for videos where Shotstack is
still the final assembly layer, but one or more scenes need a code-driven
precomposed video clip from Remotion or Hyperframes.

Use hybrid only when the final timeline benefits from Shotstack Studio
compatibility, source-audio reuse, editable text overlays, or downstream merge
slots, while a scene-level animation would be too brittle to express directly in
Shotstack.

## Non-goals

- Do not replace Shotstack as the final assembler.
- Do not treat Remotion or Hyperframes as the top-level renderer for a
  `renderer: "hybrid"` package. Contract v1.2 separately allows
  `renderer: "hyperframes"` as its own top-level package type.
- Do not run Remotion renders, Hyperframes renders, provider calls, or Shotstack
  final renders by default.
- Do not bake operator-editable copy into precompose clips when it can remain a
  Shotstack text overlay.

## Package Shape

Hybrid packages keep the canonical planning files:

```text
output/<job_id>/
  analysis.json
  story.json
  variable_map.json
  blueprint.json
  template_contract.json
  source_audio.mp3
  manifest.json
  result.json
  package.zip
```

Hybrid packages also include the Shotstack final assembly artifacts:

```text
output/<job_id>/
  shotstack.json
  cloudinary_assets.json
  shotstack.pasteable.json
```

Optional precompose review packages live under scene-scoped directories:

```text
output/<job_id>/
  precompose/
    scene_001/
      remotion/
        package.json
        README.md
        src/
        props/
        public/
        template-partition.json
    scene_002/
      hyperframes/
        package.json
        README.md
        meta.json
        index.html
        assets/
        template-partition.json
```

The precompose package is a review artifact. It may describe how to render the
clip later, but it must not include a rendered final clip unless the caller has
explicitly approved rendering for that step.

## Blueprint Contract

Top-level `blueprint.renderer` must be `hybrid`.

Every hybrid scene must keep a `shotstack` object because Shotstack owns the
final timeline. Scenes that need an inner code-driven clip add `precompose`.

Example:

```json
{
  "scene_id": "scene_001",
  "duration_sec": 3.2,
  "video": {
    "mode": "code-driven",
    "model": null,
    "prompt_file": null,
    "reference_assets": []
  },
  "precompose": {
    "renderer": "remotion",
    "output_merge_key": "SCENE_001_PRECOMP_VIDEO",
    "package_dir": "precompose/scene_001/remotion",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "duration_sec": 3.2,
    "audio_policy": "mute",
    "status": "package_created"
  },
  "shotstack": {
    "asset_type": "video",
    "alias": "SCENE_001",
    "merge_key": "SCENE_001_PRECOMP_VIDEO",
    "clip_length_sec": 3.2,
    "text_overlays": [],
    "overlay_layers": []
  }
}
```

`precompose.output_merge_key` must match `shotstack.merge_key`. The Shotstack
clip uses that merge placeholder as the video source.

## Allowed Inner Renderers

- `remotion`: use for React/props-driven animation, kinetic typography,
  procedural visuals, precise sequence timing, and reusable code compositions.
- `hyperframes`: use for HTML/CSS/JS-native animation packages, web-style
  layouts, caption choreography, or DOM inspection workflows.

Hyperframes is experimental in this repository. It is static-validation-first
and should not become a default render path.

For a top-level Hyperframes package, use `renderer: "hyperframes"` and
`hyperframes_package/` instead of hybrid. Hybrid only uses Hyperframes as an
inner precompose package whose rendered clip will later fill a Shotstack video
merge slot.

## Audio Policy

Hybrid v1 supports only:

- `mute`
- `strip`

`source_audio.mp3` remains the Shotstack timeline audio. Precompose clips must
not preserve their own audio by default, because that can duplicate source audio
or drift against the final Shotstack sequence.

## Editable Text Policy

Operator-editable text stays in Shotstack `text_overlays` unless there is a
specific review-approved reason to bake it into the precompose clip.

Good Shotstack-owned text:

- hook text
- meme captions
- name labels
- year labels
- caption bars
- text that downstream users need to edit without changing code

Good precompose-owned visuals:

- procedural background animation
- graph/chart motion
- mask or reveal motion
- non-editable typography choreography
- scene-local effects that are not intended to be edited in Shotstack Studio

## Template Contract

`template_contract.json` uses `renderer: "hybrid"`.

Contract v1.2 adds `precompose_required: true` and
`precompose_plan.steps[]`. Pending precompose steps carry explicit blockers,
such as `missing_precompose_output` and `pending_adult_ai_materialization`,
until a downstream system renders and approves the clip.

Hybrid slots use Shotstack-style bindings:

```json
{
  "kind": "media",
  "media_kind": "video",
  "fill_strategy": "precompose_video",
  "renderer_binding": {
    "merge_key": "SCENE_001_PRECOMP_VIDEO",
    "alias": "SCENE_001",
    "precompose": {
      "renderer": "remotion",
      "package_dir": "precompose/scene_001/remotion",
      "output_merge_key": "SCENE_001_PRECOMP_VIDEO",
      "status": "package_created"
    }
  }
}
```

The binding stays Shotstack-compatible so downstream systems can fill the final
merge slot after a reviewed precompose render exists.

## Validation Rules

Validation must fail when:

- `renderer = "hybrid"` has no scene-level `precompose`
- any hybrid scene lacks a `shotstack` final assembly binding
- `precompose.renderer` is not `remotion` or `hyperframes`
- `precompose.output_merge_key` is missing, malformed, or differs from
  `shotstack.merge_key`
- `precompose.duration_sec` differs from `scene.duration_sec`
- `precompose.audio_policy` is not `mute` or `strip`
- `precompose.status = "rendered"` or the metadata includes rendered output
  fields without explicit render approval

## Review Gate

Default package generation stops after docs, schemas, blueprint, prompt files,
Shotstack JSON, template contract, and optional precompose review package files.

No default path may:

- run `npx remotion render`
- run `npx hyperframes render`
- call AI media generation providers
- call Shotstack final render

The only exception remains the existing explicit Shotstack smoke path, capped at
one attempt and used only for review evidence.
