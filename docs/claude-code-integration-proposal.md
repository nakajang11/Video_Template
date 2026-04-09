# Claude Code Integration Proposal

## Goal

Enable a Claude Code driven workflow where a user can provide one input short video and receive a validated template package from this repository.

The returned package should stop at the current review gate and include:

- `analysis.json`
- `story.json`
- `variable_map.json`
- `blueprint.json`
- `manifest.json`
- `source_audio.mp3`
- scene prompt files
- `shotstack.json`

This proposal keeps the current repository rule that paid generation and final rendering are out of scope.

## Assumptions

- Claude Code can invoke a local command or a local MCP tool.
- The repository remains the source of truth for artifact structure and validation rules.
- The integration target is "generate the template package", not "render the final video".
- The current two-phase workflow stays intact:
  1. analysis and blueprint generation
  2. prompt and Shotstack packaging

## Current State

The repository already has most of the domain logic defined as workflow instructions and validation rules:

- project workflow and review gate in `AGENTS.md`
- planning phase in `.agents/skills/trend-short-blueprint/`
- packaging phase in `.agents/skills/shotstack-remix-package/`
- output contract in `docs/output-contract.md`
- package validator in `.agents/skills/shotstack-remix-package/scripts/validate_package.py`
- audio extraction script in `.agents/skills/shotstack-remix-package/scripts/extract_source_audio.sh`

What is still missing is a stable machine-callable entrypoint. Right now the repo explains how an agent should work, but it does not yet expose one command or one tool that Claude Code can call with structured inputs and outputs.

## Recommendation

Implement the integration in two stages.

### Stage 1: CLI wrapper

Create one deterministic command that Claude Code can run:

```bash
python3 scripts/run_pipeline.py \
  --input-video /absolute/path/to/video.mp4 \
  --job-id trend_con_7 \
  --output-root output \
  --result-json
```

This should be the primary integration surface.

### Stage 2: MCP wrapper

After the CLI is stable, expose the same pipeline as a small local MCP server so Claude Code can call it as a named tool instead of constructing shell commands.

This keeps the hard part in the pipeline code and makes the transport replaceable.

## Why CLI First

- It is the smallest change from the current repository shape.
- It is easy to test locally and in CI.
- Claude Code can call it even without a custom app integration.
- The same command can later be wrapped by MCP, HTTP, or job queues.
- Validation and error reporting are easier to keep deterministic in a process boundary.

## Target User Flow

1. A user gives Claude Code a local video path or uploads a video.
2. Claude Code calls this repository's pipeline entrypoint with the input path and a `job_id`.
3. The pipeline creates or refreshes `input/<job_id>.mp4`.
4. The planning phase generates:
   - `analysis.json`
   - `story.json`
   - `variable_map.json`
   - `blueprint.json`
5. The packaging phase:
   - extracts `source_audio.mp3`
   - writes scene prompt files
   - writes `shotstack.json`
   - updates `manifest.json`
6. The validator checks package consistency.
7. The pipeline returns a small JSON result with:
   - status
   - review status
   - artifact paths
   - validation summary
   - human-readable notes
8. Claude Code replies with the returned package paths and, if needed, the review-required reason.

## Proposed Architecture

```text
Claude Code
  -> pipeline entrypoint
     -> job staging
     -> source inspection
     -> planning phase
     -> packaging phase
     -> validation
     -> structured result
```

## Proposed Components

### 1. Pipeline entrypoint

Add:

- `scripts/run_pipeline.py`

Responsibilities:

- parse arguments
- create a normalized `job_id`
- copy or symlink the source video into `input/<job_id>.mp4`
- orchestrate the planning and packaging phases
- call validation
- emit a final JSON response

Suggested CLI flags:

- `--input-video`
- `--job-id`
- `--output-root`
- `--skip-package`
- `--skip-validation`
- `--result-json`
- `--force`

### 2. Planning runner

Add:

- `scripts/run_planning_phase.py`

Responsibilities:

- inspect the source video with deterministic helpers such as `ffprobe` and frame extraction
- load repository instructions and schemas
- produce:
  - `analysis.json`
  - `story.json`
  - `variable_map.json`
  - `blueprint.json`
  - initial `manifest.json`

Important note:

This phase is currently described as an agent workflow, not as a standalone script. The cleanest implementation is to move the reusable logic into Python helpers and keep the language-model specific prompt assembly in one adapter module.

### 3. Packaging runner

Add:

- `scripts/run_packaging_phase.py`

Responsibilities:

- call `extract_source_audio.sh`
- write prompt files from `blueprint.json`
- build `shotstack.json`
- update `manifest.json`
- call `validate_package.py`

### 4. Shared helpers

Add:

- `scripts/lib/job_paths.py`
- `scripts/lib/media_probe.py`
- `scripts/lib/frame_sampling.py`
- `scripts/lib/manifest_ops.py`
- `scripts/lib/result_formatter.py`

Responsibilities:

- centralize path building
- keep media inspection deterministic
- avoid duplicating package bookkeeping

### 5. JSON contract for Claude Code

Add:

- `schemas/run_request.schema.json`
- `schemas/run_result.schema.json`

Suggested result payload:

```json
{
  "status": "ok",
  "job_id": "trend_con_7",
  "renderer": "shotstack",
  "review_status": "approved_for_packaging",
  "package_dir": "output/trend_con_7",
  "artifacts": {
    "analysis": "output/trend_con_7/analysis.json",
    "story": "output/trend_con_7/story.json",
    "variable_map": "output/trend_con_7/variable_map.json",
    "blueprint": "output/trend_con_7/blueprint.json",
    "manifest": "output/trend_con_7/manifest.json",
    "shotstack": "output/trend_con_7/shotstack.json",
    "remotion_package": null
  },
  "validation": {
    "passed": true,
    "errors": [],
    "warnings": []
  },
  "notes": [
    "Package stops at the review gate."
  ]
}
```

## Planning Phase Design

The planning phase should be split into deterministic work and model-assisted work.

### Deterministic work

- read media metadata with `ffprobe`
- sample representative frames
- detect coarse cuts when possible
- gather source frame references
- prefill package metadata

### Model-assisted work

- explain story structure
- decide cast continuity
- separate locks from variables
- assign model routing
- decide overlay-layer requirements

This split matters because Claude Code integration becomes much more stable when only the interpretation layer depends on the model.

## Integration Modes

### Mode A: Claude Code runs the local CLI directly

Recommended first release.

Flow:

1. Claude Code receives a video path.
2. Claude Code runs `python3 scripts/run_pipeline.py ...`.
3. Claude Code reads the JSON result.
4. Claude Code returns the artifact paths to the user.

Pros:

- fastest implementation
- no extra runtime process
- easiest to debug

Cons:

- command invocation details live in Claude Code prompts unless wrapped again later

### Mode B: Claude Code calls a local MCP tool

Recommended second release.

Add a tiny MCP server with one tool such as:

- `build_trend_template(input_video_path, job_id, force=false)`

The MCP tool should internally call the same `run_pipeline.py`.

Pros:

- cleaner user experience inside Claude Code
- typed tool interface
- reusable by other agents

Cons:

- more moving parts
- extra setup for local tool registration

### Mode C: HTTP service

Not recommended as the first step.

This is only worth it if the pipeline must be called by many clients outside local agent environments.

## Output Semantics

The integration should explicitly return one of these statuses:

- `ok`
- `review_required`
- `validation_failed`
- `input_error`
- `internal_error`

Recommended behavior:

- `ok`: package created and validator passed
- `review_required`: package created but the blueprint or story confidence is low
- `validation_failed`: files exist but package consistency checks failed
- `input_error`: missing video, unsupported media, or bad arguments
- `internal_error`: unexpected exception

## File Layout Proposal

```text
docs/
  claude-code-integration-proposal.md
scripts/
  run_pipeline.py
  run_planning_phase.py
  run_packaging_phase.py
  lib/
    job_paths.py
    manifest_ops.py
    media_probe.py
    frame_sampling.py
    result_formatter.py
schemas/
  run_request.schema.json
  run_result.schema.json
```

## Implementation Steps

### Milestone 1: Stable CLI shell

Deliver:

- `run_pipeline.py` argument parsing
- job staging into `input/<job_id>.mp4`
- final JSON result envelope

At this milestone, internal phase calls may still be thin wrappers.

### Milestone 2: Deterministic packaging phase

Deliver:

- audio extraction wiring
- prompt file generation wiring
- `shotstack.json` builder
- `manifest.json` update logic
- validator execution and structured error reporting

This milestone should make the second half of the flow stable first.

### Milestone 3: Planning phase runner

Deliver:

- media probing
- frame extraction
- structured planning outputs
- review-status assignment

This is the most important and highest-risk milestone because it replaces the currently manual or agent-driven interpretation step.

### Milestone 4: MCP adapter

Deliver:

- local MCP server
- single build tool
- tool result mapped from `run_result.schema.json`

## Validation Strategy

Every pipeline run should execute:

1. source file existence check
2. media probe check
3. package validation using `validate_package.py`
4. result JSON schema validation

The CLI should exit non-zero for:

- `validation_failed`
- `input_error`
- `internal_error`

It may still exit zero for `review_required` if the package was created successfully and the caller is expected to inspect it.

## Observability

Each run should write:

- `output/<job_id>/run.log`
- `output/<job_id>/manifest.json`
- `output/<job_id>/result.json`

`result.json` should match the returned terminal JSON so Claude Code and a human reviewer see the same state.

## Risks

### Risk 1: The planning phase is not fully scripted yet

Today the repository documents the planning workflow well, but the logic still depends on agent interpretation. This is the main gap for Claude Code integration.

Mitigation:

- move deterministic inspection into scripts first
- keep prompt templates and model output normalization explicit
- require conservative `review_required` when confidence is low

### Risk 2: Validation drift between blueprint and Shotstack

Some existing sample outputs already show why validation matters.

Mitigation:

- keep `analysis.json` as the timing source of truth
- always populate `clip_length_sec`
- fail fast on merge-key or alias mismatches

### Risk 3: Claude Code transport assumptions may differ by environment

Different environments may prefer local command execution, MCP tools, or wrappers.

Mitigation:

- treat the CLI as the canonical backend
- keep MCP as a thin adapter only

## Recommendation Summary

The best implementation path is:

1. build a single stable CLI entrypoint
2. script the packaging phase fully
3. progressively script the planning phase
4. wrap the CLI in a local MCP tool for Claude Code

This gives the repository a reliable callable backend without changing its core artifact contract or review-gated workflow.

## Acceptance Criteria

The proposal is considered implemented when Claude Code can:

1. pass one video path and one `job_id`
2. receive a structured success or review-required result
3. open a completed `output/<job_id>/`
4. find a validator-checked `shotstack.json`
5. return those artifact paths to the user without manual repo-specific steps
