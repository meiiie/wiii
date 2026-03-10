"""Shared response-construction helpers for chat API endpoints."""

from fastapi.responses import JSONResponse, StreamingResponse


def build_json_response(*, status_code: int, content: dict) -> JSONResponse:
    """Build a JSONResponse with the provided status code and payload."""
    return JSONResponse(
        status_code=status_code,
        content=content,
    )


def build_sse_streaming_response(*, event_generator) -> StreamingResponse:
    """Build the standard SSE response shared by chat stream endpoints."""
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
