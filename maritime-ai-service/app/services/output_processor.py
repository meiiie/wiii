"""Output processor compatibility facade."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.schemas import InternalChatResponse, Source, UserRole
from app.services.output_response_runtime import (
    create_blocked_response as _create_blocked_response,
)
from app.services.output_response_runtime import (
    create_clarification_response as _create_clarification_response,
)
from app.services.output_response_runtime import validate_and_format as _validate_and_format
from app.services.output_source_runtime import (
    coerce_source_mapping as _coerce_source_mapping,
)
from app.services.output_source_runtime import format_sources as _format_sources
from app.services.output_source_runtime import (
    merge_same_page_sources as _merge_same_page_sources,
)
from app.services.output_thinking_runtime import (
    extract_thinking_from_response as _extract_thinking_from_response,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a chat request."""

    message: str
    agent_type: Any
    sources: Optional[List[Source]] = None
    blocked: bool = False
    metadata: dict = None
    thinking: Optional[str] = None


def extract_thinking_from_response(content: Any) -> tuple[str, Optional[str]]:
    """Backward-compatible wrapper for centralized thinking extraction."""
    return _extract_thinking_from_response(content)


class OutputProcessor:
    """Facade for response validation, source formatting, and metadata shaping."""

    def __init__(self, guardrails=None, response_builder=None):
        self._guardrails = guardrails
        self._response_builder = response_builder
        logger.info("OutputProcessor initialized")

    async def validate_and_format(
        self,
        result: ProcessingResult,
        session_id: UUID,
        user_name: Optional[str] = None,
        user_role: UserRole = UserRole.STUDENT,
    ) -> InternalChatResponse:
        return await _validate_and_format(
            guardrails=self._guardrails,
            logger=logger,
            result=result,
            session_id=session_id,
            user_name=user_name,
            user_role=user_role,
        )

    def merge_same_page_sources(self, sources: List[Any]) -> List[Dict[str, Any]]:
        return _merge_same_page_sources(sources, response_builder=self._response_builder)

    @staticmethod
    def _coerce_source_mapping(source: Any) -> Dict[str, Any]:
        return _coerce_source_mapping(source)

    def format_sources(self, raw_sources: List[Any]) -> List[Source]:
        return _format_sources(raw_sources, response_builder=self._response_builder)

    def create_blocked_response(
        self,
        issues: List[str],
        refusal_message: Optional[str] = None,
    ) -> InternalChatResponse:
        return _create_blocked_response(
            guardrails=self._guardrails,
            issues=issues,
            refusal_message=refusal_message,
        )

    def create_clarification_response(self, content: str) -> InternalChatResponse:
        return _create_clarification_response(content)


_output_processor: Optional[OutputProcessor] = None


def get_output_processor() -> OutputProcessor:
    """Get or create OutputProcessor singleton."""
    global _output_processor
    if _output_processor is None:
        _output_processor = OutputProcessor()
    return _output_processor


def init_output_processor(
    guardrails=None,
    response_builder=None,
) -> OutputProcessor:
    """Initialize OutputProcessor with dependencies."""
    global _output_processor
    _output_processor = OutputProcessor(
        guardrails=guardrails,
        response_builder=response_builder,
    )
    return _output_processor
