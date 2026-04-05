"""Research-backed embedding strategy recommendations for Wiii."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class EmbeddingStrategyCandidate:
    key: str
    title: str
    provider: str
    model: str
    dimensions: int
    recommendation_tier: str
    current_runtime_state: str
    summary: str
    rationale: str
    tradeoffs: str
    adoption_path: str
    measured_query_ms: float | None = None
    measured_hybrid_ms: float | None = None
    sources: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_latest_embedding_benchmark(reports_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    """Load the latest benchmark payload if present."""
    candidates = sorted(reports_dir.glob("embedding-retrieval-benchmark-*.json"))
    if not candidates:
        return None, None
    latest = candidates[-1]
    try:
        return latest, json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return latest, None


def benchmark_snapshot(benchmark_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not benchmark_payload:
        return []
    runs = benchmark_payload.get("runs", [])
    if not isinstance(runs, list):
        return []
    for item in runs:
        if isinstance(item, dict) and isinstance(item.get("snapshot"), list):
            return item["snapshot"]
    return []


def benchmark_canonical_dimensions(benchmark_payload: dict[str, Any] | None) -> int | None:
    if not benchmark_payload:
        return None
    runs = benchmark_payload.get("runs", [])
    if not isinstance(runs, list):
        return None
    for item in runs:
        if not isinstance(item, dict):
            continue
        policy = item.get("policy")
        if isinstance(policy, dict):
            value = policy.get("embedding_dimensions")
            if isinstance(value, int) and value > 0:
                return value
    return None


def _run_map(benchmark_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not benchmark_payload:
        return {}
    return {
        item["policy"]["name"]: item
        for item in benchmark_payload.get("runs", [])
        if isinstance(item, dict) and isinstance(item.get("policy"), dict)
    }


def _provider_state(snapshot: Iterable[dict[str, Any]], provider: str) -> dict[str, Any]:
    for item in snapshot:
        if item.get("provider") == provider:
            return item
    return {}


def _runtime_state(snapshot_item: dict[str, Any]) -> str:
    if not snapshot_item:
        return "unknown"
    if snapshot_item.get("is_active") and snapshot_item.get("available"):
        return "active"
    if snapshot_item.get("available"):
        return "available"
    reason_code = snapshot_item.get("reason_code")
    if reason_code:
        return f"blocked:{reason_code}"
    return "blocked"


def _pick_measurement(
    run_map: dict[str, dict[str, Any]],
    *,
    preferred_policies: list[str],
    provider: str,
) -> tuple[float | None, float | None]:
    for policy_name in preferred_policies:
        item = run_map.get(policy_name)
        if not item:
            continue
        raw = item.get("raw_embeddings", {})
        hybrid = item.get("hybrid_search", {})
        if raw.get("provider") == provider and raw.get("query_ok"):
            return raw.get("query_ms"), hybrid.get("elapsed_ms")
    return None, None


def _provider_promoted(run_map: dict[str, dict[str, Any]], primary_provider: str, fallback_provider: str) -> bool:
    for item in run_map.values():
        policy = item.get("policy", {})
        observations = item.get("observations", [])
        chain = policy.get("embedding_failover_chain", [])
        if not isinstance(chain, list) or not chain:
            continue
        if chain[0] != primary_provider:
            continue
        if f"provider_promoted_to_{fallback_provider}" in observations:
            return True
    return False


def recommend_embedding_strategies(
    *,
    canonical_dimensions: int,
    snapshot: list[dict[str, Any]],
    benchmark_payload: dict[str, Any] | None,
) -> list[EmbeddingStrategyCandidate]:
    """Build ranked embedding recommendations for current Wiii runtime."""
    run_map = _run_map(benchmark_payload)
    google_state = _provider_state(snapshot, "google")
    openai_state = _provider_state(snapshot, "openai")
    openrouter_state = _provider_state(snapshot, "openrouter")
    ollama_state = _provider_state(snapshot, "ollama")

    openai_query_ms, openai_hybrid_ms = _pick_measurement(
        run_map,
        preferred_policies=["google_openai_auto", "ollama_local_first"],
        provider="openai",
    )
    google_query_ms, google_hybrid_ms = _pick_measurement(
        run_map,
        preferred_policies=["google_first"],
        provider="google",
    )
    ollama_query_ms, ollama_hybrid_ms = _pick_measurement(
        run_map,
        preferred_policies=["ollama_local_first"],
        provider="ollama",
    )
    openai_large_query_ms, openai_large_hybrid_ms = _pick_measurement(
        run_map,
        preferred_policies=["openai_large_768"],
        provider="openai",
    )

    recommendations: list[EmbeddingStrategyCandidate] = []

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="openai_text_embedding_3_large_768",
            title="OpenAI text-embedding-3-large (768d request)",
            provider="openai",
            model="text-embedding-3-large",
            dimensions=canonical_dimensions,
            recommendation_tier="best_quality_now",
            current_runtime_state="active" if openai_large_query_ms is not None else "not_benchmarked_locally",
            summary="Current best quality-first choice on this machine and benchmark set.",
            rationale=(
                "OpenAI positions text-embedding-3-large as its most capable embedding model for English and "
                "non-English retrieval. In Wiii's latest direct benchmark, it also delivered the fastest query "
                "embedding measurement among the benchmarked paths while keeping hybrid retrieval healthy."
            ),
            tradeoffs=(
                "Higher cost than text-embedding-3-small and still cloud-dependent. The current evidence is strong, "
                "but it should still be rechecked over multiple benchmark rounds before becoming the only default."
            ),
            adoption_path=(
                "Use for quality-first retrieval lanes, premium orgs, or controlled bake-offs. If later rounds stay "
                "consistent, promote it as the quality tier while keeping a cheaper balanced tier beside it."
            ),
            measured_query_ms=openai_large_query_ms,
            measured_hybrid_ms=openai_large_hybrid_ms,
            sources=(
                "https://developers.openai.com/api/docs/models/text-embedding-3-large",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="openai_text_embedding_3_small_768",
            title="OpenAI text-embedding-3-small (768d request)",
            provider="openai",
            model="text-embedding-3-small",
            dimensions=canonical_dimensions,
            recommendation_tier="balanced_default_now",
            current_runtime_state=_runtime_state(openai_state),
            summary="Best balanced default when cost and safety matter more than absolute quality.",
            rationale=(
                "OpenAI positions text-embedding-3-small as the default small embedding model, "
                "with materially lower cost than text-embedding-3-large. On Wiii's latest live "
                "benchmark, it completed query embedding, semantic "
                "context retrieval, and hybrid search successfully against the current 768d index."
            ),
            tradeoffs=(
                "Cloud-only dependency and, in the latest benchmark, no longer the fastest option. It remains "
                "valuable because its cost profile is much easier to carry as a broad default."
            ),
            adoption_path=(
                "Keep as the default balanced tier and as the cloud safety net behind local-first or quality-first "
                "choices."
            ),
            measured_query_ms=openai_query_ms,
            measured_hybrid_ms=openai_hybrid_ms,
            sources=(
                "https://developers.openai.com/api/docs/models/text-embedding-3-small",
                "https://platform.openai.com/docs/api-reference/embeddings/create",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="google_embeddinggemma_768",
            title="EmbeddingGemma via Ollama (768d)",
            provider="ollama",
            model="embeddinggemma",
            dimensions=768,
            recommendation_tier="preferred_local_first",
            current_runtime_state=_runtime_state(ollama_state),
            summary="Best local-first destination for Wiii once Ollama is healthy.",
            rationale=(
                "Google's EmbeddingGemma model card and overview describe it as a lightweight multilingual "
                "embedding model with native 768d output, MRL-based truncation, and an on-device footprint "
                "explicitly aimed at laptops and mobile-class hardware. That makes it the cleanest fit for "
                "Wiii's canonical 768d vector space and privacy-first ambitions."
            ),
            tradeoffs=(
                "Requires Ollama to be installed, reachable, and to have the model pulled locally. Query and "
                "document prompting should also be tuned for best retrieval quality."
            ),
            adoption_path=(
                "Make this the first provider in the auto embedding chain on machines where Ollama is healthy, "
                "and keep OpenAI behind it as the safety net."
            ),
            measured_query_ms=ollama_query_ms,
            measured_hybrid_ms=ollama_hybrid_ms,
            sources=(
                "https://ai.google.dev/gemma/docs/embeddinggemma",
                "https://ai.google.dev/gemma/docs/embeddinggemma/model_card",
                "https://ollama.com/library/embeddinggemma",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="google_gemini_embedding_001_768",
            title="Google gemini-embedding-001 (768d)",
            provider="google",
            model="models/gemini-embedding-001",
            dimensions=canonical_dimensions,
            recommendation_tier="cloud_primary_when_healthy",
            current_runtime_state=(
                "degraded:promoted_to_openai"
                if _provider_promoted(run_map, "google", "openai")
                else _runtime_state(google_state)
            ),
            summary="Still a strong cloud primary when quota and billing are stable.",
            rationale=(
                "Google's embeddings guide explicitly supports flexible dimensions from 128 to 3072 and "
                "recommends 768, 1536, and 3072. The model is stable, and the MTEB table in the guide shows "
                "768d staying close to higher-dimensional variants. This makes gemini-embedding-001 a strong "
                "cloud fit for Wiii's current 768d index."
            ),
            tradeoffs=(
                "Recent Wiii evidence shows quota pressure and provider promotion to OpenAI. It should not be "
                "the sole dependency for semantic memory or retrieval."
            ),
            adoption_path=(
                "Keep enabled as a selectable cloud primary, but only trust it as the first choice when project "
                "quota, billing, and observed reliability are healthy."
            ),
            measured_query_ms=google_query_ms,
            measured_hybrid_ms=google_hybrid_ms,
            sources=(
                "https://ai.google.dev/gemini-api/docs/embeddings",
                "https://ai.google.dev/gemini-api/docs/rate-limits?pubDate=20250330",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="qwen3_embedding_family",
            title="Qwen3-Embedding family (0.6B/4B/8B)",
            provider="ollama",
            model="qwen3-embedding",
            dimensions=1024,
            recommendation_tier="future_candidate",
            current_runtime_state="not_in_catalog_contract",
            summary="Most interesting open candidate for the next generation of local retrieval.",
            rationale=(
                "Qwen's official blog and Ollama library page describe a strong multilingual/open embedding family, "
                "including MRL support, instruction-aware behavior, and top multilingual leaderboard claims for the "
                "8B variant. This makes it the best open-model family to benchmark after Wiii finishes the current "
                "768d stabilization phase."
            ),
            tradeoffs=(
                "Different default dimensions, larger hardware requirements, and a likely need for a reranker story. "
                "It should not be dropped into the existing 768d production index without a clear contract."
            ),
            adoption_path=(
                "Treat as the next controlled benchmark wave: add catalog metadata, choose one canonical dimension, "
                "and test it together with a reranker rather than swapping it in blindly."
            ),
            sources=(
                "https://qwenlm.github.io/blog/qwen3-embedding/",
                "https://ollama.com/library/qwen3-embedding",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="openrouter_embeddings_router",
            title="OpenRouter embeddings router",
            provider="openrouter",
            model="text-embedding-3-small",
            dimensions=canonical_dimensions,
            recommendation_tier="routing_layer_only",
            current_runtime_state=_runtime_state(openrouter_state),
            summary="Useful as a routing control plane, not as Wiii's primary embedding contract.",
            rationale=(
                "OpenRouter's embeddings guide exposes a unified embeddings API and explicit provider routing "
                "controls such as provider order, fallback, and data collection policy. That is valuable as a "
                "routing layer once credentials and policies are configured explicitly."
            ),
            tradeoffs=(
                "Adds another control plane and should not be allowed to masquerade as a model choice. Credential "
                "surfaces must stay explicit to avoid false selectability."
            ),
            adoption_path=(
                "Enable only when Wiii truly wants router-level control across multiple cloud backends, and keep the "
                "actual embedding model contract explicit underneath it."
            ),
            sources=(
                "https://openrouter.ai/docs/api/reference/embeddings",
                "https://openrouter.ai/docs/guides/routing/provider-selection",
            ),
        )
    )

    recommendations.append(
        EmbeddingStrategyCandidate(
            key="google_gemini_embedding_2_preview",
            title="Google gemini-embedding-2-preview",
            provider="google",
            model="gemini-embedding-2-preview",
            dimensions=3072,
            recommendation_tier="hold_for_separate_index",
            current_runtime_state="preview_not_adopted",
            summary="Promising, but not a drop-in replacement for Wiii's current production index.",
            rationale=(
                "Google released gemini-embedding-2-preview on March 10, 2026 as its first multimodal embedding "
                "model with a shared embedding space across text, image, audio, video, and PDF. That is strategically "
                "important, but it belongs to a different adoption track than Wiii's current text-first 768d path."
            ),
            tradeoffs=(
                "Preview lifecycle, likely different operational limits, and a new vector space. Moving to it would "
                "require a deliberate re-embedding and likely a separate multimodal index."
            ),
            adoption_path=(
                "Do not switch the current production index in place. Evaluate it later as a dedicated multimodal "
                "index or sidecar retrieval space with separate parity tests."
            ),
            sources=(
                "https://ai.google.dev/gemini-api/docs/changelog",
                "https://ai.google.dev/gemini-api/docs/embeddings",
            ),
        )
    )

    tier_order = {
        "best_quality_now": 0,
        "balanced_default_now": 1,
        "preferred_local_first": 2,
        "cloud_primary_when_healthy": 3,
        "future_candidate": 4,
        "routing_layer_only": 5,
        "hold_for_separate_index": 6,
    }
    recommendations.sort(key=lambda item: (tier_order.get(item.recommendation_tier, 99), item.title))
    return recommendations


def build_embedding_strategy_guardrails() -> list[str]:
    return [
        "Keep Wiii's current production vector space canonical at 768d until a deliberate migration says otherwise.",
        "Never mix embeddings from different model families inside the same retrieval index without re-embedding.",
        "If you adopt gemini-embedding-2-preview or another new family, treat it as a new index space, not an in-place swap.",
        "Prefer local-first only when the local backend is actually healthy; otherwise fail over honestly to cloud.",
        "Treat OpenRouter as a routing surface, not as a hidden replacement for explicit provider credentials.",
        "Benchmark query latency, semantic-context quality, and hybrid retrieval together; do not choose on leaderboard claims alone.",
        "For local open models, benchmark the embedding model and reranker story together when retrieval quality matters.",
    ]


def render_embedding_strategy_markdown(
    *,
    canonical_dimensions: int,
    recommendations: list[EmbeddingStrategyCandidate],
    benchmark_payload: dict[str, Any] | None,
    benchmark_source: str | None,
) -> str:
    run_map = _run_map(benchmark_payload)
    lines: list[str] = []
    lines.append("# Embedding Model Selection Matrix for Wiii")
    lines.append("")
    lines.append("Date: 2026-04-02")
    lines.append("")
    lines.append("## Current recommendation")
    lines.append("")
    lines.append(f"- Canonical production vector space: `{canonical_dimensions}d`")
    if benchmark_source:
        lines.append(f"- Latest benchmark evidence: `{benchmark_source}`")
    tier_map = {item.recommendation_tier: item for item in recommendations}
    quality_now = tier_map.get("best_quality_now")
    balanced_now = tier_map.get("balanced_default_now")
    local_first = tier_map.get("preferred_local_first")
    if quality_now:
        lines.append(
            f"- Best quality now: `{quality_now.provider} / {quality_now.model} / {quality_now.dimensions}d`"
        )
    if balanced_now:
        lines.append(
            f"- Best balanced default: `{balanced_now.provider} / {balanced_now.model} / {balanced_now.dimensions}d`"
        )
    if local_first:
        lines.append(
            f"- Best local-first path: `{local_first.provider} / {local_first.model} / {local_first.dimensions}d`"
        )
    lines.append("- Do not in-place replace the current index with `gemini-embedding-2-preview`")
    lines.append("")
    lines.append("## Ranked strategies")
    lines.append("")
    for item in recommendations:
        lines.append(f"### {item.title}")
        lines.append("")
        lines.append(f"- Tier: `{item.recommendation_tier}`")
        lines.append(f"- Runtime state: `{item.current_runtime_state}`")
        lines.append(f"- Provider/model: `{item.provider} / {item.model}`")
        lines.append(f"- Target dimensions: `{item.dimensions}`")
        lines.append(f"- Summary: {item.summary}")
        lines.append(f"- Why it fits Wiii: {item.rationale}")
        lines.append(f"- Tradeoffs: {item.tradeoffs}")
        lines.append(f"- Adoption path: {item.adoption_path}")
        if item.measured_query_ms is not None:
            lines.append(f"- Measured query embed latency: `{item.measured_query_ms:.2f} ms`")
        if item.measured_hybrid_ms is not None:
            lines.append(f"- Measured hybrid search latency: `{item.measured_hybrid_ms:.2f} ms`")
        if item.sources:
            lines.append("- Sources:")
            for source in item.sources:
                lines.append(f"  - {source}")
        lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    for entry in build_embedding_strategy_guardrails():
        lines.append(f"- {entry}")

    if run_map:
        lines.append("")
        lines.append("## Benchmark evidence")
        lines.append("")
        for run_name, run in sorted(run_map.items()):
            raw = run.get("raw_embeddings", {})
            semantic = run.get("semantic_context", {})
            hybrid = run.get("hybrid_search", {})
            lines.append(f"### {run_name}")
            lines.append("")
            lines.append(
                f"- Active backend: `{raw.get('provider')} / {raw.get('model')} / {raw.get('dimensions')}d`"
            )
            if raw.get("query_ms") is not None:
                lines.append(
                    f"- Query embedding: `{float(raw['query_ms']):.2f} ms`, ok=`{bool(raw.get('query_ok'))}`"
                )
            if raw.get("document_ms") is not None:
                lines.append(
                    f"- Document embedding: `{float(raw['document_ms']):.2f} ms`, ok=`{bool(raw.get('document_ok'))}`"
                )
            if semantic:
                lines.append(
                    f"- Semantic context: `{float(semantic.get('elapsed_ms', 0.0)):.2f} ms`, "
                    f"memories=`{semantic.get('relevant_memory_count')}`, facts=`{semantic.get('user_fact_count')}`"
                )
            if hybrid:
                lines.append(
                    f"- Hybrid search: `{float(hybrid.get('elapsed_ms', 0.0)):.2f} ms`, "
                    f"results=`{hybrid.get('result_count')}`, method=`{hybrid.get('search_method')}`"
                )
            observations = run.get("observations", [])
            if observations:
                lines.append(f"- Observations: {', '.join(str(item) for item in observations)}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"
