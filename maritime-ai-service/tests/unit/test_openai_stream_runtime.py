from types import SimpleNamespace

import pytest

from app.engine.multi_agent.openai_stream_runtime import (
    _stream_openai_compatible_answer_with_route_impl,
    _supports_native_answer_streaming_impl,
)


def test_supports_native_answer_streaming_now_includes_google():
    assert _supports_native_answer_streaming_impl("google") is True


@pytest.mark.asyncio
async def test_google_direct_stream_emits_visible_reasoning_before_answer():
    events = []

    async def _push_event(event):
        events.append(event)

    class _FakeStream:
        def __aiter__(self):
            async def _gen():
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="<thinking>Cham vao phan tu than cua minh.</thinking>Minh la Wiii.",
                            )
                        )
                    ]
                )
            return _gen()

    class _FakeChatCompletions:
        async def create(self, **_kwargs):
            return _FakeStream()

    class _FakeChat:
        completions = _FakeChatCompletions()

    class _FakeClient:
        chat = _FakeChat()

    route = SimpleNamespace(
        provider="google",
        llm=SimpleNamespace(
            _wiii_tier_key="deep",
            temperature=0.2,
        ),
    )

    response, streamed = await _stream_openai_compatible_answer_with_route_impl(
        route,
        messages=[SimpleNamespace(content="Wiii duoc sinh ra nhu the nao?")],
        push_event=_push_event,
        node="direct",
        thinking_stop_signal=None,
        supports_native_answer_streaming=lambda provider: provider == "google",
        create_openai_compatible_stream_client=lambda _provider: _FakeClient(),
        resolve_openai_stream_model_name=lambda *_args: "gemini-3.1-pro-preview",
        langchain_message_to_openai_payload=lambda message: {"role": "user", "content": message.content},
        extract_openai_delta_text=lambda delta: ("", str(getattr(delta, "content", "") or "")),
    )

    assert streamed is True
    assert str(getattr(response, "content", "")) == "Minh la Wiii."
    assert [event["type"] for event in events] == [
        "thinking_start",
        "thinking_delta",
        "thinking_end",
        "answer_delta",
    ]
    assert events[1]["content"] == "Cham vao phan tu than cua minh."
    assert events[3]["content"] == "Minh la Wiii."
