import asyncio
import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from tests.unit.tutor_agent_node_helpers import (
    _make_tutor,
    base_state as base_state,
    mock_llm as mock_llm,
)


class TestTutorPublicThinkingSanitization:
    @pytest.mark.asyncio
    async def test_process_suppresses_raw_llm_planner_thinking_from_user_review(self, mock_llm, base_state):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Rule 15 giải thích ngắn gọn."
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        base_state["context"]["response_language"] = "en"

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Rule 15 giải thích ngắn gọn.", "Okay, here's my interpretation before I answer."),
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
            result = await node.process(base_state)

        assert result.get("thinking") in (None, "")

    @pytest.mark.asyncio
    async def test_tool_call_stream_suppresses_answerish_pretool_text_when_no_native_thinking_exists(self, mock_llm):
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
                    "Rule 15 trong COLREGs tập trung vào tình huống cắt mặt.",
                    [{"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}],
                )
                return
            yield _Chunk("Rule 15 answer from knowledge base", [])

        mock_llm.astream = _astream

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Rule 15 answer from knowledge base", None),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node._iteration_beat",
            AsyncMock(return_value=types.SimpleNamespace(
                label="Phan tich cau hoi",
                summary="Minh canh lai cach mo bai truoc khi keo tri thuc len.",
                phase="clarify",
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
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(return_value=types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=True,
            )),
        ), patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=None,
        ):
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Rule 15",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )
        answer_chunks = "".join(
            event["content"] for event in events if event.get("type") == "answer_delta"
        )

        assert response == "Rule 15 answer from knowledge base"
        assert streamed is False
        assert thinking_chunks == ""
        assert answer_chunks == ""

    @pytest.mark.asyncio
    async def test_tool_think_keeps_raw_thought_out_of_public_thinking(self, mock_llm):
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
                    [{"name": "tool_think", "args": {"thought": "Chao ban, minh se giai thich ngay cho ban nhe."}, "id": "call_1"}],
                )
                return
            yield _Chunk("Rule 15 answer", [])

        mock_llm.astream = _astream

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Rule 15 answer", None),
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
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Rule 15 khac gi Rule 13",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Rule 15 answer"
        assert streamed is False
        assert "Chao ban, minh se giai thich ngay cho ban nhe." not in thinking_chunks
        assert thinking_chunks == ""

    @pytest.mark.asyncio
    async def test_pre_tool_stream_text_surfaces_as_raw_thinking_when_native_thinking_missing(self, mock_llm):
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        response_with_tool.content = ""

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Rule 15 answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()
        captured_system_prompts = []
        captured_human_prompts = []
        captured_human_prompts = []

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {
                        "name": "tool_knowledge_search",
                        "result": "Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
                        "id": "call_1",
                    },
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
            )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(
                side_effect=[
                    (
                        response_with_tool,
                        "The user is trying to pin down when Rule 15 really triggers, so I should lock that condition before the explanation drifts.",
                        False,
                    ),
                    (response_final, "", False),
                ]
            ),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            side_effect=[
                ("", None),
                ("Rule 15 answer", None),
                ("Rule 15 answer", None),
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
            AsyncMock(return_value=types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=True,
            )),
        ):
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Rule 15",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Rule 15 answer"
        assert streamed is False
        assert "trying to pin down when Rule 15 really triggers" in thinking_chunks

    @pytest.mark.asyncio
    async def test_stream_surfaces_second_post_tool_thinking_interval_when_tool_thought_is_missing(self, mock_llm):
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        response_with_tool.content = (
            "<thinking>Minh can chot dieu kien kich hoat cua Rule 15 truoc khi di vao cach nhuong duong.</thinking>"
        )

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "<thinking>Ket qua vua lo ra moc can neo that ro: tau thay doi phuong o man phai moi la tau phai nhuong, "
            "nen luc giai thich can bat dau tu goc nhin cua nguoi cam lai thay vi doc nguyen van dieu luat.</thinking>"
        )

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Rule 15 answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()
        captured_system_prompts = []
        captured_human_prompts = []

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {
                        "name": "tool_knowledge_search",
                        "result": "Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
                        "id": "call_1",
                    },
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
            )

        async def _collect_side_effect(*args, **kwargs):
            messages = []
            if len(args) >= 2:
                messages = args[1] or []
            elif "messages" in kwargs:
                messages = kwargs["messages"] or []
            if messages:
                first_content = messages[0]["content"] if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
                if isinstance(first_content, str):
                    captured_system_prompts.append(first_content)
                if len(messages) > 1:
                    second_content = messages[1]["content"] if isinstance(messages[1], dict) else getattr(messages[1], "content", "")
                    if isinstance(second_content, str):
                        captured_human_prompts.append(second_content)
            call_index = len(captured_system_prompts)
            if call_index == 1:
                return (response_with_tool, "", False)
            if call_index == 2:
                return (continuation_response, "", False)
            return (response_final, "", False)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
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
            return_value=(0.85, True),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Giải thích Rule 15",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        event_types = [event.get("type") for event in events]
        thinking_starts = [idx for idx, kind in enumerate(event_types) if kind == "thinking_start"]
        tool_result_index = event_types.index("tool_result")

        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Rule 15 answer"
        assert streamed is False
        assert len(thinking_starts) >= 2
        assert thinking_starts[1] > tool_result_index
        assert "Minh can chot dieu kien kich hoat" in thinking_chunks
        assert "Ket qua vua lo ra moc can neo that ro" in thinking_chunks
        assert len(captured_system_prompts) >= 2
        assert len(captured_human_prompts) >= 2
        assert "--- WIII HOUSE CORE (TUTOR) ---" in captured_system_prompts[1]
        assert "Wiii Tutor" in captured_system_prompts[1]
        assert "Day van la Wiii" in captured_system_prompts[1]
        assert "## WIII CONTINUATION MODE" in captured_system_prompts[1]
        assert "## VÍ DỤ NHANH" in captured_system_prompts[1]
        assert "người học" in captured_system_prompts[1].lower()
        assert "KHÔNG lập dàn ý câu trả lời" in captured_system_prompts[1]
        assert "KHÔNG đặt tiêu đề markdown tiếng Anh" in captured_system_prompts[1]
        assert "## GOI Y DUNG TOOL" not in captured_system_prompts[1]

    @pytest.mark.asyncio
    async def test_post_tool_continuation_keeps_living_context_and_wiii_house_core_together(
        self,
        mock_llm,
    ):
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {"name": "tool_knowledge_search", "args": {"query": "Rule 15"}, "id": "call_1"}
        ]
        response_with_tool.content = (
            "<thinking>Minh can chot dieu kien kich hoat cua Rule 15 truoc khi di vao cach nhuong duong.</thinking>"
        )

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "<thinking>Ket qua vua lo ra moc can neo that ro: tau thay doi phuong o man phai moi la tau phai nhuong.</thinking>"
        )

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Rule 15 answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()
        captured_system_prompts = []
        captured_human_prompts = []

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {
                        "name": "tool_knowledge_search",
                        "result": "Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
                        "id": "call_1",
                    },
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="Rule 15 ap dung cho tinh huong cat huong, tau thay doi phuong o man phai thi phai nhuong duong.",
            )

        async def _collect_side_effect(*args, **kwargs):
            messages = []
            if len(args) >= 2:
                messages = args[1] or []
            elif "messages" in kwargs:
                messages = kwargs["messages"] or []
            if messages:
                first_content = messages[0]["content"] if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
                if isinstance(first_content, str):
                    captured_system_prompts.append(first_content)
                if len(messages) > 1:
                    second_content = messages[1]["content"] if isinstance(messages[1], dict) else getattr(messages[1], "content", "")
                    if isinstance(second_content, str):
                        captured_human_prompts.append(second_content)
            call_index = len(captured_system_prompts)
            if call_index == 1:
                return (response_with_tool, "", False)
            if call_index == 2:
                return (continuation_response, "", False)
            return (response_final, "", False)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
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
            return_value=(0.85, True),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            await node._react_loop(
                "Giải thích Rule 15",
                {
                    "living_context_prompt": "## Living Context Block V1\n- name: Wiii\n- identity_anchor: living-neo",
                    "user_id": "user-123",
                    "mood_hint": "Nguoi dung dang hoc Rule 15",
                    "personality_mode": "professional",
                },
                event_queue=queue,
            )

        assert len(captured_system_prompts) >= 2
        assert len(captured_human_prompts) >= 2
        assert "## Living Context Block V1" in captured_system_prompts[1]

    @pytest.mark.asyncio
    async def test_visual_tool_stream_surfaces_post_tool_living_continuation(self, mock_llm):
        visual_html = (
            "<div><h3>Quy tac 15: Cat huong</h3>"
            "<p>Tau thay doi phuong ben man phai thi phai nhuong duong.</p>"
            "<p>Can tranh cat mui va giu moc man phai de nguoi hoc khong nham.</p></div>"
        )
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {
                "name": "tool_generate_visual",
                "args": {
                    "title": "Rule 15 visual",
                    "code_html": visual_html,
                },
                "id": "call_visual",
            }
        ]
        response_with_tool.content = ""

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "<thinking>Visual nay khoa duoc vai tro cua tau nhuong duong va tau duoc nhuong, "
            "nhung minh van can giu diem neo o cho de nham nhat: nguoi hoc rat de quen mat "
            "rang nhin thay o man phai moi la luc phai nhuong.</thinking>"
        )

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Visual answer"

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()
        captured_system_prompts = []
        captured_human_prompts = []

        async def _dispatch_side_effect(**kwargs):
            await kwargs["push"](
                {
                    "type": "tool_result",
                    "content": {
                        "name": "tool_generate_visual",
                        "result": "{\"claim\":\"Chart trong mot khung nhin truc quan de doc nhanh.\",\"title\":\"Runtime benchmark\",\"pedagogical_role\":\"benchmark\",\"visual_type\":\"chart\",\"renderer_kind\":\"inline_html\",\"presentation_intent\":\"chart_runtime\"}",
                        "id": "call_visual",
                    },
                    "node": "tutor_agent",
                }
            )
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=False,
                tool_result_text="{\"claim\":\"Chart trong mot khung nhin truc quan de doc nhanh.\",\"title\":\"Runtime benchmark\",\"pedagogical_role\":\"benchmark\",\"visual_type\":\"chart\",\"renderer_kind\":\"inline_html\",\"presentation_intent\":\"chart_runtime\"}",
                tool_args={"title": "Rule 15 visual", "code_html": visual_html},
            )

        async def _collect_side_effect(*args, **kwargs):
            messages = []
            if len(args) >= 2:
                messages = args[1] or []
            elif "messages" in kwargs:
                messages = kwargs["messages"] or []
            if messages:
                first_content = messages[0]["content"] if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
                if isinstance(first_content, str):
                    captured_system_prompts.append(first_content)
                if len(messages) > 1:
                    second_content = messages[1]["content"] if isinstance(messages[1], dict) else getattr(messages[1], "content", "")
                    if isinstance(second_content, str):
                        captured_human_prompts.append(second_content)
            call_index = len(captured_system_prompts)
            if call_index == 1:
                return (response_with_tool, "", False)
            if call_index == 2:
                return (continuation_response, "", False)
            return (response_final, "", False)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
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
            return_value=(0.85, True),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, _thinking, streamed = await node._react_loop(
                "Tao visual Quy tac 15",
                {},
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        event_types = [event.get("type") for event in events]
        thinking_starts = [idx for idx, kind in enumerate(event_types) if kind == "thinking_start"]
        tool_result_index = event_types.index("tool_result")
        thinking_chunks = "".join(
            event["content"] for event in events if event.get("type") == "thinking_delta"
        )

        assert response == "Visual answer"
        assert streamed is False
        assert len(thinking_starts) >= 2
        assert thinking_starts[1] > tool_result_index
        assert "Visual nay khoa duoc vai tro" in thinking_chunks
        assert "## WIII CONTINUATION MODE" in captured_system_prompts[1]
        assert "visual vua duoc tao" in captured_system_prompts[1]
        assert "cat huong" in captured_human_prompts[1].lower()
        assert "man phai" in captured_human_prompts[1].lower()
        assert "rule 15 visual" in captured_human_prompts[1].lower()
        assert "runtime benchmark" not in captured_human_prompts[1].lower()
        assert "--- WIII HOUSE CORE (TUTOR) ---" in captured_system_prompts[1]
        assert "visual" in captured_human_prompts[1].lower()
        assert "Chao ban" not in captured_human_prompts[1]
        assert "de minh giai thich" not in captured_human_prompts[1].lower()
        assert ("Bông" in captured_system_prompts[1]) or ("Bong" in captured_system_prompts[1])

    @pytest.mark.asyncio
    async def test_sync_falls_back_to_post_tool_continuation_when_visual_turn_has_no_native_thinking(
        self,
        mock_llm,
    ):
        visual_html = (
            "<div><p>Tau thay doi phuong o man phai thi phai nhuong duong.</p>"
            "<p>Can tranh cat ngang mui tau duoc nhuong.</p></div>"
        )
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {
                "name": "tool_generate_visual",
                "args": {
                    "title": "Rule 15 visual",
                    "code_html": visual_html,
                },
                "id": "call_visual",
            }
        ]
        response_with_tool.content = ""

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Visual answer"

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = (
            "<thinking>Visual nay giu duoc moc man phai kha ro, va diem can neo tiep theo la nhac nguoi hoc "
            "rang tau phai nhuong nen tranh cat ngang mui tau kia.</thinking>"
        )

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        captured_system_prompts = []
        captured_human_prompts = []

        async def _dispatch_side_effect(**_kwargs):
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=True,
                tool_result_text=(
                    "{\"claim\":\"Rule 15 visual\",\"visual_type\":\"inline_html\","
                    "\"renderer_kind\":\"inline_html\",\"pedagogical_role\":\"explanation\"}"
                ),
                tool_args={"title": "Rule 15 visual", "code_html": visual_html},
            )

        async def _collect_side_effect(*args, **kwargs):
            messages = []
            if len(args) >= 2:
                messages = args[1] or []
            elif "messages" in kwargs:
                messages = kwargs["messages"] or []
            if messages:
                first_content = messages[0]["content"] if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
                if isinstance(first_content, str):
                    captured_system_prompts.append(first_content)
                if len(messages) > 1:
                    second_content = messages[1]["content"] if isinstance(messages[1], dict) else getattr(messages[1], "content", "")
                    if isinstance(second_content, str):
                        captured_human_prompts.append(second_content)

            call_index = len(captured_system_prompts)
            if call_index == 1:
                return (response_with_tool, "", False)
            if call_index == 2:
                return (response_final, "", False)
            return (continuation_response, "", False)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
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
            return_value=(0.85, True),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Tao visual Quy tac 15",
                {},
                event_queue=None,
            )

        assert response == "Visual answer"
        assert streamed is False
        assert "moc man phai" in thinking.lower()
        assert "tranh cat ngang mui" in thinking.lower()
        assert len(captured_system_prompts) >= 3
        assert "## WIII CONTINUATION MODE" in captured_system_prompts[-1]
        assert "visual vua duoc tao" in captured_system_prompts[-1]
        assert "tin hieu" in captured_human_prompts[-1].lower()

    @pytest.mark.asyncio
    async def test_sync_uses_distilled_visual_fallback_when_continuation_is_answerish(
        self,
        mock_llm,
    ):
        visual_html = (
            "<div><p>Tau thay doi phuong o man phai thi phai nhuong duong.</p>"
            "<p>Can tranh cat ngang mui tau duoc nhuong.</p></div>"
        )
        response_with_tool = MagicMock()
        response_with_tool.tool_calls = [
            {
                "name": "tool_generate_visual",
                "args": {
                    "title": "Rule 15 visual",
                    "code_html": visual_html,
                },
                "id": "call_visual",
            }
        ]
        response_with_tool.content = ""

        response_final = MagicMock()
        response_final.tool_calls = []
        response_final.content = "Visual answer"

        continuation_response = MagicMock()
        continuation_response.tool_calls = []
        continuation_response.content = "Chao ban, de minh giai thich visual nay theo tung muc cho de nho."

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        async def _dispatch_side_effect(**_kwargs):
            return types.SimpleNamespace(
                phase_transition_count=0,
                last_tool_was_progress=False,
                should_break_loop=True,
                tool_result_text=(
                    "{\"claim\":\"Rule 15 visual\",\"visual_type\":\"inline_html\","
                    "\"renderer_kind\":\"inline_html\",\"pedagogical_role\":\"explanation\"}"
                ),
                tool_args={"title": "Rule 15 visual", "code_html": visual_html},
            )

        async def _collect_side_effect(*_args, **_kwargs):
            if not hasattr(_collect_side_effect, "calls"):
                _collect_side_effect.calls = 0
            _collect_side_effect.calls += 1
            if _collect_side_effect.calls == 1:
                return (response_with_tool, "", False)
            if _collect_side_effect.calls == 2:
                return (response_final, "", False)
            return (continuation_response, "", False)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.collect_tutor_model_message",
            AsyncMock(side_effect=_collect_side_effect),
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
            return_value=(0.85, True),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(side_effect=lambda text, **_: text),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.dispatch_tutor_tool_call",
            AsyncMock(side_effect=_dispatch_side_effect),
        ):
            response, _sources, _tools_used, thinking, streamed = await node._react_loop(
                "Tao visual Quy tac 15",
                {},
                event_queue=None,
            )

        assert response == "Visual answer"
        assert streamed is False
        assert "chao ban" not in thinking.lower()
        assert any(
            marker in thinking.lower()
            for marker in ("visual vừa khóa", "visual này khóa", "visual vua khoa", "visual nay khoa")
        )
        assert "rule 15 visual" in thinking.lower()
        assert "người học" in thinking.lower()

    @pytest.mark.asyncio
    async def test_final_generation_streams_curated_tutor_answer(self, mock_llm):
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

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        queue = asyncio.Queue()

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
                event_queue=queue,
            )

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        answer_chunks = "".join(
            event["content"] for event in events if event.get("type") == "answer_delta"
        )

        assert streamed is False
        assert not response.startswith("Chào bạn")
        assert response.startswith("Khác biệt cốt lõi")
        assert "Mình cùng nhìn nhận" not in response
        assert answer_chunks == ""
