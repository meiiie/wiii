"""Search subgraph state definitions.

Two state schemas:
- PlatformWorkerState: Send() target — single platform search worker
- SearchSubgraphState: Full subgraph state with operator.add accumulators
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class PlatformWorkerState(TypedDict):
    """State for a single platform search worker (Send() target).

    Each parallel worker receives a copy of this with a specific
    ``platform_id``.  Results flow back into SearchSubgraphState
    via ``operator.add`` reducers on the accumulator fields.
    """

    query: str
    platform_id: str
    max_results: int
    page: int
    organization_id: Optional[str]
    _event_bus_id: Optional[str]


class SearchSubgraphState(TypedDict, total=False):
    """State for the full product search subgraph.

    Fields shared with parent AgentState are used for input/output.
    Fields unique to this state are private to the subgraph.

    Accumulator fields use ``Annotated[List, operator.add]`` so that
    parallel Send() workers can safely append results without conflict.
    """

    # ── Input (shared with parent AgentState) ─────────────────────────
    query: str
    context: Dict[str, Any]
    organization_id: Optional[str]
    _event_bus_id: Optional[str]
    _trace_id: Optional[str]
    thinking_effort: Optional[str]
    user_id: str
    session_id: str

    # ── Subgraph-private: planning ────────────────────────────────────
    platforms_to_search: List[str]
    query_variants: List[str]
    search_round: int
    _query_plan_text: Optional[str]  # Sprint 197: LLM Query Planner output

    # ── Subgraph-private: accumulation (operator.add reducers) ────────
    all_products: Annotated[List[Dict[str, Any]], operator.add]
    platform_errors: Annotated[List[str], operator.add]
    platforms_searched: Annotated[List[str], operator.add]
    tools_used: Annotated[List[Dict[str, Any]], operator.add]

    # ── Subgraph-private: aggregation (set by aggregate node) ─────────
    deduped_products: List[Dict[str, Any]]
    excel_path: Optional[str]

    # ── Subgraph-private: curation (Sprint 202) ────────────────────────
    curated_products: List[Dict[str, Any]]

    # ── Subgraph-private: full product preservation (Sprint 202b) ──────
    _all_search_products_json: str

    # ── Output (flows back to parent AgentState) ──────────────────────
    final_response: str
    agent_outputs: Dict[str, Any]
    current_agent: str
    thinking: Optional[str]
    _answer_streamed_via_bus: Optional[bool]
