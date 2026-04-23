# prompt-lens Adoption Review

調査対象: [raojiacui/prompt-lens](https://github.com/raojiacui/prompt-lens)  
一次情報 commit: `7b9e2cd8030c884a6a8f5b8d2a296ef6bcaaa508`  
調査方針: read-only。コード、UI、DB、認証、storage、secret handling、provider call は移植しない。

## 概要

`prompt-lens` は Next.js ベースの prompt reverse-engineering アプリで、画像/動画フレームを LLM vision provider に渡し、動画生成向けの構造化 prompt を返す。主な構成は以下。

- `lib/utils/frame-extractor.ts`: browser canvas による均等フレーム抽出
- `lib/video-processor/index.ts`: `fluent-ffmpeg` による動画メタデータ取得、均等 frame extraction、base64 化
- `lib/ai/analyzer.ts`: Zhipu / Gemini / OpenRouter の簡易 provider 切り替えと、single / batch analysis prompt
- `lib/audio-processor/index.ts`, `lib/audio-processor/llm-segmenter.ts`, `app/api/audio-analyze/route.ts`: audio extraction、Whisper/AssemblyAI 文字起こし、LLM segment 化
- `lib/db/schema.ts`: `analysis_history`, `audio_analysis`, `video_clip`, `operation_logs`, `user_api_keys`
- `lib/video-processor/editor.ts`, `app/api/video-edit/route.ts`: FFmpeg video edit 系

## Infulencer_Shotstack に有用そうな機能

- prompt 分析観点: subject / environment / camera / lighting / style / mood、および batch での temporal continuity / camera movement / visual consistency / narrative rhythm は、`trend-short-blueprint` の `analysis.json` と `blueprint.json` の観察項目に近い。
- frame extraction の考え方: `duration / (frameCount + 1)` で端を避けて均等抽出する方針は、レビュー用 contact sheet や scene start/end evidence の軽量補助に使える。ただし実装は既存の FFmpeg/Python 支援へ吸収する。
- audio transcript の構造: `TranscriptionSegment { start, end, text }` と `VideoSegment { start, end, summary, tags }` は、`transcript_packed.md` や downstream handoff の dialogue/segment 表現に参考になる。
- 保存項目: `analysis_history` の `mediaType`, `mediaUrl`, `frameCount`, `analyzeMode`, `prompt`, `corePrompt`, `tags`, `favorite` は、Infulencer_Shotstack では DB ではなく `manifest.json` / package artifact の metadata として参考にする程度がよい。

## 採用しない方がよい機能

- Next.js UI、dashboard、history UI、settings UI
- Supabase/Drizzle/better-auth/user/session schema
- R2/B2 storage layer、upload/download API
- `user_api_keys`、暗号化 API key 保存、provider secret handling
- Gemini/OpenRouter/Zhipu/DeepSeek/AssemblyAI の provider call 実装
- video edit / clip / final render 系 API
- `@ffmpeg-installer+win32-x64` 固定 path と `ffmpeg.exe` 前提
- `eval(videoStream.r_frame_rate)` の fps parse
- provider response をそのまま prompt/history として保存する実装

## 既存 workflow との対応表

| prompt-lens 要素 | 参考にできる点 | Infulencer_Shotstack 側の対応 |
| --- | --- | --- |
| `lib/utils/frame-extractor.ts` | browser/canvas の均等抽出 | 既存の `$video-analysis-support` にある `timeline_view/` と contact sheet の補助観点のみ |
| `lib/video-processor/index.ts` | FFprobe metadata、均等 timestamp、frame base64 化 | `scripts/run_pipeline.py` の staged input と repo-local FFmpeg helper に寄せる。Windows 固定 path は不採用 |
| `lib/ai/analyzer.ts` single prompt | subject/environment/camera/lighting/style/mood | `trend-short-blueprint` の観察軸として部分採用 |
| `lib/ai/analyzer.ts` batch prompt | temporal continuity、camera movement、visual consistency、rhythm | `analysis.json.scenes[]` と `blueprint.scenes[]` の scene/cut 推定観点として部分採用 |
| `lib/audio-processor/*` | `{start,end,text}` transcript と `{start,end,summary,tags}` segment | `transcript_packed.md`、将来の dialogue extraction、Adult handoff suggestion の source audio token へ構造だけ参考 |
| `app/api/analyze/route.ts` | analysis start/complete/error の保存タイミング | DB ではなく `request.json`, `result.json`, `manifest.json` の package-local state に対応 |
| `lib/db/schema.ts` | history/result の保存項目 | `template_contract.json` と optional artifact metadata の項目候補として参考 |
| provider abstraction | provider 名で分岐する最小インターフェイス | provider execution は行わず、`assembly_flow_suggestion.json` では tokenized handoff steps の `target` だけに限定 |

## 実装に取り込むなら最小単位

1. prompt 分析観点のラベルだけを `analysis.json` / prompt 設計の checklist に反映する。
2. 均等 keyframe 抽出の考え方だけを、既存 FFmpeg helper の review evidence 用に参考化する。
3. audio transcript は `{start_sec,end_sec,text,speaker?}` と `{start_sec,end_sec,summary,tags}` のような保存形式だけ参考化する。
4. history/result は DB ではなく package-local artifact の metadata として保存する。

## `assembly_flow_suggestion.json` への有用性

役立つ。特に以下の観点を Adult AI Influencer 向け handoff suggestion に反映できる。

- start frame reference を source scene token として渡す考え方
- prompt generation step の前段に、subject / scene / wardrobe / room / camera / lighting を分ける観点
- source audio を実 URLではなく `{{source_audio.url}}` token として渡す構造
- 実行済み provider result ではなく、`image_prompt`, `image_generate`, `video_prompt`, `video_generate`, `assemble`, `validate` の提案 step として保存する形式

ただし、この repo では Adult 側 DB id、Cloudinary URL、wardrobe random select、provider execution、render result は扱わない。

## 結論

`partially adopt`

採用候補は限定する。取り込むのは prompt 分析観点、frame extraction の考え方、audio transcript の構造化、analysis result の保存形式だけ。アプリ基盤、認証、DB、UI、storage、deployment、provider call、API key handling、video edit/final render は採用しない。
