"""
Sprint 196: Contact Extraction Tool Tests — "Thợ Săn Chuyên Nghiệp"

Tests for app/engine/tools/contact_extraction_tool.py
30 tests covering regex patterns, address extraction, page fetch, tool function, and StructuredTool.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Contact Extraction Pattern Tests
# =============================================================================

class TestExtractAllContacts:
    """Test _extract_all_contacts()."""

    def _fn(self, text):
        from app.engine.tools.contact_extraction_tool import _extract_all_contacts
        return _extract_all_contacts(text)

    def test_vn_phone_standard(self):
        result = self._fn("SĐT: 0901234567")
        assert "0901234567" in result["phones"]

    def test_vn_phone_landline(self):
        result = self._fn("Tel: 02812345678")
        assert "02812345678" in result["phones"]

    def test_multiple_vn_phones(self):
        result = self._fn("Hotline: 0901234567 / 0912345678 / 0938765432")
        assert len(result["phones"]) == 3

    def test_intl_phone_plus84(self):
        result = self._fn("Phone: +84 901 234 567")
        assert len(result["international_phones"]) >= 1

    def test_intl_phone_plus1(self):
        result = self._fn("US Office: +1 555 123 4567")
        assert len(result["international_phones"]) >= 1

    def test_email_standard(self):
        result = self._fn("Email: contact@company.vn")
        assert "contact@company.vn" in result["emails"]

    def test_email_multiple(self):
        result = self._fn("sales@abc.com, support@abc.com")
        assert len(result["emails"]) == 2

    def test_email_filter_images(self):
        result = self._fn("bg@image.png icon@file.jpg real@company.com")
        assert "real@company.com" in result["emails"]
        assert not any(e.endswith(".png") for e in result["emails"])
        assert not any(e.endswith(".jpg") for e in result["emails"])

    def test_email_max_limit(self):
        text = " ".join([f"user{i}@example.com" for i in range(10)])
        result = self._fn(text)
        assert len(result["emails"]) <= 5

    def test_zalo_colon(self):
        result = self._fn("Zalo: 0901234567")
        assert "0901234567" in result["zalo"]

    def test_zalo_case_insensitive(self):
        result = self._fn("ZALO: 0912345678")
        assert "0912345678" in result["zalo"]

    def test_viber_pattern(self):
        result = self._fn("Viber: +84901234567")
        assert len(result["viber"]) >= 1

    def test_facebook_page(self):
        result = self._fn("Facebook: facebook.com/dealerpage")
        assert any("dealerpage" in f for f in result["facebook"])

    def test_fb_com_short(self):
        result = self._fn("Visit fb.com/myshop")
        assert any("myshop" in f for f in result["facebook"])

    def test_empty_text(self):
        result = self._fn("")
        assert result["phones"] == []
        assert result["emails"] == []
        assert result["zalo"] == []
        assert result["viber"] == []
        assert result["facebook"] == []
        assert result["address"] == ""

    def test_phone_deduplication(self):
        result = self._fn("0901234567 0901234567 0901234567")
        assert result["phones"].count("0901234567") == 1

    def test_all_contact_types(self):
        text = """
        Công ty ABC
        SĐT: 0901234567, +84 912 345 678
        Zalo: 0938765432
        Viber: +84901234567
        Email: info@abc.vn
        Facebook: facebook.com/abcdealer
        Địa chỉ: 123 Nguyễn Huệ, Q1, TP.HCM
        """
        result = self._fn(text)
        assert len(result["phones"]) >= 1
        assert len(result["emails"]) >= 1
        assert len(result["zalo"]) >= 1
        assert len(result["facebook"]) >= 1
        assert result["address"] != ""


# =============================================================================
# Address Extraction Tests
# =============================================================================

class TestExtractAddress:
    """Test _extract_address()."""

    def _fn(self, text):
        from app.engine.tools.contact_extraction_tool import _extract_address
        return _extract_address(text)

    def test_dia_chi_keyword(self):
        result = self._fn("Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM")
        assert "123 Nguyễn Huệ" in result

    def test_tru_so_keyword(self):
        result = self._fn("Trụ sở: Lầu 5, Tòa nhà ABC, Đường Lê Lợi, Hà Nội")
        assert "Lê Lợi" in result

    def test_address_keyword(self):
        result = self._fn("Address: 456 Tran Hung Dao, Da Nang")
        assert "Tran Hung Dao" in result

    def test_too_short_ignored(self):
        result = self._fn("Địa chỉ: HN")
        assert result == ""

    def test_no_address(self):
        result = self._fn("This is a product listing page with specs only.")
        assert result == ""


# =============================================================================
# Page Fetch Tests
# =============================================================================

class TestFetchPageMarkdownContact:
    """Test _fetch_page_markdown()."""

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_successful_fetch(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Page\nContent with contacts"
        mock_httpx.get.return_value = mock_resp

        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com")
        assert "Content" in result

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_http_error(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_httpx.get.return_value = mock_resp

        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://example.com/404")
        assert result == ""

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_timeout(self, mock_httpx):
        import httpx as real_httpx
        mock_httpx.TimeoutException = real_httpx.TimeoutException
        mock_httpx.get.side_effect = real_httpx.TimeoutException("Connection timed out")

        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        result = _fetch_page_markdown("https://slow.example.com")
        assert result == ""


# =============================================================================
# Tool Function Tests
# =============================================================================

class TestToolExtractContactsFn:
    """Test tool_extract_contacts_fn()."""

    @patch("app.core.config.get_settings")
    def test_gate_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(enable_contact_extraction=False)

        from app.engine.tools.contact_extraction_tool import tool_extract_contacts_fn
        result = json.loads(tool_extract_contacts_fn("https://example.com"))
        assert "error" in result

    @patch("app.engine.tools.contact_extraction_tool._fetch_page_markdown")
    @patch("app.core.config.get_settings")
    def test_gate_enabled_success(self, mock_settings, mock_fetch):
        mock_settings.return_value = MagicMock(enable_contact_extraction=True)
        mock_fetch.return_value = "SĐT: 0901234567, Email: info@test.vn"

        from app.engine.tools.contact_extraction_tool import tool_extract_contacts_fn
        result = json.loads(tool_extract_contacts_fn("https://dealer.vn"))
        assert "contacts" in result
        assert result["total_contact_methods"] >= 2

    @patch("app.core.config.get_settings")
    def test_invalid_url(self, mock_settings):
        mock_settings.return_value = MagicMock(enable_contact_extraction=True)

        from app.engine.tools.contact_extraction_tool import tool_extract_contacts_fn
        result = json.loads(tool_extract_contacts_fn("not-a-url"))
        assert "error" in result

    @patch("app.engine.tools.contact_extraction_tool._fetch_page_markdown")
    @patch("app.core.config.get_settings")
    def test_page_fetch_fails(self, mock_settings, mock_fetch):
        mock_settings.return_value = MagicMock(enable_contact_extraction=True)
        mock_fetch.return_value = ""

        from app.engine.tools.contact_extraction_tool import tool_extract_contacts_fn
        result = json.loads(tool_extract_contacts_fn("https://example.com"))
        assert "error" in result

    @patch("app.engine.tools.contact_extraction_tool._fetch_page_markdown")
    @patch("app.core.config.get_settings")
    def test_total_contact_methods_count(self, mock_settings, mock_fetch):
        mock_settings.return_value = MagicMock(enable_contact_extraction=True)
        mock_fetch.return_value = "0901234567 info@test.vn Zalo: 0912345678"

        from app.engine.tools.contact_extraction_tool import tool_extract_contacts_fn
        result = json.loads(tool_extract_contacts_fn("https://example.com"))
        assert result["total_contact_methods"] >= 3


# =============================================================================
# StructuredTool Tests
# =============================================================================

class TestGetContactExtractionTool:
    """Test get_contact_extraction_tool()."""

    def test_tool_name(self):
        from app.engine.tools.contact_extraction_tool import get_contact_extraction_tool
        tool = get_contact_extraction_tool()
        assert tool.name == "tool_extract_contacts"

    def test_tool_description_vietnamese(self):
        from app.engine.tools.contact_extraction_tool import get_contact_extraction_tool
        tool = get_contact_extraction_tool()
        assert "liên hệ" in tool.description.lower() or "trích xuất" in tool.description.lower()
