"""Transport helpers for the sync chat API endpoint."""

import time

from fastapi import status
from fastapi.responses import JSONResponse

from app.api.v1.chat_api_response_support import build_json_response
from app.core.exceptions import ProviderUnavailableError, WiiiException
from app.models.schemas import (
    ChatResponse,
    DeleteHistoryResponse,
    GetHistoryResponse,
    HistoryMessage,
    HistoryPagination,
)
from app.services.chat_response_presenter import build_chat_response
from app.services.llm_runtime_audit_service import (
    infer_runtime_completion_degraded_reason,
    record_llm_runtime_observation,
)
from app.services.model_switch_prompt_service import (
    build_model_switch_prompt_for_unavailable,
)


def log_chat_completion_request(
    *,
    logger,
    chat_request,
    auth_method: str,
) -> None:
    """Log the incoming sync chat request in one consistent format."""
    logger.info(
        "Chat request from user %s (role: %s, auth: %s): %s...",
        chat_request.user_id,
        chat_request.role.value,
        auth_method,
        chat_request.message[:50],
    )


def log_chat_completion_response(
    *,
    logger,
    response,
    internal_response,
    processing_time: float,
) -> None:
    """Log the sync chat response metadata in one consistent format."""
    if response.metadata.reasoning_trace:
        logger.info(
            "[REASONING_TRACE] Included %d steps in response",
            response.metadata.reasoning_trace.total_steps,
        )
    if response.metadata.thinking:
        logger.info(
            "[THINKING] Included %d chars natural thinking",
            len(response.metadata.thinking),
        )

    logger.info(
        "Chat response generated in %.3fs (agent: %s)",
        processing_time,
        internal_response.agent_type.value,
    )


def build_chat_completion_success_response(
    *,
    logger,
    chat_request,
    internal_response,
    start_time: float,
    provider_name: str | None,
    model_name: str | None,
    runtime_authoritative: bool = True,
) -> ChatResponse:
    """Build and log the successful /chat response."""
    processing_time = time.time() - start_time
    metadata = internal_response.metadata or {}
    try:
        record_llm_runtime_observation(
            provider=provider_name,
            success=True,
            model_name=model_name,
            note=None,
            source="chat_sync",
            failover=metadata.get("failover"),
            degraded_reason=infer_runtime_completion_degraded_reason(metadata),
        )
    except Exception as exc:
        logger.debug("Could not record sync LLM runtime observation: %s", exc)
    response = build_chat_response(
        chat_request=chat_request,
        internal_response=internal_response,
        processing_time=processing_time,
        provider_name=provider_name,
        model_name=model_name,
        runtime_authoritative=runtime_authoritative,
    )

    log_chat_completion_response(
        logger=logger,
        response=response,
        internal_response=internal_response,
        processing_time=processing_time,
    )
    return response


def build_chat_service_error_response(
    *,
    error_code: str,
    message: str,
    http_status: int,
    request_id: str | None,
    extra: dict | None = None,
) -> JSONResponse:
    """Build the handled WiiiException response payload for /chat."""
    payload = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }
    if extra:
        payload.update(extra)
    return build_json_response(
        status_code=http_status,
        content=payload,
    )


def build_chat_internal_error_response(
    *,
    request_id: str | None,
) -> JSONResponse:
    """Build the generic internal-error response payload for /chat."""
    return build_json_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


def build_chat_completion_error_response(
    *,
    logger,
    error: Exception,
    request_id: str | None,
) -> JSONResponse:
    """Map /chat execution errors to the standard error payloads."""
    if isinstance(error, WiiiException):
        logger.error(
            "Chat service error [%s]: %s",
            error.error_code,
            error.message,
        )
        extra: dict | None = None
        if isinstance(error, ProviderUnavailableError):
            try:
                record_llm_runtime_observation(
                    provider=error.provider,
                    success=False,
                    error=error.message,
                    note=(
                        f"chat_sync:error: requested provider {error.provider} unavailable"
                        f"{f' ({error.reason_code})' if error.reason_code else ''}."
                    ),
                    source="chat_sync:error",
                )
            except Exception as exc:
                logger.debug("Could not record sync LLM runtime failure: %s", exc)
            extra = {
                "provider": error.provider,
                "reason_code": error.reason_code,
                "model_switch_prompt": build_model_switch_prompt_for_unavailable(
                    provider=error.provider,
                    reason_code=error.reason_code,
                ),
            }
        return build_chat_service_error_response(
            error_code=error.error_code,
            message=error.message,
            http_status=error.http_status,
            request_id=request_id,
            extra=extra,
        )

    logger.exception("Unexpected error processing chat request: %s", error)
    return build_chat_internal_error_response(request_id=request_id)


def build_chat_api_error_response(
    *,
    status_code: int,
    error: str,
    message: str,
) -> JSONResponse:
    """Build the standard simple error payload used by chat sub-endpoints."""
    return build_json_response(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
        },
    )


def build_logged_chat_api_error_response(
    *,
    logger,
    operation_label: str,
    error,
    error_code: str,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> JSONResponse:
    """Log an endpoint failure and build the standard simple error payload."""
    logger.exception("Error %s: %s", operation_label, error)
    return build_chat_api_error_response(
        status_code=status_code,
        error=error_code,
        message=message,
    )


def build_missing_session_response() -> JSONResponse:
    """Build the standard missing-session response for context endpoints."""
    return build_chat_api_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error="missing_session",
        message="X-Session-ID header required",
    )


def normalize_history_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Clamp history pagination inputs to the endpoint contract."""
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 20
    if offset < 0:
        offset = 0
    return limit, offset


def build_get_chat_history_response(
    *,
    messages,
    total: int,
    limit: int,
    offset: int,
) -> GetHistoryResponse:
    """Build the standard paginated history response."""
    history_messages = [
        HistoryMessage(
            role=msg.role,
            content=msg.content,
            timestamp=msg.created_at,
        )
        for msg in messages
    ]

    return GetHistoryResponse(
        data=history_messages,
        pagination=HistoryPagination(
            total=total,
            limit=limit,
            offset=offset,
        ),
    )


def build_delete_chat_history_response(
    *,
    user_id: str,
    deleted_count: int,
    deleted_by: str,
) -> DeleteHistoryResponse:
    """Build the standard delete-history success response."""
    return DeleteHistoryResponse(
        status="deleted",
        user_id=user_id,
        messages_deleted=deleted_count,
        deleted_by=deleted_by,
    )


def log_get_chat_history_response(
    *,
    logger,
    message_count: int,
    user_id: str,
    total: int,
) -> None:
    """Log the get-history response in one consistent format."""
    logger.info(
        "Retrieved %d messages for user %s (total: %d)",
        message_count,
        user_id,
        total,
    )


def log_delete_chat_history_response(
    *,
    logger,
    deleted_count: int,
    user_id: str,
    deleted_by: str,
    role: str,
) -> None:
    """Log the delete-history response in one consistent format."""
    logger.info(
        "Deleted %d chat messages for user %s by %s (%s)",
        deleted_count,
        user_id,
        deleted_by,
        role,
    )
