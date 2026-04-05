from types import SimpleNamespace

import pytest

from app.engine.multi_agent.direct_execution import _stream_answer_with_fallback


class _FakeStringChunk:
    def __init__(self, content, *, additional_kwargs=None, response_metadata=None):
        self.content = content
        self.additional_kwargs = additional_kwargs or {}
        self.response_metadata = response_metadata or {}

    def __add__(self, other):
        merged_content = f"{self.content}{other.content}"
        merged_kwargs = dict(self.additional_kwargs)
        merged_kwargs.update(getattr(other, "additional_kwargs", {}) or {})
        merged_metadata = dict(self.response_metadata)
        merged_metadata.update(getattr(other, "response_metadata", {}) or {})
        return _FakeStringChunk(
            merged_content,
            additional_kwargs=merged_kwargs,
            response_metadata=merged_metadata,
        )


@pytest.mark.asyncio
async def test_stream_answer_with_fallback_does_not_replay_full_answer_after_delta_chunks(monkeypatch):
    events = []

    async def _push_event(event):
        events.append(event)

    async def _compat_stream_should_not_run(*_args, **_kwargs):
        raise AssertionError("google direct should bypass compat stream here")

    monkeypatch.setattr(
        "app.engine.multi_agent.direct_execution._stream_openai_compatible_answer_with_route",
        _compat_stream_should_not_run,
    )

    class _ReplayChunkLLM:
        _wiii_tier_key = "deep"

        async def astream(self, _messages):
            yield _FakeStringChunk("Minh ra doi vao mot dem mua")
            yield _FakeStringChunk(", khi The Wiii Lab van con dang thu nghiem.")
            yield _FakeStringChunk(
                "Minh ra doi vao mot dem mua, khi The Wiii Lab van con dang thu nghiem."
            )
            yield _FakeStringChunk(
                "Minh ra doi vao mot dem mua,  khi The Wiii Lab van con dang thu nghiem."
            )
            yield _FakeStringChunk(
                "Minh ra doi vao mot dem mua, khi The Wiii Lab van con dang thu nghiem."
            )

    class _FakePool:
        @staticmethod
        def resolve_runtime_route(*_args, **_kwargs):
            return SimpleNamespace(provider="google", llm=_ReplayChunkLLM())

    monkeypatch.setattr("app.engine.llm_pool.LLMPool", _FakePool)

    response, streamed = await _stream_answer_with_fallback(
        _ReplayChunkLLM(),
        messages=[SimpleNamespace(content="Wiii duoc sinh ra nhu the nao?")],
        push_event=_push_event,
        provider="google",
        resolved_provider="google",
        node="direct",
        thinking_block_opened=False,
        state={"context": {"response_language": "vi"}},
    )

    assert streamed is True
    assert response.content == (
        "Minh ra doi vao mot dem mua, khi The Wiii Lab van con dang thu nghiem."
    )
    assert [event["type"] for event in events] == ["answer_delta", "answer_delta"]
    assert events[0]["content"] == "Minh ra doi vao mot dem mua"
    assert events[1]["content"] == ", khi The Wiii Lab van con dang thu nghiem."
