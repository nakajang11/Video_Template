# Remotion Package for input/test_3.mp4

This package rebuilds `input/test_3.mp4` as a review-gated Remotion template.
It now separates three responsibilities on purpose:

- `input media`: source-derived or dummy plates that hold hard-to-recreate
  textures and backdrops
- `animation`: editable text, highlight, glow, and reveal logic implemented in
  code
- `transition`: cross-scene timing and overlap logic implemented in code

What is included:

- `src/Test3GlossaryTemplate.jsx`: code-driven composition for the three-scene
  glossary flow
- `template-partition.json`: exact mapping of which parts are input media,
  animation, and transitions
- `props/default-props.json`: source-faithful text and palette values based on
  the reference clip
- `props/variant-props.json`: swap example showing the same animation can be
  reused with different wording
- `public/source_audio.mp3`: extracted input audio reused by the composition
- `public/assets/scene_001_dictionary_plate.png`: source-derived blurred
  dictionary plate
- `public/assets/scene_002_neural_plate.png`: source-derived neural backdrop
  plate
- `public/assets/scene_003_card_plate.png`: dummy definition-card plate

What is intentionally not included:

- no generated startframe prompt files
- no Kling video prompt files
- no rendered preview outputs at the review gate

How to edit:

- change `props/default-props.json` to swap text, example copy, colors, and
  transition settings
- replace files in `public/assets/` when the backdrop itself should change
- keep `src/Test3GlossaryTemplate.jsx` for reusable motion logic

Typical commands after review approval:

```bash
npm install
npm run studio
npm run render:review
npm run still:variant
```
