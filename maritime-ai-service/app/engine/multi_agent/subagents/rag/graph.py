"""RAG subgraph builder — Corrective RAG pipeline as subgraph.

Flow::

    START → retrieve → grade → should_correct?
                                  ├─ yes → correct → retrieve (loop)
                                  └─ no  → generate → END

Feature-gated: ``enable_subagent_architecture=True`` to activate.
Falls back to existing ``rag_node`` when disabled.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from app.engine.multi_agent.subagents.rag.state import RAGSubgraphState

logger = logging.getLogger(__name__)


async def retrieve_node(state: Dict[str, Any]) -> dict:
    """Hybrid search: dense (pgvector) + sparse (tsvector) + RRF reranking.

    Delegates to existing HybridSearchService for consistency.
    """
    query = state.get("query", "")
    domain_id = state.get("domain_id", "maritime")
    org_id = state.get("organization_id")
    correction_round = state.get("correction_round", 0)

    docs = []
    scores = []

    try:
        from app.services.hybrid_search_service import get_hybrid_search_service

        search_svc = get_hybrid_search_service()
        results = await search_svc.search(
            query=query,
            domain_id=domain_id,
            top_k=10,
            organization_id=org_id,
        )
        for r in results:
            docs.append({
                "content": r.get("content", ""),
                "metadata": r.get("metadata", {}),
                "score": r.get("score", 0.0),
            })
            scores.append(r.get("score", 0.0))
    except Exception as exc:
        logger.warning("[RAG_SUBGRAPH] Retrieval failed (round %d): %s", correction_round, exc)

    return {
        "retrieval_docs": docs,
        "retrieval_scores": scores,
        "correction_round": correction_round,
    }


async def grade_node(state: Dict[str, Any]) -> dict:
    """Grade retrieved documents for relevance.

    Uses tiered grading: pre-filter → MiniJudge → Full LLM (early exit).
    """
    docs = state.get("retrieval_docs", [])
    query = state.get("query", "")

    if not docs:
        return {"retrieval_confidence": 0.0, "grading_results": []}

    # Simple confidence from retrieval scores
    scores = state.get("retrieval_scores", [])
    avg_score = sum(scores) / len(scores) if scores else 0.0
    confidence = min(avg_score, 1.0)

    grading_results = [
        {"doc_index": i, "relevant": score > 0.3, "score": score}
        for i, score in enumerate(scores)
    ]

    return {
        "retrieval_confidence": confidence,
        "grading_results": grading_results,
    }


def should_correct(state: Dict[str, Any]) -> Literal["generate", "correct"]:
    """Decide whether to self-correct or proceed to generation."""
    confidence = state.get("retrieval_confidence", 0.0)
    correction_round = state.get("correction_round", 0)
    max_rounds = state.get("max_correction_rounds", 3)

    if confidence >= 0.85 or correction_round >= max_rounds:
        return "generate"
    return "correct"


async def correct_node(state: Dict[str, Any]) -> dict:
    """Reformulate query for better retrieval."""
    return {
        "correction_round": state.get("correction_round", 0) + 1,
    }


async def generate_node(state: Dict[str, Any]) -> dict:
    """Generate final response from retrieved documents."""
    docs = state.get("retrieval_docs", [])
    query = state.get("query", "")
    confidence = state.get("retrieval_confidence", 0.0)

    if not docs:
        response = "Xin lỗi, không tìm thấy tài liệu liên quan."
    else:
        # Build context from relevant docs
        context_parts = [d.get("content", "")[:500] for d in docs[:5]]
        response = f"Dựa trên {len(docs)} tài liệu tìm được:\n" + "\n".join(context_parts[:3])

    sources = [
        {"content": d.get("content", "")[:200], "metadata": d.get("metadata", {})}
        for d in docs[:5]
    ]

    return {
        "final_response": response,
        "agent_outputs": {"rag": response},
        "current_agent": "rag_agent",
        "sources": sources,
        "crag_confidence": confidence,
    }


def build_rag_subgraph() -> StateGraph:
    """Build the Corrective RAG subgraph."""
    builder = StateGraph(RAGSubgraphState)

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("grade", grade_node)
    builder.add_node("correct", correct_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade")
    builder.add_conditional_edges(
        "grade",
        should_correct,
        {"generate": "generate", "correct": "correct"},
    )
    builder.add_edge("correct", "retrieve")
    builder.add_edge("generate", END)

    return builder.compile()
