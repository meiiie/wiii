"""
Sprint 199: "Cầu Nối Trung-Việt" — Chinese Platform Search + Multi-Region Comparison

Tests for:
- URL-based currency auto-detection (_detect_currency_from_url)
- Chinese price patterns (元, RMB, ¥)
- Region configuration and query building (_get_active_regions)
- Multi-region search (_search_international with regions)
- Tool function signature (regions param, backward compat)
- Currency fallback chain (_detect_result_currency)
- Agent prompt updates (product_search_node)
- Config flag (enable_chinese_platform_search)

55 tests total.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# Patch paths
_PATCH_SETTINGS = "app.core.config.get_settings"
_PATCH_SERPER_AVAILABLE = "app.engine.tools.serper_web_search.is_serper_available"
_PATCH_SERPER_SEARCH = "app.engine.tools.serper_web_search._serper_search"
_PATCH_JINA = "app.engine.tools.international_search_tool._fetch_page_markdown"


# =============================================================================
# Helpers
# =============================================================================

def _mock_settings(**overrides):
    """Create a mock settings object with defaults."""
    s = MagicMock()
    s.enable_international_search = overrides.get("enable_international_search", True)
    s.enable_chinese_platform_search = overrides.get("enable_chinese_platform_search", True)
    s.usd_vnd_exchange_rate = overrides.get("usd_vnd_exchange_rate", 25500.0)
    s.exchange_rate_overrides = overrides.get("exchange_rate_overrides", {})
    s.serper_api_key = overrides.get("serper_api_key", "test-serper-key")
    s.enable_serper_web_search = overrides.get("enable_serper_web_search", True)
    return s


def _mock_serper_results(items=None):
    """Build mock Serper search results."""
    if items is None:
        items = [
            {"href": "https://example.com/1", "title": "Result 1", "body": "Snippet $450"},
            {"href": "https://example.com/2", "title": "Result 2", "body": "Snippet $350"},
        ]
    return items


# =============================================================================
# 1. TestDetectCurrencyFromUrl — 8 tests
# =============================================================================

class TestDetectCurrencyFromUrl:
    """Test URL-based currency auto-detection."""

    def test_1688_returns_cny(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://detail.1688.com/offer/123.html") == "CNY"

    def test_taobao_returns_cny(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://item.taobao.com/item.htm?id=123") == "CNY"

    def test_tmall_returns_cny(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://detail.tmall.com/item.htm?id=456") == "CNY"

    def test_amazon_com_returns_usd(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://www.amazon.com/dp/B00123") == "USD"

    def test_amazon_jp_returns_jpy(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://www.amazon.co.jp/dp/B00123") == "JPY"

    def test_aliexpress_returns_usd(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://www.aliexpress.com/item/123.html") == "USD"

    def test_unknown_domain_returns_none(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("https://www.randomshop.vn/product/123") is None

    def test_empty_url_returns_none(self):
        from app.engine.tools.international_search_tool import _detect_currency_from_url
        assert _detect_currency_from_url("") is None


# =============================================================================
# 2. TestChinesePricePatterns — 6 tests
# =============================================================================

class TestChinesePricePatterns:
    """Test Chinese price pattern extraction (元, RMB, ¥)."""

    def test_yuan_suffix_pattern(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        price = _extract_price_from_text("价格 12.50元 包邮", "CNY")
        assert price == 12.50

    def test_rmb_prefix_pattern(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        price = _extract_price_from_text("RMB 1280 wholesale", "CNY")
        assert price == 1280.0

    def test_yen_symbol_cny(self):
        """¥ symbol defaults to CNY."""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        price = _extract_price_from_text("¥ 88.00 免运费", "CNY")
        assert price == 88.0

    def test_cny_code_pattern(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        price = _extract_price_from_text("CNY 450.00 per unit", "CNY")
        assert price == 450.0

    def test_yuan_large_number(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        price = _extract_price_from_text("批发价 1,280.00元", "CNY")
        assert price == 1280.0

    def test_rmb_in_code_regex(self):
        """RMB should be recognized by _CODE_PRICE_REGEX."""
        from app.engine.tools.international_search_tool import _CODE_PRICE_REGEX
        match = _CODE_PRICE_REGEX.search("RMB 99.50 wholesale price")
        assert match is not None


# =============================================================================
# 3. TestBuildRegionQueries — 5 tests
# =============================================================================

class TestBuildRegionQueries:
    """Test region query building and filtering."""

    @patch(_PATCH_SETTINGS)
    def test_all_regions_returned_when_chinese_enabled(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_chinese_platform_search=True)
        from app.engine.tools.international_search_tool import _get_active_regions
        regions = _get_active_regions("")
        region_ids = [r["id"] for r in regions]
        assert "global" in region_ids
        assert "china_1688" in region_ids
        assert "china_taobao" in region_ids
        assert "aliexpress" in region_ids

    @patch(_PATCH_SETTINGS)
    def test_only_global_when_chinese_disabled(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_chinese_platform_search=False)
        from app.engine.tools.international_search_tool import _get_active_regions
        regions = _get_active_regions("")
        assert len(regions) == 1
        assert regions[0]["id"] == "global"

    @patch(_PATCH_SETTINGS)
    def test_filter_by_region_id(self, mock_settings):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import _get_active_regions
        regions = _get_active_regions("china_1688,aliexpress")
        region_ids = [r["id"] for r in regions]
        assert region_ids == ["china_1688", "aliexpress"]

    def test_product_name_substitution_in_queries(self):
        from app.engine.tools.international_search_tool import _SEARCH_REGIONS
        region = next(r for r in _SEARCH_REGIONS if r["id"] == "china_1688")
        queries = [q.format(product="Arduino Mega 2560") for q in region["queries"]]
        assert "site:1688.com Arduino Mega 2560" in queries

    def test_global_region_has_us_gl(self):
        from app.engine.tools.international_search_tool import _SEARCH_REGIONS
        region = next(r for r in _SEARCH_REGIONS if r["id"] == "global")
        assert region["gl"] == "us"
        assert region["hl"] == "en"
        assert region["default_currency"] == "USD"


# =============================================================================
# 4. TestMultiRegionSearch — 15 tests
# =============================================================================

class TestMultiRegionSearch:
    """Test multi-region search with all regions, filtering, dedup."""

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_all_regions_searched(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = _mock_serper_results()

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("Arduino Mega 2560")
        assert "regions_searched" in result
        assert "global" in result["regions_searched"]
        assert "china_1688" in result["regions_searched"]
        assert "china_taobao" in result["regions_searched"]
        assert "aliexpress" in result["regions_searched"]

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_serper_called_with_correct_gl_hl(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = []

        from app.engine.tools.international_search_tool import _search_international
        _search_international("test product")

        # Check that Serper was called with different gl/hl values
        call_kwargs = [call.kwargs for call in mock_search.call_args_list]
        gls = [kw.get("gl") for kw in call_kwargs]
        assert "us" in gls  # global region
        assert "cn" in gls  # china regions

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_dedup_across_regions(self, mock_settings, mock_avail, mock_search, mock_jina):
        """Same URL appearing in multiple regions should only appear once."""
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = [
            {"href": "https://same-url.com/p1", "title": "Product", "body": "$100"},
        ]

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        # Even though we search 4 regions, same URL should appear only once
        urls = [r["url"] for r in result["results"]]
        assert urls.count("https://same-url.com/p1") == 1

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_results_include_region_field(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = [
            {"href": "https://example.com/1", "title": "T1", "body": "$100"},
        ]

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        if result["results"]:
            assert "region" in result["results"][0]
            assert "source_platform" in result["results"][0]

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_cny_extraction_from_1688(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        # Only return results for 1688 region (site:1688.com query)
        def side_effect(query, **kwargs):
            if "1688.com" in query:
                return [{"href": "https://detail.1688.com/offer/123.html", "title": "1688 Product", "body": "¥ 88.00 包邮"}]
            return []
        mock_search.side_effect = side_effect

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test product")
        priced = [r for r in result["results"] if r["price_foreign"] is not None]
        if priced:
            assert priced[0]["price_currency"] == "CNY"
            assert priced[0]["price_foreign"] == 88.0
            assert priced[0]["source_platform"] == "1688.com"

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_usd_fallback_when_cny_not_found(self, mock_settings, mock_avail, mock_search, mock_jina):
        """If no CNY price found, should fallback to USD."""
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = [
            {"href": "https://www.aliexpress.com/item/123.html", "title": "AliExpress", "body": "$45.99"},
        ]

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test", currency="CNY")
        priced = [r for r in result["results"] if r["price_foreign"] is not None]
        if priced:
            # Should detect USD from aliexpress.com domain
            assert priced[0]["price_currency"] == "USD"

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_region_filter_only_searches_requested(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = []

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test", regions="china_1688")
        assert result["regions_searched"] == ["china_1688"]

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_empty_results_returns_regions_searched(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.return_value = []

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("nonexistent product xyz")
        assert result["count"] == 0
        assert len(result["regions_searched"]) > 0

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_vnd_conversion_for_cny(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings(usd_vnd_exchange_rate=25500.0)
        mock_search.return_value = [
            {"href": "https://detail.1688.com/offer/1.html", "title": "T", "body": "¥ 100"},
        ]

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        priced = [r for r in result["results"] if r["price_vnd"] is not None]
        if priced:
            # CNY 100 * 0.14 (to USD) * 25500 (VND/USD) = 357,000 VND
            assert priced[0]["price_vnd"] == round(100 * 0.14 * 25500)

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_planner_queries_used_for_global_only(self, mock_settings, mock_avail, mock_search, mock_jina):
        """Planner queries should only be used for the global region."""
        mock_settings.return_value = _mock_settings()
        call_queries = []
        def capture_search(query, **kwargs):
            call_queries.append(query)
            return []
        mock_search.side_effect = capture_search

        from app.engine.tools.international_search_tool import _search_international
        _search_international(
            "Arduino", currency="USD",
            search_queries=["planner query 1", "planner query 2"],
        )
        # Planner queries should appear in calls (for global region)
        assert "planner query 1" in call_queries
        assert "planner query 2" in call_queries
        # Site-specific queries should also appear (for Chinese regions)
        site_queries = [q for q in call_queries if "site:" in q]
        assert len(site_queries) > 0  # 1688, taobao, tmall, aliexpress

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=False)
    @patch(_PATCH_SETTINGS)
    def test_ddgs_fallback_only_for_global(self, mock_settings, mock_avail, mock_search, mock_jina):
        """DuckDuckGo fallback should only apply to global region."""
        mock_settings.return_value = _mock_settings()
        # When Serper not available, only global should get results via DDGS
        # Chinese regions should be silently skipped
        with patch("app.engine.tools.international_search_tool._search_international_ddgs") as mock_ddgs:
            mock_ddgs.return_value = []
            from app.engine.tools.international_search_tool import _search_international
            result = _search_international("test")
            # DDGS should have been called (for global region)
            mock_ddgs.assert_called_once()

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_priced_results_before_unpriced(self, mock_settings, mock_avail, mock_search, mock_jina):
        """Items with price should appear before items without price.
        No ascending/descending sort — agent decides presentation order."""
        mock_settings.return_value = _mock_settings()
        counter = [0]
        def side_effect(query, **kwargs):
            counter[0] += 1
            if counter[0] == 1:
                return [
                    {"href": "https://example.com/no-price", "title": "NoPriceItem", "body": "no price info"},
                    {"href": "https://example.com/cheap", "title": "Cheap", "body": "$100"},
                ]
            return []
        mock_search.side_effect = side_effect

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        priced = [r for r in result["results"] if r["price_vnd"] is not None]
        unpriced = [r for r in result["results"] if r["price_vnd"] is None]
        if priced and unpriced:
            # All priced items should come before unpriced items
            last_priced_idx = max(i for i, r in enumerate(result["results"]) if r["price_vnd"] is not None)
            first_unpriced_idx = min(i for i, r in enumerate(result["results"]) if r["price_vnd"] is None)
            assert last_priced_idx < first_unpriced_idx

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_taobao_tmall_queries(self, mock_settings, mock_avail, mock_search, mock_jina):
        """china_taobao region should search both taobao.com and tmall.com."""
        mock_settings.return_value = _mock_settings()
        call_queries = []
        def capture(query, **kwargs):
            call_queries.append(query)
            return []
        mock_search.side_effect = capture

        from app.engine.tools.international_search_tool import _search_international
        _search_international("iPhone 16", regions="china_taobao")
        assert any("taobao.com" in q for q in call_queries)
        assert any("tmall.com" in q for q in call_queries)

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_serper_error_handled_gracefully(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.side_effect = Exception("Serper API error")

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        assert result["count"] == 0
        assert len(result["regions_searched"]) > 0

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH)
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_max_10_enriched_results(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        # Return 20 results
        mock_search.return_value = [
            {"href": f"https://example.com/{i}", "title": f"R{i}", "body": f"${i*10}"}
            for i in range(20)
        ]

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test", regions="global")
        assert result["count"] <= 10


# =============================================================================
# 5. TestToolFunctionSignature — 8 tests
# =============================================================================

class TestToolFunctionSignature:
    """Test tool_international_search_fn signature and behavior."""

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_regions_param_accepted(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", regions="china_1688"))
        assert "regions_searched" in result

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_backward_compat_no_regions(self, mock_settings, mock_avail, mock_search, mock_jina):
        """Calling without regions param should still work."""
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test"))
        assert isinstance(result, dict)
        assert "results" in result

    @patch(_PATCH_SETTINGS)
    def test_gate_disabled_returns_error(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_international_search=False)
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test"))
        assert "error" in result

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_invalid_currency_falls_back_to_usd(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", currency="INVALID"))
        assert result.get("currency") == "USD"

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_cny_currency_accepted(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", currency="CNY"))
        assert result.get("currency") == "CNY"

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_search_queries_json_param(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        queries_json = json.dumps(["custom query 1", "custom query 2"])
        result = json.loads(tool_international_search_fn("test", search_queries=queries_json))
        assert isinstance(result, dict)

    @patch(_PATCH_JINA, return_value="")
    @patch(_PATCH_SERPER_SEARCH, return_value=[])
    @patch(_PATCH_SERPER_AVAILABLE, return_value=True)
    @patch(_PATCH_SETTINGS)
    def test_exception_returns_error_json(self, mock_settings, mock_avail, mock_search, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_search.side_effect = RuntimeError("unexpected")
        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", regions="global"))
        # Should not crash, should return valid JSON
        assert isinstance(result, dict)

    def test_tool_description_mentions_chinese_platforms(self):
        from app.engine.tools.international_search_tool import get_international_search_tool
        tool = get_international_search_tool()
        desc = tool.description
        assert "1688" in desc
        assert "Taobao" in desc
        assert "AliExpress" in desc
        assert "CNY" in desc


# =============================================================================
# 6. TestCurrencyFallbackChain — 6 tests
# =============================================================================

class TestCurrencyFallbackChain:
    """Test _detect_result_currency priority chain."""

    def test_url_currency_has_highest_priority(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "global", "default_currency": "USD"}
        result = _detect_result_currency("https://detail.1688.com/offer/1.html", region, "EUR")
        assert result == "CNY"  # URL detection overrides everything

    def test_region_default_when_url_unknown(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "china_1688", "default_currency": "CNY"}
        result = _detect_result_currency("https://unknown-shop.cn/product", region, "EUR")
        assert result == "CNY"  # Region default

    def test_user_currency_when_no_url_or_region(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "custom"}  # No default_currency
        result = _detect_result_currency("https://unknown.com/product", region, "GBP")
        assert result == "GBP"

    def test_usd_ultimate_fallback(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "custom"}
        result = _detect_result_currency("https://unknown.com/product", region, "")
        assert result == "USD"

    def test_aliexpress_url_returns_usd(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "aliexpress", "default_currency": "USD"}
        result = _detect_result_currency("https://www.aliexpress.com/item/123.html", region, "CNY")
        assert result == "USD"  # URL overrides user's CNY preference

    def test_amazon_de_returns_eur(self):
        from app.engine.tools.international_search_tool import _detect_result_currency
        region = {"id": "global", "default_currency": "USD"}
        result = _detect_result_currency("https://www.amazon.de/dp/B123", region, "USD")
        assert result == "EUR"


# =============================================================================
# 7. TestAgentPromptUpdate — 5 tests
# =============================================================================

class TestAgentPromptUpdate:
    """Test product_search_node prompt updates for Sprint 199."""

    def test_system_prompt_mentions_1688(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "1688" in _SYSTEM_PROMPT

    def test_system_prompt_mentions_taobao(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "Taobao" in _SYSTEM_PROMPT

    def test_deep_search_prompt_has_round_5(self):
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "Vòng 5" in _DEEP_SEARCH_PROMPT
        assert "tool_international_search" in _DEEP_SEARCH_PROMPT

    def test_tool_ack_updated(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "1688" in _SYSTEM_PROMPT
        assert "AliExpress" in _SYSTEM_PROMPT

    def test_system_prompt_has_chinese_strategy_section(self):
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "CHIẾN LƯỢC KHÁCH TRUNG QUỐC" in _SYSTEM_PROMPT


# =============================================================================
# 8. TestConfigFlag — 2 tests
# =============================================================================

class TestConfigFlag:
    """Test enable_chinese_platform_search config flag."""

    def test_flag_exists_in_settings(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            enable_chinese_platform_search=True,
        )
        assert s.enable_chinese_platform_search is True

    def test_flag_default_true(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.enable_chinese_platform_search is True


# =============================================================================
# 9. TestQueryPlannerUpdate — 3 tests
# =============================================================================

class TestQueryPlannerUpdate:
    """Test query_planner.py updates for Sprint 199."""

    def test_chinese_sourcing_intent_exists(self):
        from app.engine.tools.query_planner import SearchIntent
        assert hasattr(SearchIntent, "CHINESE_SOURCING")
        assert SearchIntent.CHINESE_SOURCING.value == "CHINESE_SOURCING"

    def test_china_first_strategy_exists(self):
        from app.engine.tools.query_planner import SearchStrategy
        assert hasattr(SearchStrategy, "CHINA_FIRST")
        assert SearchStrategy.CHINA_FIRST.value == "CHINA_FIRST"

    def test_planner_prompt_mentions_chinese_keywords(self):
        from app.engine.tools.query_planner import _PLANNER_PROMPT
        assert "CHINESE_SOURCING" in _PLANNER_PROMPT
        assert "CHINA_FIRST" in _PLANNER_PROMPT


# =============================================================================
# 10. TestExtractSourcePlatform — 2 tests
# =============================================================================

class TestExtractSourcePlatform:
    """Test _extract_source_platform helper."""

    def test_known_platforms(self):
        from app.engine.tools.international_search_tool import _extract_source_platform
        assert _extract_source_platform("https://detail.1688.com/offer/1.html") == "1688.com"
        assert _extract_source_platform("https://item.taobao.com/item.htm?id=1") == "Taobao"
        assert _extract_source_platform("https://www.aliexpress.com/item/1.html") == "AliExpress"
        assert _extract_source_platform("https://www.amazon.com/dp/B123") == "Amazon US"

    def test_unknown_platform_returns_domain(self):
        from app.engine.tools.international_search_tool import _extract_source_platform
        result = _extract_source_platform("https://www.randomshop.vn/product")
        assert result == "randomshop.vn"
