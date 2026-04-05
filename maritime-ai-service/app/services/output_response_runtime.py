"""Response-building helpers for the output processor facade."""

from enum import Enum
from logging import Logger
from typing import Optional
from uuid import UUID, uuid4

from app.models.schemas import InternalChatResponse, UserRole


class _ChatAgentType(str, Enum):
    CHAT = "chat"


async def validate_and_format(
    *,
    guardrails,
    logger: Logger,
    result,
    session_id: UUID,
    user_name: Optional[str] = None,
    user_role: UserRole = UserRole.STUDENT,
) -> InternalChatResponse:
    """Validate a processor result and convert it into InternalChatResponse."""
    message = result.message

    if guardrails:
        from app.engine.guardrails import ValidationStatus

        output_result = await guardrails.validate_output(message)
        if output_result.status == ValidationStatus.FLAGGED:
            message += "\n\n_Note: Please verify safety-critical information with official sources._"

    response_metadata = {
        "session_id": str(session_id),
        "user_name": user_name,
        "user_role": user_role.value,
        **(result.metadata or {}),
    }

    if result.thinking:
        response_metadata["thinking"] = result.thinking
        logger.info("[THINKING] Included %d chars of reasoning in response", len(result.thinking))

    return InternalChatResponse(
        response_id=uuid4(),
        message=message,
        agent_type=result.agent_type,
        sources=result.sources,
        metadata=response_metadata,
    )


def create_blocked_response(
    *,
    guardrails,
    issues,
    refusal_message: Optional[str] = None,
) -> InternalChatResponse:
    """Create a blocked response payload."""
    message = refusal_message or "Xin lỗi, mình không thể xử lý yêu cầu này nha~ (˶˃ ᵕ ˂˶)"
    if guardrails:
        message = guardrails.get_refusal_message()

    return InternalChatResponse(
        response_id=uuid4(),
        message=message,
        agent_type=_ChatAgentType.CHAT,
        metadata={"blocked": True, "issues": issues},
    )


def create_clarification_response(content: str) -> InternalChatResponse:
    """Create a response asking the user to clarify their request."""
    return InternalChatResponse(
        response_id=uuid4(),
        message=content,
        agent_type=_ChatAgentType.CHAT,
        metadata={"requires_clarification": True},
    )
