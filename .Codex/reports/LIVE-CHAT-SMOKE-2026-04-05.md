# Live Chat Smoke 2026-04-05

## Scope

Live chat prompts run against the real HTTP backend after:
- `direct_identity` was split onto a deep runtime socket
- chat failover chain was moved to `zhipu -> ollama -> openrouter`
- Ollama base URL was switched to `http://host.docker.internal:11434`
- direct-lane Zhipu selfhood/emotion SLAs were raised

## Main Artifacts

- Source report (completed): `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-05-190456.json`
- Source report (latest partial with newer direct selfhood): `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-05-191611.json`
- Curated composite for viewer: `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-live-chat-composite-2026-04-05.json`
- Viewer HTML: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`
- Viewer screenshot: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest-full-2026-04-05.png`

## Current Truth

### Direct Selfhood + Bong

- `origin / sync` improved materially in the latest partial run:
  - provider: `openrouter`
  - model: `qwen/qwen3.6-plus:free`
  - visible thinking present
  - answer stays in Wiii lore and mentions `The Wiii Lab`
- `origin / stream` is still unstable:
  - it can still time out on the primary selfhood path and collapse to the generic answer
  - latest failover evidence shows `zhipu` selfhood was still timing out before final fallback
- `bong_followup / stream` is now often the stronger side:
  - visible thinking present
  - answer keeps `Bông` as the virtual cat, not a random unknown person
- `bong_followup / sync` can still fall into the generic error bubble

### Emotion Direct

- `sadness` is still not healthy in the latest completed run:
  - sync + stream both answered with the generic `Mình là Wiii! Bạn muốn tìm hiểu gì hôm nay?`
  - this is not a viewer bug; it is a real runtime/provider-quality problem

## Architectural Reading

- The `direct_identity` socket change was correct and did help `origin/selfhood`.
- The next real bottleneck is no longer just renderer/plumbing.
- It is now the interaction between:
  - direct-lane SLA policy
  - provider failover
  - degraded provider quality on fallback models

## Most Important Remaining Bug

The system is still too willing to land on `openrouter/qwen3.6-plus:free` for direct chat turns where Wiii's identity matters.

That fallback can produce:
- one good lore-rich answer in one transport
- and a generic or weak answer in the sibling transport

This means the remaining issue is now mainly `provider/runtime quality parity`, not missing HTML, missing lifecycle, or missing routing scaffolding.


## Postfix 2026-04-05 20:57

Source reports:
- `wiii-golden-eval-2026-04-05-205333.json`
- `wiii-golden-eval-2026-04-05-205655.json`
- composite: `wiii-live-chat-composite-2026-04-05-postfix.json`
- viewer: `thinking-review-latest.html`
- screenshot: `thinking-review-latest-postfix-2026-04-05.png`

Current truth:
- `direct_origin_bong/origin`: sync now completes on `zhipu/glm-5` with rich visible thinking.
- `direct_origin_bong/origin`: stream now stays on `zhipu` via same-provider fallback (`glm-4.5-air`) instead of falling through to `openrouter/qwen3.6-plus:free`.
- `direct_origin_bong/bong_followup`: sync + stream both complete on `zhipu/glm-4.5-air` with visible thinking and lore-consistent answers.
- `emotion_direct/sadness`: sync + stream both complete on `zhipu/glm-4.5-air`; stream still thinner than sync, but no longer collapses into the generic identity-erasing fallback.

Interpretation:
- The lane-aware fallback allowlist worked: selfhood/emotion no longer accept the generic OpenRouter free path as a normal cross-provider fallback.
- The remaining issue is now quality tuning (`stream` brevity vs `sync`) rather than catastrophic provider drift.


## Broad live matrix 2026-04-05 21:10

Additional sources:
- `wiii-golden-eval-2026-04-05-210148.json` (`tutor_rule15_visual`)
- `wiii-golden-eval-2026-04-05-210150.json` (`memory_name_roundtrip`)
- composite: `wiii-live-chat-composite-2026-04-05-broad.json`
- viewer: `thinking-review-latest.html`
- screenshot: `thinking-review-latest-broad-2026-04-05.png`

Broader current truth:
- `direct_origin_bong` is now substantially healthier on live runtime.
- `emotion_direct/sadness` no longer collapses into the generic identity-erasing fallback, but stream is still thinner than sync.
- `memory_name_roundtrip` still feels overly generic and system-like; it is functional, but not yet convincingly alive.
- `tutor_rule15_visual` is still unhealthy in live mode: missing visible thinking, weak provider/model metadata, and stream/sync drift remain visible.

Recommendation:
- Treat `direct selfhood/emotion` as the repaired lane for this round.
- Treat `memory` and especially `tutor` as the next live-quality targets.
