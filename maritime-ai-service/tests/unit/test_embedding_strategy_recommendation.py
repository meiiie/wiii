from app.services.embedding_strategy_recommendation import (
    benchmark_canonical_dimensions,
    benchmark_snapshot,
    recommend_embedding_strategies,
    render_embedding_strategy_markdown,
)


def _sample_benchmark_payload() -> dict:
    return {
        "generated_at": "2026-04-02T20:57:12.072499",
        "runs": [
            {
                "policy": {
                    "name": "openai_large_768",
                    "embedding_provider": "openai",
                    "embedding_failover_chain": ["openai", "google", "ollama"],
                    "embedding_model": "text-embedding-3-large",
                    "embedding_dimensions": 768,
                },
                "snapshot": [
                    {
                        "provider": "google",
                        "available": True,
                        "is_active": False,
                        "reason_code": None,
                    },
                    {
                        "provider": "openai",
                        "available": True,
                        "is_active": True,
                        "reason_code": None,
                    },
                    {
                        "provider": "openrouter",
                        "available": False,
                        "is_active": False,
                        "reason_code": "missing_api_key",
                    },
                    {
                        "provider": "ollama",
                        "available": True,
                        "is_active": False,
                        "reason_code": None,
                    },
                ],
                "raw_embeddings": {
                    "provider": "openai",
                    "model": "text-embedding-3-large",
                    "dimensions": 768,
                    "query_ms": 492.72,
                    "query_ok": True,
                    "document_ms": 297.12,
                    "document_ok": True,
                },
                "semantic_context": {
                    "elapsed_ms": 269.61,
                    "relevant_memory_count": 1,
                    "user_fact_count": 1,
                },
                "hybrid_search": {
                    "elapsed_ms": 180.08,
                    "result_count": 2,
                    "search_method": "hybrid",
                },
                "observations": [],
            },
            {
                "policy": {
                    "name": "google_openai_auto",
                    "embedding_provider": "auto",
                    "embedding_failover_chain": ["google", "openai", "ollama"],
                    "embedding_model": "models/gemini-embedding-001",
                    "embedding_dimensions": 768,
                },
                "snapshot": [
                    {
                        "provider": "google",
                        "available": True,
                        "is_active": False,
                        "reason_code": None,
                    },
                    {
                        "provider": "openai",
                        "available": True,
                        "is_active": True,
                        "reason_code": None,
                    },
                    {
                        "provider": "openrouter",
                        "available": False,
                        "is_active": False,
                        "reason_code": "missing_api_key",
                    },
                    {
                        "provider": "ollama",
                        "available": False,
                        "is_active": False,
                        "reason_code": "host_down",
                    },
                ],
                "raw_embeddings": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "dimensions": 768,
                    "query_ms": 7895.92,
                    "query_ok": True,
                    "document_ms": 199.3,
                    "document_ok": True,
                },
                "semantic_context": {
                    "elapsed_ms": 259.14,
                    "relevant_memory_count": 1,
                    "user_fact_count": 1,
                },
                "hybrid_search": {
                    "elapsed_ms": 1067.77,
                    "result_count": 2,
                    "search_method": "hybrid",
                },
                "observations": ["provider_promoted_to_openai"],
            }
        ],
    }


def test_benchmark_helpers_extract_current_state():
    payload = _sample_benchmark_payload()
    assert benchmark_canonical_dimensions(payload) == 768

    snapshot = benchmark_snapshot(payload)
    assert len(snapshot) == 4
    assert snapshot[1]["provider"] == "openai"


def test_embedding_recommendations_rank_current_stack_safely():
    payload = _sample_benchmark_payload()
    recommendations = recommend_embedding_strategies(
        canonical_dimensions=768,
        snapshot=benchmark_snapshot(payload),
        benchmark_payload=payload,
    )

    assert recommendations[0].key == "openai_text_embedding_3_large_768"
    assert recommendations[0].recommendation_tier == "best_quality_now"

    balanced = next(item for item in recommendations if item.key == "openai_text_embedding_3_small_768")
    assert balanced.recommendation_tier == "balanced_default_now"

    embeddinggemma = next(item for item in recommendations if item.key == "google_embeddinggemma_768")
    assert embeddinggemma.recommendation_tier == "preferred_local_first"
    assert embeddinggemma.current_runtime_state == "available"

    google = next(item for item in recommendations if item.key == "google_gemini_embedding_001_768")
    assert google.current_runtime_state == "degraded:promoted_to_openai"

    preview = next(item for item in recommendations if item.key == "google_gemini_embedding_2_preview")
    assert preview.recommendation_tier == "hold_for_separate_index"


def test_embedding_recommendation_markdown_includes_guardrails_and_evidence():
    payload = _sample_benchmark_payload()
    recommendations = recommend_embedding_strategies(
        canonical_dimensions=768,
        snapshot=benchmark_snapshot(payload),
        benchmark_payload=payload,
    )

    markdown = render_embedding_strategy_markdown(
        canonical_dimensions=768,
        recommendations=recommendations,
        benchmark_payload=payload,
        benchmark_source="embedding-retrieval-benchmark-sample.json",
    )

    assert "Best quality now" in markdown
    assert "Best balanced default" in markdown
    assert "Best local-first path" in markdown
    assert "OpenAI text-embedding-3-large (768d request)" in markdown
    assert "EmbeddingGemma via Ollama (768d)" in markdown
    assert "Never mix embeddings from different model families" in markdown
    assert "provider_promoted_to_openai" in markdown
