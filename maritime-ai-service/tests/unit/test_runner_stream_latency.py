import asyncio

import pytest

from app.engine.multi_agent.runner import (
    WiiiRunner,
    _NODE_GUARDIAN,
    _NODE_SUPERVISOR,
    _NODE_SYNTHESIZER,
)


async def _allow_input_guardrails(_state, *, guardian_passed=True):
    return True, None


async def _allow_output_guardrails(_state):
    return None


@pytest.mark.asyncio
async def test_run_streaming_emits_supervisor_status_before_supervisor_finishes(
    monkeypatch,
):
    import app.engine.multi_agent.runner as runner_mod

    monkeypatch.setattr(
        runner_mod,
        "run_input_guardrails",
        _allow_input_guardrails,
    )
    monkeypatch.setattr(
        runner_mod,
        "run_output_guardrails",
        _allow_output_guardrails,
    )

    supervisor_started = asyncio.Event()
    finish_supervisor = asyncio.Event()
    runner = WiiiRunner()

    async def guardian_node(state):
        state["guardian_passed"] = True
        return state

    async def supervisor_node(state):
        supervisor_started.set()
        await finish_supervisor.wait()
        state["next_agent"] = "direct"
        state["routing_metadata"] = {
            "final_agent": "direct",
            "intent": "social",
            "method": "test",
        }
        return state

    async def direct_node(state):
        state["current_agent"] = "direct"
        state["final_response"] = "Wiii da co du noi dung de ket thuc luot nay."
        state["grader_score"] = 8.0
        return state

    async def synthesizer_node(state):
        return state

    runner.register_node(_NODE_GUARDIAN, guardian_node)
    runner.register_node(_NODE_SUPERVISOR, supervisor_node)
    runner.register_node("direct", direct_node)
    runner.register_node(_NODE_SYNTHESIZER, synthesizer_node)

    merged_queue = asyncio.Queue()
    run_task = asyncio.create_task(
        runner.run_streaming(
            {"query": "hi", "session_id": "session-1"},
            merged_queue=merged_queue,
        )
    )

    seen = []
    while True:
        msg_type, payload = await asyncio.wait_for(merged_queue.get(), timeout=1)
        seen.append((msg_type, payload))
        if (
            msg_type == "bus"
            and payload.get("type") == "status"
            and payload.get("details", {}).get("stage") == "runtime_step_start"
            and payload.get("details", {}).get("node_name") == _NODE_SUPERVISOR
        ):
            break

    assert supervisor_started.is_set()
    assert not any(
        msg_type == "graph" and _NODE_SUPERVISOR in payload
        for msg_type, payload in seen
    )

    finish_supervisor.set()
    final_state = await asyncio.wait_for(run_task, timeout=1)
    runtime_latency = final_state["_runtime_latency"]
    assert any(
        item.get("stage") == "runtime_step"
        and item.get("node") == _NODE_SUPERVISOR
        and item.get("status") == "ok"
        and item.get("duration_ms") is not None
        for item in runtime_latency["timeline"]
    )
    assert any(
        item.get("stage") == "runtime_route"
        and item.get("from") == _NODE_SUPERVISOR
        and item.get("to") == "direct"
        for item in runtime_latency["timeline"]
    )
