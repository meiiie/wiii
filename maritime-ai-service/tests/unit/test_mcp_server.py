"""
Tests for app.mcp.server — MCP Server setup.

Sprint 56: MCP Support.
"""

import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace


class TestSetupMcpServer:
    """Test setup_mcp_server()."""

    def _mock_app_with_mcp_route(self):
        mock_app = MagicMock()
        mock_app.routes = [
            SimpleNamespace(path="/api/v1/chat", methods={"POST"}),
        ]
        return mock_app

    def test_disabled_when_config_false(self):
        """MCP server not mounted when enable_mcp_server=False."""
        mock_settings = MagicMock()
        mock_settings.enable_mcp_server = False
        mock_app = self._mock_app_with_mcp_route()

        with patch("app.mcp.server.settings", mock_settings, create=True):
            with patch("app.core.config.settings", mock_settings):
                from app.mcp.server import setup_mcp_server
                result = setup_mcp_server(mock_app)

        assert result is None

    def test_returns_none_when_fastapi_mcp_not_installed(self):
        """Graceful when fastapi-mcp not installed."""
        mock_settings = MagicMock()
        mock_settings.enable_mcp_server = True

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"fastapi_mcp": None}):
                from app.mcp.server import setup_mcp_server
                result = setup_mcp_server(self._mock_app_with_mcp_route())

        assert result is None

    def test_mounts_when_enabled(self):
        """MCP server mounts at /mcp when enabled."""
        mock_settings = MagicMock()
        mock_settings.enable_mcp_server = True

        mock_mcp_instance = MagicMock()
        mock_fastapi_mcp_cls = MagicMock(return_value=mock_mcp_instance)

        import types
        mock_module = types.ModuleType("fastapi_mcp")
        mock_module.FastApiMCP = mock_fastapi_mcp_cls

        mock_app = self._mock_app_with_mcp_route()

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"fastapi_mcp": mock_module}):
                from app.mcp.server import setup_mcp_server
                result = setup_mcp_server(mock_app)

        assert result is mock_mcp_instance
        mock_mcp_instance.mount_http.assert_called_once()

    def test_handles_mount_exception(self):
        """Graceful when mount_http raises."""
        mock_settings = MagicMock()
        mock_settings.enable_mcp_server = True

        mock_mcp_instance = MagicMock()
        mock_mcp_instance.mount_http.side_effect = Exception("Mount failed")
        mock_fastapi_mcp_cls = MagicMock(return_value=mock_mcp_instance)

        import types
        mock_module = types.ModuleType("fastapi_mcp")
        mock_module.FastApiMCP = mock_fastapi_mcp_cls

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"fastapi_mcp": mock_module}):
                from app.mcp.server import setup_mcp_server
                result = setup_mcp_server(self._mock_app_with_mcp_route())

        assert result is None
