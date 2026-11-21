import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


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
            forced_tool_choice="tool_demo",
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
async def test_execute_direct_tool_rounds_converts_raw_json_tool_call_text():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    class FakeKnowledgeTool:
        name = "tool_knowledge_search"

        async def ainvoke(self, args):
            return f"Nguon nhap mon hang hai cho {args['query']}"

    events = []

    async def push_event(event):
        events.append(event)

    async def fake_stream_direct_answer_with_fallback(*_args, **_kwargs):
        return (
            SimpleNamespace(
                content=json.dumps(
                    {
                        "name": "tool_knowledge_search",
                        "arguments": {
                            "query": "gioi thieu nganh hang hai cho nguoi moi bat dau",
                        },
                    },
                    ensure_ascii=False,
                ),
                tool_calls=[],
            ),
            True,
        )

    async def fake_ainvoke_with_fallback(_llm, _messages, **_kwargs):
        return SimpleNamespace(
            content=(
                "Được chứ. Nếu mới bắt đầu học Hàng hải, mình sẽ đi từ bức tranh lớn: "
                "tàu, cảng, an toàn, luật biển và nghiệp vụ vận hành."
            ),
            tool_calls=[],
        )

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_answer_with_fallback",
        new=fake_stream_direct_answer_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        llm_response, _messages, tool_call_events = await execute_direct_tool_rounds_impl(
            llm_with_tools=object(),
            llm_auto=object(),
            messages=[],
            tools=[FakeKnowledgeTool()],
            push_event=push_event,
            query="Mình đang muốn học về lĩnh vực Hàng Hải các bạn có thể giúp mình được không",
            state={},
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert "tool_knowledge_search" not in llm_response.content
    assert "mới bắt đầu học Hàng hải" in llm_response.content
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    assert tool_call_events[0]["name"] == "tool_knowledge_search"
    assert tool_call_events[0]["args"]["query"] == "gioi thieu nganh hang hai cho nguoi moi bat dau"
    assert any(event["type"] == "tool_call" for event in events)
    assert not any(
        event["type"] == "answer_delta" and "tool_knowledge_search" in str(event.get("content", ""))
        for event in events
    )

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
            forced_tool_choice="tool_demo",
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert captured["tier"] == "deep"

@pytest.mark.asyncio
async def test_execute_direct_tool_rounds_can_use_native_tool_messages():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )
    from app.engine.native_chat_runtime import NativeToolMessage, NativeUserMessage

    class FakeTool:
        name = "tool_demo"

        def invoke(self, args):
            return f"ket qua cho {args['query']}"

    captured_messages: list[list[object]] = []

    async def push_event(_event):
        return None

    async def fake_ainvoke_with_fallback(_llm, messages, **_kwargs):
        captured_messages.append(list(messages))
        call_index = fake_ainvoke_with_fallback.calls
        fake_ainvoke_with_fallback.calls += 1
        if call_index == 0:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool_demo", "args": {"query": "abc"}}
                ],
            )
        if call_index == 1:
            return SimpleNamespace(content="", tool_calls=[])
        return SimpleNamespace(content="Day la cau tra loi cuoi.", tool_calls=[])

    fake_ainvoke_with_fallback.calls = 0

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

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        llm_response, messages, tool_call_events = await execute_direct_tool_rounds_impl(
            llm_with_tools=object(),
            llm_auto=object(),
            messages=[],
            tools=[FakeTool()],
            push_event=push_event,
            query="Tim du kien roi tong hop lai",
            state={},
            llm_base=object(),
            forced_tool_choice="tool_demo",
            native_tool_messages=True,
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    assert llm_response.content == "Day la cau tra loi cuoi."
    assert [event["type"] for event in tool_call_events] == ["call", "result"]
    assert any(isinstance(message, NativeToolMessage) for message in captured_messages[1])
    assert isinstance(captured_messages[2][-1], NativeUserMessage)
    assert messages == captured_messages[2]

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
