"""
Chat Service - Integration layer for all components.

REFACTORED: This file is now a thin facade that delegates to:
- ChatOrchestrator: Pipeline orchestration
- SessionManager: Session and state management
- InputProcessor: Validation and context building
- OutputProcessor: Response formatting
- BackgroundTaskRunner: Async task management

**Pattern:** Facade Pattern (Gang of Four)
**Spec:** CHỈ THỊ KỸ THUẬT SỐ 25 - Project Restructure

This service wires together:
- Multi-Agent System (Phase 8, SOTA 2025) - LangGraph Supervisor
- Semantic Memory Engine v0.5 (pgvector + Gemini embeddings)
- Knowledge Graph (Neo4j GraphRAG)
- Guardrails / Guardian Agent
- Learning Profile
- Chat History

**Feature: wiii**
**Validates: Requirements 1.1, 2.1, 2.2, 2.3**
"""

import logging
from typing import Callable, Optional

from app.core.config import settings
from app.models.schemas import ChatRequest, InternalChatResponse

# Orchestrator and processors
from .chat_orchestrator import (
    get_chat_orchestrator,
    init_chat_orchestrator,
    AgentType  # Re-export for backward compatibility
)
from .session_manager import (
    SessionState,
    SessionContext
)
from .input_processor import (
    init_input_processor
)
from .output_processor import (
    ProcessingResult,
    init_output_processor
)
from .background_tasks import (
    init_background_runner
)

# Engine imports for initialization
from app.engine.guardrails import Guardrails
from app.engine.agentic_rag.rag_agent import RAGAgent, get_knowledge_repository
from app.repositories.user_graph_repository import get_user_graph_repository
from app.services.learning_graph_service import get_learning_graph_service
from app.services.chat_response_builder import get_chat_response_builder
from app.repositories.learning_profile_repository import get_learning_profile_repository
from app.repositories.chat_history_repository import get_chat_history_repository

# Optional imports with fallbacks
try:
    from app.engine.semantic_memory import get_semantic_memory_engine
    SEMANTIC_MEMORY_AVAILABLE = True
except ImportError:
    SEMANTIC_MEMORY_AVAILABLE = False


try:
    from app.prompts import get_prompt_loader
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False
    def get_prompt_loader():
        return None

try:
    from app.engine.memory_summarizer import get_memory_summarizer
    MEMORY_SUMMARIZER_AVAILABLE = True
except ImportError:
    MEMORY_SUMMARIZER_AVAILABLE = False
    def get_memory_summarizer():
        return None

try:
    from app.engine.guardian_agent import get_guardian_agent
    GUARDIAN_AGENT_AVAILABLE = True
except ImportError:
    GUARDIAN_AGENT_AVAILABLE = False
    def get_guardian_agent(fallback_guardrails=None):
        return None

try:
    from app.engine.conversation_analyzer import get_conversation_analyzer
    CONVERSATION_ANALYZER_AVAILABLE = True
except ImportError:
    CONVERSATION_ANALYZER_AVAILABLE = False
    def get_conversation_analyzer():
        return None

from app.engine.multi_agent.graph import get_multi_agent_graph

logger = logging.getLogger(__name__)


class ChatService:
    """
    Main service that integrates all components.

    REFACTORED: Now acts as a thin facade, delegating to specialized services.

    **Pattern:** Facade Pattern
    **Validates: Requirements 1.1, 2.1, 2.2, 2.3**
    """

    @staticmethod
    def _init_optional(name: str, available: bool, factory, check_available: bool = False, **kwargs):
        """Initialize an optional component with error handling."""
        if not available:
            return None
        try:
            instance = factory(**kwargs) if kwargs else factory()
            if check_available and hasattr(instance, 'is_available') and not instance.is_available():
                return None
            logger.info("[OK] %s initialized", name)
            return instance
        except Exception as e:
            logger.warning("Failed to initialize %s: %s", name, e)
            return None

    def __init__(self):
        """Initialize all components and wire up dependencies."""
        logger.info("Initializing ChatService (Facade Pattern)...")

        # ================================================================
        # CORE REPOSITORIES
        # ================================================================
        self._knowledge_graph = get_knowledge_repository()
        self._user_graph = get_user_graph_repository()
        self._learning_graph = get_learning_graph_service()
        self._pg_profile_repo = get_learning_profile_repository()
        self._chat_history = get_chat_history_repository()
        self._guardrails = Guardrails()

        if self._chat_history.is_available():
            self._chat_history.ensure_tables()
            logger.info("Chat History initialized")

        # ================================================================
        # ENGINE COMPONENTS (optional, graceful degradation)
        # ================================================================
        self._rag_agent = RAGAgent(knowledge_graph=self._knowledge_graph)

        self._semantic_memory = self._init_optional(
            "Semantic Memory v0.5",
            SEMANTIC_MEMORY_AVAILABLE and settings.semantic_memory_enabled,
            get_semantic_memory_engine, check_available=True
        )
        self._multi_agent_graph = self._init_optional(
            "Multi-Agent System",
            getattr(settings, 'use_multi_agent', True),
            get_multi_agent_graph
        )
        self._guardian_agent = self._init_optional(
            "Guardian Agent",
            GUARDIAN_AGENT_AVAILABLE,
            get_guardian_agent, check_available=True,
            fallback_guardrails=self._guardrails
        )
        self._conversation_analyzer = self._init_optional(
            "Conversation Analyzer",
            CONVERSATION_ANALYZER_AVAILABLE,
            get_conversation_analyzer
        )
        self._memory_summarizer = self._init_optional(
            "Memory Summarizer",
            MEMORY_SUMMARIZER_AVAILABLE,
            get_memory_summarizer, check_available=True
        )
        self._prompt_loader = self._init_optional(
            "Prompt Loader",
            PROMPT_LOADER_AVAILABLE,
            get_prompt_loader
        )

        self._response_builder = get_chat_response_builder()
        
        # ================================================================
        # INITIALIZE PROCESSORS WITH DEPENDENCIES
        # ================================================================
        
        # Initialize InputProcessor
        init_input_processor(
            guardian_agent=self._guardian_agent,
            guardrails=self._guardrails,
            semantic_memory=self._semantic_memory,
            chat_history=self._chat_history,
            learning_graph=self._learning_graph,
            memory_summarizer=self._memory_summarizer,
            conversation_analyzer=self._conversation_analyzer
        )
        
        # Initialize OutputProcessor
        init_output_processor(
            guardrails=self._guardrails,
            response_builder=self._response_builder
        )
        
        # Initialize BackgroundTaskRunner
        init_background_runner(
            chat_history=self._chat_history,
            semantic_memory=self._semantic_memory,
            memory_summarizer=self._memory_summarizer,
            profile_repo=self._pg_profile_repo
        )
        
        # Initialize ChatOrchestrator
        init_chat_orchestrator(
            multi_agent_graph=self._multi_agent_graph,
            rag_agent=self._rag_agent,
            semantic_memory=self._semantic_memory,
            chat_history=self._chat_history,
            prompt_loader=self._prompt_loader,
            guardrails=self._guardrails
        )
        
        # Initialize Tool Registry with dependencies
        # CRITICAL: Without this, tool_maritime_search cannot access RAG Agent!
        from app.engine.tools import init_all_tools
        init_all_tools(
            rag_agent=self._rag_agent,
            semantic_memory=self._semantic_memory
        )
        logger.info("[OK] Tool Registry initialized (RAG, Memory tools)")
        
        # Get the orchestrator
        self._orchestrator = get_chat_orchestrator()
        
        # Log availability status
        logger.info("Knowledge graph available: %s", self._knowledge_graph.is_available())
        logger.info("Chat history available: %s", self._chat_history.is_available())
        logger.info("Semantic memory available: %s", self._semantic_memory is not None)
        logger.info("Multi-Agent available: %s", self._multi_agent_graph is not None)
        
        logger.info("ChatService initialized (Facade Pattern) [OK]")
    
    async def process_message(
        self,
        request: ChatRequest,
        background_save: Optional[Callable] = None
    ) -> InternalChatResponse:
        """
        Process a chat message through the full pipeline.
        
        Delegates to ChatOrchestrator for actual processing.
        
        Args:
            request: ChatRequest from API
            background_save: FastAPI BackgroundTasks.add_task
            
        Returns:
            InternalChatResponse ready for API serialization
        """
        return await self._orchestrator.process(request, background_save)


# =============================================================================
# SINGLETON
# =============================================================================

_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create ChatService singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================

# Re-export for backward compatibility with existing code
__all__ = [
    'ChatService',
    'get_chat_service',
    'AgentType',
    'ProcessingResult',
    'SessionState',
    'SessionContext',
]
