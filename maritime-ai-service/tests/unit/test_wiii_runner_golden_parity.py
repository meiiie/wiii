"""Golden parity tests for WiiiRunner sync and streaming execution.

These tests intentionally avoid real providers and agent nodes. They lock the
runtime contract that must survive the de-LangGraph migration before any
runner-backed ``graph_*`` compatibility shells are renamed or removed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.runner import WiiiRunner


def _build_runner(step_log: list[str]) -> WiiiRunner:
    runner = WiiiRunner()

    async def guardian(state):
        step_log.append("guardian")
        state.setdefault("guardian_passed", True)
        return state

    async def supervisor(state):
        step_log.append("supervisor")
        state["next_agent"] = "direct"
        return state

    async def direct(state):
        step_log.append("direct")
        state["current_agent"] = "direct"
        state["final_response"] = "Direct answer long enough for parity checks."
        state["sources"] = [{"title": "golden-source"}]
        state["_execution_provider"] = "zhipu"
        state["_execution_model"] = "glm-5"
        return state

    async def synthesizer(state):
        step_log.append("synthesizer")
        state["current_agent"] = "synthesizer"
        state.setdefault("final_response", "Synthesized fallback.")
        state.setdefault("sources", [])
        return state

    runner.register_node("guardian", guardian)
    runner.register_node("supervisor", supervisor)
    runner.register_node("direct", direct)
    runner.register_node("synthesizer", synthesizer)
    return runner


def _node_names(events: list[tuple]) -> list[str]:
    names = []
    for event_type, payload in events:
        if event_type == "graph" and isinstance(payload, dict):
            names.extend(payload.keys())
    return names


async def _run_streaming(runner: WiiiRunner, state: dict) -> tuple[dict, list[tuple]]:
    queue: asyncio.Queue = asyncio.Queue()
    result = await runner.run_streaming(dict(state), merged_queue=queue)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return result, events


@pytest.mark.asyncio
async def test_sync_and_streaming_share_core_step_contract():
    """Sync and streaming lanes must execute the same WiiiRunner core path."""
    base_state = {
        "query": "hello",
        "user_id": "user-1",
        "session_id": "session-1",
    }
    sync_log: list[str] = []
    stream_log: list[str] = []
    sync_runner = _build_runner(sync_log)
    stream_runner = _build_runner(stream_log)

    input_guardrails = AsyncMock(return_value=(True, None))
    output_guardrails = AsyncMock(return_value=(True, None))

    with patch("app.engine.multi_agent.runtime_routes.guardian_route", return_value="supervisor"), patch(
        "app.engine.multi_agent.graph_support.route_decision", return_value="direct"
    ), patch(
        "app.engine.multi_agent.runner.run_input_guardrails", input_guardrails
    ), patch(
        "app.engine.multi_agent.runner.run_output_guardrails", output_guardrails
    ):
        sync_result = await sync_runner.run(dict(base_state))
        stream_result, stream_events = await _run_streaming(stream_runner, base_state)

    assert sync_log == ["guardian", "supervisor", "direct", "synthesizer"]
    assert stream_log == sync_log
    assert _node_names(stream_events) == ["guardian", "direct", "synthesizer"]

    for key in (
        "final_response",
        "sources",
        "_execution_provider",
        "_execution_model",
        "user_id",
        "session_id",
    ):
        assert stream_result[key] == sync_result[key]

    assert input_guardrails.await_count == 2
    assert output_guardrails.await_count == 2


@pytest.mark.asyncio
async def test_streaming_applies_input_guardrail_before_routing():
    """Streaming must not bypass guardrails that the sync lane already enforces."""
    step_log: list[str] = []
    runner = _build_runner(step_log)
    input_guardrails = AsyncMock(return_value=(False, "blocked by golden parity test"))
    output_guardrails = AsyncMock(return_value=(True, None))

    def guardian_route(state):
        return "synthesizer" if not state.get("guardian_passed", True) else "supervisor"

    with patch("app.engine.multi_agent.runtime_routes.guardian_route", side_effect=guardian_route), patch(
        "app.engine.multi_agent.graph_support.route_decision", return_value="direct"
    ), patch(
        "app.engine.multi_agent.runner.run_input_guardrails", input_guardrails
    ), patch(
        "app.engine.multi_agent.runner.run_output_guardrails", output_guardrails
    ):
        result, stream_events = await _run_streaming(
            runner,
            {
                "query": "blocked",
                "user_id": "user-1",
                "session_id": "session-1",
            },
        )

    assert step_log == ["guardian", "synthesizer"]
    assert _node_names(stream_events) == ["guardian", "synthesizer"]
    assert result["guardian_passed"] is False
    assert result["final_response"] == "blocked by golden parity test"
    input_guardrails.assert_awaited_once()
    output_guardrails.assert_awaited_once()
