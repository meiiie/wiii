"""Graph singleton and request-scoped lifecycle helpers.

NOTE: LangGraph graph lifecycle is deprecated (De-LangGraphing Phase 3).
These functions remain for backward compatibility but are no longer used
by the main execution paths which now use WiiiRunner.
"""

from __future__ import annotations

from contextlib import asynccontextmanager


def get_multi_agent_graph_impl(*, cached_graph, build_graph, set_cached_graph):
    """Get or create the sync Multi-Agent Graph singleton."""
    if cached_graph is None:
        cached_graph = build_graph()
        set_cached_graph(cached_graph)
    return cached_graph


@asynccontextmanager
async def open_multi_agent_graph_impl(*, build_graph):
    """Build a request-scoped graph (no checkpointer — LangGraph removed)."""
    yield build_graph(checkpointer=None)


async def get_multi_agent_graph_async_impl(*, build_graph):
    """Backward-compatible async accessor that builds a fresh graph."""
    return build_graph()
