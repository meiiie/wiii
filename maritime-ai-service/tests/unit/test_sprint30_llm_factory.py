"""
Tests for Sprint 30: LLM Factory coverage.

Covers:
- ThinkingTier enum values
- get_thinking_budget: config-driven, disabled, per-tier
- create_llm: default Gemini, explicit provider, fallback on import error
"""

import pytest
from unittest.mock import patch, MagicMock
from app.engine.llm_providers.wiii_chat_model import WiiiChatModel
from app.engine.llm_factory import ThinkingTier, get_thinking_budget


# =============================================================================
# ThinkingTier
# =============================================================================


class TestThinkingTier:
    """ThinkingTier enum has correct values."""

    def test_all_tiers_exist(self):
        assert ThinkingTier.DEEP.value == "deep"
        assert ThinkingTier.MODERATE.value == "moderate"
        assert ThinkingTier.LIGHT.value == "light"
        assert ThinkingTier.MINIMAL.value == "minimal"
        assert ThinkingTier.DYNAMIC.value == "dynamic"
        assert ThinkingTier.OFF.value == "off"

    def test_six_tiers_total(self):
        assert len(ThinkingTier) == 6


# =============================================================================
# get_thinking_budget
# =============================================================================


class TestGetThinkingBudget:
    """Test thinking budget resolution from config."""

    def test_returns_zero_when_thinking_disabled(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = False

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.DEEP)

        assert result == 0

    def test_deep_tier_budget(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True
        mock_settings.thinking_budget_deep = 8192

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.DEEP)

        assert result == 8192

    def test_moderate_tier_budget(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True
        mock_settings.thinking_budget_moderate = 4096

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.MODERATE)

        assert result == 4096

    def test_light_tier_budget(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True
        mock_settings.thinking_budget_light = 1024

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.LIGHT)

        assert result == 1024

    def test_minimal_tier_budget(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True
        mock_settings.thinking_budget_minimal = 512

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.MINIMAL)

        assert result == 512

    def test_dynamic_tier_returns_minus_one(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.DYNAMIC)

        assert result == -1

    def test_off_tier_returns_zero(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = True

        with patch("app.engine.llm_factory.settings", mock_settings):
            result = get_thinking_budget(ThinkingTier.OFF)

        assert result == 0


# =============================================================================
# create_llm
# =============================================================================


class TestCreateLLM:
    """Test LLM creation factory."""

    def test_default_creates_gemini(self):
        """Default provider is Google Gemini via WiiiChatModel."""
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.llm_provider = "google"

        mock_gemini_settings = MagicMock()
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_openai_compat_url = "https://test.example.com/"
        mock_gemini_settings.thinking_enabled = False

        mock_wiii = MagicMock(spec=WiiiChatModel)

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_providers.gemini_provider.settings", mock_gemini_settings), \
             patch("app.engine.llm_providers.gemini_provider.WiiiChatModel", return_value=mock_wiii) as mock_cls:
            from app.engine.llm_factory import create_llm
            result = create_llm()

        assert result == mock_wiii
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
        assert call_kwargs["api_key"] == "test-key"

    def test_custom_model_override(self):
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.google_model = "default-model"
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.llm_provider = "google"

        mock_gemini_settings = MagicMock()
        mock_gemini_settings.google_model = "default-model"
        mock_gemini_settings.google_model_advanced = "advanced-model"
        mock_gemini_settings.google_api_key = "key"
        mock_gemini_settings.google_openai_compat_url = "https://test.example.com/"
        mock_gemini_settings.thinking_enabled = False

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_providers.gemini_provider.settings", mock_gemini_settings), \
             patch("app.engine.llm_providers.gemini_provider.WiiiChatModel", return_value=MagicMock()) as mock_cls:
            from app.engine.llm_factory import create_llm
            create_llm(model="custom-model")

        assert mock_cls.call_args[1]["model"] == "custom-model"

    def test_thinking_budget_added_when_enabled(self):
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = True
        mock_factory_settings.thinking_budget_deep = 8192
        mock_factory_settings.include_thought_summaries = True
        mock_factory_settings.llm_provider = "google"

        mock_gemini_settings = MagicMock()
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_gemini_settings.google_api_key = "key"
        mock_gemini_settings.google_openai_compat_url = "https://test.example.com/"
        mock_gemini_settings.thinking_enabled = True

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_providers.gemini_provider.settings", mock_gemini_settings), \
             patch("app.engine.llm_providers.gemini_provider.WiiiChatModel", return_value=MagicMock()) as mock_cls:
            from app.engine.llm_factory import create_llm
            create_llm(tier=ThinkingTier.DEEP)

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-pro-preview"
        assert call_kwargs["model_kwargs"]["reasoning_effort"] == "high"

    def test_thinking_not_added_when_budget_zero(self):
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = True
        mock_factory_settings.thinking_budget_off = 0
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.llm_provider = "google"

        mock_gemini_settings = MagicMock()
        mock_gemini_settings.google_model = "m"
        mock_gemini_settings.google_model_advanced = "m-adv"
        mock_gemini_settings.google_api_key = "k"
        mock_gemini_settings.google_openai_compat_url = "https://test.example.com/"
        mock_gemini_settings.thinking_enabled = True

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_providers.gemini_provider.settings", mock_gemini_settings), \
             patch("app.engine.llm_providers.gemini_provider.WiiiChatModel", return_value=MagicMock()) as mock_cls:
            from app.engine.llm_factory import create_llm
            create_llm(tier=ThinkingTier.OFF)

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}

    def test_explicit_provider_openai(self):
        """Explicit provider='openai' uses OpenAIProvider."""
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = False
        mock_settings.include_thought_summaries = False

        mock_provider = MagicMock()
        mock_provider.create_instance.return_value = "openai-llm"

        with patch("app.engine.llm_factory.settings", mock_settings), \
             patch("app.engine.llm_providers.OpenAIProvider", return_value=mock_provider):
            from app.engine.llm_factory import create_llm
            result = create_llm(provider="openai")

        assert result == "openai-llm"

    def test_unknown_provider_raises(self):
        mock_settings = MagicMock()
        mock_settings.thinking_enabled = False
        mock_settings.include_thought_summaries = False

        with patch("app.engine.llm_factory.settings", mock_settings):
            from app.engine.llm_factory import create_llm
            with pytest.raises(ValueError, match="Unknown provider"):
                create_llm(provider="unknown_provider")

    def test_provider_import_error_falls_back_to_gemini(self):
        """If explicit provider lookup fails with ImportError, fallback to Gemini."""
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.llm_provider = "openai"

        mock_openai_provider = MagicMock()
        mock_openai_provider.create_instance.side_effect = ImportError("no openai")
        mock_gemini_result = MagicMock()
        mock_gemini_provider = MagicMock()
        mock_gemini_provider.create_instance.return_value = mock_gemini_result

        def provider_factory(name):
            if name == "openai":
                return mock_openai_provider
            if name == "google":
                return mock_gemini_provider
            raise AssertionError(f"Unexpected provider: {name}")

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_factory.create_provider", side_effect=provider_factory):
            from app.engine.llm_factory import create_llm
            result = create_llm()

        assert result == mock_gemini_result
        mock_openai_provider.create_instance.assert_called_once()
        mock_gemini_provider.create_instance.assert_called_once()

    def test_deep_tier_uses_google_advanced_model(self):
        mock_factory_settings = MagicMock()
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.llm_provider = "google"

        mock_gemini_settings = MagicMock()
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_openai_compat_url = "https://test.example.com/"
        mock_gemini_settings.thinking_enabled = False

        with patch("app.engine.llm_factory.settings", mock_factory_settings), \
             patch("app.engine.llm_providers.gemini_provider.settings", mock_gemini_settings), \
             patch("app.engine.llm_providers.gemini_provider.WiiiChatModel", return_value=MagicMock()) as mock_cls:
            from app.engine.llm_factory import create_llm
            create_llm(tier=ThinkingTier.DEEP)

        assert mock_cls.call_args[1]["model"] == "gemini-3.1-pro-preview"
