"""Sprint 135: Soul Emotion prompt injection tests."""
import pytest
from unittest.mock import patch, MagicMock


class TestSoulEmotionPromptInjection:
    """Tests for soul emotion instructions in prompt_loader."""

    def test_prompt_injected_when_enabled(self):
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = True
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                assert "WIII_SOUL" in prompt
                assert "BIỂU CẢM" in prompt

    def test_prompt_not_injected_when_disabled(self):
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = False
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                assert "WIII_SOUL" not in prompt

    def test_all_five_moods_have_examples(self):
        """All 5 moods must have at least one example in the prompt."""
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = True
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                assert '"mood":"excited"' in prompt
                assert '"mood":"warm"' in prompt
                assert '"mood":"concerned"' in prompt
                assert '"mood":"gentle"' in prompt
                assert '"mood":"neutral"' in prompt

    def test_schema_with_ranges(self):
        """JSON schema must document field ranges."""
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = True
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                assert "mouthCurve" in prompt
                assert "intensity" in prompt
                assert "face" in prompt
                # Check ranges are documented
                assert "-1.0..1.0" in prompt
                assert "0.0..1.0" in prompt
                assert "0.5..1.5" in prompt

    def test_chain_of_thought_hint(self):
        """Prompt should include thinking guidance for better LLM output."""
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = True
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                assert "suy nghĩ" in prompt  # chain-of-thought hint

    def test_at_least_seven_examples(self):
        """Prompt should have 7+ examples for reliable structured output."""
        with patch("app.prompts.prompt_loader._prompt_loader", None):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_soul_emotion = True
                mock_settings.identity_anchor_interval = 6
                from app.prompts.prompt_loader import PromptLoader
                loader = PromptLoader()
                prompt = loader.build_system_prompt("student", total_responses=0)
                # Count WIII_SOUL examples (each one is a complete tag)
                example_count = prompt.count('<!--WIII_SOUL:{')
                assert example_count >= 7, f"Expected >= 7 examples, got {example_count}"
