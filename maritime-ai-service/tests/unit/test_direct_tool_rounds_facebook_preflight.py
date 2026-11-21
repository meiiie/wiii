import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_wiii_connect_facebook_post_preflight_defers_ready_request_to_tool_schema(monkeypatch) -> None:
    from app.engine.multi_agent.direct_wiii_connect_host_action_runtime import (
        preflight_requested_wiii_connect_facebook_post,
    )

    state: dict = {
        "context": {
            "images": [{"type": "base64", "data": "abc"}],
            "host_context": {
                "page": {
                    "metadata": {
                        "wiii_connect": {
                            "provider_slug": "facebook",
                            "status": "connected",
                            "connection_count": 1,
                            "active_connection_count": 1,
                            "connection_state": "connected",
                        }
                    }
                }
            },
        }
    }

    def build_assistant_message(content: str, **kwargs) -> dict:
        return {"content": content, "native_tool_messages": kwargs["native_tool_messages"]}

    monkeypatch.setattr(
        "app.engine.multi_agent.external_app_action_runtime."
        "_effective_action_allowlists_for_providers",
        lambda *_args, **_kwargs: {"facebook": ("FACEBOOK_CREATE_POST",)},
    )
    monkeypatch.setattr(
        "app.engine.multi_agent.external_app_action_runtime."
        "_ready_provider_slugs_from_state",
        lambda *_args, **_kwargs: ("facebook",),
    )

    response = await preflight_requested_wiii_connect_facebook_post(
        query="Wiii đăng bài Facebook, bài nào cũng được kèm ảnh này",
        state=state,
        native_tool_messages=True,
        build_assistant_message=build_assistant_message,
    )

    assert response is None

@pytest.mark.asyncio
async def test_wiii_connect_facebook_post_preflight_preempts_forced_web_search(monkeypatch) -> None:
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )
    from app.engine.tools.tool_capability_registry import (
        WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL,
    )

    class FakeWebSearchTool:
        name = "tool_web_search"

        def invoke(self, _args):
            raise AssertionError("facebook external action should preempt web search")

        async def ainvoke(self, _args):
            raise AssertionError("facebook external action should preempt web search")

    class FakeFacebookPreviewTool:
        name = WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL

        def invoke(self, args):
            return json.dumps(
                {
                    "status": "action_requested",
                    "request_id": "fb-direct-apply-1",
                    "action": "wiii_connect.facebook_post.direct_apply",
                    "params": args,
                }
            )

        async def ainvoke(self, args):
            return self.invoke(args)

    pushed_events: list[dict] = []

    async def push_event(event: dict) -> None:
        pushed_events.append(event)

    ainvoke_calls: list[dict] = []

    async def fake_ainvoke_with_fallback(*_args, **kwargs):
        ainvoke_calls.append(kwargs)
        if len(ainvoke_calls) == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "fb-direct-apply-1",
                        "name": WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL,
                        "args": {
                            "provider_slug": "facebook",
                            "message": (
                                "Một ngày bình thường của Wiii: đang học COLREGs"
                            ),
                        },
                    }
                ],
            )
        return SimpleNamespace(
            content="Mình đã gửi yêu cầu đăng bài Facebook qua Wiii Connect.",
            tool_calls=[],
        )

    async def fake_stream_direct_answer_with_fallback(*_args, **_kwargs):
        raise AssertionError("facebook external action should not stream direct answer")

    async def fake_stream_direct_wait_heartbeats(*_args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.engine.multi_agent.external_app_action_runtime."
        "_effective_action_allowlists_for_providers",
        lambda *_args, **_kwargs: {"facebook": ("FACEBOOK_CREATE_POST",)},
    )
    monkeypatch.setattr(
        "app.engine.multi_agent.external_app_action_runtime."
        "_ready_provider_slugs_from_state",
        lambda *_args, **_kwargs: ("facebook",),
    )

    state = {
        "context": {
            "force_skills": ["web-search"],
            "host_context": {
                "page": {
                    "metadata": {
                        "wiii_connect": {
                            "provider_slug": "facebook",
                            "status": "connected",
                            "connection_count": 1,
                            "active_connection_count": 1,
                            "connection_state": "connected",
                        }
                    }
                }
            },
        }
    }

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
            tools=[FakeWebSearchTool(), FakeFacebookPreviewTool()],
            push_event=push_event,
            query=(
                'Wiii đăng một bài Facebook: "Một ngày bình thường của Wiii: '
                'đang học COLREGs" rồi đăng lên trang cá nhân đi'
            ),
            state=state,
            forced_tool_choice="tool_web_search",
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
            native_tool_messages=True,
        )

    assert "gửi yêu cầu đăng bài Facebook" in llm_response.content
    assert "chưa có nội dung" not in llm_response.content
    assert len(ainvoke_calls) == 1
    assert ainvoke_calls[0]["tool_choice"] == WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL
    assert [tool.name for tool in ainvoke_calls[0]["tools"]] == [
        WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL
    ]
    assert tool_call_events[0]["name"] == WIII_CONNECT_FACEBOOK_POST_DIRECT_APPLY_TOOL
    assert tool_call_events[0]["args"]["provider_slug"] == "facebook"
    assert (
        tool_call_events[0]["args"]["message"]
        == "Một ngày bình thường của Wiii: đang học COLREGs"
    )
    assert any(event["type"] == "host_action" for event in pushed_events)

@pytest.mark.asyncio
async def test_wiii_connect_facebook_post_preflight_blocks_pending_connection() -> None:
    from app.engine.multi_agent.direct_wiii_connect_host_action_runtime import (
        preflight_requested_wiii_connect_facebook_post,
    )

    state: dict = {
        "context": {
            "host_context": {
                "page": {
                    "metadata": {
                        "wiii_connect": {
                            "provider_slug": "facebook",
                            "status": "not_connected",
                            "connection_count": 1,
                            "active_connection_count": 0,
                            "connection_state": "waiting",
                        }
                    }
                }
            }
        }
    }

    def build_assistant_message(content: str, **kwargs) -> dict:
        return {"content": content, "native_tool_messages": kwargs["native_tool_messages"]}

    response = await preflight_requested_wiii_connect_facebook_post(
        query="Wiii dang mot bai Facebook, bai nao cung duoc",
        state=state,
        native_tool_messages=True,
        build_assistant_message=build_assistant_message,
    )

    assert response is not None
    assert "chưa có account Facebook active" in response["content"]
