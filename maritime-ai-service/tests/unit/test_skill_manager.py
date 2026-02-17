"""
Tests for Runtime Skill Manager.

Sprint 13: Extended Tools & Self-Extending Skills.
Tests create/list/delete runtime skills, YAML validation, path safety.
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from app.domains.skill_manager import SkillManager, RuntimeSkillResult


@pytest.fixture
def skill_manager(tmp_path):
    """Create a SkillManager with temp workspace."""
    return SkillManager(workspace_root=str(tmp_path))


# ============================================================================
# Create Skill Tests
# ============================================================================


class TestCreateSkill:
    """Test skill creation."""

    def test_create_basic_skill(self, skill_manager, tmp_path):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="colregs-rule-15",
            description="COLREGs Rule 15 about crossing situations",
            triggers=["colregs", "rule 15", "crossing"],
            content="# Rule 15\n\nWhen two power-driven vessels are crossing...",
        )
        assert result.success is True
        assert result.skill_id == "colregs-rule-15"
        assert result.path is not None
        assert Path(result.path).exists()

    def test_created_skill_has_yaml_frontmatter(self, skill_manager, tmp_path):
        skill_manager.create_skill(
            domain_id="maritime",
            name="test-skill",
            description="Test",
            triggers=["test"],
            content="# Test content",
        )
        skill_path = tmp_path / "skills" / "maritime" / "test-skill" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert content.startswith("---")
        # Parse frontmatter
        parts = content.split("---", 2)
        metadata = yaml.safe_load(parts[1])
        assert metadata["id"] == "test-skill"
        assert metadata["runtime"] is True
        assert "test" in metadata["triggers"]

    def test_create_with_version(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="traffic",
            name="speed-limit",
            description="Speed limits",
            triggers=["speed"],
            content="# Speed Limits",
            version="2.0.0",
        )
        assert result.success is True

    def test_create_nested_domain(self, skill_manager, tmp_path):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="solas-chapter-5",
            description="SOLAS Chapter V",
            triggers=["solas"],
            content="# SOLAS V",
        )
        assert result.success is True
        skill_dir = tmp_path / "skills" / "maritime" / "solas-chapter-5"
        assert skill_dir.exists()

    # --- Validation ---

    def test_reject_empty_name(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="",
            description="test",
            triggers=["t"],
            content="content",
        )
        assert result.success is False
        assert "2 ký tự" in result.message

    def test_reject_short_name(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="x",
            description="test",
            triggers=["t"],
            content="content",
        )
        assert result.success is False

    def test_reject_empty_description(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="test-skill",
            description="",
            triggers=["t"],
            content="content",
        )
        assert result.success is False
        assert "Mô tả" in result.message

    def test_reject_no_triggers(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="test-skill",
            description="desc",
            triggers=[],
            content="content",
        )
        assert result.success is False
        assert "trigger" in result.message

    def test_reject_empty_content(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="test-skill",
            description="desc",
            triggers=["t"],
            content="",
        )
        assert result.success is False

    def test_reject_invalid_name_characters(self, skill_manager):
        result = skill_manager.create_skill(
            domain_id="maritime",
            name="bad name with spaces!",
            description="desc",
            triggers=["t"],
            content="content",
        )
        assert result.success is False
        assert "chữ cái" in result.message


# ============================================================================
# List Skills Tests
# ============================================================================


class TestListSkills:
    """Test skill listing."""

    def test_list_empty(self, skill_manager):
        skills = skill_manager.list_runtime_skills()
        assert skills == []

    def test_list_after_create(self, skill_manager):
        skill_manager.create_skill(
            domain_id="maritime",
            name="skill-a",
            description="Skill A",
            triggers=["a"],
            content="Content A",
        )
        skills = skill_manager.list_runtime_skills()
        assert len(skills) == 1
        assert skills[0]["id"] == "skill-a"
        assert skills[0]["runtime"] is True

    def test_list_multiple_domains(self, skill_manager):
        skill_manager.create_skill("maritime", "s1", "d1", ["t1"], "c1")
        skill_manager.create_skill("traffic", "s2", "d2", ["t2"], "c2")

        all_skills = skill_manager.list_runtime_skills()
        assert len(all_skills) == 2

        maritime_skills = skill_manager.list_runtime_skills("maritime")
        assert len(maritime_skills) == 1
        assert maritime_skills[0]["domain_id"] == "maritime"

        traffic_skills = skill_manager.list_runtime_skills("traffic")
        assert len(traffic_skills) == 1

    def test_list_nonexistent_domain(self, skill_manager):
        skills = skill_manager.list_runtime_skills("nonexistent")
        assert skills == []


# ============================================================================
# Delete Skill Tests
# ============================================================================


class TestDeleteSkill:
    """Test skill deletion."""

    def test_delete_existing_skill(self, skill_manager, tmp_path):
        skill_manager.create_skill("maritime", "to-delete", "d", ["t"], "c")
        result = skill_manager.delete_skill("maritime", "to-delete")
        assert result.success is True

        # Verify removed from disk
        skill_dir = tmp_path / "skills" / "maritime" / "to-delete"
        assert not skill_dir.exists()

    def test_delete_nonexistent_skill(self, skill_manager):
        result = skill_manager.delete_skill("maritime", "nonexistent")
        assert result.success is False
        assert "không tồn tại" in result.message

    def test_delete_then_list(self, skill_manager):
        skill_manager.create_skill("maritime", "skill-x", "dx", ["tx"], "cx")
        skill_manager.delete_skill("maritime", "skill-x")
        skills = skill_manager.list_runtime_skills("maritime")
        assert len(skills) == 0


# ============================================================================
# Get Skill Content Tests
# ============================================================================


class TestGetSkillContent:
    """Test retrieving skill content body."""

    def test_get_content(self, skill_manager):
        skill_manager.create_skill(
            "maritime", "rule-15", "desc", ["colregs"],
            "# Rule 15\n\nCrossing situation details."
        )
        content = skill_manager.get_skill_content("maritime", "rule-15")
        assert "Rule 15" in content
        assert "Crossing situation" in content

    def test_get_nonexistent_content(self, skill_manager):
        content = skill_manager.get_skill_content("maritime", "nonexistent")
        assert content is None
