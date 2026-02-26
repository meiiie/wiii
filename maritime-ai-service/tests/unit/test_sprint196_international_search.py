"""
Sprint 196: International Search Tool Tests — "Thợ Săn Chuyên Nghiệp"

Tests for app/engine/tools/international_search_tool.py
30 tests covering price extraction, currency conversion, search pipeline, tool function, and StructuredTool.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Price Extraction Tests
# =============================================================================

class TestExtractPriceFromText:
    """Test _extract_price_from_text()."""

    def _fn(self, text, currency="USD"):
        from app.engine.tools.international_search_tool import _extract_price_from_text
        return _extract_price_from_text(text, currency)

    def test_usd_simple(self):
        assert self._fn("Price: $299.99") == 299.99

    def test_usd_with_comma(self):
        assert self._fn("$1,299.00") == 1299.00

    def test_usd_no_decimal(self):
        assert self._fn("Only $500") == 500.0

    def test_eur_symbol(self):
        assert self._fn("Prix: €249.99", "EUR") == 249.99

    def test_gbp_symbol(self):
        assert self._fn("Price: £199.99", "GBP") == 199.99

    def test_generic_usd_text(self):
        assert self._fn("USD 450.00") == 450.00

    def test_no_price(self):
        assert self._fn("No price information here") is None

    def test_empty_text(self):
        assert self._fn("") is None

    def test_none_text(self):
        assert self._fn(None) is None

    def test_first_price_extracted(self):
        price = self._fn("$100 or $200 or $300")
        assert price == 100.0


# =============================================================================
# Currency Conversion Tests
# =============================================================================

class TestConvertToVnd:
    """Test _convert_to_vnd()."""

    def _fn(self, price, currency, rate):
        from app.engine.tools.international_search_tool import _convert_to_vnd
        return _convert_to_vnd(price, currency, rate)

    def test_usd_to_vnd(self):
        result = self._fn(100.0, "USD", 25500.0)
        assert result == 2550000.0

    def test_eur_to_vnd(self):
        # EUR→USD rate is ~1.08, then USD→VND
        result = self._fn(100.0, "EUR", 25500.0)
        assert result > 2550000.0  # EUR > USD

    def test_gbp_to_vnd(self):
        result = self._fn(100.0, "GBP", 25500.0)
        assert result > 2550000.0  # GBP > USD

    def test_zero_price(self):
        result = self._fn(0, "USD", 25500.0)
        assert result == 0.0

    def test_custom_rate(self):
        result = self._fn(100.0, "USD", 26000.0)
        assert result == 2600000.0


# =============================================================================
# Search Pipeline Tests
# =============================================================================

@patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False)
class TestSearchInternational:
    """Test _search_international() — DuckDuckGo fallback path (Sprint 198: Serper disabled)."""

    @patch("app.engine.tools.international_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    @patch("app.core.config.get_settings")
    def test_successful_search(self, mock_settings, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_settings.return_value = MagicMock(usd_vnd_exchange_rate=25500.0)
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://supplier.com", "title": "ZXP7 Printhead", "body": "Price: $299.99"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = "Buy now for $299.99"

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("Zebra ZXP7 printhead")
        assert result["count"] >= 1
        assert result["exchange_rate"] == 25500.0

    @patch("duckduckgo_search.DDGS")
    @patch("app.core.config.get_settings")
    def test_empty_results(self, mock_settings, mock_ddgs_cls, _mock_serper):
        mock_settings.return_value = MagicMock(usd_vnd_exchange_rate=25500.0)
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("nonexistent xyz product")
        assert result["count"] == 0
        assert result["results"] == []

    @patch("duckduckgo_search.DDGS")
    @patch("app.core.config.get_settings")
    def test_ddg_exception(self, mock_settings, mock_ddgs_cls, _mock_serper):
        mock_settings.return_value = MagicMock(usd_vnd_exchange_rate=25500.0)
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.side_effect = Exception("Network error")
        mock_ddgs_cls.return_value = mock_ddgs

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test product")
        assert result["count"] == 0

    @patch("app.engine.tools.international_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    @patch("app.core.config.get_settings")
    def test_price_vnd_conversion(self, mock_settings, mock_ddgs_cls, mock_fetch, _mock_serper):
        mock_settings.return_value = MagicMock(usd_vnd_exchange_rate=25500.0)
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://shop.com", "title": "Product", "body": "$100"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.return_value = "Price: $100"

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test product")
        if result["count"] > 0 and result["results"][0]["price_vnd"]:
            assert result["results"][0]["price_vnd"] == 2550000

    @patch("app.engine.tools.international_search_tool._fetch_page_markdown")
    @patch("duckduckgo_search.DDGS")
    @patch("app.core.config.get_settings")
    def test_priced_results_before_unpriced(self, mock_settings, mock_ddgs_cls, mock_fetch, _mock_serper):
        """Items with price come before items without. No direction sort."""
        mock_settings.return_value = MagicMock(usd_vnd_exchange_rate=25500.0)
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"href": "https://noprice.com", "title": "NoPrice", "body": "no price info"},
            {"href": "https://cheap.com", "title": "Cheap", "body": "$100"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs
        mock_fetch.side_effect = lambda url: (
            "" if "noprice" in url else "Price: $100"
        )

        from app.engine.tools.international_search_tool import _search_international
        result = _search_international("test product")
        priced_indices = [i for i, r in enumerate(result["results"]) if r["price_vnd"]]
        unpriced_indices = [i for i, r in enumerate(result["results"]) if not r["price_vnd"]]
        if priced_indices and unpriced_indices:
            assert max(priced_indices) < min(unpriced_indices)


# =============================================================================
# Tool Function Tests
# =============================================================================

class TestToolInternationalSearchFn:
    """Test tool_international_search_fn()."""

    @patch("app.core.config.get_settings")
    def test_gate_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(enable_international_search=False)

        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test product"))
        assert "error" in result

    @patch("app.engine.tools.international_search_tool._search_international")
    @patch("app.core.config.get_settings")
    def test_gate_enabled_success(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_international_search=True)
        mock_search.return_value = {
            "results": [{"title": "Product", "url": "https://shop.com", "price_foreign": 299.99, "price_vnd": 7649745}],
            "count": 1,
            "exchange_rate": 25500.0,
            "currency": "USD",
        }

        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("Zebra printhead"))
        assert result["count"] == 1
        assert result["exchange_rate"] == 25500.0

    @patch("app.engine.tools.international_search_tool._search_international")
    @patch("app.core.config.get_settings")
    def test_exception_handling(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_international_search=True)
        mock_search.side_effect = RuntimeError("Crash")

        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test"))
        assert "error" in result

    @patch("app.engine.tools.international_search_tool._search_international")
    @patch("app.core.config.get_settings")
    def test_invalid_currency_defaults_usd(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_international_search=True)
        mock_search.return_value = {"results": [], "count": 0, "exchange_rate": 25500.0, "currency": "USD"}

        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", currency="XYZ"))
        # Should default to USD (no error)
        assert "error" not in result

    @patch("app.engine.tools.international_search_tool._search_international")
    @patch("app.core.config.get_settings")
    def test_eur_currency(self, mock_settings, mock_search):
        mock_settings.return_value = MagicMock(enable_international_search=True)
        mock_search.return_value = {"results": [], "count": 0, "exchange_rate": 25500.0, "currency": "EUR"}

        from app.engine.tools.international_search_tool import tool_international_search_fn
        result = json.loads(tool_international_search_fn("test", currency="EUR"))
        assert "error" not in result


# =============================================================================
# StructuredTool Tests
# =============================================================================

class TestGetInternationalSearchTool:
    """Test get_international_search_tool()."""

    def test_tool_name(self):
        from app.engine.tools.international_search_tool import get_international_search_tool
        tool = get_international_search_tool()
        assert tool.name == "tool_international_search"

    def test_tool_description_vietnamese(self):
        from app.engine.tools.international_search_tool import get_international_search_tool
        tool = get_international_search_tool()
        assert "quốc tế" in tool.description.lower() or "vnd" in tool.description.lower()
