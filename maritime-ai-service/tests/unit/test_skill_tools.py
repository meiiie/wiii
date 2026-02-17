"""
Tests for Skill Management Tools.

Sprint 13: Extended Tools & Self-Extending Skills.
Tests tool interface for creating/listing/deleting skills.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.tools.skill_tools import (
    tool_create_skill,
    tool_list_skills,
    tool_delete_skill,
    get_skill_tools,
)
from app.domains.skill_manager import SkillManager, RuntimeSkillResult


@pytest.fixture
def mock_manager(tmp_path):
    """Create a real SkillManager with temp workspace."""
    return SkillManager(workspace_root=str(tmp_path))


# ============================================================================
# Tool Create Skill Tests
# ============================================================================


class TestToolCreateSkill:
    """Test tool_create_skill LangChain tool."""

    def test_create_skill_success(self, mock_manager):
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_create_skill.invoke({
                "name": "test-skill",
                "description": "A test skill",
                "triggers": "test, demo, example",
                "content": "# Test Skill\n\nThis is a test.",
                "domain_id": "maritime",
            })
        assert "✅" in result
        assert "test-skill" in result

    def test_create_skill_validation_error(self, mock_manager):
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_create_skill.invoke({
                "name": "",
                "description": "desc",
                "triggers": "t",
                "content": "c",
                "domain_id": "maritime",
            })
        assert "❌" in result

    def test_create_skill_default_domain(self, mock_manager):
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_create_skill.invoke({
                "name": "default-domain-skill",
                "description": "test",
                "triggers": "trigger1",
                "content": "content",
            })
        assert "✅" in result

    def test_create_skill_triggers_split(self, mock_manager):
        """Triggers string should be split by comma."""
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_create_skill.invoke({
                "name": "multi-trigger",
                "description": "desc",
                "triggers": "a, b, c",
                "content": "content",
                "domain_id": "maritime",
            })
        assert "✅" in result
        # Verify triggers were split
        skills = mock_manager.list_runtime_skills("maritime")
        assert len(skills) == 1
        assert "a" in skills[0]["triggers"]
        assert "b" in skills[0]["triggers"]
        assert "c" in skills[0]["triggers"]


# ============================================================================
# Tool List Skills Tests
# ============================================================================


class TestToolListSkills:
    """Test tool_list_skills LangChain tool."""

    def test_list_empty(self, mock_manager):
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_list_skills.invoke({})
        assert "Chưa có" in result

    def test_list_after_create(self, mock_manager):
        mock_manager.create_skill("maritime", "s1", "desc1", ["t1"], "c1")
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_list_skills.invoke({})
        assert "1 runtime skills" in result
        assert "S1" in result or "s1" in result.lower()

    def test_list_with_domain_filter(self, mock_manager):
        mock_manager.create_skill("maritime", "s1", "d1", ["t1"], "c1")
        mock_manager.create_skill("traffic", "s2", "d2", ["t2"], "c2")
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_list_skills.invoke({"domain_id": "maritime"})
        assert "1 runtime skills" in result


# ============================================================================
# Tool Delete Skill Tests
# ============================================================================


class TestToolDeleteSkill:
    """Test tool_delete_skill LangChain tool."""

    def test_delete_existing(self, mock_manager):
        mock_manager.create_skill("maritime", "to-delete", "d", ["t"], "c")
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_delete_skill.invoke({
                "domain_id": "maritime",
                "skill_id": "to-delete",
            })
        assert "✅" in result

    def test_delete_nonexistent(self, mock_manager):
        with patch("app.domains.skill_manager.get_skill_manager", return_value=mock_manager):
            result = tool_delete_skill.invoke({
                "domain_id": "maritime",
                "skill_id": "nonexistent",
            })
        assert "❌" in result


# ============================================================================
# Registration Tests
# ============================================================================


class TestRegistration:
    def test_get_skill_tools_returns_three(self):
        tools = get_skill_tools()
        assert len(tools) == 3

    def test_tool_names(self):
        tools = get_skill_tools()
        names = [t.name for t in tools]
        assert "tool_create_skill" in names
        assert "tool_list_skills" in names
        assert "tool_delete_skill" in names
