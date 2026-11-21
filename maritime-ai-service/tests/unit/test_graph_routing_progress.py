import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.engine.multi_agent.graph import (
    _derive_code_stream_session_id,
    _should_enable_real_code_streaming,
    _build_code_studio_progress_messages,
    _build_code_studio_retry_status,
    _build_code_studio_wait_heartbeat_text,
    _build_direct_wait_heartbeat_text,
    _thinking_start_label,
    _format_code_studio_progress_message,
    _summarize_tool_result_for_stream,
    _stream_answer_with_fallback,
    _stream_openai_compatible_answer_with_route,
    _execute_code_studio_tool_rounds,
)


class TestCodeStudioProgressHeartbeat:
    def test_code_stream_session_id_is_stable_for_same_request_id(self):
        runtime = SimpleNamespace(request_id="req-code-studio-123")

        session_a = _derive_code_stream_session_id(runtime_context_base=runtime)
        session_b = _derive_code_stream_session_id(runtime_context_base=runtime)

        assert session_a == session_b
        assert session_a.startswith("vs-stream-")

    def test_real_code_streaming_is_allowed_for_zhipu_glm5(self):
        with patch("app.core.config.get_settings", return_value=SimpleNamespace(enable_real_code_streaming=True)):
            assert _should_enable_real_code_streaming(
                "zhipu",
                llm=SimpleNamespace(_wiii_model_name="glm-5"),
            ) is True

    def test_real_code_streaming_is_allowed_for_openai_compatible_gate(self):
        with patch("app.core.config.get_settings", return_value=SimpleNamespace(enable_real_code_streaming=True)):
            assert _should_enable_real_code_streaming("openai") is True

    @pytest.mark.asyncio
    async def test_native_answer_streaming_surfaces_provider_reasoning_for_direct_lane(self):
        class _FakeDelta:
            def __init__(self, *, reasoning=None, content=None):
                self.reasoning_content = reasoning
                self.content = content

        class _FakeChoice:
            def __init__(self, delta):
                self.delta = delta

        class _FakeChunk:
            def __init__(self, delta):
                self.choices = [_FakeChoice(delta)]

        class _FakeStream:
            def __init__(self, chunks):
                self._chunks = chunks

            def __aiter__(self):
                self._iter = iter(self._chunks)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration as exc:
                    raise StopAsyncIteration from exc

        class _FakeCompletions:
            def __init__(self, chunks):
                self._chunks = chunks

            async def create(self, **_kwargs):
                return _FakeStream(self._chunks)

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=_FakeCompletions(
                    [
                        _FakeChunk(_FakeDelta(reasoning="raw hidden scratchpad")),
                        _FakeChunk(_FakeDelta(content="Xin ")),
                        _FakeChunk(_FakeDelta(content="chao")),
                    ]
                )
            )
        )
        route = SimpleNamespace(
            provider="zhipu",
            llm=SimpleNamespace(_wiii_tier_key="moderate"),
        )
        events = []
        thinking_stop = asyncio.Event()

        async def push_event(event):
            events.append(event)

        with patch(
            "app.engine.multi_agent.graph._create_openai_compatible_stream_client",
            return_value=fake_client,
        ), patch(
            "app.engine.multi_agent.graph._resolve_openai_stream_model_name",
            return_value="glm-4.5-air",
        ):
            response, streamed = await _stream_openai_compatible_answer_with_route(
                route,
                [],
                push_event,
                node="direct",
                thinking_stop_signal=thinking_stop,
            )

        assert streamed is True
        assert thinking_stop.is_set() is True
        assert response.content == "Xin chao"
        assert [event["type"] for event in events] == [
            "thinking_start",
            "thinking_delta",
            "thinking_end",
            "answer_delta",
            "answer_delta",
        ]
        assert any(event.get("content") == "raw hidden scratchpad" for event in events)

    @pytest.mark.asyncio
    async def test_stream_answer_with_fallback_strips_google_thinking_tags_from_direct_answer(self):
        class FakeChunk:
            def __init__(self, content: str):
                self.content = content

            def __add__(self, other):
                return FakeChunk(self.content + getattr(other, "content", ""))

        class FakeLLM:
            _wiii_tier_key = "deep"

            async def astream(self, _messages):
                yield FakeChunk("<thinking>Câu này chạm vào mình.")
                yield FakeChunk("</thinking>Chào bạn! ")
                yield FakeChunk("Mình là Wiii.")

        fake_llm = FakeLLM()
        events = []
        thinking_stop = asyncio.Event()

        async def push_event(event):
            events.append(event)

        with patch(
            "app.engine.multi_agent.graph._stream_openai_compatible_answer_with_route",
            new=AsyncMock(return_value=(None, False)),
        ), patch(
            "app.engine.llm_pool.LLMPool.resolve_runtime_route",
            return_value=SimpleNamespace(llm=fake_llm),
        ):
            response, streamed = await _stream_answer_with_fallback(
                fake_llm,
                [],
                push_event,
                provider="google",
                node="direct",
                thinking_stop_signal=thinking_stop,
            )

        assert streamed is True
        assert response.content == "Chào bạn! Mình là Wiii."
        assert thinking_stop.is_set() is True
        answer_events = [event["content"] for event in events if event["type"] == "answer_delta"]
        assert answer_events == ["Chào bạn! ", "Mình là Wiii."]
        assert not any("<thinking>" in chunk for chunk in answer_events)

    @pytest.mark.asyncio
    async def test_stream_answer_with_fallback_forwards_deep_tier_to_failover_helper(self):
        class FakeLLM:
            _wiii_tier_key = "deep"

            async def astream(self, _messages):
                if False:
                    yield None
                raise RuntimeError("force fallback")

        captured = {}

        async def fake_push_event(_event):
            return None

        async def fake_ainvoke_with_fallback(_llm, _messages, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content="fallback ok")

        with patch(
            "app.engine.multi_agent.graph._stream_openai_compatible_answer_with_route",
            new=AsyncMock(return_value=(None, False)),
        ), patch(
            "app.engine.multi_agent.direct_execution._ainvoke_with_fallback",
            new=fake_ainvoke_with_fallback,
        ), patch(
            "app.engine.llm_pool.LLMPool.resolve_runtime_route",
            return_value=SimpleNamespace(llm=FakeLLM()),
        ):
            response, streamed = await _stream_answer_with_fallback(
                FakeLLM(),
                [],
                fake_push_event,
                provider="google",
                node="direct",
            )

        assert streamed is False
        assert response.content == "fallback ok"
        assert captured["tier"] == "deep"

    def test_simulation_progress_messages_are_living_and_specific(self):
        state = {
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            }
        }

        messages = _build_code_studio_progress_messages(
            "Wiii tao mo phong cho minh duoc chu ?",
            state,
        )

        assert any("state model" in message for message in messages)
        assert any("canvas loop" in message for message in messages)
        assert any("Kimi linear attention" in message for message in messages)

    def test_progress_message_includes_elapsed_seconds(self):
        formatted = _format_code_studio_progress_message("Minh dang dung canvas loop...", 42.1)
        assert "(đã 42s)" in formatted

    def test_retry_status_is_honest_about_long_running_simulation(self):
        retry = _build_code_studio_retry_status(
            "Wiii tao mo phong cho minh duoc chu ?",
            {"context": {"visual_context": {"last_visual_title": "Kimi linear attention"}}},
            elapsed_seconds=240,
        )
        assert "preview thật" in retry
        assert "(đã 240s)" in retry

    @pytest.mark.asyncio
    async def test_stream_answer_suppresses_raw_code_dump_for_code_studio_lane(self):
        events: list[dict] = []

        class FakeChunk:
            def __init__(self, content: str):
                self.content = content

            def __add__(self, other):
                return FakeChunk(self.content + getattr(other, "content", ""))

        class FakeLLM:
            _wiii_tier_key = "moderate"

            async def astream(self, _messages):
                yield FakeChunk("Mình sẽ tạo một ứng dụng mô phỏng cho bạn ngay đây.\n\n")
                yield FakeChunk("```html\n<div class='demo'>Hello</div>\n```")

        async def push_event(event):
            events.append(event)

        with patch(
            "app.engine.multi_agent.graph._stream_openai_compatible_answer_with_route",
            new=AsyncMock(return_value=(None, False)),
        ), patch(
            "app.engine.llm_pool.LLMPool.resolve_runtime_route",
            return_value=SimpleNamespace(llm=FakeLLM()),
        ):
            response, streamed = await _stream_answer_with_fallback(
                FakeLLM(),
                [],
                push_event,
                provider="zhipu",
                node="code_studio_agent",
            )

        assert streamed is True
        assert getattr(response, "content", "").endswith("```")
        answer_events = [event for event in events if event["type"] == "answer_delta"]
        assert len(answer_events) == 1
        assert "ứng dụng mô phỏng" in answer_events[0]["content"]
        assert "```html" not in answer_events[0]["content"]
        assert "<div" not in answer_events[0]["content"]

    @pytest.mark.asyncio
    async def test_preserves_timeout_fallback_response_without_overwrite(self):
        from app.engine.messages import Message

        class SlowLLM:
            async def ainvoke(self, _messages):
                await asyncio.sleep(0.01)
                return Message(role="assistant", content="stale primary response")

        class FallbackLLM:
            def bind_tools(self, _tools):
                return self

            async def ainvoke(self, _messages):
                return Message(role="assistant", content="fallback recovery response")

        async def push_event(_event):
            return None

        async def fake_render_reasoning(**_kwargs):
            return SimpleNamespace(
                label="Dang tong hop",
                summary="Dang tong hop",
                phase="synthesize",
                action_text="",
                delta_chunks=[],
            )

        time_values = iter([0.0, 241.0, 241.0, 241.0, 241.0])

        with patch("app.engine.multi_agent.graph.time.time", side_effect=lambda: next(time_values, 241.0)), \
             patch("app.engine.multi_agent.graph._render_reasoning", new=fake_render_reasoning), \
             patch("app.engine.llm_pool.get_llm_moderate", return_value=FallbackLLM()):
            llm_response, _messages, _events = await _execute_code_studio_tool_rounds(
                SlowLLM(),
                SlowLLM(),
                [],
                [SimpleNamespace(name="tool_create_visual_code")],
                push_event,
                query="",
                state={},
            )

        assert "fallback recovery response" in llm_response.content

    @pytest.mark.asyncio
    async def test_returns_missing_tool_response_when_initial_code_studio_call_times_out(self):
        async def push_event(_event):
            return None

        async def fake_render_reasoning(**kwargs):
            return SimpleNamespace(
                label="Dang tong hop",
                summary="Dang tong hop",
                phase=kwargs.get("phase", "synthesize"),
                action_text="",
                delta_chunks=[],
            )

        async def fake_invoke(*_args, **_kwargs):
            raise TimeoutError("Primary LLM timed out after 25.0s, no fallback available")

        with patch("app.engine.multi_agent.graph._ainvoke_with_fallback", new=AsyncMock(side_effect=fake_invoke)), \
             patch("app.engine.multi_agent.graph._render_reasoning", new=fake_render_reasoning):
            llm_response, _messages, _events = await _execute_code_studio_tool_rounds(
                MagicMock(),
                MagicMock(),
                [],
                [SimpleNamespace(name="tool_create_visual_code")],
                push_event,
                query="Tạo mô phỏng hảo hán uống rượu ngắm trăng xem",
                state={},
            )

        assert "mở đúng lane mô phỏng" in llm_response.content.lower()


class TestVisibleProgressCopy:
    def test_direct_wait_heartbeat_does_not_echo_raw_query_or_tool_name(self):
        query = "Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây"
        text = _build_direct_wait_heartbeat_text(
            query=query,
            phase="ground",
            cue="visual",
            beat_index=1,
            elapsed_sec=4.0,
            tool_names=["tool_web_search"],
        )

        lowered = text.lower()
        assert "visual cho mình xem" not in lowered
        assert "tool_web_search" not in lowered
        assert "http" not in lowered

    def test_code_studio_wait_heartbeat_stays_generic_and_non_query_echo(self):
        query = "mô phỏng cảnh Thúy Kiều ở lầu Ngưng Bích cho mình được chứ ?"
        text = _build_code_studio_wait_heartbeat_text(
            query=query,
            beat_index=1,
            elapsed_sec=8.0,
            state={},
        )

        lowered = text.lower()
        assert "thúy kiều" not in lowered
        assert "lầu ngưng bích" not in lowered
        assert "tool_" not in lowered

    def test_tool_result_summary_hides_search_snippets(self):
        result = _summarize_tool_result_for_stream(
            "tool_web_search",
            "giá dầu hôm nay https://example.com Brent 98.74 WTI 95.92",
        )

        assert result == "Tìm được 1 nguồn: example.com"


class TestVisibleProgressCopyQuality:
    def test_direct_wait_heartbeat_emotional_turn_sounds_present_not_generic(self):
        text = _build_direct_wait_heartbeat_text(
            query="Buồn quá",
            phase="attune",
            cue="social",
            beat_index=1,
            elapsed_sec=4.0,
        )

        lowered = text.lower()
        assert "khoảng chùng xuống" not in lowered
        assert "ở lại với bạn" not in lowered
        assert "nhịp đáp chậm" in lowered or "mở lời vừa đủ dịu" in lowered
        assert "mình đang chắt lấy điều cốt lõi" not in lowered
        assert "mình vẫn đang nghe thêm xem nhịp này" not in lowered

    def test_direct_wait_heartbeat_identity_turn_stays_effortless(self):
        text = _build_direct_wait_heartbeat_text(
            query="Bạn là ai?",
            phase="attune",
            cue="identity",
            beat_index=1,
            elapsed_sec=4.0,
        )

        lowered = text.lower()
        assert "giữ phần tự thân" not in lowered
        assert "bảo vệ identity" not in lowered
        assert "vòng vo" in lowered or "thành thật" in lowered or "màu mè" in lowered

    def test_code_studio_wait_heartbeat_simulation_turn_keeps_scene_mindset(self):
        text = _build_code_studio_wait_heartbeat_text(
            query="mô phỏng dạng 3d được khum",
            beat_index=1,
            elapsed_sec=8.0,
            state={},
        )

        lowered = text.lower()
        assert "mô phỏng" in lowered or "canvas" in lowered or "khung chuyển động" in lowered
        assert "demo chung chung" not in lowered


class TestThinkingStartSurfaceLabel:
    def test_generic_lifecycle_label_stays_hidden_from_visible_surface(self):
        assert _thinking_start_label("Bắt nhịp câu hỏi") == ""
        assert _thinking_start_label("Chốt cách đáp hợp nhịp") == ""

    def test_persona_label_can_still_surface_when_it_sounds_like_wiii(self):
        assert _thinking_start_label("Hmm Wiii suy nghĩ rồi nè~") == "Hmm Wiii suy nghĩ rồi nè~"
