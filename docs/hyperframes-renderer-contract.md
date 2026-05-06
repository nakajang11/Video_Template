# Hyperframes Renderer Contract

`renderer: "hyperframes"` is a top-level review-gated package type for
HTML/CSS/JS-native animation packages.

Hyperframes is an assembly renderer in this repository. It must not be used as a
media generation provider, a model route in `generation_policy`, or a default
render execution path.

## Package Shape

```text
output/<job_id>/
  analysis.json
  story.json
  variable_map.json
  blueprint.json
  template_contract.json
  adult_ai_influencer_template_contract.json
  source_audio.mp3
  manifest.json
  result.json
  package.zip
  hyperframes_package/
    package.json
    README.md
    meta.json
    index.html
    assets/
    template-partition.json
```

`hyperframes_package/meta.json` records static composition metadata:

- `composition_id`
- `width`
- `height`
- `fps`
- `duration_sec`
- `render_status`, normally `not_rendered`

`hyperframes_package/template-partition.json` exposes editable slots, each with
a stable `slot_id` and `graph_ref`.

## Template Contract

Hyperframes slots use graph references:

```json
{
  "slot_id": "scene_001.text.title",
  "kind": "text",
  "media_kind": null,
  "fill_strategy": "generate_text",
  "generation_policy": {
    "model_route": null,
    "prompt_file": null,
    "reference_assets": [],
    "renderer_use": "hyperframes_input"
  },
  "renderer_binding": {
    "graph_ref": "nodes.title.text",
    "package_dir": "hyperframes_package"
  }
}
```

`generation_policy.model_route` must not be `hyperframes`,
`hyperframes_package`, or `hyperframes_renderer`.

## Review Gate

Default validation is static only:

- check required package files
- check `meta.json`
- check editable graph slots
- check `template_contract.json`
- reject remote URLs, default render commands, and rendered status claims

No default path may run:

- `npx hyperframes render`
- provider APIs
- Shotstack final render
- Remotion render
