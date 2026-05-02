# Hyperframes Adoption Review

調査対象: [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes/)
一次情報 commit: `b9a9998ff068f04c16b43d0bb0e1719b2c3fe2c4`
npm package: `hyperframes@0.4.37`
調査方針: read-only。Codex plugin install、npm install、renderer 実行、provider call、final render は行わない。

## 概要

Hyperframes は HTML/CSS/GSAP を動画 composition のソースとして扱い、headless Chrome と FFmpeg で frame-by-frame に MP4 を生成する OSS video rendering framework。AI agent 向けの skills / Codex plugin も提供されている。

主な特徴:

- HTML native: `index.html` と `data-*` 属性で scene/timing/media を表現する。
- agent-first: `npx skills add heygen-com/hyperframes` または Codex plugin で authoring / CLI skill を追加できる。
- deterministic rendering: frame seek ベースで同じ入力から同じ出力を狙う。
- CLI: `npx hyperframes init`, `lint`, `inspect`, `preview`, `render`, `transcribe`, `tts`, `doctor`。
- local requirements: Node.js `>=22` と FFmpeg。現在のローカル環境は `node v23.5.0`, `ffmpeg 8.1` で要件を満たす。

## Infulencer_Shotstack との相性

`partially adopt` が妥当。既存の `shotstack` / `remotion` を置き換えるのではなく、将来の第3 renderer 候補として小さく試すのがよい。

相性がよい用途:

- kinetic typography、caption choreography、SNS overlay、lower-third、animated label など、HTML/CSS で正確に組める表現。
- data visualization、chart race、shader transition、webpage-to-video のような Shotstack では手作業が増える素材。
- Remotion よりも JSX/React 化の負担を下げたい、HTML をそのまま editable template source として保存したいケース。
- `hyperframes inspect` による text overflow / clipping の自動検査。既存の text geometry guardrail と相性がよい。

相性が悪い、または注意が必要な用途:

- Shotstack Studio で直接レビュー・編集する package。Hyperframes HTML は Shotstack JSON / merge placeholders とは互換ではない。
- 既存 downstream が `renderer in {shotstack, remotion}` を前提にしている箇所。schema / result contract を不用意に広げると strict consumer を壊す。
- 最終レンダー自動化。Hyperframes の render は local/free でも、この repo の review gate では final render をデフォルト成果物にしない。
- distributed rendering / production scale。README 上では single-machine today とされており、Remotion Lambda 相当の成熟度は前提にしない。
- full repo clone / skill install。Git LFS や plugin side effect があるため、導入時は sparse/plugin install か npm CLI 利用に限定する。

## 既存 renderer との対応

| 対象 | 現在の役割 | Hyperframes 導入後の位置づけ |
| --- | --- | --- |
| Shotstack | default。scene sequencing、editable text overlay、Studio review | 引き続き default。Shotstack Studio compatibility が必要なら Hyperframes にしない |
| Remotion | code-driven typography、procedural graphics、JSON props template | React/Remotion が必要な複雑 composition のまま維持 |
| Hyperframes | 未導入 | HTML-native animation package。Remotion より軽い authoring が有利な場合だけ opt-in |

## 採用しない方がよいもの

- `hyperframes render` を pipeline default に入れること。
- Codex plugin / skills を repo 初期化時に自動 install すること。
- Hyperframes の TTS / transcription をこの repo の標準 provider execution として扱うこと。
- Shotstack JSON と同じ `merge[]` contract に無理やり変換すること。
- Adult AI Influencer 側の DB、Cloudinary、paid generation、template execution に踏み込むこと。
- external CDN 前提の GSAP / assets を review package の唯一の実行経路にすること。必要なら local vendoring を検討する。

## 導入するなら最小単位

Phase 0: research only

- このドキュメントを採用判断の記録として残す。
- 依存追加、plugin install、schema 変更、render 実行はしない。

Phase 1: experimental package target

- `docs/renderer-routing.md` に `hyperframes` を experimental renderer として追加する。
- `docs/output-contract.md` に `output/<job_id>/hyperframes_package/` を追加する。
- package shape は以下に限定する。

```text
output/<job_id>/hyperframes_package/
  package.json
  README.md
  meta.json
  index.html
  compositions/
  assets/
  source_audio.mp3
  template-partition.json
```

- `blueprint.renderer = "hyperframes"` を許可する場合は、`blueprint.hyperframes_package` に `package_dir`, `entry_file`, `composition_id`, `editable_props` を持たせる。
- `template_contract.json` の slot binding は Remotion の `prop_path` に近い形で、HTML text/media editable fields を指す。

Phase 2: validator only

- `scripts/validate_hyperframes_package.py` を追加する。
- 最初は静的検査だけにする。
  - required files
  - `index.html` の `data-composition-id`, `data-width`, `data-height`
  - timed elements の `data-start`, `data-duration`, `data-track-index`
  - `window.__timelines` registration
  - local asset paths under `assets/`
  - `source_audio.mp3`
  - `template_contract.json` binding
- 明示指定がある場合だけ `npx hyperframes lint` / `inspect` を review smoke として許可する。
- `npx hyperframes render` は final render 扱いにして、ユーザー明示承認があるまで禁止する。

Phase 3: tiny pilot

- kinetic typography か data visualization の短い source を1本だけ選び、`--preferred-renderer hyperframes` 相当の実験で package を作る。
- 既存 `shotstack` / `remotion` の default route と result schema を壊さないため、最初は CLI option ではなく手動 pilot か hidden experimental flag にする。

## 必要な repo 変更候補

本格導入時の変更候補:

- `docs/renderer-routing.md`: `hyperframes` の選択条件と review gate を追加。
- `docs/output-contract.md`: `hyperframes_package/` の artifact contract を追加。
- `schemas/run_result.schema.json`: `renderer` enum に `hyperframes` を追加。ただし strict consumer 影響があるため最後に変更する。
- `scripts/run_pipeline.py`: `--preferred-renderer hyperframes` を追加する場合は validator routing も同時に追加。
- `scripts/template_package_support.py`: `derive_hyperframes_slots()` を追加。
- `scripts/validate_hyperframes_package.py`: static validation と optional CLI smoke。
- `.agents/skills/hyperframes-package/SKILL.md`: repo-local package shape を Hyperframes upstream skills より優先する guardrail。

## 結論

`partially adopt`

Hyperframes はこの repo に合うが、Shotstack/Remotion の置き換えではない。最初の導入価値は「HTML-native な code-driven review package」の追加であり、final render engine の導入ではない。

推奨は Phase 1/2 の最小実験。`renderer = "hyperframes"` を experimental として追加し、package と validator を作る。ただし `render` は明示承認があるまで禁止し、default renderer は引き続き Shotstack、複雑な React/props template は Remotion のままにする。
