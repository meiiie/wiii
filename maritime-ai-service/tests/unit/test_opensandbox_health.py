"""Tests for /api/v1/health/opensandbox endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOpenSandboxHealthEndpoint:
    @pytest.mark.asyncio
    async def test_disabled_when_feature_flag_off(self):
        mock_settings = MagicMock()
        mock_settings.enable_privileged_sandbox = False
        mock_settings.sandbox_provider = "disabled"

        with patch("app.api.v1.health.settings", mock_settings):
            from app.api.v1.health import opensandbox_health

            result = await opensandbox_health()

        assert result["status"] == "disabled"
        assert result["provider"] == "disabled"

    @pytest.mark.asyncio
    async def test_disabled_when_provider_is_not_opensandbox(self):
        mock_settings = MagicMock()
        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "local_subprocess"

        with patch("app.api.v1.health.settings", mock_settings):
            from app.api.v1.health import opensandbox_health

            result = await opensandbox_health()

        assert result["status"] == "disabled"
        assert result["provider"] == "local_subprocess"

    @pytest.mark.asyncio
    async def test_unavailable_without_base_url(self):
        mock_settings = MagicMock()
        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.opensandbox_base_url = None

        with patch("app.api.v1.health.settings", mock_settings):
            from app.api.v1.health import opensandbox_health

            result = await opensandbox_health()

        assert result["status"] == "unavailable"
        assert "not configured" in result["reason"]

    @pytest.mark.asyncio
    async def test_available_when_executor_healthcheck_passes(self):
        mock_settings = MagicMock()
        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.opensandbox_base_url = "http://opensandbox.local"
        mock_settings.opensandbox_code_template = "code"
        mock_settings.opensandbox_browser_template = "browser"
        mock_settings.opensandbox_network_mode = "egress"
        mock_settings.sandbox_allow_browser_workloads = True

        mock_executor = MagicMock()
        mock_executor.is_configured.return_value = True
        mock_executor.healthcheck = AsyncMock(return_value=True)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch(
                "app.sandbox.factory.get_sandbox_executor",
                return_value=mock_executor,
            ):
                from app.api.v1.health import opensandbox_health

                result = await opensandbox_health()

        assert result["status"] == "available"
        assert result["provider"] == "opensandbox"
        assert result["base_url"] == "http://opensandbox.local"
        assert result["browser_workloads_enabled"] is True

    @pytest.mark.asyncio
    async def test_unavailable_when_executor_healthcheck_fails(self):
        mock_settings = MagicMock()
        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.opensandbox_base_url = "http://opensandbox.local"
        mock_settings.opensandbox_code_template = "code"
        mock_settings.opensandbox_browser_template = "browser"
        mock_settings.opensandbox_network_mode = "egress"
        mock_settings.sandbox_allow_browser_workloads = False

        mock_executor = MagicMock()
        mock_executor.is_configured.return_value = True
        mock_executor.healthcheck = AsyncMock(return_value=False)

        with patch("app.api.v1.health.settings", mock_settings):
            with patch(
                "app.sandbox.factory.get_sandbox_executor",
                return_value=mock_executor,
            ):
                from app.api.v1.health import opensandbox_health

                result = await opensandbox_health()

        assert result["status"] == "unavailable"
        assert result["provider"] == "opensandbox"
