# Remotion Package for input/test_2.mp4

This package rebuilds `input/test_2.mp4` as an editable Remotion template.

The package is intentionally split into three kinds of responsibility:

- `input media`: scenic background plates and the knight foreground cutout
- `animation`: word reveals, slight plate drift, and foreground positioning
- `transition`: the opening split-curtain and background crossfades

Edit points:

- Replace files in `public/assets/` to change the scenic look or foreground
  character asset.
- Edit `props/default-props.json` to swap words, timings, and text styling.
- Keep `src/Test2QuoteTemplate.jsx` as the reusable motion and layout logic.

Typical commands:

```bash
npm install
npm run studio
npm run render:review
```
