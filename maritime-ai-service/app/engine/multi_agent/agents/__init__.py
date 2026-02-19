"""
Specialized Agents Module - Phase 8.3

Individual agent implementations for Multi-Agent System.

Sprint 140: Lazy imports to break circular dependency chain
(graph → agents/__init__ → tutor_node → services/__init__ → chat_service → graph).
"""

__all__ = [
    "RAGAgentNode",
    "get_rag_agent_node",
    "TutorAgentNode",
    "get_tutor_agent_node",
    "MemoryAgentNode",
    "get_memory_agent_node",
    "GraderAgentNode",
    "get_grader_agent_node",
    "KGBuilderAgentNode",
    "get_kg_builder_agent",
    "ProductSearchAgentNode",
    "get_product_search_agent_node",
]

_ATTR_MAP = {
    "RAGAgentNode": ("app.engine.multi_agent.agents.rag_node", "RAGAgentNode"),
    "get_rag_agent_node": ("app.engine.multi_agent.agents.rag_node", "get_rag_agent_node"),
    "TutorAgentNode": ("app.engine.multi_agent.agents.tutor_node", "TutorAgentNode"),
    "get_tutor_agent_node": ("app.engine.multi_agent.agents.tutor_node", "get_tutor_agent_node"),
    "MemoryAgentNode": ("app.engine.multi_agent.agents.memory_agent", "MemoryAgentNode"),
    "get_memory_agent_node": ("app.engine.multi_agent.agents.memory_agent", "get_memory_agent_node"),
    "GraderAgentNode": ("app.engine.multi_agent.agents.grader_agent", "GraderAgentNode"),
    "get_grader_agent_node": ("app.engine.multi_agent.agents.grader_agent", "get_grader_agent_node"),
    "KGBuilderAgentNode": ("app.engine.multi_agent.agents.kg_builder_agent", "KGBuilderAgentNode"),
    "get_kg_builder_agent": ("app.engine.multi_agent.agents.kg_builder_agent", "get_kg_builder_agent"),
    "ProductSearchAgentNode": ("app.engine.multi_agent.agents.product_search_node", "ProductSearchAgentNode"),
    "get_product_search_agent_node": ("app.engine.multi_agent.agents.product_search_node", "get_product_search_agent_node"),
}


def __getattr__(name: str):
    if name in _ATTR_MAP:
        module_path, attr_name = _ATTR_MAP[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
