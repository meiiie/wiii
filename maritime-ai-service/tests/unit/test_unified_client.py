"""
Tests for app.engine.llm_providers.unified_client — UnifiedLLMClient.

Sprint 55: Phase 1 — Unified Provider Layer (AsyncOpenAI SDK).
Tests initialization, get_client, get_model, feature gates, error handling.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass

from app.engine.llm_providers.unified_client import (
    UnifiedLLMClient,
    ProviderConfig,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_unified_client():
    """Reset UnifiedLLMClient state before each test."""
    UnifiedLLMClient.reset()
    yield
    UnifiedLLMClient.reset()


def _make_settings(**overrides):
    """Create a mock settings object with defaults for unified client tests."""
    defaults = {
        "enable_unified_client": True,
        "google_api_key": "test-google-key",
        "google_model": "gemini-3-flash-preview",
        "google_model_advanced": "gemini-3.1-pro-preview",
        "google_openai_compat_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "openai_api_key": "test-openai-key",
        "openai_base_url": None,
        "openai_model": "gpt-4o-mini",
        "openai_model_advanced": "gpt-4o",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3.2",
        "llm_failover_chain": ["google", "openai", "ollama"],
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


# ============================================================================
# ProviderConfig Tests
# ============================================================================


class TestProviderConfig:
    """Test ProviderConfig dataclass."""

    def test_default_models_populated(self):
        """Empty models dict gets populated with default_model."""
        config = ProviderConfig(
            name="test",
            api_key="key",
            base_url="http://test",
            default_model="test-model",
        )
        assert config.models["deep"] == "test-model"
        assert config.models["moderate"] == "test-model"
        assert config.models["light"] == "test-model"

    def test_explicit_models_preserved(self):
        """Explicit models dict is NOT overwritten."""
        config = ProviderConfig(
            name="test",
            api_key="key",
            base_url="http://test",
            default_model="default",
            models={"deep": "big", "moderate": "mid", "light": "small"},
        )
        assert config.models["deep"] == "big"
        assert config.models["moderate"] == "mid"
        assert config.models["light"] == "small"

    def test_thinking_config(self):
        """ProviderConfig stores thinking parameters."""
        config = ProviderConfig(
            name="google",
            api_key="key",
            base_url="http://test",
            default_model="gemini",
            supports_thinking=True,
            thinking_param="thinking_budget",
        )
        assert config.supports_thinking is True
        assert config.thinking_param == "thinking_budget"

    def test_defaults(self):
        """Default values for optional fields."""
        config = ProviderConfig(
            name="test",
            api_key="key",
            base_url="http://test",
            default_model="m",
        )
        assert config.supports_thinking is False
        assert config.thinking_param == ""


# ============================================================================
# UnifiedLLMClient — Feature Gate
# ============================================================================


class TestUnifiedClientFeatureGate:
    """Test feature gating (enable_unified_client=False)."""

    def test_disabled_by_default(self):
        """When enable_unified_client=False, no clients are created."""
        mock_settings = _make_settings(enable_unified_client=False)

        with patch("app.engine.llm_providers.unified_client.AsyncOpenAI", create=True):
            with patch(
                "app.engine.llm_providers.unified_client.settings",
                mock_settings,
                create=True,
            ):
                # Patch the lazy import
                with patch(
                    "app.core.config.settings", mock_settings
                ):
                    UnifiedLLMClient.initialize()

        assert not UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == []

    def test_not_initialized_raises_on_get_client(self):
        """get_client() raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            UnifiedLLMClient.get_client()

    def test_not_initialized_raises_on_get_config(self):
        """get_config() raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            UnifiedLLMClient.get_config()

    def test_not_initialized_raises_on_get_model(self):
        """get_model() raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            UnifiedLLMClient.get_model()


# ============================================================================
# UnifiedLLMClient — Initialization
# ============================================================================


class TestUnifiedClientInitialization:
    """Test initialization with different provider configurations."""

    def test_initialize_all_providers(self):
        """Initialize with all 3 providers configured."""
        mock_settings = _make_settings()
        mock_async_openai = MagicMock()
        mock_async_openai_cls = MagicMock(return_value=mock_async_openai)

        with patch(
            "app.engine.llm_providers.unified_client.importlib_or_direct",
            side_effect=None,
            create=True,
        ):
            with patch("app.core.config.settings", mock_settings):
                # Mock the openai import inside initialize()
                import types

                mock_openai_module = types.ModuleType("openai")
                mock_openai_module.AsyncOpenAI = mock_async_openai_cls

                with patch.dict(
                    "sys.modules", {"openai": mock_openai_module}
                ):
                    UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert len(UnifiedLLMClient.get_available_providers()) == 3
        assert "google" in UnifiedLLMClient.get_available_providers()
        assert "openai" in UnifiedLLMClient.get_available_providers()
        assert "ollama" in UnifiedLLMClient.get_available_providers()

    def test_initialize_google_only(self):
        """Initialize with only Google configured."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == ["google"]

    def test_initialize_openai_only(self):
        """Initialize with only OpenAI configured."""
        mock_settings = _make_settings(
            google_api_key=None,
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == ["openai"]

    def test_initialize_ollama_only(self):
        """Initialize with only Ollama configured."""
        mock_settings = _make_settings(
            google_api_key=None,
            openai_api_key=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == ["ollama"]

    def test_initialize_no_providers(self):
        """Initialize with no providers configured — still initializes, empty."""
        mock_settings = _make_settings(
            google_api_key=None,
            openai_api_key=None,
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == []

    def test_openai_package_not_installed(self):
        """Graceful degradation when openai package is not installed."""
        mock_settings = _make_settings()

        with patch("app.core.config.settings", mock_settings):
            # Simulate ImportError for openai
            with patch.dict("sys.modules", {"openai": None}):
                UnifiedLLMClient.initialize()

        # Should not crash, but not be initialized either
        assert not UnifiedLLMClient.is_initialized()

    def test_primary_provider_follows_failover_chain(self):
        """Primary provider is the first available in failover chain."""
        mock_settings = _make_settings(
            google_api_key=None,
            llm_failover_chain=["google", "openai", "ollama"],
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        # Google is skipped (no key), so primary is openai
        assert UnifiedLLMClient._primary_provider == "openai"

    def test_duplicate_providers_in_chain_ignored(self):
        """Duplicate provider names in failover chain are ignored."""
        mock_settings = _make_settings(
            llm_failover_chain=["google", "google", "openai"],
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        providers = UnifiedLLMClient.get_available_providers()
        assert providers.count("google") == 1


# ============================================================================
# UnifiedLLMClient — get_client / get_model
# ============================================================================


class TestUnifiedClientAccess:
    """Test get_client and get_model after initialization."""

    def _init_with_all_providers(self):
        """Helper to initialize with all providers."""
        mock_settings = _make_settings()
        mock_clients = {}

        def mock_async_openai_factory(**kwargs):
            client = MagicMock()
            client._base_url = kwargs.get("base_url", "")
            mock_clients[kwargs.get("base_url", "")] = client
            return client

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_factory

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

    def test_get_client_default(self):
        """get_client() returns primary provider client."""
        self._init_with_all_providers()
        client = UnifiedLLMClient.get_client()
        assert client is not None

    def test_get_client_specific_provider(self):
        """get_client('openai') returns OpenAI-specific client."""
        self._init_with_all_providers()
        client = UnifiedLLMClient.get_client("openai")
        assert client is not None

    def test_get_client_unknown_provider(self):
        """get_client('unknown') raises RuntimeError."""
        self._init_with_all_providers()
        with pytest.raises(RuntimeError, match="not available"):
            UnifiedLLMClient.get_client("unknown")

    def test_get_model_deep(self):
        """get_model returns correct model for 'deep' tier."""
        self._init_with_all_providers()
        model = UnifiedLLMClient.get_model("google", "deep")
        assert model == "gemini-3.1-pro-preview"

    def test_get_model_openai_deep(self):
        """get_model('openai', 'deep') returns advanced model."""
        self._init_with_all_providers()
        model = UnifiedLLMClient.get_model("openai", "deep")
        assert model == "gpt-4o"

    def test_get_model_openai_moderate(self):
        """get_model('openai', 'moderate') returns standard model."""
        self._init_with_all_providers()
        model = UnifiedLLMClient.get_model("openai", "moderate")
        assert model == "gpt-4o-mini"

    def test_get_model_unknown_tier_fallback(self):
        """get_model with unknown tier falls back to default_model."""
        self._init_with_all_providers()
        model = UnifiedLLMClient.get_model("google", "ultra")
        assert model == "gemini-3-flash-preview"

    def test_get_config_returns_provider_config(self):
        """get_config() returns ProviderConfig for the provider."""
        self._init_with_all_providers()
        config = UnifiedLLMClient.get_config("google")
        assert isinstance(config, ProviderConfig)
        assert config.name == "google"
        assert config.supports_thinking is True
        assert config.thinking_param == "thinking_budget"

    def test_get_config_ollama(self):
        """get_config('ollama') has correct base_url with /v1 suffix."""
        self._init_with_all_providers()
        config = UnifiedLLMClient.get_config("ollama")
        assert config.base_url == "http://localhost:11434/v1"
        assert config.api_key == "ollama"


# ============================================================================
# UnifiedLLMClient — Provider URL Mapping
# ============================================================================


class TestProviderURLMapping:
    """Test provider-specific URL and key mapping."""

    def test_google_base_url(self):
        """Google uses generativelanguage.googleapis.com endpoint."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert len(configs) == 1
        assert configs[0].base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"

    def test_openai_default_base_url(self):
        """OpenAI defaults to api.openai.com/v1."""
        mock_settings = _make_settings(
            google_api_key=None,
            ollama_base_url=None,
            openai_base_url=None,
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert len(configs) == 1
        assert configs[0].base_url == "https://api.openai.com/v1"

    def test_openai_custom_base_url(self):
        """OpenAI respects custom base_url (e.g., OpenRouter)."""
        mock_settings = _make_settings(
            google_api_key=None,
            ollama_base_url=None,
            openai_base_url="https://openrouter.ai/api/v1",
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert len(configs) == 1
        assert configs[0].base_url == "https://openrouter.ai/api/v1"

    def test_ollama_appends_v1(self):
        """Ollama base_url gets /v1 appended."""
        mock_settings = _make_settings(
            google_api_key=None,
            openai_api_key=None,
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert len(configs) == 1
        assert configs[0].base_url == "http://localhost:11434/v1"

    def test_ollama_strips_trailing_slash(self):
        """Ollama base_url trailing slash is stripped before /v1."""
        mock_settings = _make_settings(
            google_api_key=None,
            openai_api_key=None,
            ollama_base_url="http://localhost:11434/",
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert configs[0].base_url == "http://localhost:11434/v1"

    def test_unknown_provider_skipped(self):
        """Unknown provider names in failover chain are skipped."""
        mock_settings = _make_settings(
            llm_failover_chain=["unknown_provider"],
            google_api_key=None,
            openai_api_key=None,
            ollama_base_url=None,
        )
        configs = UnifiedLLMClient._build_provider_configs(mock_settings)
        assert len(configs) == 0


# ============================================================================
# UnifiedLLMClient — Reset
# ============================================================================


class TestUnifiedClientReset:
    """Test reset functionality."""

    def test_reset_clears_state(self):
        """reset() clears all clients and configs."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert len(UnifiedLLMClient.get_available_providers()) == 1

        UnifiedLLMClient.reset()

        assert not UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == []

    def test_reinitialize_after_reset(self):
        """Can reinitialize after reset."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )
        mock_async_openai_cls = MagicMock(return_value=MagicMock())

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = mock_async_openai_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()
                assert UnifiedLLMClient.is_initialized()

                UnifiedLLMClient.reset()
                assert not UnifiedLLMClient.is_initialized()

                UnifiedLLMClient.initialize()
                assert UnifiedLLMClient.is_initialized()


# ============================================================================
# UnifiedLLMClient — AsyncOpenAI Client Creation
# ============================================================================


class TestAsyncOpenAICreation:
    """Test that AsyncOpenAI is created with correct parameters."""

    def test_google_client_params(self):
        """Google client created with correct api_key and base_url."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )
        created_params = []

        def capture_params(**kwargs):
            created_params.append(kwargs)
            return MagicMock()

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = capture_params

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert len(created_params) == 1
        assert created_params[0]["api_key"] == "test-google-key"
        assert "generativelanguage.googleapis.com" in created_params[0]["base_url"]

    def test_ollama_client_uses_dummy_key(self):
        """Ollama client uses 'ollama' as api_key."""
        mock_settings = _make_settings(
            google_api_key=None,
            openai_api_key=None,
        )
        created_params = []

        def capture_params(**kwargs):
            created_params.append(kwargs)
            return MagicMock()

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = capture_params

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert len(created_params) == 1
        assert created_params[0]["api_key"] == "ollama"

    def test_client_creation_failure_skips_provider(self):
        """If AsyncOpenAI() raises, that provider is skipped gracefully."""
        mock_settings = _make_settings(
            openai_api_key=None,
            ollama_base_url=None,
        )

        def raise_on_create(**kwargs):
            raise Exception("Connection refused")

        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_module.AsyncOpenAI = raise_on_create

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                UnifiedLLMClient.initialize()

        assert UnifiedLLMClient.is_initialized()
        assert UnifiedLLMClient.get_available_providers() == []
