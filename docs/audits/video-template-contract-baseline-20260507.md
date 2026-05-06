# Video_Template Contract Baseline Audit - 2026-05-07

## Scope

Repository: `nakajang11/Video_Template`

Baseline commit: `a61a31cb125074fc18a366edb6cfaea3f0c73397`

This audit is read-only baseline context for the contract v1.2 completion work.
It does not authorize provider calls, paid media generation, Adult AI runtime DB
mutation, or final rendering.

## Current State

- `scripts/template_package_support.py` builds `template_contract.json` with
  `TEMPLATE_CONTRACT_VERSION = "1.0"`.
- Current result and blueprint renderer enums support `shotstack`, `remotion`,
  and `hybrid`.
- `hybrid` currently means Shotstack final assembly plus scene-level
  Remotion/Hyperframes `precompose` metadata.
- Hyperframes is present as an inner hybrid precompose renderer, but not yet as a
  top-level package renderer.
- The current Adult AI consumer profile is
  `adult_ai_influencer_media_template`, which creates
  `assembly_flow_suggestion.json`.
- `adult_ai_influencer_template_contract.json` is not generated yet.
- Standalone validator entrypoints for template contract, Adult AI consumer
  contract, Hyperframes package, and hybrid precompose plan are not present yet.
- There is no committed `examples/` fixture set.

## Local Worktree Notes

The local worktree contains untracked `input/` and `output/` artifacts. They are
generated/source-package work areas and must not be broadly staged.

## Safety Boundary

The implementation must remain in the Video_Template package-contract layer only.
Adult AI owns runtime materialization, DB resolution, approvals, preview render,
media effects, publishing, queues, and runtime identity/coverage/wardrobe packs.

No paid generation, provider API call, Remotion render, Hyperframes render, or
Shotstack final render is allowed by default.
