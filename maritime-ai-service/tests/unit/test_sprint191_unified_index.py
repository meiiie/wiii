"""
Sprint 191: Unified Skill Index Unit Tests

Tests the UnifiedSkillIndex, source adapters, and UnifiedSkillManifest model.
All tests run WITHOUT real ToolRegistry/DomainRegistry/SkillBuilder/MCP — fully mocked.

40 tests across 7 categories:
1. SkillType & SkillMetrics models (5 tests)
2. UnifiedSkillManifest (6 tests)
3. UnifiedSkillIndex initialization (4 tests)
4. UnifiedSkillIndex refresh (6 tests)
5. UnifiedSkillIndex query API (9 tests)
6. Source adapters (7 tests)
7. Singleton & thread safety (3 tests)
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.engine.skills.skill_manifest_v2 import (
    SkillMetrics,
    SkillType,
    UnifiedSkillManifest,
)
from app.engine.skills.unified_index import (
    UnifiedSkillIndex,
    get_unified_skill_index,
    _load_from_tool_registry,
    _load_from_domain_plugins,
    _load_from_living_agent,
    _load_from_mcp_tools,
)
import app.engine.skills.unified_index as idx_module


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after every test."""
    idx_module._index_instance = None
    yield
    idx_module._index_instance = None


@pytest.fixture
def sample_tools():
    """Sample tool manifests for testing."""
    return [
        UnifiedSkillManifest(
            id="tool:tool_search_shopee",
            name="tool_search_shopee",
            description="Tìm kiếm sản phẩm trên Shopee",
            skill_type=SkillType.TOOL,
            category="product_search",
            tool_name="tool_search_shopee",
        ),
        UnifiedSkillManifest(
            id="tool:tool_knowledge_search",
            name="tool_knowledge_search",
            description="Tìm kiếm kiến thức trong cơ sở dữ liệu",
            skill_type=SkillType.TOOL,
            category="rag",
            tool_name="tool_knowledge_search",
        ),
    ]


@pytest.fixture
def sample_domain_skills():
    """Sample domain skill manifests."""
    return [
        UnifiedSkillManifest(
            id="domain:maritime:colregs",
            name="COLREGs Navigation Rules",
            description="International regulations for preventing collisions at sea",
            skill_type=SkillType.DOMAIN_KNOWLEDGE,
            domain_id="maritime",
            triggers=["colregs", "collision", "navigation"],
            content_path=Path("/app/domains/maritime/skills/colregs/SKILL.md"),
        ),
        UnifiedSkillManifest(
            id="domain:maritime:solas",
            name="SOLAS Safety",
            description="Safety of Life at Sea international convention",
            skill_type=SkillType.DOMAIN_KNOWLEDGE,
            domain_id="maritime",
            triggers=["solas", "safety", "lifesaving"],
        ),
    ]


@pytest.fixture
def sample_living_skills():
    """Sample living agent skill manifests."""
    return [
        UnifiedSkillManifest(
            id="living:colregs_rule_14",
            name="colregs_rule_14",
            description="Head-on situation rules",
            skill_type=SkillType.LIVING_AGENT,
            domain_id="maritime",
            wiii_skill_id=uuid4(),
            status="mastered",
            confidence=0.95,
        ),
    ]


@pytest.fixture
def sample_mcp_tools():
    """Sample MCP tool manifests."""
    return [
        UnifiedSkillManifest(
            id="mcp:external:read_file",
            name="read_file",
            description="Read a file from the filesystem",
            skill_type=SkillType.MCP_EXTERNAL,
            mcp_server="filesystem",
        ),
    ]


@pytest.fixture
def populated_index(sample_tools, sample_domain_skills, sample_living_skills, sample_mcp_tools):
    """Index pre-populated with all sample data."""
    index = UnifiedSkillIndex()
    index._sources.clear()  # Remove default sources
    all_items = sample_tools + sample_domain_skills + sample_living_skills + sample_mcp_tools
    index.register_source("test", lambda: all_items)
    index.refresh()
    return index


# ============================================================================
# 1. SkillType & SkillMetrics Models (5 tests)
# ============================================================================


class TestSkillModels:
    """Test SkillType enum and SkillMetrics dataclass."""

    def test_skill_type_values(self):
        """SkillType has all 4 expected values."""
        assert SkillType.TOOL.value == "tool"
        assert SkillType.DOMAIN_KNOWLEDGE.value == "domain_knowledge"
        assert SkillType.LIVING_AGENT.value == "living_agent"
        assert SkillType.MCP_EXTERNAL.value == "mcp_external"

    def test_skill_metrics_defaults(self):
        """SkillMetrics has zero defaults."""
        m = SkillMetrics()
        assert m.total_invocations == 0
        assert m.successful_invocations == 0
        assert m.avg_latency_ms == 0.0
        assert m.total_tokens_used == 0
        assert m.cost_estimate_usd == 0.0
        assert m.last_used is None

    def test_skill_metrics_success_rate(self):
        """success_rate calculates correctly."""
        m = SkillMetrics(total_invocations=10, successful_invocations=8)
        assert m.success_rate == pytest.approx(0.8)

    def test_skill_metrics_success_rate_zero(self):
        """success_rate is 0 when no invocations."""
        m = SkillMetrics()
        assert m.success_rate == 0.0

    def test_skill_metrics_success_rate_all_success(self):
        """success_rate is 1.0 when all succeed."""
        m = SkillMetrics(total_invocations=5, successful_invocations=5)
        assert m.success_rate == pytest.approx(1.0)


# ============================================================================
# 2. UnifiedSkillManifest (6 tests)
# ============================================================================


class TestUnifiedSkillManifest:
    """Test manifest data model and matching."""

    def test_tool_manifest_fields(self):
        """Tool manifest has expected fields."""
        m = UnifiedSkillManifest(
            id="tool:test",
            name="test_tool",
            description="A test tool",
            skill_type=SkillType.TOOL,
            tool_name="test_tool",
            category="utility",
        )
        assert m.id == "tool:test"
        assert m.skill_type == SkillType.TOOL
        assert m.tool_name == "test_tool"
        assert m.category == "utility"

    def test_domain_manifest_fields(self):
        """Domain manifest has content_path and triggers."""
        m = UnifiedSkillManifest(
            id="domain:maritime:colregs",
            name="COLREGs",
            description="Rules",
            skill_type=SkillType.DOMAIN_KNOWLEDGE,
            domain_id="maritime",
            triggers=["colregs", "collision"],
            content_path=Path("/path/to/SKILL.md"),
        )
        assert m.domain_id == "maritime"
        assert m.content_path == Path("/path/to/SKILL.md")
        assert "colregs" in m.triggers

    def test_living_agent_manifest_fields(self):
        """Living agent manifest has status and confidence."""
        uid = uuid4()
        m = UnifiedSkillManifest(
            id="living:test_skill",
            name="test_skill",
            description="Learned skill",
            skill_type=SkillType.LIVING_AGENT,
            wiii_skill_id=uid,
            status="mastered",
            confidence=0.95,
        )
        assert m.wiii_skill_id == uid
        assert m.status == "mastered"
        assert m.confidence == 0.95

    def test_matches_query_positive(self):
        """matches_query returns True for matching keywords."""
        m = UnifiedSkillManifest(
            id="tool:test",
            name="Product Search Shopee",
            description="Search products on Shopee marketplace",
            skill_type=SkillType.TOOL,
        )
        assert m.matches_query("shopee") is True
        assert m.matches_query("product search") is True

    def test_matches_query_negative(self):
        """matches_query returns False for non-matching query."""
        m = UnifiedSkillManifest(
            id="tool:test",
            name="Product Search",
            description="Search products",
            skill_type=SkillType.TOOL,
        )
        assert m.matches_query("colregs navigation") is False

    def test_matches_query_empty(self):
        """matches_query returns False for empty query."""
        m = UnifiedSkillManifest(
            id="tool:test", name="Test", description="",
            skill_type=SkillType.TOOL,
        )
        assert m.matches_query("") is False
        assert m.matches_query("   ") is False


# ============================================================================
# 3. UnifiedSkillIndex Initialization (4 tests)
# ============================================================================


class TestIndexInit:
    """Test index creation and source registration."""

    def test_creates_empty_index(self):
        """New index has no cached skills."""
        index = UnifiedSkillIndex()
        assert index._cache == {}
        assert index.last_refresh_time == 0.0

    def test_has_default_sources(self):
        """Default sources are auto-registered."""
        index = UnifiedSkillIndex()
        assert "tool_registry" in index._sources
        assert "domain_plugins" in index._sources
        assert "living_agent" in index._sources
        assert "mcp_tools" in index._sources

    def test_register_custom_source(self):
        """Custom source can be registered."""
        index = UnifiedSkillIndex()
        index.register_source("custom", lambda: [])
        assert "custom" in index._sources

    def test_custom_source_overrides_default(self):
        """Registering same name replaces previous loader."""
        index = UnifiedSkillIndex()
        custom_loader = lambda: []  # noqa: E731
        index.register_source("tool_registry", custom_loader)
        assert index._sources["tool_registry"] is custom_loader


# ============================================================================
# 4. UnifiedSkillIndex Refresh (6 tests)
# ============================================================================


class TestIndexRefresh:
    """Test cache refresh from sources."""

    def test_refresh_populates_cache(self, populated_index):
        """After refresh, cache has all skills."""
        assert len(populated_index._cache) == 6  # 2 tools + 2 domain + 1 living + 1 mcp

    def test_refresh_returns_count(self):
        """refresh() returns total skill count."""
        index = UnifiedSkillIndex()
        index._sources.clear()
        index.register_source("test", lambda: [
            UnifiedSkillManifest(id="tool:a", name="A", description="", skill_type=SkillType.TOOL),
            UnifiedSkillManifest(id="tool:b", name="B", description="", skill_type=SkillType.TOOL),
        ])
        count = index.refresh()
        assert count == 2

    def test_refresh_updates_timestamp(self):
        """refresh() updates last_refresh_time."""
        index = UnifiedSkillIndex()
        index._sources.clear()
        index.register_source("test", lambda: [])
        assert index.last_refresh_time == 0.0
        index.refresh()
        assert index.last_refresh_time > 0.0

    def test_refresh_handles_source_error(self):
        """refresh() tolerates source errors and continues."""
        index = UnifiedSkillIndex()
        index._sources.clear()

        def failing_source():
            raise RuntimeError("Source failed")

        index.register_source("failing", failing_source)
        index.register_source("working", lambda: [
            UnifiedSkillManifest(id="tool:ok", name="OK", description="", skill_type=SkillType.TOOL),
        ])
        count = index.refresh()
        assert count == 1

    def test_refresh_deduplicates(self):
        """Duplicate IDs are dropped (first wins)."""
        index = UnifiedSkillIndex()
        index._sources.clear()
        index.register_source("source1", lambda: [
            UnifiedSkillManifest(id="tool:dup", name="First", description="", skill_type=SkillType.TOOL),
        ])
        index.register_source("source2", lambda: [
            UnifiedSkillManifest(id="tool:dup", name="Second", description="", skill_type=SkillType.TOOL),
        ])
        index.refresh()
        assert index.get_by_id("tool:dup").name == "First"

    def test_lazy_load_on_first_query(self):
        """First query triggers automatic refresh."""
        index = UnifiedSkillIndex()
        index._sources.clear()
        index.register_source("test", lambda: [
            UnifiedSkillManifest(id="tool:lazy", name="Lazy", description="", skill_type=SkillType.TOOL),
        ])
        # No explicit refresh
        result = index.get_by_id("tool:lazy")
        assert result is not None
        assert result.name == "Lazy"
        assert index.last_refresh_time > 0.0


# ============================================================================
# 5. UnifiedSkillIndex Query API (9 tests)
# ============================================================================


class TestIndexQueryAPI:
    """Test search, get_all, get_by_id, count."""

    def test_get_by_id(self, populated_index):
        """get_by_id returns correct manifest."""
        result = populated_index.get_by_id("tool:tool_search_shopee")
        assert result is not None
        assert result.name == "tool_search_shopee"

    def test_get_by_id_missing(self, populated_index):
        """get_by_id returns None for unknown ID."""
        assert populated_index.get_by_id("tool:nonexistent") is None

    def test_get_all_no_filter(self, populated_index):
        """get_all() returns all skills."""
        all_skills = populated_index.get_all()
        assert len(all_skills) == 6

    def test_get_all_by_type(self, populated_index):
        """get_all(skill_type=...) filters by type."""
        tools = populated_index.get_all(skill_type=SkillType.TOOL)
        assert len(tools) == 2
        assert all(s.skill_type == SkillType.TOOL for s in tools)

    def test_get_all_by_domain(self, populated_index):
        """get_all(domain_id=...) filters by domain."""
        maritime = populated_index.get_all(domain_id="maritime")
        assert len(maritime) == 3  # 2 domain + 1 living (domain_id=maritime)

    def test_get_all_by_category(self, populated_index):
        """get_all(category=...) filters by tool category."""
        rag_tools = populated_index.get_all(category="rag")
        assert len(rag_tools) == 1
        assert rag_tools[0].category == "rag"

    def test_search_keyword_matching(self, populated_index):
        """search() returns matches by keyword."""
        results = populated_index.search("shopee")
        assert len(results) >= 1
        assert any("shopee" in r.name.lower() for r in results)

    def test_search_empty_query(self, populated_index):
        """search() with empty query returns empty list."""
        assert populated_index.search("") == []
        assert populated_index.search("   ") == []

    def test_count_by_type(self, populated_index):
        """count() returns correct type breakdown."""
        counts = populated_index.count()
        assert counts["total"] == 6
        assert counts["tool"] == 2
        assert counts["domain_knowledge"] == 2
        assert counts["living_agent"] == 1
        assert counts["mcp_external"] == 1


# ============================================================================
# 6. Source Adapters (7 tests)
# ============================================================================


class TestSourceAdapters:
    """Test individual source loader functions.

    NOTE: Lazy imports in function bodies → patch at SOURCE module.
    _load_from_tool_registry does `from app.engine.tools.registry import get_tool_registry`
    _load_from_domain_plugins does `from app.domains.registry import get_domain_registry`
    _load_from_living_agent does `from app.core.config import get_settings`
    _load_from_mcp_tools does `from app.core.config import get_settings`
    """

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_tool_registry_adapter(self, mock_get_registry):
        """_load_from_tool_registry converts ToolInfo to manifests."""
        mock_registry = MagicMock()
        mock_registry._initialized = True
        mock_info = MagicMock()
        mock_info.description = "Test tool"
        mock_info.category = MagicMock()
        mock_info.category.value = "utility"
        mock_info.roles = ["student", "admin"]
        mock_registry._tools = {"test_tool": mock_info}
        mock_get_registry.return_value = mock_registry

        results = _load_from_tool_registry()
        assert len(results) == 1
        assert results[0].id == "tool:test_tool"
        assert results[0].skill_type == SkillType.TOOL

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_tool_registry_not_initialized(self, mock_get_registry):
        """Uninitialized ToolRegistry returns empty list."""
        mock_registry = MagicMock()
        mock_registry._initialized = False
        mock_get_registry.return_value = mock_registry
        assert _load_from_tool_registry() == []

    @patch("app.domains.registry.get_domain_registry")
    def test_domain_plugins_adapter(self, mock_get_domain_reg):
        """_load_from_domain_plugins converts SkillManifest to unified manifests."""
        mock_domain_reg = MagicMock()
        mock_domain_reg.list_ids.return_value = ["maritime"]
        mock_plugin = MagicMock()
        mock_skill = MagicMock()
        mock_skill.id = "colregs"
        mock_skill.name = "COLREGs"
        mock_skill.description = "Navigation rules"
        mock_skill.triggers = ["colregs"]
        mock_skill.content_path = None
        mock_skill.version = "1.0.0"
        mock_plugin.get_skills.return_value = [mock_skill]
        mock_domain_reg.get.return_value = mock_plugin
        mock_get_domain_reg.return_value = mock_domain_reg

        results = _load_from_domain_plugins()
        assert len(results) == 1
        assert results[0].id == "domain:maritime:colregs"
        assert results[0].skill_type == SkillType.DOMAIN_KNOWLEDGE

    @patch("app.domains.registry.get_domain_registry")
    def test_domain_plugins_no_skills(self, mock_get_domain_reg):
        """Domain with no skills returns empty list."""
        mock_domain_reg = MagicMock()
        mock_domain_reg.list_ids.return_value = ["empty_domain"]
        mock_plugin = MagicMock()
        mock_plugin.get_skills.return_value = []
        mock_domain_reg.get.return_value = mock_plugin
        mock_get_domain_reg.return_value = mock_domain_reg

        results = _load_from_domain_plugins()
        assert results == []

    @patch("app.core.config.get_settings")
    def test_living_agent_disabled(self, mock_settings):
        """Living agent returns empty when disabled."""
        mock_settings.return_value = MagicMock(enable_living_agent=False)
        assert _load_from_living_agent() == []

    @patch("app.core.config.get_settings")
    def test_mcp_tools_disabled(self, mock_settings):
        """MCP tools returns empty when disabled."""
        mock_settings.return_value = MagicMock(enable_mcp_client=False)
        assert _load_from_mcp_tools() == []

    def test_source_adapter_import_error(self):
        """Source adapter handles errors gracefully via index."""
        # Direct test: the index wraps source errors
        index = UnifiedSkillIndex()
        index._sources.clear()

        def failing_loader():
            raise ImportError("Missing module")

        index.register_source("bad", failing_loader)
        count = index.refresh()
        assert count == 0


# ============================================================================
# 7. Singleton & Thread Safety (3 tests)
# ============================================================================


class TestSingleton:
    """Verify singleton behavior and thread safety."""

    def test_returns_same_instance(self):
        """get_unified_skill_index() returns same object."""
        idx1 = get_unified_skill_index()
        idx2 = get_unified_skill_index()
        assert idx1 is idx2

    def test_reset_creates_new_instance(self):
        """Resetting module-level instance creates fresh index."""
        idx1 = get_unified_skill_index()
        idx_module._index_instance = None
        idx2 = get_unified_skill_index()
        assert idx1 is not idx2

    def test_thread_safe_creation(self):
        """Concurrent threads get same singleton."""
        instances = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            instances.append(get_unified_skill_index())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 5
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first
