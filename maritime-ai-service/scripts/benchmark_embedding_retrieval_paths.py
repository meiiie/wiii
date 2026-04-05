"""Benchmark embedding and retrieval paths across runtime embedding policies.

This script compares two embedding runtime policies against the same benchmark
workflow:

1. Raw query/document embedding latency
2. Semantic memory context retrieval after seeding a temporary benchmark user
3. Hybrid knowledge search latency against the current knowledge store

It writes both JSON and Markdown reports into the workspace .Codex/reports
folder so results can be compared over time.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text

CURRENT_FILE = Path(__file__).resolve()
SERVICE_DIR = CURRENT_FILE.parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.core.config import settings
from app.engine.embedding_runtime import (
    get_embedding_backend,
    reset_embedding_backend,
)
from app.engine.semantic_memory.context import ContextRetriever
from app.models.semantic_memory import MemoryType, SemanticMemoryCreate
from app.repositories.dense_search_repository import get_dense_search_repository
from app.repositories.semantic_memory_repository import SemanticMemoryRepository
from app.services.embedding_selectability_service import (
    get_embedding_selectability_snapshot,
    invalidate_embedding_selectability_cache,
)
from app.services.llm_runtime_policy_service import apply_persisted_llm_runtime_policy
from app.services.hybrid_search_service import HybridSearchService


WORKSPACE_DIR = SERVICE_DIR.parent
REPORTS_DIR = WORKSPACE_DIR / ".Codex" / "reports"


@dataclass
class PolicySpec:
    name: str
    embedding_provider: str
    embedding_failover_chain: list[str]
    embedding_model: str
    embedding_dimensions: int


@dataclass
class RawEmbeddingMetrics:
    provider: str | None
    model: str | None
    dimensions: int | None
    query_ms: float | None
    query_vector_len: int
    query_ok: bool
    document_ms: float | None
    document_vector_len: int
    document_ok: bool


@dataclass
class SemanticContextMetrics:
    elapsed_ms: float | None
    similarity_threshold: float
    total_tokens: int
    relevant_memory_count: int
    user_fact_count: int
    top_memory_preview: list[str]
    top_fact_preview: list[str]


@dataclass
class HybridSearchMetrics:
    elapsed_ms: float | None
    total_knowledge_embeddings: int
    result_count: int
    search_method: str | None
    top_result_preview: list[str]


POLICIES: dict[str, PolicySpec] = {
    "google_first": PolicySpec(
        name="google_first",
        embedding_provider="google",
        embedding_failover_chain=["google", "openai", "ollama", "openrouter"],
        embedding_model="models/gemini-embedding-001",
        embedding_dimensions=768,
    ),
    "ollama_local_first": PolicySpec(
        name="ollama_local_first",
        embedding_provider="auto",
        embedding_failover_chain=["ollama", "google", "openai"],
        embedding_model="embeddinggemma",
        embedding_dimensions=768,
    ),
    "google_openai_auto": PolicySpec(
        name="google_openai_auto",
        embedding_provider="auto",
        embedding_failover_chain=["google", "openai", "ollama"],
        embedding_model="models/gemini-embedding-001",
        embedding_dimensions=768,
    ),
    "openai_large_768": PolicySpec(
        name="openai_large_768",
        embedding_provider="openai",
        embedding_failover_chain=["openai", "google", "ollama"],
        embedding_model="text-embedding-3-large",
        embedding_dimensions=768,
    ),
}


def _round_ms(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def _snapshot_runtime_settings() -> dict[str, Any]:
    return {
        "embedding_provider": copy.deepcopy(settings.embedding_provider),
        "embedding_failover_chain": copy.deepcopy(settings.embedding_failover_chain),
        "embedding_model": copy.deepcopy(settings.embedding_model),
        "embedding_dimensions": copy.deepcopy(settings.embedding_dimensions),
        "ollama_base_url": copy.deepcopy(getattr(settings, "ollama_base_url", None)),
        "openai_base_url": copy.deepcopy(getattr(settings, "openai_base_url", None)),
    }


def _restore_runtime_settings(snapshot: dict[str, Any]) -> None:
    settings.embedding_provider = snapshot["embedding_provider"]
    settings.embedding_failover_chain = snapshot["embedding_failover_chain"]
    settings.embedding_model = snapshot["embedding_model"]
    settings.embedding_dimensions = snapshot["embedding_dimensions"]
    settings.ollama_base_url = snapshot["ollama_base_url"]
    settings.openai_base_url = snapshot["openai_base_url"]
    settings.refresh_nested_views()
    reset_embedding_backend()
    invalidate_embedding_selectability_cache()


def _apply_policy(spec: PolicySpec) -> None:
    settings.embedding_provider = spec.embedding_provider
    settings.embedding_failover_chain = list(spec.embedding_failover_chain)
    settings.embedding_model = spec.embedding_model
    settings.embedding_dimensions = spec.embedding_dimensions
    settings.refresh_nested_views()
    reset_embedding_backend()
    invalidate_embedding_selectability_cache()


def _restore_persisted_runtime_policy() -> bool:
    record = apply_persisted_llm_runtime_policy()
    reset_embedding_backend()
    invalidate_embedding_selectability_cache()
    return bool(record and record.payload)


async def _cleanup_benchmark_user(user_id: str) -> None:
    repo = SemanticMemoryRepository()
    repo._ensure_initialized()
    with repo._session_factory() as session:
        session.execute(
            text("DELETE FROM semantic_memories WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        session.commit()


async def _seed_benchmark_user(user_id: str, session_id: str) -> None:
    repo = SemanticMemoryRepository()
    backend = get_embedding_backend()
    documents = [
        "name: Nam",
        (
            "Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có "
            "nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường."
        ),
    ]
    vectors = await backend.aembed_documents(documents)

    repo.save_memory(
        SemanticMemoryCreate(
            user_id=user_id,
            content=documents[0],
            embedding=vectors[0],
            memory_type=MemoryType.USER_FACT,
            importance=0.95,
            metadata={
                "fact_type": "name",
                "confidence": 0.99,
                "source_message": "Mình tên Nam.",
            },
            session_id=None,
        )
    )
    repo.save_memory(
        SemanticMemoryCreate(
            user_id=user_id,
            content=documents[1],
            embedding=vectors[1],
            memory_type=MemoryType.MESSAGE,
            importance=0.82,
            metadata={
                "domain_id": "maritime",
                "topic": "rule15",
            },
            session_id=session_id,
        )
    )


async def _measure_raw_embeddings() -> RawEmbeddingMetrics:
    backend = get_embedding_backend()

    started = time.perf_counter()
    query_vector = await backend.aembed_query("Mình tên gì và Quy tắc 15 nói gì?")
    query_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    document_vectors = await backend.aembed_documents(
        [
            (
                "Quy tắc 15 của COLREGs mô tả tình huống cắt ngang, trong đó tàu "
                "thấy tàu kia ở mạn phải phải tránh đường."
            )
        ]
    )
    document_ms = (time.perf_counter() - started) * 1000.0

    return RawEmbeddingMetrics(
        provider=backend.provider,
        model=backend.model_name,
        dimensions=backend.dimensions,
        query_ms=_round_ms(query_ms),
        query_vector_len=len(query_vector),
        query_ok=bool(query_vector),
        document_ms=_round_ms(document_ms),
        document_vector_len=len(document_vectors[0]) if document_vectors else 0,
        document_ok=bool(document_vectors and document_vectors[0]),
    )


async def _measure_semantic_context(policy_name: str) -> SemanticContextMetrics:
    user_id = f"bench_user_{policy_name}_{uuid4().hex[:8]}"
    session_id = f"bench_session_{uuid4().hex[:8]}"
    repo = SemanticMemoryRepository()
    backend = get_embedding_backend()
    retriever = ContextRetriever(backend, repo)

    await _cleanup_benchmark_user(user_id)
    try:
        await _seed_benchmark_user(user_id, session_id)
        similarity_threshold = 0.3
        started = time.perf_counter()
        context = await retriever.retrieve_context(
            user_id=user_id,
            query=(
                "Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho "
                "có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường."
            ),
            search_limit=3,
            similarity_threshold=similarity_threshold,
            include_user_facts=True,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return SemanticContextMetrics(
            elapsed_ms=_round_ms(elapsed_ms),
            similarity_threshold=similarity_threshold,
            total_tokens=context.total_tokens,
            relevant_memory_count=len(context.relevant_memories),
            user_fact_count=len(context.user_facts),
            top_memory_preview=[
                item.content[:160] for item in context.relevant_memories[:2]
            ],
            top_fact_preview=[item.content[:120] for item in context.user_facts[:2]],
        )
    finally:
        await _cleanup_benchmark_user(user_id)


async def _measure_hybrid_search() -> HybridSearchMetrics:
    dense_repo = get_dense_search_repository()
    total_embeddings = await dense_repo.count_embeddings()

    service = HybridSearchService()
    started = time.perf_counter()
    results = await service.search(
        query="Quy tắc 15 tình huống cắt ngang là gì?",
        limit=3,
        domain_id="maritime",
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    search_method = results[0].search_method if results else None
    preview = []
    for item in results[:3]:
        content = getattr(item, "content", "") or getattr(item, "text", "")
        preview.append(content[:160])

    return HybridSearchMetrics(
        elapsed_ms=_round_ms(elapsed_ms),
        total_knowledge_embeddings=total_embeddings,
        result_count=len(results),
        search_method=search_method,
        top_result_preview=preview,
    )


def _serialize_snapshot() -> list[dict[str, Any]]:
    snapshot = get_embedding_selectability_snapshot(force_refresh=True)
    return [item.to_dict() for item in snapshot]


async def _run_policy(spec: PolicySpec) -> dict[str, Any]:
    settings_snapshot = _snapshot_runtime_settings()
    try:
        _apply_policy(spec)
        raw = await _measure_raw_embeddings()
        semantic = await _measure_semantic_context(spec.name)
        hybrid = await _measure_hybrid_search()
        observations: list[str] = []
        if not raw.query_ok:
            observations.append("query_embedding_failed_or_empty")
        if not raw.document_ok:
            observations.append("document_embedding_failed_or_empty")
        if spec.embedding_provider == "auto" and raw.provider:
            primary_provider = spec.embedding_failover_chain[0] if spec.embedding_failover_chain else None
            if primary_provider and raw.provider != primary_provider:
                observations.append(f"provider_promoted_to_{raw.provider}")
        if hybrid.total_knowledge_embeddings == 0:
            observations.append("knowledge_embedding_store_empty")
        if semantic.relevant_memory_count == 0 and raw.query_ok:
            observations.append("semantic_memory_message_not_retrieved")
        return {
            "policy": asdict(spec),
            "snapshot": _serialize_snapshot(),
            "raw_embeddings": asdict(raw),
            "semantic_context": asdict(semantic),
            "hybrid_search": asdict(hybrid),
            "observations": observations,
        }
    finally:
        _restore_runtime_settings(settings_snapshot)


def _render_markdown(results: dict[str, Any]) -> str:
    lines = [
        "# Embedding Retrieval Benchmark",
        "",
        f"- Generated at: `{results['generated_at']}`",
        f"- Workspace: `{WORKSPACE_DIR}`",
        f"- Database URL host: `{settings.postgres_host}:{settings.postgres_port}`",
        "",
        "## Summary",
        "",
    ]

    for item in results["runs"]:
        raw = item["raw_embeddings"]
        semantic = item["semantic_context"]
        hybrid = item["hybrid_search"]
        lines.extend(
            [
                f"### {item['policy']['name']}",
                "",
                f"- Active embedding backend: `{raw['provider']}/{raw['model']}` `{raw['dimensions']}d`",
                f"- Raw query embed: `{raw['query_ms']} ms` ({raw['query_vector_len']} dims, ok={raw['query_ok']})",
                f"- Raw document embed: `{raw['document_ms']} ms` ({raw['document_vector_len']} dims, ok={raw['document_ok']})",
                f"- Semantic context: `{semantic['elapsed_ms']} ms`, memories={semantic['relevant_memory_count']}, facts={semantic['user_fact_count']}, tokens={semantic['total_tokens']}, threshold={semantic['similarity_threshold']}",
                f"- Hybrid search: `{hybrid['elapsed_ms']} ms`, results={hybrid['result_count']}, knowledge_embeddings={hybrid['total_knowledge_embeddings']}, method={hybrid['search_method']}",
                "",
                "Snapshot:",
            ]
        )
        for snap in item["snapshot"]:
            state = "usable" if snap["available"] else f"blocked:{snap['reason_code']}"
            lines.append(
                f"- `{snap['provider']}` -> {state}, model=`{snap['selected_model']}`, active={snap['is_active']}"
            )
        if semantic["top_fact_preview"] or semantic["top_memory_preview"]:
            lines.extend(
                [
                    "",
                    "Context preview:",
                ]
            )
            for fact in semantic["top_fact_preview"]:
                lines.append(f"- Fact: `{fact}`")
            for memory in semantic["top_memory_preview"]:
                lines.append(f"- Memory: `{memory}`")
        if hybrid["top_result_preview"]:
            lines.extend(
                [
                    "",
                    "Hybrid preview:",
                ]
            )
            for result in hybrid["top_result_preview"]:
                lines.append(f"- Result: `{result}`")
        if item["observations"]:
            lines.extend(
                [
                    "",
                    "Observations:",
                ]
            )
            for observation in item["observations"]:
                lines.append(f"- `{observation}`")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policies",
        nargs="+",
        default=["google_first", "ollama_local_first"],
        choices=sorted(POLICIES.keys()),
        help="Embedding policies to benchmark.",
    )
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    persisted_runtime_restored = _restore_persisted_runtime_policy()

    payload = {
        "generated_at": datetime.now().isoformat(),
        "persisted_runtime_restored": persisted_runtime_restored,
        "runs": [],
    }

    for policy_name in args.policies:
        payload["runs"].append(await _run_policy(POLICIES[policy_name]))

    json_path = REPORTS_DIR / f"embedding-retrieval-benchmark-{stamp}.json"
    md_path = REPORTS_DIR / f"EMBEDDING-RETRIEVAL-BENCHMARK-{stamp}.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
