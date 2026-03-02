"""Sprint 222b Phase 7: Browser agent MCP integration."""
import pytest
from unittest.mock import patch, MagicMock


class TestBrowserAgentConfig:
    def test_get_mcp_server_config_when_enabled(self):
        from app.engine.context.browser_agent import get_browser_mcp_config
        mock_settings = MagicMock()
        mock_settings.enable_browser_agent = True
        mock_settings.browser_agent_mcp_command = "npx"
        mock_settings.browser_agent_mcp_args = ["@playwright/mcp", "--headless"]
        with patch("app.core.config.get_settings", return_value=mock_settings):
            config = get_browser_mcp_config()
        assert config is not None
        assert config["name"] == "playwright"
        assert config["command"] == "npx"
        assert config["transport"] == "stdio"

    def test_get_mcp_server_config_when_disabled(self):
        from app.engine.context.browser_agent import get_browser_mcp_config
        mock_settings = MagicMock()
        mock_settings.enable_browser_agent = False
        with patch("app.core.config.get_settings", return_value=mock_settings):
            config = get_browser_mcp_config()
        assert config is None


class TestBrowserUrlValidation:
    def test_allows_public(self):
        from app.engine.context.browser_agent import validate_browser_url
        assert validate_browser_url("https://google.com") is True
        assert validate_browser_url("https://vietnamairlines.com") is True

    def test_blocks_private(self):
        from app.engine.context.browser_agent import validate_browser_url
        assert validate_browser_url("http://127.0.0.1") is False
        assert validate_browser_url("http://localhost") is False
        assert validate_browser_url("http://192.168.1.1") is False
        assert validate_browser_url("http://10.0.0.1") is False
        assert validate_browser_url("http://172.16.0.1") is False

    def test_blocks_file(self):
        from app.engine.context.browser_agent import validate_browser_url
        assert validate_browser_url("file:///etc/passwd") is False

    def test_blocks_internal(self):
        from app.engine.context.browser_agent import validate_browser_url
        assert validate_browser_url("http://169.254.169.254") is False


class TestExpectedBrowserTools:
    def test_browser_tool_names(self):
        from app.engine.context.browser_agent import EXPECTED_BROWSER_TOOLS
        assert "browser_navigate" in EXPECTED_BROWSER_TOOLS
        assert "browser_snapshot" in EXPECTED_BROWSER_TOOLS
        assert "browser_click" in EXPECTED_BROWSER_TOOLS


class TestBrowserSessionLimiter:
    def test_allows_within_limit(self):
        from app.engine.context.browser_agent import BrowserSessionLimiter
        limiter = BrowserSessionLimiter(max_per_hour=3)
        assert limiter.check_and_increment("user-1") is True
        assert limiter.check_and_increment("user-1") is True
        assert limiter.check_and_increment("user-1") is True

    def test_blocks_over_limit(self):
        from app.engine.context.browser_agent import BrowserSessionLimiter
        limiter = BrowserSessionLimiter(max_per_hour=2)
        assert limiter.check_and_increment("user-1") is True
        assert limiter.check_and_increment("user-1") is True
        assert limiter.check_and_increment("user-1") is False

    def test_per_user(self):
        from app.engine.context.browser_agent import BrowserSessionLimiter
        limiter = BrowserSessionLimiter(max_per_hour=1)
        assert limiter.check_and_increment("user-1") is True
        assert limiter.check_and_increment("user-2") is True
        assert limiter.check_and_increment("user-1") is False
