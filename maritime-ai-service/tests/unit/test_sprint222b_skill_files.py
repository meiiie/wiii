"""Sprint 222b Phase 6: Verify YAML skill files are valid and loadable."""
import pytest
from pathlib import Path
import yaml


SKILLS_DIR = Path(__file__).parent.parent.parent / "app" / "engine" / "context" / "skills"

EXPECTED_FILES = [
    "lms/quiz.skill.yaml",
    "lms/lesson.skill.yaml",
    "lms/assignment.skill.yaml",
    "lms/course.skill.yaml",
    "lms/default.skill.yaml",
    "generic/default.skill.yaml",
]

REQUIRED_FIELDS = ["name", "host_type", "page_types", "description"]


class TestSkillFilesExist:
    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_skill_file_exists(self, rel_path):
        path = SKILLS_DIR / rel_path
        assert path.exists(), f"Missing skill file: {path}"


class TestSkillFilesValid:
    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_skill_file_parseable(self, rel_path):
        path = SKILLS_DIR / rel_path
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict), f"Skill file should be a dict: {rel_path}"
        for field in REQUIRED_FIELDS:
            assert field in raw, f"Missing required field '{field}' in {rel_path}"

    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_skill_file_loadable_as_context_skill(self, rel_path):
        from app.engine.context.skill_loader import ContextSkill
        path = SKILLS_DIR / rel_path
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        skill = ContextSkill(
            name=raw["name"],
            host_type=raw.get("host_type", "generic"),
            page_types=raw.get("page_types", ["*"]),
            description=raw.get("description", ""),
            priority=float(raw.get("priority", 0.5)),
            prompt_addition=raw.get("prompt_addition", ""),
            tools=raw.get("tools", []),
            enrichment_triggers=raw.get("enrichment_triggers", []),
        )
        assert skill.name


class TestSkillContent:
    def test_quiz_skill_never_reveal_answers(self):
        path = SKILLS_DIR / "lms" / "quiz.skill.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "quiz" in raw["page_types"]
        prompt = raw.get("prompt_addition", "")
        assert "đáp án" in prompt.lower() or "answer" in prompt.lower()

    def test_quiz_skill_has_socratic_guidance(self):
        path = SKILLS_DIR / "lms" / "quiz.skill.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        prompt = raw.get("prompt_addition", "")
        assert "socratic" in prompt.lower() or "gợi mở" in prompt.lower() or "suy nghĩ" in prompt.lower()

    def test_lms_default_is_wildcard(self):
        path = SKILLS_DIR / "lms" / "default.skill.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "*" in raw["page_types"]

    def test_generic_default_is_wildcard(self):
        path = SKILLS_DIR / "generic" / "default.skill.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "*" in raw["page_types"]
        assert raw["host_type"] == "generic"

    def test_loader_finds_production_skills(self):
        from app.engine.context.skill_loader import ContextSkillLoader
        loader = ContextSkillLoader(skills_dir=SKILLS_DIR)
        skills = loader.load_skills("lms", "quiz")
        assert len(skills) >= 1
        assert any(s.name == "lms-quiz" for s in skills)
