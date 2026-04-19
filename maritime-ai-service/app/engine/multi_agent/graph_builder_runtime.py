"""DEPRECATED: Graph builder for LangGraph StateGraph.

This file is preserved as architectural documentation showing the original
LangGraph graph structure. Replaced by WiiiRunner (De-LangGraphing Phase 3).

The graph topology is now encoded in WiiiRunner.run() / run_streaming():
    guardian → supervisor → {agent} → synthesizer
"""

from __future__ import annotations

import logging

# LangGraph imports removed — this module is no longer importable without langgraph.
# from langgraph.graph import END, StateGraph

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)


def build_multi_agent_graph_impl(
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
) -> object:
    """DEPRECATED — use WiiiRunner instead.

    Original: Build and compile the LangGraph workflow.
    Now: Raises RuntimeError if called (langgraph dependency removed).
    """
    raise RuntimeError(
        "build_multi_agent_graph_impl is deprecated (De-LangGraphing Phase 3). "
        "Use WiiiRunner from app.engine.multi_agent.runner instead."
    )


def _build_multi_agent_graph_impl_original(
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
) -> object:
    """Build and compile the LangGraph workflow for the multi-agent system."""
    logger.info("Building Multi-Agent Graph...")

    workflow = StateGraph(AgentState)

    workflow.add_node("guardian", guardian_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("rag_agent", rag_node)
    workflow.add_node("tutor_agent", tutor_node)
    workflow.add_node("memory_agent", memory_node)
    workflow.add_node("direct", direct_response_node)
    workflow.add_node("code_studio_agent", code_studio_node)
    workflow.add_node("synthesizer", synthesizer_node)

    if settings_obj.enable_cross_soul_query and settings_obj.enable_soul_bridge:
        workflow.add_node("colleague_agent", colleague_agent_node)
        logger.info("Colleague agent node added (cross-soul query enabled)")

    if settings_obj.enable_product_search:
        if settings_obj.enable_subagent_architecture:
            from app.engine.multi_agent.subagents.search.graph import build_search_subgraph

            search_subgraph = build_search_subgraph()
            workflow.add_node("product_search_agent", search_subgraph)
            logger.info("Product search: using SUBGRAPH (parallel Send)")
        else:
            workflow.add_node("product_search_agent", product_search_node)

    aggregator_route = None
    if settings_obj.enable_subagent_architecture:
        from app.engine.multi_agent.subagents.aggregator import (
            aggregator_node,
            aggregator_route as aggregator_route_impl,
        )

        aggregator_route = aggregator_route_impl
        workflow.add_node("parallel_dispatch", parallel_dispatch_node)
        workflow.add_node("aggregator", aggregator_node)
        logger.info("Phase 4: parallel_dispatch + aggregator nodes added")

    workflow.set_entry_point("guardian")
    workflow.add_conditional_edges(
        "guardian",
        guardian_route,
        {"supervisor": "supervisor", "synthesizer": "synthesizer"},
    )

    routing_map = {
        "rag_agent": "rag_agent",
        "tutor_agent": "tutor_agent",
        "memory_agent": "memory_agent",
        "direct": "direct",
        "code_studio_agent": "code_studio_agent",
    }
    if settings_obj.enable_product_search:
        routing_map["product_search_agent"] = "product_search_agent"
    if settings_obj.enable_cross_soul_query and settings_obj.enable_soul_bridge:
        routing_map["colleague_agent"] = "colleague_agent"
    if settings_obj.enable_subagent_architecture:
        routing_map["parallel_dispatch"] = "parallel_dispatch"
    workflow.add_conditional_edges("supervisor", route_decision, routing_map)

    workflow.add_edge("rag_agent", "synthesizer")
    workflow.add_edge("tutor_agent", "synthesizer")
    workflow.add_edge("memory_agent", "synthesizer")
    workflow.add_edge("direct", "synthesizer")
    workflow.add_edge("code_studio_agent", "synthesizer")

    if settings_obj.enable_product_search:
        workflow.add_edge("product_search_agent", "synthesizer")

    if settings_obj.enable_cross_soul_query and settings_obj.enable_soul_bridge:
        workflow.add_edge("colleague_agent", "synthesizer")

    if settings_obj.enable_subagent_architecture and aggregator_route is not None:
        workflow.add_edge("parallel_dispatch", "aggregator")
        workflow.add_conditional_edges(
            "aggregator",
            aggregator_route,
            {"synthesizer": "synthesizer", "supervisor": "supervisor"},
        )

    workflow.add_edge("synthesizer", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("Graph compiled WITH checkpointer (multi-turn persistence enabled)")
    else:
        logger.info("Graph compiled WITHOUT checkpointer")

    graph = workflow.compile(**compile_kwargs)
    logger.info("Multi-Agent Graph built successfully")
    return graph
