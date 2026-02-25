"""
Sprint 196: Dealer Search Tool Tests — "Thợ Săn Chuyên Nghiệp"

Tests for app/engine/tools/dealer_search_tool.py
40 tests covering contact extraction, Jina fetch, search pipeline, tool function, and StructuredTool.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Contact Extraction Tests
# =============================================================================

class TestExtractContactsFromText:
    """Test _extract_contacts_from_text()."""

    def _fn(self, text):
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        return _extract_contacts_from_text(text)

    def test_vietnamese_phone_standard(self):
        result = self._fn("Liên hệ: 0901234567 để được tư vấn")
        assert "0901234567" in result["phones"]

    def test_vietnamese_phone_landline(self):
        result = self._fn("Hotline: 02812345678")
        assert "02812345678" in result["phones"]

    def test_multiple_phones(self):
        result = self._fn("SĐT: 0901234567, 0912345678, 0938765432")
        assert len(result["phones"]) == 3

    def test_phone_deduplication(self):
        result = self._fn("Call 0901234567 or 0901234567")
        assert result["phones"].count("0901234567") == 1

    def test_phone_max_limit(self):
        text = " ".join([f"09{i:08d}" for i in range(10)])
        result = self._fn(text)
        assert len(result["phones"]) <= 5

    def test_zalo_pattern_colon(self):
        result = self._fn("Zalo: 0901234567")
        assert "0901234567" in result["zalo"]

    def test_zalo_pattern_slash(self):
        result = self._fn("zalo/0912345678")
        assert "0912345678" in result["zalo"]

    def test_zalo_deduplication(self):
        result = self._fn("Zalo: 0901234567 — Zalo: 0901234567")
        assert result["zalo"].count("0901234567") == 1

    def test_email_extraction(self):
        result = self._fn("Email: sales@company.vn")
        assert "sales@company.vn" in result["emails"]

    def test_email_filter_false_positives(self):
        result = self._fn("icon@image.png, style@file.css, real@email.com")
        assert "real@email.com" in result["emails"]
        assert not any(e.endswith(".png") for e in result["emails"])
        assert not any(e.endswith(".css") for e in result["emails"])

    def test_email_max_limit(self):
        text = " ".join([f"user{i}@example.com" for i in range(10)])
        result = self._fn(text)
        assert len(result["emails"]) <= 3

    def test_address_vietnamese(self):
        result = self._fn("Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM")
        assert "123 Nguyễn Huệ" in result["address"]

    def test_address_tru_so(self):
        result = self._fn("Trụ sở: Tầng 5, 456 Lê Lợi, Hà Nội")
        assert result["address"] != ""

    def test_address_too_short_ignored(self):
        result = self._fn("Địa chỉ: HN")
        assert result["address"] == ""

    def test_empty_text(self):
        result = self._fn("")
        assert result["phones"] == []
        assert result["emails"] == []
        assert result["zalo"] == []
        assert result["address"] == ""

    def test_none_text(self):
        result = self._fn(None)
        assert result["phones"] == []

    def test_mixed_contacts(self):
        text = """
        Công ty TNHH ABC
        SĐT: 0901234567
        Zalo: 0912345678
        Email: info@abc.vn
        Địa chỉ: 100 Trần Hưng Đạo, Q5, TP.HCM
        """
        result = self._fn(text)
        assert len(result["phones"]) >= 1
        assert len(result["zalo"]) >= 1
        assert len(result["emails"]) >= 1
        assert result["address"] != ""

    def test_no_contacts_in_text(self):
        result = self._fn("This is a product description with no contact info.")
        assert result["phones"] == []
        assert result["emails"] == []
        assert result["zalo"] == []


# =============================================================================
# Jina Reader Fetch Tests
# =============================================================================

class TestFetchPageMarkdown:
    """Test _fetch_page_markdown()."""

    @patch("app.engine.tools.dealer_search_tool.httpx")
    def test_successful_fetch(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Page Title\nContent here"
        mock_httpx.get.return_value = mock_resp

        from app.engine.tools.dealer_search_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com")
        assert "Page Title" in result

    @patch("app.engine.tools.dealer_search_tool.httpx")
    def test_failed_fetch_500(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_httpx.get.return_value = mock_resp

        from app.engine.tools.dealer_search_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com")
        assert result == ""

    @patch("app.engine.tools.dealer_search_tool.httpx")
    def test_fetch_timeout(self, mock_httpx):
        import httpx as real_httpx
        mock_httpx.TimeoutException = real_httpx.TimeoutException
        mock_httpx.get.side_effect = real_httpx.TimeoutException("Timeout")

        from app.engine.tools.dealer_search_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com")
        assert result == ""

    @patch("app.engine.tools.dealer_search_tool.httpx")
    def test_content_truncation(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "x" * 30000
        mock_httpx.get.return_value = mock_resp

        from app.engine.tools.dealer_search_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com")
        assert len(result) == 20000  # Sprint 198b: 10k → 20k


# =============================================================================
# Search Pipeline Tests
# =============================================================================

@patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False)
class TestSearchDealers:
    """Test _search_dealers() — DuckDuckGo fallback path (Sprint 198: Serper disabled)."""

    @patch("app.engine.tools.dealer_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    def test_successful_search(self, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://dealer1.vn", "title": "Đại lý ABC", "body": "SĐT 0901234567"},
            {"href": "https://dealer2.vn", "title": "NPP XYZ", "body": "info@xyz.vn"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = "Liên hệ: 0901234567, Email: sales@abc.vn"

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("Zebra ZXP7 printhead")
        assert result["count"] >= 1
        assert len(result["dealers"]) >= 1

    @patch("duckduckgo_search.DDGS")
    def test_empty_ddg_results(self, mock_ddgs_cls, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("nonexistent product xyz")
        assert result["dealers"] == []
        assert result["count"] == 0

    @patch("duckduckgo_search.DDGS")
    def test_ddg_exception_handled(self, mock_ddgs_cls, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.side_effect = Exception("Network error")
        mock_ddgs_cls.return_value = mock_ddgs

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        assert result["dealers"] == []
        assert result["count"] == 0

    @patch("app.engine.tools.dealer_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    def test_contacts_first_sort(self, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://nocontact.com", "title": "No Contact", "body": "Just text"},
            {"href": "https://hascontact.vn", "title": "Has Contact", "body": "Call 0901234567"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.side_effect = lambda url: (
            "SĐT: 0901234567" if "hascontact" in url else "No info"
        )

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        if result["count"] >= 2:
            assert result["dealers"][0]["has_contact_info"]

    @patch("app.engine.tools.dealer_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    def test_url_deduplication(self, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        # Same URL returned by both queries
        mock_ddgs.text.return_value = [
            {"href": "https://same.vn", "title": "Same Page", "body": "Info"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = ""

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        # Should not have duplicate URLs
        urls = [d["url"] for d in result["dealers"]]
        assert len(urls) == len(set(urls))

    @patch("app.engine.tools.dealer_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    def test_jina_failure_uses_snippet(self, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://dealer.vn", "title": "Dealer", "body": "Call 0901234567"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = ""  # Jina fails

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        assert result["count"] >= 1
        # Should still extract contacts from snippet
        dealer = result["dealers"][0]
        assert "0901234567" in dealer["contacts"]["phones"]

    @patch("app.engine.tools.dealer_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    def test_max_pages_limit(self, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        # Return 20 results
        mock_ddgs.text.return_value = [
            {"href": f"https://site{i}.vn", "title": f"Site {i}", "body": "Info"}
            for i in range(20)
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = ""

        from app.engine.tools.dealer_search_tool import _search_dealers
        result = _search_dealers("test product")
        # Should cap at 8 pages fetched
        assert result["count"] <= 8


# =============================================================================
# Tool Function Tests
# =============================================================================

class TestToolDealerSearchFn:
    """Test tool_dealer_search_fn()."""

    @patch("app.core.config.get_settings")
    def test_gate_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(enable_dealer_search=False)

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("test product"))
        assert "error" in result
        assert result["count"] == 0

    @patch("app.engine.tools.dealer_search_tool._search_dealers")
    @patch("app.core.config.get_settings")
    def test_gate_enabled_success(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_dealer_search=True)
        mock_search.return_value = {
            "dealers": [{"name": "ABC Corp", "url": "https://abc.vn", "contacts": {}}],
            "count": 1,
            "query": "test",
        }

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("test product"))
        assert result["count"] == 1
        assert len(result["dealers"]) == 1

    @patch("app.engine.tools.dealer_search_tool._search_dealers")
    @patch("app.core.config.get_settings")
    def test_exception_handling(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_dealer_search=True)
        mock_search.side_effect = RuntimeError("Unexpected error")

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("test product"))
        assert "error" in result
        assert result["count"] == 0

    @patch("app.engine.tools.dealer_search_tool._search_dealers")
    @patch("app.core.config.get_settings")
    def test_vietnamese_product_name(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_dealer_search=True)
        mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("đầu in Zebra ZXP Series 7"))
        assert "error" not in result

    @patch("app.engine.tools.dealer_search_tool._search_dealers")
    @patch("app.core.config.get_settings")
    def test_custom_location(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_dealer_search=True)
        mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("Zebra printer", location="Singapore"))
        assert "error" not in result

    @patch("app.engine.tools.dealer_search_tool._search_dealers")
    @patch("app.core.config.get_settings")
    def test_return_format(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_dealer_search=True)
        mock_search.return_value = {
            "dealers": [
                {
                    "name": "Test Dealer",
                    "url": "https://test.vn",
                    "snippet": "Info",
                    "contacts": {"phones": ["0901234567"], "emails": [], "zalo": [], "address": ""},
                    "has_contact_info": True,
                }
            ],
            "count": 1,
            "query": "test query",
            "total_pages_scanned": 5,
        }

        from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
        result = json.loads(tool_dealer_search_fn("test"))
        assert "dealers" in result
        assert "count" in result
        assert isinstance(result["dealers"], list)


# =============================================================================
# StructuredTool Tests
# =============================================================================

class TestGetDealerSearchTool:
    """Test get_dealer_search_tool()."""

    def test_tool_name(self):
        from app.engine.tools.dealer_search_tool import get_dealer_search_tool
        tool = get_dealer_search_tool()
        assert tool.name == "tool_dealer_search"

    def test_tool_description_vietnamese(self):
        from app.engine.tools.dealer_search_tool import get_dealer_search_tool
        tool = get_dealer_search_tool()
        assert "đại lý" in tool.description.lower() or "phân phối" in tool.description.lower()
