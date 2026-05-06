# Oracle Planning Request: Video_Template Contract Completion

Validity gate:

This planning review is valid only if the observed model is GPT-5.5 Pro / Extended Pro.
If the observed model is GPT-5 Pro, unknown, fallback, or cannot be verified, respond only:

```yaml
observed_model:
review_validity: invalid_review
verdict: reject_without_review
reason: wrong_model_or_fallback
```

Mode:

- Review mode: GitHub connector + browser mode.
- Use the currently selected GitHub connector repository: `nakajang11/Video_Template`.
- Do not rely on local attachments, screenshots, private media URLs, DB dumps, or secrets.
- Browser model picker should already be set by the human; do not require a model switch.

Current repo baseline:

- Repo: `nakajang11/Video_Template`
- Branch: `main`
- Baseline commit: `a61a31cb125074fc18a366edb6cfaea3f0c73397`
- Baseline includes the previous hybrid renderer contract commit.
- Known untracked local files under `input/` and `output/` must be ignored and are not part of GitHub connector review.

Project boundary:

`Video_Template` produces validated template packages for `adult-ai-influencer`.

It may do:

- source video analysis
- story/scene/variable extraction
- slot manifest and stable slot IDs
- renderer-specific package artifacts
- `template_contract.json`
- `adult_ai_influencer_template_contract.json`
- validation scripts and examples

It must not do:

- adult runtime DB mutation
- paid image/video generation
- provider calls
- Post Engine approvals
- publishing
- production queue mutation
- identity/coverage/wardrobe pack mutation
- final rendering by default

Mission:

Make `Video_Template` emit a validated package contract that Adult AI can import without manual translation, so Adult AI can later perform slot materialization, startframe/key image generation, approval, render preview, media effects, and publish through its own gates.

Requested target from the attached implementation brief:

- Contract version should move to `1.2`.
- Renderer support must cover `shotstack`, `remotion`, `hyperframes`, and `hybrid`.
- `precompose_required` must be explicit.
- Every slot must have stable `slot_id`.
- Slot schema should include `kind`, `media_kind`, `required`, `fill_strategy`, `generation_policy`, `approval_policy`, `renderer_binding`, and `validation`.
- Fill strategies should include:
  - `generate_startframe`
  - `generate_image_slot`
  - `generate_video_slot`
  - `select_existing_asset`
  - `reuse_template_asset`
  - `reuse_source_trend_video`
  - `generate_text`
  - `precompose_video`
  - `keep_locked`
- Hyperframes should be represented as a renderer/assembly target, not an image model.
- Hybrid/precompose should include `precompose_plan.steps[]`, `input_slots`, `output_slot`, and blockers when output is missing.
- Add `--consumer-profile adult_ai_influencer_template` support and generate `adult_ai_influencer_template_contract.json`.
- Consumer contract must use tokenized refs only and exclude private URLs, local absolute paths, secrets, adult DB IDs, provider responses, and paid generation output.
- Add/extend validators:
  - `scripts/validate_template_contract.py`
  - `scripts/validate_adult_ai_consumer_contract.py`
  - `scripts/validate_hyperframes_package.py`
  - `scripts/validate_hybrid_precompose_plan.py`
- Add committed example packages:
  - `examples/shotstack_basic/`
  - `examples/remotion_basic/`
  - `examples/hyperframes_basic/`
  - `examples/hybrid_precompose/`
- Do not run paid generation, provider APIs, Hyperframes render, Remotion render, or Shotstack render.

Please inspect the GitHub connector repo and propose a practical implementation plan.

Required response format:

```yaml
observed_model:
review_validity:
verdict: approve | approve_with_conditions | request_revisions | reject_without_review
score:
repo_findings:
blocking_risks:
recommended_scope_for_this_session:
phase_plan:
  phase_0_baseline_audit:
  phase_1_contract_schema_v12:
  phase_2_hyperframes_binding:
  phase_3_hybrid_precompose:
  phase_4_adult_ai_consumer_profile:
  phase_5_validation_and_examples:
  phase_6_cross_repo_import_fixture:
test_plan:
files_to_change:
files_not_to_change:
no_paid_generation_assessment:
overall_recommendation:
```
