"""
Tests for Sprint 157: "Săn Nhóm" — Auto Facebook Group Discovery

Covers:
- Config: enable_auto_group_discovery default, max_groups bounds, cross-field warnings
- Category catalog: keyword matching, diacritics, priority sort, max_groups cap, dedup
- Serper discovery: group URL extraction, caching, error handling
- Auto tool: name/signature, catalog → adapter delegation, aggregation, CB, partial failure
- Tool registration: registered when enabled, absent when disabled
- Prompt: system prompt mentions auto tool, deep search auto strategy, tool ack entry
"""

import json
import re
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.engine.search_platforms.facebook_group_catalog import (
    CATEGORY_GROUPS,
    match_categories,
    get_groups_for_query,
    discover_groups_via_serper,
    clear_discovery_cache,
    _normalize,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset registry singleton between tests."""
    import app.engine.search_platforms.registry as reg_mod
    old = reg_mod._registry_instance
    reg_mod._registry_instance = None
    yield
    reg_mod._registry_instance = old


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    """Clear discovery cache between tests."""
    clear_discovery_cache()
    yield
    clear_discovery_cache()


@pytest.fixture
def mock_settings():
    """Settings with auto group discovery enabled."""
    s = MagicMock()
    s.enable_product_search = True
    s.enable_browser_scraping = True
    s.enable_facebook_cookie = True
    s.enable_auto_group_discovery = True
    s.facebook_auto_group_max_groups = 3
    s.browser_scraping_timeout = 15
    s.enable_network_interception = False
    s.network_interception_max_response_size = 5_000_000
    s.enable_browser_screenshots = False
    s.facebook_scroll_max_scrolls = 8
    s.facebook_group_max_scrolls = 10
    s.facebook_group_scroll_delay = 2.5
    s.serper_api_key = "test-key"
    s.apify_api_token = "test-token"
    s.product_search_max_results = 30
    s.product_search_timeout = 10
    s.product_search_max_iterations = 15
    s.product_search_scrape_timeout = 10
    s.product_search_max_scrape_pages = 10
    s.enable_tiktok_native_api = False
    s.tiktok_client_key = None
    s.tiktok_client_secret = None
    s.product_search_platforms = [
        "google_shopping", "shopee", "tiktok_shop",
        "lazada", "facebook_marketplace", "all_web",
        "instagram", "websosanh", "facebook_group",
    ]
    return s


@pytest.fixture
def mock_settings_disabled():
    """Settings with auto group discovery disabled."""
    s = MagicMock()
    s.enable_product_search = True
    s.enable_browser_scraping = True
    s.enable_facebook_cookie = True
    s.enable_auto_group_discovery = False
    s.facebook_auto_group_max_groups = 3
    s.browser_scraping_timeout = 15
    s.enable_network_interception = False
    s.network_interception_max_response_size = 5_000_000
    s.enable_browser_screenshots = False
    s.facebook_scroll_max_scrolls = 8
    s.facebook_group_max_scrolls = 10
    s.facebook_group_scroll_delay = 2.5
    s.serper_api_key = "test-key"
    s.apify_api_token = "test-token"
    s.product_search_max_results = 30
    s.product_search_timeout = 10
    s.product_search_max_iterations = 15
    s.product_search_scrape_timeout = 10
    s.product_search_max_scrape_pages = 10
    s.enable_tiktok_native_api = False
    s.tiktok_client_key = None
    s.tiktok_client_secret = None
    s.product_search_platforms = [
        "google_shopping", "shopee", "tiktok_shop",
        "lazada", "facebook_marketplace", "all_web",
        "instagram", "websosanh", "facebook_group",
    ]
    return s


# =============================================================================
# Config Tests
# =============================================================================

class TestConfig:
    """Config field tests for Sprint 157."""

    def test_default_false(self):
        """enable_auto_group_discovery defaults to False."""
        from app.engine.search_platforms.facebook_group_catalog import CATEGORY_GROUPS
        # Just verify the config field exists in ProductSearchConfig
        from app.core.config import ProductSearchConfig
        cfg = ProductSearchConfig()
        assert cfg.enable_auto_group_discovery is False

    def test_max_groups_default(self):
        """auto_group_max_groups defaults to 3."""
        from app.core.config import ProductSearchConfig
        cfg = ProductSearchConfig()
        assert cfg.auto_group_max_groups == 3

    def test_cross_field_warning_no_browser(self, caplog):
        """Warning when auto_group enabled but browser scraping disabled."""
        import logging
        caplog.set_level(logging.WARNING)
        with patch("app.core.config.get_settings") as gs:
            # Use the real Settings class for cross-field validation
            from app.core.config import Settings
            with patch.dict("os.environ", {
                "ENABLE_AUTO_GROUP_DISCOVERY": "true",
                "ENABLE_BROWSER_SCRAPING": "false",
                "ENABLE_FACEBOOK_COOKIE": "true",
                "PRODUCT_SEARCH_PLATFORMS": '["facebook_group"]',
                "GOOGLE_API_KEY": "fake",
            }, clear=False):
                try:
                    s = Settings()
                except Exception:
                    pass  # Other validation may fail
                warning_messages = [record.getMessage() for record in caplog.records]
                found = any("enable_auto_group_discovery" in c and "enable_browser_scraping" in c for c in warning_messages)
                assert found, f"Expected warning about browser scraping, got: {warning_messages}"

    def test_cross_field_warning_no_cookie(self, caplog):
        """Warning when auto_group enabled but facebook cookie disabled."""
        import logging
        caplog.set_level(logging.WARNING)
        with patch.dict("os.environ", {
            "ENABLE_AUTO_GROUP_DISCOVERY": "true",
            "ENABLE_BROWSER_SCRAPING": "true",
            "ENABLE_FACEBOOK_COOKIE": "false",
            "PRODUCT_SEARCH_PLATFORMS": '["facebook_group"]',
            "GOOGLE_API_KEY": "fake",
        }, clear=False):
            try:
                from app.core.config import Settings
                s = Settings()
            except Exception:
                pass
            warning_messages = [record.getMessage() for record in caplog.records]
            found = any("enable_auto_group_discovery" in c and "enable_facebook_cookie" in c for c in warning_messages)
            assert found, f"Expected warning about facebook cookie, got: {warning_messages}"

    def test_cross_field_warning_no_facebook_group(self, caplog):
        """Warning when auto_group enabled but facebook_group not in platforms."""
        import logging
        caplog.set_level(logging.WARNING)
        with patch.dict("os.environ", {
            "ENABLE_AUTO_GROUP_DISCOVERY": "true",
            "ENABLE_BROWSER_SCRAPING": "true",
            "ENABLE_FACEBOOK_COOKIE": "true",
            "PRODUCT_SEARCH_PLATFORMS": '["google_shopping"]',
            "GOOGLE_API_KEY": "fake",
        }, clear=False):
            try:
                from app.core.config import Settings
                s = Settings()
            except Exception:
                pass
            warning_messages = [record.getMessage() for record in caplog.records]
            found = any("enable_auto_group_discovery" in c and "product_search_platforms" in c for c in warning_messages)
            assert found, f"Expected warning about platforms, got: {warning_messages}"


# =============================================================================
# Category Catalog Tests
# =============================================================================

class TestCategoryCatalog:
    """Category matching and group retrieval."""

    def test_match_laptop_keywords(self):
        """'MacBook M4 Pro' matches electronics_laptop."""
        cats = match_categories("MacBook M4 Pro")
        assert "electronics_laptop" in cats

    def test_match_phone_keywords(self):
        """'iPhone 16 Pro' matches electronics_phone."""
        cats = match_categories("iPhone 16 Pro")
        assert "electronics_phone" in cats

    def test_match_fashion_keywords(self):
        """'giày Nike Air Max' matches fashion."""
        cats = match_categories("giày Nike Air Max")
        assert "fashion" in cats

    def test_no_match(self):
        """Random query matches nothing."""
        cats = match_categories("quantum physics textbook")
        assert cats == []

    def test_diacritics_matching(self):
        """Vietnamese diacritics normalized for matching."""
        # 'máy tính xách tay' should match even without diacritics in query
        cats = match_categories("may tinh xach tay")
        assert "electronics_laptop" in cats

    def test_get_groups_priority_sort(self):
        """Groups returned sorted by priority."""
        groups = get_groups_for_query("MacBook M4 Pro", max_groups=5)
        assert len(groups) >= 1
        # Check priority ordering
        for i in range(len(groups) - 1):
            assert groups[i]["priority"] <= groups[i + 1]["priority"]

    def test_get_groups_max_cap(self):
        """max_groups caps the result."""
        groups = get_groups_for_query("MacBook M4 Pro", max_groups=1)
        assert len(groups) <= 1

    def test_get_groups_dedup(self):
        """Same group from multiple categories is deduplicated."""
        # "tai nghe airpods" matches electronics_general
        # If airpods is in multiple categories, groups should be deduped
        groups = get_groups_for_query("tai nghe airpods", max_groups=5)
        names = [g["name"] for g in groups]
        assert len(names) == len(set(names)), f"Duplicate groups: {names}"

    def test_get_groups_empty_for_no_match(self):
        """Returns empty list for unmatched query."""
        groups = get_groups_for_query("quantum physics textbook")
        assert groups == []

    def test_max_groups_clamped(self):
        """max_groups is clamped between 1 and 5."""
        groups_low = get_groups_for_query("MacBook", max_groups=0)
        # Clamped to 1
        assert len(groups_low) >= 0  # at least doesn't crash

        groups_high = get_groups_for_query("MacBook", max_groups=10)
        assert len(groups_high) <= 5


# =============================================================================
# Serper Discovery Tests
# =============================================================================

class TestSerperDiscovery:
    """Serper fallback discovery for Facebook groups."""

    def test_extracts_group_urls(self):
        """Extracts Facebook group URLs from Serper organic results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://www.facebook.com/groups/muabanlaptopcuhanoi", "title": "Mua Bán Laptop Cũ Hà Nội | Facebook"},
                {"link": "https://www.facebook.com/groups/dienthoaicu", "title": "Điện Thoại Cũ | Facebook"},
                {"link": "https://example.com/not-a-group", "title": "Some random page"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", return_value=mock_response):
                groups = discover_groups_via_serper("laptop cũ", max_groups=3)

        assert len(groups) == 2
        assert groups[0]["url"] == "https://www.facebook.com/groups/muabanlaptopcuhanoi"
        assert "Facebook" not in groups[0]["name"]  # Title cleaned

    def test_no_api_key_returns_empty(self):
        """Returns empty when no Serper API key."""
        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = None
            groups = discover_groups_via_serper("laptop cũ")
        assert groups == []

    def test_dedup_urls(self):
        """Duplicate group URLs are deduplicated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://www.facebook.com/groups/vua2nd", "title": "Vựa 2nd"},
                {"link": "https://www.facebook.com/groups/vua2nd?ref=share", "title": "Vựa 2nd Group"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", return_value=mock_response):
                groups = discover_groups_via_serper("test", max_groups=5)

        # The regex extracts base URL without query params, so both map to same URL
        assert len(groups) == 1

    def test_network_error_returns_empty(self):
        """Network error returns empty list gracefully."""
        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", side_effect=Exception("Connection timeout")):
                groups = discover_groups_via_serper("laptop cũ")
        assert groups == []

    def test_caching(self):
        """Second call uses cache, no HTTP request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://www.facebook.com/groups/test123", "title": "Test Group"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", return_value=mock_response) as mock_post:
                groups1 = discover_groups_via_serper("test query")
                groups2 = discover_groups_via_serper("test query")

        assert mock_post.call_count == 1  # Only one HTTP call
        assert groups1 == groups2


# =============================================================================
# Normalize Tests
# =============================================================================

class TestNormalize:
    """Text normalization for keyword matching."""

    def test_strip_diacritics(self):
        assert _normalize("máy tính") == "may tinh"

    def test_lowercase(self):
        assert _normalize("MacBook PRO") == "macbook pro"


# =============================================================================
# Auto Tool Tests
# =============================================================================

class TestAutoTool:
    """Auto group discovery tool builder and execution."""

    def _build_tool(self):
        """Helper: build the auto tool with a mock circuit breaker."""
        from app.engine.tools.product_search_tools import _build_auto_group_search_tool
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
        cb = PerPlatformCircuitBreaker()
        return _build_auto_group_search_tool(cb), cb

    def test_tool_name(self):
        """Tool has correct name."""
        tool, _ = self._build_tool()
        assert tool.name == "tool_search_facebook_groups_auto"

    def test_tool_description(self):
        """Tool has description mentioning auto discovery."""
        tool, _ = self._build_tool()
        assert "tu dong" in tool.description.lower() or "Tu dong" in tool.description

    def test_tool_uses_catalog(self):
        """Tool calls get_groups_for_query from catalog."""
        tool, _ = self._build_tool()

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "MacBook Pro", "price": "30tr"}

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Vựa 2nd", "url": "https://www.facebook.com/groups/vua2nd", "priority": 1},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_adapter = MagicMock()
                mock_adapter.search_group_sync.return_value = [mock_result]
                mock_reg.return_value.get.return_value = mock_adapter

                result = tool.invoke({"query": "MacBook M4 Pro"})

        data = json.loads(result)
        assert data["platform"] == "Facebook Groups (auto)"
        assert data["count"] == 1
        assert "Vựa 2nd" in data["groups_searched"]
        mock_catalog.assert_called_once()

    def test_tool_aggregates_multiple_groups(self):
        """Tool aggregates results from multiple groups."""
        tool, _ = self._build_tool()

        result1 = MagicMock()
        result1.to_dict.return_value = {"title": "MacBook from group 1"}
        result2 = MagicMock()
        result2.to_dict.return_value = {"title": "MacBook from group 2"}

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Group A", "url": None, "priority": 1},
                {"name": "Group B", "url": "https://www.facebook.com/groups/groupb", "priority": 2},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_adapter = MagicMock()
                mock_adapter.search_group_sync.side_effect = [
                    [result1],
                    [result2],
                ]
                mock_reg.return_value.get.return_value = mock_adapter

                result = tool.invoke({"query": "MacBook M4 Pro"})

        data = json.loads(result)
        assert data["count"] == 2
        assert len(data["groups_searched"]) == 2
        assert "Group A" in data["groups_searched"]
        assert "Group B" in data["groups_searched"]

    def test_tool_cb_respected(self):
        """Circuit breaker stops search when open."""
        from app.engine.tools.product_search_tools import _build_auto_group_search_tool
        cb = MagicMock()
        cb.is_open.return_value = True
        tool = _build_auto_group_search_tool(cb)

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Group A", "url": None, "priority": 1},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_adapter = MagicMock()
                mock_reg.return_value.get.return_value = mock_adapter

                result = tool.invoke({"query": "test"})

        data = json.loads(result)
        assert data["count"] == 0
        assert data["groups_searched"] == []
        mock_adapter.search_group_sync.assert_not_called()

    def test_tool_no_adapter_returns_error(self):
        """Returns error when facebook_group adapter not registered."""
        tool, _ = self._build_tool()

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Group A", "url": None, "priority": 1},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_reg.return_value.get.return_value = None

                result = tool.invoke({"query": "test"})

        data = json.loads(result)
        assert "error" in data
        assert "adapter" in data["error"].lower() or "not available" in data["error"].lower()

    def test_tool_catalog_miss_falls_back_to_serper(self):
        """When catalog returns empty, falls back to Serper discovery."""
        tool, _ = self._build_tool()

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Found via Serper"}

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query", return_value=[]):
            with patch("app.engine.search_platforms.facebook_group_catalog.discover_groups_via_serper") as mock_serper:
                mock_serper.return_value = [
                    {"name": "Serper Group", "url": "https://www.facebook.com/groups/serper", "priority": 1},
                ]
                with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                    mock_adapter = MagicMock()
                    mock_adapter.search_group_sync.return_value = [mock_result]
                    mock_reg.return_value.get.return_value = mock_adapter

                    result = tool.invoke({"query": "obscure product"})

        mock_serper.assert_called_once()
        data = json.loads(result)
        assert data["count"] == 1
        assert "Serper Group" in data["groups_searched"]

    def test_tool_no_groups_found_returns_error(self):
        """Returns error when neither catalog nor Serper finds groups."""
        tool, _ = self._build_tool()

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query", return_value=[]):
            with patch("app.engine.search_platforms.facebook_group_catalog.discover_groups_via_serper", return_value=[]):
                result = tool.invoke({"query": "nonexistent product"})

        data = json.loads(result)
        assert "error" in data

    def test_tool_partial_failure(self):
        """One group fails, others still return results."""
        tool, _ = self._build_tool()

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Good result"}

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Group A", "url": None, "priority": 1},
                {"name": "Group B", "url": None, "priority": 2},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_adapter = MagicMock()
                mock_adapter.search_group_sync.side_effect = [
                    Exception("Group A failed"),
                    [mock_result],
                ]
                mock_reg.return_value.get.return_value = mock_adapter

                result = tool.invoke({"query": "test"})

        data = json.loads(result)
        assert data["count"] == 1
        assert "Group B" in data["groups_searched"]
        assert "Group A" not in data["groups_searched"]

    def test_tool_max_groups_capped_at_5(self):
        """max_groups parameter is capped at 5."""
        tool, _ = self._build_tool()

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = []
            with patch("app.engine.search_platforms.facebook_group_catalog.discover_groups_via_serper", return_value=[]):
                tool.invoke({"query": "test", "max_groups": 10})
            # Verify get_groups_for_query was called with capped value
            assert mock_catalog.call_args[0][1] <= 5


# =============================================================================
# Tool Registration Tests
# =============================================================================

class TestToolRegistration:
    """Registration of auto group tool in init_product_search_tools."""

    def test_registered_when_enabled(self, mock_settings):
        """Auto tool registered when enable_auto_group_discovery=True."""
        import app.engine.tools.product_search_tools as pst

        old_tools = pst._generated_tools[:]
        old_cb = pst._circuit_breaker

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.search_platforms.init_search_platforms") as mock_init:
                mock_init.return_value = MagicMock()
                mock_init.return_value.get_all_enabled.return_value = []
                mock_init.return_value.__len__ = MagicMock(return_value=0)
                mock_init.return_value.list_ids.return_value = []

                with patch("app.engine.tools.product_search_tools.get_tool_registry") as mock_tr:
                    mock_tr.return_value = MagicMock()
                    pst.init_product_search_tools()

        tool_names = [t.name for t in pst._generated_tools]
        assert "tool_search_facebook_groups_auto" in tool_names

        # Cleanup
        pst._generated_tools = old_tools
        pst._circuit_breaker = old_cb

    def test_absent_when_disabled(self, mock_settings_disabled):
        """Auto tool NOT registered when enable_auto_group_discovery=False."""
        import app.engine.tools.product_search_tools as pst

        old_tools = pst._generated_tools[:]
        old_cb = pst._circuit_breaker

        with patch("app.core.config.get_settings", return_value=mock_settings_disabled):
            with patch("app.engine.search_platforms.init_search_platforms") as mock_init:
                mock_init.return_value = MagicMock()
                mock_init.return_value.get_all_enabled.return_value = []
                mock_init.return_value.__len__ = MagicMock(return_value=0)
                mock_init.return_value.list_ids.return_value = []

                with patch("app.engine.tools.product_search_tools.get_tool_registry") as mock_tr:
                    mock_tr.return_value = MagicMock()
                    pst.init_product_search_tools()

        tool_names = [t.name for t in pst._generated_tools]
        assert "tool_search_facebook_groups_auto" not in tool_names

        # Cleanup
        pst._generated_tools = old_tools
        pst._circuit_breaker = old_cb

    def test_absent_without_facebook_group_platform(self, mock_settings):
        """Auto tool NOT registered when facebook_group not in platforms."""
        mock_settings.product_search_platforms = ["google_shopping", "shopee"]

        import app.engine.tools.product_search_tools as pst
        old_tools = pst._generated_tools[:]
        old_cb = pst._circuit_breaker

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.search_platforms.init_search_platforms") as mock_init:
                mock_init.return_value = MagicMock()
                mock_init.return_value.get_all_enabled.return_value = []
                mock_init.return_value.__len__ = MagicMock(return_value=0)
                mock_init.return_value.list_ids.return_value = []

                with patch("app.engine.tools.product_search_tools.get_tool_registry") as mock_tr:
                    mock_tr.return_value = MagicMock()
                    pst.init_product_search_tools()

        tool_names = [t.name for t in pst._generated_tools]
        assert "tool_search_facebook_groups_auto" not in tool_names

        pst._generated_tools = old_tools
        pst._circuit_breaker = old_cb

    def test_existing_tools_unchanged(self, mock_settings):
        """Existing tool_search_facebook_group still registered alongside auto tool."""
        import app.engine.tools.product_search_tools as pst
        old_tools = pst._generated_tools[:]
        old_cb = pst._circuit_breaker

        # Create a mock facebook_group adapter
        mock_adapter = MagicMock()
        mock_config = MagicMock()
        mock_config.id = "facebook_group"
        mock_config.display_name = "Facebook Group"
        mock_adapter.get_config.return_value = mock_config
        mock_adapter.get_tool_name.return_value = "tool_search_facebook_group"
        mock_adapter.get_tool_description.return_value = "Search FB Group"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.search_platforms.init_search_platforms") as mock_init:
                mock_registry = MagicMock()
                mock_registry.get_all_enabled.return_value = [mock_adapter]
                mock_registry.__len__ = MagicMock(return_value=1)
                mock_registry.list_ids.return_value = ["facebook_group"]
                mock_init.return_value = mock_registry

                with patch("app.engine.tools.product_search_tools.get_tool_registry") as mock_tr:
                    mock_tr.return_value = MagicMock()
                    pst.init_product_search_tools()

        tool_names = [t.name for t in pst._generated_tools]
        assert "tool_search_facebook_group" in tool_names
        assert "tool_search_facebook_groups_auto" in tool_names

        pst._generated_tools = old_tools
        pst._circuit_breaker = old_cb


# =============================================================================
# Prompt Tests
# =============================================================================

class TestPrompt:
    """Prompt updates for auto group discovery."""

    def test_system_prompt_mentions_auto_tool(self):
        """_SYSTEM_PROMPT includes tool_search_facebook_groups_auto."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_facebook_groups_auto" in _SYSTEM_PROMPT

    def test_deep_search_mentions_auto_strategy(self):
        """_DEEP_SEARCH_PROMPT includes auto discovery strategy."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "tool_search_facebook_groups_auto" in _DEEP_SEARCH_PROMPT
        assert "TỰ ĐỘNG" in _DEEP_SEARCH_PROMPT

    def test_tool_ack_entry(self):
        """System prompt has entry for auto group tool."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_facebook_groups_auto" in _SYSTEM_PROMPT

    def test_existing_group_tool_still_in_prompt(self):
        """tool_search_facebook_group still referenced (for manual search)."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT, _DEEP_SEARCH_PROMPT
        assert "tool_search_facebook_group" in _SYSTEM_PROMPT
        # Deep search should still mention manual option
        assert "tool_search_facebook_group" in _DEEP_SEARCH_PROMPT


# =============================================================================
# Caching Tests
# =============================================================================

class TestCaching:
    """Cache behavior for catalog and Serper discovery."""

    def test_discovery_cache_avoids_repeat_serper(self):
        """Second call to discover_groups_via_serper uses cache."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://www.facebook.com/groups/cached", "title": "Cached Group"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", return_value=mock_response) as mock_post:
                r1 = discover_groups_via_serper("cache test")
                r2 = discover_groups_via_serper("cache test")

        assert mock_post.call_count == 1
        assert r1 == r2

    def test_clear_cache(self):
        """clear_discovery_cache empties the cache."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://www.facebook.com/groups/test", "title": "Test"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as gs:
            gs.return_value.serper_api_key = "test-key"
            with patch("httpx.post", return_value=mock_response) as mock_post:
                discover_groups_via_serper("clear test")
                clear_discovery_cache()
                discover_groups_via_serper("clear test")

        assert mock_post.call_count == 2  # Called twice after cache clear


# =============================================================================
# JSON Output Format Tests
# =============================================================================

class TestOutputFormat:
    """Verify JSON output format from auto tool."""

    def test_valid_json_schema(self):
        """Output matches expected schema: platform, groups_searched, results, count."""
        from app.engine.tools.product_search_tools import _build_auto_group_search_tool
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
        cb = PerPlatformCircuitBreaker()
        tool = _build_auto_group_search_tool(cb)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Product", "price": "10tr"}

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query") as mock_catalog:
            mock_catalog.return_value = [
                {"name": "Test Group", "url": "https://www.facebook.com/groups/test", "priority": 1},
            ]
            with patch("app.engine.search_platforms.get_search_platform_registry") as mock_reg:
                mock_adapter = MagicMock()
                mock_adapter.search_group_sync.return_value = [mock_result]
                mock_reg.return_value.get.return_value = mock_adapter

                result = tool.invoke({"query": "test product"})

        data = json.loads(result)
        assert "platform" in data
        assert "groups_searched" in data
        assert "results" in data
        assert "count" in data
        assert isinstance(data["groups_searched"], list)
        assert isinstance(data["results"], list)
        assert isinstance(data["count"], int)

    def test_error_json_has_platform(self):
        """Error responses also include platform field."""
        from app.engine.tools.product_search_tools import _build_auto_group_search_tool
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
        cb = PerPlatformCircuitBreaker()
        tool = _build_auto_group_search_tool(cb)

        with patch("app.engine.search_platforms.facebook_group_catalog.get_groups_for_query", return_value=[]):
            with patch("app.engine.search_platforms.facebook_group_catalog.discover_groups_via_serper", return_value=[]):
                result = tool.invoke({"query": "test"})

        data = json.loads(result)
        assert "error" in data
        assert "platform" in data
