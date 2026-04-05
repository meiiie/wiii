"""Lazy runtime initialization for the chat service shell."""

from __future__ import annotations

from typing import Any

from app.services.chat_service_runtime_bindings import (
    create_guardrails,
    create_rag_agent,
    get_chat_history_repository,
    get_chat_orchestrator,
    get_chat_response_builder,
    get_conversation_analyzer,
    get_guardian_agent,
    get_knowledge_repository,
    get_learning_graph_service,
    get_learning_profile_repository,
    get_memory_summarizer,
    get_multi_agent_graph,
    get_prompt_loader,
    get_semantic_memory_engine,
    get_user_graph_repository,
    init_all_tools,
    init_background_runner,
    init_chat_orchestrator,
    init_input_processor,
    init_output_processor,
)


def initialize_chat_service_runtime_impl(
    *,
    service: Any,
    settings_obj: Any,
    logger: Any,
) -> None:
    try:
        semantic_memory_available = True
    except ImportError:
        semantic_memory_available = False

    try:
        prompt_loader_available = True
    except ImportError:
        prompt_loader_available = False

    try:
        memory_summarizer_available = True
    except ImportError:
        memory_summarizer_available = False

    try:
        guardian_agent_available = True
    except ImportError:
        guardian_agent_available = False

    try:
        conversation_analyzer_available = True
    except ImportError:
        conversation_analyzer_available = False

    logger.info("Initializing ChatService (Facade Pattern)...")

    service._knowledge_graph = get_knowledge_repository()
    service._user_graph = get_user_graph_repository()
    service._learning_graph = get_learning_graph_service()
    service._pg_profile_repo = get_learning_profile_repository()
    service._chat_history = get_chat_history_repository()
    service._guardrails = create_guardrails()

    if service._chat_history.is_available():
        service._chat_history.ensure_tables()
        logger.info("Chat History initialized")

    service._rag_agent = create_rag_agent(knowledge_graph=service._knowledge_graph)

    service._semantic_memory = service._init_optional(
        "Semantic Memory v0.5",
        semantic_memory_available and settings_obj.semantic_memory_enabled,
        get_semantic_memory_engine,
        check_available=True,
    )
    service._multi_agent_graph = service._init_optional(
        "Multi-Agent System",
        getattr(settings_obj, "use_multi_agent", True),
        get_multi_agent_graph,
    )
    service._guardian_agent = service._init_optional(
        "Guardian Agent",
        guardian_agent_available,
        get_guardian_agent,
        check_available=True,
        fallback_guardrails=service._guardrails,
    )
    service._conversation_analyzer = service._init_optional(
        "Conversation Analyzer",
        conversation_analyzer_available,
        get_conversation_analyzer,
    )
    service._memory_summarizer = service._init_optional(
        "Memory Summarizer",
        memory_summarizer_available,
        get_memory_summarizer,
        check_available=True,
    )
    service._prompt_loader = service._init_optional(
        "Prompt Loader",
        prompt_loader_available,
        get_prompt_loader,
    )

    service._response_builder = get_chat_response_builder()

    init_input_processor(
        guardian_agent=service._guardian_agent,
        guardrails=service._guardrails,
        semantic_memory=service._semantic_memory,
        chat_history=service._chat_history,
        learning_graph=service._learning_graph,
        memory_summarizer=service._memory_summarizer,
        conversation_analyzer=service._conversation_analyzer,
    )

    init_output_processor(
        guardrails=service._guardrails,
        response_builder=service._response_builder,
    )

    init_background_runner(
        chat_history=service._chat_history,
        semantic_memory=service._semantic_memory,
        memory_summarizer=service._memory_summarizer,
        profile_repo=service._pg_profile_repo,
    )

    init_chat_orchestrator(
        multi_agent_graph=service._multi_agent_graph,
        rag_agent=service._rag_agent,
        semantic_memory=service._semantic_memory,
        chat_history=service._chat_history,
        prompt_loader=service._prompt_loader,
        guardrails=service._guardrails,
    )

    init_all_tools(
        rag_agent=service._rag_agent,
        semantic_memory=service._semantic_memory,
    )
    logger.info("[OK] Tool Registry initialized (RAG, Memory tools)")

    service._orchestrator = get_chat_orchestrator()

    logger.info("Knowledge graph available: %s", service._knowledge_graph.is_available())
    logger.info("Chat history available: %s", service._chat_history.is_available())
    logger.info("Semantic memory available: %s", service._semantic_memory is not None)
    logger.info("Multi-Agent available: %s", service._multi_agent_graph is not None)
    logger.info("ChatService initialized (Facade Pattern) [OK]")
