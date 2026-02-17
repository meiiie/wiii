"""
Input Processor - Input Validation and Context Building

Extracted from chat_service.py as part of Clean Architecture refactoring.
Handles all input processing: validation, guardian, pronoun detection, context building.

**Pattern:** Processor Service
**Spec:** CHỈ THỊ KỸ THUẬT SỐ 25 - Project Restructure
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.config import settings
from app.models.schemas import ChatRequest, UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ValidationResult:
    """Result of input validation."""
    blocked: bool = False
    blocked_response: Any = None  # InternalChatResponse
    flagged: bool = False
    flag_reason: Optional[str] = None
    pronoun_style: Optional[dict] = None


@dataclass
class ChatContext:
    """Complete context for chat processing."""
    user_id: str
    session_id: UUID
    message: str
    user_role: UserRole
    user_name: Optional[str] = None

    # LMS Context
    lms_user_name: Optional[str] = None
    lms_module_id: Optional[str] = None
    lms_course_name: Optional[str] = None
    lms_language: str = "vi"

    # Memory Context
    semantic_context: str = ""
    conversation_history: str = ""
    history_list: List[Dict[str, str]] = None
    user_facts: List[Any] = None
    conversation_summary: Optional[str] = None

    # Sprint 77: LangChain messages for agent nodes (no truncation)
    langchain_messages: List[Any] = None  # List[BaseMessage]

    # Sprint 73: Core Memory Block (structured user profile for all agents)
    core_memory_block: str = ""

    # Sprint 115: Emotional state mood hint
    mood_hint: str = ""

    # Analysis Context
    conversation_analysis: Any = None  # ConversationContext

    def __post_init__(self):
        if self.history_list is None:
            self.history_list = []
        if self.user_facts is None:
            self.user_facts = []
        if self.langchain_messages is None:
            self.langchain_messages = []


# =============================================================================
# INPUT PROCESSOR SERVICE
# =============================================================================

class InputProcessor:
    """
    Handles all input processing for chat requests.
    
    Responsibilities:
    - Input validation (Guardian Agent / Guardrails)
    - Pronoun detection
    - Context building (memory, history, insights)
    - User name extraction
    
    **Pattern:** Processor Service
    """
    
    def __init__(
        self,
        guardian_agent=None,
        guardrails=None,
        semantic_memory=None,
        chat_history=None,
        learning_graph=None,
        memory_summarizer=None,
        conversation_analyzer=None
    ):
        """
        Initialize with dependencies (lazy loaded).
        
        All dependencies are optional and will be lazily initialized if not provided.
        """
        self._guardian_agent = guardian_agent
        self._guardrails = guardrails
        self._semantic_memory = semantic_memory
        self._chat_history = chat_history
        self._learning_graph = learning_graph
        self._memory_summarizer = memory_summarizer
        self._conversation_analyzer = conversation_analyzer
        
        logger.info("InputProcessor initialized")
    
    async def validate(
        self,
        request: ChatRequest,
        session_id: UUID,
        create_blocked_response: callable
    ) -> ValidationResult:
        """
        Validate input with Guardian or Guardrails.
        
        CHỈ THỊ SỐ 21: Guardian Agent (LLM-based Content Moderation)
        
        Args:
            request: ChatRequest from API
            session_id: Session UUID for logging blocked messages
            create_blocked_response: Callback to create blocked response
            
        Returns:
            ValidationResult with blocked status and optional blocked response
        """
        message = request.message
        user_id = str(request.user_id)
        
        result = ValidationResult()
        
        # Use LLM-based Guardian Agent for contextual content filtering
        if self._guardian_agent is not None:
            guardian_decision = await self._guardian_agent.validate_message(
                message=message,
                context="education"
            )
            
            if guardian_decision.action == "BLOCK":
                logger.warning("[GUARDIAN] Input blocked for user %s: %s", user_id, guardian_decision.reason)
                result.blocked = True
                result.blocked_response = create_blocked_response([guardian_decision.reason or "Nội dung không phù hợp"])
                
                # Log blocked message to DB
                self._log_blocked_message(session_id, message, user_id, guardian_decision.reason)
                
            elif guardian_decision.action == "FLAG":
                logger.info("[GUARDIAN] Input flagged for user %s: %s", user_id, guardian_decision.reason)
                result.flagged = True
                result.flag_reason = guardian_decision.reason
        else:
            # Fallback to rule-based Guardrails
            if self._guardrails:
                input_result = await self._guardrails.validate_input(message)
                if not input_result.is_valid:
                    logger.warning("Input blocked for user %s: %s", user_id, input_result.issues)
                    result.blocked = True
                    result.blocked_response = create_blocked_response(input_result.issues)
                    
                    # Log blocked message
                    self._log_blocked_message(session_id, message, user_id, "; ".join(input_result.issues))
        
        return result
    
    def _log_blocked_message(
        self,
        session_id: UUID,
        message: str,
        user_id: str,
        reason: str
    ) -> None:
        """Log blocked message to chat history for admin review."""
        if self._chat_history and self._chat_history.is_available():
            self._chat_history.save_message(
                session_id=session_id,
                role="user",
                content=message,
                user_id=user_id,
                is_blocked=True,
                block_reason=reason
            )
            logger.info("[MEMORY ISOLATION] Blocked message saved to chat_history with is_blocked=True")
    
    async def build_context(
        self,
        request: ChatRequest,
        session_id: UUID,
        user_name: Optional[str] = None
    ) -> ChatContext:
        """
        Build complete context for chat processing.
        
        Retrieves:
        - Semantic memory (insights + facts)
        - Conversation history
        - Learning graph context
        - Conversation summary
        
        Args:
            request: ChatRequest from API
            session_id: Session UUID
            user_name: Optional pre-known user name
            
        Returns:
            ChatContext with all retrieved context
        """
        user_id = str(request.user_id)
        message = request.message
        user_context = request.user_context
        
        # Initialize context
        context = ChatContext(
            user_id=user_id,
            session_id=session_id,
            message=message,
            user_role=request.role,
            user_name=user_name,
            lms_user_name=user_context.display_name if user_context else None,
            lms_module_id=user_context.current_module_id if user_context else None,
            lms_course_name=user_context.current_course_name if user_context else None,
            lms_language=user_context.language if user_context else "vi"
        )
        
        # Prioritize LMS user name
        if context.lms_user_name and not context.user_name:
            context.user_name = context.lms_user_name
        
        # Build semantic context
        semantic_parts = []
        
        # 1. Retrieve prioritized insights (v0.5) - Parallelized for performance
        if self._semantic_memory and self._semantic_memory.is_available():
            try:
                # Create parallel tasks for insights and context retrieval
                insights_task = self._semantic_memory.retrieve_insights_prioritized(
                    user_id=user_id,
                    query=message,
                    limit=10
                )
                # Sprint 122 (Bug F4): include_user_facts=False to eliminate path 1
                # of triple injection. User facts are now ONLY injected via
                # build_system_prompt() → "THÔNG TIN NGƯỜI DÙNG" section.
                context_task = self._semantic_memory.retrieve_context(
                    user_id=user_id,
                    query=message,
                    search_limit=5,
                    similarity_threshold=settings.similarity_threshold,
                    include_user_facts=False
                )

                # Execute in parallel
                results = await asyncio.gather(
                    insights_task,
                    context_task,
                    return_exceptions=True
                )

                insights, mem_context = results

                # Handle insights result
                if isinstance(insights, Exception):
                    logger.warning("Insights retrieval failed: %s", insights)
                    insights = []
                elif insights:
                    insight_lines = [f"- [{i.category.value}] {i.content}" for i in insights[:5]]
                    semantic_parts.append(f"=== Behavioral Insights ===\n" + "\n".join(insight_lines))
                    logger.info("[INSIGHT ENGINE] Retrieved %d prioritized insights for user %s", len(insights), user_id)

                # Handle context result
                if isinstance(mem_context, Exception):
                    logger.warning("Context retrieval failed: %s", mem_context)
                    context.user_facts = []
                else:
                    traditional_context = mem_context.to_prompt_context()
                    if traditional_context:
                        semantic_parts.append(traditional_context)
                    # Sprint 122 (Bug F4): User facts fetched separately below
                    context.user_facts = []

            except Exception as e:
                logger.warning("Semantic memory retrieval failed: %s", e)

            # Sprint 122 (Bug F4): Fetch user facts ONCE for build_system_prompt() injection
            # Sprint 123 (P1): Convert to FactWithProvenance for provenance annotations
            try:
                from app.models.semantic_memory import FactWithProvenance
                from app.engine.semantic_memory.importance_decay import (
                    calculate_effective_importance_from_timestamps,
                )

                raw_facts = self._semantic_memory.get_user_facts(
                    user_id=user_id, limit=20, deduplicate=True, apply_decay=True,
                )
                provenance_facts = []
                for rf in (raw_facts or []):
                    meta = rf.metadata or {}
                    fact_type = meta.get("fact_type", "unknown")
                    access_count = meta.get("access_count", 0)
                    effective = calculate_effective_importance_from_timestamps(
                        base_importance=rf.importance,
                        fact_type=fact_type,
                        last_accessed=meta.get("last_accessed"),
                        created_at=rf.created_at,
                        access_count=access_count,
                    )
                    # Extract value from "fact_type: value" format
                    value = rf.content.split(": ", 1)[-1] if ": " in rf.content else rf.content
                    provenance_facts.append(FactWithProvenance(
                        content=value,
                        fact_type=fact_type,
                        confidence=meta.get("confidence", 0.8),
                        created_at=rf.created_at,
                        last_accessed=meta.get("last_accessed"),
                        access_count=access_count,
                        source_quote=meta.get("source_quote"),
                        effective_importance=effective,
                        memory_id=rf.id,
                    ))
                context.user_facts = provenance_facts
            except Exception as e:
                logger.warning("User facts retrieval failed: %s", e)
                context.user_facts = []
        
        # 2. Parallel context retrieval (REFACTOR-004: ~20% latency reduction)
        # Learning Graph and Memory Summarizer are independent async operations
        # Pattern: asyncio.gather with return_exceptions for graceful degradation
        # Reference: app/services/hybrid_search_service.py:173-177

        parallel_tasks = {}

        # Task 1: Learning Graph context (students only)
        if (self._learning_graph and
            self._learning_graph.is_available() and
            request.role == UserRole.STUDENT):
            parallel_tasks['learning_graph'] = self._learning_graph.get_user_learning_context(user_id)

        # Task 2: Conversation summary
        if self._memory_summarizer:
            parallel_tasks['memory_summary'] = self._memory_summarizer.get_summary_async(str(session_id))

        # Task 3: Session summaries — Layer 3 cross-session context (Sprint 17)
        # Sprint 121: Skip cross-session injection for very short messages (<10 chars)
        # Short messages like "in", "hi", "ok" don't need old session context —
        # injecting it causes LLM to fabricate "you mentioned X before" hallucinations.
        if len(message.strip()) >= 10:
            try:
                from app.services.session_summarizer import get_session_summarizer
                parallel_tasks['session_summaries'] = get_session_summarizer().get_recent_summaries(user_id)
            except Exception as e:
                logger.debug("Session summarizer not available: %s", e)
        else:
            logger.debug("[SESSION_SUMMARY] Skipped for short message (%d chars)", len(message.strip()))

        # Execute parallel tasks
        if parallel_tasks:
            results = await asyncio.gather(*parallel_tasks.values(), return_exceptions=True)
            parallel_results = dict(zip(parallel_tasks.keys(), results))

            # Handle Learning Graph result
            if 'learning_graph' in parallel_results:
                graph_result = parallel_results['learning_graph']
                if isinstance(graph_result, Exception):
                    logger.warning("Learning graph retrieval failed: %s", graph_result)
                else:
                    graph_context = graph_result
                    if graph_context.get("learning_path"):
                        path_items = [f"- {m['title']}" for m in graph_context["learning_path"][:5]]
                        semantic_parts.append(f"=== Learning Path ===\n" + "\n".join(path_items))

                    if graph_context.get("knowledge_gaps"):
                        gap_items = [f"- {g['topic_name']}" for g in graph_context["knowledge_gaps"][:5]]
                        semantic_parts.append(f"=== Knowledge Gaps ===\n" + "\n".join(gap_items))

                    logger.info("[LEARNING GRAPH] Added graph context for %s", user_id)

            # Handle Memory Summary result
            if 'memory_summary' in parallel_results:
                summary_result = parallel_results['memory_summary']
                if isinstance(summary_result, Exception):
                    logger.warning("Failed to get conversation summary: %s", summary_result)
                else:
                    context.conversation_summary = summary_result

            # Handle Session Summaries result (Layer 3: cross-session context, Sprint 17)
            if 'session_summaries' in parallel_results:
                ss_result = parallel_results['session_summaries']
                if isinstance(ss_result, Exception):
                    logger.warning("Session summaries retrieval failed: %s", ss_result)
                elif ss_result:
                    semantic_parts.append(ss_result)
                    logger.info("[SESSION_SUMMARY] Layer 3 context added for %s", user_id)

        context.semantic_context = "\n\n".join(semantic_parts)

        # 2b. Sprint 73: Compile Core Memory Block (structured profile)
        try:
            from app.engine.semantic_memory.core_memory_block import get_core_memory_block
            core_block = get_core_memory_block()
            context.core_memory_block = await core_block.get_block(
                user_id=user_id,
                semantic_memory=self._semantic_memory,
            )
            if context.core_memory_block:
                logger.info("[CORE_MEMORY] Compiled profile for %s: %d chars", user_id, len(context.core_memory_block))
        except Exception as e:
            logger.warning("[CORE_MEMORY] Failed to compile profile: %s", e)

        # 3. Get sliding window history (synchronous - fast local operation)
        if self._chat_history and self._chat_history.is_available():
            recent_messages = self._chat_history.get_recent_messages(session_id)
            logger.info("[HISTORY] Loaded %d messages for session %s", len(recent_messages), session_id)
            context.conversation_history = self._chat_history.format_history_for_prompt(recent_messages)

            # Build history list for multi-agent processing
            for msg in recent_messages:
                context.history_list.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Get user name if not already set
            if not context.user_name:
                context.user_name = self._chat_history.get_user_name(session_id)
        else:
            logger.warning(
                "[HISTORY] ⚠️ Chat history UNAVAILABLE — conversation recall will not work. "
                "Ensure PostgreSQL is running (docker compose up -d wiii-postgres)."
            )

        # 5. Analyze conversation for deep reasoning
        if self._conversation_analyzer and context.history_list:
            try:
                context.conversation_analysis = self._conversation_analyzer.analyze(context.history_list)
                logger.info("[CONTEXT ANALYZER] Question type: %s", context.conversation_analysis.question_type.value)
            except Exception as e:
                logger.warning("Failed to analyze conversation: %s", e)
        
        # Sprint 78: Budget-aware context building with auto-compaction
        # Keep semantic_context SEPARATE — do NOT merge into conversation_history
        from app.engine.conversation_window import ConversationWindowManager
        window_mgr = ConversationWindowManager()

        try:
            from app.engine.context_manager import get_compactor
            compactor = get_compactor()

            # Auto-compact if needed: summarize older messages, build budget-aware window
            running_summary, lc_messages, budget = await compactor.maybe_compact(
                session_id=str(session_id),
                history_list=context.history_list or [],
                system_prompt="",  # System prompt estimated at ~2000 tokens
                core_memory=context.core_memory_block or "",
                user_id=user_id,  # Sprint 79: enables DB persistence
            )

            context.langchain_messages = lc_messages
            if running_summary:
                context.conversation_summary = running_summary

            if budget:
                logger.info(
                    "[CONTEXT_MGR] Budget: %d/%d tokens (%.0f%%), %d msgs included, %d dropped%s",
                    budget.total_used, budget.total_budget, budget.utilization * 100,
                    budget.messages_included, budget.messages_dropped,
                    ", COMPACTED" if budget.has_summary else "",
                )
        except Exception as e:
            logger.warning("[CONTEXT_MGR] Budget manager unavailable, using fixed window: %s", e)
            context.langchain_messages = window_mgr.build_messages(context.history_list or [])

        context.conversation_history = window_mgr.format_for_prompt(context.history_list or [])
        # semantic_context stays in its own field — injected separately into system prompts

        # Sprint 115: Detect emotional state (feature-gated)
        if settings.enable_emotional_state:
            try:
                from app.engine.emotional_state import get_emotional_state_manager
                esm = get_emotional_state_manager()
                context.mood_hint = esm.detect_and_update(
                    user_id=user_id,
                    message=message,
                    decay_rate=settings.emotional_decay_rate,
                )
            except Exception as e:
                logger.debug("[EMOTIONAL] State detection failed: %s", e)

        # Sprint 79: Consolidated debug log (was 4 verbose logger.info lines)
        logger.debug(
            "[CONTEXT] user=%s name=%s history=%d semantic=%d",
            user_id, context.user_name or "?",
            len(context.conversation_history), len(context.semantic_context),
        )
        
        return context
    
    def extract_user_name(self, message: str) -> Optional[str]:
        """
        Extract user name from message.
        
        Enhanced patterns for Vietnamese and English:
        - "tên là X", "tên tôi là X", "mình tên là X"
        - "tôi là X", "em là X", "mình là X"
        - "tôi tên X", "em tên X"
        - "gọi tôi là X"
        - "I'm X", "my name is X", "call me X"
        
        **Validates: Requirements 2.1**
        """
        patterns = [
            # Vietnamese patterns
            r"tên (?:là|tôi là|mình là|em là)\s+(\w+)",
            r"mình tên là\s+(\w+)",
            r"(?:tôi|mình|em) là\s+(\w+)",
            r"(?:tôi|mình|em) tên\s+(\w+)",
            r"gọi (?:tôi|mình|em) là\s+(\w+)",
            r"tên\s+(\w+)",
            # English patterns
            r"(?:i'm|i am|my name is|call me)\s+(\w+)",
        ]
        
        # Common Vietnamese words that aren't names
        not_names = [
            "là", "tôi", "mình", "em", "anh", "chị", "bạn",
            "the", "a", "an", "gì", "đây", "này", "kia",
            "học", "sinh", "viên", "giáo", "sư"
        ]
        
        message_lower = message.lower()
        for pattern in patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                name = match.group(1).capitalize()
                if name.lower() not in not_names:
                    return name
        return None
    
    async def validate_pronoun_request(
        self,
        message: str,
        current_style: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Validate custom pronoun request with GuardianAgent.
        
        CHỈ THỊ SỐ 21: Custom pronoun validation
        
        Returns:
            Updated pronoun style if approved, None otherwise
        """
        if not self._guardian_agent:
            return None
        
        try:
            pronoun_result = await self._guardian_agent.validate_pronoun_request(message)
            if pronoun_result.approved:
                return {
                    "user_called": pronoun_result.user_called,
                    "ai_self": pronoun_result.ai_self
                }
        except Exception as e:
            logger.warning("Failed to validate pronoun request: %s", e)
        
        return None


# =============================================================================
# SINGLETON
# =============================================================================

_input_processor: Optional[InputProcessor] = None


def get_input_processor() -> InputProcessor:
    """Get or create InputProcessor singleton with GuardianAgent enabled."""
    global _input_processor
    if _input_processor is None:
        guardian = None
        try:
            from app.engine.guardian_agent import GuardianAgent
            guardian = GuardianAgent()
        except Exception as e:
            logger.warning("GuardianAgent init failed: %s", e)
        _input_processor = InputProcessor(guardian_agent=guardian)
    return _input_processor


def init_input_processor(
    guardian_agent=None,
    guardrails=None,
    semantic_memory=None,
    chat_history=None,
    learning_graph=None,
    memory_summarizer=None,
    conversation_analyzer=None
) -> InputProcessor:
    """Initialize InputProcessor with dependencies."""
    global _input_processor
    _input_processor = InputProcessor(
        guardian_agent=guardian_agent,
        guardrails=guardrails,
        semantic_memory=semantic_memory,
        chat_history=chat_history,
        learning_graph=learning_graph,
        memory_summarizer=memory_summarizer,
        conversation_analyzer=conversation_analyzer
    )
    return _input_processor
