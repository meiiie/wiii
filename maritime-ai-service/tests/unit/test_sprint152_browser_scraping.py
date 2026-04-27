"""
Tests for Sprint 152: "Trinh Duyet Thong Minh" — Playwright + LLM Extraction

Covers:
- BackendType.BROWSER enum value
- Config fields (enable_browser_scraping, browser_scraping_timeout)
- URL building (Facebook search URL encoding)
- LLM extraction (JSON parsing, malformed, empty, field mapping)
- Facebook adapter (config, fallback, post_navigate)
- Browser base (page text truncation, empty query, timeout)
- Registration (browser vs serper based on feature flag)
- Extraction prompt template validation
- Regression (Sprint 149-151 tests unbroken)
"""

import json
import re
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


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
def _reset_browser():
    """Reset browser singleton between tests."""
    import app.engine.search_platforms.adapters.browser_base as bb
    old_browser = bb._browser
    old_pw = bb._playwright_instance
    bb._browser = None
    bb._playwright_instance = None
    yield
    bb._browser = old_browser
    bb._playwright_instance = old_pw


@pytest.fixture
def mock_settings():
    """Settings with browser scraping enabled."""
    s = MagicMock()
    s.enable_product_search = True
    s.enable_browser_scraping = True
    s.browser_scraping_timeout = 15
    s.serper_api_key = "test-serper-key"
    s.apify_api_token = "test-apify-token"
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
        "instagram", "websosanh",
    ]
    return s


@pytest.fixture
def mock_settings_no_browser():
    """Settings with browser scraping disabled (default)."""
    s = MagicMock()
    s.enable_product_search = True
    s.enable_browser_scraping = False
    s.browser_scraping_timeout = 15
    s.serper_api_key = "test-serper-key"
    s.apify_api_token = "test-apify-token"
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
        "instagram", "websosanh",
    ]
    return s


# Sample LLM response — valid JSON
_SAMPLE_LLM_RESPONSE = """[
  {
    "title": "iPhone 16 Pro Max 256GB",
    "price": "29.990.000 d",
    "seller": "Nguyen Van A",
    "link": "https://facebook.com/marketplace/item/123",
    "location": "TP. Ho Chi Minh"
  },
  {
    "title": "iPhone 16 Pro Max 512GB Like New",
    "price": "35.000.000 d",
    "seller": "Shop Dien Thoai XYZ",
    "link": "",
    "location": "Ha Noi"
  }
]"""

# Sample LLM response with markdown fences
_FENCED_RESPONSE = """Here are the products I found:

```json
[
  {"title": "Test Product", "price": "1.000.000 d", "seller": "Shop A"}
]
```
"""


# =============================================================================
# Group 1: BackendType.BROWSER
# =============================================================================

class TestBackendTypeBrowser:
    """BackendType enum should include BROWSER value."""

    def test_browser_value_exists(self):
        from app.engine.search_platforms.base import BackendType
        assert BackendType.BROWSER.value == "browser"

    def test_browser_in_enum_members(self):
        from app.engine.search_platforms.base import BackendType
        assert "BROWSER" in [m.name for m in BackendType]


# =============================================================================
# Group 2: Config Fields
# =============================================================================

class TestConfigFields:
    """Config should have browser scraping settings."""

    def test_enable_browser_scraping_default_false(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.enable_browser_scraping is False

    def test_browser_scraping_timeout_default_15(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.browser_scraping_timeout == 15

    def test_enable_browser_scraping_override(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", enable_browser_scraping=True)
        assert s.enable_browser_scraping is True


# =============================================================================
# Group 3: URL Building
# =============================================================================

class TestFacebookURLBuilding:
    """Facebook search URL should be correctly built."""

    def test_basic_query(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        url = adapter._build_url("iPhone 16 Pro Max", 1)
        assert url == "https://www.facebook.com/marketplace/search/?query=iPhone+16+Pro+Max"

    def test_vietnamese_query(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        url = adapter._build_url("dien thoai gia re", 1)
        assert "query=dien+thoai+gia+re" in url

    def test_special_chars(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        url = adapter._build_url("cap USB-C 2m", 1)
        assert "facebook.com/marketplace/search/" in url
        assert "query=" in url


# =============================================================================
# Group 4: LLM Extraction (JSON Parsing)
# =============================================================================

class TestLLMExtraction:
    """JSON extraction from LLM responses."""

    def test_extract_clean_json_array(self):
        from app.engine.search_platforms.adapters.browser_base import _extract_json_array
        result = _extract_json_array('[{"title": "Test"}]')
        assert len(result) == 1
        assert result[0]["title"] == "Test"

    def test_extract_fenced_json(self):
        from app.engine.search_platforms.adapters.browser_base import _extract_json_array
        result = _extract_json_array(_FENCED_RESPONSE)
        assert len(result) == 1
        assert result[0]["title"] == "Test Product"

    def test_extract_empty_response(self):
        from app.engine.search_platforms.adapters.browser_base import _extract_json_array
        assert _extract_json_array("") == []
        assert _extract_json_array("No products found.") == []

    def test_extract_malformed_json(self):
        from app.engine.search_platforms.adapters.browser_base import _extract_json_array
        result = _extract_json_array("[{broken json")
        assert result == []

    def test_extract_empty_array(self):
        from app.engine.search_platforms.adapters.browser_base import _extract_json_array
        result = _extract_json_array("[]")
        assert result == []

    def test_vnd_price_parsing(self):
        from app.engine.search_platforms.adapters.browser_base import _parse_vnd_price
        assert _parse_vnd_price("29.990.000 d") == 29990000.0
        assert _parse_vnd_price("1.234.567") == 1234567.0
        assert _parse_vnd_price("") is None
        assert _parse_vnd_price("50") is None  # Below 100 threshold


# =============================================================================
# Group 5: Facebook Adapter Config
# =============================================================================

class TestFacebookConfig:
    """Facebook adapter config should be correct."""

    def test_platform_id(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        assert adapter.get_config().id == "facebook_search"

    def test_display_name(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        assert adapter.get_config().display_name == "Facebook"

    def test_backend_type_browser(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import BackendType
        adapter = FacebookSearchAdapter()
        assert adapter.get_config().backend == BackendType.BROWSER

    def test_tool_name(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        assert adapter.get_tool_name() == "tool_search_facebook_search"


# =============================================================================
# Group 6: Fallback Behavior
# =============================================================================

class TestFallbackBehavior:
    """Facebook adapter should fall back to Serper when Playwright unavailable."""

    def test_fallback_on_playwright_import_error(self):
        """When playwright not installed, should use serper fallback."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        mock_fallback = MagicMock()
        mock_fallback.search_sync.return_value = [
            ProductSearchResult(platform="Facebook Marketplace", title="Test FB", price="1.000.000 d")
        ]

        adapter = FacebookSearchAdapter(serper_fallback=mock_fallback)

        # Sprint 155: search_sync now calls _run_fetch_with_scroll directly.
        # Simulate Playwright unavailable via ImportError from the import check.
        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            results = adapter.search_sync("test query")

        mock_fallback.search_sync.assert_called_once_with("test query", 20, 1)
        assert len(results) == 1
        assert results[0].title == "Test FB"

    def test_fallback_on_browser_error(self):
        """When browser fails, should use serper fallback."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        mock_fallback = MagicMock()
        mock_fallback.search_sync.return_value = [
            ProductSearchResult(platform="Facebook Marketplace", title="Fallback Result")
        ]

        adapter = FacebookSearchAdapter(serper_fallback=mock_fallback)

        # Sprint 155: simulate browser failure via _run_fetch_with_scroll
        with patch.dict("sys.modules", {"playwright.sync_api": MagicMock()}):
            with patch.object(
                adapter, "_run_fetch_with_scroll",
                side_effect=RuntimeError("Browser crashed"),
            ):
                results = adapter.search_sync("test query")

        assert len(results) == 1
        assert results[0].title == "Fallback Result"

    def test_no_fallback_returns_empty(self):
        """When no fallback and Playwright fails, return empty list."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter(serper_fallback=None)

        # Sprint 155: simulate Playwright import failure
        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            results = adapter.search_sync("test query")

        assert results == []

    def test_empty_query_returns_empty(self):
        """Empty query should return empty list without calling anything."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        assert adapter.search_sync("") == []
        assert adapter.search_sync("   ") == []


# =============================================================================
# Group 7: Browser Base Class
# =============================================================================

class TestBrowserBase:
    """PlaywrightLLMAdapter base class behavior."""

    def test_page_text_truncation(self):
        """Page text should be truncated to 50KB."""
        from app.engine.search_platforms.adapters.browser_base import _MAX_PAGE_TEXT
        assert _MAX_PAGE_TEXT == 50000

    def test_prompt_text_limit(self):
        """LLM prompt text should be limited to 30KB."""
        from app.engine.search_platforms.adapters.browser_base import _MAX_PROMPT_TEXT
        assert _MAX_PROMPT_TEXT == 30000

    def test_map_to_result_fields(self):
        """_map_to_result should correctly map LLM output dict."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        item = {
            "title": "iPhone Test",
            "price": "10.000.000 d",
            "seller": "Shop ABC",
            "link": "https://fb.com/item/1",
            "location": "Ha Noi",
        }
        result = adapter._map_to_result(item)
        assert result.platform == "Facebook"
        assert result.title == "iPhone Test"
        assert result.price == "10.000.000 d"
        assert result.extracted_price == 10000000.0
        assert result.seller == "Shop ABC"
        assert result.link == "https://fb.com/item/1"
        assert result.location == "Ha Noi"

    def test_map_to_result_missing_fields(self):
        """_map_to_result should handle missing fields gracefully."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        result = adapter._map_to_result({"title": "Minimal"})
        assert result.title == "Minimal"
        assert result.price == ""
        assert result.seller == ""


# =============================================================================
# Group 8: Registration
# =============================================================================

class TestRegistration:
    """Platform registration with browser scraping feature flag."""

    def test_browser_scraping_enabled_registers_facebook_search(self, mock_settings):
        """When enable_browser_scraping=True, should register facebook_search adapter."""
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()
            ids = registry.list_ids()

        assert "facebook_search" in ids
        assert "facebook_marketplace" not in ids

    def test_browser_scraping_disabled_registers_serper(self, mock_settings_no_browser):
        """When enable_browser_scraping=False, should register facebook_marketplace (Serper)."""
        with patch("app.core.config.get_settings", return_value=mock_settings_no_browser):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()
            ids = registry.list_ids()

        assert "facebook_marketplace" in ids
        assert "facebook_search" not in ids

    def test_tool_auto_generated_for_facebook_search(self, mock_settings):
        """Tool should be auto-generated with correct name."""
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()

        adapter = registry.get("facebook_search")
        assert adapter is not None
        assert adapter.get_tool_name() == "tool_search_facebook_search"


# =============================================================================
# Group 9: Extraction Prompt Template
# =============================================================================

class TestExtractionPrompt:
    """LLM extraction prompt template validation."""

    def test_prompt_has_text_placeholder(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        prompt = FacebookSearchAdapter()._get_extraction_prompt()
        assert "{text}" in prompt

    def test_prompt_has_max_results_placeholder(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        prompt = FacebookSearchAdapter()._get_extraction_prompt()
        assert "{max_results}" in prompt

    def test_prompt_mentions_json_array(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        prompt = FacebookSearchAdapter()._get_extraction_prompt()
        assert "JSON" in prompt


# =============================================================================
# Group 10: LLM Extract Integration (mocked LLM)
# =============================================================================

class TestLLMExtractIntegration:
    """Test _llm_extract with mocked LLM."""

    def test_llm_extract_returns_products(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()

        mock_response = MagicMock()
        mock_response.content = _SAMPLE_LLM_RESPONSE

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            results = adapter._llm_extract("Some page text with products", 20)

        assert len(results) == 2
        assert results[0].title == "iPhone 16 Pro Max 256GB"
        assert results[0].price == "29.990.000 d"
        assert results[0].extracted_price == 29990000.0
        assert results[0].platform == "Facebook"
        assert results[1].seller == "Shop Dien Thoai XYZ"

    def test_llm_extract_empty_page(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()

        mock_response = MagicMock()
        mock_response.content = "[]"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            results = adapter._llm_extract("Login to Facebook", 20)

        assert results == []

    def test_llm_extract_respects_max_results(self):
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()

        # LLM returns 5 products but we ask for max 2
        many_products = json.dumps([{"title": f"Product {i}", "price": "1.000.000 d"} for i in range(5)])
        mock_response = MagicMock()
        mock_response.content = many_products

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response

        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            results = adapter._llm_extract("page text", 2)

        assert len(results) == 2


# =============================================================================
# Group 11: Tool Ack in Product Search Node
# =============================================================================

class TestToolAck:
    """Product search node should have tool ack for facebook_search."""

    def test_facebook_search_tool_ack_exists(self):
        from app.engine.multi_agent.agents.product_search_node import _PRODUCT_RESULT_TOOLS
        assert "tool_search_facebook_search" in _PRODUCT_RESULT_TOOLS

    def test_facebook_marketplace_tool_ack_still_exists(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_facebook_marketplace" in _SYSTEM_PROMPT


# =============================================================================
# Group 12: Regression — Sprint 149-151 Platforms Unbroken
# =============================================================================

class TestRegression:
    """Existing platforms should still be registered correctly."""

    def test_all_standard_platforms_registered(self, mock_settings_no_browser):
        """When browser scraping disabled, all standard platforms registered."""
        with patch("app.core.config.get_settings", return_value=mock_settings_no_browser):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()

        ids = set(registry.list_ids())
        expected = {"google_shopping", "shopee", "tiktok_shop", "lazada",
                    "facebook_marketplace", "all_web", "instagram", "websosanh"}
        assert expected == ids

    def test_websosanh_still_works(self, mock_settings_no_browser):
        """WebSosanh adapter should still be registered (Sprint 151)."""
        with patch("app.core.config.get_settings", return_value=mock_settings_no_browser):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()

        ws = registry.get("websosanh")
        assert ws is not None
        assert ws.get_config().display_name == "WebSosanh.vn"

    def test_browser_enabled_keeps_other_platforms(self, mock_settings):
        """Browser scraping enabled should not affect other platform registrations."""
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.search_platforms import init_search_platforms
            registry = init_search_platforms()

        ids = set(registry.list_ids())
        # facebook_marketplace replaced by facebook_search
        assert "google_shopping" in ids
        assert "shopee" in ids
        assert "websosanh" in ids
        assert "facebook_search" in ids

    def test_default_platform_list_includes_facebook_marketplace(self):
        """Default config should include facebook_marketplace in platform list."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert "facebook_marketplace" in s.product_search_platforms


# =============================================================================
# Group 13: close_browser cleanup
# =============================================================================

class TestBrowserCleanup:
    """Browser cleanup function should be safe to call."""

    def test_close_browser_no_error_when_none(self):
        """close_browser should not error when no browser is open."""
        from app.engine.search_platforms.adapters.browser_base import close_browser
        close_browser()  # Should not raise

    def test_close_browser_closes_mock_browser(self):
        """close_browser should close existing browser."""
        import app.engine.search_platforms.adapters.browser_base as bb

        mock_browser = MagicMock()
        mock_pw = MagicMock()
        bb._browser = mock_browser
        bb._playwright_instance = mock_pw

        bb.close_browser()

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert bb._browser is None
        assert bb._playwright_instance is None
