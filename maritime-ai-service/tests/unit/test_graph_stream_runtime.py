from types import SimpleNamespace

import pytest

from app.engine.multi_agent.graph_stream_runtime import (
    build_stream_bootstrap_impl,
    emit_stream_finalization_impl,
)
from app.engine.reasoning import capture_thinking_lifecycle_event
from app.engine.multi_agent.stream_utils import (
    create_done_event,
    create_metadata_event,
    create_sources_event,
)


class _RegistryStub:
    def end_request_trace(self, trace_id: str):
        return {"trace_id": trace_id, "span_count": 0}


@pytest.mark.asyncio
async def test_build_stream_bootstrap_matches_sync_context_injection(monkeypatch):
    import app.engine.multi_agent.graph as graph_module

    def _inject_host_context(state):
        state["host_capabilities_prompt"] = "HOST CAPS"
        return "HOST PROMPT"

    monkeypatch.setattr(graph_module, "_inject_host_context", _inject_host_context)
    monkeypatch.setattr(graph_module, "_inject_host_session", lambda _state: "HOST SESSION")
    monkeypatch.setattr(graph_module, "_inject_operator_context", lambda _state: "OPERATOR PROMPT")
    monkeypatch.setattr(graph_module, "_inject_living_context", lambda _state: "LIVING PROMPT")
    monkeypatch.setattr(graph_module, "_inject_visual_context", lambda _state: "")
    monkeypatch.setattr(graph_module, "_inject_visual_cognition_context", lambda _state: "")
    monkeypatch.setattr(graph_module, "_inject_widget_feedback_context", lambda _state: "")
    monkeypatch.setattr(graph_module, "_inject_code_studio_context", lambda _state: "")

    bootstrap = await build_stream_bootstrap_impl(
        query="hello",
        user_id="user-1",
        session_id="session-1",
        context={"organization_id": "org-1"},
        domain_id="maritime",
        thinking_effort="medium",
        provider="google",
        settings_obj=SimpleNamespace(enable_preview=False, enable_soul_emotion=False),
        register_event_queue=lambda *_args, **_kwargs: None,
        cleanup_stale_queues=lambda: None,
        build_domain_config=lambda _domain_id: {},
        build_turn_local_state_defaults=lambda _context: {},
    )

    initial_state = bootstrap["initial_state"]
    assert initial_state["host_context_prompt"] == "HOST PROMPT"
    assert initial_state["host_capabilities_prompt"] == "HOST CAPS"
    assert initial_state["host_session_prompt"] == "HOST SESSION"
    assert initial_state["operator_context_prompt"] == "OPERATOR PROMPT"
    assert initial_state["living_context_prompt"] == "LIVING PROMPT"


@pytest.mark.asyncio
async def test_emit_stream_finalization_prefers_public_thinking_fragments():
    final_state = {
        "session_id": "session-1",
        "grader_score": 8.0,
        "thinking": "native private thinking",
        "thinking_content": "Nhịp này không cần kéo dài quá tay.",
        "_public_thinking_fragments": [
            "Mình đang gom các biến số thị trường quan trọng trước.",
            "Sau đó mình đối chiếu cung cầu với yếu tố địa chính trị để tránh nhận định bề mặt.",
        ],
        "routing_metadata": {"final_agent": "direct"},
    }

    events = [
        event
        async for event in emit_stream_finalization_impl(
            final_state=final_state,
            session_id="session-1",
            context={"user_id": "user-1"},
            start_time=0.0,
            resolve_runtime_llm_metadata=lambda *_args, **_kwargs: {
                "provider": "google",
                "model": "gemini-3.1-flash-lite-preview",
                "runtime_authoritative": True,
            },
            create_sources_event=create_sources_event,
            create_metadata_event=create_metadata_event,
            create_done_event=create_done_event,
            registry=_RegistryStub(),
            trace_id="trace-1",
        )
    ]

    metadata_event = next(event for event in events if event.type == "metadata")
    assert metadata_event.content["thinking"] == "native private thinking"
    assert metadata_event.content["thinking_content"] == "Nhịp này không cần kéo dài quá tay."
    assert metadata_event.content["thinking_lifecycle"]["final_text"] == "Nhịp này không cần kéo dài quá tay."
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_emit_stream_finalization_falls_back_to_existing_thinking_content():
    final_state = {
        "session_id": "session-2",
        "grader_score": 7.0,
        "thinking_content": "Đây là thinking content cuối cùng đã có sẵn.",
        "routing_metadata": {"final_agent": "rag_agent"},
    }

    events = [
        event
        async for event in emit_stream_finalization_impl(
            final_state=final_state,
            session_id="session-2",
            context={"user_id": "user-2"},
            start_time=0.0,
            resolve_runtime_llm_metadata=lambda *_args, **_kwargs: {
                "provider": "google",
                "model": "gemini-3.1-flash-lite-preview",
                "runtime_authoritative": True,
            },
            create_sources_event=create_sources_event,
            create_metadata_event=create_metadata_event,
            create_done_event=create_done_event,
            registry=_RegistryStub(),
            trace_id="trace-2",
        )
    ]

    metadata_event = next(event for event in events if event.type == "metadata")
    assert metadata_event.content["thinking_content"] == "Đây là thinking content cuối cùng đã có sẵn."


@pytest.mark.asyncio
async def test_emit_stream_finalization_merges_bus_lifecycle_from_initial_state():
    initial_state = {
        "session_id": "session-merge",
        "context": {"user_id": "user-merge"},
        "routing_metadata": {"final_agent": "tutor"},
    }
    capture_thinking_lifecycle_event(
        initial_state,
        {
            "type": "thinking_start",
            "content": "Phan tich quy tac",
            "node": "tutor_agent",
            "summary": "Dang chot diem neo truoc khi giai thich.",
        },
    )
    capture_thinking_lifecycle_event(
        initial_state,
        {
            "type": "thinking_delta",
            "content": "Minh dang chot diem neo ve Rule 15 truoc khi mo loi giai thich.",
            "node": "tutor_agent",
        },
    )
    capture_thinking_lifecycle_event(
        initial_state,
        {
            "type": "thinking_end",
            "content": "",
            "node": "tutor_agent",
        },
    )

    final_state = {
        "session_id": "session-merge",
        "grader_score": 9.0,
        "routing_metadata": {"final_agent": "tutor"},
    }

    events = [
        event
        async for event in emit_stream_finalization_impl(
            final_state=final_state,
            initial_state=initial_state,
            session_id="session-merge",
            context={"user_id": "user-merge"},
            start_time=0.0,
            resolve_runtime_llm_metadata=lambda *_args, **_kwargs: {
                "provider": "google",
                "model": "gemini-3.1-flash-lite-preview",
                "runtime_authoritative": True,
            },
            create_sources_event=create_sources_event,
            create_metadata_event=create_metadata_event,
            create_done_event=create_done_event,
            registry=_RegistryStub(),
            trace_id="trace-merge",
        )
    ]

    metadata_event = next(event for event in events if event.type == "metadata")
    lifecycle = metadata_event.content["thinking_lifecycle"]

    assert metadata_event.content["thinking_content"] == (
        "Minh dang chot diem neo ve Rule 15 truoc khi mo loi giai thich."
    )
    assert lifecycle["final_text"] == metadata_event.content["thinking_content"]
    assert lifecycle["live_length"] == len(metadata_event.content["thinking_content"])
    assert "live_native" in lifecycle["provenance_mix"]
