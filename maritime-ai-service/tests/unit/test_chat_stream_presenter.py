import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_chat_stream_presenter():
    path = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "chat_stream_presenter.py"
    spec = spec_from_file_location("chat_stream_presenter_test", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_emit_blocked_sse_events_emits_answer_metadata_done():
    from types import SimpleNamespace

    presenter = _load_chat_stream_presenter()

    blocked_response = SimpleNamespace(
        message="Blocked message",
        metadata={"blocked": True},
    )

    chunks, counter = presenter.emit_blocked_sse_events(
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

    presenter = _load_chat_stream_presenter()

    event = SimpleNamespace(type="metadata", content={"processing_time": 1.5})

    chunks, counter, should_stop = presenter.serialize_stream_event(
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

    presenter = _load_chat_stream_presenter()

    event = SimpleNamespace(
        type="artifact",
        content={"artifact_id": "a1"},
        node="tutor_agent",
    )

    chunks, counter, should_stop = presenter.serialize_stream_event(
        event=event,
        event_counter=2,
        enable_artifacts=False,
    )

    assert chunks == []
    assert counter == 2
    assert should_stop is False


def test_serialize_stream_event_error_requests_stop():
    from types import SimpleNamespace

    presenter = _load_chat_stream_presenter()

    event = SimpleNamespace(type="error", content={"message": "boom"})

    chunks, counter, should_stop = presenter.serialize_stream_event(
        event=event,
        event_counter=7,
        enable_artifacts=True,
    )

    assert counter == 8
    assert should_stop is True
    assert "stream_error" in chunks[0]


def test_serialize_stream_event_visual_emits_sse_chunk():
    from types import SimpleNamespace

    presenter = _load_chat_stream_presenter()

    event = SimpleNamespace(
        type="visual",
        content={
            "id": "visual-1",
            "visual_session_id": "vs-1",
            "type": "comparison",
            "runtime": "svg",
            "title": "A vs B",
            "summary": "Quick compare",
            "spec": {"left": {"title": "A"}, "right": {"title": "B"}},
        },
        node="direct",
    )

    chunks, counter, should_stop = presenter.serialize_stream_event(
        event=event,
        event_counter=1,
        enable_artifacts=False,
    )

    assert should_stop is False
    assert counter == 2
    assert len(chunks) == 1
    assert "event: visual" in chunks[0]
    data_line = next(
        line for line in chunks[0].split("\n") if line.startswith("data: ")
    )
    payload = json.loads(data_line[6:])
    assert payload["display_role"] == "artifact"
    assert payload["presentation"] == "compact"


def test_serialize_stream_event_visual_lifecycle_chunks():
    from types import SimpleNamespace

    presenter = _load_chat_stream_presenter()

    events = [
        SimpleNamespace(
            type="visual_open",
            content={
                "id": "visual-2",
                "visual_session_id": "vs-2",
                "type": "process",
                "runtime": "svg",
                "title": "Pipeline",
                "summary": "Quick process",
                "spec": {"steps": [{"title": "Start"}, {"title": "End"}]},
            },
            node="direct",
        ),
        SimpleNamespace(
            type="visual_commit",
            content={"visual_session_id": "vs-2", "status": "committed"},
            node="direct",
        ),
        SimpleNamespace(
            type="visual_dispose",
            content={"visual_session_id": "vs-2", "status": "disposed", "reason": "reset"},
            node="direct",
        ),
    ]

    counter = 2
    emitted = []
    for event in events:
        chunks, counter, should_stop = presenter.serialize_stream_event(
            event=event,
            event_counter=counter,
            enable_artifacts=False,
        )
        assert should_stop is False
        emitted.extend(chunks)

    assert any("event: visual_open" in chunk for chunk in emitted)
    assert any("event: visual_commit" in chunk for chunk in emitted)
    assert any("event: visual_dispose" in chunk for chunk in emitted)


def test_serialize_stream_event_code_studio_chunks():
    from types import SimpleNamespace

    presenter = _load_chat_stream_presenter()

    events = [
        SimpleNamespace(
            type="code_open",
            content={
                "session_id": "vs-code-1",
                "title": "Pendulum App",
                "language": "html",
                "version": 1,
                "studio_lane": "app",
                "artifact_kind": "html_app",
            },
            node="code_studio_agent",
        ),
        SimpleNamespace(
            type="code_delta",
            content={
                "session_id": "vs-code-1",
                "chunk": "<div>",
                "chunk_index": 0,
                "total_bytes": 1024,
            },
            node="code_studio_agent",
        ),
        SimpleNamespace(
            type="code_complete",
            content={
                "session_id": "vs-code-1",
                "full_code": "<div>done</div>",
                "language": "html",
                "version": 1,
            },
            node="code_studio_agent",
        ),
    ]

    counter = 0
    emitted = []
    for event in events:
        chunks, counter, should_stop = presenter.serialize_stream_event(
            event=event,
            event_counter=counter,
            enable_artifacts=True,
        )
        assert should_stop is False
        emitted.extend(chunks)

    assert any("event: code_open" in chunk for chunk in emitted)
    assert any("event: code_delta" in chunk for chunk in emitted)
    assert any("event: code_complete" in chunk for chunk in emitted)

    code_open_data = next(chunk for chunk in emitted if "event: code_open" in chunk)
    data_line = next(line for line in code_open_data.split("\n") if line.startswith("data: "))
    payload = json.loads(data_line[6:])
    assert payload["display_role"] == "artifact"
    assert payload["presentation"] == "compact"


def test_emit_internal_error_sse_events_can_include_done():
    presenter = _load_chat_stream_presenter()

    chunks, counter = presenter.emit_internal_error_sse_events(
        processing_time=1.25,
        event_counter=3,
    )

    assert counter == 5
    assert "event: error" in chunks[0]
    assert "Internal processing error" in chunks[0]
    assert "event: done" in chunks[1]


def test_emit_internal_error_sse_events_supports_single_error_chunk():
    presenter = _load_chat_stream_presenter()

    chunks, counter = presenter.emit_internal_error_sse_events()

    assert counter is None
    assert len(chunks) == 1
    assert "event: error" in chunks[0]
