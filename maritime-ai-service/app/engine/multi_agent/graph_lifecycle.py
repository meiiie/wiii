"""Graph singleton and request-scoped lifecycle helpers."""

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
    """Build a request-scoped graph with its own checkpointer connection."""
    from app.engine.multi_agent.checkpointer import open_checkpointer

    async with open_checkpointer() as checkpointer:
        yield build_graph(checkpointer=checkpointer)


async def get_multi_agent_graph_async_impl(*, build_graph):
    """Backward-compatible async accessor that builds a fresh graph."""
    return build_graph()
