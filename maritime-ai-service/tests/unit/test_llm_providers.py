"""
Tests for app.engine.llm_providers — LLM Provider Abstraction Layer.

Sprint 11: Multi-Provider LLM Failover & Resilience.
Tests provider ABC, Gemini/OpenAI/Ollama provider creation, is_available, is_configured.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from langchain_core.language_models import BaseChatModel

from app.engine.llm_providers.base import LLMProvider
from app.engine.llm_providers.gemini_provider import GeminiProvider
from app.engine.llm_providers.openai_provider import OpenAIProvider
from app.engine.llm_providers.ollama_provider import (
    OllamaProvider,
    check_ollama_host_reachable,
    reset_ollama_availability_cache,
)


# ============================================================================
# LLMProvider ABC Tests
# ============================================================================


class TestLLMProviderABC:
    """Test the abstract base class interface."""

    def test_cannot_instantiate_abc(self):
        """LLMProvider is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_abc_requires_name(self):
        """Subclass must implement name property."""

        class IncompleteProvider(LLMProvider):
            def is_configured(self):
                return True

            def create_instance(self, tier, **kwargs):
                return MagicMock()

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_abc_requires_is_configured(self):
        """Subclass must implement is_configured method."""

        class IncompleteProvider(LLMProvider):
            @property
            def name(self):
                return "test"

            def create_instance(self, tier, **kwargs):
                return MagicMock()

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_abc_requires_create_instance(self):
        """Subclass must implement create_instance method."""

        class IncompleteProvider(LLMProvider):
            @property
            def name(self):
                return "test"

            def is_configured(self):
                return True

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_is_available_defaults_to_is_configured(self):
        """Default is_available() returns is_configured()."""

        class MinimalProvider(LLMProvider):
            @property
            def name(self):
                return "minimal"

            def is_configured(self):
                return True

            def create_instance(self, tier, **kwargs):
                return MagicMock()

        p = MinimalProvider()
        assert p.is_available() is True

    def test_repr_contains_class_name(self):
        """__repr__ includes class name and configured status."""

        class TestProvider(LLMProvider):
            @property
            def name(self):
                return "test_prov"

            def is_configured(self):
                return False

            def create_instance(self, tier, **kwargs):
                return MagicMock()

        p = TestProvider()
        r = repr(p)
        assert "TestProvider" in r
        assert "test_prov" in r
        assert "False" in r


# ============================================================================
# GeminiProvider Tests
# ============================================================================


class TestGeminiProvider:
    """Test the Google Gemini provider."""

    def test_name_is_google(self):
        p = GeminiProvider()
        assert p.name == "google"

    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_is_configured_with_api_key(self, mock_settings):
        mock_settings.google_api_key = "test-key-123"
        p = GeminiProvider()
        assert p.is_configured() is True

    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_not_configured_without_api_key(self, mock_settings):
        mock_settings.google_api_key = None
        p = GeminiProvider()
        assert p.is_configured() is False

    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_not_configured_empty_api_key(self, mock_settings):
        mock_settings.google_api_key = ""
        p = GeminiProvider()
        assert p.is_configured() is False

    @patch("app.engine.llm_providers.gemini_provider._gemini_cb", None)
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_is_available_no_circuit_breaker(self, mock_settings):
        """Available when configured and no circuit breaker."""
        mock_settings.google_api_key = "key"
        p = GeminiProvider()
        assert p.is_available() is True

    @patch("app.engine.llm_providers.gemini_provider._gemini_cb")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_is_available_circuit_breaker_closed(self, mock_settings, mock_cb):
        mock_settings.google_api_key = "key"
        mock_cb.is_available.return_value = True
        p = GeminiProvider()
        assert p.is_available() is True

    @patch("app.engine.llm_providers.gemini_provider._gemini_cb")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_not_available_circuit_breaker_open(self, mock_settings, mock_cb):
        mock_settings.google_api_key = "key"
        mock_cb.is_available.return_value = False
        p = GeminiProvider()
        assert p.is_available() is False

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_returns_base_chat_model(self, mock_settings, mock_chat):
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_instance = MagicMock(spec=BaseChatModel)
        mock_chat.return_value = mock_instance

        p = GeminiProvider()
        llm = p.create_instance(tier="deep", thinking_budget=8192, include_thoughts=True)
        assert llm == mock_instance
        mock_chat.assert_called_once()
        assert mock_chat.call_args[1]["model"] == "gemini-3.1-pro-preview"

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_without_thinking(self, mock_settings, mock_chat):
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_instance = MagicMock(spec=BaseChatModel)
        mock_chat.return_value = mock_instance

        p = GeminiProvider()
        llm = p.create_instance(tier="light", thinking_budget=0)
        assert llm == mock_instance
        # When thinking disabled, model_kwargs should be empty (no extra_body)
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs.get("model_kwargs", {}) == {}

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_with_thinking_budget_high(self, mock_settings, mock_chat):
        """High budget (>4096) maps to reasoning_effort=high.

        The legacy ``extra_body={"google": {"thinking_config": ...}}`` shape
        was rejected by Gemini's OpenAI-compatible endpoint with
        ``Unknown name "google": Cannot find field``. The provider now maps
        ``thinking_budget`` to OpenAI-style ``reasoning_effort`` (low/medium/
        high) so the same call works against the v1beta/openai/ endpoint.
        """
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="deep", thinking_budget=8192, include_thoughts=True)
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gemini-3.1-pro-preview"
        model_kwargs = call_kwargs["model_kwargs"]
        assert model_kwargs == {"reasoning_effort": "high"}
        # Legacy shape must NOT be present — Gemini rejects it
        assert "extra_body" not in model_kwargs

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_with_thinking_budget_medium(self, mock_settings, mock_chat):
        """Budget in (1024, 4096] maps to reasoning_effort=medium."""
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="moderate", thinking_budget=2048)
        model_kwargs = mock_chat.call_args[1]["model_kwargs"]
        assert model_kwargs == {"reasoning_effort": "medium"}

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_with_thinking_budget_low(self, mock_settings, mock_chat):
        """Budget <=1024 maps to reasoning_effort=low."""
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = True
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="light", thinking_budget=512)
        model_kwargs = mock_chat.call_args[1]["model_kwargs"]
        assert model_kwargs == {"reasoning_effort": "low"}

    @patch("app.engine.llm_providers.gemini_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.gemini_provider.settings")
    def test_create_instance_thinking_disabled_in_settings_skips_effort(self, mock_settings, mock_chat):
        """thinking_enabled=False suppresses reasoning_effort even with positive budget."""
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.google_model_advanced = "gemini-3.1-pro-preview"
        mock_settings.google_openai_compat_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        mock_settings.thinking_enabled = False
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = GeminiProvider()
        p.create_instance(tier="deep", thinking_budget=8192)
        model_kwargs = mock_chat.call_args[1]["model_kwargs"]
        assert model_kwargs == {}


# ============================================================================
# OpenAIProvider Tests
# ============================================================================


class TestOpenAIProvider:
    """Test the OpenAI/OpenRouter provider."""

    def test_name_is_openai(self):
        p = OpenAIProvider()
        assert p.name == "openai"

    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_is_configured_with_api_key(self, mock_settings):
        mock_settings.openai_api_key = "sk-test-123"
        p = OpenAIProvider()
        assert p.is_configured() is True

    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_not_configured_without_api_key(self, mock_settings):
        mock_settings.openai_api_key = None
        p = OpenAIProvider()
        assert p.is_configured() is False

    @patch(
        "app.engine.llm_providers.openai_provider._get_openai_compatible_circuit_breaker",
        return_value=None,
    )
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_is_available_no_circuit_breaker(self, mock_settings, _mock_cb_factory):
        mock_settings.openai_api_key = "sk-test"
        p = OpenAIProvider()
        assert p.is_available() is True

    @patch("app.engine.llm_providers.openai_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_create_instance_deep_uses_advanced_model(self, mock_settings, mock_chat):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.openai_model_advanced = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OpenAIProvider()
        llm = p.create_instance(tier="deep")
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"

    @patch("app.engine.llm_providers.openai_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_create_instance_light_uses_standard_model(self, mock_settings, mock_chat):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.openai_model_advanced = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OpenAIProvider()
        llm = p.create_instance(tier="light")
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"

    @patch("app.engine.llm_providers.openai_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_create_instance_with_custom_base_url(self, mock_settings, mock_chat):
        """Support OpenRouter via custom base_url."""
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.openai_model_advanced = "gpt-4o"
        mock_settings.openai_base_url = "https://openrouter.ai/api/v1"
        mock_settings.openrouter_model_fallbacks = []
        mock_settings.openrouter_provider_order = []
        mock_settings.openrouter_allowed_providers = []
        mock_settings.openrouter_ignored_providers = []
        mock_settings.openrouter_allow_fallbacks = None
        mock_settings.openrouter_require_parameters = None
        mock_settings.openrouter_data_collection = None
        mock_settings.openrouter_zdr = None
        mock_settings.openrouter_provider_sort = None
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OpenAIProvider()
        p.create_instance(tier="moderate")
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"

    @patch("app.engine.llm_providers.openai_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_create_instance_adds_openrouter_extra_body(self, mock_settings, mock_chat):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_model = "openai/gpt-oss-20b:free"
        mock_settings.openai_model_advanced = "openai/gpt-oss-120b:free"
        mock_settings.openai_base_url = "https://openrouter.ai/api/v1"
        mock_settings.openrouter_model_fallbacks = ["anthropic/claude-sonnet-4"]
        mock_settings.openrouter_provider_order = ["anthropic", "openai"]
        mock_settings.openrouter_allowed_providers = []
        mock_settings.openrouter_ignored_providers = []
        mock_settings.openrouter_allow_fallbacks = False
        mock_settings.openrouter_require_parameters = True
        mock_settings.openrouter_data_collection = "deny"
        mock_settings.openrouter_zdr = True
        mock_settings.openrouter_provider_sort = "latency"
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OpenAIProvider()
        p.create_instance(tier="moderate")
        call_kwargs = mock_chat.call_args[1]
        # extra_body is now inside model_kwargs
        assert call_kwargs["model_kwargs"]["extra_body"] == {
            "models": ["anthropic/claude-sonnet-4"],
            "provider": {
                "order": ["anthropic", "openai"],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
                "zdr": True,
                "sort": "latency",
            },
        }

    @patch("app.engine.llm_providers.openai_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.openai_provider.settings")
    def test_create_instance_no_base_url(self, mock_settings, mock_chat):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.openai_model_advanced = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_settings.openrouter_model_fallbacks = ["anthropic/claude-sonnet-4"]
        mock_settings.openrouter_provider_order = ["anthropic"]
        mock_settings.openrouter_allowed_providers = []
        mock_settings.openrouter_ignored_providers = []
        mock_settings.openrouter_allow_fallbacks = False
        mock_settings.openrouter_require_parameters = True
        mock_settings.openrouter_data_collection = "deny"
        mock_settings.openrouter_zdr = True
        mock_settings.openrouter_provider_sort = "latency"
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OpenAIProvider()
        p.create_instance(tier="moderate")
        call_kwargs = mock_chat.call_args[1]
        # When no base_url, it's passed as empty string
        assert call_kwargs["base_url"] == ""
        # No OpenRouter extra_body when base_url is not an OpenRouter URL
        assert "extra_body" not in call_kwargs.get("model_kwargs", {})


# ============================================================================
# OllamaProvider Tests
# ============================================================================


class TestOllamaProvider:
    """Test the Ollama (local) provider."""

    def setup_method(self):
        reset_ollama_availability_cache()

    def test_name_is_ollama(self):
        p = OllamaProvider()
        assert p.name == "ollama"

    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_is_configured_with_base_url(self, mock_settings):
        mock_settings.ollama_base_url = "http://localhost:11434"
        p = OllamaProvider()
        assert p.is_configured() is True

    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_not_configured_without_base_url(self, mock_settings):
        mock_settings.ollama_base_url = None
        p = OllamaProvider()
        assert p.is_configured() is False

    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_not_configured_empty_base_url(self, mock_settings):
        mock_settings.ollama_base_url = ""
        p = OllamaProvider()
        assert p.is_configured() is False

    @patch("app.engine.llm_providers.ollama_provider._ollama_cb", None)
    @patch("app.engine.llm_providers.ollama_provider.check_ollama_host_reachable", return_value=True)
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_is_available_no_circuit_breaker(self, mock_settings, _mock_reachable):
        mock_settings.ollama_base_url = "http://localhost:11434"
        p = OllamaProvider()
        assert p.is_available() is True

    @patch("app.engine.llm_providers.ollama_provider._ollama_cb", None)
    @patch("app.engine.llm_providers.ollama_provider.check_ollama_host_reachable", return_value=False)
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_not_available_when_ollama_host_unreachable(self, mock_settings, _mock_reachable):
        mock_settings.ollama_base_url = "http://localhost:11434"
        p = OllamaProvider()
        assert p.is_available() is False

    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_check_ollama_host_reachable_via_version_endpoint(self, mock_settings):
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_api_key = None

        mock_response = MagicMock(status_code=200)
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.get.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            assert check_ollama_host_reachable(force_refresh=True) is True

        called_url = mock_client.get.call_args[0][0]
        assert called_url == "http://localhost:11434/api/version"

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_create_instance_uses_config(self, mock_settings, mock_chat):
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_api_key = None
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        llm = p.create_instance(tier="moderate", temperature=0.5)
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model"] == "llama3.2"
        # OllamaProvider appends /v1 for OpenAI-compat endpoint
        assert call_kwargs["base_url"] == "http://localhost:11434/v1"
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["api_key"] == "ollama"  # default placeholder

    @patch("app.engine.llm_providers.ollama_provider.WiiiChatModel")
    @patch("app.engine.llm_providers.ollama_provider.settings")
    def test_create_instance_with_cloud_api_key_sets_auth_header(self, mock_settings, mock_chat):
        mock_settings.ollama_base_url = "https://ollama.com/api"
        mock_settings.ollama_model = "gpt-oss:20b"
        mock_settings.ollama_api_key = "ollama-cloud-key"
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        p = OllamaProvider()
        p.create_instance(tier="moderate", temperature=0.1)
        call_kwargs = mock_chat.call_args[1]
        # Cloud key is passed directly as api_key (OpenAI SDK uses Bearer auth)
        assert call_kwargs["api_key"] == "ollama-cloud-key"
        assert call_kwargs["base_url"] == "https://ollama.com/api/v1"

    def test_create_instance_propagates_errors(self):
        """Errors from WiiiChatModel creation propagate correctly."""
        p = OllamaProvider()
        with patch.object(
            OllamaProvider,
            "create_instance",
            side_effect=RuntimeError("connection refused"),
        ):
            with pytest.raises(RuntimeError, match="connection refused"):
                p.create_instance(tier="light")


# ============================================================================
# Provider __init__ Package Tests
# ============================================================================


class TestProviderPackage:
    """Test the providers package exports."""

    def test_all_exports(self):
        from app.engine.llm_providers import __all__

        assert "LLMProvider" in __all__
        assert "GeminiProvider" in __all__
        assert "OpenAIProvider" in __all__
        assert "OllamaProvider" in __all__

    def test_import_base(self):
        from app.engine.llm_providers import LLMProvider

        assert LLMProvider is not None

    def test_import_all_providers(self):
        from app.engine.llm_providers import (
            GeminiProvider,
            OpenAIProvider,
            OllamaProvider,
        )

        assert GeminiProvider is not None
        assert OpenAIProvider is not None
        assert OllamaProvider is not None

    def test_all_providers_implement_abc(self):
        """All providers are subclasses of LLMProvider."""
        assert issubclass(GeminiProvider, LLMProvider)
        assert issubclass(OpenAIProvider, LLMProvider)
        assert issubclass(OllamaProvider, LLMProvider)
