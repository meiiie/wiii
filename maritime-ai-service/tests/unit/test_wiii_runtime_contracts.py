"""Tests for native Wiii runtime contracts and adapters."""

from __future__ import annotations

import pytest

from app.engine.multi_agent.runtime_contracts import (
    WiiiRunContext,
    WiiiStreamEvent,
    WiiiTurnRequest,
    WiiiTurnResult,
    WiiiTurnState,
)


def test_wiii_turn_request_adapts_to_existing_runtime_kwargs():
    context = {"response_language": "vi"}
    request = WiiiTurnRequest(
        query="chao Wiii",
        run_context=WiiiRunContext(
            user_id="user-1",
            session_id="session-1",
            domain_id="maritime",
            organization_id="org-1",
            context=context,
            thinking_effort="low",
            provider="nvidia",
            model="deepseek-ai/deepseek-v3.1",
        ),
    )

    kwargs = request.to_runtime_kwargs()

    assert kwargs == {
        "query": "chao Wiii",
        "user_id": "user-1",
        "session_id": "session-1",
        "context": {"response_language": "vi", "organization_id": "org-1"},
        "domain_id": "maritime",
        "thinking_effort": "low",
        "provider": "nvidia",
        "model": "deepseek-ai/deepseek-v3.1",
    }
    assert context == {"response_language": "vi"}


def test_wiii_turn_result_and_state_expose_stable_fields():
    result = WiiiTurnResult.from_payload(
        {
            "response": "Xin chao.",
            "current_agent": "direct",
            "_execution_provider": "nvidia",
            "_execution_model": "deepseek-v3.1",
        }
    )
    state = WiiiTurnState(
        {
            "final_response": "Xin chao.",
            "current_agent": "direct",
            "_execution_provider": "nvidia",
            "_execution_model": "deepseek-v3.1",
        }
    )

    assert result.response == "Xin chao."
    assert result.current_agent == "direct"
    assert result.provider == "nvidia"
    assert result.model == "deepseek-v3.1"
    assert state.final_response == "Xin chao."
    assert state.current_agent == "direct"
    assert state.provider == "nvidia"
    assert state.model == "deepseek-v3.1"


def test_wiii_stream_event_wraps_existing_tuple_contract():
    event = WiiiStreamEvent.from_legacy_tuple(("graph", {"direct": {"response": "ok"}}))

    assert event.event_type == "graph"
    assert event.node_name == "direct"
    assert event.to_legacy_tuple() == ("graph", {"direct": {"response": "ok"}})


@pytest.mark.asyncio
async def test_run_wiii_turn_uses_existing_runtime_adapter(monkeypatch):
    from app.engine.multi_agent import runtime

    captured = {}

    async def fake_process_with_multi_agent(**kwargs):
        captured.update(kwargs)
        return {
            "response": "Wiii day.",
            "current_agent": "direct",
            "provider": kwargs["provider"],
            "model": kwargs["model"],
        }

    monkeypatch.setattr(runtime, "process_with_multi_agent", fake_process_with_multi_agent)

    result = await runtime.run_wiii_turn(
        WiiiTurnRequest(
            query="hello",
            run_context=WiiiRunContext(
                user_id="user-1",
                session_id="session-1",
                context={"conversation_summary": "recent"},
                domain_id="general",
                provider="nvidia",
                model="deepseek-v3.1",
            ),
        )
    )

    assert captured["query"] == "hello"
    assert captured["context"] == {"conversation_summary": "recent"}
    assert captured["domain_id"] == "general"
    assert result.response == "Wiii day."
    assert result.provider == "nvidia"


@pytest.mark.asyncio
async def test_stream_wiii_turn_wraps_existing_stream_events(monkeypatch):
    from app.engine.multi_agent import streaming_runtime

    captured = {}

    async def fake_process_with_multi_agent_streaming(**kwargs):
        captured.update(kwargs)
        yield ("graph", {"guardian": {"guardian_passed": True}})
        yield ("graph_done", None)

    monkeypatch.setattr(
        streaming_runtime,
        "process_with_multi_agent_streaming",
        fake_process_with_multi_agent_streaming,
    )

    events = [
        event
        async for event in streaming_runtime.stream_wiii_turn(
            WiiiTurnRequest(
                query="hello",
                run_context=WiiiRunContext(user_id="user-1", session_id="session-1"),
            )
        )
    ]

    assert captured["query"] == "hello"
    assert events[0].event_type == "graph"
    assert events[0].node_name == "guardian"
    assert events[0].to_legacy_tuple() == ("graph", {"guardian": {"guardian_passed": True}})
    assert events[1].event_type == "graph_done"
