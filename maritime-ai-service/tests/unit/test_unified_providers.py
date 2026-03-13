"""
Tests for unified provider mode (enable_unified_providers=True).

Phase 1: All LLM providers use ChatOpenAI via OpenAI-compatible endpoints.
Tests GeminiProvider, OllamaProvider, llm_factory, and llm_pool under the
unified providers gate.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.language_models import BaseChatModel

from app.engine.llm_providers.gemini_provider import GeminiProvider
from app.engine.llm_providers.ollama_provider import OllamaProvider
from app.engine.llm_pool import LLMPool, ThinkingTier


# ============================================================================
# GeminiProvider — Unified Mode
# ============================================================================


class TestGeminiProviderUnified:
    """Test GeminiProvider with enable_unified_providers=True."""

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_uses_chat_openai(self, mock_settings, mock_chat):
        """Unified mode uses ChatOpenAI, not ChatGoogleGenerativeAI."""
        mock_settings.enable_unified_providers = True
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_instance = MagicMock(spec=BaseChatModel)
        mock_chat.return_value = mock_instance

        p = GeminiProvider()
        llm = p.create_instance(tier="light", thinking_budget=0)

        assert llm == mock_instance
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
        assert call_kwargs["streaming"] is True

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_thinking_via_model_kwargs(self, mock_settings, mock_chat):
        """Thinking budget is passed via model_kwargs.extra_body."""
        mock_settings.enable_unified_providers = True
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="deep", thinking_budget=8192, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert "model_kwargs" in call_kwargs
        extra_body = call_kwargs["model_kwargs"]["extra_body"]
        assert extra_body["google"]["thinking_config"]["thinking_budget"] == 8192
        assert extra_body["google"]["thinking_config"]["include_thoughts"] is True

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_no_thinking_when_disabled(self, mock_settings, mock_chat):
        """No model_kwargs when thinking is disabled."""
        mock_settings.enable_unified_providers = True
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="light", thinking_budget=0)

        call_kwargs = mock_chat.call_args[1]
        assert "model_kwargs" not in call_kwargs

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_no_thinking_when_budget_zero(self, mock_settings, mock_chat):
        """No model_kwargs even when thinking_enabled but budget=0."""
        mock_settings.enable_unified_providers = True
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="light", thinking_budget=0)

        call_kwargs = mock_chat.call_args[1]
        assert "model_kwargs" not in call_kwargs


# ============================================================================
# OllamaProvider — Unified Mode
# ============================================================================


class TestOllamaProviderUnified:
    """Test OllamaProvider with enable_unified_providers=True."""

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_uses_chat_openai(self, mock_settings, mock_chat):
        """Unified mode uses ChatOpenAI, not ChatOllama."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:4b-instruct-2507-q4_K_M"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_instance = MagicMock(spec=BaseChatModel)
        mock_chat.return_value = mock_instance

        p = OllamaProvider()
        llm = p.create_instance(tier="moderate", thinking_budget=0)

        assert llm == mock_instance
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "qwen3:4b-instruct-2507-q4_K_M"
        assert call_kwargs["api_key"] == "ollama"  # Default for Ollama /v1
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"
        assert call_kwargs["streaming"] is True

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_appends_v1_to_base_url(self, mock_settings, mock_chat):
        """Ensures /v1 is appended to Ollama base URL."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434/"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="light")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_does_not_double_v1(self, mock_settings, mock_chat):
        """If base URL already ends with /v1, don't double it."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434/v1"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="light")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_custom_api_key(self, mock_settings, mock_chat):
        """Custom API key for Ollama Cloud is used."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "https://ollama.com"
        mock_settings.ollama_model = "gpt-oss:20b"
        mock_settings.ollama_api_key = "ollama-cloud-key"
        mock_settings.ollama_thinking_models = ["qwen3"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate")

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["api_key"] == "ollama-cloud-key"

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_thinking_mode_qwen3(self, mock_settings, mock_chat):
        """Thinking-capable model with budget > 0 passes extra_body."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:8b"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model_kwargs"]["extra_body"] == {"think": True}

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_no_thinking_for_non_thinking_model(self, mock_settings, mock_chat):
        """Non-thinking model does NOT get model_kwargs."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert "model_kwargs" not in call_kwargs

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_instruct_tag_excluded(self, mock_settings, mock_chat):
        """Qwen3 instruct tags are NOT thinking-capable."""
        mock_settings.enable_unified_providers = True
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:4b-instruct-2507-q4_K_M"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", thinking_budget=1024, include_thoughts=True)

        call_kwargs = mock_chat.call_args[1]
        assert "model_kwargs" not in call_kwargs


# ============================================================================
# LLM Factory — Unified Mode
# ============================================================================


class TestLLMFactoryUnified:
    """Test create_llm() with enable_unified_providers=True."""

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    @patch("app.engine.llm_factory.settings")
    def test_default_google_uses_unified_path(self, mock_factory_settings, mock_gemini_settings, mock_chat):
        """Default provider=google with unified gate goes through GeminiProvider."""
        mock_factory_settings.llm_provider = "google"
        mock_factory_settings.thinking_enabled = False
        mock_factory_settings.include_thought_summaries = False
        mock_factory_settings.enable_unified_providers = True

        mock_gemini_settings.enable_unified_providers = True
        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_gemini_settings.thinking_enabled = False

        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        from app.engine.llm_factory import create_llm
        llm = create_llm(tier=ThinkingTier.LIGHT)

        assert llm is not None
        mock_chat.assert_called_once()


# ============================================================================
# LLM Pool Legacy Path — Unified Mode
# ============================================================================


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset LLMPool state between tests."""
    LLMPool.reset()
    yield
    LLMPool.reset()


class TestLLMPoolLegacyUnified:
    """Test _create_instance_legacy with enable_unified_providers=True."""

    @patch("langchain_openai.ChatOpenAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    @patch("app.engine.llm_pool.settings")
    def test_legacy_path_uses_unified_provider(self, mock_pool_settings, mock_gemini_settings, mock_chat):
        """Legacy path delegates to GeminiProvider with unified gate on."""
        mock_pool_settings.enable_llm_failover = False
        mock_pool_settings.enable_unified_providers = True
        mock_pool_settings.google_api_key = "test-key"
        mock_pool_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_pool_settings.llm_failover_chain = ["google"]

        mock_gemini_settings.enable_unified_providers = True
        mock_gemini_settings.google_api_key = "test-key"
        mock_gemini_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_gemini_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_gemini_settings.thinking_enabled = True

        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        LLMPool._providers = {}  # Empty providers to trigger legacy path
        llm = LLMPool._create_instance("moderate")

        assert llm is not None
        mock_chat.assert_called_once()
        assert LLMPool._active_provider == "google"


# ============================================================================
# Backward Compatibility — Gate Off
# ============================================================================


class TestGateOffBackwardCompat:
    """Verify that with enable_unified_providers=False, everything works as before."""

    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_gemini_uses_native_provider(self, mock_settings, mock_chat):
        """With gate off, GeminiProvider uses ChatGoogleGenerativeAI."""
        mock_settings.enable_unified_providers = False
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.thinking_enabled = False
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        llm = p.create_instance(tier="light", thinking_budget=0)

        assert llm is not None
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
        assert call_kwargs["google_api_key"] == "test-key"

    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_ollama_uses_native_provider(self, mock_settings):
        """With gate off, OllamaProvider uses ChatOllama."""
        import sys

        mock_settings.enable_unified_providers = False
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_settings.ollama_keep_alive = None
        mock_settings.ollama_thinking_models = ["qwen3"]

        mock_chat_ollama = MagicMock(return_value=MagicMock(spec=BaseChatModel))
        mock_module = MagicMock()
        mock_module.ChatOllama = mock_chat_ollama

        with patch.dict(sys.modules, {"langchain_ollama": mock_module}):
            p = OllamaProvider()
            llm = p.create_instance(tier="moderate", temperature=0.5)
            mock_chat_ollama.assert_called_once()
            call_kwargs = mock_chat_ollama.call_args[1]
            assert call_kwargs["model"] == "llama3.2"

    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("app.engine.llm_pool.settings")
    def test_pool_legacy_uses_native_gemini(self, mock_settings, mock_chat):
        """With gate off, pool legacy path uses ChatGoogleGenerativeAI directly."""
        mock_settings.enable_llm_failover = False
        mock_settings.enable_unified_providers = False
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3.1-flash-lite-preview"
        mock_settings.thinking_enabled = True
        mock_settings.llm_failover_chain = ["google"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        LLMPool._providers = {}
        llm = LLMPool._create_instance("moderate")

        assert llm is not None
        mock_chat.assert_called_once()
        assert LLMPool._active_provider == "google"
