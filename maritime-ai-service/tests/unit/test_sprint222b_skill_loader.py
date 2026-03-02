"""Sprint 222b Phase 6: ContextSkillLoader — YAML skill loading with fallback chain."""
import pytest
from pathlib import Path
from unittest.mock import patch
import yaml


class TestContextSkillModel:
    """Test ContextSkill dataclass."""

    def test_context_skill_fields(self):
        from app.engine.context.skill_loader import ContextSkill
        skill = ContextSkill(
            name="lms-quiz",
            host_type="lms",
            page_types=["quiz", "exam"],
            description="Socratic quiz guidance",
            priority=1.0,
            prompt_addition="KHÔNG cho đáp án trực tiếp",
            tools=["tool_knowledge_search"],
            enrichment_triggers=[{"pattern": "giải thích", "action": "request_content_snippet"}],
        )
        assert skill.name == "lms-quiz"
        assert skill.priority == 1.0
        assert "quiz" in skill.page_types
        assert len(skill.tools) == 1

    def test_context_skill_defaults(self):
        from app.engine.context.skill_loader import ContextSkill
        skill = ContextSkill(
            name="test",
            host_type="generic",
            page_types=["default"],
            description="test skill",
        )
        assert skill.priority == 0.5
        assert skill.prompt_addition == ""
        assert skill.tools == []
        assert skill.enrichment_triggers == []


class TestContextSkillLoader:
    """Test YAML skill loading with fallback chain."""

    @pytest.fixture
    def skill_dir(self, tmp_path):
        """Create temporary skill directory with test YAML files."""
        lms_dir = tmp_path / "lms"
        lms_dir.mkdir()
        quiz_skill = {
            "name": "lms-quiz",
            "host_type": "lms",
            "page_types": ["quiz", "exam"],
            "description": "Socratic quiz guidance",
            "priority": 1.0,
            "prompt_addition": "KHÔNG cho đáp án trực tiếp",
            "tools": ["tool_knowledge_search", "tool_explain_concept"],
            "enrichment_triggers": [
                {"pattern": "giải thích|explain", "action": "request_content_snippet"}
            ],
        }
        (lms_dir / "quiz.skill.yaml").write_text(
            yaml.dump(quiz_skill, allow_unicode=True), encoding="utf-8"
        )

        default_skill = {
            "name": "lms-default",
            "host_type": "lms",
            "page_types": ["*"],
            "description": "General LMS behavior",
            "priority": 0.1,
            "prompt_addition": "Hỗ trợ sinh viên trong LMS.",
            "tools": ["tool_knowledge_search"],
        }
        (lms_dir / "default.skill.yaml").write_text(
            yaml.dump(default_skill, allow_unicode=True), encoding="utf-8"
        )

        generic_dir = tmp_path / "generic"
        generic_dir.mkdir()
        generic_skill = {
            "name": "generic-default",
            "host_type": "generic",
            "page_types": ["*"],
            "description": "Universal fallback",
            "priority": 0.0,
            "prompt_addition": "Liên hệ nội dung trang khi trả lời.",
        }
        (generic_dir / "default.skill.yaml").write_text(
            yaml.dump(generic_skill, allow_unicode=True), encoding="utf-8"
        )

        return tmp_path

    def test_load_exact_match(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "quiz")
        assert any(s.name == "lms-quiz" for s in skills)

    def test_load_fallback_to_host_default(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "dashboard")
        assert any(s.name == "lms-default" for s in skills)
        assert not any(s.name == "lms-quiz" for s in skills)

    def test_load_fallback_to_generic_default(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("ecommerce", "product_page")
        assert any(s.name == "generic-default" for s in skills)

    def test_skills_sorted_by_priority(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "quiz")
        priorities = [s.priority for s in skills]
        assert priorities == sorted(priorities, reverse=True)

    def test_get_prompt_addition(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "quiz")
        prompt = loader.get_prompt_addition(skills)
        assert "KHÔNG cho đáp án trực tiếp" in prompt

    def test_get_tool_ids(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "quiz")
        tool_ids = loader.get_tool_ids(skills)
        assert "tool_knowledge_search" in tool_ids

    def test_caching(self, skill_dir):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills1 = loader.load_skills("lms", "quiz")
        skills2 = loader.load_skills("lms", "quiz")
        assert skills1 is skills2

    def test_empty_dir(self, tmp_path):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("lms", "quiz")
        assert skills == []

    def test_malformed_yaml_skipped(self, skill_dir):
        (skill_dir / "lms" / "broken.skill.yaml").write_text(
            "name: broken\n  invalid: [yaml", encoding="utf-8"
        )
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=skill_dir)
        skills = loader.load_skills("lms", "quiz")
        assert any(s.name == "lms-quiz" for s in skills)
        assert not any(s.name == "broken" for s in skills)

    def test_get_skill_loader_singleton(self, skill_dir):
        from app.engine.context.skill_loader import get_skill_loader, _reset_skill_loader
        _reset_skill_loader()
        with patch("app.engine.context.skill_loader._DEFAULT_SKILLS_DIR", skill_dir):
            loader1 = get_skill_loader()
            loader2 = get_skill_loader()
            assert loader1 is loader2
            _reset_skill_loader()


class TestPromptAdditionFormatting:
    def test_multiple_skills_concatenated(self):
        from app.engine.context.skill_loader import ContextSkill, ContextSkillLoader
        skills = [
            ContextSkill(name="a", host_type="lms", page_types=["quiz"],
                         description="", priority=1.0, prompt_addition="First block."),
            ContextSkill(name="b", host_type="lms", page_types=["quiz"],
                         description="", priority=0.5, prompt_addition="Second block."),
        ]
        prompt = ContextSkillLoader.get_prompt_addition(skills)
        assert "First block." in prompt
        assert "Second block." in prompt

    def test_empty_prompt_additions_skipped(self):
        from app.engine.context.skill_loader import ContextSkill, ContextSkillLoader
        skills = [
            ContextSkill(name="a", host_type="lms", page_types=["quiz"],
                         description="", priority=1.0, prompt_addition=""),
            ContextSkill(name="b", host_type="lms", page_types=["quiz"],
                         description="", priority=0.5, prompt_addition="Only this."),
        ]
        prompt = ContextSkillLoader.get_prompt_addition(skills)
        assert prompt.strip() == "Only this."

    def test_tool_ids_deduped(self):
        from app.engine.context.skill_loader import ContextSkill, ContextSkillLoader
        skills = [
            ContextSkill(name="a", host_type="lms", page_types=["quiz"],
                         description="", tools=["tool_a", "tool_b"]),
            ContextSkill(name="b", host_type="lms", page_types=["quiz"],
                         description="", tools=["tool_b", "tool_c"]),
        ]
        tool_ids = ContextSkillLoader.get_tool_ids(skills)
        assert sorted(tool_ids) == ["tool_a", "tool_b", "tool_c"]
