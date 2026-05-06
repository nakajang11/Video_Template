# Adult AI Template Consumer Contract

`adult_ai_influencer_template_contract.json` is the primary Adult AI import
artifact for `consumer_profile=adult_ai_influencer_template`.

It is generated only from validated `template_contract.json` v1.2. It must not
be populated from `cloudinary_assets.json`, `shotstack.pasteable.json`, Adult AI
database lookups, Cloudinary URL resolution, wardrobe randomization, provider
responses, or render outputs.

## Boundary

This repository may describe template slots and renderer bindings. It must not:

- mutate Adult AI runtime state
- resolve Adult AI DB ids
- resolve Cloudinary URLs
- select wardrobe or identity assets
- call paid generation providers
- render precompose or final videos

## Shape

Minimum fields:

- `consumer_profile: "adult_ai_influencer_template"`
- `schema_version: "adult_ai_influencer_template_contract.v1"`
- `contract_version: "1.2"`
- `source.repo`
- `source.commit`
- `source.job_id`
- `template`
- `slots[]`
- `renderer`
- `validation`

Every slot includes a deterministic `token_ref`:

```json
{
  "slot_id": "scene_001.media.main",
  "kind": "media",
  "media_kind": "video",
  "fill_strategy": "generate_video_slot",
  "token_ref": "{{slot.scene_001.media.main}}",
  "approval_policy": {
    "requires_slot_approval": true,
    "approval_type": "post_template_slot"
  },
  "renderer_binding": {
    "merge_key": "SCENE_001_MEDIA"
  }
}
```

Adult AI can map the token refs to its own runtime assets after review. The
contract does not carry actual media URLs.

## Validation

Validation rejects:

- resolved URLs
- local absolute paths
- provider response keys
- generated media URL keys
- Adult-side DB id keys
- secret-like values
- duplicate `slot_id` values
- non-tokenized `token_ref` values
- contracts not generated from v1.2 `template_contract.json`

Use:

```bash
python3 scripts/validate_adult_ai_consumer_contract.py output/<job_id>
```
