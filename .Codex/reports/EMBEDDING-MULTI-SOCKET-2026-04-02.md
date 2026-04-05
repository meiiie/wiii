# Embedding Multi-Socket V1

Date: 2026-04-02

## Problem

Semantic memory was still effectively single-provider:

- `EmbeddingGenerator` used `GeminiOptimizedEmbeddings` directly.
- `SemanticMemoryEngine` defaulted to `GeminiOptimizedEmbeddings`.
- `input_processor_context_runtime` instantiated `GeminiOptimizedEmbeddings()` directly for semantic fact retrieval.
- The current pgvector path is tuned around a canonical `768d` production embedding shape.

This meant Google key/quota problems could degrade semantic recall even when other providers were healthy.

## Research Notes

Observed / confirmed:

- Google Gemini embeddings support `output_dimensionality` and explicitly recommend `768`, `1536`, or `3072`.
- Ollama embeddings are model-dependent in vector length and the docs explicitly state dimensions vary by model.
- OpenRouter exposes a unified embeddings API across multiple providers.
- OpenAI `text-embedding-3-small` was verified live with the provided project key to return `768d` vectors when requested, which makes it a strong fit for the existing `vector(768)` storage path.

## Architecture Decision

V1 keeps one canonical vector shape for semantic memory:

- canonical dimension: `settings.embedding_dimensions` (currently `768`)
- provider selection is separated from vector-store shape
- only providers/models that can satisfy the canonical dimension cleanly should write/search against the current pgvector path

This avoids mixing heterogeneous vector dimensions inside the same index family.

## Implemented

New authority:

- `app/engine/embedding_runtime.py`

Capabilities:

- provider-agnostic semantic embedding backend
- providers supported by the runtime layer:
  - `google`
  - `openai`
  - `openrouter`
  - `ollama`
  - `zhipu`
- `embedding_provider`
  - explicit provider pin
  - or `auto` with `embedding_failover_chain`
- dimension compatibility enforcement
- OpenAI-compatible adapter path with dimension override when supported

Config additions:

- `embedding_provider`
- `embedding_failover_chain`

Catalog additions:

- `text-embedding-3-small`
- `text-embedding-3-large`
- `embeddinggemma`
- provider metadata for embedding models
- dimension-override metadata for embedding models

Semantic memory wiring updated:

- `app/engine/semantic_memory/embeddings.py`
- `app/engine/semantic_memory/core.py`
- `app/engine/semantic_memory/context.py`
- `app/engine/semantic_memory/extraction.py`
- `app/engine/semantic_memory/insight_provider.py`
- `app/services/input_processor_context_runtime.py`

## Live Validation

OpenAI live smoke with `embedding_provider=openai`, `embedding_model=text-embedding-3-small`, `embedding_dimensions=768`:

- provider: `openai`
- model: `text-embedding-3-small`
- vector length: `768`
- norm: `1.0`

Auto fallback smoke with `embedding_provider=auto`, `embedding_failover_chain=[google, openai]`, `google_api_key=None`:

- resolved provider: `openai`
- resolved model: `text-embedding-3-small`
- vector length: `768`

## Tests

Focused tests passing:

- `tests/unit/test_embedding_runtime.py`
- `tests/unit/test_sprint30_semantic_memory_core.py`
- `tests/unit/test_sprint137_vector_facts.py`
- `tests/unit/test_sprint47_gemini_embedding.py`
- `tests/unit/test_embedding_validation.py`
- `tests/unit/test_model_catalog.py`
- `tests/unit/test_model_catalog_service.py`
- `tests/unit/test_input_processor.py`

Totals run during this step:

- `81 passed`
- `62 passed`

## Current Limits

This step makes semantic memory multi-socket, but not every embedding callsite in the whole repo has been migrated yet.

Still legacy / follow-up candidates:

- hybrid search service
- multimodal ingestion
- visual memory
- knowledge visualization
- any other path still instantiating `GeminiOptimizedEmbeddings()` directly

## Recommended Next Step

Promote the same embedding authority into:

1. hybrid search
2. ingestion / knowledge embeddings
3. visual memory

That will complete the transition from single-provider embeddings to a consistent platform-wide embedding runtime.
