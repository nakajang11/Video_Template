# Rendervid PoC for trend_con_87

Artifacts in this folder are intentionally isolated from the canonical `shotstack.json` package.

Files:
- `template.json`: Rendervid template built from the existing analysis and blueprint.
- `template.localhost.json`: same template, but asset URLs are rewritten for a local HTTP server.
- `metadata.json`: frame math and PoC assumptions.
- `validation.json`: optional validation result captured during this test run.
- `render.mp4`: file-URI render attempt captured during this test run.
- `render.localhost.mp4`: localhost-served render output captured during this test run.
- `render.localhost.result.json`: renderer result metadata for the localhost render.

Notes:
- `template.json` is the canonical PoC artifact and uses local `file://` asset URIs.
- `template.localhost.json` assumes the repository root is served over HTTP, for example with `python3 -m http.server 8765`.
- The localhost template targets `http://127.0.0.1:8765/...` asset URLs.
- In this test, `@rendervid/core` validation passed for the template structure.
- In this test, `@rendervid/renderer-node@0.1.0` timed out under `networkidle0` and produced black frames from `file://` video assets, while localhost-served assets rendered visible frames after a temporary throwaway patch switched that wait condition to `domcontentloaded`.
- In this test, the extracted scene clips contained AAC audio, but the final Rendervid MP4s were video-only, so audio carry-through remains unresolved.
