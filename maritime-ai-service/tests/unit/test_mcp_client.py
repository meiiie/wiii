"""
Tests for app.mcp.client — MCP Client (MCPToolManager).

Sprint 56: MCP Support.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.mcp.client import MCPToolManager, MCPServerConfig


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
    async def test_missing_langchain_mcp_adapters(self):
        configs = [MCPServerConfig(name="test", transport="http", url="http://test/mcp")]

        with patch.dict("sys.modules", {"langchain_mcp_adapters": None, "langchain_mcp_adapters.client": None}):
            await MCPToolManager.initialize(configs)

        assert MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []

    @pytest.mark.asyncio
    async def test_stdio_without_command_skipped(self):
        """stdio config without command is skipped."""
        import types
        mock_module = types.ModuleType("langchain_mcp_adapters")
        mock_client_module = types.ModuleType("langchain_mcp_adapters.client")
        mock_client_cls = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.get_tools = AsyncMock(return_value=[])
        mock_client_cls.return_value = mock_client_instance
        mock_client_module.MultiServerMCPClient = mock_client_cls
        mock_module.client = mock_client_module

        configs = [MCPServerConfig(name="bad", transport="stdio")]  # No command

        with patch.dict("sys.modules", {
            "langchain_mcp_adapters": mock_module,
            "langchain_mcp_adapters.client": mock_client_module,
        }):
            await MCPToolManager.initialize(configs)

        assert MCPToolManager.is_initialized()

    @pytest.mark.asyncio
    async def test_http_without_url_skipped(self):
        """http config without URL is skipped."""
        import types
        mock_module = types.ModuleType("langchain_mcp_adapters")
        mock_client_module = types.ModuleType("langchain_mcp_adapters.client")
        mock_client_cls = MagicMock()
        mock_client_module.MultiServerMCPClient = mock_client_cls
        mock_module.client = mock_client_module

        configs = [MCPServerConfig(name="bad", transport="http")]  # No URL

        with patch.dict("sys.modules", {
            "langchain_mcp_adapters": mock_module,
            "langchain_mcp_adapters.client": mock_client_module,
        }):
            await MCPToolManager.initialize(configs)

        assert MCPToolManager.is_initialized()


class TestMCPToolManagerShutdown:
    """Test MCPToolManager.shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_without_init(self):
        await MCPToolManager.shutdown()
        assert not MCPToolManager.is_initialized()

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        MCPToolManager._initialized = True
        MCPToolManager._tools = [MagicMock()]
        MCPToolManager._client = MagicMock()
        MCPToolManager._client.close = AsyncMock()

        await MCPToolManager.shutdown()

        assert not MCPToolManager.is_initialized()
        assert MCPToolManager.get_tools() == []


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

    def test_parse_invalid_json(self):
        assert MCPToolManager.parse_configs("invalid") == []

    def test_parse_non_list(self):
        assert MCPToolManager.parse_configs('{"name": "test"}') == []

    def test_parse_non_dict_items_skipped(self):
        assert MCPToolManager.parse_configs('["string"]') == []
