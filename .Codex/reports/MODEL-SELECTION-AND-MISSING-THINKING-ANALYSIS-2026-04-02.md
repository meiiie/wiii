# Model Selection And Missing Thinking Analysis - 2026-04-02

## Question
- Do leading tools let users switch models when the current model is limited or unavailable?
- Is Wiii's missing visible thinking caused by the model itself, or by runtime/lane handling?

## External references
- Anthropic Claude Code model configuration:
  - [Claude Code model config](https://code.claude.com/docs/en/model-config)
- Cursor official signals:
  - [Cursor changelog](https://cursor.com/changelog)
  - search snippet for Cursor auto-select behavior from official docs/changelog
- OpenAI official model selection:
  - [OpenAI models](https://developers.openai.com/api/docs/models)
- Google official model/rate-limit docs:
  - [Gemini rate limits](https://ai.google.dev/gemini-api/docs/quota)
  - [Gemini troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting)
  - [Gemini models](https://ai.google.dev/models/gemini)

## What the large tools are doing

### Anthropic / Claude Code
- Claude Code explicitly supports switching models during a live session with `/model <alias|name>`.
- Anthropic also exposes a model picker, allowlists, default aliases, and effort controls.
- Their docs explicitly say Claude Code may automatically fall back to Sonnet if the user hits a usage threshold with Opus.
- This is the clearest example of the hybrid pattern:
  - auto fallback exists
  - user can still override and pick a model directly

### Cursor
- Cursor publicly describes a multi-model harness and model configuration surface.
- Official changelog and docs/search snippets indicate an `Auto` selection mode that chooses a model based on performance, speed, and availability.
- Cursor also exposes configured models in product settings, so users can move out of Auto and select a specific model manually.
- Practical pattern:
  - default = auto routing
  - advanced users can pin/switch models

### OpenAI
- Official API docs emphasize choosing a model explicitly based on task needs.
- The docs recommend using the strongest model for hard reasoning and smaller variants for latency/cost-sensitive work.
- OpenAI's public API docs are more developer-facing than end-user UX-facing here, but the pattern is still clear:
  - model choice should be surfaced as a real control
  - smaller models are valid fallbacks for speed/cost

### Google
- Gemini docs make two points that matter for Wiii:
  - rate limits are model-specific
  - preview/experimental variants may have stricter limits and more volatility
- Google troubleshooting docs also note that higher latency/token usage can come from thinking being enabled by default on some models.
- So on Google specifically, both "model unavailable" and "thinking behavior changed" can be tied to the chosen model family/tier.

## Local Claude Code source learning
- In local source:
  - [query.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/query.ts)
  - [QueryEngine.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/QueryEngine.ts)
  - [commands/model/model.tsx](E:/Sach/Sua/test/claude_lo/claude-code/src/commands/model/model.tsx)
- Claude Code clearly carries:
  - `fallbackModel`
  - `FallbackTriggeredError`
  - explicit `/model` picker command
- This means their runtime supports both:
  - automatic retry on fallback model
  - direct user model switching

## Current truth for Wiii

### Missing thinking is not purely "the model is bad"
Evidence from:
- [glm-targeted-live-smoke-2026-04-02-045832.json](E:/Sach/Sua/AI_v1/.Codex/reports/glm-targeted-live-smoke-2026-04-02-045832.json)
- [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

With the same `provider=zhipu` and `model=glm-5`:
- `emotion_direct / sadness`
  - sync has thinking
  - stream has thinking
- `direct_origin_bong / origin`
  - stream has thinking
  - sync misses thinking
- `direct_origin_bong / bong_followup`
  - sync passes
  - stream misses thinking
- `tutor_rule15_visual / rule15_explain`
  - stream has thinking
  - sync misses thinking

So the current failure pattern is:
- partly model/turn variability
- but mainly lane/runtime/transport capture differences

If the model were the sole cause, the same model would fail consistently across all lanes. That is not what the live data shows.

### What is probably causing missing thinking in practice
1. Provider/model variability
- Some turns naturally return weaker or no visible thought.
- Some providers expose thought better on stream than on final merged objects, or vice versa.

2. Lane-specific runtime gaps
- `direct`, `tutor`, `memory`, and tool-heavy paths still differ in how they populate lifecycle segments.
- Some lanes backfill from final snapshot correctly; others still leave holes.

3. Sync vs stream capture asymmetry
- In a few cases the final object contains less usable thought than the streamed deltas.
- In other cases the opposite happens.
- This is why a Thinking Lifecycle authority was needed in the first place.

4. Fallback / degraded mode
- When the primary provider is unavailable, Wiii may still route and answer, but thinking quality can collapse if the degraded path is rule-based or partially structured.

## Recommended UX for Wiii

### Best default
- Keep auto-routing and auto-failover as the default.

### Add user-facing model switch when needed
- If the selected model is:
  - rate-limited
  - auth-invalid
  - unavailable
  - repeatedly timing out
- then Wiii should surface a compact prompt like:
  - "Model hiện tại đang bị giới hạn. Chuyển sang GLM-5 cho lượt này hay cho cả phiên?"

### Offer two scopes
- `For this turn`
- `For this session`

### When to ask the user vs auto-failover silently
- Silent auto-failover:
  - transient timeout
  - server unavailable
  - temporary provider outage
  - fallback provider is same-quality-enough
- Ask the user:
  - model is pinned/preferred by the user
  - switching would noticeably change quality/cost/latency
  - the task is high-value and the user may prefer to wait for a better model

## Recommendation
- Do not blame missing thinking on the model alone.
- Fix remaining lane/runtime holes first.
- Then add a small UX layer for manual model switching when the active model is limited or unavailable.
- Keep Wiii's multi-provider pool.
- If latency remains poor, add a same-provider `fallbackModel` tier as a secondary optimization, not as a replacement for the pool.
