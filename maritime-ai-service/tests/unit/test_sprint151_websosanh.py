"""
Tests for Sprint 151: "So Sanh Gia" — WebSosanh.vn Price Aggregator Adapter

Covers:
- PlatformConfig fields (id, backend, display_name)
- URL building (spaces, Vietnamese chars, special chars, pagination, empty)
- HTML parsing (product items, price/title/seller/link extraction, missing fields)
- VND price parsing (dots, commas, currency symbols, out-of-range)
- Pagination (page=1 default, page=2+)
- Error handling (404, timeout, connection error, non-HTML)
- Registration (in registry, auto-tool generated, tool name)
- Regression (Sprint 149/150 tests unbroken, default platform list updated)
"""

import json
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


@pytest.fixture
def mock_settings():
    """Settings with product search and websosanh enabled."""
    s = MagicMock()
    s.enable_product_search = True
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
    s.enable_browser_scraping = False
    s.product_search_platforms = [
        "google_shopping", "shopee", "tiktok_shop",
        "lazada", "facebook_marketplace", "all_web",
        "instagram", "websosanh",
    ]
    return s


# Sample WebSosanh HTML — matches live structure (verified Feb 2026)
_SAMPLE_HTML = """
<html>
<body>
<div class="product-single-info">
  <h2 class="product-single-name">
    <a href="/macbook-pro-m4-14-16gb512gb/1234/5678/direct.htm" rel="nofollow" target="_blank">MacBook Pro M4 14 inch 16GB/512GB</a>
  </h2>
  <div class="product-single-price-box">
    <span class="product-single-price">35.490.000 &#x111;</span>
  </div>
  <div class="product-single-merchant direct">
    <div class="merchant-name">bvtmobile.com</div>
  </div>
</div>
<div class="product-single-info">
  <h2 class="product-single-name">
    <a href="/macbook-pro-m4-pro/9999/1111/direct.htm" rel="nofollow" target="_blank">MacBook Pro M4 Pro 24GB 512GB</a>
  </h2>
  <div class="product-single-price-box">
    <span class="product-single-price">44.790.000 &#x111;</span>
  </div>
  <div class="product-single-merchant direct">
    <div class="merchant-name">cellphones.com.vn</div>
  </div>
</div>
<div class="product-single-info">
  <h2 class="product-single-name">
    <a href="/macbook-pro-m4-max/2222/3333/direct.htm" rel="nofollow" target="_blank">MacBook Pro M4 Max 36GB</a>
  </h2>
  <div class="product-single-price-box">
    <span class="product-single-price">69.990.000 &#x111;</span>
  </div>
  <div class="product-single-merchant direct">
    <div class="merchant-name">fptshop.com.vn</div>
  </div>
</div>
</body>
</html>
"""

_SAMPLE_HTML_MISSING_FIELDS = """
<html>
<body>
<div class="product-single-info">
  <h2 class="product-single-name">
    <a href="/product/123/456/direct.htm">Product With No Price</a>
  </h2>
  <div class="product-single-merchant direct">
    <div class="merchant-name">someshop.vn</div>
  </div>
</div>
<div class="product-single-info">
  <div class="product-single-price-box">
    <span class="product-single-price">10.000 &#x111;</span>
  </div>
</div>
</body>
</html>
"""

_EMPTY_HTML = """
<html><body><div class="no-results">Khong tim thay san pham nao</div></body></html>
"""

_MALFORMED_HTML = """
<html><body>
<div class="product-single-info">
  <h2 class="product-single-name"><a>No href here</a></h2>
  <div class="product-single-price-box">
    <span class="product-single-price">abc invalid price</span>
  </div>
</div>
</body></html>
"""


# =============================================================================
# 1. PlatformConfig (3 tests)
# =============================================================================


class TestWebSosanhConfig:
    def test_config_id(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        config = adapter.get_config()
        assert config.id == "websosanh"

    def test_config_backend_type(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        from app.engine.search_platforms.base import BackendType
        adapter = WebSosanhAdapter()
        assert adapter.get_config().backend == BackendType.CUSTOM

    def test_config_display_name_and_tool(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        config = adapter.get_config()
        assert config.display_name == "WebSosanh.vn"
        assert adapter.get_tool_name() == "tool_search_websosanh"
        assert config.max_results_default == 20
        assert config.tool_description_vi  # non-empty


# =============================================================================
# 2. URL Building (4 tests)
# =============================================================================


class TestURLBuilding:
    def test_simple_query(self):
        from app.engine.search_platforms.adapters.websosanh import _build_search_url
        url = _build_search_url("MacBook Pro M4")
        assert url == "https://websosanh.vn/s/MacBook+Pro+M4.htm"

    def test_vietnamese_chars(self):
        from app.engine.search_platforms.adapters.websosanh import _build_search_url
        url = _build_search_url("dien thoai Samsung")
        assert "dien+thoai+Samsung" in url
        assert url.endswith(".htm")

    def test_special_chars(self):
        from app.engine.search_platforms.adapters.websosanh import _build_search_url
        url = _build_search_url("cable 2.5mm²")
        assert ".htm" in url
        assert "page" not in url

    def test_pagination_page2(self):
        from app.engine.search_platforms.adapters.websosanh import _build_search_url
        url = _build_search_url("test query", page=2)
        assert url.endswith("?page=2")

    def test_pagination_page1_no_param(self):
        from app.engine.search_platforms.adapters.websosanh import _build_search_url
        url = _build_search_url("test query", page=1)
        assert "?page=" not in url


# =============================================================================
# 3. HTML Parsing (10 tests)
# =============================================================================


class TestHTMLParsing:
    def test_parse_standard_items(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert len(results) == 3

    def test_extract_title(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert results[0].title == "MacBook Pro M4 14 inch 16GB/512GB"

    def test_extract_price(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        # Price text preserved as-is from HTML
        assert "35.490.000" in results[0].price

    def test_extract_price_value(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert results[0].extracted_price == 35490000.0
        assert results[1].extracted_price == 44790000.0

    def test_extract_seller(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert results[0].seller == "bvtmobile.com"
        assert results[1].seller == "cellphones.com.vn"

    def test_extract_link_absolute(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert results[0].link.startswith("https://websosanh.vn/")
        assert "/direct.htm" in results[0].link

    def test_platform_name(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 20)
        assert all(r.platform == "WebSosanh.vn" for r in results)

    def test_max_results_respected(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML, 2)
        assert len(results) == 2

    def test_missing_fields_handled(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_SAMPLE_HTML_MISSING_FIELDS, 20)
        # First item has title but no price, second has price but no title/link
        assert len(results) >= 1
        # The item with only title (no price) should still be included
        has_title_only = any(r.title and not r.extracted_price for r in results)
        assert has_title_only

    def test_empty_results(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_EMPTY_HTML, 20)
        assert results == []

    def test_malformed_html(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        adapter = WebSosanhAdapter()
        results = adapter._parse_html(_MALFORMED_HTML, 20)
        # Should not crash — item has no href, invalid price
        assert len(results) >= 0  # graceful handling


# =============================================================================
# 4. VND Price Parsing (4 tests)
# =============================================================================


class TestVNDPriceParsing:
    def test_price_with_dots(self):
        from app.engine.search_platforms.adapters.websosanh import _parse_vnd_price
        assert _parse_vnd_price("35.490.000") == 35490000.0

    def test_price_with_commas(self):
        from app.engine.search_platforms.adapters.websosanh import _parse_vnd_price
        assert _parse_vnd_price("35,490,000") == 35490000.0

    def test_price_with_currency_symbol(self):
        from app.engine.search_platforms.adapters.websosanh import _parse_vnd_price
        assert _parse_vnd_price("44.790.000 d") == 44790000.0

    def test_price_out_of_range(self):
        from app.engine.search_platforms.adapters.websosanh import _parse_vnd_price
        assert _parse_vnd_price("50") is None  # too small
        assert _parse_vnd_price("") is None
        assert _parse_vnd_price("abc") is None


# =============================================================================
# 5. Pagination via search_sync (3 tests)
# =============================================================================


class TestPagination:
    def test_page1_default(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter

        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_HTML
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client_cls.return_value = mock_client
                # Use httpx.get directly (not Client context)
                with patch("httpx.get", return_value=mock_resp) as mock_get:
                    adapter = WebSosanhAdapter()
                    results = adapter.search_sync("MacBook", page=1)
                    url_called = mock_get.call_args[0][0]
                    assert "?page=" not in url_called

    def test_page2_url(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter

        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_HTML
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", return_value=mock_resp) as mock_get:
                adapter = WebSosanhAdapter()
                results = adapter.search_sync("MacBook", page=2)
                url_called = mock_get.call_args[0][0]
                assert "?page=2" in url_called

    def test_page3_url(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter

        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_HTML
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", return_value=mock_resp) as mock_get:
                adapter = WebSosanhAdapter()
                adapter.search_sync("MacBook", page=3)
                url_called = mock_get.call_args[0][0]
                assert "?page=3" in url_called


# =============================================================================
# 6. Error Handling (4 tests)
# =============================================================================


class TestErrorHandling:
    def test_404_returns_empty(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", return_value=mock_resp):
                adapter = WebSosanhAdapter()
                results = adapter.search_sync("nonexistent product")
                assert results == []

    def test_timeout_returns_empty(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        import httpx

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
                adapter = WebSosanhAdapter()
                results = adapter.search_sync("slow query")
                assert results == []

    def test_connection_error_returns_empty(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        import httpx

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
                adapter = WebSosanhAdapter()
                results = adapter.search_sync("offline query")
                assert results == []

    def test_non_html_returns_empty(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.get", return_value=mock_resp):
                adapter = WebSosanhAdapter()
                results = adapter.search_sync("json response")
                assert results == []

    def test_empty_query_returns_empty(self, mock_settings):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter

        with patch("app.core.config.get_settings", return_value=mock_settings):
            adapter = WebSosanhAdapter()
            results = adapter.search_sync("")
            assert results == []
            results2 = adapter.search_sync("   ")
            assert results2 == []


# =============================================================================
# 7. Registration & Tool Generation (3 tests)
# =============================================================================


class TestRegistration:
    def test_registered_in_registry(self, mock_settings):
        from app.engine.search_platforms import init_search_platforms

        with patch("app.core.config.get_settings", return_value=mock_settings):
            registry = init_search_platforms()

        assert "websosanh" in registry.list_ids()

    def test_auto_tool_generated(self, mock_settings):
        from app.engine.search_platforms import init_search_platforms
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
        from app.engine.tools.product_search_tools import _build_platform_tool

        with patch("app.core.config.get_settings", return_value=mock_settings):
            registry = init_search_platforms()

        adapter = registry.get("websosanh")
        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(adapter, cb)
        assert tool.name == "tool_search_websosanh"

    def test_tool_output_format(self, mock_settings):
        """Tool output is JSON with platform, results, count keys."""
        from app.engine.search_platforms import init_search_platforms
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
        from app.engine.tools.product_search_tools import _build_platform_tool

        with patch("app.core.config.get_settings", return_value=mock_settings):
            registry = init_search_platforms()

        adapter = registry.get("websosanh")
        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(adapter, cb)

        # Mock adapter search
        with patch.object(adapter, "search_sync", return_value=[]):
            result = tool.invoke({"query": "test", "max_results": 5})
            data = json.loads(result)
            assert "platform" in data
            assert "results" in data
            assert "count" in data
            assert data["platform"] == "WebSosanh.vn"


# =============================================================================
# 8. Regression (4 tests)
# =============================================================================


class TestRegression:
    def test_default_platform_list_includes_websosanh(self):
        """Config default includes websosanh."""
        from app.core.config import Settings
        defaults = Settings.model_fields["product_search_platforms"].default
        assert "websosanh" in defaults

    def test_existing_platforms_still_present(self):
        """All Sprint 149 platforms still in default list."""
        from app.core.config import Settings
        defaults = Settings.model_fields["product_search_platforms"].default
        for platform in ["google_shopping", "shopee", "tiktok_shop",
                         "lazada", "facebook_marketplace", "all_web", "instagram"]:
            assert platform in defaults

    def test_registry_count_with_websosanh(self, mock_settings):
        """Registry has 8 adapters with websosanh included."""
        from app.engine.search_platforms import init_search_platforms

        with patch("app.core.config.get_settings", return_value=mock_settings):
            registry = init_search_platforms()

        assert len(registry) == 8

    def test_websosanh_excluded_when_not_in_list(self, mock_settings):
        """WebSosanh not registered when removed from platform list."""
        mock_settings.product_search_platforms = ["google_shopping", "shopee"]

        from app.engine.search_platforms import init_search_platforms

        with patch("app.core.config.get_settings", return_value=mock_settings):
            registry = init_search_platforms()

        assert "websosanh" not in registry.list_ids()
        assert len(registry) == 2


# =============================================================================
# 9. to_dict output (2 tests)
# =============================================================================


class TestResultSerialization:
    def test_to_dict_minimal(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(
            platform="WebSosanh.vn",
            title="MacBook Pro",
            price="35.490.000 d",
            extracted_price=35490000.0,
            seller="bvtmobile.com",
            link="https://websosanh.vn/macbook/123/456/direct.htm",
        )
        d = r.to_dict()
        assert d["platform"] == "WebSosanh.vn"
        assert d["title"] == "MacBook Pro"
        assert d["seller"] == "bvtmobile.com"
        assert d["extracted_price"] == 35490000.0

    def test_to_dict_omits_empty(self):
        from app.engine.search_platforms.base import ProductSearchResult
        r = ProductSearchResult(platform="WebSosanh.vn", title="Test")
        d = r.to_dict()
        assert "seller" not in d
        assert "rating" not in d
        assert "image" not in d
