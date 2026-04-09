# Trend Short Video Agent Plan

## Goal

Build a repo-local Codex agent flow that takes a reference short video, analyzes the scenes, cuts, story, and reusable variables, then produces:

- a reusable planning package
- image prompts for `nano banana2` or `grok imagine`
- video prompts for `kling v3` or `kling v3 motion control`
- a validated `shotstack.json`

The workflow should stop before paid generation or paid rendering.

## What Exists Today

Current inputs:

- `input/sample_1.mp4`
- `input/sample_2.mp4`

Current outputs:

- `output/sample_1/blueprint.json`
- `output/sample_1/scene_1_startframe_image_prompt.md`
- `output/sample_1/scene_2_startframe_image_prompt.md`
- `output/sample_1/scene_2_video_prompt.md`
- `output/sample_1/shotstack.json`
- `output/sample_2/blueprint.json`
- `output/sample_2/scene_1_startframe_image_prompt.md`
- `output/sample_2/scene_2_startframe_image_prompt.md`
- `output/sample_2/scene_3_startframe_image_prompt.md`
- `output/sample_2/scene_3_video_prompt.md`
- `output/sample_2/shotstack.json`

Observed media metadata:

- `sample_1.mp4`: `10.332s`, `720x1280`
- `sample_2.mp4`: `6.036s`, `720x1280`

## Sample Audit

### `sample_1`

What the folder implies:

- Two-scene vertical influencer clip.
- Scene 1 uses a startframe prompt that composites a garment, locked background, and the influencer's hands.
- Scene 2 uses a strict face-preservation outfit-replacement prompt.
- Scene 2 also has a Kling-style low-motion video prompt.
- `shotstack.json` stitches one generated clip with another clip and reuses the source audio.

What is missing:

- No persisted scene analysis or cut report.
- No explicit cast registry.
- No variable map explaining what is fixed versus what is swap-ready.
- No artifact manifest tying prompt files to blueprint scene ids.

What is inconsistent:

- `shotstack.json` contains `VIDEO_START` in `merge`, but the template does not reference it.
- The blueprint is too loose to validate against the prompt files or Shotstack payload.

### `sample_2`

What the folder implies:

- Three-scene timeline or age-progression format.
- Scene 1 and Scene 2 are still images animated in Shotstack with `zoomInSlow` and `zoomOut`.
- Scene 3 becomes a generated motion clip and uses overlaid year and age text.
- This format requires global plot understanding because the subject age changes across scenes and may imply off-screen family involvement.

What is missing:

- No explicit explanation of the time-jump structure.
- No record of which text values are variable versus locked.
- No formal mapping from scene ids to merge keys.

What is inconsistent:

- `shotstack.json` mixes `{age1}`, `{{age2}}`, and `{age3}` placeholder styles.
- The video clip references `{{ MEDIA_2 }}`, but the `merge` array exposes `VIDEO_SRC`.
- Merge keys such as `year` and `age` are too generic for multi-scene packages.

## Design Conclusions

The sample folders prove the desired deliverables, but they also show why the agent needs stricter intermediate artifacts.

The agent should always split the work into four phases:

1. Source analysis
2. Story and variable extraction
3. Blueprinting
4. Prompt and Shotstack packaging

That separation lets us review the plot and cast before we commit to image and video prompts.

## Proposed Repository Structure

Keep the current top-level folders and add repo-local skills:

```text
input/
output/
docs/
.agents/
  skills/
    trend-short-blueprint/
    shotstack-remix-package/
```

Canonical output package for a new job:

```text
output/<job_id>/
  analysis.json
  story.json
  variable_map.json
  blueprint.json
  manifest.json
  source_audio.mp3
  scene_001_startframe_image_prompt.md
  scene_001_video_prompt.md
  scene_002_startframe_image_prompt.md
  scene_002_video_prompt.md
  shotstack.json
```

## Artifact Responsibilities

`analysis.json`

- Media metadata
- Scene boundaries
- Source-of-truth scene durations
- Visual evidence
- Camera, framing, and pacing observations
- Confidence and review flags

`story.json`

- One global synopsis across all scenes
- Cast registry for lead, parent, friend, partner, or childhood self
- Role dependencies and continuity notes

`variable_map.json`

- What must stay locked
- What may be replaced or parameterized
- Which model is responsible for each variable type

`blueprint.json`

- Per-scene scene ids, durations, role in the story, cast, overlays, and model routing
- Source-audio policy and the merge key used by Shotstack
- Expected prompt filenames
- Expected Shotstack aliases and merge keys
- Per-scene Shotstack clip length equal to the analyzed source-scene duration
- Optional `overlay_layers` for image-on-video or video-on-video compositions

`manifest.json`

- Machine-readable list of every artifact in the package
- Review status

`source_audio.mp3`

- MP3 extracted from the input video
- Default audio source for the Shotstack package

`shotstack.json`

- Final reusable Shotstack edit template
- Uses aliases and merge fields consistently

## Skill Split

### Skill 1: `trend-short-blueprint`

Responsibilities:

- inspect the input video and any prior output artifacts
- infer scene boundaries and plot flow
- detect whether supporting characters are actually needed
- decide what is locked versus variable
- write `analysis.json`, `story.json`, `variable_map.json`, and `blueprint.json`

Review gate:

- stop here if plot or cast confidence is low

### Skill 2: `shotstack-remix-package`

Responsibilities:

- take an approved blueprint package
- extract `source_audio.mp3` from the input video
- write scene prompt files
- build `shotstack.json`
- validate placeholders, aliases, and required files

Review gate:

- stop after a valid package exists

## Why This Structure Fits the Referenced Docs

OpenAI Codex docs:

- repository-level `AGENTS.md` is the right place for project norms
- repo-local skills belong in `.agents/skills`
- `agents/openai.yaml` gives UI metadata and invocation hints

Shotstack docs:

- merge placeholders use double braces inside template strings
- `merge[].find` values do not include braces
- aliases and smart clips are a better fit than hand-copying timing numbers

Project-specific timing rule:

- base scene clips in Shotstack should still use explicit numeric `length` values copied from the analyzed source scene durations
- aliases remain useful for overlays and sync, but they should sit on top of fixed scene durations instead of replacing them

Additional layout rule:

- if a scene contains a picture-in-picture image, inserted portrait card, or any image/video overlay, represent it as a separate overlay layer on a higher Shotstack track instead of merging it into the base asset description

Nano Banana guidance:

- prompts should be specific, positive, and composition-aware
- multi-reference image generation works best when each reference has an explicit relationship
- image editing prompts should state both what changes and what remains locked

Kling guidance:

- the user-selected stack is `kling v3` with optional `kling v3 motion control`
- because the official Kling quickstart page was not text-extractable in this environment, the repo should keep Kling controls abstract in the blueprint and only commit to stable fields such as `duration_sec`, `camera_lock`, `motion_intent`, `motion_reference_asset`, and `negative_motion`

## Implementation Choices In This Commit

- Add a repository `AGENTS.md`
- Add two repo-local skills under `.agents/skills`
- Add an explicit output contract document
- Add starter schemas and a Shotstack template skeleton
- Add a validator script so placeholder drift is caught early
