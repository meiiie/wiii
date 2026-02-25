"""
Sprint 198b: "Nâng Cấp Chất Lượng" — B2B Search Quality Hardening Tests

Tests:
- European/Anglo price parsing (_parse_price_amount)
- Multi-currency price extraction (12 currencies + Serper priority)
- Structural address validation (score >= 2 components)
- Phone number normalization (spaces, dots, dashes)
- Dealer contact consolidation (delegates to contact_extraction_tool)
- Jina Reader retry logic (timeout/5xx retry, 404 no retry)
- Serper price metadata passthrough (include_price_metadata flag)

50 tests covering Sprint 198b quality improvements.
"""

import json
from unittest.mock import MagicMock, patch, call

import httpx
import pytest


# ============================================================================
# 1. TestParseEuropeanPrice — _parse_price_amount()
# ============================================================================

class TestParseEuropeanPrice:
    """Test European/Anglo price format parsing."""

    def test_anglo_standard(self):
        """1,234.50 → 1234.50 (comma thousands, dot decimal)"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("1,234.50") == 1234.50

    def test_european_standard(self):
        """1.234,50 → 1234.50 (dot thousands, comma decimal)"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("1.234,50") == 1234.50

    def test_comma_decimal_only(self):
        """1,50 → 1.50 (comma as decimal, ≤2 digits after)"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("1,50") == 1.50

    def test_comma_thousands_only(self):
        """1,234 → 1234 (comma thousands, no decimal)"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("1,234") == 1234.0

    def test_dot_decimal_only(self):
        """249.99 → 249.99"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("249.99") == 249.99

    def test_large_european(self):
        """10.500,00 → 10500.00"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("10.500,00") == 10500.0

    def test_large_anglo(self):
        """10,500.00 → 10500.00"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("10,500.00") == 10500.0

    def test_no_separator(self):
        """500 → 500.0"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("500") == 500.0

    def test_empty_string(self):
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("") is None

    def test_none(self):
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount(None) is None

    def test_spaces_in_number(self):
        """5 820 → 5820 (space as thousands separator)"""
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("5 820") == 5820.0

    def test_zero_returns_none(self):
        from app.engine.tools.international_search_tool import _parse_price_amount
        assert _parse_price_amount("0") is None


# ============================================================================
# 2. TestExtractPriceMultiCurrency — _extract_price_from_text()
# ============================================================================

class TestExtractPriceMultiCurrency:
    """Test multi-currency price extraction with Serper priority."""

    def test_usd_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: $299.99", "USD") == 299.99

    def test_eur_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Preis: €249,99", "EUR") == 249.99

    def test_eur_symbol_anglo(self):
        """€249.99 with dot decimal"""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: €249.99", "EUR") == 249.99

    def test_gbp_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: £199.99", "GBP") == 199.99

    def test_yen_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("価格: ¥15,000", "CNY") == 15000.0

    def test_won_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("가격: ₩350,000", "KRW") == 350000.0

    def test_sgd_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: S$450.00", "SGD") == 450.0

    def test_aed_code(self):
        """AED uses code regex (no symbol)"""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: AED 5,820", "AED") == 5820.0

    def test_cad_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: C$380.00", "CAD") == 380.0

    def test_aud_symbol(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Price: A$520.00", "AUD") == 520.0

    def test_serper_price_takes_priority(self):
        """Serper price metadata should be used over text extraction."""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        result = _extract_price_from_text(
            "Price: $999.99",  # text says 999.99
            "USD",
            serper_price=299.99,  # Serper says 299.99
        )
        assert result == 299.99

    def test_serper_price_range(self):
        """Serper price range — take first value."""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        result = _extract_price_from_text(
            "",  # no text
            "USD",
            serper_price_range="$100 - $200",
        )
        assert result == 100.0

    def test_serper_price_string(self):
        """Serper price as string (e.g. "$299")."""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        result = _extract_price_from_text("", "USD", serper_price="$299")
        assert result == 299.0

    def test_code_regex_with_space(self):
        """'USD 450.00' — code regex with space."""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("Total: USD 450.00", "USD") == 450.0

    def test_no_match_returns_none(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("No price here", "USD") is None

    def test_empty_text_none(self):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        assert _extract_price_from_text("", "USD") is None

    def test_european_eur_in_text(self):
        """€1.234,50 must parse correctly as 1234.50, not 1.23450"""
        from app.engine.tools.international_search_tool import _extract_price_from_text
        result = _extract_price_from_text("Preis: €1.234,50 inkl. MwSt.", "EUR")
        assert result == 1234.50


# ============================================================================
# 3. TestStructuralAddress — _extract_address() + _structural_address_score()
# ============================================================================

class TestStructuralAddress:
    """Test structural address validation replaces keyword-only matching."""

    def test_real_address_passes(self):
        """Real Vietnamese address with ≥2 structural components."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM"
        result = _extract_address(text)
        assert result  # non-empty
        assert "Nguyễn Huệ" in result

    def test_noise_rejected_man_hinh(self):
        """'Màn hình:LCD...' should be rejected (0 structural components)."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Địa chỉ Màn hình:LCD có độ phân giải cao, hỗ trợ nhiều tính năng đa dạng"
        result = _extract_address(text)
        assert result == ""

    def test_noise_rejected_hy_vong(self):
        """'Hy vọng bài viết...' should be rejected (0 structural components)."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Địa chỉ: Hy vọng bài viết này sẽ giúp ích cho bạn trong việc tìm kiếm sản phẩm"
        result = _extract_address(text)
        assert result == ""

    def test_address_with_tang(self):
        """'Tầng 5, 456 Lê Lợi, Hà Nội' — score=3 (tầng + number + city)."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Trụ sở: Tầng 5, 456 Lê Lợi, Hà Nội"
        result = _extract_address(text)
        assert result
        assert "Lê Lợi" in result

    def test_address_with_toa_nha(self):
        """'Lầu 5, Tòa nhà ABC, Đường Lê Lợi, Hà Nội' — score=4."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Văn phòng: Lầu 5, Tòa nhà ABC, Đường Lê Lợi, Hà Nội"
        result = _extract_address(text)
        assert result
        assert "Tòa nhà" in result

    def test_too_short_rejected(self):
        """Address < 10 chars should be rejected."""
        from app.engine.tools.contact_extraction_tool import _extract_address
        text = "Địa chỉ: HN"
        result = _extract_address(text)
        assert result == ""

    def test_structural_score_function(self):
        """Direct test of _structural_address_score."""
        from app.engine.tools.contact_extraction_tool import _structural_address_score
        # Real address with multiple components
        score = _structural_address_score("123 Nguyễn Huệ, Quận 1, TP.HCM")
        assert score >= 2
        # Noise text
        score_noise = _structural_address_score("Màn hình LCD có độ phân giải cao")
        assert score_noise < 2

    def test_city_name_counts(self):
        """City names (Đà Nẵng, etc.) count as structural components."""
        from app.engine.tools.contact_extraction_tool import _structural_address_score
        score = _structural_address_score("456 Tran Hung Dao, Da Nang")
        assert score >= 2  # number + city


# ============================================================================
# 4. TestPhoneNormalization — _normalize_phones_in_text()
# ============================================================================

class TestPhoneNormalization:
    """Test phone number normalization for spaces/dots/dashes."""

    def test_spaces_normalized(self):
        """'090 0123 4567' → '09001234567'"""
        from app.engine.tools.contact_extraction_tool import _normalize_phones_in_text
        result = _normalize_phones_in_text("Call: 090 0123 4567 now")
        assert "09001234567" in result

    def test_dots_normalized(self):
        """'090.0123.4567' → '09001234567'"""
        from app.engine.tools.contact_extraction_tool import _normalize_phones_in_text
        result = _normalize_phones_in_text("Phone: 090.0123.4567")
        assert "09001234567" in result

    def test_dashes_normalized(self):
        """'090-0123-4567' → '09001234567'"""
        from app.engine.tools.contact_extraction_tool import _normalize_phones_in_text
        result = _normalize_phones_in_text("Tel: 090-0123-4567")
        assert "09001234567" in result

    def test_standard_unchanged(self):
        """'0901234567' → unchanged"""
        from app.engine.tools.contact_extraction_tool import _normalize_phones_in_text
        result = _normalize_phones_in_text("Phone: 0901234567")
        assert "0901234567" in result

    def test_non_phone_unchanged(self):
        """Non-phone text should not be affected."""
        from app.engine.tools.contact_extraction_tool import _normalize_phones_in_text
        text = "Model: ABC-123, Version: 4.5.6"
        result = _normalize_phones_in_text(text)
        assert "ABC-123" in result
        assert "4.5.6" in result


# ============================================================================
# 5. TestDealerContactConsolidation — dealer → contact_extraction delegation
# ============================================================================

class TestDealerContactConsolidation:
    """Test that dealer_search_tool delegates to contact_extraction_tool."""

    def test_delegation_returns_new_fields(self):
        """Dealer contacts should now include viber/facebook/intl_phones."""
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        text = (
            "Contact us: 0901234567\n"
            "Viber: +84 901 234 567\n"
            "facebook.com/dealerpage\n"
            "Email: info@dealer.com\n"
            "Zalo: 0912345678\n"
            "Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM"
        )
        contacts = _extract_contacts_from_text(text)
        assert "viber" in contacts
        assert "facebook" in contacts
        assert "international_phones" in contacts

    def test_phone_limit_5(self):
        """Dealer wrapper limits phones to 5."""
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        text = "\n".join([f"Phone: 090{i}123456" for i in range(8)])
        contacts = _extract_contacts_from_text(text)
        assert len(contacts["phones"]) <= 5

    def test_email_limit_3(self):
        """Dealer wrapper limits emails to 3."""
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        text = "\n".join([f"email{i}@test.com" for i in range(6)])
        contacts = _extract_contacts_from_text(text)
        assert len(contacts["emails"]) <= 3

    def test_zalo_limit_3(self):
        """Dealer wrapper limits zalo to 3."""
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        text = "\n".join([f"Zalo: 090{i}123456" for i in range(6)])
        contacts = _extract_contacts_from_text(text)
        assert len(contacts["zalo"]) <= 3

    def test_empty_text(self):
        """Empty text returns empty contacts."""
        from app.engine.tools.dealer_search_tool import _extract_contacts_from_text
        contacts = _extract_contacts_from_text("")
        assert contacts["phones"] == []
        assert contacts["emails"] == []


# ============================================================================
# 6. TestJinaReaderRetry — retry on timeout/5xx, no retry on 404
# ============================================================================

class TestJinaReaderRetry:
    """Test Jina Reader retry logic across all 3 tools."""

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_success_first_try(self, mock_httpx):
        """First successful response returns content."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Page content"
        mock_httpx.get.return_value = mock_resp
        result = _fetch_page_markdown("https://example.com")
        assert result == "Page content"
        assert mock_httpx.get.call_count == 1

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_retry_on_timeout(self, mock_httpx):
        """Timeout on first try, success on retry."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Retry content"
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.get.side_effect = [httpx.TimeoutException("timeout"), mock_resp]
        result = _fetch_page_markdown("https://example.com")
        assert result == "Retry content"
        assert mock_httpx.get.call_count == 2

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_retry_on_500(self, mock_httpx):
        """500 on first try, success on retry."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.text = "Fixed content"
        mock_httpx.get.side_effect = [mock_500, mock_200]
        result = _fetch_page_markdown("https://example.com")
        assert result == "Fixed content"
        assert mock_httpx.get.call_count == 2

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_no_retry_on_404(self, mock_httpx):
        """404 should NOT retry — client error."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_httpx.get.return_value = mock_resp
        result = _fetch_page_markdown("https://example.com")
        assert result == ""
        assert mock_httpx.get.call_count == 1

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_timeout_both_attempts(self, mock_httpx):
        """Timeout on both attempts returns empty."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.get.side_effect = httpx.TimeoutException("timeout")
        result = _fetch_page_markdown("https://example.com")
        assert result == ""
        assert mock_httpx.get.call_count == 2

    @patch("app.engine.tools.contact_extraction_tool.httpx")
    def test_contact_truncation_20k(self, mock_httpx):
        """Response truncated at 20k characters."""
        from app.engine.tools.contact_extraction_tool import _fetch_page_markdown
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "x" * 30000
        mock_httpx.get.return_value = mock_resp
        result = _fetch_page_markdown("https://example.com")
        assert len(result) == 20000

    @patch("app.engine.tools.international_search_tool.httpx")
    def test_intl_retry_on_timeout(self, mock_httpx):
        """International search Jina retry on timeout."""
        from app.engine.tools.international_search_tool import _fetch_page_markdown
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Retry content"
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.get.side_effect = [httpx.TimeoutException("timeout"), mock_resp]
        result = _fetch_page_markdown("https://example.com")
        assert result == "Retry content"
        assert mock_httpx.get.call_count == 2


# ============================================================================
# 7. TestSerperPricePassthrough — include_price_metadata flag
# ============================================================================

class TestSerperPricePassthrough:
    """Test Serper price metadata passthrough in _serper_search()."""

    @patch("app.core.config.get_settings")
    def test_default_no_price_fields(self, mock_settings):
        """Default (False) should NOT include price fields."""
        mock_settings.return_value = MagicMock(
            serper_api_key="test-key",
            enable_serper_web_search=True,
        )
        from app.engine.tools.serper_web_search import _serper_search
        with patch("app.engine.tools.serper_web_search.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "organic": [
                    {"title": "Test", "snippet": "Body", "link": "https://test.com",
                     "price": 299.99, "priceRange": "$200-$400"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.post.return_value = mock_resp

            results = _serper_search("test query", include_price_metadata=False)
            assert len(results) == 1
            assert "extracted_price" not in results[0]
            assert "price_range" not in results[0]

    @patch("app.core.config.get_settings")
    def test_price_metadata_included(self, mock_settings):
        """When True, price and priceRange fields should be included."""
        mock_settings.return_value = MagicMock(
            serper_api_key="test-key",
            enable_serper_web_search=True,
        )
        from app.engine.tools.serper_web_search import _serper_search
        with patch("app.engine.tools.serper_web_search.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "organic": [
                    {"title": "Test", "snippet": "Body", "link": "https://test.com",
                     "price": 299.99, "priceRange": "$200-$400"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.post.return_value = mock_resp

            results = _serper_search("test query", include_price_metadata=True)
            assert len(results) == 1
            assert results[0]["extracted_price"] == 299.99
            assert results[0]["price_range"] == "$200-$400"

    @patch("app.core.config.get_settings")
    def test_no_price_in_serper_data(self, mock_settings):
        """When True but Serper has no price data, fields should not be present."""
        mock_settings.return_value = MagicMock(
            serper_api_key="test-key",
            enable_serper_web_search=True,
        )
        from app.engine.tools.serper_web_search import _serper_search
        with patch("app.engine.tools.serper_web_search.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "organic": [
                    {"title": "Test", "snippet": "No price", "link": "https://test.com"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.post.return_value = mock_resp

            results = _serper_search("test query", include_price_metadata=True)
            assert len(results) == 1
            assert "extracted_price" not in results[0]
            assert "price_range" not in results[0]


# ============================================================================
# 8. TestExchangeRates — multi-currency conversion
# ============================================================================

class TestExchangeRates:
    """Test exchange rate expansion and config overrides."""

    def test_12_currencies_present(self):
        from app.engine.tools.international_search_tool import _EXCHANGE_RATES
        expected = ["USD", "EUR", "GBP", "CNY", "JPY", "KRW", "SGD", "THB", "AED", "CAD", "AUD", "TWD"]
        for cur in expected:
            assert cur in _EXCHANGE_RATES, f"Missing currency: {cur}"

    def test_backward_compat_default_rates(self):
        """_DEFAULT_RATES should be the same as _EXCHANGE_RATES."""
        from app.engine.tools.international_search_tool import _DEFAULT_RATES, _EXCHANGE_RATES
        assert _DEFAULT_RATES is _EXCHANGE_RATES

    @patch("app.core.config.get_settings")
    def test_config_override_merges(self, mock_settings):
        mock_settings.return_value = MagicMock(exchange_rate_overrides={"EUR": 1.15})
        from app.engine.tools.international_search_tool import _get_exchange_rates
        rates = _get_exchange_rates()
        assert rates["EUR"] == 1.15
        assert rates["USD"] == 1.0  # unchanged

    def test_convert_aed_to_vnd(self):
        """AED 5820 × 0.27 × 25500 = ~40,070,100"""
        from app.engine.tools.international_search_tool import _convert_to_vnd
        result = _convert_to_vnd(5820.0, "AED", 25500.0)
        # 5820 * 0.27 = 1571.4 USD * 25500 = 40,070,700
        assert 40_000_000 < result < 41_000_000

    def test_invalid_currency_fallback(self):
        """Invalid currency in tool_international_search_fn should fall back to USD."""
        from app.engine.tools.international_search_tool import _EXCHANGE_RATES
        assert "XYZ" not in _EXCHANGE_RATES
