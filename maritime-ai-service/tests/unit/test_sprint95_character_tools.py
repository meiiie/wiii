"""
Sprint 95: Wire Character Tools into Agent Graph + Dead Code Cleanup — Tests

Tests:
1. @tool decorators on note/read, plain on replace/log
2. ToolCategory.CHARACTER in enum
3. Config flag enable_character_tools
4. Tutor node wiring (init + ReAct dispatch)
5. get_character_tools() accessor
6. Edge cases (invoke works, reflection unaffected, DB unavailable)
7. Dead code cleanup (_shared.yaml stale comment removed)
"""

import sys
import types
import asyncio
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Break circular import
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs


PROMPTS_DIR = Path(__file__).parent.parent.parent / "app" / "prompts"


# =============================================================================
# Phase 1: Tool Decorators
# =============================================================================

class TestToolDecorators:
    """Verify @tool on note/read, plain on replace/log."""

    def test_tool_character_note_is_structured_tool(self):
        """tool_character_note should be a LangChain StructuredTool."""
        from app.engine.character.character_tools import tool_character_note
        assert hasattr(tool_character_note, 'invoke'), "Should have .invoke() method"
        assert hasattr(tool_character_note, 'name'), "Should have .name attribute"
        assert tool_character_note.name == "tool_character_note"

    def test_tool_character_read_is_structured_tool(self):
        """tool_character_read should be a LangChain StructuredTool."""
        from app.engine.character.character_tools import tool_character_read
        assert hasattr(tool_character_read, 'invoke'), "Should have .invoke() method"
        assert hasattr(tool_character_read, 'name'), "Should have .name attribute"
        assert tool_character_read.name == "tool_character_read"

    def test_tool_character_replace_is_plain_function(self):
        """tool_character_replace should remain a plain function (not @tool)."""
        from app.engine.character.character_tools import tool_character_replace
        assert not hasattr(tool_character_replace, 'invoke'), \
            "Should NOT have .invoke() — used by reflection engine only"
        assert callable(tool_character_replace)

    def test_tool_character_log_experience_is_structured_tool(self):
        """tool_character_log_experience should be a LangChain StructuredTool (Sprint 97)."""
        from app.engine.character.character_tools import tool_character_log_experience
        assert hasattr(tool_character_log_experience, 'invoke'), "Should have .invoke() method"
        assert hasattr(tool_character_log_experience, 'name'), "Should have .name attribute"
        assert tool_character_log_experience.name == "tool_character_log_experience"

    def test_tool_note_description_is_ascii(self):
        """Tool description should be ASCII (no diacritics) for LLM compatibility."""
        from app.engine.character.character_tools import tool_character_note
        desc = tool_character_note.description
        assert "Ghi chu" in desc
        assert "bo nho song" in desc

    def test_tool_read_description_is_ascii(self):
        """Tool description should be ASCII (no diacritics) for LLM compatibility."""
        from app.engine.character.character_tools import tool_character_read
        desc = tool_character_read.description
        assert "Doc noi dung" in desc
        assert "bo nho song" in desc


# =============================================================================
# Phase 2: ToolCategory.CHARACTER
# =============================================================================

class TestToolCategoryCharacter:
    """Verify CHARACTER category in ToolCategory enum."""

    def test_character_in_enum(self):
        from app.engine.tools.registry import ToolCategory
        assert hasattr(ToolCategory, 'CHARACTER')
        assert ToolCategory.CHARACTER.value == "character"

    def test_registration_when_enabled(self):
        """Character tools should register when enable_character_tools=True."""
        from app.engine.tools.registry import ToolRegistry, ToolCategory, ToolAccess
        from app.engine.character.character_tools import get_character_tools

        registry = ToolRegistry()
        for tool_fn in get_character_tools():
            registry.register(tool_fn, ToolCategory.CHARACTER, ToolAccess.WRITE)

        char_tools = registry.get_by_category(ToolCategory.CHARACTER)
        assert len(char_tools) == 3
        names = [t.name for t in char_tools]
        assert "tool_character_note" in names
        assert "tool_character_read" in names
        assert "tool_character_log_experience" in names

    def test_registration_not_when_disabled(self):
        """Character tools should NOT register when enable_character_tools=False."""
        from app.engine.tools.registry import ToolRegistry, ToolCategory

        registry = ToolRegistry()
        # Don't register anything
        char_tools = registry.get_by_category(ToolCategory.CHARACTER)
        assert len(char_tools) == 0

    def test_write_access(self):
        """Character tools should be WRITE access."""
        from app.engine.tools.registry import ToolRegistry, ToolCategory, ToolAccess
        from app.engine.character.character_tools import get_character_tools

        registry = ToolRegistry()
        for tool_fn in get_character_tools():
            registry.register(tool_fn, ToolCategory.CHARACTER, ToolAccess.WRITE)

        for name in ["tool_character_note", "tool_character_read", "tool_character_log_experience"]:
            info = registry.get_info(name)
            assert info is not None
            assert info.access == ToolAccess.WRITE


# =============================================================================
# Phase 3: Config Flag
# =============================================================================

class TestConfigFlag:
    """Test enable_character_tools config field."""

    def test_default_true(self):
        """enable_character_tools should default to True (Sprint 97)."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.enable_character_tools is True

    def test_can_set_true(self):
        """Should be able to set enable_character_tools=True."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_character_tools=True,
            _env_file=None,
        )
        assert s.enable_character_tools is True

    def test_independent_from_reflection_flag(self):
        """enable_character_tools should be independent from enable_character_reflection."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_character_tools=True,
            enable_character_reflection=False,
            _env_file=None,
        )
        assert s.enable_character_tools is True
        assert s.enable_character_reflection is False


# =============================================================================
# Phase 4: Tutor Node Wiring
# =============================================================================

class TestTutorNodeWiring:
    """Test character tools wiring in TutorAgentNode.__init__."""

    @patch("app.engine.multi_agent.agents.tutor_runtime.AgentConfigRegistry")
    def test_default_6_tools(self, mock_acr):
        """Without character tools enabled, should have 6 base tools."""
        mock_llm = MagicMock()
        mock_acr.get_llm.return_value = mock_llm
        with patch("app.engine.multi_agent.agents.tutor_node.settings") as mock_settings:
            mock_settings.enable_character_tools = False
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            old = mod._tutor_node
            mod._tutor_node = None
            try:
                node = TutorAgentNode()
                # Base tool count grows as new tools are added; verify character tools NOT included
                base_count = len(node._tools)
                assert base_count >= 6  # At least 6 base tools
                assert node._character_tools_enabled is False
            finally:
                mod._tutor_node = old

    @patch("app.engine.multi_agent.agents.tutor_runtime.AgentConfigRegistry")
    def test_more_tools_when_enabled(self, mock_acr):
        """With character tools enabled, should have base + 3 character tools."""
        mock_llm = MagicMock()
        mock_acr.get_llm.return_value = mock_llm
        with patch("app.engine.multi_agent.agents.tutor_node.settings") as mock_settings:
            mock_settings.enable_character_tools = True
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            old = mod._tutor_node
            mod._tutor_node = None
            try:
                node = TutorAgentNode()
                assert len(node._tools) >= 9  # base + character tools
                assert node._character_tools_enabled is True
                tool_names = [getattr(t, 'name', getattr(t, '__name__', '')) for t in node._tools]
                assert "tool_character_note" in tool_names
                assert "tool_character_read" in tool_names
            finally:
                mod._tutor_node = old

    @patch("app.engine.multi_agent.agents.tutor_runtime.AgentConfigRegistry")
    def test_graceful_when_unavailable(self, mock_acr):
        """Should handle ImportError gracefully."""
        mock_llm = MagicMock()
        mock_acr.get_llm.return_value = mock_llm
        with patch("app.engine.multi_agent.agents.tutor_node.settings") as mock_settings:
            mock_settings.enable_character_tools = True
            # Make character_tools import fail
            with patch.dict(sys.modules, {"app.engine.character.character_tools": None}):
                from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
                import app.engine.multi_agent.agents.tutor_node as mod
                old = mod._tutor_node
                mod._tutor_node = None
                try:
                    node = TutorAgentNode()
                    # Character tools unavailable, should fall back to base count
                    assert len(node._tools) >= 6
                    assert node._character_tools_enabled is False
                finally:
                    mod._tutor_node = old

    @patch("app.engine.multi_agent.agents.tutor_runtime.AgentConfigRegistry")
    def test_bind_tools_called_with_all(self, mock_acr):
        """bind_tools should be called with all tools including character."""
        mock_llm = MagicMock()
        mock_acr.get_llm.return_value = mock_llm
        with patch("app.engine.multi_agent.agents.tutor_node.settings") as mock_settings:
            mock_settings.enable_character_tools = True
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            old = mod._tutor_node
            mod._tutor_node = None
            try:
                node = TutorAgentNode()
                # bind_tools should have been called with the full tool list
                mock_llm.bind_tools.assert_called_once_with(node._tools)
            finally:
                mod._tutor_node = old


# =============================================================================
# Phase 5: ReAct Dispatch
# =============================================================================

class TestReActDispatch:
    """Test character tool dispatch in ReAct loop."""

    @pytest.fixture
    def mock_tutor(self):
        """Create a TutorAgentNode with mocked LLM."""
        with patch("app.engine.multi_agent.agents.tutor_runtime.AgentConfigRegistry") as mock_acr, \
             patch("app.engine.multi_agent.agents.tutor_node.settings") as mock_settings:
            mock_settings.enable_character_tools = True
            mock_settings.default_domain = "maritime"
            mock_llm = MagicMock()
            mock_acr.get_llm.return_value = mock_llm
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            old = mod._tutor_node
            mod._tutor_node = None
            try:
                node = TutorAgentNode()
                yield node
            finally:
                mod._tutor_node = old

    @pytest.mark.asyncio
    async def test_note_dispatched(self, mock_tutor):
        """tool_character_note should be dispatched via ReAct loop."""
        # Simulate LLM returning a tool call then a final response
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "tool_character_note", "args": {"note": "test note", "block": "self_notes"}, "id": "call_1"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Done!"

        mock_tutor._llm_with_tools = MagicMock()
        mock_tutor._llm_with_tools.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        # Mock the character tool
        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            from app.engine.character.models import CharacterBlock
            mock_mgr_inst = MagicMock()
            mock_mgr_inst.update_block.return_value = CharacterBlock(
                label="self_notes", content="- test", char_limit=1000
            )
            mock_mgr.return_value = mock_mgr_inst

            response, sources, tools_used, thinking, streamed = await mock_tutor._react_loop(
                query="test query",
                context={"user_role": "student"},
            )

        assert len(tools_used) == 1
        assert tools_used[0]["name"] == "tool_character_note"
        assert "Character: note" in tools_used[0]["description"]

    @pytest.mark.asyncio
    async def test_read_dispatched(self, mock_tutor):
        """tool_character_read should be dispatched via ReAct loop."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "tool_character_read", "args": {"block": "learned_lessons"}, "id": "call_2"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Here are my notes."

        mock_tutor._llm_with_tools = MagicMock()
        mock_tutor._llm_with_tools.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            from app.engine.character.models import CharacterBlock
            mock_mgr_inst = MagicMock()
            mock_mgr_inst.get_block.return_value = CharacterBlock(
                label="learned_lessons", content="- Rule 15 notes"
            )
            mock_mgr.return_value = mock_mgr_inst

            response, sources, tools_used, thinking, streamed = await mock_tutor._react_loop(
                query="review notes",
                context={"user_role": "student"},
            )

        assert len(tools_used) == 1
        assert tools_used[0]["name"] == "tool_character_read"
        assert "Character: read" in tools_used[0]["description"]

    @pytest.mark.asyncio
    async def test_tool_message_appended(self, mock_tutor):
        """ToolMessage should be appended after character tool execution."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "tool_character_note", "args": {"note": "hi", "block": "self_notes"}, "id": "call_3"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Noted."

        mock_tutor._llm_with_tools = MagicMock()
        mock_tutor._llm_with_tools.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            from app.engine.character.models import CharacterBlock
            mock_mgr_inst = MagicMock()
            mock_mgr_inst.update_block.return_value = CharacterBlock(
                label="self_notes", content="- hi", char_limit=1000
            )
            mock_mgr.return_value = mock_mgr_inst

            response, sources, tools_used, thinking, streamed = await mock_tutor._react_loop(
                query="note this",
                context={"user_role": "student"},
            )

        # The second ainvoke should have received messages with ToolMessage
        call_args = mock_tutor._llm_with_tools.ainvoke.call_args_list
        assert len(call_args) == 2
        # Messages for second call should include ToolMessage
        second_messages = call_args[1][0][0]
        from langchain_core.messages import ToolMessage
        tool_msgs = [m for m in second_messages if isinstance(m, ToolMessage)]
        assert len(tool_msgs) >= 1

    @pytest.mark.asyncio
    async def test_event_pushed(self, mock_tutor):
        """tool_result event should be pushed to event queue."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "tool_character_note", "args": {"note": "test", "block": "self_notes"}, "id": "call_4"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "OK."

        # When event_queue is provided, tutor uses astream (not ainvoke)
        async def _mock_astream(messages):
            """Yield chunks — first call returns tool_call, second returns final."""
            if not hasattr(_mock_astream, '_call_count'):
                _mock_astream._call_count = 0
            _mock_astream._call_count += 1
            if _mock_astream._call_count == 1:
                yield tool_call_response
            else:
                yield final_response

        mock_tutor._llm_with_tools = MagicMock()
        mock_tutor._llm_with_tools.astream = _mock_astream

        event_queue = asyncio.Queue()

        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            from app.engine.character.models import CharacterBlock
            mock_mgr_inst = MagicMock()
            mock_mgr_inst.update_block.return_value = CharacterBlock(
                label="self_notes", content="- test", char_limit=1000
            )
            mock_mgr.return_value = mock_mgr_inst

            await mock_tutor._react_loop(
                query="note",
                context={"user_role": "student"},
                event_queue=event_queue,
            )

        # Collect events
        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        # Should have tool_call and tool_result events
        tool_result_events = [e for e in events if e.get("type") == "tool_result"]
        assert len(tool_result_events) >= 1
        assert tool_result_events[0]["content"]["name"] == "tool_character_note"

    @pytest.mark.asyncio
    async def test_error_handled(self, mock_tutor):
        """Character tool errors should be caught gracefully."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "tool_character_note", "args": {"note": "test", "block": "self_notes"}, "id": "call_5"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Error handled."

        mock_tutor._llm_with_tools = MagicMock()
        mock_tutor._llm_with_tools.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        # Make the character tool raise an exception
        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            mock_mgr.side_effect = RuntimeError("DB crash")

            response, sources, tools_used, thinking, streamed = await mock_tutor._react_loop(
                query="note this",
                context={"user_role": "student"},
            )

        # Should still return a response (not crash)
        assert response == "Error handled."


# =============================================================================
# Phase 6: Tool Accessors
# =============================================================================

class TestToolAccessors:
    """Test get_character_tools() accessor."""

    def test_returns_3_tools(self):
        """Sprint 97: get_character_tools returns 3 tools (note, read, log_experience)."""
        from app.engine.character.character_tools import get_character_tools
        tools = get_character_tools()
        assert len(tools) == 3

    def test_correct_names(self):
        from app.engine.character.character_tools import get_character_tools
        tools = get_character_tools()
        names = [t.name for t in tools]
        assert "tool_character_note" in names
        assert "tool_character_read" in names
        assert "tool_character_log_experience" in names

    def test_correct_types(self):
        """All returned tools should be StructuredTool instances."""
        from app.engine.character.character_tools import get_character_tools
        from langchain_core.tools import StructuredTool
        tools = get_character_tools()
        for t in tools:
            assert isinstance(t, StructuredTool), f"{t.name} should be StructuredTool"


# =============================================================================
# Phase 7: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge cases for Sprint 95 wiring."""

    def test_invoke_works_for_note(self):
        """tool_character_note.invoke() should work with valid block."""
        from app.engine.character.character_tools import tool_character_note
        from app.engine.character.models import CharacterBlock
        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            mock_inst = MagicMock()
            mock_inst.update_block.return_value = CharacterBlock(
                label="self_notes", content="- test", char_limit=1000
            )
            mock_mgr.return_value = mock_inst
            result = tool_character_note.invoke({"note": "test", "block": "self_notes"})
        assert "ghi nhận" in result

    def test_invoke_works_for_read(self):
        """tool_character_read.invoke() should work."""
        from app.engine.character.character_tools import tool_character_read
        from app.engine.character.models import CharacterBlock
        with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
            mock_inst = MagicMock()
            mock_inst.get_block.return_value = CharacterBlock(
                label="self_notes", content="My content"
            )
            mock_mgr.return_value = mock_inst
            result = tool_character_read.invoke({"block": "self_notes"})
        assert "My content" in result

    def test_reflection_engine_unaffected(self):
        """Reflection engine uses state_manager directly, not tools.
        tool_character_replace should still be callable as plain function."""
        from app.engine.character.character_tools import tool_character_replace
        # tool_character_replace is a plain function, not @tool
        assert callable(tool_character_replace)
        # Can be called directly (not .invoke())
        result = tool_character_replace("invalid_block", "content")
        assert "không hợp lệ" in result

    def test_invoke_invalid_block(self):
        """invoke() with invalid block should return error message."""
        from app.engine.character.character_tools import tool_character_note
        result = tool_character_note.invoke({"note": "test", "block": "invalid_xyz"})
        assert "không hợp lệ" in result


# =============================================================================
# Phase 8: Dead Code Cleanup
# =============================================================================

class TestDeadCodeCleanup:
    """Verify stale RESPONSE QUALITY comment removed from _shared.yaml."""

    def test_shared_yaml_no_stale_comment(self):
        """_shared.yaml should NOT have the Sprint 87 stale comment."""
        path = PROMPTS_DIR / "base" / "_shared.yaml"
        content = path.read_text(encoding="utf-8")
        assert "RESPONSE QUALITY — MOVED" not in content
        assert "BUG #C1" not in content

    def test_shared_yaml_still_valid(self):
        """_shared.yaml should still be valid YAML after cleanup."""
        path = PROMPTS_DIR / "base" / "_shared.yaml"
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "extraction" in data or "memory" in data or "shared" in data or isinstance(data, dict)
