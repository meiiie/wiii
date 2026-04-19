"""Product search subgraph — parallel platform search via Send() map-reduce."""

from app.engine.multi_agent.subagents.search.state import (
    PlatformWorkerState,
    SearchSubgraphState,
)
# build_search_subgraph removed (De-LangGraphing Phase 3) — pipeline runs via WiiiRunner

__all__ = [
    "PlatformWorkerState",
    "SearchSubgraphState",
]
