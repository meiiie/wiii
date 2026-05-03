"""
Tests for WiiiChatModel-backed providers (De-LangChaining Phase 1).

All LLM providers now use WiiiChatModel (AsyncOpenAI SDK) via OpenAI-compatible
endpoints. These tests verify provider behavior: model selection, thinking mode,
base URL handling, and integration with llm_factory / llm_pool.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.llm_providers.wiii_chat_model import WiiiChatModel
from app.engine.llm_providers.gemini_provider import GeminiProvider
from app.engine.llm_providers.ollama_provider import OllamaProvider
from app.engine.llm_pool import LLMPool, ThinkingTier


# ============================================================================
# GeminiProvider — WiiiChatModel backend
# ============================================================================


class TestGeminiProviderUnified:
    """Test GeminiProvider always uses WiiiChatModel."""

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_uses_wiii_chat_model(self, mock_settings, mock_chat):
        """GeminiProvider uses WiiiChatModel with correct api_key and base_url."""
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_instance = MagicMock(spec=WiiiChatModel)
        mock_chat.return_value = mock_instance

        p = GeminiProvider()
        llm = p.create_instance(tier="light", thinking_budget=0)

        assert llm == mock_instance
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_thinking_via_model_kwargs(self, mock_settings, mock_chat):
        """Thinking budget maps to OpenAI-compatible reasoning_effort."""
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = GeminiProvider()
        p.create_instance(tier="deep", thinking_budget=8192, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model_kwargs"] == {"reasoning_effort": "high"}

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_no_thinking_when_disabled(self, mock_settings, mock_chat):
        """No extra_body in model_kwargs when thinking is disabled."""
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = GeminiProvider()
        p.create_instance(tier="light", thinking_budget=0)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_no_thinking_when_budget_zero(self, mock_settings, mock_chat):
        """No extra_body even when thinking_enabled but budget=0."""
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = GeminiProvider()
        p.create_instance(tier="light", thinking_budget=0)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}


# ============================================================================
# OllamaProvider — WiiiChatModel backend
# ============================================================================


class TestOllamaProviderUnified:
    """Test OllamaProvider always uses WiiiChatModel at /v1 endpoint."""

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_uses_wiii_chat_model(self, mock_settings, mock_chat):
        """OllamaProvider uses WiiiChatModel with correct api_key and /v1 url."""
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:4b-instruct-2507-q4_K_M"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_instance = MagicMock(spec=WiiiChatModel)
        mock_chat.return_value = mock_instance

        p = OllamaProvider()
        llm = p.create_instance(tier="moderate", thinking_budget=0)

        assert llm == mock_instance
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "qwen3:4b-instruct-2507-q4_K_M"
        assert call_kwargs["api_key"] == "ollama"  # Default for Ollama /v1
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_appends_v1_to_base_url(self, mock_settings, mock_chat):
        """Ensures /v1 is appended to Ollama base URL."""
        mock_settings.ollama_base_url = "http://localhost:11434/"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="light")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_does_not_double_v1(self, mock_settings, mock_chat):
        """If base URL already ends with /v1, don't double it."""
        mock_settings.ollama_base_url = "http://localhost:11434/v1"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="light")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_custom_api_key(self, mock_settings, mock_chat):
        """Custom API key for Ollama Cloud is passed as api_key."""
        mock_settings.ollama_base_url = "https://ollama.com"
        mock_settings.ollama_model = "gpt-oss:20b"
        mock_settings.ollama_api_key = "ollama-cloud-key"
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["api_key"] == "ollama-cloud-key"

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_thinking_mode_qwen3(self, mock_settings, mock_chat):
        """Thinking-capable model with budget > 0 passes extra_body."""
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:8b"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model_kwargs"]["extra_body"] == {"think": True}

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_no_thinking_for_non_thinking_model(self, mock_settings, mock_chat):
        """Non-thinking model gets empty model_kwargs."""
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_instruct_tag_excluded(self, mock_settings, mock_chat):
        """Qwen3 instruct tags are NOT thinking-capable."""
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:4b-instruct-2507-q4_K_M"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}


# ============================================================================
# LLM Factory — WiiiChatModel path
# ============================================================================


class TestLLMFactoryUnified:
    """Test create_llm() routes through GeminiProvider → WiiiChatModel."""

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    @patch("app.engine.llm_factory.settings")
    def test_default_google_uses_wiii_chat_model(self, mock_factory_settings, mock_gemini_settings, mock_chat):
        """Default provider=google goes through GeminiProvider → WiiiChatModel."""
        mock_factory_settings.llm_provider = "google"
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.include_thought_summaries = False

        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_gemini_settings.thinking_enabled = False

        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        from app.engine.llm_factory import create_llm
        llm = create_llm(tier=ThinkingTier.LIGHT)

        assert llm is not None
        mock_chat.assert_called_once()


# ============================================================================
# LLM Pool Legacy Path — WiiiChatModel
# ============================================================================


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset LLMPool state between tests."""
    LLMPool.reset()
    yield
    LLMPool.reset()


class TestLLMPoolLegacyUnified:
    """Test LLMPool._create_instance delegates to GeminiProvider → WiiiChatModel."""

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    @patch("app.engine.llm_pool.settings")
    def test_legacy_path_uses_wiii_chat_model(self, mock_pool_settings, mock_gemini_settings, mock_chat):
        """Pool legacy path delegates to GeminiProvider which uses WiiiChatModel."""
        mock_pool_settings.enable_llm_failover = False
        mock_pool_settings.google_api_key = "test-key"
        mock_pool_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_pool_settings.llm_failover_chain = ["google"]

        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_gemini_settings.thinking_enabled = True

        mock_chat.return_value = MagicMock(spec=WiiiChatModel)

        LLMPool._providers = {}  # Empty providers to trigger legacy path
        llm = LLMPool._create_instance("moderate")

        assert llm is not None
        mock_chat.assert_called_once()
        assert LLMPool._active_provider == "google"
