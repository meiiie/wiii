from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from tests.unit.tutor_agent_node_helpers import (
    _make_tutor,
    base_state as base_state,
    mock_llm as mock_llm,
)


class TestTutorProcess:
    @pytest.mark.asyncio
    async def test_process_happy_path(self, mock_llm, base_state):
        # LLM returns direct answer (no tool calls)
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Rule 13 quy định về tàu vượt."
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Rule 13 quy định về tàu vượt.", None),
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

        assert result["tutor_output"] == "Rule 13 quy định về tàu vượt."
        assert result["current_agent"] == "tutor_agent"
        assert result["agent_outputs"]["tutor"] == result["tutor_output"]

    @pytest.mark.asyncio
    async def test_process_llm_unavailable_fallback(self, base_state):
        node = _make_tutor(llm=None, llm_with_tools=None)

        with patch(
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

        assert "Giải thích COLREGs Rule 13" in result["tutor_output"]
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_process_exception_sets_error(self, mock_llm, base_state):
        mock_llm.ainvoke.side_effect = Exception("LLM crash")
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.clear_retrieved_sources",
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ):
            result = await node.process(base_state)

        assert "error" in result
        assert result["error"] == "tutor_error"
        assert result["sources"] == []
        assert result["tools_used"] == []

    @pytest.mark.asyncio
    async def test_process_propagates_thinking(self, mock_llm, base_state):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Answer text"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=(
                "Answer text",
                "Voi Rule 13, cho de lech nhat la nham giua dieu kien vuot va tinh huong cat mat. Minh can chot tung moc truoc khi giai thich.",
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
            result = await node.process(base_state)

        assert "thinking" in result
        assert result["thinking"]
        assert "Answer text" not in result["thinking"]
        assert (
            "cho de" in result["thinking"].lower()
            or "nguoi hoc" in result["thinking"].lower()
            or "giai thich" in result["thinking"].lower()
        )

    @pytest.mark.asyncio
    async def test_process_aligns_visible_thinking_to_turn_language(self, mock_llm, base_state):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Answer text"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        base_state["context"]["response_language"] = "vi"
        aligned_visible_thinking = (
            "Nguoi dung dang hoi ve Rule 15. "
            "Minh can chot diem neo truoc khi phan giai thich bi troi."
        )

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=(
                "Answer text",
                (
                    "Okay, the user is asking about Rule 15. "
                    "I need to anchor the trigger first before the explanation drifts."
                ),
            ),
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.align_visible_thinking_language",
            new=AsyncMock(return_value=aligned_visible_thinking),
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

        assert "thinking" in result
        assert result["thinking"] == aligned_visible_thinking
        assert result["thinking_content"] == result["thinking"]

    @pytest.mark.asyncio
    async def test_process_does_not_invent_tutor_thinking_when_native_thinking_missing(
        self,
        mock_llm,
        base_state,
    ):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Answer text"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        base_state["query"] = "Giải thích Rule 15 khác gì Rule 13"
        base_state["context"] = {
            "user_id": "user-123",
            "organization_id": None,
            "mood_hint": "",
            "personality_mode": None,
        }

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Answer text", None),
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
    async def test_process_propagates_crag_trace(self, mock_llm, base_state):
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Answer"
        mock_llm.ainvoke.return_value = response_msg

        mock_trace = MagicMock()
        mock_trace.total_steps = 3

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Answer", None),
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
            return_value=mock_trace,
        ), patch(
            "app.engine.multi_agent.agents.tutor_node.get_last_confidence",
            return_value=(0.0, False),
        ):
            result = await node.process(base_state)

        assert result["reasoning_trace"] is mock_trace

    @pytest.mark.asyncio
    async def test_process_commits_runtime_provider_and_model(self, mock_llm, base_state):
        mock_llm._wiii_provider_name = "zhipu"
        mock_llm._wiii_model_name = "glm-5"
        response_msg = MagicMock()
        response_msg.tool_calls = []
        response_msg.content = "Answer"
        mock_llm.ainvoke.return_value = response_msg

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Answer", None),
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

        assert result["_execution_provider"] == "zhipu"
        assert result["_execution_model"] == "glm-5"
        assert result["model"] == "glm-5"

    @pytest.mark.asyncio
    async def test_process_filters_legacy_visual_tools_for_structured_visual_intent(self, base_state):
        class _Tool:
            def __init__(self, name: str):
                self.name = name

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        node._llm = mock_llm
        node._tools = [
            _Tool("tool_knowledge_search"),
            _Tool("tool_think"),
            _Tool("tool_report_progress"),
            _Tool("tool_generate_interactive_chart"),
            _Tool("tool_generate_visual"),
        ]

        state = {
            **base_state,
            "query": "Explain Kimi linear attention in charts",
            "routing_metadata": {"intent": "learning"},
        }

        with patch(
            "app.engine.multi_agent.agents.tutor_node.settings.enable_structured_visuals",
            True,
        ), patch(
            "app.engine.skills.skill_recommender.select_runtime_tools",
            return_value=[
                _Tool("tool_generate_interactive_chart"),
                _Tool("tool_generate_visual"),
                _Tool("tool_knowledge_search"),
            ],
        ), patch.object(
            node,
            "_react_loop",
            AsyncMock(return_value=("Visual answer", [], [], None, False)),
        ):
            result = await node.process(state)

        bound_tools = mock_llm.bind_tools.call_args[0][0]
        bound_names = [tool.name for tool in bound_tools]
        policy = state["_tool_policy_session"]

        assert "tool_generate_visual" in bound_names
        assert "tool_generate_interactive_chart" not in bound_names
        assert policy["path"] == "tutor"
        assert policy["reason"] == "tutor_tool_setup"
        assert "tool_generate_visual" in policy["visible_tool_names"]
        assert "tool_generate_interactive_chart" not in policy["visible_tool_names"]
        assert policy["tool_capabilities"]["tool_generate_visual"]["group"] == "visual"
        assert result["tutor_output"] == "Visual answer"

    def test_build_system_prompt_mentions_structured_visual_priority(self, mock_llm, base_state):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.settings.enable_structured_visuals",
            True,
        ):
            prompt = node._build_system_prompt(
                base_state["context"],
                "Hay mo phong vat ly con lac co the keo tha",
            )

        assert "tool_generate_visual" in prompt
        assert "widget/chart legacy" in prompt
