"""Transport helpers for the streaming chat endpoint."""

import time

from fastapi.responses import StreamingResponse

from app.api.v1.chat_api_response_support import build_sse_streaming_response

__all__ = [
    "log_chat_stream_request",
    "log_chat_stream_reconnect",
    "begin_chat_stream_request",
    "build_chat_streaming_response",
]


def log_chat_stream_request(*, logger, chat_request) -> None:
    """Log the incoming streaming request in one consistent format."""
    logger.info(
        "[STREAM-V3] Request from %s: %s...",
        chat_request.user_id,
        chat_request.message[:50],
    )


def log_chat_stream_reconnect(*, logger, last_event_id: str | None) -> None:
    """Log browser reconnect attempts when Last-Event-ID is present."""
    if last_event_id:
        logger.info(
            "[STREAM-V3] Reconnect with Last-Event-ID: %s",
            last_event_id,
        )


def begin_chat_stream_request(*, logger, request, chat_request) -> float:
    """Capture stream route timing and emit the standard request logs."""
    start_time = time.time()
    log_chat_stream_request(
        logger=logger,
        chat_request=chat_request,
    )
    log_chat_stream_reconnect(
        logger=logger,
        last_event_id=request.headers.get("last-event-id"),
    )
    return start_time


def build_chat_streaming_response(*, event_generator) -> StreamingResponse:
    """Build the standard SSE StreamingResponse for /chat/stream/v3."""
    return build_sse_streaming_response(
        event_generator=event_generator,
    )
