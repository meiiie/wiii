"""
Tests for LLM Multi-Provider Failover Chain.

Sprint 11: Tests failover logic in LLMPool._create_instance():
- Primary fails → secondary kicks in
- All providers fail → RuntimeError
- Circuit breaker per provider
- Failover disabled → legacy path
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.language_models import BaseChatModel

from app.engine.llm_pool import LLMPool, ThinkingTier
from app.engine.llm_providers.base import LLMProvider


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset LLMPool state between tests."""
    LLMPool.reset()
    yield
    LLMPool.reset()


def _make_mock_provider(name: str, configured: bool = True, available: bool = True, fail: bool = False):
    """Create a mock LLM provider for testing.

    Note: We use MagicMock() without spec=LLMProvider because the concrete
    providers have extra methods (get_circuit_breaker, record_success, record_failure)
    not defined on the ABC.
    """
    provider = MagicMock()
    provider.name = name
    provider.is_configured.return_value = configured
    provider.is_available.return_value = available
    if fail:
        provider.create_instance.side_effect = Exception(f"{name} provider failed")
    else:
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_llm._provider_name = name  # Tag for identification
        provider.create_instance.return_value = mock_llm
    provider.get_circuit_breaker.return_value = None
    provider.record_success = AsyncMock()
    provider.record_failure = AsyncMock()
    return provider


# ============================================================================
# Failover Chain Tests
# ============================================================================


class TestFailoverChain:
    """Test the multi-provider failover chain logic."""

    @patch("app.engine.llm_pool.settings")
    def test_primary_provider_succeeds(self, mock_settings):
        """When primary provider works, use it directly."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai", "ollama"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google")
        openai = _make_mock_provider("openai")

        LLMPool._providers = {"google": google, "openai": openai}
        llm = LLMPool._create_instance("deep")

        assert llm is not None
        google.create_instance.assert_called_once()
        openai.create_instance.assert_not_called()
        assert LLMPool._active_provider == "google"

    @patch("app.engine.llm_pool.settings")
    def test_failover_to_secondary(self, mock_settings):
        """When primary fails, try secondary."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai", "ollama"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google", fail=True)
        openai = _make_mock_provider("openai")

        LLMPool._providers = {"google": google, "openai": openai}
        llm = LLMPool._create_instance("moderate")

        assert llm is not None
        google.create_instance.assert_called_once()
        openai.create_instance.assert_called_once()
        assert LLMPool._active_provider == "openai"

    @patch("app.engine.llm_pool.settings")
    def test_failover_to_tertiary(self, mock_settings):
        """When primary + secondary fail, try tertiary."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai", "ollama"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google", fail=True)
        openai = _make_mock_provider("openai", fail=True)
        ollama = _make_mock_provider("ollama")

        LLMPool._providers = {"google": google, "openai": openai, "ollama": ollama}
        llm = LLMPool._create_instance("light")

        assert llm is not None
        assert LLMPool._active_provider == "ollama"

    @patch("app.engine.llm_pool.settings")
    def test_all_providers_fail_raises_error(self, mock_settings):
        """When ALL providers fail, raise RuntimeError."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google", fail=True)
        openai = _make_mock_provider("openai", fail=True)

        LLMPool._providers = {"google": google, "openai": openai}

        with pytest.raises(RuntimeError, match="All providers failed"):
            LLMPool._create_instance("deep")

    @patch("app.engine.llm_pool.settings")
    def test_skip_unavailable_provider(self, mock_settings):
        """Skip providers where is_available() returns False (circuit open)."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google", available=False)
        openai = _make_mock_provider("openai")

        LLMPool._providers = {"google": google, "openai": openai}
        llm = LLMPool._create_instance("moderate")

        google.create_instance.assert_not_called()
        openai.create_instance.assert_called_once()
        assert LLMPool._active_provider == "openai"

    @patch("app.engine.llm_pool.settings")
    def test_no_providers_available_raises_error(self, mock_settings):
        """When no providers are available at all, raise RuntimeError."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google", available=False)
        LLMPool._providers = {"google": google}

        with pytest.raises(RuntimeError, match="no providers available"):
            LLMPool._create_instance("light")

    @patch("app.engine.llm_pool.settings")
    def test_cached_instance_returned(self, mock_settings):
        """If tier already in pool, return cached instance."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google"]
        mock_settings.thinking_enabled = True

        cached_llm = MagicMock(spec=BaseChatModel)
        LLMPool._pool["deep"] = cached_llm

        result = LLMPool._create_instance("deep")
        assert result is cached_llm


# ============================================================================
# Legacy Path Tests (Failover Disabled)
# ============================================================================


class TestLegacyPath:
    """Test behavior when failover is disabled."""

    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("app.engine.llm_pool.settings")
    def test_legacy_creates_gemini_directly(self, mock_settings, mock_chat):
        """With failover disabled, create Gemini instance directly."""
        mock_settings.enable_llm_failover = False
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.thinking_enabled = True
        mock_settings.llm_failover_chain = ["google"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        LLMPool._providers = {}  # Empty providers
        llm = LLMPool._create_instance("moderate")

        assert llm is not None
        mock_chat.assert_called_once()
        assert LLMPool._active_provider == "google"

    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("app.engine.llm_pool.settings")
    def test_legacy_thinking_disabled(self, mock_settings, mock_chat):
        mock_settings.enable_llm_failover = False
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.thinking_enabled = False
        mock_settings.llm_failover_chain = ["google"]
        mock_chat.return_value = MagicMock(spec=BaseChatModel)

        LLMPool._providers = {}
        LLMPool._create_instance("light")

        call_kwargs = mock_chat.call_args[1]
        assert "thinking_budget" not in call_kwargs

    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("app.engine.llm_pool.settings")
    def test_legacy_failure_raises(self, mock_settings, mock_chat):
        mock_settings.enable_llm_failover = False
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-3-flash-preview"
        mock_settings.thinking_enabled = True
        mock_settings.llm_failover_chain = ["google"]
        mock_chat.side_effect = Exception("API key invalid")

        LLMPool._providers = {}

        with pytest.raises(Exception, match="API key invalid"):
            LLMPool._create_instance("deep")


# ============================================================================
# Circuit Breaker per Provider Tests
# ============================================================================


class TestPerProviderCircuitBreaker:
    """Test circuit breaker integration per provider."""

    @patch("app.engine.llm_pool.settings")
    def test_provider_with_open_circuit_skipped(self, mock_settings):
        """Provider with open circuit breaker is skipped."""
        mock_settings.enable_llm_failover = True
        mock_settings.llm_failover_chain = ["google", "openai"]
        mock_settings.thinking_enabled = True

        google = _make_mock_provider("google")
        google.is_available.return_value = False  # Circuit open
        openai = _make_mock_provider("openai")

        LLMPool._providers = {"google": google, "openai": openai}
        llm = LLMPool._create_instance("moderate")

        google.create_instance.assert_not_called()
        openai.create_instance.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.engine.llm_pool.settings")
    async def test_record_success_delegates_to_active_provider(self, mock_settings):
        """record_success() delegates to the active provider."""
        mock_settings.enable_llm_failover = True

        provider = _make_mock_provider("openai")
        LLMPool._providers = {"openai": provider}
        LLMPool._active_provider = "openai"

        await LLMPool.record_success()
        provider.record_success.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.engine.llm_pool.settings")
    async def test_record_failure_delegates_to_active_provider(self, mock_settings):
        """record_failure() delegates to the active provider."""
        mock_settings.enable_llm_failover = True

        provider = _make_mock_provider("google")
        LLMPool._providers = {"google": provider}
        LLMPool._active_provider = "google"

        await LLMPool.record_failure()
        provider.record_failure.assert_awaited_once()


# ============================================================================
# is_available() with Multiple Providers
# ============================================================================


class TestIsAvailableMultiProvider:
    """Test is_available with multiple providers."""

    @patch("app.engine.llm_pool.settings")
    def test_any_provider_available_returns_true(self, mock_settings):
        mock_settings.enable_llm_failover = True

        google = _make_mock_provider("google", available=False)
        openai = _make_mock_provider("openai", available=True)

        LLMPool._providers = {"google": google, "openai": openai}
        assert LLMPool.is_available() is True

    @patch("app.engine.llm_pool.settings")
    def test_no_provider_available_returns_false(self, mock_settings):
        mock_settings.enable_llm_failover = True

        google = _make_mock_provider("google", available=False)
        openai = _make_mock_provider("openai", available=False)

        LLMPool._providers = {"google": google, "openai": openai}
        assert LLMPool.is_available() is False

    @patch("app.engine.llm_pool._gemini_cb", None)
    @patch("app.engine.llm_pool.settings")
    def test_legacy_no_cb_returns_true(self, mock_settings):
        mock_settings.enable_llm_failover = False
        LLMPool._providers = {}
        assert LLMPool.is_available() is True
