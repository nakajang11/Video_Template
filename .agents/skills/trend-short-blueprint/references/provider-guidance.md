# Provider Guidance

## Nano Banana 2

Use `nano banana2` as the default model for startframe generation and multi-reference composition.

Prompting rules adapted from the Google Cloud Nano Banana guide:

- start with a clear action verb
- be specific about subject, lighting, composition, and background
- prefer positive framing over a long list of negations
- for text-only generation, structure the prompt as subject plus action plus background plus composition plus style
- for multi-reference generation, make each attachment role explicit as reference image plus relationship plus new scenario
- for image editing, clearly state what changes and what must stay fixed

This makes Nano Banana a good fit for:

- room-locked garment composites
- identity-consistent startframes
- timeline snapshots when the exact scene must be freshly generated

## Grok Imagine

Use `grok imagine` for wardrobe replacement scenes rather than for broad scene invention.

Best use cases:

- outfit swap with face and framing preserved
- changing one garment while keeping body, composition, and room mostly fixed

Guardrail:

- if the request is broader than wardrobe editing, prefer `nano banana2`

## Kling V3

Use `kling v3` when the startframe is approved and the next step is prompt-driven motion.

Prompt-writing rules:

- anchor the motion to the exact uploaded start frame
- describe only the allowed movement budget
- state camera lock or camera movement explicitly
- keep environment and composition continuity explicit
- specify duration and realism expectations

Recommended fields to preserve in the blueprint:

- `motion_intent`
- `camera_lock`
- `duration_sec`
- `negative_motion`
- `reference_assets`

## Kling V3 Motion Control

Use `kling v3 motion control` only when the output must inherit motion from a reference clip.

Good fit:

- dance transfer
- gesture transfer
- specific camera-move transfer

Guardrail:

- do not default to motion control when a normal Kling prompt is enough

## Important note

The official Kling quickstart page linked by the user was not text-extractable from this environment during setup, so keep Kling-specific controls abstract in the blueprint. Prefer stable semantic fields over UI-specific toggle names.
