"""
Chat Orchestrator - Pipeline Orchestration for Chat Processing

Extracted from chat_service.py as part of Clean Architecture refactoring.
Orchestrates the complete chat processing pipeline.

**Pattern:** Orchestrator / Pipeline
**Spec:** CHỈ THỊ KỸ THUẬT SỐ 25 - Project Restructure
"""

import logging
from enum import Enum
from typing import Callable, Optional

from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH
from app.models.schemas import ChatRequest, InternalChatResponse, Source

from .session_manager import SessionContext, SessionManager, get_session_manager
from .input_processor import InputProcessor, ChatContext, get_input_processor
from .output_processor import OutputProcessor, ProcessingResult, get_output_processor
from .background_tasks import BackgroundTaskRunner, get_background_runner

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT TYPE ENUM (for backward compatibility)
# =============================================================================

class AgentType(str, Enum):
    """Types of agents in the system."""
    CHAT = "chat"
    RAG = "rag"
    TUTOR = "tutor"
    DIRECT = "direct"
    MEMORY = "memory"


# Map supervisor next_agent values → AgentType
_AGENT_TYPE_MAP = {
    "rag_agent": AgentType.RAG,
    "tutor_agent": AgentType.TUTOR,
    "memory_agent": AgentType.MEMORY,
    "direct": AgentType.DIRECT,
}


# =============================================================================
# CHAT ORCHESTRATOR
# =============================================================================

class ChatOrchestrator:
    """
    Orchestrates the chat processing pipeline.
    
    Pipeline stages:
    1. Input validation (Guardian/Guardrails)
    2. Context retrieval (Memory, History, Insights)
    3. Agent processing (MultiAgent)
    4. Output validation & formatting
    5. Background tasks (Memory, Profile)
    
    **Pattern:** Orchestrator with Single Responsibility stages
    """
    
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        input_processor: Optional[InputProcessor] = None,
        output_processor: Optional[OutputProcessor] = None,
        background_runner: Optional[BackgroundTaskRunner] = None,
        multi_agent_graph=None,
        rag_agent=None,
        semantic_memory=None,
        chat_history=None,
        prompt_loader=None,
        guardrails=None
    ):
        """
        Initialize orchestrator with all dependencies.
        
        Dependencies are lazily initialized if not provided.
        """
        # Core processors
        self._session_manager = session_manager or get_session_manager()
        self._input_processor = input_processor or get_input_processor()
        self._output_processor = output_processor or get_output_processor()
        self._background_runner = background_runner or get_background_runner()
        
        # Agents
        self._multi_agent_graph = multi_agent_graph
        self._rag_agent = rag_agent
        
        # Dependencies for context building
        self._semantic_memory = semantic_memory
        self._chat_history = chat_history
        self._prompt_loader = prompt_loader
        self._guardrails = guardrails
        
        # Configuration flags
        self._use_multi_agent = getattr(settings, 'use_multi_agent', True)
        
        logger.info("ChatOrchestrator initialized")
    
    async def process(
        self,
        request: ChatRequest,
        background_save: Optional[Callable] = None
    ) -> InternalChatResponse:
        """
        Process a chat request through the full pipeline.
        
        Pipeline:
        1. Get/create session
        2. Validate input
        3. Build context
        4. Process with agent
        5. Format output
        6. Schedule background tasks
        
        Args:
            request: ChatRequest from API
            background_save: FastAPI BackgroundTasks.add_task
            
        Returns:
            InternalChatResponse ready for API serialization
        """
        user_id = str(request.user_id)
        message = request.message
        user_role = request.role

        # Handle thread_id "new" as None
        thread_id = request.thread_id
        if thread_id and thread_id.lower() == "new":
            thread_id = None
        # Fall back to session_id when no thread_id (connects API session to pipeline)
        if not thread_id and request.session_id:
            thread_id = request.session_id

        # ================================================================
        # STAGE 0: DOMAIN RESOLUTION (Wiii)
        # ================================================================
        from app.domains.router import get_domain_router
        from app.core.org_context import get_current_org_id, get_current_org_allowed_domains

        # Resolve org_id: request body → context var → config default
        org_id = (
            getattr(request, 'organization_id', None)
            or get_current_org_id()
            or settings.default_organization_id
        )
        self._current_org_id = org_id

        domain_router = get_domain_router()
        org_allowed_domains = get_current_org_allowed_domains()
        domain_id = await domain_router.resolve(
            query=message,
            explicit_domain_id=getattr(request, 'domain_id', None),
            allowed_domains=org_allowed_domains,
        )
        logger.info("[DOMAIN] Resolved domain: %s (org: %s)", domain_id, org_id)

        # Store domain_id for later stages
        self._current_domain_id = domain_id

        # Store thinking_effort for multi-agent processing (Sprint 66)
        self._thinking_effort = getattr(request, 'thinking_effort', None)

        # ================================================================
        # STAGE 1: SESSION MANAGEMENT
        # ================================================================
        session = self._session_manager.get_or_create_session(user_id, thread_id)
        session_id = session.session_id

        # Sprint 79: Auto-summarize previous session on new session start
        if session.state.is_first_message and background_save:
            self._maybe_summarize_previous_session(background_save, user_id)

        # Sprint 79: Pre-populate pronoun style from stored facts (cross-session)
        if session.state.is_first_message and session.state.pronoun_style is None:
            self._load_pronoun_style_from_facts(session, user_id)

        logger.info("Processing request for user %s with role: %s", user_id, user_role.value)
        
        # ================================================================
        # STAGE 2: INPUT VALIDATION
        # ================================================================
        validation = await self._input_processor.validate(
            request=request,
            session_id=session_id,
            create_blocked_response=self._output_processor.create_blocked_response
        )
        
        if validation.blocked:
            return validation.blocked_response
        
        # Save user message to history
        if self._chat_history and self._chat_history.is_available() and background_save:
            background_save(
                self._chat_history.save_message,
                session_id, "user", message
            )
        
        # ================================================================
        # STAGE 3: CONTEXT BUILDING
        # ================================================================
        context = await self._input_processor.build_context(
            request=request,
            session_id=session_id,
            user_name=session.user_name
        )

        # Sprint 160: Thread org_id into ChatContext for data isolation
        context.organization_id = org_id
        
        # Update session with extracted user name
        if not session.user_name:
            extracted_name = self._input_processor.extract_user_name(message)
            if extracted_name:
                self._session_manager.update_user_name(session_id, extracted_name)
                context.user_name = extracted_name
        
        # Pronoun detection: regex first, LLM validation only if regex fails
        from app.prompts.prompt_loader import detect_pronoun_style
        effective_pronoun = detect_pronoun_style(message)
        if effective_pronoun:
            session.state.update_pronoun_style(effective_pronoun)
        else:
            # Custom pronoun validation with Guardian (only when regex detection fails)
            effective_pronoun = await self._input_processor.validate_pronoun_request(
                message=message,
                current_style=session.state.pronoun_style
            )
            if effective_pronoun:
                session.state.update_pronoun_style(effective_pronoun)

        # Sprint 79: Persist pronoun style as fact for cross-session survival
        if effective_pronoun and self._semantic_memory and background_save:
            self._persist_pronoun_style(background_save, user_id, effective_pronoun)

        # ================================================================
        # STAGE 4: AGENT PROCESSING
        # ================================================================
        
        # Option A: Multi-Agent System (SOTA 2025)
        if self._use_multi_agent and self._multi_agent_graph is not None:
            result = await self._process_with_multi_agent(context, session)

        # Option B: Fallback to direct RAG mode
        else:
            logger.warning("[FALLBACK] Multi-Agent unavailable, using direct RAG")

            if self._rag_agent:
                rag_result = await self._rag_agent.query(
                    question=context.message,
                    user_role=context.user_role.value,
                    limit=5
                )
                result = ProcessingResult(
                    message=rag_result.answer,
                    agent_type=AgentType.RAG,
                    sources=self._output_processor.format_sources(rag_result.citations) if rag_result.citations else None,
                    metadata={"mode": "fallback_rag"}
                )
            else:
                logger.error("[ERROR] No processing agent available")
                raise RuntimeError("No processing agent available")
        
        # ================================================================
        # STAGE 5: OUTPUT FORMATTING
        # ================================================================
        response = await self._output_processor.validate_and_format(
            result=result,
            session_id=session_id,
            user_name=context.user_name,
            user_role=user_role
        )
        
        # ================================================================
        # STAGE 6: POST-PROCESSING & BACKGROUND TASKS
        # ================================================================
        
        # Update session state
        used_name = (
            bool(context.user_name)
            and context.user_name.lower() in result.message.lower()
        ) if context.user_name else False
        opening = result.message[:50].strip() if result.message else None
        self._session_manager.update_state(
            session_id=session_id,
            phrase=opening,
            used_name=used_name
        )
        
        # Save AI response
        if self._chat_history and self._chat_history.is_available() and background_save:
            background_save(
                self._chat_history.save_message,
                session_id, "assistant", result.message
            )
        
        # Schedule background tasks
        if background_save and self._background_runner:
            # Skip redundant fact extraction if memory agent already handled it
            current_agent = (result.metadata or {}).get("current_agent", "")
            self._background_runner.schedule_all(
                background_save=background_save,
                user_id=user_id,
                session_id=session_id,
                message=message,
                response=result.message,
                skip_fact_extraction=current_agent == "memory_agent",
            )
        
        return response
    
    def _load_pronoun_style_from_facts(
        self,
        session: SessionContext,
        user_id: str,
    ) -> None:
        """Sprint 79: Load persisted pronoun style from user facts into new session."""
        try:
            if not self._semantic_memory or not self._semantic_memory.is_available():
                return

            import json
            from app.repositories.semantic_memory_repository import get_semantic_memory_repository
            from app.models.semantic_memory import MemoryType

            repo = get_semantic_memory_repository()
            if not repo.is_available():
                return

            # Query facts with pronoun_style type
            results = repo.get_memories_by_type(
                user_id=user_id,
                memory_type=MemoryType.USER_FACT,
                limit=10,
            )
            for mem in results:
                meta = mem.metadata or {}
                if meta.get("fact_type") == "pronoun_style":
                    # Content is "pronoun_style: {json}"
                    content = mem.content
                    value = content.split(": ", 1)[-1] if ": " in content else content
                    pronoun_dict = json.loads(value)
                    session.state.update_pronoun_style(pronoun_dict)
                    logger.debug("[SPRINT79] Loaded pronoun_style from facts for %s", user_id)
                    return
        except Exception as e:
            logger.debug("Failed to load pronoun style from facts: %s", e)

    def _persist_pronoun_style(
        self,
        background_save: Callable,
        user_id: str,
        pronoun_style: dict,
    ) -> None:
        """Sprint 79: Store detected pronoun style as a user fact for cross-session persistence."""
        import json

        def _store():
            try:
                from app.repositories.semantic_memory_repository import get_semantic_memory_repository
                from app.models.semantic_memory import (
                    SemanticTriple,
                    Predicate,
                )

                repo = get_semantic_memory_repository()
                if not repo.is_available():
                    return

                pronoun_str = json.dumps(pronoun_style, ensure_ascii=False)
                triple = SemanticTriple(
                    subject=user_id,
                    predicate=Predicate.HAS_PRONOUN_STYLE,
                    object=pronoun_str,
                    object_type="personal",
                    confidence=0.8,
                )
                repo.upsert_triple(triple)
                logger.debug("[SPRINT79] Persisted pronoun_style for %s", user_id)
            except Exception as e:
                logger.debug("Failed to persist pronoun style: %s", e)

        background_save(_store)

    def _maybe_summarize_previous_session(
        self,
        background_save: Callable,
        user_id: str,
    ) -> None:
        """Sprint 79: Trigger background summarization of user's previous session.

        When a user starts a new session (first message), summarize the previous
        session so that Layer 3 cross-session context (session_summarizer) is populated.
        """
        try:
            from app.repositories.thread_repository import get_thread_repository
            repo = get_thread_repository()
            threads = repo.list_threads(user_id=user_id, limit=2)
            if len(threads) >= 2:
                prev = threads[1]  # threads[0] is current, threads[1] is previous
                extra = prev.get("extra_data") or {}
                if not extra.get("summary"):
                    from app.tasks.summarize_tasks import summarize_thread_background
                    background_save(
                        summarize_thread_background,
                        prev["thread_id"],
                        user_id,
                    )
                    logger.info(
                        "[SPRINT79] Triggered auto-summarize of previous session %s",
                        prev["thread_id"],
                    )
        except Exception as e:
            logger.debug("Auto-summarize previous session failed: %s", e)

    async def _process_with_multi_agent(
        self,
        context: ChatContext,
        session: SessionContext
    ) -> ProcessingResult:
        """
        Process with Multi-Agent System (LangGraph).
        
        Phase 8: SOTA 2025 - Supervisor Agent
        """
        logger.info("[MULTI-AGENT] Processing with Multi-Agent System (SOTA 2025)")
        
        from app.engine.multi_agent.graph import process_with_multi_agent
        
        # Build context for multi-agent
        multi_agent_context = {
            "user_name": context.user_name,
            "user_role": context.user_role.value,
            "lms_course": context.lms_course_name,
            "lms_module": context.lms_module_id,
            "conversation_history": context.conversation_history,  # flat string (backward compat)
            "semantic_context": context.semantic_context,          # SEPARATE (not merged)
            # Sprint 77: LangChain messages for agent node history injection
            "langchain_messages": context.langchain_messages,
            "conversation_summary": context.conversation_summary or "",
            # Sprint 73: Core Memory Block (structured user profile)
            "core_memory_block": context.core_memory_block,
            # Sprint 76: Follow-up detection — suppress repeated greetings
            "is_follow_up": bool(context.history_list) and len(context.history_list) > 0,
            # Sprint 115: Identity anchor data flow fix — pass session counters
            "total_responses": session.state.total_responses,
            "name_usage_count": session.state.name_usage_count,
            "recent_phrases": session.state.recent_phrases,
            # Sprint 115: Emotional state mood hint
            "mood_hint": getattr(context, 'mood_hint', "") or "",
            # Sprint 160: Multi-Tenant Data Isolation
            "organization_id": getattr(context, 'organization_id', None),
        }

        # Use domain_id from Stage 0 (falls back to config default)
        domain_id = getattr(self, '_current_domain_id', None) or settings.default_domain

        result = await process_with_multi_agent(
            query=context.message,
            user_id=context.user_id,
            session_id=str(context.session_id),
            context=multi_agent_context,
            domain_id=domain_id,
            thinking_effort=getattr(self, '_thinking_effort', None)
        )
        
        response_text = result.get("response", "")
        sources = result.get("sources", [])
        
        # Convert sources to Source objects
        source_objects = []
        for s in sources:
            source_objects.append(Source(
                node_id=s.get("node_id", ""),
                title=s.get("title", ""),
                source_type="knowledge_graph",
                content_snippet=s.get("content", "")[:MAX_CONTENT_SNIPPET_LENGTH],
                image_url=s.get("image_url"),
                # Feature: source-highlight-citation - Copy metadata for PDF highlighting
                page_number=s.get("page_number"),
                document_id=s.get("document_id"),
                bounding_boxes=s.get("bounding_boxes")
            ))
        
        # Extract tools_used from Multi-Agent result (SOTA: API transparency)
        tools_used = result.get("agent_outputs", {}).get("tutor_tools_used", [])
        if not tools_used:
            # Fallback: check top-level tools_used
            tools_used = result.get("tools_used", [])
        
        # Sprint 85: Use actual routing decision instead of hardcoded RAG
        routed_agent = result.get("next_agent", "")
        agent_type = _AGENT_TYPE_MAP.get(routed_agent, AgentType.RAG)

        return ProcessingResult(
            message=response_text,
            agent_type=agent_type,
            sources=source_objects if source_objects else None,
            metadata={
                "multi_agent": True,
                "current_agent": result.get("current_agent", ""),
                "grader_score": result.get("grader_score", 0),
                "tools_used": tools_used,  # SOTA: Track tool usage
                # CHỈ THỊ SỐ 28: Include reasoning_trace from multi-agent flow
                "reasoning_trace": result.get("reasoning_trace"),
                # CHỈ THỊ SỐ 29: Thinking fields - prioritize thinking over thinking_content
                "thinking": result.get("thinking") or result.get("thinking_content"),
                "thinking_content": result.get("thinking_content"),
                # Sprint 80b: Domain notice for off-domain content
                "domain_notice": result.get("domain_notice"),
                # Sprint 103: Routing metadata for API debugging
                "routing_metadata": result.get("routing_metadata"),
            }
        )


# =============================================================================
# SINGLETON
# =============================================================================

_chat_orchestrator: Optional[ChatOrchestrator] = None


def get_chat_orchestrator() -> ChatOrchestrator:
    """Get or create ChatOrchestrator singleton."""
    global _chat_orchestrator
    if _chat_orchestrator is None:
        _chat_orchestrator = ChatOrchestrator()
    return _chat_orchestrator


def init_chat_orchestrator(
    session_manager=None,
    input_processor=None,
    output_processor=None,
    background_runner=None,
    multi_agent_graph=None,
    rag_agent=None,
    semantic_memory=None,
    chat_history=None,
    prompt_loader=None,
    guardrails=None
) -> ChatOrchestrator:
    """Initialize ChatOrchestrator with all dependencies."""
    global _chat_orchestrator
    _chat_orchestrator = ChatOrchestrator(
        session_manager=session_manager,
        input_processor=input_processor,
        output_processor=output_processor,
        background_runner=background_runner,
        multi_agent_graph=multi_agent_graph,
        rag_agent=rag_agent,
        semantic_memory=semantic_memory,
        chat_history=chat_history,
        prompt_loader=prompt_loader,
        guardrails=guardrails
    )
    return _chat_orchestrator
