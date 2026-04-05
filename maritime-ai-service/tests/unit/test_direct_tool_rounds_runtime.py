import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_build_direct_final_synthesis_instruction_is_mode_aware_for_market_turn():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        _build_direct_final_synthesis_instruction,
    )

    instruction = _build_direct_final_synthesis_instruction(
        "phan tich gia dau",
        {},
        ["tool_web_search"],
    ).lower()

    assert "khong goi them cong cu" in instruction
    assert "mot cau thesis ve mat bang thi truong hien tai" in instruction
    assert "khong dung heading markdown nhu #, ##, ###" in instruction
    assert "khong dung bullet/bold kieu ban tin tong hop" in instruction
    assert "opec+" in instruction or "ton kho" in instruction


def test_direct_public_thinking_dedupe_detects_identical_blocks():
    from app.engine.multi_agent.direct_public_thinking_runtime import (
        remember_direct_public_thinking_chunks,
        should_emit_direct_public_thinking_chunks,
    )

    state = {}
    opening_chunks = [
        "Cau nay can mot nhip dap cham va that hon la mot loi giai thich voi.",
        "Minh muon mo loi vua du diu de neu ban muon ke tiep thi van con cho cho nhip do di ra.",
    ]
    remember_direct_public_thinking_chunks(state, opening_chunks)

    assert should_emit_direct_public_thinking_chunks(state, list(opening_chunks)) is False


def test_direct_public_thinking_dedupe_allows_changed_blocks():
    from app.engine.multi_agent.direct_public_thinking_runtime import (
        remember_direct_public_thinking_chunks,
        should_emit_direct_public_thinking_chunks,
    )

    state = {}
    remember_direct_public_thinking_chunks(
        state,
        [
            "Cau nay can mot nhip dap cham va that hon la mot loi giai thich voi.",
            "Minh muon mo loi vua du diu de neu ban muon ke tiep thi van con cho cho nhip do di ra.",
        ],
    )

    assert should_emit_direct_public_thinking_chunks(
        state,
        [
            "Gio minh da co them du kien nen co the noi cu the hon.",
            "Minh se giu nhip diu nhung neo cau tra loi vao dieu vua kiem chung.",
        ],
    ) is True


def test_build_direct_final_synthesis_instruction_is_mode_aware_for_math_turn():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        _build_direct_final_synthesis_instruction,
    )

    instruction = _build_direct_final_synthesis_instruction(
        "Phan tich ve toan hoc con lac don",
        {},
        [],
    ).lower()

    assert "khong goi them cong cu" in instruction
    assert "mot cau thesis ve mo hinh dang dung" in instruction
    assert "mo hinh/gia dinh -> phuong trinh hoac suy dan -> y nghia vat ly" in instruction
    assert "khong dung heading markdown nhu #, ##, ###" in instruction


@pytest.mark.asyncio
async def test_execute_direct_tool_rounds_does_not_emit_authored_public_thinking_for_tool_rounds():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    class FakeTool:
        name = "tool_demo"

        async def ainvoke(self, args):
            return f"ket qua cho {args['query']}"

    events = []

    async def push_event(event):
        events.append(event)

    async def fake_ainvoke_with_fallback(_llm, _messages, **kwargs):
        call_index = fake_ainvoke_with_fallback.calls
        fake_ainvoke_with_fallback.calls += 1
        if call_index == 0:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool_demo", "args": {"query": "abc"}}
                ],
            )
        return SimpleNamespace(content="Day la cau tra loi cuoi.", tool_calls=[])

    fake_ainvoke_with_fallback.calls = 0

    async def fake_stream_direct_answer_with_fallback(*args, **kwargs):
        raise AssertionError("No-tool streaming path should not be used in this test")

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(push_event, node, content, subtype):
        await push_event(
            {
                "type": "status",
                "content": content,
                "node": node,
                "subtype": subtype,
            }
        )

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        llm_response, _messages, tool_call_events = await execute_direct_tool_rounds_impl(
            llm_with_tools=object(),
            llm_auto=object(),
            messages=[],
            tools=[FakeTool()],
            push_event=push_event,
            query="Tim giup minh mot du kien roi tra loi ngan gon.",
            state={},
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert llm_response.content == "Day la cau tra loi cuoi."
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    event_types = [event["type"] for event in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "thinking_start" not in event_types
    assert "thinking_delta" not in event_types
    assert "action_text" not in event_types


@pytest.mark.asyncio
async def test_execute_direct_tool_rounds_forwards_runtime_tier_to_failover_helper():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    class FakeTool:
        name = "tool_demo"

        async def ainvoke(self, args):
            return f"ket qua cho {args['query']}"

    captured: dict[str, object] = {}

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(_llm, _messages, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content="final", tool_calls=[])

    async def fake_stream_direct_answer_with_fallback(*args, **kwargs):
        raise AssertionError("tool-bound turn should not use no-tool streaming path")

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    llm = SimpleNamespace(_wiii_tier_key="deep", _wiii_provider_name="google")

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        await execute_direct_tool_rounds_impl(
            llm_with_tools=llm,
            llm_auto=llm,
            messages=[],
            tools=[FakeTool()],
            push_event=push_event,
            query="Hay giai thich spectral theorem va self-adjoint operator",
            state={},
            llm_base=llm,
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert captured["tier"] == "deep"


@pytest.mark.asyncio
async def test_execute_direct_tool_rounds_forwards_primary_timeout_to_stream_path():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    captured: dict[str, object] = {}

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(*args, **kwargs):
        raise AssertionError("no-tool turn should use streaming helper first")

    async def fake_stream_direct_answer_with_fallback(_llm, _messages, _push_event, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content="xin chao", tool_calls=[]), True

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    llm = SimpleNamespace(_wiii_tier_key="deep", _wiii_provider_name="zhipu")

    with patch(
        "app.engine.multi_agent.graph._stream_direct_answer_with_fallback",
        new=fake_stream_direct_answer_with_fallback,
    ):
        await execute_direct_tool_rounds_impl(
            llm_with_tools=llm,
            llm_auto=llm,
            messages=[],
            tools=[],
            push_event=push_event,
            query="Wiii duoc sinh ra nhu the nao?",
            state={},
            llm_base=llm,
            direct_answer_timeout_profile="structured",
            direct_answer_primary_timeout=6.0,
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert captured["primary_timeout"] == pytest.approx(6.0)
    assert captured["timeout_profile"] == "structured"
