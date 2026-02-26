"""Product search subgraph builder — LangGraph Send() map-reduce.

Flow::

    START
      → plan_search
      → [platform_worker × N]  (parallel via Send)
      → aggregate_results
      → curate_products       (Sprint 202: LLM curation)
      → synthesize_response
      → END

Feature-gated: ``enable_subagent_architecture=True`` to activate.
Falls back to original ``ProductSearchAgentNode`` when disabled.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
from app.engine.multi_agent.subagents.search.workers import (
    aggregate_results,
    curate_products,
    plan_search,
    platform_worker,
    synthesize_response,
)

logger = logging.getLogger(__name__)


def route_to_platforms(state: Dict[str, Any]) -> List[Send]:
    """Fan-out: create parallel ``Send()`` for each platform.

    Each Send targets ``platform_worker`` with a ``PlatformWorkerState``
    dict.  Results accumulate back via ``operator.add`` reducers on
    ``SearchSubgraphState``.
    """
    platforms = state.get("platforms_to_search", [])
    query = state.get("query", "")
    org_id = state.get("organization_id")
    bus_id = state.get("_event_bus_id")

    sends = [
        Send(
            "platform_worker",
            {
                "query": query,
                "platform_id": pid,
                "max_results": 20,
                "page": 1,
                "organization_id": org_id,
                "_event_bus_id": bus_id,
            },
        )
        for pid in platforms
    ]

    if not sends:
        # Fallback — always search at least Google Shopping
        sends.append(
            Send(
                "platform_worker",
                {
                    "query": query,
                    "platform_id": "google_shopping",
                    "max_results": 20,
                    "page": 1,
                    "organization_id": org_id,
                    "_event_bus_id": bus_id,
                },
            )
        )

    logger.info("[SEARCH_SUBGRAPH] Fan-out: %d parallel platform workers", len(sends))
    return sends


def build_search_subgraph() -> StateGraph:
    """Build and compile the product search subgraph.

    Returns a compiled LangGraph that can be added as a node in the parent
    multi-agent graph::

        if settings.enable_subagent_architecture:
            search_subgraph = build_search_subgraph()
            workflow.add_node("product_search_agent", search_subgraph)
    """
    builder = StateGraph(SearchSubgraphState)

    builder.add_node("plan_search", plan_search)
    builder.add_node("platform_worker", platform_worker)
    builder.add_node("aggregate_results", aggregate_results)
    builder.add_node("curate_products", curate_products)
    builder.add_node("synthesize_response", synthesize_response)

    builder.add_edge(START, "plan_search")
    builder.add_conditional_edges("plan_search", route_to_platforms, ["platform_worker"])
    builder.add_edge("platform_worker", "aggregate_results")
    builder.add_edge("aggregate_results", "curate_products")
    builder.add_edge("curate_products", "synthesize_response")
    builder.add_edge("synthesize_response", END)

    return builder.compile()
