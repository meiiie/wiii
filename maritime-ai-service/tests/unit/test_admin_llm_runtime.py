import types
from unittest.mock import patch

import pytest


def test_serialize_llm_runtime_includes_use_multi_agent():
    from app.api.v1.admin import _serialize_llm_runtime
    from app.core.config import settings

    original = getattr(settings, "use_multi_agent", True)
    original_google_api_key = getattr(settings, "google_api_key", None)
    original_google_model = getattr(settings, "google_model", None)
    original_ollama_api_key = getattr(settings, "ollama_api_key", None)
    try:
        settings.use_multi_agent = False
        settings.google_api_key = "gemini-test-key"
        settings.google_model = "gemini-3.1-flash-lite-preview"
        settings.ollama_api_key = "ollama-test-key"
        with patch(
            "app.engine.llm_pool.LLMPool.get_stats",
            return_value={"active_provider": None, "providers_registered": []},
        ):
            result = _serialize_llm_runtime()

        assert result.use_multi_agent is False
        assert result.google_model == "gemini-3.1-flash-lite-preview"
        assert result.google_api_key_configured is True
        assert result.ollama_api_key_configured is True
    finally:
        settings.use_multi_agent = original
        settings.google_api_key = original_google_api_key
        settings.google_model = original_google_model
        settings.ollama_api_key = original_ollama_api_key
        settings.refresh_nested_views()


@pytest.mark.asyncio
async def test_update_llm_runtime_config_updates_use_multi_agent_and_resets_services():
    from app.api.v1.admin import LlmRuntimeConfigUpdate, update_llm_runtime_config
    from app.core.config import settings

    auth = types.SimpleNamespace(role="admin", auth_method="oauth")
    original = getattr(settings, "use_multi_agent", True)
    original_google_api_key = getattr(settings, "google_api_key", None)
    original_google_model = getattr(settings, "google_model", None)
    original_provider = getattr(settings, "llm_provider", "google")
    original_ollama_api_key = getattr(settings, "ollama_api_key", None)
    try:
        settings.use_multi_agent = True
        settings.google_api_key = None
        settings.google_model = "gemini-3.1-flash-lite-preview"
        settings.llm_provider = "ollama"
        settings.ollama_api_key = None
        with patch("app.engine.llm_pool.LLMPool.reset") as mock_pool_reset, patch(
            "app.engine.llm_pool.LLMPool.get_stats",
            return_value={"active_provider": None, "providers_registered": []},
        ), patch(
            "app.services.chat_service.reset_chat_service"
        ) as mock_reset_chat:
            result = await update_llm_runtime_config(
                LlmRuntimeConfigUpdate(
                    provider="google",
                    use_multi_agent=False,
                    google_api_key="gemini-runtime-key",
                    google_model="gemini-2.5-flash",
                    ollama_api_key="ollama-cloud-key",
                ),
                auth,
            )

        assert settings.use_multi_agent is False
        assert settings.llm_provider == "google"
        assert settings.google_api_key == "gemini-runtime-key"
        assert settings.google_model == "gemini-2.5-flash"
        assert settings.llm.google_api_key == "gemini-runtime-key"
        assert settings.llm.google_model == "gemini-2.5-flash"
        assert settings.ollama_api_key == "ollama-cloud-key"
        assert result.use_multi_agent is False
        assert result.provider == "google"
        assert result.google_model == "gemini-2.5-flash"
        assert result.google_api_key_configured is True
        assert result.ollama_api_key_configured is True
        mock_pool_reset.assert_called_once()
        mock_reset_chat.assert_called_once()
    finally:
        settings.use_multi_agent = original
        settings.google_api_key = original_google_api_key
        settings.google_model = original_google_model
        settings.llm_provider = original_provider
        settings.ollama_api_key = original_ollama_api_key
        settings.refresh_nested_views()
