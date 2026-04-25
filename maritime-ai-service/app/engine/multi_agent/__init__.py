"""
Multi-Agent System Module - Phase 8

Supervisor pattern with specialized agents, routed through WiiiRunner.

Compatibility exports remain available for deprecated graph entrypoints while
the active runtime uses the custom runner and streaming shell.

Sprint 140: Lazy imports via __getattr__ to break circular dependency
(state ↔ graph via __init__.py eager imports).
"""

__all__ = [
    "AgentState",
    "SupervisorAgent",
    "get_supervisor_agent",
    "build_multi_agent_graph",
    "get_multi_agent_graph",
    "process_with_multi_agent",
    "process_with_multi_agent_streaming",
]


def __getattr__(name: str):
    if name == "AgentState":
        from app.engine.multi_agent.state import AgentState
        return AgentState
    if name in ("SupervisorAgent", "get_supervisor_agent"):
        from app.engine.multi_agent import supervisor
        return getattr(supervisor, name)
    if name in ("build_multi_agent_graph", "get_multi_agent_graph", "process_with_multi_agent"):
        from app.engine.multi_agent import graph
        return getattr(graph, name)
    if name == "process_with_multi_agent_streaming":
        from app.engine.multi_agent.graph_streaming import process_with_multi_agent_streaming
        return process_with_multi_agent_streaming
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
