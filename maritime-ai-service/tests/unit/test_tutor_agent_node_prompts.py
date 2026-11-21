from unittest.mock import MagicMock, patch

from tests.unit.tutor_agent_node_helpers import (
    DOMAIN_REGISTRY_PATCH,
    _make_tutor,
    mock_llm as mock_llm,
)


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

    def test_prompt_includes_instructional_answer_style_contract(self, mock_llm):
        node = _make_tutor(llm=mock_llm, llm_with_tools=mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("no registry")):
            prompt = node._build_system_prompt(
                {"user_name": "Minh", "user_role": "student"},
                "Giai thich Rule 15 khac gi Rule 13",
            )

        assert "KHONG mo dau bang loi chao" in prompt
        assert "thesis-first" in prompt
