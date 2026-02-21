"""RAG subgraph state — private retrieval internals invisible to parent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class RAGSubgraphState(TypedDict, total=False):
    """State for the RAG (Corrective Retrieval-Augmented Generation) subgraph.

    Shared fields pass in/out of the parent AgentState.
    Private fields (prefixed with retrieval/grading) stay within the subgraph.
    """

    # ── Input (shared with parent AgentState) ─────────────────────────
    query: str
    context: Dict[str, Any]
    user_id: str
    session_id: str
    domain_id: str
    organization_id: Optional[str]
    _event_bus_id: Optional[str]
    _trace_id: Optional[str]
    thinking_effort: Optional[str]

    # ── Subgraph-private: retrieval pipeline ──────────────────────────
    retrieval_docs: List[Dict[str, Any]]
    retrieval_scores: List[float]
    grading_results: List[Dict[str, Any]]
    correction_round: int
    max_correction_rounds: int
    retrieval_confidence: float

    # ── Output (flows back to parent AgentState) ──────────────────────
    final_response: str
    agent_outputs: Dict[str, Any]
    current_agent: str
    sources: List[Dict[str, Any]]
    reasoning_trace: Optional[Any]
    thinking: Optional[str]
    crag_confidence: float
