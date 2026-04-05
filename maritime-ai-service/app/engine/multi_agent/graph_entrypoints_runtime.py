"""Entry-point and singleton helpers for the graph shell."""

from __future__ import annotations

from contextlib import asynccontextmanager

from app.engine.multi_agent.graph_builder_runtime import build_multi_agent_graph_impl
from app.engine.multi_agent.graph_lifecycle import (
    get_multi_agent_graph_async_impl,
    get_multi_agent_graph_impl,
    open_multi_agent_graph_impl,
)

_sync_graph = None


def build_multi_agent_graph_entry_impl(
    *,
    checkpointer=None,
    settings_obj,
    guardian_node,
    supervisor_node,
    rag_node,
    tutor_node,
    memory_node,
    direct_response_node,
    code_studio_node,
    synthesizer_node,
    colleague_agent_node,
    product_search_node,
    parallel_dispatch_node,
    route_decision,
    guardian_route,
):
    """Build the compiled multi-agent graph from shell callbacks."""
    return build_multi_agent_graph_impl(
        checkpointer=checkpointer,
        settings_obj=settings_obj,
        guardian_node=guardian_node,
        supervisor_node=supervisor_node,
        rag_node=rag_node,
        tutor_node=tutor_node,
        memory_node=memory_node,
        direct_response_node=direct_response_node,
        code_studio_node=code_studio_node,
        synthesizer_node=synthesizer_node,
        colleague_agent_node=colleague_agent_node,
        product_search_node=product_search_node,
        parallel_dispatch_node=parallel_dispatch_node,
        route_decision=route_decision,
        guardian_route=guardian_route,
    )


def get_multi_agent_graph_entry_impl(*, build_graph):
    """Get or create the sync Multi-Agent Graph singleton."""
    global _sync_graph
    return get_multi_agent_graph_impl(
        cached_graph=_sync_graph,
        build_graph=build_graph,
        set_cached_graph=lambda value: globals().__setitem__("_sync_graph", value),
    )


@asynccontextmanager
async def open_multi_agent_graph_entry_impl(*, build_graph):
    """Build a request-scoped graph with its own checkpointer connection."""
    async with open_multi_agent_graph_impl(build_graph=build_graph) as graph:
        yield graph


async def get_multi_agent_graph_async_entry_impl(*, build_graph):
    """Backward-compatible async accessor that builds a fresh graph."""
    return await get_multi_agent_graph_async_impl(build_graph=build_graph)
