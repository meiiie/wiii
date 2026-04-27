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
- Multi-Agent System (Phase 8, SOTA 2025) - WiiiRunner Supervisor
- Semantic Memory Engine v0.5 (pgvector + Gemini embeddings)
- Knowledge Graph (Neo4j GraphRAG)
- Guardrails / Guardian Agent
- Learning Profile
- Chat History

Authoritative request flow:
see app/services/REQUEST_FLOW_CONTRACT.md

**Feature: wiii**
**Validates: Requirements 1.1, 2.1, 2.2, 2.3**
"""

import logging
from typing import Callable, Optional

from app.core.config import settings
from app.models.schemas import ChatRequest, InternalChatResponse
from .chat_service_runtime import initialize_chat_service_runtime_impl

logger = logging.getLogger(__name__)


class ChatService:
    """
    Main service that integrates all components.

    REFACTORED: Now acts as a thin facade, delegating to specialized services.

    **Pattern:** Facade Pattern
    **Validates: Requirements 1.1, 2.1, 2.2, 2.3**

    Contract note:
    This facade should stay thin. Stage ordering and mutation rights are
    defined in REQUEST_FLOW_CONTRACT.md, not here.
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
        initialize_chat_service_runtime_impl(
            service=self,
            settings_obj=settings,
            logger=logger,
        )
    
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


def reset_chat_service() -> None:
    """Clear the ChatService singleton so the next request rebuilds runtime state."""
    global _chat_service
    _chat_service = None


# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================

# Re-export for backward compatibility with existing code
__all__ = [
    'ChatService',
    'get_chat_service',
    'reset_chat_service',
    'AgentType',
    'ProcessingResult',
    'SessionState',
    'SessionContext',
]


def __getattr__(name: str):
    if name == "AgentType":
        from .chat_orchestrator import AgentType

        return AgentType
    if name in {"SessionState", "SessionContext"}:
        from .session_manager import SessionContext, SessionState

        return {
            "SessionState": SessionState,
            "SessionContext": SessionContext,
        }[name]
    if name == "ProcessingResult":
        from .output_processor import ProcessingResult

        return ProcessingResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
