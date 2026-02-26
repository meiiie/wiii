"""
Sprint 198: "Nâng Cấp Serper" — Replace DuckDuckGo with Serper.dev

Tests for:
- app/engine/tools/serper_web_search.py (shared utility)
- Dealer search with Serper (dealer_search_tool.py)
- International search with Serper (international_search_tool.py)
- Web search tools with Serper (web_search_tools.py)
- Config flag + feature gate (enable_serper_web_search)
- Integration with Sprint 197 Query Planner

65 tests total.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# All tools use lazy `from app.core.config import get_settings` — patch at SOURCE.
_PATCH_SETTINGS = "app.core.config.get_settings"
_PATCH_HTTPX = "app.engine.tools.serper_web_search.httpx.post"
_PATCH_DEALER_JINA = "app.engine.tools.dealer_search_tool._fetch_page_markdown"
_PATCH_INTL_JINA = "app.engine.tools.international_search_tool._fetch_page_markdown"


# =============================================================================
# Helper: Mock Serper API response
# =============================================================================

def _mock_serper_response(items=None, search_type="search"):
    """Build a mock httpx Response for Serper API."""
    if items is None:
        items = [
            {"title": "Result 1", "snippet": "Snippet 1", "link": "https://example.com/1"},
            {"title": "Result 2", "snippet": "Snippet 2", "link": "https://example.com/2"},
            {"title": "Result 3", "snippet": "Snippet 3", "link": "https://example.com/3"},
        ]
    key = "news" if search_type == "news" else "organic"
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {key: items}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_settings(**overrides):
    """Create a mock settings object with defaults."""
    s = MagicMock()
    s.serper_api_key = overrides.get("serper_api_key", "test-serper-key")
    s.enable_serper_web_search = overrides.get("enable_serper_web_search", True)
    s.enable_dealer_search = overrides.get("enable_dealer_search", True)
    s.enable_international_search = overrides.get("enable_international_search", True)
    s.usd_vnd_exchange_rate = overrides.get("usd_vnd_exchange_rate", 25500.0)
    return s


# =============================================================================
# 1. Serper Utility Tests (_serper_search, _serper_news_search)
# =============================================================================

class TestSerperSearch:
    """Tests for app/engine/tools/serper_web_search._serper_search()."""

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_basic_search_returns_results(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test query")
        assert len(results) == 3
        assert results[0]["title"] == "Result 1"
        assert results[0]["href"] == "https://example.com/1"
        assert results[0]["body"] == "Snippet 1"

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_gl_hl_params_sent(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.serper_web_search import _serper_search
        _serper_search("test", gl="us", hl="en")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["gl"] == "us"
        assert payload["hl"] == "en"

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_max_results_capped(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        items = [{"title": f"R{i}", "snippet": f"S{i}", "link": f"https://e.com/{i}"} for i in range(20)]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test", max_results=5)
        assert len(results) == 5

    @patch(_PATCH_SETTINGS)
    def test_no_api_key_returns_empty(self, mock_settings):
        mock_settings.return_value = _mock_settings(serper_api_key=None)
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []

    @patch(_PATCH_SETTINGS)
    def test_empty_api_key_returns_empty(self, mock_settings):
        mock_settings.return_value = _mock_settings(serper_api_key="")
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_timeout_returns_empty(self, mock_settings, mock_post):
        import httpx
        mock_settings.return_value = _mock_settings()
        mock_post.side_effect = httpx.TimeoutException("timeout")
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_http_error_returns_empty(self, mock_settings, mock_post):
        import httpx
        mock_settings.return_value = _mock_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limit", request=MagicMock(), response=mock_resp
        )
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_type(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        news_items = [
            {"title": "News 1", "snippet": "Breaking", "link": "https://news.com/1", "date": "2h ago", "source": "VnExpress"},
        ]
        mock_post.return_value = _mock_serper_response(news_items, search_type="news")
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test", search_type="news")
        assert len(results) == 1
        assert results[0]["date"] == "2h ago"
        assert results[0]["source"] == "VnExpress"

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_endpoint_url_for_search(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.serper_web_search import _serper_search
        _serper_search("test", search_type="search")
        assert "google.serper.dev/search" in str(mock_post.call_args)

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_endpoint_url_for_news(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response(search_type="news")
        from app.engine.tools.serper_web_search import _serper_search
        _serper_search("test", search_type="news")
        assert "google.serper.dev/news" in str(mock_post.call_args)

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_api_key_in_headers(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings(serper_api_key="my-key-123")
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.serper_web_search import _serper_search
        _serper_search("test")
        headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
        assert headers["X-API-KEY"] == "my-key-123"

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_empty_organic_returns_empty(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response(items=[])
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_general_exception_returns_empty(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.side_effect = Exception("network error")
        from app.engine.tools.serper_web_search import _serper_search
        results = _serper_search("test")
        assert results == []


class TestSerperNewsSearch:
    """Tests for _serper_news_search() convenience wrapper."""

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_calls_serper(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response(search_type="news")
        from app.engine.tools.serper_web_search import _serper_news_search
        results = _serper_news_search("tin tức hàng hải")
        assert isinstance(results, list)
        assert "google.serper.dev/news" in str(mock_post.call_args)

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_default_params(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response(search_type="news")
        from app.engine.tools.serper_web_search import _serper_news_search
        _serper_news_search("test")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["gl"] == "vn"
        assert payload["hl"] == "vi"


class TestIsSerperAvailable:
    """Tests for is_serper_available()."""

    @patch(_PATCH_SETTINGS)
    def test_available_when_configured(self, mock_settings):
        mock_settings.return_value = _mock_settings()
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is True

    @patch(_PATCH_SETTINGS)
    def test_not_available_no_key(self, mock_settings):
        mock_settings.return_value = _mock_settings(serper_api_key=None)
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is False

    @patch(_PATCH_SETTINGS)
    def test_not_available_disabled(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_serper_web_search=False)
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is False

    @patch(_PATCH_SETTINGS)
    def test_not_available_on_exception(self, mock_settings):
        mock_settings.side_effect = Exception("config error")
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is False


# =============================================================================
# 2. Dealer Search Tool with Serper
# =============================================================================

class TestDealerSearchSerper:
    """Tests for dealer_search_tool.py with Serper integration."""

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_uses_serper(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        items = [
            {"title": "Dealer VN 1", "snippet": "Đại lý phân phối chính hãng", "link": "https://dealer.vn/1"},
            {"title": "Dealer VN 2", "snippet": "Nhà cung cấp uy tín", "link": "https://dealer.vn/2"},
        ]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("Zebra ZXP7")
        assert result["count"] > 0
        assert any("dealer.vn" in d["url"] for d in result["dealers"])

    @patch(_PATCH_DEALER_JINA, return_value="Liên hệ: 0901234567")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_contact_extraction_preserved(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        items = [{"title": "Dealer", "snippet": "Test", "link": "https://dealer.vn/1"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("Zebra ZXP7")
        assert result["count"] == 1
        dealer = result["dealers"][0]
        assert "0901234567" in dealer["contacts"]["phones"]

    @patch("app.engine.tools.dealer_search_tool._search_dealers_ddgs", return_value=[])
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_ddgs_fallback_no_key(self, mock_settings, mock_ddgs):
        """When Serper has no API key, falls back to DuckDuckGo."""
        mock_settings.return_value = _mock_settings(serper_api_key=None)
        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        assert result["dealers"] == []
        mock_ddgs.assert_called_once()

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_gl_vn(self, mock_settings, mock_post, mock_jina):
        """Dealer search uses gl=vn for Vietnamese results."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import _search_dealers
        _search_dealers("test")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["gl"] == "vn"
        assert payload["hl"] == "vi"

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_url_deduplication(self, mock_settings, mock_post, mock_jina):
        """Duplicate URLs across queries are deduplicated."""
        mock_settings.return_value = _mock_settings()
        items = [{"title": "Dup", "snippet": "Same", "link": "https://dealer.vn/same"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test")
        assert result["count"] == 1  # deduped despite multiple queries

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_search_with_planned_queries(self, mock_settings, mock_post, mock_jina):
        """Sprint 197: Pre-optimized queries from planner are used."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import _search_dealers
        custom_queries = ["Zebra ZXP7 đại lý HCM", "Zebra ZXP7 mua giá sỉ"]
        result = _search_dealers("Zebra ZXP7", search_queries=custom_queries)
        assert mock_post.call_count == 2
        first_payload = mock_post.call_args_list[0].kwargs.get("json") or mock_post.call_args_list[0][1].get("json")
        assert "Zebra ZXP7 đại lý HCM" in first_payload["q"]

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_dealer_tool_fn_json_output(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        output = tool_dealer_search_fn("test product")
        parsed = json.loads(output)
        assert "dealers" in parsed
        assert "count" in parsed

    @patch(_PATCH_SETTINGS)
    def test_dealer_tool_fn_disabled(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_dealer_search=False)
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        output = tool_dealer_search_fn("test")
        parsed = json.loads(output)
        assert "error" in parsed


# =============================================================================
# 3. International Search Tool with Serper
# =============================================================================

class TestInternationalSearchSerper:
    """Tests for international_search_tool.py with Serper integration."""

    @patch(_PATCH_INTL_JINA, return_value="Price: $150.00")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_uses_serper(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        items = [{"title": "Global Supplier", "snippet": "Wholesale $150", "link": "https://supplier.com/1"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("Zebra ZXP7 printhead")
        assert result["count"] > 0
        assert result["results"][0]["url"] == "https://supplier.com/1"

    @patch(_PATCH_INTL_JINA, return_value="Price: $200.00")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_gl_us(self, mock_settings, mock_post, mock_jina):
        """International search uses gl=us, hl=en for US market."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.international_search_tool import _search_international
        _search_international("test product")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["gl"] == "us"
        assert payload["hl"] == "en"

    @patch(_PATCH_INTL_JINA, return_value="Price: $100.00")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_vnd_conversion(self, mock_settings, mock_post, mock_jina):
        """Price is extracted and converted to VND."""
        mock_settings.return_value = _mock_settings(usd_vnd_exchange_rate=25000.0)
        items = [{"title": "Product", "snippet": "$100", "link": "https://shop.com/1"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test", currency="USD")
        item = result["results"][0]
        assert item["price_foreign"] == 100.0
        assert item["price_vnd"] == 2500000  # 100 * 25000

    @patch("app.engine.tools.international_search_tool._search_international_ddgs", return_value=[])
    @patch(_PATCH_SETTINGS)
    def test_intl_search_ddgs_fallback_no_key(self, mock_settings, mock_ddgs):
        mock_settings.return_value = _mock_settings(serper_api_key=None)
        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        assert result["results"] == []
        mock_ddgs.assert_called_once()

    @patch(_PATCH_INTL_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_with_planned_queries(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.international_search_tool import _search_international
        custom = ["ZXP7 wholesale price", "Zebra printhead supplier"]
        # Sprint 199: planner queries used for global region (2), plus
        # china_1688 (1), china_taobao (2), aliexpress (1) = 6 total
        result = _search_international("ZXP7", search_queries=custom)
        assert mock_post.call_count >= 2  # at least planner queries

    @patch(_PATCH_INTL_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_exchange_rate_in_output(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings(usd_vnd_exchange_rate=26000.0)
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        assert result["exchange_rate"] == 26000.0

    @patch(_PATCH_INTL_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_tool_fn_json_output(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        output = tool_international_search_fn("test")
        parsed = json.loads(output)
        assert "results" in parsed
        assert "count" in parsed

    @patch(_PATCH_SETTINGS)
    def test_intl_tool_fn_disabled(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_international_search=False)
        from app.engine.tools.international_search_tool import tool_international_search_fn
        output = tool_international_search_fn("test")
        parsed = json.loads(output)
        assert "error" in parsed

    @patch(_PATCH_INTL_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_intl_search_url_deduplication(self, mock_settings, mock_post, mock_jina):
        mock_settings.return_value = _mock_settings()
        items = [{"title": "Dup", "snippet": "Same", "link": "https://shop.com/same"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test")
        assert result["count"] == 1


# =============================================================================
# 4. Web Search Tools with Serper
# =============================================================================

class TestWebSearchSerper:
    """Tests for web_search_tools.py with Serper integration."""

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_web_search_uses_serper(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "test query"})
        assert "Result 1" in result
        assert "example.com/1" in result

    @patch(_PATCH_SETTINGS)
    def test_web_search_ddgs_fallback(self, mock_settings):
        """When Serper unavailable, falls back to DuckDuckGo."""
        mock_settings.return_value = _mock_settings(serper_api_key=None)
        with patch("app.engine.tools.web_search_tools._search_sync", return_value=[
            {"title": "DDG Result", "body": "DuckDuckGo fallback", "href": "https://ddg.com/1"}
        ]):
            from app.engine.tools.web_search_tools import tool_web_search
            result = tool_web_search.invoke({"query": "test"})
            assert "DDG Result" in result

    def test_web_search_circuit_breaker(self):
        """Circuit breaker blocks requests after repeated failures."""
        from app.engine.tools.web_search_tools import _cb_states, _CB_THRESHOLD
        import time
        _cb_states["web_search"] = {"failures": _CB_THRESHOLD, "last_failure": time.time()}
        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "blocked query"})
        assert "không khả dụng" in result
        _cb_states.pop("web_search", None)

    @patch("app.engine.tools.web_search_tools._rss_fetch_sync", return_value=[])
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_uses_serper(self, mock_settings, mock_post, mock_rss):
        mock_settings.return_value = _mock_settings()
        news_items = [
            {"title": "News Headline", "snippet": "Breaking news", "link": "https://news.vn/1", "date": "3h ago"},
        ]
        mock_post.return_value = _mock_serper_response(news_items, search_type="news")
        from app.engine.tools.web_search_tools import tool_search_news
        result = tool_search_news.invoke({"query": "tin tức"})
        assert "News Headline" in result

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_legal_search_uses_serper_site_filter(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        items = [{"title": "Nghị Định 123", "snippet": "Quy định về...", "link": "https://thuvienphapluat.vn/1"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.web_search_tools import tool_search_legal
        result = tool_search_legal.invoke({"query": "an toàn hàng hải"})
        assert "Nghị Định 123" in result
        payload = mock_post.call_args_list[0].kwargs.get("json") or mock_post.call_args_list[0][1].get("json")
        assert "site:thuvienphapluat.vn" in payload["q"]

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_maritime_search_uses_serper_site_filter(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        items = [{"title": "IMO Regulation", "snippet": "SOLAS chapter V", "link": "https://imo.org/1"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.web_search_tools import tool_search_maritime
        result = tool_search_maritime.invoke({"query": "SOLAS amendments"})
        assert "IMO Regulation" in result
        payload = mock_post.call_args_list[0].kwargs.get("json") or mock_post.call_args_list[0][1].get("json")
        assert "site:imo.org" in payload["q"]

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_legal_search_fallback_no_site_results(self, mock_settings, mock_post):
        """Legal search falls back to unrestricted search when site-restricted returns nothing."""
        mock_settings.return_value = _mock_settings()
        empty_resp = _mock_serper_response(items=[])
        result_resp = _mock_serper_response([{"title": "General Legal", "snippet": "Law info", "link": "https://legal.vn/1"}])
        mock_post.side_effect = [empty_resp, result_resp]
        from app.engine.tools.web_search_tools import tool_search_legal
        result = tool_search_legal.invoke({"query": "nghị định"})
        assert "General Legal" in result

    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_maritime_search_fallback_no_site_results(self, mock_settings, mock_post):
        mock_settings.return_value = _mock_settings()
        empty_resp = _mock_serper_response(items=[])
        result_resp = _mock_serper_response([{"title": "General Maritime", "snippet": "Shipping info", "link": "https://maritime.com/1"}])
        mock_post.side_effect = [empty_resp, result_resp]
        from app.engine.tools.web_search_tools import tool_search_maritime
        result = tool_search_maritime.invoke({"query": "COLREG"})
        assert "General Maritime" in result

    @patch("app.engine.tools.web_search_tools._rss_fetch_sync")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_merges_serper_and_rss(self, mock_settings, mock_post, mock_rss):
        """News search merges Serper results with RSS results."""
        mock_settings.return_value = _mock_settings()
        news_items = [{"title": "Serper News", "snippet": "From Serper", "link": "https://serper.com/1"}]
        mock_post.return_value = _mock_serper_response(news_items, search_type="news")
        mock_rss.return_value = [{"title": "RSS News", "body": "From RSS", "href": "https://rss.com/1", "source": "vnexpress"}]
        from app.engine.tools.web_search_tools import tool_search_news
        result = tool_search_news.invoke({"query": "tin tức"})
        assert "Serper News" in result
        assert "RSS News" in result

    @patch("app.engine.tools.web_search_tools._rss_fetch_sync")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_news_search_deduplicates_urls(self, mock_settings, mock_post, mock_rss):
        """Duplicate URLs from Serper + RSS are deduplicated."""
        mock_settings.return_value = _mock_settings()
        news_items = [{"title": "Same Article", "snippet": "Content", "link": "https://same.com/1"}]
        mock_post.return_value = _mock_serper_response(news_items, search_type="news")
        mock_rss.return_value = [{"title": "Same Article Dup", "body": "Content", "href": "https://same.com/1", "source": "rss"}]
        from app.engine.tools.web_search_tools import tool_search_news
        result = tool_search_news.invoke({"query": "test"})
        assert result.count("https://same.com/1") == 1


# =============================================================================
# 5. Config Flag Tests
# =============================================================================

class TestConfigFlag:
    """Tests for enable_serper_web_search config flag."""

    def test_config_flag_exists(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test", enable_serper_web_search=True)
        assert s.enable_serper_web_search is True

    def test_config_flag_default_true(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.enable_serper_web_search is True

    def test_config_flag_can_disable(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test", enable_serper_web_search=False)
        assert s.enable_serper_web_search is False

    @patch(_PATCH_SETTINGS)
    def test_serper_disabled_returns_empty(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_serper_web_search=False)
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is False

    @patch(_PATCH_SETTINGS)
    def test_serper_enabled_with_key_returns_true(self, mock_settings):
        mock_settings.return_value = _mock_settings(enable_serper_web_search=True, serper_api_key="key")
        from app.engine.tools.serper_web_search import is_serper_available
        assert is_serper_available() is True


# =============================================================================
# 6. Integration: Sprint 197 Planner + Serper Execution
# =============================================================================

class TestPlannerSerperIntegration:
    """Tests for Sprint 197 Query Planner queries flowing through Serper."""

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_planner_queries_dealer_serper(self, mock_settings, mock_post, mock_jina):
        """Planner-generated Vietnamese queries execute via Serper gl=vn."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        planned = json.dumps(["đầu in Zebra ZXP7 đại lý Hà Nội", "Zebra ZXP7 nhà phân phối HCM"])
        output = tool_dealer_search_fn("Zebra ZXP7", search_queries=planned)
        parsed = json.loads(output)
        assert "dealers" in parsed

    @patch(_PATCH_INTL_JINA, return_value="$250.00")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_planner_queries_intl_serper(self, mock_settings, mock_post, mock_jina):
        """Planner-generated English queries execute via Serper gl=us."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.international_search_tool import tool_international_search_fn
        planned = json.dumps(["Zebra ZXP7 printhead wholesale price", "ZXP Series 7 replacement head cost"])
        output = tool_international_search_fn("Zebra ZXP7", search_queries=planned)
        parsed = json.loads(output)
        assert "results" in parsed
        payload = mock_post.call_args_list[0].kwargs.get("json") or mock_post.call_args_list[0][1].get("json")
        assert payload["gl"] == "us"

    @patch(_PATCH_DEALER_JINA, return_value="Email: sales@zebra.vn")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_planner_queries_with_site_filter(self, mock_settings, mock_post, mock_jina):
        """Planner can include site: filters that work natively with Serper."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        planned = json.dumps(["site:.vn Zebra ZXP7 đại lý", "Zebra ZXP7 authorized dealer Vietnam"])
        output = tool_dealer_search_fn("Zebra ZXP7", search_queries=planned)
        parsed = json.loads(output)
        assert "dealers" in parsed
        first_payload = mock_post.call_args_list[0].kwargs.get("json") or mock_post.call_args_list[0][1].get("json")
        assert "site:.vn" in first_payload["q"]

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_planner_invalid_json_uses_defaults(self, mock_settings, mock_post, mock_jina):
        """Invalid planner JSON gracefully falls back to default queries."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        output = tool_dealer_search_fn("Zebra ZXP7", search_queries="not valid json")
        parsed = json.loads(output)
        assert "dealers" in parsed
        # Should have used default queries (4 queries for Vietnam)
        assert mock_post.call_count == 4

    @patch(_PATCH_DEALER_JINA, return_value="Zalo: 0901234567")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_full_pipeline_serper_jina_contacts(self, mock_settings, mock_post, mock_jina):
        """Full pipeline: Serper → Jina Reader → Contact extraction."""
        mock_settings.return_value = _mock_settings()
        items = [{"title": "VN Dealer", "snippet": "Đại lý chính hãng", "link": "https://dealer.vn/zebra"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        output = tool_dealer_search_fn("Zebra ZXP7")
        parsed = json.loads(output)
        assert parsed["count"] > 0
        dealer = parsed["dealers"][0]
        assert "0901234567" in dealer["contacts"]["zalo"]
        assert dealer["has_contact_info"]  # truthy (Python `or` returns first truthy value)

    @patch(_PATCH_INTL_JINA, return_value="€180.00 EUR price")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_full_pipeline_intl_eur_conversion(self, mock_settings, mock_post, mock_jina):
        """Full pipeline: Serper → Jina → EUR price extraction → VND."""
        mock_settings.return_value = _mock_settings(usd_vnd_exchange_rate=25000.0)
        # Sprint 199: Use amazon.de so URL-based detection returns EUR
        items = [{"title": "EU Supplier", "snippet": "€180.00", "link": "https://www.amazon.de/dp/B00123"}]
        mock_post.return_value = _mock_serper_response(items)
        from app.engine.tools.international_search_tool import tool_international_search_fn
        output = tool_international_search_fn("Zebra ZXP7", currency="EUR")
        parsed = json.loads(output)
        assert parsed["count"] > 0
        item = parsed["results"][0]
        assert item["price_foreign"] == 180.0
        assert item["price_currency"] == "EUR"
        # EUR→USD→VND: 180 * 1.08 * 25000 = 4,860,000
        assert item["price_vnd"] == 4860000

    @patch(_PATCH_DEALER_JINA, return_value="")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_non_vietnam_adds_location_query(self, mock_settings, mock_post, mock_jina):
        """Non-Vietnam location adds a location-specific query."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response()
        from app.engine.tools.dealer_search_tool import _search_dealers
        _search_dealers("Zebra ZXP7", location="Thailand")
        # Default queries (4) + 1 location-specific = 5
        assert mock_post.call_count == 5

    @patch("app.engine.tools.web_search_tools._search_sync")
    @patch(_PATCH_HTTPX)
    @patch(_PATCH_SETTINGS)
    def test_web_search_serper_empty_falls_to_ddgs(self, mock_settings, mock_post, mock_ddgs):
        """Web search: Serper returns empty → falls back to DuckDuckGo."""
        mock_settings.return_value = _mock_settings()
        mock_post.return_value = _mock_serper_response(items=[])
        mock_ddgs.return_value = [
            {"title": "DDG Fallback", "body": "From DuckDuckGo", "href": "https://ddg.com/1"}
        ]
        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "test"})
        assert "DDG Fallback" in result
