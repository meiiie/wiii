"""
Unit tests for TutorAgentNode non-LLM methods.

Tests:
- Tool list verification (4 tools bound)
- TOOL_INSTRUCTION_DEFAULT content
- _fallback_response() domain-agnostic
- TutorAgentNode initialization
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

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


# =============================================================================
# Tests: Tool list and instruction
# =============================================================================

class TestToolInstruction:
    def test_instruction_mentions_knowledge_search(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert "tool_knowledge_search" in TOOL_INSTRUCTION_DEFAULT

    def test_instruction_mentions_calculator(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert "tool_calculator" in TOOL_INSTRUCTION_DEFAULT

    def test_instruction_mentions_datetime(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert "tool_current_datetime" in TOOL_INSTRUCTION_DEFAULT

    def test_instruction_mentions_web_search(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert "tool_web_search" in TOOL_INSTRUCTION_DEFAULT

    def test_instruction_has_rag_first_rule(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert "RAG-First" in TOOL_INSTRUCTION_DEFAULT

    def test_instruction_not_empty(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION_DEFAULT
        assert len(TOOL_INSTRUCTION_DEFAULT) > 100

    def test_legacy_alias_matches(self):
        from app.engine.multi_agent.agents.tutor_node import TOOL_INSTRUCTION, TOOL_INSTRUCTION_DEFAULT
        assert TOOL_INSTRUCTION is TOOL_INSTRUCTION_DEFAULT


# =============================================================================
# Tests: Tool binding
# =============================================================================

class TestToolBinding:
    def test_tutor_has_9_tools(self):
        """TutorAgentNode should bind 9 tools: 6 base + 3 character (Sprint 97: defaults on)."""
        with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            # Reset singleton
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        assert len(node._tools) == 9

    def test_tutor_tools_have_names(self):
        with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        tool_names = [t.name for t in node._tools]
        assert "tool_knowledge_search" in tool_names
        assert "tool_calculator" in tool_names
        assert "tool_current_datetime" in tool_names
        assert "tool_web_search" in tool_names


# =============================================================================
# Tests: Fallback response
# =============================================================================

class TestFallbackResponse:
    def test_fallback_includes_query(self):
        with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        response = node._fallback_response("Rule 5 explained")
        assert "Rule 5 explained" in response

    def test_fallback_is_domain_agnostic(self):
        """Fallback should NOT mention COLREGs, SOLAS, or other domain-specific terms."""
        with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        response = node._fallback_response("anything")
        assert "COLREGs" not in response
        assert "SOLAS" not in response
        assert "MARPOL" not in response

    def test_fallback_has_learning_suggestions(self):
        with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        response = node._fallback_response("anything")
        assert "1." in response  # Has numbered list
        assert "2." in response
        assert "3." in response


# =============================================================================
# Tests: Availability
# =============================================================================

class TestAvailability:
    def test_available_with_llm(self):
        mock_llm_instance = MagicMock()
        mock_llm_instance.bind_tools.return_value = MagicMock()
        with patch.object(AgentConfigRegistry, "get_llm", return_value=mock_llm_instance):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        assert node.is_available() is True

    def test_unavailable_without_llm(self):
        with patch.object(AgentConfigRegistry, "get_llm", side_effect=Exception("no LLM")):
            from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
            import app.engine.multi_agent.agents.tutor_node as mod
            mod._tutor_node = None
            node = TutorAgentNode()
        assert node.is_available() is False
