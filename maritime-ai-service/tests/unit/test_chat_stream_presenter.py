import json


def test_emit_blocked_sse_events_emits_answer_metadata_done():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_presenter import emit_blocked_sse_events

    blocked_response = SimpleNamespace(
        message="Blocked message",
        metadata={"blocked": True},
    )

    chunks, counter = emit_blocked_sse_events(
        blocked_response=blocked_response,
        session_id="session-1",
        processing_time=0.25,
        event_counter=0,
    )

    assert counter == 3
    assert "event: answer" in chunks[0]
    assert "event: metadata" in chunks[1]
    assert "session-1" in chunks[1]
    assert "event: done" in chunks[2]


def test_serialize_stream_event_metadata_adds_streaming_version():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_presenter import serialize_stream_event

    event = SimpleNamespace(type="metadata", content={"processing_time": 1.5})

    chunks, counter, should_stop = serialize_stream_event(
        event=event,
        event_counter=4,
        enable_artifacts=True,
    )

    assert counter == 5
    assert should_stop is False
    data_line = next(
        line for line in chunks[0].split("\n") if line.startswith("data: ")
    )
    payload = json.loads(data_line[6:])
    assert payload["streaming_version"] == "v3-graph"


def test_serialize_stream_event_skips_artifact_when_disabled():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_presenter import serialize_stream_event

    event = SimpleNamespace(
        type="artifact",
        content={"artifact_id": "a1"},
        node="tutor_agent",
    )

    chunks, counter, should_stop = serialize_stream_event(
        event=event,
        event_counter=2,
        enable_artifacts=False,
    )

    assert chunks == []
    assert counter == 2
    assert should_stop is False


def test_serialize_stream_event_error_requests_stop():
    from types import SimpleNamespace

    from app.api.v1.chat_stream_presenter import serialize_stream_event

    event = SimpleNamespace(type="error", content={"message": "boom"})

    chunks, counter, should_stop = serialize_stream_event(
        event=event,
        event_counter=7,
        enable_artifacts=True,
    )

    assert counter == 8
    assert should_stop is True
    assert "stream_error" in chunks[0]


def test_emit_internal_error_sse_events_can_include_done():
    from app.api.v1.chat_stream_presenter import emit_internal_error_sse_events

    chunks, counter = emit_internal_error_sse_events(
        processing_time=1.25,
        event_counter=3,
    )

    assert counter == 5
    assert "event: error" in chunks[0]
    assert "Internal processing error" in chunks[0]
    assert "event: done" in chunks[1]


def test_emit_internal_error_sse_events_supports_single_error_chunk():
    from app.api.v1.chat_stream_presenter import emit_internal_error_sse_events

    chunks, counter = emit_internal_error_sse_events()

    assert counter is None
    assert len(chunks) == 1
    assert "event: error" in chunks[0]
