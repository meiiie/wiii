"""
Tests for TutorAgentNode - Teaching Specialist (SOTA ReAct Pattern).

Tests ReAct loop, tool execution, thinking extraction, prompt building,
fallback response, and state wiring.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.agent_config import AgentConfigRegistry

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Lazy import inside _build_system_prompt() does:
#   from app.domains.registry import get_domain_registry
# Patch at SOURCE module.
DOMAIN_REGISTRY_PATCH = "app.domains.registry.get_domain_registry"

_SENTINEL = object()


def _make_tutor(llm=None, llm_with_tools=_SENTINEL):
    """Create TutorAgentNode with mocked LLM and tools.

    Args:
        llm: Mock for self._llm. None = unavailable.
        llm_with_tools: Mock for self._llm_with_tools.
            _SENTINEL (default) = use whatever _init_llm() produces.
            None = explicitly set _llm_with_tools to None (for testing unavailable).
            MagicMock = override with that mock.
    """
    with patch.object(
        AgentConfigRegistry, "get_llm", return_value=llm,
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.get_prompt_loader",
    ) as mock_loader_fn:
        mock_loader = MagicMock()
        mock_loader.build_system_prompt.return_value = "You are Wiii Tutor."
        mock_loader_fn.return_value = mock_loader

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()

        # Override _llm_with_tools if explicitly specified
        if llm_with_tools is not _SENTINEL:
            node._llm_with_tools = llm_with_tools

        return node


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def base_state():
    return {
        "query": "Giải thích COLREGs Rule 13",
        "context": {
            "user_name": "Minh",
            "user_role": "student",
            "pronoun_style": {"user_called": "em", "ai_self": "thầy"},
        },
        "learning_context": {},
    }


# ---------------------------------------------------------------------------
# process() tests
# ---------------------------------------------------------------------------

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
            return_value=("Answer text", "Deep thinking here"),
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

        assert result["thinking"] == "Deep thinking here"

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


# ---------------------------------------------------------------------------
# _react_loop() tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _build_system_prompt() tests
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    def test_basic_prompt_construction(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("no registry")):
            prompt = node._build_system_prompt(
                {"user_name": "Minh", "user_role": "student"},
                "test query",
            )

        assert "Wiii Tutor" in prompt or "You are" in prompt
        assert "test query" in prompt

    def test_prompt_includes_skill_context(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("no registry")):
            prompt = node._build_system_prompt(
                {"user_name": "Minh", "skill_context": "## COLREGs Overview"},
                "query",
            )

        assert "COLREGs Overview" in prompt

    def test_prompt_includes_capability_context(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("no registry")):
            prompt = node._build_system_prompt(
                {"user_name": "Minh", "capability_context": "Capability handbook phù hợp lúc này:\n- tool_knowledge_search"},
                "query",
            )

        assert "Capability handbook phù hợp lúc này" in prompt

    def test_prompt_uses_domain_tool_instruction(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        mock_domain = MagicMock()
        mock_domain.get_tool_instruction.return_value = "## CUSTOM TOOL INSTRUCTION"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_domain

        with patch(DOMAIN_REGISTRY_PATCH, return_value=mock_registry):
            prompt = node._build_system_prompt({"domain_id": "maritime"}, "query")

        assert "CUSTOM TOOL INSTRUCTION" in prompt


# ---------------------------------------------------------------------------
# _extract_content() / _extract_content_with_thinking()
# ---------------------------------------------------------------------------

class TestExtractContent:
    def test_extract_content_with_thinking_returns_tuple(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(
            "app.engine.multi_agent.agents.tutor_node.extract_thinking_from_response",
            return_value=("Answer", "Thinking process"),
        ):
            text, thinking = node._extract_content_with_thinking("raw content")

        assert text == "Answer"
        assert thinking == "Thinking process"


# ---------------------------------------------------------------------------
# _fallback_response()
# ---------------------------------------------------------------------------

class TestFallbackResponse:
    def test_fallback_includes_query(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        result = node._fallback_response("COLREGs Rule 13")
        assert "COLREGs Rule 13" in result
        assert "tài liệu" in result.lower() or "bài tập" in result.lower()


# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------

class TestTutorIsAvailable:
    def test_available_with_both_llms(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        assert node.is_available() is True

    def test_not_available_without_llm(self):
        node = _make_tutor(llm=None, llm_with_tools=None)
        assert node.is_available() is False

    def test_not_available_without_tools(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=None)
        assert node.is_available() is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestTutorSingleton:
    def test_get_tutor_agent_node_returns_instance(self):
        import app.engine.multi_agent.agents.tutor_node as mod
        mod._tutor_node = None
        try:
            with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
                with patch.object(mod, "get_prompt_loader", return_value=MagicMock()):
                    node = mod.get_tutor_agent_node()
                    assert isinstance(node, mod.TutorAgentNode)
                    node2 = mod.get_tutor_agent_node()
                    assert node is node2
        finally:
            mod._tutor_node = None
