"""
Chat Orchestrator - Pipeline Orchestration for Chat Processing

Extracted from chat_service.py as part of Clean Architecture refactoring.
Orchestrates the complete chat processing pipeline.

**Pattern:** Orchestrator / Pipeline
**Spec:** CHỈ THỊ KỸ THUẬT SỐ 25 - Project Restructure

Authoritative request flow:
see app/services/REQUEST_FLOW_CONTRACT.md
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH
from app.engine.llm_runtime_metadata import resolve_runtime_llm_metadata
from app.models.schemas import ChatRequest, InternalChatResponse, Source

from .session_manager import (
    SessionContext,
    SessionManager,
    get_session_manager,
)
from .input_processor import InputProcessor, ChatContext, get_input_processor
from .output_processor import (
    OutputProcessor,
    ProcessingResult,
    extract_thinking_from_response,
    get_output_processor,
)
from .background_tasks import BackgroundTaskRunner, get_background_runner
from . import living_continuity as _living_continuity

PostResponseContinuityContext = _living_continuity.PostResponseContinuityContext
schedule_post_response_continuity = _living_continuity.schedule_post_response_continuity
_analyze_and_process_sentiment = _living_continuity._analyze_and_process_sentiment

# Compatibility note: legacy Sprint 210 source-inspection tests still verify
# that chat_orchestrator.py references the LLM sentiment path via
# SentimentAnalyzer/get_sentiment_analyzer, even though the implementation now
# lives behind living_continuity.schedule_post_response_continuity().

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
    CODE_STUDIO = "code_studio"


# Map supervisor next_agent values → AgentType
_AGENT_TYPE_MAP = {
    "rag_agent": AgentType.RAG,
    "tutor_agent": AgentType.TUTOR,
    "memory_agent": AgentType.MEMORY,
    "direct": AgentType.DIRECT,
    "code_studio_agent": AgentType.CODE_STUDIO,
}


@dataclass(frozen=True)
class RequestScope:
    """Resolved organization and domain for a chat request."""

    organization_id: str | None
    domain_id: str | None


@dataclass
class PreparedTurn:
    """Shared turn-preparation result for sync and streaming paths."""

    request_scope: RequestScope
    session: SessionContext
    session_id: object
    validation: object
    chat_context: ChatContext | None = None


@dataclass(frozen=True)
class MultiAgentExecutionInput:
    """Authoritative invocation payload for the multi-agent graph."""

    query: str
    user_id: str
    session_id: str
    context: dict
    domain_id: str
    thinking_effort: str | None = None
    provider: str | None = None


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

    Contract note:
    Stage ordering here is the authoritative sync implementation for the chat
    business flow. Changes to that ordering should be reflected in
    REQUEST_FLOW_CONTRACT.md.
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

    async def validate_request(
        self,
        request: ChatRequest,
        session_id,
    ):
        """Run the authoritative input validation contract for this request."""
        return await self._input_processor.validate(
            request=request,
            session_id=session_id,
            create_blocked_response=self._output_processor.create_blocked_response,
        )

    def persist_chat_message(
        self,
        session_id,
        role: str,
        content: str,
        user_id: str | None = None,
        background_save: Optional[Callable] = None,
        immediate: bool = False,
    ) -> None:
        """Persist a chat message using transport-specific timing."""
        if not content:
            return
        if not self._chat_history or not self._chat_history.is_available():
            return

        if immediate or background_save is None:
            self._chat_history.save_message(session_id, role, content, user_id)
            return

        background_save(
            self._chat_history.save_message,
            session_id,
            role,
            content,
            user_id,
        )

    def upsert_thread_view(
        self,
        *,
        user_id: str,
        session_id,
        domain_id: str | None,
        title: str,
        organization_id: str | None,
    ) -> None:
        """Keep thread discovery state aligned across sync and streaming paths."""
        if not title:
            return

        try:
            from app.repositories.thread_repository import get_thread_repository
            from app.core.thread_utils import build_thread_id

            thread_repo = get_thread_repository()
            if not thread_repo.is_available():
                return

            thread_id = build_thread_id(
                str(user_id),
                str(session_id),
                org_id=organization_id,
            )
            thread_repo.upsert_thread(
                thread_id=thread_id,
                user_id=str(user_id),
                domain_id=domain_id or "maritime",
                title=title[:50],
                message_count_increment=2,
                organization_id=organization_id,
            )
        except Exception as exc:
            logger.warning("[ORCHESTRATOR] thread_views upsert failed: %s", exc)

    def finalize_response_turn(
        self,
        *,
        session_id,
        user_id: str,
        user_role,
        message: str,
        response_text: str,
        context: ChatContext | None,
        domain_id: str | None,
        organization_id: str | None,
        current_agent: str = "",
        background_save: Optional[Callable] = None,
        save_response_immediately: bool = False,
        include_lms_insights: bool = True,
        continuity_channel: str = "web",
        transport_type: str = "sync",
    ) -> None:
        """Run the authoritative post-response scheduling contract."""
        used_name = (
            bool(context and context.user_name)
            and context.user_name.lower() in response_text.lower()
        ) if response_text else False
        opening = response_text[:50].strip() if response_text else None
        self._session_manager.update_state(
            session_id=session_id,
            phrase=opening,
            used_name=used_name,
        )

        self.persist_chat_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            user_id=user_id,
            background_save=background_save,
            immediate=save_response_immediately,
        )

        if response_text:
            self.upsert_thread_view(
                user_id=user_id,
                session_id=session_id,
                domain_id=domain_id,
                title=message,
                organization_id=organization_id,
            )

        if background_save and self._background_runner:
            self._background_runner.schedule_all(
                background_save=background_save,
                user_id=user_id,
                session_id=session_id,
                message=message,
                response=response_text,
                skip_fact_extraction=current_agent == "memory_agent",
                org_id=organization_id or "",
            )

        scheduled_hooks = schedule_post_response_continuity(
            PostResponseContinuityContext(
                user_id=user_id,
                user_role=user_role,
                message=message,
                response_text=response_text,
                domain_id=domain_id or "",
                organization_id=organization_id,
                channel=continuity_channel,
            ),
            include_lms_insights=include_lms_insights,
        )

        continuity_summary = {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "domain_id": domain_id or "",
            "organization_id": organization_id or "",
            "transport_type": transport_type,
            "continuity_channel": continuity_channel,
            "include_lms_insights": include_lms_insights,
            "scheduled_hooks": list(scheduled_hooks),
            "background_tasks_scheduled": bool(
                background_save and self._background_runner
            ),
            "response_persistence": (
                "immediate"
                if save_response_immediately or background_save is None
                else "background"
            ),
        }
        logger.info(
            "[CONTINUITY] Finalized turn summary: %s",
            json.dumps(continuity_summary, sort_keys=True),
        )

    @staticmethod
    def normalize_thread_id(request: ChatRequest) -> str | None:
        """Normalize thread/session identifiers into one authoritative thread id."""
        thread_id = request.thread_id
        if thread_id and thread_id.lower() == "new":
            thread_id = None
        if not thread_id and request.session_id:
            thread_id = request.session_id
        return thread_id

    async def resolve_request_scope(self, request: ChatRequest) -> RequestScope:
        """Resolve the authoritative organization and domain for this request."""
        from app.core.org_context import (
            get_current_org_allowed_domains,
            get_current_org_id,
        )
        from app.domains.router import get_domain_router

        organization_id = (
            getattr(request, "organization_id", None)
            or get_current_org_id()
            or settings.default_organization_id
        )
        domain_router = get_domain_router()
        org_allowed_domains = get_current_org_allowed_domains()
        domain_id = await domain_router.resolve(
            query=request.message,
            explicit_domain_id=getattr(request, "domain_id", None),
            allowed_domains=org_allowed_domains,
        )
        return RequestScope(
            organization_id=organization_id,
            domain_id=domain_id,
        )

    async def resolve_lms_identity(
        self,
        user_id: str,
        organization_id: str | None,
    ) -> tuple[str | None, str | None]:
        """Resolve the LMS external identity for a user when integration is enabled."""
        if not settings.enable_lms_integration:
            return None, None

        try:
            from app.auth.external_identity import resolve_lms_identity

            return await resolve_lms_identity(user_id, organization_id)
        except Exception as exc:
            logger.debug("[ORCH] LMS identity resolve failed: %s", exc)
            return None, None

    async def build_multi_agent_context(
        self,
        context: ChatContext,
        session: SessionContext,
    ) -> dict:
        """Build the authoritative multi-agent context payload."""
        lms_external_id, lms_connector_id = await self.resolve_lms_identity(
            context.user_id,
            getattr(context, "organization_id", None),
        )

        return {
            "user_name": context.user_name,
            "user_role": context.user_role.value,
            "lms_course": context.lms_course_name,
            "lms_module": context.lms_module_id,
            "conversation_history": context.conversation_history,
            "semantic_context": context.semantic_context,
            "langchain_messages": context.langchain_messages,
            "conversation_summary": context.conversation_summary or "",
            "core_memory_block": context.core_memory_block,
            "is_follow_up": bool(context.history_list) and len(context.history_list) > 0,
            "conversation_phase": (
                "opening" if session.state.total_responses == 0
                else (
                    "engaged" if session.state.total_responses < 5
                    else (
                        "deep"
                        if session.state.total_responses < 20
                        else "closing"
                    )
                )
            ),
            "total_responses": session.state.total_responses,
            "name_usage_count": session.state.name_usage_count,
            "recent_phrases": session.state.recent_phrases,
            "mood_hint": getattr(context, "mood_hint", "") or "",
            "organization_id": getattr(context, "organization_id", None),
            "images": [
                img.model_dump() if hasattr(img, "model_dump") else img
                for img in context.images
            ] if getattr(context, "images", None) else None,
            "lms_external_id": lms_external_id,
            "lms_connector_id": lms_connector_id,
            "page_context": getattr(context, "page_context", None),
            "student_state": getattr(context, "student_state", None),
            "available_actions": getattr(context, "available_actions", None),
            "host_context": getattr(context, "host_context", None),
            "visual_context": getattr(context, "visual_context", None),
            "widget_feedback": getattr(context, "widget_feedback", None),
            "code_studio_context": getattr(context, "code_studio_context", None),
        }

    async def build_multi_agent_execution_input(
        self,
        *,
        request: ChatRequest,
        prepared_turn: PreparedTurn,
        include_streaming_fields: bool = False,
        thinking_effort: str | None = None,
        provider: str | None = None,
    ) -> MultiAgentExecutionInput:
        """Build the authoritative graph invocation payload for this turn."""
        context = prepared_turn.chat_context
        session = prepared_turn.session
        if context is None:
            raise ValueError("Prepared turn must include chat context")

        graph_context = await self.build_multi_agent_context(context, session)
        if include_streaming_fields:
            graph_context.update(
                {
                    "user_id": request.user_id,
                    "user_facts": getattr(context, "user_facts", []),
                    "pronoun_style": (
                        getattr(context, "pronoun_style", None)
                        or getattr(session.state, "pronoun_style", None)
                    ),
                    "history_list": context.history_list or [],
                    "show_previews": request.show_previews,
                    "preview_types": request.preview_types,
                    "preview_max_count": request.preview_max_count,
                }
            )

        return MultiAgentExecutionInput(
            query=context.message,
            user_id=context.user_id,
            session_id=str(prepared_turn.session_id),
            context=graph_context,
            domain_id=prepared_turn.request_scope.domain_id or settings.default_domain,
            thinking_effort=thinking_effort,
            provider=provider,
        )

    def build_minimal_multi_agent_execution_input(
        self,
        *,
        request: ChatRequest,
        prepared_turn: PreparedTurn,
        thinking_effort: str | None = None,
        provider: str | None = None,
    ) -> MultiAgentExecutionInput:
        """Build a minimal but valid graph invocation payload for degraded paths."""
        return MultiAgentExecutionInput(
            query=request.message,
            user_id=str(request.user_id),
            session_id=str(prepared_turn.session_id),
            context={
                "user_id": request.user_id,
                "user_role": request.role.value,
                "user_name": None,
                "conversation_history": "",
                "organization_id": prepared_turn.request_scope.organization_id,
            },
            domain_id=prepared_turn.request_scope.domain_id or settings.default_domain,
            thinking_effort=thinking_effort,
            provider=provider,
        )

    async def prepare_turn(
        self,
        request: ChatRequest,
        background_save: Optional[Callable] = None,
        persist_user_message_immediately: bool = False,
    ) -> PreparedTurn:
        """Prepare the authoritative pre-execution turn state."""
        user_id = str(request.user_id)
        message = request.message

        thread_id = self.normalize_thread_id(request)
        request_scope = await self.resolve_request_scope(request)

        session = self._session_manager.get_or_create_session(
            user_id,
            thread_id,
            organization_id=request_scope.organization_id,
        )
        session_id = session.session_id

        if session.state.is_first_message and background_save:
            self._maybe_summarize_previous_session(background_save, user_id)
        if session.state.is_first_message and session.state.pronoun_style is None:
            self._load_pronoun_style_from_facts(session, user_id)

        validation = await self.validate_request(
            request=request,
            session_id=session_id,
        )
        if validation.blocked:
            return PreparedTurn(
                request_scope=request_scope,
                session=session,
                session_id=session_id,
                validation=validation,
            )

        self.persist_chat_message(
            session_id=session_id,
            role="user",
            content=message,
            user_id=user_id,
            background_save=background_save,
            immediate=persist_user_message_immediately,
        )

        context = await self._input_processor.build_context(
            request=request,
            session_id=session_id,
            user_name=session.user_name,
        )
        context.organization_id = request_scope.organization_id

        if not session.user_name:
            extracted_name = self._input_processor.extract_user_name(message)
            if extracted_name:
                self._session_manager.update_user_name(session_id, extracted_name)
                context.user_name = extracted_name

        from app.prompts.prompt_loader import detect_pronoun_style

        effective_pronoun = detect_pronoun_style(message)
        if effective_pronoun:
            session.state.update_pronoun_style(effective_pronoun)
        else:
            effective_pronoun = await self._input_processor.validate_pronoun_request(
                message=message,
                current_style=session.state.pronoun_style,
            )
            if effective_pronoun:
                session.state.update_pronoun_style(effective_pronoun)

        if effective_pronoun and self._semantic_memory and background_save:
            self._persist_pronoun_style(background_save, user_id, effective_pronoun)

        return PreparedTurn(
            request_scope=request_scope,
            session=session,
            session_id=session_id,
            validation=validation,
            chat_context=context,
        )
    
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

        prepared_turn = await self.prepare_turn(
            request=request,
            background_save=background_save,
        )
        org_id = prepared_turn.request_scope.organization_id
        domain_id = prepared_turn.request_scope.domain_id
        logger.info("[DOMAIN] Resolved domain: %s (org: %s)", domain_id, org_id)

        # Sprint 66: thinking effort for multi-agent processing
        thinking_effort = getattr(request, 'thinking_effort', None)
        provider = getattr(request, 'provider', None)

        session = prepared_turn.session
        session_id = prepared_turn.session_id

        logger.info("Processing request for user %s with role: %s", user_id, user_role.value)

        if prepared_turn.validation.blocked:
            return prepared_turn.validation.blocked_response

        context = prepared_turn.chat_context

        # ================================================================
        # STAGE 4: AGENT PROCESSING
        # ================================================================
        
        # Option A: Multi-Agent System (SOTA 2025)
        if self._use_multi_agent:
            result = await self._process_with_multi_agent(context, session, domain_id, thinking_effort, provider)

        # Option B: Fallback to direct RAG mode
        else:
            result = await self.process_without_multi_agent(context)
        
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
        # Source-inspection compatibility: this stage still covers
        # save_message, schedule_all, routine_tracker.record_interaction,
        # and _analyze_and_process_sentiment via finalize_response_turn()
        # and living_continuity.schedule_post_response_continuity().
        
        self.finalize_response_turn(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            message=message,
            response_text=result.message or "",
            context=context,
            domain_id=domain_id,
            organization_id=org_id,
            current_agent=(result.metadata or {}).get("current_agent", ""),
            background_save=background_save,
            continuity_channel="web",
            transport_type="sync",
        )

        return response

    def _should_use_local_direct_llm_fallback(self) -> bool:
        """Use direct local inference when local mode is enabled without cloud retrieval support."""
        provider = getattr(settings, "llm_provider", "google")
        return provider == "ollama" and not settings.google_api_key

    async def process_without_multi_agent(self, context: ChatContext) -> ProcessingResult:
        """Run the authoritative non-multi-agent fallback used by sync and stream."""
        if self._should_use_local_direct_llm_fallback():
            logger.warning("[FALLBACK] Multi-Agent unavailable, using local direct LLM")
            return await self._process_with_direct_llm(context)

        logger.warning("[FALLBACK] Multi-Agent unavailable, using direct RAG")

        if self._rag_agent:
            rag_result = await self._rag_agent.query(
                question=context.message,
                user_role=context.user_role.value,
                limit=5
            )
            runtime_llm = resolve_runtime_llm_metadata()
            return ProcessingResult(
                message=rag_result.content,
                agent_type=AgentType.RAG,
                sources=self._output_processor.format_sources(rag_result.citations) if rag_result.citations else None,
                metadata={
                    "mode": "fallback_rag",
                    **runtime_llm,
                },
                thinking=getattr(rag_result, "native_thinking", None),
            )

        logger.error("[ERROR] No processing agent available")
        raise RuntimeError("No processing agent available")

    async def _process_with_direct_llm(self, context: ChatContext) -> ProcessingResult:
        """Generate a local-first response without RAG when cloud retrieval is unavailable."""
        from app.engine.llm_pool import get_llm_light

        llm = get_llm_light()
        response = await llm.ainvoke(context.message)
        message, thinking = extract_thinking_from_response(response.content)

        return ProcessingResult(
            message=message,
            agent_type=AgentType.DIRECT,
            metadata={
                "mode": "local_direct_llm",
                **resolve_runtime_llm_metadata(
                    {
                        "provider": getattr(settings, "llm_provider", "ollama"),
                        "model": getattr(settings, "ollama_model", None),
                    }
                ),
            },
            thinking=thinking,
        )
    
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
        session: SessionContext,
        domain_id: str | None = None,
        thinking_effort: str | None = None,
        provider: str | None = None,
    ) -> ProcessingResult:
        """
        Process with Multi-Agent System (LangGraph).
        
        Phase 8: SOTA 2025 - Supervisor Agent
        """
        logger.info("[MULTI-AGENT] Processing with Multi-Agent System (SOTA 2025)")
        
        from app.engine.multi_agent.graph import process_with_multi_agent

        prepared_turn = PreparedTurn(
            request_scope=RequestScope(
                organization_id=getattr(context, "organization_id", None),
                domain_id=domain_id,
            ),
            session=session,
            session_id=context.session_id,
            validation=None,
            chat_context=context,
        )
        execution_input = await self.build_multi_agent_execution_input(
            request=ChatRequest.model_construct(
                user_id=context.user_id,
                message=context.message,
                role=context.user_role,
                show_previews=False,
                preview_types=None,
                preview_max_count=None,
            ),
            prepared_turn=prepared_turn,
            thinking_effort=thinking_effort,
            provider=provider,
        )

        result = await process_with_multi_agent(
            query=execution_input.query,
            user_id=execution_input.user_id,
            session_id=execution_input.session_id,
            context=execution_input.context,
            domain_id=execution_input.domain_id,
            thinking_effort=execution_input.thinking_effort,
            provider=execution_input.provider,
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
