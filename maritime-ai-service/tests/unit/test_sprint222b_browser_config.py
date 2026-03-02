# tests/unit/test_sprint222b_browser_config.py
"""Sprint 222b Phase 7: Browser agent configuration."""
import pytest


class TestBrowserAgentConfig:
    def test_enable_browser_agent_default_false(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_browser_agent"].default
        assert default is False

    def test_browser_agent_mcp_command_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["browser_agent_mcp_command"].default
        assert default == "npx"

    def test_browser_agent_mcp_args_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["browser_agent_mcp_args"].default
        assert "@playwright/mcp" in default

    def test_browser_agent_timeout_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["browser_agent_timeout"].default
        assert default == 120

    def test_browser_agent_max_sessions_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["browser_agent_max_sessions_per_hour"].default
        assert default == 10
