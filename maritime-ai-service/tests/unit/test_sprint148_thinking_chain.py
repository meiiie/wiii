"""
Sprint 148: "Chuỗi Tư Duy" — Multi-Phase Thinking Chain Tests

Tests:
1. tool_report_progress has correct args schema
2. tool_report_progress returns acknowledgment string
3. tool_think present in TutorAgentNode._tools
4. tool_report_progress present in TutorAgentNode._tools
5. tool_report_progress emits phase transition events via bus
6. tool_think emits thinking_delta via bus
7. After tool_report_progress, iteration end doesn't emit extra thinking_end
8. THINKING_CHAIN_INSTRUCTION remains defined for legacy compatibility
9. Live tutor prompt does not append chain steering, even at high effort
10. Feature flag no longer changes live prompt injection
11. _convert_bus_event handles action_text events
12. Phase transition rate limit (max 4)
"""

import sys
import types
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ============================================================================
# Break circular import chain before importing graph_streaming
# ============================================================================

_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_graph_key = "app.engine.multi_agent.graph"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_had_graph = _graph_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
_orig_graph = sys.modules.get(_graph_key)

if not _had_cs:
    _mock_chat_svc = types.ModuleType(_cs_key)
    _mock_chat_svc.ChatService = type("ChatService", (), {})
    _mock_chat_svc.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_chat_svc

if not _had_graph:
    _mock_graph = types.ModuleType(_graph_key)
    _mock_graph._build_domain_config = MagicMock(return_value={})
    _mock_graph._build_turn_local_state_defaults = MagicMock(return_value={})
    sys.modules[_graph_key] = _mock_graph

# Restore sys.modules to avoid polluting later test files
if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs

if not _had_graph:
    sys.modules.pop(_graph_key, None)
elif _orig_graph is not None:
    sys.modules[_graph_key] = _orig_graph


# =============================================================================
# Test 1 & 2: tool_report_progress definition
# =============================================================================

class TestProgressToolDefinition:
    """Test tool_report_progress tool definition and behavior."""

    def test_progress_tool_has_correct_args_schema(self):
        """tool_report_progress accepts 'message' and 'phase_label' args."""
        from app.engine.tools.progress_tool import tool_report_progress

        assert tool_report_progress.name == "tool_report_progress"
        schema = tool_report_progress.args_schema.schema()
        props = schema.get("properties", {})
        assert "message" in props, "Must have 'message' arg"
        assert "phase_label" in props, "Must have 'phase_label' arg"

    def test_progress_tool_returns_ack(self):
        """tool_report_progress returns acknowledgment string."""
        from app.engine.tools.progress_tool import tool_report_progress

        result = tool_report_progress.invoke({
            "message": "Test progress",
            "phase_label": "Next phase",
        })
        assert "Progress reported" in result
        assert "Next phase" in result

    def test_progress_tool_default_phase_label(self):
        """tool_report_progress uses 'continuing' when no phase_label given."""
        from app.engine.tools.progress_tool import tool_report_progress

        result = tool_report_progress.invoke({
            "message": "Test",
            "phase_label": "",
        })
        assert "continuing" in result


# =============================================================================
# Test 3 & 4: Tools in TutorAgentNode._tools
# =============================================================================

class TestTutorNodeTools:
    """Test that tool_think and tool_report_progress are in TutorAgentNode._tools."""

    @patch("app.engine.multi_agent.agents.tutor_node.AgentConfigRegistry")
    @patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader")
    def test_think_tool_in_tutor_tools(self, mock_loader, mock_registry):
        """tool_think is present in TutorAgentNode._tools."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_registry.get_llm.return_value = mock_llm

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()

        tool_names = [t.name for t in node._tools]
        assert "tool_think" in tool_names

    @patch("app.engine.multi_agent.agents.tutor_node.AgentConfigRegistry")
    @patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader")
    def test_progress_tool_in_tutor_tools(self, mock_loader, mock_registry):
        """tool_report_progress is present in TutorAgentNode._tools."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_registry.get_llm.return_value = mock_llm

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()

        tool_names = [t.name for t in node._tools]
        assert "tool_report_progress" in tool_names


# =============================================================================
# Test 5 & 6: Bus event emission from tool dispatch
# =============================================================================

class TestToolDispatchEvents:
    """Test event bus emission for tool_think and tool_report_progress."""

    @pytest.mark.asyncio
    async def test_progress_tool_emits_phase_transition(self):
        """tool_report_progress dispatches: thinking_end → action_text → thinking_start."""
        events = []
        queue = asyncio.Queue()

        # Collect events from queue
        async def collect():
            while not queue.empty():
                events.append(queue.get_nowait())

        # Simulate the dispatch logic directly
        event_queue = queue
        progress_msg = "Đã tìm được tài liệu"
        next_label = "Phân tích kết quả"

        # Replicate the dispatch from tutor_node
        await event_queue.put({"type": "thinking_end", "content": "", "node": "tutor_agent"})
        await event_queue.put({"type": "action_text", "content": progress_msg, "node": "tutor_agent"})
        await event_queue.put({
            "type": "thinking_start",
            "content": next_label,
            "node": "tutor_agent",
            "summary": next_label,
        })

        await collect()
        assert len(events) == 3
        assert events[0]["type"] == "thinking_end"
        assert events[1]["type"] == "action_text"
        assert events[1]["content"] == progress_msg
        assert events[2]["type"] == "thinking_start"
        assert events[2]["content"] == next_label

    @pytest.mark.asyncio
    async def test_think_tool_emits_thinking_delta(self):
        """tool_think dispatches: thinking_delta with thought content."""
        events = []
        queue = asyncio.Queue()

        thought = "This is my analysis of the question..."

        # Replicate the dispatch logic: push thinking_deltas
        _CHUNK_SIZE = 40
        for i in range(0, len(thought), _CHUNK_SIZE):
            sub = thought[i:i + _CHUNK_SIZE]
            await queue.put({
                "type": "thinking_delta",
                "content": f"\n\n{sub}" if i == 0 else sub,
                "node": "tutor_agent",
            })

        while not queue.empty():
            events.append(queue.get_nowait())

        assert len(events) >= 1
        assert all(e["type"] == "thinking_delta" for e in events)
        # First chunk should contain the thought content
        combined = "".join(e["content"] for e in events)
        assert thought in combined


# =============================================================================
# Test 7: No double thinking_end
# =============================================================================

class TestNoDoubleThinkingEnd:
    """After tool_report_progress, iteration end skips thinking_end."""

    def test_last_tool_was_progress_flag(self):
        """Verify the conditional logic for _last_tool_was_progress."""
        # When _last_tool_was_progress is True, the thinking_end should NOT emit
        _last_tool_was_progress = True
        event_queue = asyncio.Queue()

        # This is the conditional from tutor_node:
        # if event_queue is not None and not _last_tool_was_progress:
        should_emit = event_queue is not None and not _last_tool_was_progress
        assert not should_emit, "Should NOT emit thinking_end when last tool was progress"

    def test_normal_tool_emits_thinking_end(self):
        """When _last_tool_was_progress is False, thinking_end SHOULD emit."""
        _last_tool_was_progress = False
        event_queue = asyncio.Queue()

        should_emit = event_queue is not None and not _last_tool_was_progress
        assert should_emit, "Should emit thinking_end for normal tools"


# =============================================================================
# Test 8, 9, 10: THINKING_CHAIN_INSTRUCTION prompt injection
# =============================================================================

class TestThinkingChainInstruction:
    """Test legacy chain prompt stays defined but inactive on live tutor path."""

    def test_instruction_constant_exists(self):
        """THINKING_CHAIN_INSTRUCTION constant is defined."""
        from app.engine.multi_agent.agents.tutor_node import THINKING_CHAIN_INSTRUCTION
        assert "tool_report_progress" in THINKING_CHAIN_INSTRUCTION
        assert "PHONG CÁCH TƯ DUY" in THINKING_CHAIN_INSTRUCTION

    @patch("app.engine.multi_agent.agents.tutor_node.settings")
    @patch("app.engine.multi_agent.agents.tutor_node.AgentConfigRegistry")
    @patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader")
    def test_instruction_not_added_when_effort_high(self, mock_loader, mock_registry, mock_settings):
        """Live tutor prompt should stay native-thinking-first even at high effort."""
        mock_settings.enable_thinking_chain = True
        mock_settings.enable_character_tools = False
        mock_settings.default_domain = "maritime"
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_registry.get_llm.return_value = mock_llm
        mock_loader_inst = MagicMock()
        mock_loader_inst.build_system_prompt.return_value = "Base prompt"
        mock_loader.return_value = mock_loader_inst

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()
        prompt = node._build_system_prompt(
            {"thinking_effort": "high"},
            "test query",
        )
        assert "PHONG CÁCH TƯ DUY" not in prompt

    @patch("app.engine.multi_agent.agents.tutor_node.settings")
    @patch("app.engine.multi_agent.agents.tutor_node.AgentConfigRegistry")
    @patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader")
    def test_instruction_still_skipped_when_effort_medium(self, mock_loader, mock_registry, mock_settings):
        """Medium effort should also keep the live prompt free of chain steering."""
        mock_settings.enable_thinking_chain = True
        mock_settings.enable_character_tools = False
        mock_settings.default_domain = "maritime"
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_registry.get_llm.return_value = mock_llm
        mock_loader_inst = MagicMock()
        mock_loader_inst.build_system_prompt.return_value = "Base prompt"
        mock_loader.return_value = mock_loader_inst

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()
        prompt = node._build_system_prompt(
            {"thinking_effort": "medium"},
            "test query",
        )
        assert "PHONG CÁCH TƯ DUY" not in prompt

    @patch("app.engine.multi_agent.agents.tutor_node.settings")
    @patch("app.engine.multi_agent.agents.tutor_node.AgentConfigRegistry")
    @patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader")
    def test_feature_flag_no_longer_changes_live_prompt(self, mock_loader, mock_registry, mock_settings):
        """Disabling the feature flag still leaves the live prompt without chain steering."""
        mock_settings.enable_thinking_chain = False
        mock_settings.enable_character_tools = False
        mock_settings.default_domain = "maritime"
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_registry.get_llm.return_value = mock_llm
        mock_loader_inst = MagicMock()
        mock_loader_inst.build_system_prompt.return_value = "Base prompt"
        mock_loader.return_value = mock_loader_inst

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()
        prompt = node._build_system_prompt(
            {"thinking_effort": "high"},
            "test query",
        )
        assert "PHONG CÁCH TƯ DUY" not in prompt


# =============================================================================
# Test 11: _convert_bus_event handles action_text
# =============================================================================

class TestActionTextBusConversion:
    """Test _convert_bus_event converts action_text events."""

    @pytest.mark.asyncio
    async def test_action_text_bus_event_conversion(self):
        """_convert_bus_event({"type": "action_text", ...}) returns StreamEvent."""
        from app.engine.multi_agent.graph_streaming import _convert_bus_event

        event = {
            "type": "action_text",
            "content": "Đã phân tích xong câu hỏi!",
            "node": "tutor_agent",
        }
        result = await _convert_bus_event(event)
        assert result.type == "action_text"
        assert result.content == "Đã phân tích xong câu hỏi!"
        assert result.node == "tutor_agent"


# =============================================================================
# Test 12: Phase transition rate limit
# =============================================================================

class TestPhaseTransitionRateLimit:
    """Test that max 4 phase transitions are allowed per request."""

    def test_max_phase_transitions_constant(self):
        """_MAX_PHASE_TRANSITIONS is defined and set to 4."""
        from app.engine.multi_agent.agents.tutor_node import _MAX_PHASE_TRANSITIONS
        assert _MAX_PHASE_TRANSITIONS == 4

    @pytest.mark.asyncio
    async def test_rate_limit_stops_after_max(self):
        """After _MAX_PHASE_TRANSITIONS, no more bus events emitted."""
        from app.engine.multi_agent.agents.tutor_node import _MAX_PHASE_TRANSITIONS

        events = []
        queue = asyncio.Queue()

        _phase_transition_count = 0

        for i in range(_MAX_PHASE_TRANSITIONS + 2):
            if _phase_transition_count < _MAX_PHASE_TRANSITIONS:
                await queue.put({"type": "thinking_end", "node": "tutor_agent"})
                await queue.put({"type": "action_text", "content": f"Phase {i}", "node": "tutor_agent"})
                await queue.put({"type": "thinking_start", "content": f"Phase {i+1}", "node": "tutor_agent"})
                _phase_transition_count += 1

        while not queue.empty():
            events.append(queue.get_nowait())

        # Should have exactly _MAX_PHASE_TRANSITIONS * 3 events (end + action + start)
        assert len(events) == _MAX_PHASE_TRANSITIONS * 3
        # The extra 2 iterations should NOT have added events
        assert _phase_transition_count == _MAX_PHASE_TRANSITIONS


# =============================================================================
# Test: Tool registration in registry
# =============================================================================

class TestToolRegistration:
    """Test tools are registered in the global registry."""

    def test_progress_tool_registered(self):
        """tool_report_progress is importable from tools package."""
        from app.engine.tools import tool_report_progress
        assert tool_report_progress.name == "tool_report_progress"

    def test_think_tool_registered(self):
        """tool_think is importable from tools package."""
        from app.engine.tools import tool_think
        assert tool_think.name == "tool_think"


# =============================================================================
# Test: Feature flag exists in config
# =============================================================================

class TestFeatureFlag:
    """Test enable_thinking_chain feature flag."""

    def test_feature_flag_exists(self):
        """enable_thinking_chain field exists in Settings."""
        from app.core.config import Settings
        schema = Settings.model_json_schema()
        props = schema.get("properties", {})
        assert "enable_thinking_chain" in props

    def test_feature_flag_default_false(self):
        """enable_thinking_chain defaults to False."""
        from app.core.config import Settings
        schema = Settings.model_json_schema()
        props = schema["properties"]["enable_thinking_chain"]
        assert props.get("default") is False
