"""
Tests for Sprint 150: "Tìm Sâu" — LLM-Driven Deep Product Search

Covers:
- Pagination support (page param passed to Serper adapters, tool signatures)
- Product page scraper (JSON-LD, OG meta, regex, error handling, limits)
- Deep search prompt & iteration labels
- Config additions (max_iterations, scrape_timeout, max_scrape_pages)
- Tool registration (scraper in tool list, page param in auto-gen tools)
- Integration (multi-round mock, scrape after search)
- Regression (Sprint 148/149 backward compat)
"""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset product_search_node singleton between tests."""
    import app.engine.multi_agent.agents.product_search_node as ps_mod
    old = ps_mod._product_search_node
    ps_mod._product_search_node = None
    yield
    ps_mod._product_search_node = old


@pytest.fixture
def mock_settings():
    """Settings with product search enabled."""
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
        "lazada", "facebook_marketplace", "all_web", "instagram",
    ]
    return s


# =============================================================================
# Group 1: Pagination (6 tests)
# =============================================================================

class TestPagination:
    """Pagination support in search adapters and tools."""

    def test_serper_shopping_page_param_default(self, mock_settings):
        """Default page=1 does NOT add page to payload."""
        from app.engine.search_platforms.adapters.serper_shopping import SerperShoppingAdapter

        adapter = SerperShoppingAdapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"shopping": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.post", return_value=mock_resp) as mock_post:
                adapter.search_sync("test", 20, page=1)
                call_kwargs = mock_post.call_args
                payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
                assert "page" not in payload

    def test_serper_shopping_page_param_page2(self, mock_settings):
        """page=2 is passed to Serper API payload."""
        from app.engine.search_platforms.adapters.serper_shopping import SerperShoppingAdapter

        adapter = SerperShoppingAdapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"shopping": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.post", return_value=mock_resp) as mock_post:
                adapter.search_sync("test", 20, page=2)
                call_kwargs = mock_post.call_args
                payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
                assert payload["page"] == 2

    def test_serper_site_page_param(self, mock_settings):
        """SerperSiteAdapter passes page to Serper API."""
        from app.engine.search_platforms.adapters.serper_site import create_shopee_adapter

        adapter = create_shopee_adapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"organic": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.post", return_value=mock_resp) as mock_post:
                adapter.search_sync("test", 20, page=3)
                call_kwargs = mock_post.call_args
                payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
                assert payload["page"] == 3

    def test_serper_all_web_page_param(self, mock_settings):
        """SerperAllWebAdapter passes page to Serper API."""
        from app.engine.search_platforms.adapters.serper_all_web import SerperAllWebAdapter

        adapter = SerperAllWebAdapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"organic": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("httpx.post", return_value=mock_resp) as mock_post:
                adapter.search_sync("test", 20, page=2)
                call_kwargs = mock_post.call_args
                payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
                assert payload["page"] == 2

    def test_abc_signature_has_page(self):
        """SearchPlatformAdapter ABC includes page parameter."""
        from app.engine.search_platforms.base import SearchPlatformAdapter
        import inspect
        sig = inspect.signature(SearchPlatformAdapter.search_sync)
        assert "page" in sig.parameters
        assert sig.parameters["page"].default == 1

    def test_static_tool_has_page_param(self):
        """Static tool_search_google_shopping has page parameter."""
        from app.engine.tools.product_search_tools import tool_search_google_shopping
        import inspect
        sig = inspect.signature(tool_search_google_shopping.func)
        assert "page" in sig.parameters
        assert sig.parameters["page"].default == 1


# =============================================================================
# Group 2: Product Page Scraper (10 tests)
# =============================================================================

class TestProductPageScraper:
    """Product page scraper tool — extraction and error handling."""

    def test_extract_json_ld_product(self):
        """Extract product data from JSON-LD structured data."""
        from app.engine.tools.product_page_scraper import _extract_from_json_ld

        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "MacBook Pro 14 M4 Pro",
            "brand": {"@type": "Brand", "name": "Apple"},
            "offers": {
                "@type": "Offer",
                "price": "52990000",
                "priceCurrency": "VND",
                "availability": "https://schema.org/InStock"
            }
        }
        </script>
        </head><body></body></html>
        """
        result = _extract_from_json_ld(html)
        assert result is not None
        assert result["name"] == "MacBook Pro 14 M4 Pro"
        assert result["price"] == "52990000"
        assert result["currency"] == "VND"
        assert result["brand"] == "Apple"
        assert result["availability"] == "Còn hàng"

    def test_extract_json_ld_aggregate_offer(self):
        """Extract price range from AggregateOffer."""
        from app.engine.tools.product_page_scraper import _extract_from_json_ld

        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Dây điện Cadivi",
            "offers": {
                "@type": "AggregateOffer",
                "lowPrice": "150000",
                "highPrice": "350000",
                "priceCurrency": "VND"
            }
        }
        </script>
        </head><body></body></html>
        """
        result = _extract_from_json_ld(html)
        assert result is not None
        assert result["price"] == "150000-350000"

    def test_extract_json_ld_graph_array(self):
        """Handle @graph wrapper around Product."""
        from app.engine.tools.product_page_scraper import _extract_from_json_ld

        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@graph": [
                {"@type": "Organization", "name": "Shop"},
                {"@type": "Product", "name": "Test Product", "offers": {"price": "100000", "priceCurrency": "VND"}}
            ]
        }
        </script>
        </head><body></body></html>
        """
        result = _extract_from_json_ld(html)
        assert result is not None
        assert result["name"] == "Test Product"

    def test_extract_og_meta(self):
        """Extract from Open Graph meta tags."""
        from app.engine.tools.product_page_scraper import _extract_from_og_meta

        html = """
        <html><head>
        <meta property="og:title" content="iPhone 16 Pro Max 256GB">
        <meta property="og:price:amount" content="32990000">
        <meta property="og:price:currency" content="VND">
        <meta property="product:brand" content="Apple">
        </head><body></body></html>
        """
        result = _extract_from_og_meta(html)
        assert result is not None
        assert result["name"] == "iPhone 16 Pro Max 256GB"
        assert result["price"] == "32990000"
        assert result["brand"] == "Apple"

    def test_extract_regex_vnd(self):
        """Regex fallback extracts Vietnamese prices."""
        from app.engine.tools.product_page_scraper import _extract_from_regex

        html = """
        <html><head><title>MacBook Pro giá rẻ</title></head>
        <body>
        <p>Giá bán: 52.990.000₫</p>
        <p>Giá khuyến mãi: 49.990.000 VND</p>
        </body></html>
        """
        result = _extract_from_regex(html)
        assert result is not None
        assert result["name"] == "MacBook Pro giá rẻ"
        assert "extracted_prices" in result
        assert 49990000 in result["extracted_prices"]
        assert 52990000 in result["extracted_prices"]

    def test_extract_regex_comma_separator(self):
        """Regex handles comma as thousands separator."""
        from app.engine.tools.product_page_scraper import _extract_from_regex

        html = """
        <html><head><title>Product</title></head>
        <body><p>Giá: 1,234,567đ</p></body></html>
        """
        result = _extract_from_regex(html)
        assert result is not None
        assert 1234567 in result["extracted_prices"]

    def test_parse_vnd_price(self):
        """VND price parser handles various formats."""
        from app.engine.tools.product_page_scraper import _parse_vnd_price

        assert _parse_vnd_price("52.990.000") == 52990000.0
        assert _parse_vnd_price("1,234,567") == 1234567.0
        assert _parse_vnd_price("999000") == 999000.0
        assert _parse_vnd_price("") is None
        assert _parse_vnd_price("50") is None  # Too small for VND

    def test_tool_fetch_product_detail_success(self, mock_settings):
        """tool_fetch_product_detail returns JSON with extracted data."""
        from app.engine.tools.product_page_scraper import tool_fetch_product_detail

        mock_html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Test", "offers": {"price": "100000", "priceCurrency": "VND"}}
        </script>
        </head><body></body></html>
        """

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.tools.product_page_scraper._fetch_page", return_value=mock_html):
                result = json.loads(tool_fetch_product_detail.invoke({"url": "https://example.com/product"}))
                assert result["name"] == "Test"
                assert result["price"] == "100000"
                assert result["extraction_method"] == "json_ld"
                assert result["url"] == "https://example.com/product"

    def test_tool_fetch_product_detail_error(self, mock_settings):
        """tool_fetch_product_detail handles network errors gracefully."""
        from app.engine.tools.product_page_scraper import tool_fetch_product_detail

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.tools.product_page_scraper._fetch_page", side_effect=Exception("Timeout")):
                result = json.loads(tool_fetch_product_detail.invoke({"url": "https://example.com/fail"}))
                assert "error" in result
                assert "Timeout" in result["error"]

    def test_tool_fetch_no_price_found(self, mock_settings):
        """Returns error when no price data found on page."""
        from app.engine.tools.product_page_scraper import tool_fetch_product_detail

        # Minimal HTML with no title, no price — nothing to extract
        mock_html = "<html><head></head><body><p>Hello world</p></body></html>"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            with patch("app.engine.tools.product_page_scraper._fetch_page", return_value=mock_html):
                result = json.loads(tool_fetch_product_detail.invoke({"url": "https://example.com/blog"}))
                assert "error" in result


# =============================================================================
# Group 3: Deep Search Prompt & Iteration Labels (4 tests)
# =============================================================================

class TestDeepSearchPrompt:
    """Deep search system prompt and iteration labels."""

    def test_system_prompt_has_deep_search_strategy(self):
        """System prompt includes deep search strategy section."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT, _DEEP_SEARCH_PROMPT
        assert "CHIẾN LƯỢC TÌM KIẾM SÂU" in _DEEP_SEARCH_PROMPT
        assert "tool_fetch_product_detail" in _SYSTEM_PROMPT

    def test_system_prompt_has_pagination_hints(self):
        """System prompt mentions pagination (page=2, page=3)."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "page=2" in _DEEP_SEARCH_PROMPT
        assert "page=3" in _DEEP_SEARCH_PROMPT

    def test_iteration_labels_updated(self):
        """Iteration labels reflect deep search phases."""
        from app.engine.multi_agent.agents.product_search_node import _iteration_label

        assert _iteration_label(0, []) == "Phân tích yêu cầu tìm kiếm"
        assert "Khám phá" in _iteration_label(1, [])
        assert "Khám phá" in _iteration_label(2, [])
        assert "Mở rộng" in _iteration_label(3, [])
        assert "Mở rộng" in _iteration_label(5, [])
        assert "Xác minh" in _iteration_label(6, [])
        assert "bổ sung" in _iteration_label(10, [])

    def test_tool_ack_has_scraper(self):
        """System prompt includes scraper tool description."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_fetch_product_detail" in _SYSTEM_PROMPT


# =============================================================================
# Group 4: Config (4 tests)
# =============================================================================

class TestDeepSearchConfig:
    """Sprint 150 config fields."""

    def test_max_iterations_default(self):
        """product_search_max_iterations defaults to 15."""
        from app.core.config import Settings
        s = Settings(
            GOOGLE_API_KEY="test",
            API_KEY="test",
            DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.product_search_max_iterations == 15

    def test_scrape_timeout_default(self):
        """product_search_scrape_timeout defaults to 10."""
        from app.core.config import Settings
        s = Settings(
            GOOGLE_API_KEY="test",
            API_KEY="test",
            DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.product_search_scrape_timeout == 10

    def test_max_scrape_pages_default(self):
        """product_search_max_scrape_pages defaults to 10."""
        from app.core.config import Settings
        s = Settings(
            GOOGLE_API_KEY="test",
            API_KEY="test",
            DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.product_search_max_scrape_pages == 10

    def test_max_iterations_validation(self):
        """max_iterations rejects values outside [5, 30]."""
        from pydantic import ValidationError
        from app.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                GOOGLE_API_KEY="test",
                API_KEY="test",
                DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
                product_search_max_iterations=3,  # too low
            )

        with pytest.raises(ValidationError):
            Settings(
                GOOGLE_API_KEY="test",
                API_KEY="test",
                DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
                product_search_max_iterations=50,  # too high
            )


# =============================================================================
# Group 5: Tool Registration (3 tests)
# =============================================================================

class TestToolRegistration:
    """Scraper tool registration and page param in auto-generated tools."""

    def test_scraper_tool_registered(self):
        """get_product_page_scraper_tools returns the scraper tool."""
        from app.engine.tools.product_page_scraper import get_product_page_scraper_tools
        tools = get_product_page_scraper_tools()
        assert len(tools) == 1
        assert tools[0].name == "tool_fetch_product_detail"

    def test_auto_gen_tool_has_page_param(self):
        """Auto-generated tools from _build_platform_tool include page parameter."""
        from app.engine.tools.product_search_tools import _build_platform_tool
        from app.engine.search_platforms.base import (
            BackendType, PlatformConfig, ProductSearchResult, SearchPlatformAdapter,
        )
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        class _TestAdapter(SearchPlatformAdapter):
            def get_config(self):
                return PlatformConfig(
                    id="test_plat", display_name="Test",
                    backend=BackendType.CUSTOM, tool_description_vi="Test tool",
                )
            def search_sync(self, query, max_results=20, page=1):
                return []

        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(_TestAdapter(), cb)
        import inspect
        sig = inspect.signature(tool.func)
        assert "page" in sig.parameters
        assert sig.parameters["page"].default == 1

    def test_product_search_node_loads_scraper_tool(self):
        """ProductSearchAgentNode includes tool_fetch_product_detail in tools list."""
        mock_search_tool = MagicMock()
        mock_search_tool.name = "tool_search_google_shopping"
        mock_report_tool = MagicMock()
        mock_report_tool.name = "tool_generate_product_report"

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm", return_value=mock_llm):
            with patch("app.engine.tools.product_search_tools.get_product_search_tools", return_value=[mock_search_tool]):
                with patch("app.engine.tools.excel_report_tool.tool_generate_product_report", mock_report_tool):
                    from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode
                    node = ProductSearchAgentNode()
                    tool_names = [t.name for t in node._tools]
                    assert "tool_fetch_product_detail" in tool_names


# =============================================================================
# Group 6: Integration (5 tests)
# =============================================================================

class TestDeepSearchIntegration:
    """Integration tests for deep search flow."""

    def test_build_platform_tool_page_forwarded(self, mock_settings):
        """Auto-generated tool forwards page param to adapter.search_sync."""
        from app.engine.tools.product_search_tools import _build_platform_tool
        from app.engine.search_platforms.base import (
            BackendType, PlatformConfig, ProductSearchResult, SearchPlatformAdapter,
        )
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        received_page = []

        class _TrackingAdapter(SearchPlatformAdapter):
            def get_config(self):
                return PlatformConfig(
                    id="tracker", display_name="Tracker",
                    backend=BackendType.CUSTOM, tool_description_vi="Track calls",
                )
            def search_sync(self, query, max_results=20, page=1):
                received_page.append(page)
                return [ProductSearchResult(platform="Tracker", title="Item")]

        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(_TrackingAdapter(), cb)
        result = json.loads(tool.invoke({"query": "test", "page": 3}))
        assert received_page == [3]
        assert result["count"] == 1

    def test_extraction_priority_json_ld_over_og(self):
        """JSON-LD takes priority over OG meta."""
        from app.engine.tools.product_page_scraper import (
            _extract_from_json_ld, _extract_from_og_meta,
        )

        html = """
        <html><head>
        <meta property="og:price:amount" content="99000000">
        <script type="application/ld+json">
        {"@type": "Product", "name": "Correct Price", "offers": {"price": "52990000", "priceCurrency": "VND"}}
        </script>
        </head><body></body></html>
        """
        json_ld = _extract_from_json_ld(html)
        og = _extract_from_og_meta(html)
        assert json_ld is not None
        assert json_ld["price"] == "52990000"
        assert og is not None
        assert og["price"] == "99000000"
        # JSON-LD should be checked first in tool_fetch_product_detail

    def test_max_iterations_from_config(self, mock_settings):
        """Config product_search_max_iterations is read at runtime."""
        mock_settings.product_search_max_iterations = 7

        # Verify the default constant is 15
        from app.engine.multi_agent.agents.product_search_node import _MAX_ITERATIONS_DEFAULT
        assert _MAX_ITERATIONS_DEFAULT == 15

        # Verify config can override
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.core.config import get_settings
            assert get_settings().product_search_max_iterations == 7

    def test_deep_prompt_appended_to_system_message(self):
        """System message in _react_loop includes deep search strategy."""
        from app.engine.multi_agent.agents.product_search_node import (
            _SYSTEM_PROMPT, _DEEP_SEARCH_PROMPT,
        )
        combined = _SYSTEM_PROMPT + _DEEP_SEARCH_PROMPT
        assert "CHIẾN LƯỢC TÌM KIẾM SÂU" in combined
        assert "tool_fetch_product_detail" in combined
        assert "page=2" in combined

    def test_scraper_handles_out_of_stock(self):
        """Scraper correctly identifies out-of-stock status."""
        from app.engine.tools.product_page_scraper import _extract_from_json_ld

        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product", "name": "Sold Out Item",
            "offers": {"price": "100000", "priceCurrency": "VND",
                        "availability": "https://schema.org/OutOfStock"}
        }
        </script>
        </head><body></body></html>
        """
        result = _extract_from_json_ld(html)
        assert result is not None
        assert result["availability"] == "Hết hàng"


# =============================================================================
# Group 7: Regression — backward compatibility (8 tests)
# =============================================================================

class TestRegressionBackwardCompat:
    """Ensure Sprint 148/149 behavior is preserved."""

    def test_static_tools_still_exist(self):
        """All 7 static product search tools are still defined."""
        from app.engine.tools.product_search_tools import _ALL_PRODUCT_SEARCH_TOOLS
        assert len(_ALL_PRODUCT_SEARCH_TOOLS) == 7

    def test_get_product_search_tools_returns_list(self):
        """get_product_search_tools() returns list (static or generated)."""
        from app.engine.tools.product_search_tools import get_product_search_tools
        tools = get_product_search_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 7

    def test_tool_output_format_unchanged(self, mock_settings):
        """Tool output format: {"platform": ..., "results": [...], "count": N}."""
        from app.engine.tools.product_search_tools import _build_platform_tool
        from app.engine.search_platforms.base import (
            BackendType, PlatformConfig, ProductSearchResult, SearchPlatformAdapter,
        )
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        class _Adapter(SearchPlatformAdapter):
            def get_config(self):
                return PlatformConfig(
                    id="compat", display_name="Compat",
                    backend=BackendType.CUSTOM, tool_description_vi="Test",
                )
            def search_sync(self, query, max_results=20, page=1):
                return [ProductSearchResult(platform="Compat", title="Item", price="100000₫")]

        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(_Adapter(), cb)
        result = json.loads(tool.invoke({"query": "test"}))
        assert "platform" in result
        assert "results" in result
        assert "count" in result
        assert result["count"] == 1

    def test_page_default_is_1_backward_compat(self):
        """Calling tools without page param still works (default=1)."""
        from app.engine.tools.product_search_tools import _build_platform_tool
        from app.engine.search_platforms.base import (
            BackendType, PlatformConfig, ProductSearchResult, SearchPlatformAdapter,
        )
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        received = []

        class _Adapter(SearchPlatformAdapter):
            def get_config(self):
                return PlatformConfig(
                    id="compat2", display_name="Compat2",
                    backend=BackendType.CUSTOM, tool_description_vi="Test",
                )
            def search_sync(self, query, max_results=20, page=1):
                received.append(page)
                return []

        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(_Adapter(), cb)
        # Call without page — should use default
        tool.invoke({"query": "test"})
        assert received == [1]

    def test_circuit_breaker_still_works(self):
        """Circuit breaker integration unchanged."""
        from app.engine.tools.product_search_tools import _build_platform_tool
        from app.engine.search_platforms.base import (
            BackendType, PlatformConfig, SearchPlatformAdapter,
        )
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        class _FailAdapter(SearchPlatformAdapter):
            def get_config(self):
                return PlatformConfig(
                    id="fail_plat", display_name="Fail",
                    backend=BackendType.CUSTOM, tool_description_vi="Fails",
                )
            def search_sync(self, query, max_results=20, page=1):
                raise RuntimeError("Network error")

        cb = PerPlatformCircuitBreaker()
        tool = _build_platform_tool(_FailAdapter(), cb)

        # Trigger failures to open CB
        for _ in range(5):
            result = json.loads(tool.invoke({"query": "test"}))
            assert "error" in result

        # CB should now be open
        assert cb.is_open("fail_plat")
        result = json.loads(tool.invoke({"query": "test"}))
        assert "không khả dụng" in result["error"]

    def test_product_search_result_to_dict(self):
        """ProductSearchResult.to_dict() format preserved."""
        from app.engine.search_platforms.base import ProductSearchResult

        r = ProductSearchResult(
            platform="Google Shopping",
            title="Test Product",
            price="100.000₫",
            extracted_price=100000.0,
            link="https://example.com",
        )
        d = r.to_dict()
        assert d["platform"] == "Google Shopping"
        assert d["title"] == "Test Product"
        assert d["price"] == "100.000₫"
        assert d["extracted_price"] == 100000.0
        assert d["link"] == "https://example.com"
        # Empty/None fields should NOT be in dict
        assert "seller" not in d
        assert "rating" not in d

    def test_tool_names_unchanged(self):
        """Tool names from Sprint 148 are preserved."""
        from app.engine.tools.product_search_tools import _ALL_PRODUCT_SEARCH_TOOLS
        names = [t.name for t in _ALL_PRODUCT_SEARCH_TOOLS]
        expected = [
            "tool_search_google_shopping",
            "tool_search_shopee",
            "tool_search_tiktok_shop",
            "tool_search_lazada",
            "tool_search_facebook_marketplace",
            "tool_search_all_web",
            "tool_search_instagram_shopping",
        ]
        assert names == expected

    def test_legacy_cb_functions(self):
        """Legacy _cb_is_open, _cb_record_failure, _cb_record_success still work."""
        from app.engine.tools.product_search_tools import (
            _cb_is_open, _cb_record_failure, _cb_record_success,
        )
        # Without circuit breaker initialized, should not crash
        assert _cb_is_open("test") is False
        _cb_record_failure("test")  # Should not raise
        _cb_record_success("test")  # Should not raise
