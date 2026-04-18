# Claude Code Backend Usage

## Recommended setup

Keep this repository as the dedicated backend workspace.

Claude Code should not import the whole repository into its own main working directory. Instead, it should call this repository through the backend CLI so Claude only needs to pass:

- source video path
- `job_id`
- optional Codex model override

This keeps Claude-side token usage much lower than mirroring the full repository and asking Claude to explore all of the sample outputs, assets, and prior package files.

## Entry point

Use:

```bash
python3 scripts/run_pipeline.py \
  --input-video /absolute/path/to/source.mp4 \
  --job-id my_job \
  --preferred-renderer auto \
  --context-json /absolute/path/to/context.json \
  --result-json
```

The command will:

1. stage the input video as `input/<job_id>.mp4`
2. invoke `codex exec` inside this repository
3. ask Codex to follow the repo-local workflow and stop at the review gate
4. run the local package validator
5. write `output/<job_id>/result.json`
6. print the structured result

`--preferred-renderer` is optional and accepts `auto`, `shotstack`, or
`remotion`.

Shotstack smoke rendering is off by default. For a review-only external smoke,
callers may pass:

- `--shotstack-smoke-render`
- `--shotstack-mcp-mode render-once`
- `--shotstack-smoke-limit 1`

The limit is intentionally fixed at one attempt. The CLI rejects higher values
to prevent automatic render loops. The smoke hook uses the
`SHOTSTACK_MCP_RENDER_COMMAND` adapter when configured; without it, the run
records a configuration-required smoke result and does not call Shotstack.
Shotstack MCP is treated as an external render smoke path, not the primary
validator; the repo-local validator must pass before any smoke attempt.

For Remotion packages, the backend uses the repo-local `$remotion-package`
workflow and `scripts/validate_remotion_package.py`. That validator is static
by default and checks composition metadata, JSON prop paths, local public assets,
scene frame ranges, and `template_contract.json`. A Remotion CLI smoke may be
run manually with `python3 scripts/validate_remotion_package.py output/<job_id> --run-cli-smoke`.

For difficult source analysis, the repo also provides `$video-analysis-support`.
It can create optional `timeline_view/` contact sheets and `transcript_packed.md`
without changing the package contract or rendering a final video.

Caller context is optional and may be provided with either:

- `--context-json /path/to/context.json`
- `--context-inline-json '{"template_type":"A-7_trend_single"}'`

Do not pass both at once.

## Dry run

To inspect the command shape and prompt without spending Codex tokens:

```bash
python3 scripts/run_pipeline.py \
  --input-video /absolute/path/to/source.mp4 \
  --job-id my_job \
  --dry-run \
  --result-json
```

## Suggested Claude Code wrapper behavior

Claude Code should behave like a thin orchestrator:

1. receive a local video path from the user
2. generate or accept a `job_id`
3. run the backend CLI in this repository
4. read the returned JSON
5. report:
   - `status`
   - `renderer`
   - `review_status`
   - `caller_context_echo`
   - `source_summary`
   - `package_summary`
   - `package_dir`
   - key artifact paths
   - validation errors or warnings

Claude Code should avoid re-exploring this repository unless the backend returns a failure that needs human investigation.

## Output files

For each run, the backend writes these run-specific files under `output/<job_id>/`:

- `request.json`
- `codex_prompt.txt`
- `run.log`
- `codex_result.json` when Codex returns a structured result
- `validator.log` when the validator emits output
- `result.json`
- `template_contract.json`
- `package.zip` when validation passes
- `remotion_package/` when `renderer = "remotion"`
- `timeline_view/` or `transcript_packed.md` when optional source evidence was generated
- `shotstack_smoke_result.json` when Shotstack smoke was requested
- `shotstack_smoke_compare.json` and `shotstack_smoke_contact_sheet.jpg` when a local smoke render is available for comparison

`request.json` stores the raw caller context, while `result.json` returns only a
compact `caller_context_echo` summary.

These files are intended to make debugging possible without making Claude re-read the whole repository.

## Notes

- The backend still follows the repository rule that it stops at the review gate.
- Paid generation and final rendering are intentionally out of scope. The only exception is an explicitly requested Shotstack smoke render, capped at one attempt and used only for validation/comparison notes.
- If the planning confidence is low, the backend should return `review_required` instead of inventing unsupported details.
