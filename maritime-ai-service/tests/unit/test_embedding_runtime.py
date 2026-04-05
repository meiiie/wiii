from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import URLError

import pytest


class TestEmbeddingCatalogHelpers:
    def test_infer_embedding_provider_from_known_models(self):
        from app.engine.model_catalog import get_embedding_provider

        assert get_embedding_provider("models/gemini-embedding-001") == "google"
        assert get_embedding_provider("text-embedding-3-small") == "openai"
        assert get_embedding_provider("embeddinggemma") == "ollama"

    def test_zhipu_has_no_default_embedding_model_until_cataloged(self):
        from app.engine.model_catalog import get_default_embedding_model_for_provider

        assert get_default_embedding_model_for_provider("zhipu") is None

    def test_sanitize_error_for_log_redacts_api_key_shapes(self):
        from app.engine.embedding_runtime import _sanitize_error_for_log

        sanitized = _sanitize_error_for_log(
            "Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-proj-abc123XYZ'}}"
        )

        assert "sk-proj-abc123XYZ" not in sanitized
        assert "[REDACTED]" in sanitized or "sk-REDACTED" in sanitized

    def test_provider_can_serve_embedding_model_requires_same_space(self):
        from app.engine.model_catalog import provider_can_serve_embedding_model

        assert provider_can_serve_embedding_model("ollama", "embeddinggemma") is True
        assert provider_can_serve_embedding_model("openrouter", "text-embedding-3-small") is True
        assert provider_can_serve_embedding_model("openai", "embeddinggemma") is False
        assert provider_can_serve_embedding_model("google", "text-embedding-3-small") is False


class TestOpenAICompatibleEmbeddings:
    @patch("openai.OpenAI")
    def test_openai_embeddings_request_dimensions_when_supported(self, mock_openai_cls):
        from app.engine.embedding_runtime import OpenAICompatibleEmbeddings

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[3.0, 4.0, 0.0])]
        )
        mock_openai_cls.return_value = mock_client

        embeddings = OpenAICompatibleEmbeddings(
            provider="openai",
            api_key="test-key",
            model_name="text-embedding-3-small",
            dimensions=3,
        )

        result = embeddings.embed_query("hello")

        assert len(result) == 3
        assert mock_client.embeddings.create.call_args.kwargs["dimensions"] == 3


class TestSemanticEmbeddingBackend:
    def test_build_embedding_backend_for_provider_model_refuses_cross_space_pair(self):
        from app.engine import embedding_runtime as mod

        backend = mod.build_embedding_backend_for_provider_model(
            "openai",
            "embeddinggemma",
            dimensions=768,
        )

        assert backend is None

    def test_auto_mode_promotes_first_available_same_space_provider(self):
        from app.engine import embedding_runtime as mod

        backend = MagicMock()
        backend.provider = "openai"
        backend.model_name = "text-embedding-3-small"
        backend.dimensions = 768

        patched_settings = SimpleNamespace(
            embedding_provider="auto",
            embedding_failover_chain=["google", "openai"],
            embedding_model="text-embedding-3-small",
            embedding_dimensions=768,
        )

        with patch.object(mod, "settings", patched_settings), patch.object(
            mod.SemanticEmbeddingBackend,
            "_build_backend",
            side_effect=lambda provider: None if provider == "google" else backend,
        ):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.provider == "openai"
        assert runtime.model_name == "text-embedding-3-small"

    def test_auto_mode_refuses_cross_space_provider_promotion(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="auto",
            embedding_failover_chain=["google", "openai"],
            embedding_model="embeddinggemma",
            embedding_dimensions=768,
            google_api_key="google-key",
            openai_api_key="openai-key",
            openai_base_url="https://api.openai.com/v1",
        )

        with patch.object(mod, "settings", patched_settings), patch.object(
            mod,
            "probe_ollama_embedding_model",
            return_value=SimpleNamespace(
                available=False,
                reason_code="host_down",
                reason_label="Ollama down",
                resolved_base_url=None,
            ),
        ):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is False
        assert runtime.provider is None

    def test_zhipu_embedding_provider_fails_closed_without_verified_model(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="zhipu",
            embedding_failover_chain=["zhipu"],
            embedding_model=None,
            embedding_dimensions=768,
            zhipu_api_key="live-key",
        )

        with patch.object(mod, "settings", patched_settings):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is False
        assert runtime.provider is None

    def test_openrouter_embedding_provider_fails_closed_without_openrouter_base_url_signal(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="openrouter",
            embedding_failover_chain=["openrouter"],
            embedding_model="text-embedding-3-small",
            embedding_dimensions=768,
            openai_api_key="openai-key",
            openai_base_url="https://api.openai.com/v1",
        )

        with patch.object(mod, "settings", patched_settings):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is False
        assert runtime.provider is None

    def test_openrouter_embedding_provider_builds_when_openrouter_base_url_is_explicit(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="openrouter",
            embedding_failover_chain=["openrouter"],
            embedding_model="text-embedding-3-small",
            embedding_dimensions=768,
            openai_api_key="openrouter-key",
            openai_base_url="https://openrouter.ai/api/v1",
        )

        with patch.object(mod, "settings", patched_settings):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is True
        assert runtime.provider == "openrouter"
        assert runtime.model_name == "text-embedding-3-small"

    def test_ollama_embedding_provider_fails_closed_when_model_not_installed(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="ollama",
            embedding_failover_chain=["ollama"],
            embedding_model="embeddinggemma",
            embedding_dimensions=768,
            ollama_base_url="http://localhost:11434",
        )

        with patch.object(mod, "settings", patched_settings), patch.object(
            mod,
            "probe_ollama_embedding_model",
            return_value=SimpleNamespace(
                available=False,
                reason_code="model_missing",
                reason_label="Model embedding local chua duoc cai tren Ollama.",
                resolved_base_url="http://localhost:11434",
            ),
        ):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is False
        assert runtime.provider is None

    def test_ollama_embedding_provider_builds_when_model_is_installed(self):
        from app.engine import embedding_runtime as mod

        patched_settings = SimpleNamespace(
            embedding_provider="ollama",
            embedding_failover_chain=["ollama"],
            embedding_model="embeddinggemma",
            embedding_dimensions=768,
            ollama_base_url="http://localhost:11434",
            ollama_api_key=None,
        )

        with patch.object(mod, "settings", patched_settings), patch.object(
            mod,
            "probe_ollama_embedding_model",
            return_value=SimpleNamespace(
                available=True,
                reason_code=None,
                reason_label=None,
                resolved_base_url="http://localhost:11434",
            ),
        ):
            runtime = mod.SemanticEmbeddingBackend()

        assert runtime.is_available() is True
        assert runtime.provider == "ollama"
        assert runtime.model_name == "embeddinggemma"

    def test_probe_ollama_embedding_model_falls_back_to_localhost_candidate(self):
        from app.engine import embedding_runtime as mod

        host_down = URLError("timed out")
        localhost_payload = {
            "models": [
                {"name": "embeddinggemma"},
            ]
        }

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                import json as _json

                return _json.dumps(self._payload).encode("utf-8")

        def _fake_urlopen(request, timeout):
            url = request.full_url
            if "host.docker.internal" in url:
                raise host_down
            return _Response(localhost_payload)

        with patch.object(mod, "urlopen", side_effect=_fake_urlopen):
            result = mod.probe_ollama_embedding_model(
                "http://host.docker.internal:11434",
                "embeddinggemma",
            )

        assert result.available is True
        assert result.resolved_base_url == "http://localhost:11434"

    def test_probe_ollama_embedding_model_accepts_latest_tag_variant(self):
        from app.engine import embedding_runtime as mod

        payload = {
            "models": [
                {"name": "embeddinggemma:latest"},
            ]
        }

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                import json as _json

                return _json.dumps(self._payload).encode("utf-8")

        with patch.object(mod, "urlopen", return_value=_Response(payload)):
            result = mod.probe_ollama_embedding_model(
                "http://localhost:11434",
                "embeddinggemma",
            )

        assert result.available is True

    def test_probe_ollama_embedding_model_uses_short_cache(self):
        from app.engine import embedding_runtime as mod

        payload = {
            "models": [
                {"name": "embeddinggemma"},
            ]
        }

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                import json as _json

                return _json.dumps(self._payload).encode("utf-8")

        mod.reset_ollama_embedding_probe_cache()
        with patch.object(mod, "urlopen", return_value=_Response(payload)) as mock_urlopen:
            first = mod.probe_ollama_embedding_model(
                "http://localhost:11434",
                "embeddinggemma",
            )
            second = mod.probe_ollama_embedding_model(
                "http://localhost:11434",
                "embeddinggemma",
            )

        assert first.available is True
        assert second.available is True
        assert mock_urlopen.call_count == 1


@pytest.mark.asyncio
async def test_input_processor_semantic_fact_retrieval_uses_embedding_generator():
    from app.services.input_processor_context_runtime import _populate_semantic_memory_context

    context = SimpleNamespace(user_facts=None, semantic_context="")
    semantic_memory = MagicMock()
    semantic_memory.retrieve_insights_prioritized = AsyncMock(return_value=[])
    semantic_context = MagicMock()
    semantic_context.to_prompt_context.return_value = ""
    semantic_memory.retrieve_context = AsyncMock(return_value=semantic_context)
    semantic_memory.search_relevant_facts.return_value = []

    generator = MagicMock()
    generator.agenerate = AsyncMock(return_value=[0.1, 0.2, 0.3])

    settings_obj = SimpleNamespace(
        enable_semantic_fact_retrieval=True,
        fact_min_similarity=0.3,
        max_injected_facts=5,
    )
    logger_obj = MagicMock()

    with patch(
        "app.engine.semantic_memory.embeddings.get_embedding_generator",
        return_value=generator,
    ):
        await _populate_semantic_memory_context(
            semantic_memory=semantic_memory,
            context=context,
            user_id="user-1",
            message="mình tên Nam",
            settings_obj=settings_obj,
            logger_obj=logger_obj,
        )

    generator.agenerate.assert_awaited_once_with("mình tên Nam")
    semantic_memory.search_relevant_facts.assert_called_once()
