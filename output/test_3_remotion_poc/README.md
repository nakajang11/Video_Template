# Remotion PoC for input/test_3.mp4

This isolated package explores whether Remotion is a better fit than Shotstack
for typography-heavy motion graphics like `input/test_3.mp4`.

What is included:

- `src/Test3EpiphanyPoC.jsx`: the composition code
- `props/default-props.json`: the default render inputs
- `props/variant-props.json`: a replacement-data example showing the same
  template can be reused with different words and colors
- `public/test_3_audio.m4a`: audio extracted from the source video

Key goal:

- prove a Remotion flow where the animation logic stays in code while the
  editable content lives in JSON props

Typical commands:

```bash
npm install
npm run studio
npm run render
npm run still:variant
```

Rendered during this PoC:

- `renders/test_3_remotion_poc.mp4`
- `renders/test_3_variant_finale.png`
