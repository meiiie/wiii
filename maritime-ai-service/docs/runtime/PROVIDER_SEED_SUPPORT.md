# Provider Seed Support Matrix

Phase 22 of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Closes the documentation gap around deterministic seeded replay
(Phase 11c) so future contributors know what's wired, what isn't,
and why.

## Why this exists

Phase 11c shipped a ContextVar (`replay_context.replay_seed_scope`)
that propagates `EvalRecord.replay_seed` from the replay script down
into `WiiiChatModel._build_api_kwargs`. When the seed is set, the
model adds `seed=<int>` to the OpenAI Chat Completions request.

This is the right pattern for OpenAI-compatible endpoints — but only
some providers actually honor a `seed` parameter. The brutal-honest
SOTA assessment flagged Anthropic and Gemini native paths as
"upstream-blocked"; this doc explains why and what would unlock them.

## Support matrix

| Provider              | Seed param exposed?           | Wired in Wiii?           | Notes                                                                                          |
|-----------------------|-------------------------------|--------------------------|------------------------------------------------------------------------------------------------|
| OpenAI (native)       | Yes — `seed: int`             | Yes (via WiiiChatModel)  | Documented as best-effort; not a strict guarantee even on OpenAI's side.                       |
| OpenAI-compat (Gemini) | Yes — passes through          | Yes (via WiiiChatModel)  | Gemini's OpenAI-compat endpoint accepts `seed`; native Gemini SDK does not.                    |
| OpenAI-compat (Ollama)| Yes — `seed: int`             | Yes (via WiiiChatModel)  | Ollama documents seed as deterministic given the same model + temperature.                     |
| OpenAI-compat (NVIDIA NIM) | Yes — passes through      | Yes (via WiiiChatModel)  | Surfaces upstream model's seed support; varies by hosted model.                                |
| OpenAI-compat (DeepSeek via NIM) | Yes               | Yes (via WiiiChatModel)  | Same path as NVIDIA NIM.                                                                       |
| OpenAI-compat (OpenRouter) | Pass-through              | Yes (via WiiiChatModel)  | Whether seed honored depends on which underlying model OpenRouter routes to.                   |
| Zhipu (BigModel)      | No — explicitly stripped      | No (filter removes it)   | `_strip_unsupported_params` drops `seed` for Zhipu hosts. See `wiii_chat_model.py`.            |
| **Anthropic native**  | **No** — no public seed param | **Blocked**              | The Messages API does not expose a sampling seed. Watch `https://docs.claude.com/en/api/messages`. |
| **Gemini native SDK** | **No** — no public seed param | **Blocked**              | The native `google-genai` SDK has no seed; only the OpenAI-compat surface does.                |

## What "blocked" means concretely

The two **blocked** rows above are NOT a Wiii bug. The provider's API
itself does not accept a deterministic seed parameter. Wiring would
require either:

1. The provider adding a public seed parameter (no public roadmap as of
   2026-05).
2. Wiii running a local model where it controls the sampler (out of
   scope; Phase 17 load test + Phase 20 chaos harness assume cloud
   providers).
3. Wiii setting `temperature=0` for replay turns, accepting that
   greedy decoding is "deterministic enough" for regression checks
   even without a seed. **This is the recommended workaround** when
   replay accuracy matters and the provider lacks a seed.

## Recommended workaround for blocked providers

When the replay script targets an Anthropic or Gemini-native turn:

1. The original turn was recorded with `replay_seed=<value>`.
2. The replay script reads `replay_seed`, but `WiiiChatModel` skips
   the `seed=` parameter for Anthropic/Gemini-native paths because
   the strip filter excludes those hosts.
3. **Add a fallback:** in `replay_eval.py`, when a record's provider
   is known to be Anthropic-native or Gemini-native, force
   `temperature=0` for the replay. Greedy decoding is reproducible
   enough that the diff metrics (`token_jaccard`, `sources_overlap`)
   still detect real regressions, even without seed.

This workaround is **not yet implemented** because production traffic
today goes through OpenAI-compat endpoints (Gemini's compat surface,
not native; OpenAI directly; Ollama for local). When the team enables
a native Anthropic or Gemini SDK code path and starts recording its
turns, this workaround moves from "TODO" to "must implement."

## How to verify a provider honors `seed`

The most reliable test: replay the same prompt 5 times with the same
seed + temperature 0.0, and compute `token_jaccard` across the 5
responses. A score of 1.0 means the provider is honoring the seed
deterministically. Anything less means the parameter is accepted but
not enforced — common for OpenAI-compat surfaces that proxy to a
non-deterministic upstream.

```bash
# Quick check (requires a recorded turn + an API key)
WIII_LOAD_PROFILE=edge_only \
WIII_REPLAY_SEED=42 \
python scripts/replay_eval.py --day 2026-05-01 --org test-org \
    --limit 1 --dry-run=false --report-out /tmp/seed-check.html
# Run the same command 4 more times; if all 5 reports have
# token_jaccard=1.0, the provider honors the seed.
```

## Review log

| Date       | Reviewer | Change                                              |
|------------|----------|-----------------------------------------------------|
| 2026-05-03 | runtime  | v1 — initial matrix, Phase 22 of #207               |
