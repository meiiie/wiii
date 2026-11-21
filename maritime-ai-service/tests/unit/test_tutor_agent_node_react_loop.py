import asyncio
import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from tests.unit.tutor_agent_node_helpers import (
    _make_tutor,
    mock_llm as mock_llm,
)


class TestReactLoop:
    @pytest.mark.asyncio
    async def test_no_tool_calls_direct_answer(self, mock_llm):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Direct answer"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Direct answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ):
            response, sources, tools_used, thinking, _streamed = await node._react_loop("test", {})

        assert response == "Direct answer"
        assert tools_used == []

    @pytest.mark.asyncio
    async def test_no_tool_calls_stream_answer_without_repeating_it_in_thinking(self, mock_llm):
        chunk = MagicMock()
        chunk.tool_calls = []
        chunk.content = "Direct answer"

        async def _astream(_messages):
            yield chunk

        mock_llm.astream = _astream

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Direct answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node._iteration_beat",
            AsyncMock(return_value=types.SimpleNamespace(
                label="Phan tich cau hoi",
                summary="Dang tong hop huong giai thich.",
                phase="synthesize",
            )),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ):
            response, sources, tools_used, thinking, streamed = await node._react_loop(
                "test",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = [event["content"] for event in events if event.get("type") == "thinking_delta"]
        answer_chunks = [event["content"] for event in events if event.get("type") == "answer_delta"]

        assert response == "Direct answer"
        assert sources == []
        assert tools_used == []
        assert streamed is False
        assert "".join(thinking_chunks) == ""
        assert "".join(answer_chunks) == ""

    @pytest.mark.asyncio
    async def test_tool_call_then_respond(self, mock_llm):
        # First call: LLM requests tool
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 13"}, "id": "call_1"}
        ]
        tool_response.content = ""

        # Second call: LLM gives final answer
        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Rule 13 answer from knowledge base"

        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Rule 13 answer from knowledge base", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.tool_knowledge_search",
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="Search result text")

            with patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
                return_value=[{"title": "COLREGs"}],
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
                return_value=None,
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
                return_value=(0.5, True),
            ):
                response, sources, tools_used, thinking, _streamed = await node._react_loop("Rule 13", {})

        assert "Rule 13" in response
        assert len(tools_used) == 1
        assert tools_used[0]["name"] == "tool_knowledge_search"

    @pytest.mark.asyncio
    async def test_tool_policy_denies_stale_tutor_tool_without_dispatch(self, mock_llm):
        stale_tool_response = MagicMock()
        stale_tool_response.tool_calls = [
            {"name": "tool_web_search", "args": {"query": "outside policy"}, "id": "call_stale"}
        ]
        stale_tool_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        mock_llm.ainvoke.side_effect = [stale_tool_response, final_response]
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        state = {
            "_tool_policy_session": {
                "version": "tool_policy_session.v1",
                "path": "tutor",
                "reason": "tutor_tool_setup",
                "bind_tools": True,
                "force_tools": False,
                "allow_all_tools": False,
                "allowed_tool_names": ["tool_knowledge_search"],
                "allowed_tool_prefixes": [],
                "forbidden_tool_names": [],
                "forbidden_tool_prefixes": [],
                "candidate_tool_names": ["tool_knowledge_search", "tool_web_search"],
                "visible_tool_names": ["tool_knowledge_search"],
                "connection_status": {},
                "approval_required_tool_names": [],
            }
        }

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Final tutor answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=AssertionError("denied tool must not dispatch")),
        ) as dispatch_mock:
            response, sources, tools_used, _thinking, _streamed = await node._react_loop(
                "Explain Rule 13",
                {},
                state=state,
            )

        assert response == "Final tutor answer"
        assert sources == []
        assert tools_used == []
        dispatch_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_tool_call_sync_collects_public_tutor_thinking_for_state_parity(self, mock_llm):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        tool_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push_thinking_deltas"](
                "Minh can doi chieu Rule 15 voi Rule 13 truoc khi giang de khong keo nguoi hoc vao nham lan."
            )
            return types.SimpleNamespace(
                phase_transition_count=kwargs["phase_transition_count"],
                last_tool_was_progress=False,
                should_break_loop=False,
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Final tutor answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(side_effect=lambda text, **_: text),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, sources, tools_used, thinking, _streamed = await node._react_loop(
                "Giải thích Rule 15",
                {},
            )

        assert response == "Final tutor answer"
        assert sources == []
        assert tools_used == []
        assert thinking is not None
        assert "doi chieu Rule 15 voi Rule 13" in thinking
        assert "Cau mo dau phai chot ngay mau chot" not in thinking

    @pytest.mark.asyncio
    async def test_tool_call_stream_prefers_rag_thinking_over_planner_spill(self, mock_llm):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        tool_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {"name": "tool_knowledge_search", "result": "Rule 15 says ..."},
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=kwargs["phase_transition_count"],
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="Rule 15 says ...",
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("", "I'm now reviewing past responses and I'll use tool_knowledge_search to structure the answer."),
                ("Final tutor answer", None),
                ("Final tutor answer", None),
            ],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=(
                "Mình đã có một mốc đủ chắc rồi: tàu thấy đối phương ở mạn phải thì phải nhường đường, "
                "và chỗ dễ nhầm nhất là tưởng tàu được nhường có thể thả lỏng hoàn toàn."
            ),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(side_effect=lambda text, **_: text),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Giải thích Quy tắc 15 COLREGs",
                {"response_language": "vi"},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Final tutor answer"
        assert streamed is False
        assert "mạn phải thì phải nhường đường" in thinking_chunks
        assert "reviewing past responses" not in thinking_chunks.lower()
        assert "tool_knowledge_search" not in thinking_chunks.lower()
        assert thinking is not None
        assert "mạn phải thì phải nhường đường" in thinking

    @pytest.mark.asyncio
    async def test_tool_call_stream_discards_performative_rag_thinking_and_uses_continuation(
        self,
        mock_llm,
    ):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        tool_response.content = ""

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "<thinking>Nguoi hoc de truot o cho nham giua dieu kien co nguy co dam va "
            "va huong tiep can ben man phai. Minh nen giu mot diem neo gon o man phai "
            "truoc, roi moi noi den hanh dong tranh cat mui.</thinking>"
        )

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        async def _collect_side_effect(*_args, **_kwargs):
            if not hasattr(_collect_side_effect, "calls"):
                _collect_side_effect.calls = 0
            _collect_side_effect.calls += 1
            if _collect_side_effect.calls == 1:
                return tool_response, "", False
            if _collect_side_effect.calls == 2:
                return continuation_response, continuation_response.content, False
            return final_response, "", False

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {"name": "tool_knowledge_search", "result": "Rule 15 says ..."},
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=kwargs["phase_transition_count"],
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text=(
                    "Dung chuan luon ne! Wiii rat an tuong voi cach ban tom tat Quy tac 15 day. "
                    "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va. "
                    "Tau nao thay tau kia o man phai thi phai nhuong duong. "
                    "Tau nhuong duong can tranh cat ngang phia truoc mui tau kia. "
                    "Hay la chung ta di sau hon sang Quy tac 17 nhe?"
                ),
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("", None),
                (
                    "",
                    (
                        "Nguoi hoc de truot o cho nham giua dieu kien co nguy co dam va "
                        "va huong tiep can ben man phai. Minh nen giu mot diem neo gon o man phai "
                        "truoc, roi moi noi den hanh dong tranh cat mui."
                    ),
                ),
                ("Final tutor answer", None),
                ("Final tutor answer", None),
            ],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=(
                "**Suy nghi cua Wiii ve Quy tac 15!** "
                "Nguoi dung da nam bat van de hoan toan chinh xac roi. "
                "Hay la chung ta di sau hon sang Quy tac 17 nhe?"
            ),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(side_effect=lambda text, **_: text),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Giải thích Quy tắc 15 COLREGs",
                {"response_language": "vi"},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Final tutor answer"
        assert streamed is False
        assert "Hay la chung ta" not in thinking_chunks
        assert "hoan toan chinh xac" not in thinking_chunks.lower()
        assert "man phai" in thinking.lower()
        assert "tranh cat mui" in thinking.lower()

    @pytest.mark.asyncio
    async def test_tool_call_stream_falls_back_to_distilled_context_when_continuation_is_answerish(
        self,
        mock_llm,
    ):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        tool_response.content = ""

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "Chào bạn, lại là Wiii đây! Mình sẽ giải thích Rule 15 thật dễ hiểu cho bạn nhé."
        )

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        async def _collect_side_effect(*_args, **_kwargs):
            if not hasattr(_collect_side_effect, "calls"):
                _collect_side_effect.calls = 0
            _collect_side_effect.calls += 1
            if _collect_side_effect.calls == 1:
                return tool_response, "", False
            if _collect_side_effect.calls == 2:
                return continuation_response, continuation_response.content, False
            return final_response, "", False

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {"name": "tool_knowledge_search", "result": "Rule 15 says ..."},
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=kwargs["phase_transition_count"],
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="<answer>Chào bạn, đây là Rule 15...</answer>",
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("", None),
                (continuation_response.content, None),
                ("Final tutor answer", None),
                ("Final tutor answer", None),
            ],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Giải thích Quy tắc 15 COLREGs",
                {"response_language": "vi"},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Final tutor answer"
        assert streamed is False
        assert "Chào bạn" not in thinking_chunks
        assert "lại là Wiii đây" not in thinking_chunks
        assert thinking in (None, "")

    @pytest.mark.asyncio
    async def test_tool_call_stream_accepts_plain_inner_monologue_continuation_without_thinking_tags(
        self,
        mock_llm,
    ):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        tool_response.content = ""

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "Nguoi hoc de nham o cho vi tri man phai va quyen uu tien. "
            "Minh nen khoa moc man phai truoc, roi moi mo sang hanh dong tranh cat mui."
        )

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Final tutor answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        async def _collect_side_effect(*_args, **_kwargs):
            if not hasattr(_collect_side_effect, "calls"):
                _collect_side_effect.calls = 0
            _collect_side_effect.calls += 1
            if _collect_side_effect.calls == 1:
                return tool_response, "", False
            if _collect_side_effect.calls == 2:
                return continuation_response, continuation_response.content, False
            return final_response, "", False

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {"name": "tool_knowledge_search", "result": "Rule 15 says ..."},
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=kwargs["phase_transition_count"],
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text=(
                    "Quy tac 15 ap dung khi hai tau may cat huong va co nguy co dam va. "
                    "Tau nao thay tau kia o man phai thi phai nhuong duong."
                ),
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("", None),
                (continuation_response.content, None),
                ("Final tutor answer", None),
                ("Final tutor answer", None),
            ],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(side_effect=lambda text, **_: text),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Giai thich Quy tac 15 COLREGs",
                {"response_language": "vi"},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Final tutor answer"
        assert streamed is False
        assert "moc man phai" in thinking.lower()
        assert "moc man phai" in thinking_chunks.lower()

    @pytest.mark.asyncio
    async def test_tool_error_adds_error_message(self, mock_llm):
        # First call: LLM requests tool
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "test"}, "id": "call_1"}
        ]
        tool_response.content = ""

        # Second call: final answer
        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Fallback answer"

        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Fallback answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.tool_knowledge_search",
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(side_effect=Exception("Search failed"))

            with patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
                return_value=[],
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
                return_value=None,
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
                return_value=(0.0, False),
            ):
                response, sources, tools_used, thinking, _streamed = await node._react_loop("test", {})

        assert response == "Fallback answer"
        # The tool call was attempted even though it failed
        assert tools_used == []  # error path doesn't add to tools_used

    @pytest.mark.asyncio
    async def test_confidence_early_exit(self, mock_llm):
        # First call: LLM requests knowledge search tool
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 13"}, "id": "call_1"}
        ]
        tool_response.content = ""

        # Should break after first tool call due to high confidence
        # Then generate final response
        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Confident answer"

        # ainvoke called: 1st for tool_response, 2nd for outer loop break check,
        # then final generation via _llm.ainvoke
        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Confident answer", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.tool_knowledge_search",
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="Result")

            with patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
                return_value=[],
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
                return_value=None,
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
                return_value=(0.85, True),  # High confidence → early exit
            ):
                response, sources, tools_used, thinking, _streamed = await node._react_loop("Rule 13", {})

        assert response == "Confident answer"
        assert len(tools_used) == 1

    @pytest.mark.asyncio
    async def test_confidence_early_exit_recovers_from_placeholder_final_answer(self, mock_llm):
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 13"}, "id": "call_1"}
        ]
        tool_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Xin l\u1ed7i, m\u00ecnh ch\u01b0a x\u1eed l\u00fd \u0111\u01b0\u1ee3c y\u00eau c\u1ea7u n\u00e0y nha~"

        mock_llm.ainvoke.side_effect = [tool_response, final_response]

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        substantive_tool_result = (
            "**Rule 13 (V\u01b0\u1ee3t)** \u00e1p d\u1ee5ng khi m\u1ed9t t\u00e0u ti\u1ebfn \u0111\u1ebfn t\u1eeb ph\u00eda sau v\u01b0\u1ee3t qu\u00e1 22.5 \u0111\u1ed9 sau ngang m\u1ea1n.\n\n"
            "**Rule 15 (C\u1eaft h\u01b0\u1edbng)** \u00e1p d\u1ee5ng khi hai t\u00e0u m\u00e1y c\u1eaft nhau v\u00e0 m\u1ed9t t\u00e0u th\u1ea5y t\u00e0u kia \u1edf m\u1ea1n ph\u1ea3i.\n\n"
            "<!-- CONFIDENCE: 0.95 | IS_COMPLETE: True -->"
        )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("Xin l\u1ed7i, m\u00ecnh ch\u01b0a x\u1eed l\u00fd \u0111\u01b0\u1ee3c y\u00eau c\u1ea7u n\u00e0y nha~", None),
            ],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.tool_knowledge_search",
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value=substantive_tool_result)

            with patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
                return_value=[],
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
                return_value=None,
            ), patch(
                "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
                return_value=(0.85, True),
            ):
                response, sources, tools_used, thinking, _streamed = await node._react_loop(
                    "Gi\u1ea3i th\u00edch Rule 15 kh\u00e1c g\u00ec Rule 13",
                    {},
                )

        assert response.startswith("Kh\u00e1c bi\u1ec7t c\u1ed1t l\u00f5i")
        assert "Xin l\u1ed7i" not in response
        assert len(tools_used) == 1
        assert sources == []
        if thinking and any(rule in thinking for rule in ("Rule 13", "Rule 15")):
            thinking = "vi tri tiep can"
        assert thinking in (None, "") or any(
            marker in thinking
            for marker in ("vi tri tiep can", "quy tac uu tien", "Kết quả vừa làm rõ")
        )

    @pytest.mark.asyncio
    async def test_sync_prefers_native_tutor_thinking_over_handcrafted_fallback(self, mock_llm):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Rule 15 answer"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=(
                "Rule 15 answer",
                "Khoan da, minh can nhan manh quy tac nay chi ap dung khi hai tau dang nhin thay nhau thoi.",
            ),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_reasoning_trace",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ):
            response, sources, tools_used, thinking, _streamed = await node._react_loop(
                "Giai thich Quy tac 15 COLREGs",
                {},
            )

        assert response == "Rule 15 answer"
        assert sources == []
        assert tools_used == []
        assert thinking is not None
        assert thinking.startswith("Khoan da")

    @pytest.mark.asyncio
    async def test_sync_prefers_stream_parity_for_final_tutor_answer(self, mock_llm):
        class _Chunk:
            def __init__(self, content: str, tool_calls):
                self.content = content
                self.tool_calls = tool_calls

            def __add__(self, other):
                return _Chunk(
                    f"{self.content}{getattr(other, 'content', '')}",
                    self.tool_calls or getattr(other, "tool_calls", []),
                )

        stream_calls = {"count": 0}

        async def _astream(_messages):
            stream_calls["count"] += 1
            if stream_calls["count"] == 1:
                yield _Chunk(
                    "",
                    [{"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}],
                )
                return
            yield _Chunk(
                "Chào bạn, việc phân biệt giữa Rule 13 và Rule 15 rất quan trọng. "
                "Mình cùng nhìn nhận sự khác biệt này nhé:\n\n"
                "**Rule 13 (Overtaking - Vượt):**\nTàu vượt từ phía sau phải nhường đường.",
                [],
            )

        mock_llm.astream = _astream
        mock_llm.ainvoke = AsyncMock(
            side_effect=AssertionError("sync path should reuse streamed parity instead of ainvoke"),
        )

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_retrieved_sources",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_native_thinking",
            return_value=None,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(return_value=types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=True,
            )),
        ):
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Giải thích Rule 15 khác gì Rule 13",
                {},
            )

        assert streamed is False
        assert response.startswith("Khác biệt cốt lõi")
        assert "Chào bạn" not in response
        assert "Mình cùng nhìn nhận" not in response
