# Embedding Model Selection Matrix for Wiii

Date: 2026-04-02

## Current recommendation

- Canonical production vector space: `768d`
- Latest benchmark evidence: `embedding-retrieval-benchmark-2026-04-02-205712.json`
- Best production-safe choice now: `openai / text-embedding-3-small / 768d`
- Long-term local-first destination: `ollama / embeddinggemma / 768d` once Ollama is healthy
- Do not in-place replace the current index with `gemini-embedding-2-preview`

## Ranked strategies

### OpenAI text-embedding-3-small (768d request)

- Tier: `primary_now`
- Runtime state: `active`
- Provider/model: `openai / text-embedding-3-small`
- Target dimensions: `768`
- Summary: Best production-safe choice for Wiii right now.
- Why it fits Wiii: OpenAI positions text-embedding-3-small as the default small embedding model, with materially lower cost than text-embedding-3-large. On Wiii's latest live benchmark, the runtime promoted to OpenAI and completed query embedding, semantic context retrieval, and hybrid search successfully against the current 768d index.
- Tradeoffs: Cloud-only dependency, slower than a healthy local model, and still subject to external API cost and availability.
- Adoption path: Keep as the current production-safe fallback and as the baseline for new benchmark rounds until a local-first backend is truly alive on the target machine.
- Measured query embed latency: `7895.92 ms`
- Measured hybrid search latency: `1067.77 ms`
- Sources:
  - https://developers.openai.com/api/docs/models/text-embedding-3-small
  - https://platform.openai.com/docs/api-reference/embeddings/create

### EmbeddingGemma via Ollama (768d)

- Tier: `preferred_local_first`
- Runtime state: `blocked:host_down`
- Provider/model: `ollama / embeddinggemma`
- Target dimensions: `768`
- Summary: Best local-first destination for Wiii once Ollama is healthy.
- Why it fits Wiii: Google's EmbeddingGemma model card and overview describe it as a lightweight multilingual embedding model with native 768d output, MRL-based truncation, and an on-device footprint explicitly aimed at laptops and mobile-class hardware. That makes it the cleanest fit for Wiii's canonical 768d vector space and privacy-first ambitions.
- Tradeoffs: Requires Ollama to be installed, reachable, and to have the model pulled locally. Query and document prompting should also be tuned for best retrieval quality.
- Adoption path: Make this the first provider in the auto embedding chain on machines where Ollama is healthy, and keep OpenAI behind it as the safety net.
- Sources:
  - https://ai.google.dev/gemma/docs/embeddinggemma
  - https://ai.google.dev/gemma/docs/embeddinggemma/model_card
  - https://ollama.com/library/embeddinggemma

### Google gemini-embedding-001 (768d)

- Tier: `cloud_primary_when_healthy`
- Runtime state: `degraded:promoted_to_openai`
- Provider/model: `google / models/gemini-embedding-001`
- Target dimensions: `768`
- Summary: Still a strong cloud primary when quota and billing are stable.
- Why it fits Wiii: Google's embeddings guide explicitly supports flexible dimensions from 128 to 3072 and recommends 768, 1536, and 3072. The model is stable, and the MTEB table in the guide shows 768d staying close to higher-dimensional variants. This makes gemini-embedding-001 a strong cloud fit for Wiii's current 768d index.
- Tradeoffs: Recent Wiii evidence shows quota pressure and provider promotion to OpenAI. It should not be the sole dependency for semantic memory or retrieval.
- Adoption path: Keep enabled as a selectable cloud primary, but only trust it as the first choice when project quota, billing, and observed reliability are healthy.
- Sources:
  - https://ai.google.dev/gemini-api/docs/embeddings
  - https://ai.google.dev/gemini-api/docs/rate-limits?pubDate=20250330

### OpenAI text-embedding-3-large (benchmark next)

- Tier: `benchmark_next`
- Runtime state: `not_benchmarked_locally`
- Provider/model: `openai / text-embedding-3-large`
- Target dimensions: `768`
- Summary: Strongest pure-cloud quality candidate if recall quality becomes the bottleneck.
- Why it fits Wiii: OpenAI positions text-embedding-3-large as its most capable embedding model for English and non-English tasks. If Wiii later needs a quality-first cloud tier for high-value retrieval, this is the most direct benchmark-next candidate.
- Tradeoffs: Much higher token cost than text-embedding-3-small and officially slower. We have not yet benchmarked it on Wiii's retrieval stack.
- Adoption path: Do not switch globally yet. Run a focused retrieval-quality bake-off first on the same 768d index assumptions and compare recall gains against the cost increase.
- Sources:
  - https://developers.openai.com/api/docs/models/text-embedding-3-large

### Qwen3-Embedding family (0.6B/4B/8B)

- Tier: `future_candidate`
- Runtime state: `not_in_catalog_contract`
- Provider/model: `ollama / qwen3-embedding`
- Target dimensions: `1024`
- Summary: Most interesting open candidate for the next generation of local retrieval.
- Why it fits Wiii: Qwen's official blog and Ollama library page describe a strong multilingual/open embedding family, including MRL support, instruction-aware behavior, and top multilingual leaderboard claims for the 8B variant. This makes it the best open-model family to benchmark after Wiii finishes the current 768d stabilization phase.
- Tradeoffs: Different default dimensions, larger hardware requirements, and a likely need for a reranker story. It should not be dropped into the existing 768d production index without a clear contract.
- Adoption path: Treat as the next controlled benchmark wave: add catalog metadata, choose one canonical dimension, and test it together with a reranker rather than swapping it in blindly.
- Sources:
  - https://qwenlm.github.io/blog/qwen3-embedding/
  - https://ollama.com/library/qwen3-embedding

### OpenRouter embeddings router

- Tier: `routing_layer_only`
- Runtime state: `blocked:missing_api_key`
- Provider/model: `openrouter / text-embedding-3-small`
- Target dimensions: `768`
- Summary: Useful as a routing control plane, not as Wiii's primary embedding contract.
- Why it fits Wiii: OpenRouter's embeddings guide exposes a unified embeddings API and explicit provider routing controls such as provider order, fallback, and data collection policy. That is valuable as a routing layer once credentials and policies are configured explicitly.
- Tradeoffs: Adds another control plane and should not be allowed to masquerade as a model choice. Credential surfaces must stay explicit to avoid false selectability.
- Adoption path: Enable only when Wiii truly wants router-level control across multiple cloud backends, and keep the actual embedding model contract explicit underneath it.
- Sources:
  - https://openrouter.ai/docs/api/reference/embeddings
  - https://openrouter.ai/docs/guides/routing/provider-selection

### Google gemini-embedding-2-preview

- Tier: `hold_for_separate_index`
- Runtime state: `preview_not_adopted`
- Provider/model: `google / gemini-embedding-2-preview`
- Target dimensions: `3072`
- Summary: Promising, but not a drop-in replacement for Wiii's current production index.
- Why it fits Wiii: Google released gemini-embedding-2-preview on March 10, 2026 as its first multimodal embedding model with a shared embedding space across text, image, audio, video, and PDF. That is strategically important, but it belongs to a different adoption track than Wiii's current text-first 768d path.
- Tradeoffs: Preview lifecycle, likely different operational limits, and a new vector space. Moving to it would require a deliberate re-embedding and likely a separate multimodal index.
- Adoption path: Do not switch the current production index in place. Evaluate it later as a dedicated multimodal index or sidecar retrieval space with separate parity tests.
- Sources:
  - https://ai.google.dev/gemini-api/docs/changelog
  - https://ai.google.dev/gemini-api/docs/embeddings

## Guardrails

- Keep Wiii's current production vector space canonical at 768d until a deliberate migration says otherwise.
- Never mix embeddings from different model families inside the same retrieval index without re-embedding.
- If you adopt gemini-embedding-2-preview or another new family, treat it as a new index space, not an in-place swap.
- Prefer local-first only when the local backend is actually healthy; otherwise fail over honestly to cloud.
- Treat OpenRouter as a routing surface, not as a hidden replacement for explicit provider credentials.
- Benchmark query latency, semantic-context quality, and hybrid retrieval together; do not choose on leaderboard claims alone.
- For local open models, benchmark the embedding model and reranker story together when retrieval quality matters.

## Benchmark evidence

### google_openai_auto

- Active backend: `openai / text-embedding-3-small / 768d`
- Query embedding: `7895.92 ms`, ok=`True`
- Document embedding: `199.30 ms`, ok=`True`
- Semantic context: `259.14 ms`, memories=`1`, facts=`1`
- Hybrid search: `1067.77 ms`, results=`2`, method=`hybrid`
- Observations: provider_promoted_to_openai
