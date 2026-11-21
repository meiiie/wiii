from unittest.mock import MagicMock, patch

from tests.unit.tutor_agent_node_helpers import (
    AgentConfigRegistry,
    _make_tutor,
    mock_llm as mock_llm,
)


class TestFallbackResponse:
    def test_fallback_includes_query(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)
        result = node._fallback_response("COLREGs Rule 13")
        assert "COLREGs Rule 13" in result
        assert "tài liệu" in result.lower() or "bài tập" in result.lower()


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
