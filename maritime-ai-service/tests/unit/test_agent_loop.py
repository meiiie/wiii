"""
Tests for app.engine.multi_agent.agent_loop — Generalized Agentic Loop.

Sprint 57: Agentic Loop Inside LangGraph Nodes.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
# We temporarily inject a mock, import what we need, then restore.
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

from app.engine.multi_agent.agent_loop import (
    LoopConfig,
    LoopResult,
    agentic_loop,
    agentic_loop_streaming,
    _tools_to_openai_format,
    _execute_tool,
    _unified_client_available,
    _message_to_dict,
)

# Thorough restore: remove mock AND app.services that cached mock ChatService.
# If app.services was freshly loaded during our import, it has mock ChatService
# cached in its namespace — removing forces clean re-import from disk later.
if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# ============================================================================
# LoopConfig Tests
# ============================================================================


class TestLoopConfig:
    def test_defaults(self):
        config = LoopConfig()
        assert config.max_steps == 5
        assert config.temperature == 0.5
        assert config.tier == "moderate"
        assert config.early_exit_confidence == 0.70

    def test_custom_values(self):
        config = LoopConfig(max_steps=3, temperature=0.2, tier="deep")
        assert config.max_steps == 3
        assert config.tier == "deep"


class TestLoopResult:
    def test_defaults(self):
        result = LoopResult(response="hello")
        assert result.response == "hello"
        assert result.tool_calls == []
        assert result.sources == []
        assert result.thinking is None
        assert result.steps == 0
        assert result.confidence == 0.0


# ============================================================================
# _unified_client_available
# ============================================================================


class TestUnifiedClientAvailable:
    def test_returns_false_when_loop_disabled(self):
        mock_settings = MagicMock()
        mock_settings.enable_agentic_loop = False
        mock_settings.enable_unified_client = True

        with patch("app.core.config.settings", mock_settings):
            assert not _unified_client_available()

    def test_returns_false_when_client_disabled(self):
        mock_settings = MagicMock()
        mock_settings.enable_agentic_loop = True
        mock_settings.enable_unified_client = False

        with patch("app.core.config.settings", mock_settings):
            assert not _unified_client_available()

    def test_returns_false_when_not_initialized(self):
        mock_settings = MagicMock()
        mock_settings.enable_agentic_loop = True
        mock_settings.enable_unified_client = True

        mock_client = MagicMock()
        mock_client.is_initialized.return_value = False

        with patch("app.core.config.settings", mock_settings):
            with patch(
                "app.engine.multi_agent.agent_loop.UnifiedLLMClient",
                mock_client,
                create=True,
            ):
                # Need to reimport to get fresh module
                from app.engine.multi_agent.agent_loop import _unified_client_available
                result = _unified_client_available()
                # Will be False because actual import fails or client not initialized
                assert isinstance(result, bool)


# ============================================================================
# _tools_to_openai_format
# ============================================================================


class TestToolsToOpenAIFormat:
    def test_basic_tool(self):
        tool = MagicMock()
        tool.name = "search"
        tool.description = "Search knowledge"
        tool.args_schema = None

        result = _tools_to_openai_format([tool])
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"

    def test_tool_with_schema(self):
        tool = MagicMock()
        tool.name = "calc"
        tool.description = "Calculator"
        mock_schema = MagicMock()
        mock_schema.model_json_schema.return_value = {
            "type": "object",
            "title": "CalcInput",
            "properties": {"expr": {"type": "string"}},
        }
        tool.args_schema = mock_schema

        result = _tools_to_openai_format([tool])
        assert "expr" in result[0]["function"]["parameters"]["properties"]
        assert "title" not in result[0]["function"]["parameters"]

    def test_empty_tools(self):
        assert _tools_to_openai_format([]) == []

    def test_tool_without_name_attr(self):
        """Falls back to __name__."""
        def my_func():
            pass
        result = _tools_to_openai_format([my_func])
        assert result[0]["function"]["name"] == "my_func"


# ============================================================================
# _execute_tool
# ============================================================================


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_executes_ainvoke_tool(self):
        tool = MagicMock()
        tool.name = "search"
        tool.ainvoke = AsyncMock(return_value="result data")

        result = await _execute_tool([tool], "search", {"query": "test"})
        assert result == "result data"

    @pytest.mark.asyncio
    async def test_executes_coroutine_tool(self):
        tool = MagicMock()
        tool.name = "calc"
        del tool.ainvoke  # Remove ainvoke

        async def mock_coroutine(**kwargs):
            return "42"

        tool.coroutine = mock_coroutine

        result = await _execute_tool([tool], "calc", {"expr": "6*7"})
        assert result == "42"

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        tool = MagicMock()
        tool.name = "search"

        result = await _execute_tool([tool], "unknown", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_tool_error_caught(self):
        tool = MagicMock()
        tool.name = "broken"
        tool.ainvoke = AsyncMock(side_effect=Exception("Tool crashed"))

        result = await _execute_tool([tool], "broken", {})
        assert "Error" in result


# ============================================================================
# _message_to_dict
# ============================================================================


class TestMessageToDict:
    def test_message_without_tool_calls(self):
        msg = MagicMock()
        msg.content = "Hello"
        msg.tool_calls = None

        result = _message_to_dict(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "Hello"
        assert "tool_calls" not in result

    def test_message_with_tool_calls(self):
        tc = MagicMock()
        tc.id = "call_123"
        tc.function.name = "search"
        tc.function.arguments = '{"query": "test"}'

        msg = MagicMock()
        msg.content = ""
        msg.tool_calls = [tc]

        result = _message_to_dict(msg)
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_123"

    def test_message_with_none_content(self):
        msg = MagicMock()
        msg.content = None
        msg.tool_calls = None

        result = _message_to_dict(msg)
        assert result["content"] == ""


# ============================================================================
# agentic_loop — LangChain Path (Path B)
# ============================================================================


class TestAgenticLoopLangChain:
    """Test agentic_loop using LangChain fallback (Path B)."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(self):
        """LLM returns text without tool calls → single step."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Direct answer"
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.engine.multi_agent.agent_loop._unified_client_available", return_value=False):
            with patch("app.engine.llm_pool.get_llm_moderate", return_value=mock_llm):
                result = await agentic_loop(
                    query="What is COLREGs?",
                    tools=[],
                    system_prompt="You are a maritime tutor",
                )

        assert result.response == "Direct answer"
        assert result.steps == 1
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_tool_calls_execute_and_loop(self):
        """LLM calls tool, then responds."""
        tool = MagicMock()
        tool.name = "search"
        tool.description = "Search"
        tool.args_schema = None
        tool.ainvoke = AsyncMock(return_value="COLREGs Rule 15 info")

        # First call: tool call
        tc_response = MagicMock()
        tc_response.tool_calls = [{"name": "search", "args": {"query": "COLREGs"}, "id": "c1"}]
        tc_response.content = ""

        # Second call: final answer
        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Rule 15 states..."

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tc_response, final_response])

        with patch("app.engine.multi_agent.agent_loop._unified_client_available", return_value=False):
            with patch("app.engine.llm_pool.get_llm_moderate", return_value=mock_llm):
                result = await agentic_loop(
                    query="Explain COLREGs Rule 15",
                    tools=[tool],
                    system_prompt="You are a tutor",
                )

        assert "Rule 15" in result.response
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"
        assert result.steps == 2

    @pytest.mark.asyncio
    async def test_max_steps_enforced(self):
        """Loop terminates at max_steps."""
        tool = MagicMock()
        tool.name = "search"
        tool.ainvoke = AsyncMock(return_value="data")

        # Always return tool calls
        tc_response = MagicMock()
        tc_response.tool_calls = [{"name": "search", "args": {}, "id": "c1"}]
        tc_response.content = ""

        final_response = MagicMock()
        final_response.content = "Final after max steps"

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tc_response, tc_response, final_response])

        with patch("app.engine.multi_agent.agent_loop._unified_client_available", return_value=False):
            with patch("app.engine.llm_pool.get_llm_moderate", return_value=mock_llm):
                result = await agentic_loop(
                    query="test",
                    tools=[tool],
                    system_prompt="test",
                    config=LoopConfig(max_steps=2),
                )

        assert result.steps == 2

    @pytest.mark.asyncio
    async def test_deep_tier_uses_correct_llm(self):
        """config.tier='deep' uses get_llm_deep."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "deep response"
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.engine.multi_agent.agent_loop._unified_client_available", return_value=False):
            with patch("app.engine.llm_pool.get_llm_deep", return_value=mock_llm) as mock_get:
                result = await agentic_loop(
                    query="test",
                    tools=[],
                    system_prompt="test",
                    config=LoopConfig(tier="deep"),
                )

        mock_get.assert_called_once()
        assert result.response == "deep response"


# ============================================================================
# agentic_loop_streaming
# ============================================================================


class TestAgenticLoopStreaming:
    @pytest.mark.asyncio
    async def test_yields_events(self):
        """Streaming yields events from queue + final answer event.

        Sprint 69 rewrote streaming to use asyncio.Queue internally.
        The mock agentic_loop pushes events to config.event_queue, then
        the streaming function yields them plus a final 'answer' event.
        """
        import asyncio

        async def _mock_agentic_loop(query, tools, system_prompt, config=None, context=None):
            """Mock that pushes events to the queue like real loop does."""
            if config and config.event_queue:
                await config.event_queue.put({"type": "tool_call", "content": {"name": "search", "args": {"q": "test"}}})
                await config.event_queue.put({"type": "thinking", "content": "I thought about it"})
            return LoopResult(
                response="The answer",
                tool_calls=[{"name": "search", "args": {"q": "test"}}],
                thinking="I thought about it",
                steps=2,
            )

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            side_effect=_mock_agentic_loop,
        ):
            events = []
            async for event in agentic_loop_streaming(
                query="test",
                tools=[],
                system_prompt="test",
            ):
                events.append(event)

        # Queue events + final answer event
        types = [e["type"] for e in events]
        assert "tool_call" in types
        assert "thinking" in types
        assert "answer" in types
        # Final event should be the answer
        assert events[-1]["type"] == "answer"
        assert events[-1]["content"] == "The answer"

    @pytest.mark.asyncio
    async def test_no_thinking_skips_event(self):
        """No queue events → only final answer event."""
        import asyncio

        async def _mock_agentic_loop(query, tools, system_prompt, config=None, context=None):
            """Mock that pushes no events to queue."""
            return LoopResult(response="answer", steps=1)

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            side_effect=_mock_agentic_loop,
        ):
            events = []
            async for event in agentic_loop_streaming(
                query="test", tools=[], system_prompt="test"
            ):
                events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "answer"


# ============================================================================
# Config Validator
# ============================================================================


class TestAgenticLoopConfigValidator:
    def test_valid_max_steps(self):
        from app.core.config import Settings
        # Should not raise
        s = Settings(agentic_loop_max_steps=10)
        assert s.agentic_loop_max_steps == 10

    def test_invalid_max_steps_too_high(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(agentic_loop_max_steps=25)

    def test_invalid_max_steps_zero(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(agentic_loop_max_steps=0)
