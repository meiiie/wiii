from unittest.mock import MagicMock, patch


def test_log_chat_stream_request_uses_standard_prefix():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_endpoint_support import log_chat_stream_request

    logger = MagicMock()
    chat_request = SimpleNamespace(user_id="user-1", message="Hello world")

    log_chat_stream_request(logger=logger, chat_request=chat_request)

    logger.info.assert_called_once()
    assert (
        "[STREAM-V3] Request from %s: %s..."
        in logger.info.call_args.args[0]
    )


def test_log_chat_stream_reconnect_logs_only_when_present():
    from app.api.v1.chat_stream_endpoint_support import (
        log_chat_stream_reconnect,
    )

    logger = MagicMock()

    log_chat_stream_reconnect(logger=logger, last_event_id=None)
    logger.info.assert_not_called()

    log_chat_stream_reconnect(logger=logger, last_event_id="42")
    logger.info.assert_called_once()


def test_begin_chat_stream_request_logs_and_returns_start_time():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_endpoint_support import begin_chat_stream_request

    logger = MagicMock()
    request = SimpleNamespace(headers={"last-event-id": "99"})
    chat_request = SimpleNamespace(user_id="user-1", message="Hello world")

    with patch(
        "app.api.v1.chat_stream_endpoint_support.time.time",
        return_value=123.0,
    ):
        start_time = begin_chat_stream_request(
            logger=logger,
            request=request,
            chat_request=chat_request,
        )

    assert start_time == 123.0
    assert logger.info.call_count == 2


def test_build_chat_streaming_response_uses_standard_headers():
    from app.api.v1.chat_stream_endpoint_support import (
        build_chat_streaming_response,
    )

    async def empty_gen():
        if False:
            yield "noop"

    response = build_chat_streaming_response(event_generator=empty_gen())

    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Connection"] == "keep-alive"
    assert response.headers["X-Accel-Buffering"] == "no"
