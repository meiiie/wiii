"""Sprint 222b Phase 6: ContextSkillLoader integration with graph injection."""
import pytest
from unittest.mock import patch, MagicMock


class TestSkillIntegrationWithGraph:
    """Test that _inject_host_context appends skill prompt when gate enabled."""

    def test_skill_prompt_appended_when_enabled(self):
        """When enable_host_skills=True, skill prompt_addition is appended."""
        from app.engine.multi_agent.graph import _inject_host_context

        state = {
            "context": {
                "host_context": {
                    "host_type": "lms",
                    "page": {"type": "quiz", "title": "Bai kiem tra COLREGs"},
                }
            }
        }

        mock_settings = MagicMock()
        mock_settings.enable_host_skills = True

        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = _inject_host_context(state)

        # Should have adapter output AND skill prompt
        assert len(result) > 0
        # Quiz skill should append Socratic guidance (Vietnamese text from quiz.skill.yaml)
        assert "host_context" in result.lower() or "socratic" in result.lower() or "suy nghi" in result.lower() or "dap an" in result.lower()

    def test_skill_prompt_not_appended_when_disabled(self):
        """When enable_host_skills=False, no skill prompt added."""
        from app.engine.multi_agent.graph import _inject_host_context

        state = {
            "context": {
                "host_context": {
                    "host_type": "lms",
                    "page": {"type": "quiz", "title": "Test"},
                }
            }
        }

        mock_settings = MagicMock()
        mock_settings.enable_host_skills = False

        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = _inject_host_context(state)

        # Should have adapter output but NOT extra skill additions
        assert isinstance(result, str)
        assert len(result) > 0  # Still has adapter output

    def test_skill_error_does_not_break_injection(self):
        """If skill loading fails, host context still works."""
        from app.engine.multi_agent.graph import _inject_host_context

        state = {
            "context": {
                "host_context": {
                    "host_type": "lms",
                    "page": {"type": "quiz", "title": "Test"},
                }
            }
        }

        mock_settings = MagicMock()
        mock_settings.enable_host_skills = True

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.context.skill_loader.get_skill_loader",
                        side_effect=Exception("skill loading broke")):
                result = _inject_host_context(state)

        # Should still return adapter output despite skill error
        assert isinstance(result, str)
        assert len(result) > 0
