# Video_Template Contract v1.2 Codex Implementation Plan

Date: 2026-05-07

Repo: `nakajang11/Video_Template`

Base SHA: `a61a31cb125074fc18a366edb6cfaea3f0c73397`

Initial Oracle planning review:

- Request: `docs/reviews/oracle/2026-05-07-video-template-contract-v12-initial-plan-request.md`
- Response: `docs/reviews/oracle/2026-05-07-video-template-contract-v12-initial-plan-response.md`
- Observed model: GPT-5.5 Pro
- Review validity: valid
- Verdict: approve_with_conditions

## Objective

Complete the Video_Template package contract so Adult AI can import a generated
template package without manual translation. The repo remains a review-gated
package producer and must not execute Adult AI runtime logic, provider calls,
paid media generation, publishing, or final renders.

## Implementation Scope

### 1. Contract v1.2 Core

- Set `TEMPLATE_CONTRACT_VERSION` to `1.2`.
- Add `schemas/template_contract.v1.2.schema.json`.
- Add top-level contract fields:
  - `template_id`
  - `aspect_ratio`
  - `duration_seconds`
  - `preferred_renderer`
  - `fallback_renderers`
  - `precompose_required`
  - `renderer_bindings`
  - `precompose_plan`
  - `consumer_profiles`
  - `validation`
- Keep existing `template_type`, `supported_content_types`,
  `fill_requirements`, `package_summary`, and `slots[]` for compatibility.
- Add `hyperframes` to renderer enums while keeping `shotstack`, `remotion`, and
  `hybrid`.

### 2. Slot v1.2 Shape

Every slot emitted by `build_template_contract()` must include:

- `slot_id`
- `scene_id`
- `kind`
- `media_kind`
- `required`
- `fill_strategy`
- `generation_policy`
- `approval_policy`
- `renderer_binding`
- `validation`

Fill strategies will be explicit:

- `generate_startframe`
- `generate_image_slot`
- `generate_video_slot`
- `select_existing_asset`
- `reuse_template_asset`
- `reuse_source_trend_video`
- `generate_text`
- `precompose_video`
- `keep_locked`

The old broad `generate_media` strategy will not be emitted by v1.2 contracts.

### 3. Hyperframes

- Add `hyperframes` as a top-level renderer in:
  - blueprint schema
  - run result schema
  - CLI `--preferred-renderer`
  - renderer routing docs
  - output contract docs
- Add `hyperframes_package` blueprint metadata.
- Add `derive_hyperframes_slots()` and top-level
  `renderer_bindings.hyperframes`.
- Add `scripts/validate_hyperframes_package.py` as a static validator only.
- Do not run `npx hyperframes render` by default.

### 4. Hybrid / Precompose

- Promote scene-level `precompose` metadata into a contract-level
  `precompose_plan`.
- Add `scripts/validate_hybrid_precompose_plan.py`.
- Validate:
  - `precompose_required` implies `precompose_plan.steps[]`.
  - every `input_slot` exists.
  - every `output_slot` exists.
  - output slot uses `precompose_video`.
  - missing precompose output has explicit blockers.
  - no rendered output/provider response/final video is implied without approval.

### 5. Adult AI Consumer Contract

- Add `adult_ai_influencer_template` consumer profile.
- Keep `adult_ai_influencer_media_template` as a backward-compatible alias that
  still creates the older `assembly_flow_suggestion.json`.
- Generate `adult_ai_influencer_template_contract.json` when the new profile is
  requested.
- Add `schemas/adult_ai_influencer_template_contract.schema.json`.
- Add `scripts/validate_adult_ai_consumer_contract.py`.
- Consumer contract must contain tokenized references only and reject:
  - private URLs
  - Cloudinary direct URLs
  - local absolute paths
  - secrets
  - Adult runtime DB IDs
  - provider responses
  - generated media URLs
  - paid-generation artifacts

### 6. Examples

Add stable committed fixtures:

- `examples/shotstack_basic/`
- `examples/remotion_basic/`
- `examples/hyperframes_basic/`
- `examples/hybrid_precompose/`

Each example will include canonical planning files, `template_contract.json`,
`adult_ai_influencer_template_contract.json`, `manifest.json`, `result.json`,
and a small `package.zip` fixture. Example assets must be placeholders or
tokenized/static review artifacts only.

### 7. Documentation

Update:

- `docs/output-contract.md`
- `docs/renderer-routing.md`
- `docs/hybrid-renderer-contract.md`
- `docs/claude-code-backend-usage.md`

Add:

- `docs/adult-ai-consumer-contract.md`
- `docs/hyperframes-renderer-contract.md`

### 8. Tests

Add/extend tests for:

- contract version `1.2`
- renderer enum accepts `hyperframes` and `hybrid`
- all slots include v1.2 fields
- split fill strategies
- Hyperframes package validation
- hybrid precompose plan validation
- Adult AI consumer contract safety
- example package validation
- CLI dry-run for `--preferred-renderer hyperframes`
- CLI dry-run for `--consumer-profile adult_ai_influencer_template`
- package archives include required contracts and exclude render outputs

## Explicit Non-Goals

- No Adult AI runtime code changes.
- No DB mutation.
- No Cloudinary URL resolution.
- No provider calls.
- No paid media generation.
- No Remotion render.
- No Hyperframes render.
- No Shotstack final render.
- No broad staging of `input/` or generated `output/` folders.

## Verification Plan

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/validate_template_contract.py examples/shotstack_basic/template_contract.json
python3 scripts/validate_template_contract.py examples/remotion_basic/template_contract.json
python3 scripts/validate_template_contract.py examples/hyperframes_basic/template_contract.json
python3 scripts/validate_template_contract.py examples/hybrid_precompose/template_contract.json
python3 scripts/validate_adult_ai_consumer_contract.py examples/hybrid_precompose/adult_ai_influencer_template_contract.json
python3 scripts/validate_hyperframes_package.py examples/hyperframes_basic
python3 scripts/validate_hybrid_precompose_plan.py examples/hybrid_precompose
python3 -m json.tool schemas/run_result.schema.json >/tmp/run_result.schema.check
python3 -m json.tool schemas/template_contract.v1.2.schema.json >/tmp/template_contract.schema.check
python3 -m json.tool schemas/adult_ai_influencer_template_contract.schema.json >/tmp/adult_ai_contract.schema.check
git diff --check
```

## Review Gate

Before implementation, this plan must be reviewed through Oracle browser mode
using GitHub connector context and the GPT-5.5 Pro / Extended Pro validity gate.

## Oracle Plan Review Conditions Incorporated

The plan review response at
`docs/reviews/oracle/2026-05-07-video-template-contract-v12-plan-review-response.md`
returned `review_validity: valid`, `observed_model: GPT-5.5 Pro`, and
`implementation_go_no_go: go_with_conditions`.

The following conditions are binding for implementation:

- Hyperframes is renderer/assembly only. It must never be accepted as a media
  generation model, provider, or `generation_policy.model_route` value.
- `adult_ai_influencer_template_contract.json` must be generated only from the
  validated v1.2 `template_contract.json`, not from URL-bearing sidecars such as
  `cloudinary_assets.json` or `shotstack.pasteable.json`.
- `docs/hybrid-renderer-contract.md` must distinguish
  top-level `renderer: "hyperframes"` from `renderer: "hybrid"` with an inner
  Hyperframes precompose package.
- `precompose_plan.steps[].status` vocabulary is:
  `planned`, `package_created`, `pending_render`, `blocked`, and `rendered`.
- `precompose_plan.steps[].blockers[].code` vocabulary is:
  `missing_precompose_output`, `pending_adult_ai_materialization`,
  `missing_input_slot`, `missing_output_slot`, `invalid_renderer_binding`, and
  `render_output_not_approved`.
- `media_kind` is nullable for text, color, and number slots; it is `audio` for
  audio slots and `image` or `video` for media/overlay slots.
- Validators must be schema plus semantic validators. They must perform
  cross-reference validation, recursive leak scanning, archive-content scanning,
  and no-render subprocess guards.
- Tests must include negative cases for URL leakage, local path leakage, missing
  blockers, invalid renderer binding, Hyperframes-as-generation-model misuse, and
  accidental render-output inclusion.
