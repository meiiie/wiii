"""
Tests for Sprint 59: Ollama Thinking Mode Enhancement.

Tests _model_supports_thinking(), OllamaProvider thinking params,
and UnifiedLLMClient Ollama thinking detection.
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# _model_supports_thinking
# ============================================================================


class TestModelSupportsThinking:
    """Test _model_supports_thinking() helper."""

    def test_qwen3_supports_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("qwen3:8b") is True

    def test_qwen3_14b_supports_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("qwen3:14b") is True

    def test_qwen3_instruct_tag_does_not_support_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("qwen3:4b-instruct-2507-q4_K_M") is False

    def test_qwen3_thinking_tag_supports_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("qwen3:4b-thinking-2507-q4_K_M") is True

    def test_deepseek_r1_supports_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("deepseek-r1:14b") is True

    def test_qwq_supports_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("qwq:32b") is True

    def test_llama_does_not_support_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("llama3.2") is False

    def test_mistral_does_not_support_thinking(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("mistral:7b") is False

    def test_case_insensitive(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("Qwen3:8B") is True

    def test_custom_thinking_models_list(self):
        mock_settings = MagicMock()
        mock_settings.ollama_thinking_models = ["custom-think"]

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            from app.engine.llm_providers.ollama_provider import _model_supports_thinking
            assert _model_supports_thinking("custom-think:7b") is True
            assert _model_supports_thinking("qwen3:8b") is False


# ============================================================================
# OllamaProvider.create_instance with thinking
# ============================================================================


class TestOllamaProviderThinking:
    """Test OllamaProvider thinking mode integration."""

    def test_thinking_enabled_for_qwen3(self):
        """Qwen3 model with thinking_budget > 0 passes extra_body."""
        import sys
        import types

        mock_settings = MagicMock()
        mock_settings.ollama_model = "qwen3:8b"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_keep_alive = "30m"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        mock_ollama_module = types.ModuleType("langchain_ollama")
        mock_chat_ollama = MagicMock()
        mock_ollama_module.ChatOllama = mock_chat_ollama

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            with patch.dict(sys.modules, {"langchain_ollama": mock_ollama_module}):
                from app.engine.llm_providers.ollama_provider import OllamaProvider
                provider = OllamaProvider()
                provider.create_instance(
                    tier="moderate",
                    thinking_budget=1024,
                    include_thoughts=True,
                )

        mock_chat_ollama.assert_called_once()
        call_kwargs = mock_chat_ollama.call_args
        assert call_kwargs.kwargs.get("extra_body") == {"think": True}
        assert call_kwargs.kwargs.get("keep_alive") == "30m"

    def test_thinking_not_enabled_for_llama(self):
        """Non-thinking model does NOT pass extra_body."""
        import sys
        import types

        mock_settings = MagicMock()
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        mock_ollama_module = types.ModuleType("langchain_ollama")
        mock_chat_ollama = MagicMock()
        mock_ollama_module.ChatOllama = mock_chat_ollama

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            with patch.dict(sys.modules, {"langchain_ollama": mock_ollama_module}):
                from app.engine.llm_providers.ollama_provider import OllamaProvider
                provider = OllamaProvider()
                provider.create_instance(
                    tier="moderate",
                    thinking_budget=1024,
                    include_thoughts=True,
                )

        call_kwargs = mock_chat_ollama.call_args
        assert "extra_body" not in call_kwargs.kwargs

    def test_thinking_not_enabled_without_budget(self):
        """Qwen3 without thinking_budget does NOT enable thinking."""
        import sys
        import types

        mock_settings = MagicMock()
        mock_settings.ollama_model = "qwen3:8b"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        mock_ollama_module = types.ModuleType("langchain_ollama")
        mock_chat_ollama = MagicMock()
        mock_ollama_module.ChatOllama = mock_chat_ollama

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            with patch.dict(sys.modules, {"langchain_ollama": mock_ollama_module}):
                from app.engine.llm_providers.ollama_provider import OllamaProvider
                provider = OllamaProvider()
                provider.create_instance(
                    tier="moderate",
                    thinking_budget=0,
                    include_thoughts=False,
                )

        call_kwargs = mock_chat_ollama.call_args
        assert "extra_body" not in call_kwargs.kwargs

    def test_thinking_not_enabled_for_qwen3_instruct_tag(self):
        """Explicit Qwen3 instruct tags should not receive think=True."""
        import sys
        import types

        mock_settings = MagicMock()
        mock_settings.ollama_model = "qwen3:4b-instruct-2507-q4_K_M"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        mock_ollama_module = types.ModuleType("langchain_ollama")
        mock_chat_ollama = MagicMock()
        mock_ollama_module.ChatOllama = mock_chat_ollama

        with patch("app.engine.llm_providers.ollama_provider.settings", mock_settings):
            with patch.dict(sys.modules, {"langchain_ollama": mock_ollama_module}):
                from app.engine.llm_providers.ollama_provider import OllamaProvider
                provider = OllamaProvider()
                provider.create_instance(
                    tier="moderate",
                    thinking_budget=1024,
                    include_thoughts=True,
                )

        call_kwargs = mock_chat_ollama.call_args
        assert "extra_body" not in call_kwargs.kwargs


# ============================================================================
# Config defaults
# ============================================================================


class TestOllamaConfigDefaults:
    """Test Sprint 59 config defaults."""

    def test_default_model_qwen3(self):
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.ollama_model == "qwen3:4b-instruct-2507-q4_K_M"

    def test_default_thinking_models(self):
        from app.core.config import Settings
        s = Settings()
        assert "qwen3" in s.ollama_thinking_models
        assert "deepseek-r1" in s.ollama_thinking_models
        assert "qwq" in s.ollama_thinking_models

    def test_default_keep_alive(self):
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.ollama_keep_alive == "30m"

    def test_custom_thinking_models(self):
        from app.core.config import Settings
        s = Settings(ollama_thinking_models=["custom-model"])
        assert s.ollama_thinking_models == ["custom-model"]


# ============================================================================
# UnifiedLLMClient Ollama thinking detection
# ============================================================================


class TestUnifiedClientOllamaThinking:
    """Test UnifiedLLMClient detects Ollama thinking-capable models."""

    def setup_method(self):
        from app.engine.llm_providers.unified_client import UnifiedLLMClient
        UnifiedLLMClient.reset()

    def teardown_method(self):
        from app.engine.llm_providers.unified_client import UnifiedLLMClient
        UnifiedLLMClient.reset()

    def test_qwen3_gets_thinking_support(self):
        from app.engine.llm_providers.unified_client import UnifiedLLMClient

        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:8b"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        config = UnifiedLLMClient._config_for_provider("ollama", mock_settings)
        assert config is not None
        assert config.supports_thinking is True
        assert config.thinking_param == "think"

    def test_llama_no_thinking_support(self):
        from app.engine.llm_providers.unified_client import UnifiedLLMClient

        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3.2"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        config = UnifiedLLMClient._config_for_provider("ollama", mock_settings)
        assert config is not None
        assert config.supports_thinking is False

    def test_deepseek_r1_gets_thinking_support(self):
        from app.engine.llm_providers.unified_client import UnifiedLLMClient

        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "deepseek-r1:14b"
        mock_settings.ollama_thinking_models = ["qwen3", "deepseek-r1", "qwq"]

        config = UnifiedLLMClient._config_for_provider("ollama", mock_settings)
        assert config is not None
        assert config.supports_thinking is True
