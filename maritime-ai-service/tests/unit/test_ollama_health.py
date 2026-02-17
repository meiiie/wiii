"""
Tests for Sprint 59: Ollama Health Check Endpoint.

Tests /api/v1/health/ollama endpoint.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ============================================================================
# /health/ollama endpoint
# ============================================================================


class TestOllamaHealthEndpoint:
    """Test the /health/ollama endpoint."""

    @pytest.mark.asyncio
    async def test_available_with_models(self):
        """Ollama reachable and returns models."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:8b"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "qwen3:8b"},
                {"name": "llama3.2:latest"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            # httpx is lazy-imported inside function body — patch at source
            with patch("httpx.AsyncClient", return_value=mock_client):
                from app.api.v1.health import ollama_health
                result = await ollama_health()

        assert result["status"] == "available"
        assert result["model_count"] == 2
        assert "qwen3:8b" in result["models"]
        assert result["default_model"] == "qwen3:8b"

    @pytest.mark.asyncio
    async def test_unavailable_no_base_url(self):
        """No ollama_base_url configured."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = None

        with patch("app.api.v1.health.settings", mock_settings):
            from app.api.v1.health import ollama_health
            result = await ollama_health()

        assert result["status"] == "unavailable"
        assert "not configured" in result["reason"]

    @pytest.mark.asyncio
    async def test_unavailable_empty_base_url(self):
        """Empty ollama_base_url."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = ""

        with patch("app.api.v1.health.settings", mock_settings):
            from app.api.v1.health import ollama_health
            result = await ollama_health()

        assert result["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_unavailable_connection_error(self):
        """Ollama not running — connection refused."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch("httpx.AsyncClient", return_value=mock_client):
                from app.api.v1.health import ollama_health
                result = await ollama_health()

        assert result["status"] == "unavailable"
        assert result["reason"] == "Connection failed"

    @pytest.mark.asyncio
    async def test_unavailable_http_error(self):
        """Ollama returns non-200 status."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch("httpx.AsyncClient", return_value=mock_client):
                from app.api.v1.health import ollama_health
                result = await ollama_health()

        assert result["status"] == "unavailable"
        assert result["http_status"] == 500

    @pytest.mark.asyncio
    async def test_available_empty_models(self):
        """Ollama running but no models loaded."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen3:8b"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch("httpx.AsyncClient", return_value=mock_client):
                from app.api.v1.health import ollama_health
                result = await ollama_health()

        assert result["status"] == "available"
        assert result["model_count"] == 0
        assert result["models"] == []

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_stripped(self):
        """Trailing slash in base_url is handled."""
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434/"
        mock_settings.ollama_model = "qwen3:8b"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "qwen3:8b"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch("httpx.AsyncClient", return_value=mock_client):
                from app.api.v1.health import ollama_health
                result = await ollama_health()

        # Verify the URL used doesn't have double slashes
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "//" not in url.replace("http://", "")
