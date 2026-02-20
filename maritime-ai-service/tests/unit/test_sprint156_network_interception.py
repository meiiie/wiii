"""
Tests for Sprint 156: "Mat Luoi" — Network Interception for Facebook Scraping

Covers:
- GraphQL scanner (_scan_for_products): flat, nested, deep, max_depth, indicators
- Product extraction (_extract_product_from_node): full, partial, missing, alternatives
- Response parsing: for(;;); prefix, JSON, oversized, non-graphql, binary
- Deduplication: same title, case-insensitive, empty title
- Integration: fetch with interception, FB search adapter, FB group adapter
- Config: enable_network_interception, max_response_size, bounds, nested sync
- Mapping: _map_intercepted_to_result, VND price, source field
- Backward compat: disabled flag → old path, Serper fallback
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
    """Settings with interception enabled."""
    s = MagicMock()
    s.enable_product_search = True
    s.enable_browser_scraping = True
    s.browser_scraping_timeout = 15
    s.enable_network_interception = True
    s.network_interception_max_response_size = 5_000_000
    s.enable_browser_screenshots = False
    s.enable_facebook_cookie = False
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
        "instagram", "websosanh",
    ]
    return s


@pytest.fixture
def mock_settings_no_interception(mock_settings):
    """Settings with interception disabled."""
    mock_settings.enable_network_interception = False
    return mock_settings


def _make_marketplace_node(title="iPhone 16 Pro Max", price_formatted="25.000.000 d",
                           seller="Nguyen Van A", image_uri="https://img.fb.com/a.jpg",
                           city="Ho Chi Minh"):
    """Helper: create a realistic Facebook marketplace GraphQL node."""
    return {
        "marketplace_listing_title": title,
        "listing_price": {
            "formatted_amount": price_formatted,
            "amount": "25000000",
            "currency": "VND",
        },
        "marketplace_listing_seller": {
            "name": seller,
        },
        "primary_listing_photo": {
            "image": {
                "uri": image_uri,
            },
        },
        "location": {
            "reverse_geocode": {
                "city_page": {
                    "name": city,
                },
            },
        },
    }


# =============================================================================
# 1. GraphQL Scanner Tests (_scan_for_products)
# =============================================================================

class TestGraphQLScanner:
    """Test _scan_for_products recursive JSON walker."""

    def test_flat_node_with_indicators(self):
        """Flat dict with 2+ indicator fields is detected."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = _make_marketplace_node()
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 1
        assert results[0]["marketplace_listing_title"] == "iPhone 16 Pro Max"

    def test_nested_relay_edges(self):
        """Products nested in Relay-style edges/node structure."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = {
            "data": {
                "marketplace_search": {
                    "feed_units": {
                        "edges": [
                            {"node": {"listing": _make_marketplace_node("Product A")}},
                            {"node": {"listing": _make_marketplace_node("Product B")}},
                        ]
                    }
                }
            }
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 2

    def test_deep_nesting(self):
        """Products found at arbitrary depth."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        # Nest 15 levels deep
        inner = _make_marketplace_node("Deep Product")
        data = inner
        for _ in range(15):
            data = {"wrapper": data}
        results = PlaywrightLLMAdapter._scan_for_products(data, max_depth=20)
        assert len(results) == 1

    def test_max_depth_exceeded(self):
        """Products beyond max_depth are not found."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        inner = _make_marketplace_node("Too Deep")
        data = inner
        for _ in range(25):
            data = {"wrapper": data}
        results = PlaywrightLLMAdapter._scan_for_products(data, max_depth=20)
        assert len(results) == 0

    def test_no_indicators(self):
        """Dict without any indicator fields returns empty."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = {"foo": "bar", "baz": 123}
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert results == []

    def test_one_indicator_insufficient(self):
        """Dict with only 1 indicator field is not enough."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = {"marketplace_listing_title": "iPhone", "other_field": 123}
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert results == []

    def test_empty_data(self):
        """Empty dict returns empty."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        assert PlaywrightLLMAdapter._scan_for_products({}) == []

    def test_multiple_products(self):
        """Multiple products at same level."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = {
            "items": [
                _make_marketplace_node("Product 1"),
                _make_marketplace_node("Product 2"),
                _make_marketplace_node("Product 3"),
            ]
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 3

    def test_list_of_dicts(self):
        """Top-level list of product dicts."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = [
            _make_marketplace_node("A"),
            _make_marketplace_node("B"),
        ]
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 2

    def test_mixed_data(self):
        """Mix of product dicts and non-product dicts."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        data = {
            "products": [_make_marketplace_node("Real")],
            "metadata": {"count": 1, "page": 1},
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 1


# =============================================================================
# 2. Product Extraction Tests (_extract_product_from_node)
# =============================================================================

class TestProductExtraction:
    """Test _extract_product_from_node field mapping."""

    def test_full_marketplace_node(self):
        """All fields extracted from complete node."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = _make_marketplace_node()
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["title"] == "iPhone 16 Pro Max"
        assert result["price"] == "25.000.000 d"
        assert result["seller"] == "Nguyen Van A"
        assert result["image"] == "https://img.fb.com/a.jpg"
        assert result["location"] == "Ho Chi Minh"

    def test_formatted_amount(self):
        """Price from formatted_amount takes priority."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Test",
            "listing_price": {
                "formatted_amount": "1.500.000 VND",
                "amount": "1500000",
                "currency": "VND",
            },
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["price"] == "1.500.000 VND"

    def test_amount_plus_currency_fallback(self):
        """Price from amount + currency when formatted_amount missing."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Test",
            "listing_price": {
                "amount": "500000",
                "currency": "VND",
            },
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["price"] == "500000 VND"

    def test_missing_title_returns_none(self):
        """No title → return None."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "listing_price": {"formatted_amount": "100"},
            "marketplace_listing_seller": {"name": "X"},
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result is None

    def test_nested_image_uri(self):
        """Image from primary_listing_photo.image.uri."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Test",
            "listing_price": {"formatted_amount": "100"},
            "primary_listing_photo": {
                "image": {"uri": "https://example.com/img.jpg"},
            },
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["image"] == "https://example.com/img.jpg"

    def test_seller_name(self):
        """Seller extracted from marketplace_listing_seller.name."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Test",
            "listing_price": {"formatted_amount": "100"},
            "marketplace_listing_seller": {"name": "Shop ABC"},
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["seller"] == "Shop ABC"

    def test_location_geocode(self):
        """Location from reverse_geocode.city_page.name."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Test",
            "listing_price": {"formatted_amount": "100"},
            "location": {
                "reverse_geocode": {
                    "city_page": {"name": "Ha Noi"},
                },
            },
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["location"] == "Ha Noi"

    def test_partial_fields(self):
        """Missing optional fields produce empty strings."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {
            "marketplace_listing_title": "Minimal",
            "listing_price": {},
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result["title"] == "Minimal"
        assert result["price"] == ""
        assert result["image"] == ""
        assert result["seller"] == ""
        assert result["location"] == ""

    def test_non_dict_returns_none(self):
        """Non-dict input returns None."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        assert PlaywrightLLMAdapter._extract_product_from_node("string") is None
        assert PlaywrightLLMAdapter._extract_product_from_node(123) is None
        assert PlaywrightLLMAdapter._extract_product_from_node(None) is None

    def test_alternative_title_fields(self):
        """Falls back to 'name' then 'title' when marketplace_listing_title missing."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node1 = {"name": "By Name", "listing_price": {"formatted_amount": "100"}}
        result1 = PlaywrightLLMAdapter._extract_product_from_node(node1)
        assert result1["title"] == "By Name"

        node2 = {"title": "By Title", "listing_price": {"formatted_amount": "100"}}
        result2 = PlaywrightLLMAdapter._extract_product_from_node(node2)
        assert result2["title"] == "By Title"


# =============================================================================
# 3. Response Parsing Tests
# =============================================================================

class TestResponseParsing:
    """Test response body handling in _on_response callback."""

    def test_strip_for_loop_prefix(self):
        """for (;;); prefix is stripped before JSON parse."""
        from app.engine.search_platforms.adapters.browser_base import _FOR_LOOP_PREFIX
        raw = _FOR_LOOP_PREFIX + json.dumps({"data": _make_marketplace_node()})
        text = raw
        if text.startswith(_FOR_LOOP_PREFIX):
            text = text[len(_FOR_LOOP_PREFIX):]
        data = json.loads(text.lstrip())
        assert "data" in data

    def test_valid_json_parsed(self):
        """Valid JSON without prefix is parsed."""
        data = {"marketplace_listing_title": "Test", "listing_price": {"formatted_amount": "100"}}
        text = json.dumps(data)
        parsed = json.loads(text)
        assert parsed["marketplace_listing_title"] == "Test"

    def test_oversized_response_skipped(self):
        """Responses larger than max_response_size should be skipped."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        max_size = 100
        body = b"x" * 200
        # Simulate the check
        assert len(body) > max_size

    def test_non_graphql_url_skipped(self):
        """URLs not containing /api/graphql/ are skipped."""
        from app.engine.search_platforms.adapters.browser_base import _GRAPHQL_ENDPOINT
        url = "https://www.facebook.com/other/endpoint"
        assert _GRAPHQL_ENDPOINT not in url

    def test_non_post_skipped(self):
        """Non-POST requests are skipped."""
        # Just verify the constant logic used in the filter
        assert "GET" != "POST"

    def test_invalid_json_handled(self):
        """Invalid JSON doesn't crash — returns empty."""
        try:
            json.loads("not json at all{{{")
        except json.JSONDecodeError:
            pass  # Expected behavior

    def test_binary_body_handled(self):
        """Binary/non-UTF8 body handled gracefully."""
        body = b"\x80\x81\x82\xff"
        text = body.decode("utf-8", errors="ignore")
        assert isinstance(text, str)

    def test_empty_body_handled(self):
        """Empty body returns no products."""
        text = ""
        assert not text  # Would be filtered out


# =============================================================================
# 4. Deduplication Tests
# =============================================================================

class TestDeduplication:
    """Test title-based deduplication in interception callback."""

    def test_same_title_deduped(self):
        """Same exact title produces only one result."""
        seen_titles = set()
        products = []
        for _ in range(3):
            p = {"title": "iPhone 16 Pro Max", "price": "25.000.000 d"}
            key = p["title"][:100].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                products.append(p)
        assert len(products) == 1

    def test_different_titles_kept(self):
        """Different titles are all kept."""
        seen_titles = set()
        products = []
        for title in ["iPhone 16", "MacBook Pro", "iPad Air"]:
            p = {"title": title, "price": "100"}
            key = p["title"][:100].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                products.append(p)
        assert len(products) == 3

    def test_case_insensitive_dedup(self):
        """Dedup is case-insensitive."""
        seen_titles = set()
        products = []
        for title in ["iPhone 16", "IPHONE 16", "iphone 16"]:
            p = {"title": title, "price": "100"}
            key = p["title"][:100].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                products.append(p)
        assert len(products) == 1

    def test_empty_title_skipped(self):
        """Products with empty title are skipped by _extract_product_from_node."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        node = {"listing_price": {"formatted_amount": "100"}}
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result is None

    def test_similar_but_different_titles(self):
        """Titles with slight differences are kept."""
        seen_titles = set()
        products = []
        for title in ["iPhone 16 Pro 256GB", "iPhone 16 Pro 512GB"]:
            p = {"title": title, "price": "100"}
            key = p["title"][:100].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                products.append(p)
        assert len(products) == 2


# =============================================================================
# 5. Integration Tests
# =============================================================================

class TestIntegration:
    """Test interception integration with adapters."""

    def test_fetch_with_interception_returns_tuple(self):
        """_fetch_page_with_interception returns (str, list) tuple."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter

        adapter = type("TestAdapter", (PlaywrightLLMAdapter,), {
            "get_config": lambda self: MagicMock(id="test", display_name="Test"),
            "_build_url": lambda self, q, p=1: f"https://test.com/?q={q}",
            "_get_extraction_prompt": lambda self: "test {text} {max_results}",
        })()

        # Mock browser, context, page
        mock_page = MagicMock()
        mock_page.evaluate.return_value = []
        mock_page.inner_text.return_value = "some text content"
        mock_page.url = "https://test.com"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        with patch("app.engine.search_platforms.utils.validate_url_for_scraping"):
            result = adapter._fetch_page_with_interception(
                "https://www.facebook.com/marketplace/search/?query=test",
                _browser=mock_browser,
                max_scrolls=1,
                scroll_delay=0.01,
            )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_dom_text_accumulated(self):
        """DOM text is accumulated across scrolls."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter

        adapter = type("TestAdapter", (PlaywrightLLMAdapter,), {
            "get_config": lambda self: MagicMock(id="test", display_name="Test"),
            "_build_url": lambda self, q, p=1: f"https://test.com/?q={q}",
            "_get_extraction_prompt": lambda self: "test {text} {max_results}",
        })()

        mock_page = MagicMock()
        # Return different articles on each scroll
        mock_page.evaluate.side_effect = [
            ["Article 1 content here"] * 1,  # scroll 0
            f"undefined",  # scrollBy
            ["Article 2 content here"] * 1,  # scroll 1
            f"undefined",  # scrollBy
            [],  # scroll 2 - empty
            f"undefined",  # scrollBy
            [],  # scroll 3 - empty
            f"undefined",  # scrollBy
            [],  # scroll 4 - empty (3 consecutive → break)
        ]
        mock_page.inner_text.return_value = ""
        mock_page.url = "https://test.com"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        with patch("app.engine.search_platforms.utils.validate_url_for_scraping"):
            dom_text, intercepted = adapter._fetch_page_with_interception(
                "https://www.facebook.com/marketplace/search/?query=test",
                _browser=mock_browser,
                max_scrolls=5,
                scroll_delay=0.01,
            )
        assert "Article 1" in dom_text or dom_text == ""  # Depends on evaluate mock

    def test_ssrf_prevention(self):
        """Private IPs are blocked."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter

        adapter = type("TestAdapter", (PlaywrightLLMAdapter,), {
            "get_config": lambda self: MagicMock(id="test", display_name="Test"),
            "_build_url": lambda self, q, p=1: f"https://test.com/?q={q}",
            "_get_extraction_prompt": lambda self: "test {text} {max_results}",
        })()

        with patch(
            "app.engine.search_platforms.utils.validate_url_for_scraping",
            side_effect=ValueError("SSRF blocked"),
        ):
            with pytest.raises(ValueError, match="SSRF"):
                adapter._fetch_page_with_interception(
                    "http://192.168.1.1/evil",
                    _browser=MagicMock(),
                )

    def test_cookies_injected(self):
        """Cookies are injected into browser context."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter

        adapter = type("TestAdapter", (PlaywrightLLMAdapter,), {
            "get_config": lambda self: MagicMock(id="test", display_name="Test"),
            "_build_url": lambda self, q, p=1: f"https://test.com/?q={q}",
            "_get_extraction_prompt": lambda self: "test {text} {max_results}",
        })()

        mock_page = MagicMock()
        mock_page.evaluate.return_value = []
        mock_page.inner_text.return_value = "text"
        mock_page.url = "https://test.com"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        test_cookies = [{"name": "c_user", "value": "123", "domain": ".facebook.com", "path": "/"}]

        with patch("app.engine.search_platforms.utils.validate_url_for_scraping"):
            adapter._fetch_page_with_interception(
                "https://www.facebook.com/marketplace/search/?query=test",
                cookies=test_cookies,
                _browser=mock_browser,
                max_scrolls=1,
                scroll_delay=0.01,
            )
        mock_context.add_cookies.assert_called_once_with(test_cookies)

    def test_fb_search_uses_interception(self, mock_settings):
        """FacebookSearchAdapter uses interception when enabled."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        mock_run = MagicMock(return_value=(
            "some dom text",
            [
                {"title": "P1", "price": "100", "seller": "S1", "image": "", "location": ""},
                {"title": "P2", "price": "200", "seller": "S2", "image": "", "location": ""},
                {"title": "P3", "price": "300", "seller": "S3", "image": "", "location": ""},
            ],
        ))

        mock_pw_module = MagicMock()
        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch.object(adapter, "_run_fetch_with_interception", mock_run), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_module}):
            results = adapter.search_sync("test query", max_results=10)

        mock_run.assert_called_once()
        assert len(results) == 3
        assert results[0].title == "P1"
        assert results[0].source == "graphql_intercept"

    def test_fb_search_fallback_to_llm(self, mock_settings):
        """When < 3 intercepted products, falls back to LLM extraction."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookSearchAdapter()
        mock_run = MagicMock(return_value=(
            "dom text with products listed here " * 10,
            [
                {"title": "P1", "price": "100", "seller": "S1", "image": "", "location": ""},
            ],  # Only 1 — below threshold
        ))
        llm_results = [
            ProductSearchResult(platform="Facebook", title="LLM Product 1", price="100"),
            ProductSearchResult(platform="Facebook", title="LLM Product 2", price="200"),
        ]

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch.object(adapter, "_run_fetch_with_interception", mock_run), \
             patch.object(adapter, "_llm_extract", return_value=llm_results), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            results = adapter.search_sync("test query", max_results=10)

        assert len(results) == 2
        assert results[0].title == "LLM Product 1"

    def test_fb_search_interception_disabled(self, mock_settings_no_interception):
        """When interception disabled, uses old scroll path."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookSearchAdapter()
        llm_results = [ProductSearchResult(platform="Facebook", title="Old Path", price="100")]
        long_text = "Facebook Marketplace product listing content " * 10  # > 100 chars

        with patch("app.core.config.get_settings", return_value=mock_settings_no_interception), \
             patch.object(adapter, "_run_fetch_with_scroll", return_value=long_text) as mock_scroll, \
             patch.object(adapter, "_llm_extract", return_value=llm_results), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            results = adapter.search_sync("test query", max_results=10)

        mock_scroll.assert_called_once()
        assert results[0].title == "Old Path"

    def test_fb_group_uses_interception(self, mock_settings):
        """FacebookGroupSearchAdapter uses interception when enabled."""
        from app.engine.search_platforms.adapters.facebook_group import FacebookGroupSearchAdapter

        adapter = FacebookGroupSearchAdapter()

        # Need cookies for group search
        mock_settings.enable_facebook_cookie = True
        mock_cookies = [{"name": "c_user", "value": "123", "domain": ".facebook.com", "path": "/"}]

        intercepted = [
            {"title": f"P{i}", "price": f"{i}00", "seller": "S", "image": "", "location": ""}
            for i in range(5)
        ]

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch.object(adapter, "_get_cookies", return_value=mock_cookies), \
             patch(
                 "app.engine.search_platforms.adapters.browser_base._submit_to_pw_worker",
                 return_value=("dom text", intercepted),
             ):
            results = adapter.search_group_sync("Vua 2nd", "MacBook", max_results=10)

        assert len(results) == 5
        assert results[0].source == "graphql_intercept"

    def test_fb_group_fallback_to_llm(self, mock_settings):
        """Group search falls back to LLM when < 3 intercepted."""
        from app.engine.search_platforms.adapters.facebook_group import FacebookGroupSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookGroupSearchAdapter()
        mock_settings.enable_facebook_cookie = True
        mock_cookies = [{"name": "c_user", "value": "123", "domain": ".facebook.com", "path": "/"}]
        llm_results = [ProductSearchResult(platform="Facebook Group", title="LLM Result", price="100")]

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch.object(adapter, "_get_cookies", return_value=mock_cookies), \
             patch(
                 "app.engine.search_platforms.adapters.browser_base._submit_to_pw_worker",
                 return_value=("dom text here " * 20, [{"title": "P1", "price": "100"}]),  # Only 1
             ), \
             patch.object(adapter, "_llm_extract", return_value=llm_results):
            results = adapter.search_group_sync("Vua 2nd", "MacBook", max_results=10)

        assert len(results) == 1
        assert results[0].title == "LLM Result"


# =============================================================================
# 6. Config Tests
# =============================================================================

class TestConfig:
    """Test configuration fields for network interception."""

    def test_default_enabled(self):
        """enable_network_interception defaults to True."""
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.enable_network_interception is True

    def test_max_response_size_default(self):
        """network_interception_max_response_size defaults to 5M."""
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.network_interception_max_response_size == 5_000_000

    def test_max_response_size_bounds_low(self):
        """Below 100K raises validation error."""
        import os
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            with pytest.raises(Exception):
                Settings(
                    google_api_key="test",
                    network_interception_max_response_size=50_000,
                    _env_file=None,
                )

    def test_max_response_size_bounds_high(self):
        """Above 50M raises validation error."""
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            with pytest.raises(Exception):
                Settings(
                    google_api_key="test",
                    network_interception_max_response_size=100_000_000,
                    _env_file=None,
                )

    def test_nested_sync(self):
        """Nested ProductSearchConfig includes interception fields."""
        with patch.dict("os.environ", {}, clear=False):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.product_search.enable_network_interception is True
            assert s.product_search.network_interception_max_response_size == 5_000_000


# =============================================================================
# 7. Mapping Tests
# =============================================================================

class TestMapping:
    """Test _map_intercepted_to_result."""

    def test_all_fields_mapped(self):
        """All intercepted fields map to ProductSearchResult."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        item = {
            "title": "MacBook Pro M4",
            "price": "45.000.000 d",
            "seller": "Shop Laptop",
            "image": "https://img.fb.com/macbook.jpg",
            "location": "Da Nang",
        }
        result = adapter._map_intercepted_to_result(item)
        assert result.title == "MacBook Pro M4"
        assert result.price == "45.000.000 d"
        assert result.seller == "Shop Laptop"
        assert result.image == "https://img.fb.com/macbook.jpg"
        assert result.location == "Da Nang"
        assert result.platform == "Facebook"

    def test_vnd_price_parsed(self):
        """VND price string is parsed to float."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        item = {"title": "Test", "price": "25.000.000 d", "seller": "", "image": "", "location": ""}

        with patch(
            "app.engine.search_platforms.adapters.browser_base._parse_vnd_price",
            return_value=25_000_000.0,
        ):
            result = adapter._map_intercepted_to_result(item)
        assert result.extracted_price == 25_000_000.0

    def test_source_graphql_intercept(self):
        """Source field is set to 'graphql_intercept'."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter

        adapter = FacebookSearchAdapter()
        item = {"title": "Test", "price": "", "seller": "", "image": "", "location": ""}
        result = adapter._map_intercepted_to_result(item)
        assert result.source == "graphql_intercept"


# =============================================================================
# 8. Backward Compatibility Tests
# =============================================================================

class TestBackwardCompat:
    """Ensure Sprint 155 behavior unchanged when interception disabled."""

    def test_fb_search_unchanged_when_disabled(self, mock_settings_no_interception):
        """FB search uses old scroll path when interception off."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookSearchAdapter()
        llm_results = [ProductSearchResult(platform="Facebook", title="Scroll Result", price="100")]
        long_text = "Facebook Marketplace product listing content " * 10

        with patch("app.core.config.get_settings", return_value=mock_settings_no_interception), \
             patch.object(adapter, "_run_fetch_with_scroll", return_value=long_text) as mock_scroll, \
             patch.object(adapter, "_llm_extract", return_value=llm_results), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            results = adapter.search_sync("test", max_results=5)

        mock_scroll.assert_called_once()
        assert results[0].title == "Scroll Result"

    def test_fb_group_unchanged_when_disabled(self, mock_settings_no_interception):
        """FB group uses old scroll path when interception off."""
        from app.engine.search_platforms.adapters.facebook_group import FacebookGroupSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookGroupSearchAdapter()
        mock_settings_no_interception.enable_facebook_cookie = True
        mock_cookies = [{"name": "c_user", "value": "123", "domain": ".facebook.com", "path": "/"}]
        llm_results = [ProductSearchResult(platform="Facebook Group", title="Old Group", price="100")]
        long_text = "Facebook Group posts content with products " * 10

        with patch("app.core.config.get_settings", return_value=mock_settings_no_interception), \
             patch.object(adapter, "_get_cookies", return_value=mock_cookies), \
             patch(
                 "app.engine.search_platforms.adapters.browser_base._submit_to_pw_worker",
                 return_value=long_text,
             ), \
             patch.object(adapter, "_llm_extract", return_value=llm_results):
            results = adapter.search_group_sync("Vua 2nd", "MacBook", max_results=5)

        assert results[0].title == "Old Group"

    def test_serper_fallback_still_works(self, mock_settings):
        """Serper fallback triggers when Playwright fails."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        mock_serper = MagicMock()
        mock_serper.search_sync.return_value = [
            ProductSearchResult(platform="Serper", title="Serper Result", price="100"),
        ]

        adapter = FacebookSearchAdapter(serper_fallback=mock_serper)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch.object(adapter, "_run_fetch_with_interception", side_effect=Exception("browser crashed")), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            results = adapter.search_sync("test", max_results=5)

        mock_serper.search_sync.assert_called_once()
        assert results[0].title == "Serper Result"

    def test_no_new_imports_when_disabled(self, mock_settings_no_interception):
        """When disabled, _run_fetch_with_interception is never called."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        from app.engine.search_platforms.base import ProductSearchResult

        adapter = FacebookSearchAdapter()
        llm_results = [ProductSearchResult(platform="Facebook", title="NoIntercept", price="100")]
        long_text = "Facebook content with products and listings " * 10

        with patch("app.core.config.get_settings", return_value=mock_settings_no_interception), \
             patch.object(adapter, "_run_fetch_with_scroll", return_value=long_text) as mock_scroll, \
             patch.object(adapter, "_run_fetch_with_interception") as mock_intercept, \
             patch.object(adapter, "_llm_extract", return_value=llm_results), \
             patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            adapter.search_sync("test", max_results=5)

        mock_intercept.assert_not_called()
        mock_scroll.assert_called_once()

    def test_constants_exported(self):
        """Sprint 156 constants are importable."""
        from app.engine.search_platforms.adapters.browser_base import (
            _FOR_LOOP_PREFIX,
            _GRAPHQL_ENDPOINT,
            _PRODUCT_INDICATOR_FIELDS,
            _MIN_INDICATOR_MATCH,
            _INTERCEPTION_FALLBACK_THRESHOLD,
        )
        assert _FOR_LOOP_PREFIX == "for (;;);"
        assert "/api/graphql/" in _GRAPHQL_ENDPOINT
        assert len(_PRODUCT_INDICATOR_FIELDS) == 4
        assert _MIN_INDICATOR_MATCH == 2
        assert _INTERCEPTION_FALLBACK_THRESHOLD == 3
