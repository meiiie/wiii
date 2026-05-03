"""
Tests for app.mcp.client — MCP Client (MCPToolManager).

Sprint 56: MCP Support.
Phase 9c: rewritten against the raw ``mcp`` SDK; no more
``langchain_mcp_adapters`` dependency.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.mcp.client import MCPToolManager, MCPServerConfig
from app.engine.tools.registry import ToolAccess, ToolCategory


@pytest.fixture(autouse=True)
def reset_mcp_client():
    """Reset MCPToolManager state before each test."""
    MCPToolManager.reset()
    yield
    MCPToolManager.reset()


class TestMCPServerConfig:
    """Test MCPServerConfig dataclass."""

    def test_defaults(self):
        config = MCPServerConfig(name="test")
        assert config.transport == "stdio"
        assert config.url is None
        assert config.command is None
        assert config.args == []
        assert config.headers == {}
        assert config.enabled is True

    def test_http_config(self):
        config = MCPServerConfig(
            name="remote",
            transport="http",
            url="http://localhost:8000/mcp",
            headers={"Authorization": "Bearer token"},
        )
        assert config.transport == "http"
        assert config.url == "http://localhost:8000/mcp"

    def test_stdio_config(self):
        config = MCPServerConfig(
            name="local",
            transport="stdio",
            command="python",
            args=["server.py"],
        )
        assert config.command == "python"
        assert config.args == ["server.py"]


class TestMCPToolManagerInitialize:
    """Test MCPToolManager.initialize()."""

    @pytest.mark.asyncio
    async def test_empty_configs(self):
        await MCPToolManager.initialize([])
        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []

    @pytest.mark.asyncio
    async def test_all_disabled_configs(self):
        configs = [MCPServerConfig(name="test", enabled=False)]
        await MCPToolManager.initialize(configs)
        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []

    @pytest.mark.asyncio
    async def test_missing_mcp_sdk(self):
        """When the ``mcp`` SDK is missing the manager fails soft."""
        configs = [MCPServerConfig(name="test", transport="http", url="http://test/mcp")]

        # Force the lazy import inside ``initialize`` to fail.
        with patch.dict(
            "sys.modules",
            {"mcp": None, "mcp.client.stdio": None, "mcp.client.streamable_http": None},
        ):
            await MCPToolManager.initialize(configs)

        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []

    @pytest.mark.asyncio
    async def test_stdio_without_command_skipped(self):
        """stdio config without command is skipped — manager still finishes init."""
        configs = [MCPServerConfig(name="bad", transport="stdio")]  # No command
        await MCPToolManager.initialize(configs)
        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []

    @pytest.mark.asyncio
    async def test_http_without_url_skipped(self):
        """http config without URL is skipped — manager still finishes init."""
        configs = [MCPServerConfig(name="bad", transport="http")]  # No URL
        await MCPToolManager.initialize(configs)
        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []


class TestMCPToolManagerShutdown:
    """Test MCPToolManager.shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_without_init(self):
        await MCPToolManager.shutdown()
        assert not MCPToolManager.is_initialized()

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        # Simulate a previously-initialized manager with a fake exit stack.
        MCPToolManager._initialized = True
        MCPToolManager._tools = [MagicMock()]
        fake_stack = MagicMock()
        fake_stack.aclose = AsyncMock()
        MCPToolManager._exit_stack = fake_stack

        await MCPToolManager.shutdown()

        assert not MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []
        assert MCPToolManager._exit_stack is None
        fake_stack.aclose.assert_awaited_once()


class TestMCPToolManagerParseConfigs:
    """Test MCPToolManager.parse_configs()."""

    def test_parse_empty_json(self):
        assert MCPToolManager.parse_configs("[]") == []

    def test_parse_valid_config(self):
        json_str = '[{"name": "test", "transport": "http", "url": "http://localhost/mcp"}]'
        configs = MCPToolManager.parse_configs(json_str)
        assert len(configs) == 1
        assert configs[0].name == "test"
        assert configs[0].url == "http://localhost/mcp"

    def test_parse_multiple_configs(self):
        json_str = '[{"name": "a"}, {"name": "b"}]'
        configs = MCPToolManager.parse_configs(json_str)
        assert len(configs) == 2

    def test_parse_ignores_unknown_keys(self):
        json_str = (
            '[{"name": "test", "transport": "http", '
            '"url": "http://localhost/mcp", "unexpected": "ignored"}]'
        )
        configs = MCPToolManager.parse_configs(json_str)
        assert len(configs) == 1
        assert configs[0].name == "test"
        assert not hasattr(configs[0], "unexpected")

    def test_parse_invalid_json(self):
        assert MCPToolManager.parse_configs("invalid") == []

    def test_parse_non_list(self):
        assert MCPToolManager.parse_configs('{"name": "test"}') == []

    def test_parse_non_dict_items_skipped(self):
        assert MCPToolManager.parse_configs('["string"]') == []


class TestMCPToolManagerRegistrationPolicy:
    @patch("app.engine.tools.registry.get_tool_registry")
    @patch("app.core.config.get_settings")
    def test_browser_tools_register_as_privileged_writes(
        self,
        mock_get_settings,
        mock_get_reg,
    ):
        settings = MagicMock()
        settings.mcp_auto_register_external = True
        mock_get_settings.return_value = settings

        registry = MagicMock()
        registry.get_info.return_value = None
        mock_get_reg.return_value = registry

        browser_tool = MagicMock()
        browser_tool.name = "browser_navigate"
        browser_tool.description = "Navigate browser"

        MCPToolManager._initialized = True
        MCPToolManager._tools = [browser_tool]

        count = MCPToolManager.register_discovered_tools()

        assert count == 1
        kwargs = registry.register.call_args.kwargs
        assert kwargs["category"] == ToolCategory.MCP
        assert kwargs["access"] == ToolAccess.WRITE
        assert kwargs["roles"] == ["admin"]


class TestMCPToolManagerRuntimeConfigResolution:
    def test_resolve_configs_merges_browser_helper(self):
        settings = MagicMock()
        settings.mcp_server_configs = '[{"name": "remote", "transport": "http", "url": "http://localhost/mcp"}]'

        with patch(
            "app.engine.context.browser_agent.get_browser_mcp_config",
            return_value={
                "name": "playwright",
                "transport": "stdio",
                "command": "npx",
                "args": ["@playwright/mcp", "--headless"],
            },
        ):
            configs = MCPToolManager.resolve_configs(settings)

        assert [config.name for config in configs] == ["remote", "playwright"]

    def test_resolve_configs_keeps_explicit_config_on_name_collision(self):
        settings = MagicMock()
        settings.mcp_server_configs = (
            '[{"name": "playwright", "transport": "http", "url": "http://remote/mcp"}]'
        )

        with patch(
            "app.engine.context.browser_agent.get_browser_mcp_config",
            return_value={
                "name": "playwright",
                "transport": "stdio",
                "command": "npx",
                "args": ["@playwright/mcp", "--headless"],
            },
        ):
            configs = MCPToolManager.resolve_configs(settings)

        assert len(configs) == 1
        assert configs[0].transport == "http"

    def test_merge_configs_deduplicates_by_name(self):
        merged = MCPToolManager.merge_configs(
            [MCPServerConfig(name="one", transport="http", url="http://a")],
            [
                MCPServerConfig(name="one", transport="stdio", command="npx"),
                MCPServerConfig(name="two", transport="stdio", command="npx"),
            ],
        )

        assert [config.name for config in merged] == ["one", "two"]


class TestMCPTool:
    """Test the MCPTool wrapper that bridges mcp SDK tools into Wiii's runtime."""

    @pytest.mark.asyncio
    async def test_ainvoke_flattens_text_content(self):
        from app.mcp.client import MCPTool

        text_block = MagicMock()
        text_block.text = "search result"
        result_obj = MagicMock()
        result_obj.content = [text_block]

        session = MagicMock()
        session.call_tool = AsyncMock(return_value=result_obj)

        tool = MCPTool(
            name="search",
            description="Search the docs",
            parameters={"type": "object", "properties": {}},
            session=session,
            server_name="docs-mcp",
        )

        out = await tool.ainvoke({"query": "Rule 13"})

        assert out == "search result"
        session.call_tool.assert_awaited_once_with("search", {"query": "Rule 13"})
