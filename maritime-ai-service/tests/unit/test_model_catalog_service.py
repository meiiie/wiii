"""Tests for ModelCatalogService — multi-provider catalog with Ollama discovery."""
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.engine.model_catalog import (
    ChatModelMetadata,
    GOOGLE_CHAT_MODELS,
    GOOGLE_DEFAULT_MODEL,
    OPENROUTER_CHAT_MODELS,
    OLLAMA_KNOWN_MODELS,
    EMBEDDING_MODELS,
    DEFAULT_EMBEDDING_MODEL,
    get_all_static_chat_models,
    is_known_model,
    ModelCatalogService,
)


class TestStaticCatalogs:
    def test_google_models_present(self):
        cats = get_all_static_chat_models()
        assert "google" in cats
        assert GOOGLE_DEFAULT_MODEL in cats["google"]

    def test_openrouter_models_present(self):
        cats = get_all_static_chat_models()
        assert "openrouter" in cats
        assert "openai/gpt-oss-20b:free" in cats["openrouter"]

    def test_ollama_models_present(self):
        cats = get_all_static_chat_models()
        assert "ollama" in cats
        assert len(cats["ollama"]) >= 1

    def test_all_entries_are_chat_model_metadata(self):
        for provider, models in get_all_static_chat_models().items():
            for name, meta in models.items():
                assert isinstance(meta, ChatModelMetadata)
                assert meta.provider == provider or provider in ("openrouter",)


class TestIsKnownModel:
    def test_known_google_current(self):
        assert is_known_model("google", GOOGLE_DEFAULT_MODEL) is True

    def test_known_google_legacy(self):
        assert is_known_model("google", "gemini-2.5-flash") is True

    def test_unknown_google(self):
        assert is_known_model("google", "gemini-99-turbo") is False

    def test_known_openrouter(self):
        assert is_known_model("openrouter", "openai/gpt-oss-20b:free") is True

    def test_unknown_provider(self):
        assert is_known_model("azure", "gpt-4") is False

    def test_empty_model_name(self):
        assert is_known_model("google", "") is False


class TestOllamaDiscovery:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        ModelCatalogService.reset_cache()
        yield
        ModelCatalogService.reset_cache()

    @pytest.mark.asyncio
    async def test_discover_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest", "size": 4000000000},
                {"name": "mistral:7b", "size": 7000000000},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            models = await ModelCatalogService.discover_ollama_models("http://localhost:11434")

        assert len(models) == 2
        assert models[0].model_name == "llama3:latest"
        assert models[0].provider == "ollama"
        assert models[0].status == "available"
        assert models[1].model_name == "mistral:7b"

    @pytest.mark.asyncio
    async def test_discover_timeout(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            models = await ModelCatalogService.discover_ollama_models("http://localhost:11434")

        assert models == []  # graceful degradation

    @pytest.mark.asyncio
    async def test_discover_cached(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "test:latest"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            models1 = await ModelCatalogService.discover_ollama_models("http://localhost:11434")
            models2 = await ModelCatalogService.discover_ollama_models("http://localhost:11434")

        assert len(models1) == 1
        assert len(models2) == 1
        # Only 1 HTTP call (cached)
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_discover_cache_expired(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "test:latest"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await ModelCatalogService.discover_ollama_models("http://localhost:11434")
            # Expire cache
            ModelCatalogService._ollama_cache_ts = time.time() - 120
            await ModelCatalogService.discover_ollama_models("http://localhost:11434")

        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_strips_trailing_api(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await ModelCatalogService.discover_ollama_models("http://localhost:11434/api")

        called_url = mock_client.get.call_args[0][0]
        assert called_url == "http://localhost:11434/api/tags"


class TestGetFullCatalog:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        ModelCatalogService.reset_cache()
        yield
        ModelCatalogService.reset_cache()

    @pytest.mark.asyncio
    async def test_without_ollama(self):
        catalog = await ModelCatalogService.get_full_catalog(ollama_base_url=None)
        assert "providers" in catalog
        assert "google" in catalog["providers"]
        assert "openrouter" in catalog["providers"]
        assert catalog["ollama_discovered"] is False
        assert "timestamp" in catalog

    @pytest.mark.asyncio
    async def test_with_ollama(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "phi3:latest"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            catalog = await ModelCatalogService.get_full_catalog(
                ollama_base_url="http://localhost:11434"
            )

        assert catalog["ollama_discovered"] is True
        assert "phi3:latest" in catalog["providers"]["ollama"]

    @pytest.mark.asyncio
    async def test_embedding_models_included(self):
        catalog = await ModelCatalogService.get_full_catalog()
        assert "embedding_models" in catalog
        assert DEFAULT_EMBEDDING_MODEL in catalog["embedding_models"]
