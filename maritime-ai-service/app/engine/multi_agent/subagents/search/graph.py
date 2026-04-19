"""DEPRECATED: Product search subgraph builder — LangGraph Send() map-reduce.

LangGraph removed (De-LangGraphing Phase 3).
The worker functions (plan_search, platform_worker, aggregate_results, etc.)
are preserved in workers.py for reuse.

Original flow:
    START → plan_search → [platform_worker × N] (parallel) → aggregate_results → curate_products → synthesize_response → END
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

# LangGraph imports removed
# from langgraph.graph import END, START, StateGraph
# from langgraph.types import Send

from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
from app.engine.multi_agent.subagents.search.workers import (
    aggregate_results,
    curate_products,
    plan_search,
    platform_worker,
    synthesize_response,
)

logger = logging.getLogger(__name__)


def route_to_platforms(state: Dict[str, Any]) -> List[dict]:
    """Fan-out: create parallel task dicts for each platform.

    DEPRECATED: No longer returns Send() objects. Returns plain dicts
    for use with asyncio.gather() instead.
    """
    platforms = state.get("platforms_to_search", [])
    query = state.get("query", "")
    org_id = state.get("organization_id")
    bus_id = state.get("_event_bus_id")

    tasks = [
        {
            "query": query,
            "platform_id": pid,
            "max_results": 20,
            "page": 1,
            "organization_id": org_id,
            "_event_bus_id": bus_id,
        }
        for pid in platforms
    ]

    if not tasks:
        tasks.append({
            "query": query,
            "platform_id": "google_shopping",
            "max_results": 20,
            "page": 1,
            "organization_id": org_id,
            "_event_bus_id": bus_id,
        })

    logger.info("[SEARCH_SUBGRAPH] Fan-out: %d parallel platform workers", len(tasks))
    return tasks


def build_search_subgraph():
    """DEPRECATED — LangGraph removed (De-LangGraphing Phase 3).

    Worker functions are still available in workers.py for direct async calls.
    Use asyncio.gather() for parallel execution instead of LangGraph Send().
    """
    raise RuntimeError(
        "build_search_subgraph() is deprecated (De-LangGraphing Phase 3). "
        "Use worker functions directly with asyncio.gather()."
    )
