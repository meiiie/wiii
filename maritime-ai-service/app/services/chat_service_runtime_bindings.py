"""Lazy runtime bindings for chat service bootstrap."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def get_knowledge_repository() -> Any:
    return _load_attr(
        "app.engine.agentic_rag.rag_agent",
        "get_knowledge_repository",
    )()


def create_rag_agent(*, knowledge_graph: Any) -> Any:
    rag_agent_cls = _load_attr("app.engine.agentic_rag.rag_agent", "RAGAgent")
    return rag_agent_cls(knowledge_graph=knowledge_graph)


def create_guardrails() -> Any:
    guardrails_cls = _load_attr("app.engine.guardrails", "Guardrails")
    return guardrails_cls()


def get_multi_agent_graph() -> Any:
    return _load_attr("app.engine.multi_agent.graph", "get_multi_agent_graph")()


def get_chat_history_repository() -> Any:
    return _load_attr(
        "app.repositories.chat_history_repository",
        "get_chat_history_repository",
    )()


def get_learning_profile_repository() -> Any:
    return _load_attr(
        "app.repositories.learning_profile_repository",
        "get_learning_profile_repository",
    )()


def get_user_graph_repository() -> Any:
    return _load_attr(
        "app.repositories.user_graph_repository",
        "get_user_graph_repository",
    )()


def get_chat_response_builder() -> Any:
    return _load_attr(
        "app.services.chat_response_builder",
        "get_chat_response_builder",
    )()


def get_learning_graph_service() -> Any:
    return _load_attr(
        "app.services.learning_graph_service",
        "get_learning_graph_service",
    )()


def init_background_runner(**kwargs) -> Any:
    fn = _load_attr("app.services.background_tasks", "init_background_runner")
    return fn(**kwargs)


def init_chat_orchestrator(**kwargs) -> Any:
    fn = _load_attr("app.services.chat_orchestrator", "init_chat_orchestrator")
    return fn(**kwargs)


def get_chat_orchestrator() -> Any:
    return _load_attr("app.services.chat_orchestrator", "get_chat_orchestrator")()


def init_input_processor(**kwargs) -> Any:
    fn = _load_attr("app.services.input_processor", "init_input_processor")
    return fn(**kwargs)


def init_output_processor(**kwargs) -> Any:
    fn = _load_attr("app.services.output_processor", "init_output_processor")
    return fn(**kwargs)


def get_semantic_memory_engine() -> Any:
    return _load_attr(
        "app.engine.semantic_memory",
        "get_semantic_memory_engine",
    )()


def get_prompt_loader() -> Any:
    return _load_attr("app.prompts", "get_prompt_loader")()


def get_memory_summarizer() -> Any:
    return _load_attr(
        "app.engine.memory_summarizer",
        "get_memory_summarizer",
    )()


def get_guardian_agent(*, fallback_guardrails: Any = None) -> Any:
    fn = _load_attr("app.engine.guardian_agent", "get_guardian_agent")
    return fn(fallback_guardrails=fallback_guardrails)


def get_conversation_analyzer() -> Any:
    return _load_attr(
        "app.engine.conversation_analyzer",
        "get_conversation_analyzer",
    )()


def init_all_tools(**kwargs) -> Any:
    fn = _load_attr("app.engine.tools", "init_all_tools")
    return fn(**kwargs)


__all__ = [
    "create_guardrails",
    "create_rag_agent",
    "get_chat_history_repository",
    "get_chat_orchestrator",
    "get_chat_response_builder",
    "get_conversation_analyzer",
    "get_guardian_agent",
    "get_knowledge_repository",
    "get_learning_graph_service",
    "get_learning_profile_repository",
    "get_memory_summarizer",
    "get_multi_agent_graph",
    "get_prompt_loader",
    "get_semantic_memory_engine",
    "get_user_graph_repository",
    "init_all_tools",
    "init_background_runner",
    "init_chat_orchestrator",
    "init_input_processor",
    "init_output_processor",
]
