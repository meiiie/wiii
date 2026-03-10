"""Support helpers for the sync /chat endpoint."""

import time

from app.api.v1 import chat_endpoint_presenter as _chat_endpoint_presenter

__all__ = [
    "begin_chat_completion_request",
    "process_chat_completion_request",
]


def begin_chat_completion_request(*, logger, request, chat_request, auth_method):
    """Capture sync route request metadata and emit the standard request log."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID")
    _chat_endpoint_presenter.log_chat_completion_request(
        logger=logger,
        chat_request=chat_request,
        auth_method=auth_method,
    )
    return start_time, request_id


async def process_chat_completion_request(*, chat_request, background_save):
    """Run the authoritative sync chat service for the /chat endpoint."""
    from app.services.chat_service import get_chat_service

    chat_service = get_chat_service()
    return await chat_service.process_message(
        chat_request,
        background_save=background_save,
    )
