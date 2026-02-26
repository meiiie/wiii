"""
Sprint 193: Tests for MCP Tool Server + Client auto-register.

Tests:
  1. MCPToolDefinition model (4 tests)
  2. Singleton factory (4 tests)
  3. Tool loading from ToolRegistry (8 tests)
  4. Tool loading from UnifiedSkillIndex (5 tests)
  5. list_tools filtering (6 tests)
  6. MCP format export (4 tests)
  7. Schema extraction (4 tests)
  8. MCPToolManager.register_discovered_tools (7 tests)
  9. Config flags (3 tests)
  Total: ~45 tests
"""

import pytest
from unittest.mock import MagicMock, patch

from app.mcp.tool_server import (
    MCPToolDefinition,
    MCPToolServer,
    get_mcp_tool_server,
)
import app.mcp.tool_server as ts_module


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_registry():
    """Create a mock ToolRegistry with sample tools."""
    registry = MagicMock()
    registry._initialized = True

    # Create mock ToolInfo entries
    tools = {}
    for name, cat, desc, roles in [
        ("tool_knowledge_search", "rag", "Search knowledge base", ["student", "teacher", "admin"]),
        ("tool_current_datetime", "utility", "Get current datetime", ["student", "teacher", "admin"]),
        ("tool_search_shopee", "product_search", "Search Shopee Vietnam", ["student", "teacher", "admin"]),
        ("tool_web_search", "utility", "Search the web", ["student", "teacher", "admin"]),
        ("tool_admin_only", "utility", "Admin tool", ["admin"]),
    ]:
        info = MagicMock()
        info.name = name
        info.description = desc
        info.roles = roles
        info.category = MagicMock()
        info.category.value = cat
        info.tool = MagicMock()
        info.tool.args_schema = None  # No schema by default
        tools[name] = info

    registry._tools = tools
    return registry


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton and module state between tests."""
    ts_module._server_instance = None
    yield
    ts_module._server_instance = None


@pytest.fixture
def server():
    """Create a fresh MCPToolServer."""
    return MCPToolServer()


@pytest.fixture
def mock_registry():
    """Create a mock ToolRegistry."""
    return _make_mock_registry()


# ============================================================================
# 1. MCPToolDefinition model (4 tests)
# ============================================================================


class TestMCPToolDefinition:
    """Test MCPToolDefinition dataclass."""

    def test_defaults(self):
        """Default values are sensible."""
        td = MCPToolDefinition(name="test_tool")
        assert td.name == "test_tool"
        assert td.description == ""
        assert td.input_schema == {"type": "object", "properties": {}}
        assert td.source == ""
        assert td.category == ""
        assert "student" in td.roles

    def test_with_values(self):
        """Custom values preserved."""
        td = MCPToolDefinition(
            name="tool_x",
            description="Does X",
            source="tool_registry",
            category="utility",
            roles=["admin"],
        )
        assert td.name == "tool_x"
        assert td.description == "Does X"
        assert td.roles == ["admin"]

    def test_custom_schema(self):
        """Custom input schema preserved."""
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        td = MCPToolDefinition(name="t", input_schema=schema)
        assert "query" in td.input_schema["properties"]

    def test_empty_roles_list(self):
        """Empty roles list means unrestricted."""
        td = MCPToolDefinition(name="t", roles=[])
        assert td.roles == []


# ============================================================================
# 2. Singleton factory (4 tests)
# ============================================================================


class TestSingleton:
    """Test get_mcp_tool_server() singleton."""

    def test_returns_instance(self):
        """Factory returns MCPToolServer."""
        server = get_mcp_tool_server()
        assert isinstance(server, MCPToolServer)

    def test_same_instance(self):
        """Repeated calls return same instance."""
        s1 = get_mcp_tool_server()
        s2 = get_mcp_tool_server()
        assert s1 is s2

    def test_reset_creates_new(self):
        """Resetting singleton allows new creation."""
        s1 = get_mcp_tool_server()
        ts_module._server_instance = None
        s2 = get_mcp_tool_server()
        assert s1 is not s2

    def test_has_public_methods(self):
        """Server has expected public methods."""
        server = get_mcp_tool_server()
        assert hasattr(server, "list_tools")
        assert hasattr(server, "get_tool")
        assert hasattr(server, "refresh")
        assert hasattr(server, "to_mcp_format")
        assert hasattr(server, "count")
        assert hasattr(server, "summary")
        assert hasattr(server, "reset")


# ============================================================================
# 3. Tool loading from ToolRegistry (8 tests)
# ============================================================================


class TestToolRegistryLoading:
    """Test loading tools from ToolRegistry."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_loads_all_tools(self, mock_get_reg, server, mock_registry):
        """Loads all tools from registry."""
        mock_get_reg.return_value = mock_registry
        count = server.refresh()
        assert count == 5

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_tool_names_match(self, mock_get_reg, server, mock_registry):
        """Tool names match registry entries."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        names = {t.name for t in server._cache}
        assert "tool_knowledge_search" in names
        assert "tool_search_shopee" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_source_is_tool_registry(self, mock_get_reg, server, mock_registry):
        """Source field set to 'tool_registry'."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        for t in server._cache:
            assert t.source == "tool_registry"

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_category_preserved(self, mock_get_reg, server, mock_registry):
        """Tool category from registry preserved."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        td = server.get_tool("tool_knowledge_search")
        assert td.category == "rag"

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_roles_preserved(self, mock_get_reg, server, mock_registry):
        """Tool roles from registry preserved."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        td = server.get_tool("tool_admin_only")
        assert td.roles == ["admin"]

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_uninitialized_registry_returns_zero(self, mock_get_reg, server):
        """Uninitialized registry returns 0 tools."""
        reg = MagicMock()
        reg._initialized = False
        mock_get_reg.return_value = reg
        count = server.refresh()
        assert count == 0

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_description_preserved(self, mock_get_reg, server, mock_registry):
        """Tool description from registry preserved."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        td = server.get_tool("tool_search_shopee")
        assert td.description == "Search Shopee Vietnam"

    def test_import_error_graceful(self, server):
        """Handles ImportError gracefully."""
        with patch.dict("sys.modules", {"app.engine.tools.registry": None}):
            # Force re-import to fail
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                count = server._load_from_tool_registry()
        # Should not crash; returns 0
        assert count == 0


# ============================================================================
# 4. Tool loading from UnifiedSkillIndex (5 tests)
# ============================================================================


class TestUnifiedIndexLoading:
    """Test loading from UnifiedSkillIndex."""

    @patch("app.core.config.get_settings")
    def test_disabled_when_flag_off(self, mock_settings, server):
        """Index loading skipped when flag disabled."""
        settings = MagicMock()
        settings.enable_unified_skill_index = False
        mock_settings.return_value = settings
        count = server._load_from_unified_index()
        assert count == 0

    @patch("app.engine.skills.unified_index.get_unified_skill_index")
    @patch("app.core.config.get_settings")
    def test_loads_non_tool_skills(self, mock_settings, mock_get_index, server):
        """Loads domain_knowledge, living_agent, mcp_external skills."""
        settings = MagicMock()
        settings.enable_unified_skill_index = True
        mock_settings.return_value = settings

        # Create mock manifests
        manifest_domain = MagicMock()
        manifest_domain.id = "domain:maritime:colregs"
        manifest_domain.name = "COLREGs"
        manifest_domain.description = "Collision regulations"
        manifest_domain.tool_name = None
        manifest_domain.skill_type = MagicMock()
        manifest_domain.skill_type.value = "domain_knowledge"
        manifest_domain.domain_id = "maritime"

        manifest_tool = MagicMock()
        manifest_tool.id = "tool:tool_knowledge_search"
        manifest_tool.name = "tool_knowledge_search"
        manifest_tool.description = "Search KB"
        manifest_tool.tool_name = "tool_knowledge_search"
        manifest_tool.skill_type = MagicMock()
        manifest_tool.skill_type.value = "tool"
        manifest_tool.domain_id = None

        index = MagicMock()
        index.get_all.return_value = [manifest_domain, manifest_tool]
        mock_get_index.return_value = index

        count = server._load_from_unified_index()
        # Only domain_knowledge loaded (tool type skipped)
        assert count == 1
        assert server._cache[0].name == "domain:maritime:colregs"

    @patch("app.engine.skills.unified_index.get_unified_skill_index")
    @patch("app.core.config.get_settings")
    def test_skips_tool_type(self, mock_settings, mock_get_index, server):
        """Skills with type='tool' are skipped (already in registry)."""
        settings = MagicMock()
        settings.enable_unified_skill_index = True
        mock_settings.return_value = settings

        manifest = MagicMock()
        manifest.id = "tool:tool_x"
        manifest.name = "tool_x"
        manifest.tool_name = "tool_x"
        manifest.skill_type = MagicMock()
        manifest.skill_type.value = "tool"
        manifest.domain_id = None

        index = MagicMock()
        index.get_all.return_value = [manifest]
        mock_get_index.return_value = index

        count = server._load_from_unified_index()
        assert count == 0

    @patch("app.engine.skills.unified_index.get_unified_skill_index")
    @patch("app.core.config.get_settings")
    def test_source_set_to_skill_type(self, mock_settings, mock_get_index, server):
        """Source field matches skill_type value."""
        settings = MagicMock()
        settings.enable_unified_skill_index = True
        mock_settings.return_value = settings

        manifest = MagicMock()
        manifest.id = "living:browsing_skill"
        manifest.name = "browsing_skill"
        manifest.description = "Web browsing"
        manifest.tool_name = None
        manifest.skill_type = MagicMock()
        manifest.skill_type.value = "living_agent"
        manifest.domain_id = None

        index = MagicMock()
        index.get_all.return_value = [manifest]
        mock_get_index.return_value = index

        count = server._load_from_unified_index()
        assert count == 1
        assert server._cache[0].source == "living_agent"

    @patch("app.core.config.get_settings")
    def test_import_error_returns_zero(self, mock_settings, server):
        """Handles ImportError from unified_index gracefully."""
        settings = MagicMock()
        settings.enable_unified_skill_index = True
        mock_settings.return_value = settings

        with patch.dict("sys.modules", {"app.engine.skills.unified_index": None}):
            count = server._load_from_unified_index()
        assert count == 0


# ============================================================================
# 5. list_tools filtering (6 tests)
# ============================================================================


class TestListToolsFiltering:
    """Test list_tools() with various filters."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_filter_by_role(self, mock_get_reg, server, mock_registry):
        """Role filter excludes unauthorized tools."""
        mock_get_reg.return_value = mock_registry
        tools = server.list_tools(user_role="student")
        names = [t.name for t in tools]
        assert "tool_admin_only" not in names
        assert "tool_knowledge_search" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_admin_sees_all(self, mock_get_reg, server, mock_registry):
        """Admin role sees all tools."""
        mock_get_reg.return_value = mock_registry
        tools = server.list_tools(user_role="admin")
        names = [t.name for t in tools]
        assert "tool_admin_only" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_filter_by_category(self, mock_get_reg, server, mock_registry):
        """Category filter works."""
        mock_get_reg.return_value = mock_registry
        tools = server.list_tools(user_role="", category="utility")
        names = [t.name for t in tools]
        assert "tool_web_search" in names
        assert "tool_knowledge_search" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_no_role_filter(self, mock_get_reg, server, mock_registry):
        """Empty role string skips role filter."""
        mock_get_reg.return_value = mock_registry
        tools = server.list_tools(user_role="")
        assert len(tools) == 5

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_exclude_external(self, mock_get_reg, server, mock_registry):
        """include_external=False excludes MCP external tools."""
        mock_get_reg.return_value = mock_registry
        # Add a mock external tool
        server._cache.append(MCPToolDefinition(
            name="ext_tool",
            source="mcp_external",
        ))
        server._loaded = True
        tools = server.list_tools(user_role="", include_external=False)
        names = [t.name for t in tools]
        assert "ext_tool" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_get_tool_by_name(self, mock_get_reg, server, mock_registry):
        """get_tool returns specific tool."""
        mock_get_reg.return_value = mock_registry
        td = server.get_tool("tool_search_shopee")
        assert td is not None
        assert td.name == "tool_search_shopee"

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_get_tool_not_found(self, mock_get_reg, server, mock_registry):
        """get_tool returns None for unknown tool."""
        mock_get_reg.return_value = mock_registry
        td = server.get_tool("nonexistent_tool")
        assert td is None


# ============================================================================
# 6. MCP format export (4 tests)
# ============================================================================


class TestMCPFormatExport:
    """Test to_mcp_format() export."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_returns_list_of_dicts(self, mock_get_reg, server, mock_registry):
        """Export returns list of dicts."""
        mock_get_reg.return_value = mock_registry
        result = server.to_mcp_format()
        assert isinstance(result, list)
        assert len(result) == 5
        assert all(isinstance(d, dict) for d in result)

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_has_required_fields(self, mock_get_reg, server, mock_registry):
        """Each dict has name, description, inputSchema."""
        mock_get_reg.return_value = mock_registry
        result = server.to_mcp_format()
        for d in result:
            assert "name" in d
            assert "description" in d
            assert "inputSchema" in d

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_schema_has_properties(self, mock_get_reg, server, mock_registry):
        """Each inputSchema has 'properties' key."""
        mock_get_reg.return_value = mock_registry
        result = server.to_mcp_format()
        for d in result:
            assert "properties" in d["inputSchema"]

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_summary(self, mock_get_reg, server, mock_registry):
        """summary() returns counts by source and category."""
        mock_get_reg.return_value = mock_registry
        server.refresh()
        s = server.summary()
        assert s["total"] == 5
        assert "tool_registry" in s["by_source"]
        assert s["by_source"]["tool_registry"] == 5
        assert "rag" in s["by_category"]


# ============================================================================
# 7. Schema extraction (4 tests)
# ============================================================================


class TestSchemaExtraction:
    """Test _extract_tool_schema() helper."""

    def test_no_args_schema(self, server):
        """Tool without args_schema returns default."""
        tool = MagicMock()
        tool.args_schema = None
        schema = server._extract_tool_schema(tool)
        assert schema == {"type": "object", "properties": {}}

    def test_pydantic_v2_schema(self, server):
        """Extracts schema from Pydantic v2 model."""
        tool = MagicMock()
        mock_schema = MagicMock()
        mock_schema.model_json_schema.return_value = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        tool.args_schema = mock_schema
        schema = server._extract_tool_schema(tool)
        assert "query" in schema["properties"]

    def test_pydantic_v1_schema(self, server):
        """Extracts schema from Pydantic v1 model (fallback)."""
        tool = MagicMock()
        mock_schema = MagicMock(spec=[])  # No model_json_schema
        mock_schema.schema = MagicMock(return_value={
            "type": "object",
            "properties": {"q": {"type": "string"}},
        })
        tool.args_schema = mock_schema
        schema = server._extract_tool_schema(tool)
        assert "q" in schema["properties"]

    def test_schema_error_returns_default(self, server):
        """Error during schema extraction returns default."""
        tool = MagicMock()
        tool.args_schema = MagicMock()
        tool.args_schema.model_json_schema.side_effect = Exception("boom")
        tool.args_schema.schema.side_effect = Exception("boom")
        schema = server._extract_tool_schema(tool)
        assert schema == {"type": "object", "properties": {}}


# ============================================================================
# 8. MCPToolManager.register_discovered_tools (7 tests)
# ============================================================================


class TestRegisterDiscoveredTools:
    """Test MCPToolManager.register_discovered_tools()."""

    def setup_method(self):
        """Reset MCPToolManager between tests."""
        from app.mcp.client import MCPToolManager
        MCPToolManager.reset()

    def test_not_initialized_returns_zero(self):
        """Returns 0 when not initialized."""
        from app.mcp.client import MCPToolManager
        count = MCPToolManager.register_discovered_tools()
        assert count == 0

    def test_no_tools_returns_zero(self):
        """Returns 0 when no tools loaded."""
        from app.mcp.client import MCPToolManager
        MCPToolManager._initialized = True
        MCPToolManager._tools = []
        count = MCPToolManager.register_discovered_tools()
        assert count == 0

    @patch("app.core.config.get_settings")
    def test_disabled_when_flag_off(self, mock_get_settings):
        """Returns 0 when mcp_auto_register_external=False."""
        from app.mcp.client import MCPToolManager
        MCPToolManager._initialized = True
        MCPToolManager._tools = [MagicMock()]

        settings = MagicMock()
        settings.mcp_auto_register_external = False
        mock_get_settings.return_value = settings

        count = MCPToolManager.register_discovered_tools()
        assert count == 0

    @patch("app.engine.tools.registry.get_tool_registry")
    @patch("app.core.config.get_settings")
    def test_registers_tools(self, mock_get_settings, mock_get_reg):
        """Registers MCP tools into ToolRegistry when enabled."""
        from app.mcp.client import MCPToolManager

        settings = MagicMock()
        settings.mcp_auto_register_external = True
        mock_get_settings.return_value = settings

        registry = MagicMock()
        registry.get_info.return_value = None  # Not already registered
        mock_get_reg.return_value = registry

        tool1 = MagicMock()
        tool1.name = "mcp_filesystem"
        tool1.description = "Read/write files"

        tool2 = MagicMock()
        tool2.name = "mcp_web"
        tool2.description = "Web operations"

        MCPToolManager._initialized = True
        MCPToolManager._tools = [tool1, tool2]

        count = MCPToolManager.register_discovered_tools()
        assert count == 2
        assert registry.register.call_count == 2

    @patch("app.engine.tools.registry.get_tool_registry")
    @patch("app.core.config.get_settings")
    def test_skips_already_registered(self, mock_get_settings, mock_get_reg):
        """Skips tools already in ToolRegistry."""
        from app.mcp.client import MCPToolManager

        settings = MagicMock()
        settings.mcp_auto_register_external = True
        mock_get_settings.return_value = settings

        registry = MagicMock()
        # First tool already exists, second doesn't
        registry.get_info.side_effect = [MagicMock(), None]
        mock_get_reg.return_value = registry

        tool1 = MagicMock()
        tool1.name = "existing_tool"
        tool2 = MagicMock()
        tool2.name = "new_mcp_tool"
        tool2.description = "New tool"

        MCPToolManager._initialized = True
        MCPToolManager._tools = [tool1, tool2]

        count = MCPToolManager.register_discovered_tools()
        assert count == 1  # Only new_mcp_tool registered

    @patch("app.engine.tools.registry.get_tool_registry")
    @patch("app.core.config.get_settings")
    def test_handles_registration_error(self, mock_get_settings, mock_get_reg):
        """Handles errors during individual tool registration."""
        from app.mcp.client import MCPToolManager

        settings = MagicMock()
        settings.mcp_auto_register_external = True
        mock_get_settings.return_value = settings

        registry = MagicMock()
        registry.get_info.return_value = None
        registry.register.side_effect = [Exception("boom"), None]  # First fails, second succeeds
        mock_get_reg.return_value = registry

        tool1 = MagicMock()
        tool1.name = "bad_tool"
        tool1.description = "Fails"
        tool2 = MagicMock()
        tool2.name = "good_tool"
        tool2.description = "Works"

        MCPToolManager._initialized = True
        MCPToolManager._tools = [tool1, tool2]

        count = MCPToolManager.register_discovered_tools()
        assert count == 1  # Only good_tool succeeded

    @patch("app.engine.tools.registry.get_tool_registry")
    @patch("app.core.config.get_settings")
    def test_uses_mcp_category(self, mock_get_settings, mock_get_reg):
        """Registered tools get category=MCP."""
        from app.mcp.client import MCPToolManager
        from app.engine.tools.registry import ToolCategory, ToolAccess

        settings = MagicMock()
        settings.mcp_auto_register_external = True
        mock_get_settings.return_value = settings

        registry = MagicMock()
        registry.get_info.return_value = None
        mock_get_reg.return_value = registry

        tool = MagicMock()
        tool.name = "mcp_tool"
        tool.description = "MCP tool"

        MCPToolManager._initialized = True
        MCPToolManager._tools = [tool]

        MCPToolManager.register_discovered_tools()

        # Verify register called with ToolCategory.MCP
        call_kwargs = registry.register.call_args
        assert call_kwargs[1]["category"] == ToolCategory.MCP
        assert call_kwargs[1]["access"] == ToolAccess.READ


# ============================================================================
# 9. Config flags (3 tests)
# ============================================================================


class TestConfigFlags:
    """Test Sprint 193 config flags exist."""

    def test_mcp_tool_server_flag_exists(self):
        """enable_mcp_tool_server flag exists with False default."""
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
        )
        assert hasattr(s, "enable_mcp_tool_server")
        assert s.enable_mcp_tool_server is False

    def test_mcp_auto_register_flag_exists(self):
        """mcp_auto_register_external flag exists with False default."""
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
        )
        assert hasattr(s, "mcp_auto_register_external")
        assert s.mcp_auto_register_external is False

    def test_count_and_reset(self):
        """count() and reset() work correctly."""
        server = MCPToolServer()
        server._cache = [
            MCPToolDefinition(name="t1"),
            MCPToolDefinition(name="t2"),
        ]
        server._loaded = True
        assert server.count() == 2

        server.reset()
        assert server._loaded is False
        assert len(server._cache) == 0
