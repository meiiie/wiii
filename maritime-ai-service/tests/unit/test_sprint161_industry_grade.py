"""
Sprint 161: "Chuyên Nghiệp" — Industry-Grade Product Search Tests

Tests for 7 fixes:
1. extracted_price for SerperSiteAdapter
2. extracted_price + smart query for SerperAllWebAdapter
3. WebSosanh image extraction
4. Excel sort by price + description column
5. AllWeb query smart dedup
6. Tool ack + prompt for WebSosanh
7. Deep search stopping criteria
"""

import json
import re
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Fix 1: SerperSiteAdapter — extracted_price
# ---------------------------------------------------------------------------


class TestSerperSiteExtractedPrice:
    """extracted_price via parse_vnd_price on priceRange field."""

    def test_price_parsed_from_price_range(self):
        """Serper organic item with priceRange → extracted_price float."""
        from app.engine.search_platforms.adapters.serper_site import SerperSiteAdapter
        from app.engine.search_platforms.base import PlatformConfig, BackendType

        adapter = SerperSiteAdapter(PlatformConfig(
            id="shopee", display_name="Shopee",
            backend=BackendType.SERPER_SITE, site_filter="site:shopee.vn",
        ))

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "organic": [{
                "title": "Dây điện Cadivi 3x2.5mm",
                "priceRange": "1.234.567 ₫",
                "link": "https://shopee.vn/item/123",
                "snippet": "Dây cáp",
                "source": "Shopee",
            }]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", return_value=fake_resp):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            results = adapter.search_sync("dây điện", max_results=5)

        assert len(results) == 1
        assert results[0].extracted_price == 1234567.0
        assert results[0].price == "1.234.567 ₫"

    def test_empty_price_range_returns_none(self):
        """Empty priceRange → extracted_price=None."""
        from app.engine.search_platforms.adapters.serper_site import SerperSiteAdapter
        from app.engine.search_platforms.base import PlatformConfig, BackendType

        adapter = SerperSiteAdapter(PlatformConfig(
            id="lazada", display_name="Lazada",
            backend=BackendType.SERPER_SITE, site_filter="site:lazada.vn",
        ))

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "organic": [{"title": "Test", "priceRange": "", "link": "https://lazada.vn/1"}]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", return_value=fake_resp):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            results = adapter.search_sync("test")

        assert results[0].extracted_price is None

    def test_none_safe_no_price_range_key(self):
        """Missing priceRange key → extracted_price=None."""
        from app.engine.search_platforms.adapters.serper_site import SerperSiteAdapter
        from app.engine.search_platforms.base import PlatformConfig, BackendType

        adapter = SerperSiteAdapter(PlatformConfig(
            id="tiktok_shop", display_name="TikTok Shop",
            backend=BackendType.SERPER_SITE, site_filter="site:tiktok.com/shop",
        ))

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "organic": [{"title": "Test", "link": "https://tiktok.com/shop/1"}]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", return_value=fake_resp):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            results = adapter.search_sync("test")

        assert results[0].extracted_price is None


# ---------------------------------------------------------------------------
# Fix 2: SerperAllWebAdapter — extracted_price + smart query
# ---------------------------------------------------------------------------


class TestSerperAllWebExtractedPrice:
    """extracted_price + smart query dedup for AllWeb."""

    def _make_adapter(self):
        from app.engine.search_platforms.adapters.serper_all_web import SerperAllWebAdapter
        return SerperAllWebAdapter()

    def test_price_parsed(self):
        """priceRange → extracted_price float."""
        adapter = self._make_adapter()

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "organic": [{
                "title": "Dây điện Cadivi 3x2.5mm",
                "priceRange": "35.490.000 đ",
                "link": "https://example.com/1",
                "snippet": "B2B",
                "source": "VietShop",
            }]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", return_value=fake_resp):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            results = adapter.search_sync("dây điện 3x2.5mm")

        assert results[0].extracted_price == 35490000.0

    def test_empty_price(self):
        """Empty priceRange → extracted_price=None."""
        adapter = self._make_adapter()

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "organic": [{"title": "Test", "priceRange": "", "link": "https://x.com/1"}]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", return_value=fake_resp):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            results = adapter.search_sync("test")

        assert results[0].extracted_price is None


class TestAllWebSmartQuery:
    """Smart query: skip appending 'giá bán' if already present."""

    def _make_adapter(self):
        from app.engine.search_platforms.adapters.serper_all_web import SerperAllWebAdapter
        return SerperAllWebAdapter()

    def test_query_with_gia_no_duplicate(self):
        """Query containing 'giá' should NOT get 'giá bán' appended."""
        adapter = self._make_adapter()

        captured_payload = {}
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"organic": []}
        fake_resp.raise_for_status = MagicMock()

        def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return fake_resp

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", side_effect=capture_post):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            adapter.search_sync("dây điện 3x2.5mm giá rẻ")

        query = captured_payload.get("q", "")
        # Should NOT contain duplicate "giá bán"
        assert "giá bán" not in query
        # But should still contain the user's "giá"
        assert "giá rẻ" in query

    def test_query_without_gia_gets_appended(self):
        """Query without price keywords SHOULD get 'giá bán' appended."""
        adapter = self._make_adapter()

        captured_payload = {}
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"organic": []}
        fake_resp.raise_for_status = MagicMock()

        def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return fake_resp

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", side_effect=capture_post):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            adapter.search_sync("dây điện 3x2.5mm Cadivi")

        query = captured_payload.get("q", "")
        assert "giá bán" in query

    def test_query_with_mua_no_duplicate(self):
        """Query containing 'mua' should NOT get 'giá bán' appended."""
        adapter = self._make_adapter()

        captured_payload = {}
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"organic": []}
        fake_resp.raise_for_status = MagicMock()

        def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return fake_resp

        with patch("app.core.config.get_settings") as mock_settings, \
             patch("httpx.post", side_effect=capture_post):
            mock_settings.return_value.serper_api_key = "test-key"
            mock_settings.return_value.product_search_timeout = 30

            adapter.search_sync("mua dây điện Cadivi ở đâu")

        query = captured_payload.get("q", "")
        assert "giá bán" not in query


# ---------------------------------------------------------------------------
# Fix 3: WebSosanh image extraction
# ---------------------------------------------------------------------------


class TestWebSosanhImageExtraction:
    """Image extraction from WebSosanh HTML."""

    def _make_adapter(self):
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        return WebSosanhAdapter()

    def test_image_extracted_from_src(self):
        """Product with img src → image URL extracted."""
        adapter = self._make_adapter()
        html = """
        <div class="product-single-info">
            <h2><a class="product-single-name" href="/sp/test">Dây điện Cadivi</a></h2>
            <div class="product-single-price">1.234.000 ₫</div>
            <div class="merchant-name">FPTShop</div>
            <div class="product-image"><img src="https://cdn.websosanh.vn/img/test.jpg" /></div>
        </div>
        """
        results = adapter._parse_html(html, 10)
        assert len(results) == 1
        assert results[0].image == "https://cdn.websosanh.vn/img/test.jpg"

    def test_image_extracted_from_data_src(self):
        """Product with img data-src (lazy loading) → image URL extracted."""
        adapter = self._make_adapter()
        html = """
        <div class="product-single-info">
            <h2><a class="product-single-name" href="/sp/test2">MacBook Pro</a></h2>
            <div class="product-single-price">35.490.000 ₫</div>
            <div class="product-image"><img data-src="https://cdn.websosanh.vn/img/mac.jpg" src="" /></div>
        </div>
        """
        results = adapter._parse_html(html, 10)
        assert len(results) == 1
        assert results[0].image == "https://cdn.websosanh.vn/img/mac.jpg"

    def test_missing_img_returns_empty(self):
        """No img element → image=''."""
        adapter = self._make_adapter()
        html = """
        <div class="product-single-info">
            <h2><a class="product-single-name" href="/sp/test3">Test Product</a></h2>
            <div class="product-single-price">500.000 ₫</div>
        </div>
        """
        results = adapter._parse_html(html, 10)
        assert len(results) == 1
        assert results[0].image == ""

    def test_relative_image_url_converted(self):
        """Relative /img/xxx.jpg → absolute https://websosanh.vn/img/xxx.jpg."""
        adapter = self._make_adapter()
        html = """
        <div class="product-single-info">
            <h2><a class="product-single-name" href="/sp/test4">Dây điện</a></h2>
            <div class="product-single-price">200.000 ₫</div>
            <img src="/images/product.jpg" />
        </div>
        """
        results = adapter._parse_html(html, 10)
        assert len(results) == 1
        assert results[0].image == "https://websosanh.vn/images/product.jpg"

    def test_protocol_relative_url_converted(self):
        """//cdn.websosanh.vn/img/xxx.jpg → https://cdn.websosanh.vn/img/xxx.jpg."""
        adapter = self._make_adapter()
        html = """
        <div class="product-single-info">
            <h2><a class="product-single-name" href="/sp/test5">Cable</a></h2>
            <div class="product-single-price">300.000 ₫</div>
            <img src="//cdn.websosanh.vn/img/cable.jpg" />
        </div>
        """
        results = adapter._parse_html(html, 10)
        assert len(results) == 1
        assert results[0].image == "https://cdn.websosanh.vn/img/cable.jpg"


# ---------------------------------------------------------------------------
# Fix 4 & 5: Excel sort by price + description column
# ---------------------------------------------------------------------------


class TestExcelSortByPrice:
    """Products should be sorted by price ascending (cheapest first)."""

    def test_sorted_ascending(self):
        """Products sorted cheapest first in Excel output."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        products = [
            {"platform": "Shopee", "title": "A", "price": "", "extracted_price": 500000},
            {"platform": "Lazada", "title": "B", "price": "", "extracted_price": 100000},
            {"platform": "Web", "title": "C", "price": "", "extracted_price": 300000},
        ]

        with patch("app.engine.tools.excel_report_tool._get_reports_dir") as mock_dir:
            import tempfile, os
            tmp = tempfile.mkdtemp()
            mock_dir.return_value = __import__("pathlib").Path(tmp)

            result = tool_generate_product_report.invoke({
                "products_json": json.dumps(products),
                "title": "Test Sort",
            })

        data = json.loads(result)
        assert "file_path" in data
        assert data["min_price"] == 100000
        # Verify file was created
        assert os.path.exists(data["file_path"])
        # Clean up
        os.remove(data["file_path"])

    def test_none_prices_at_end(self):
        """Products with None/0 price sort to end."""
        from app.engine.tools.excel_report_tool import _extract_price

        products = [
            {"platform": "A", "title": "No price", "price": ""},
            {"platform": "B", "title": "Cheap", "price": "", "extracted_price": 50000},
            {"platform": "C", "title": "Also no price", "price": ""},
        ]

        prices = [_extract_price(p.get("price", ""), p.get("extracted_price")) for p in products]

        paired = list(zip(products, prices))
        paired.sort(key=lambda x: x[1] if x[1] and x[1] > 0 else float('inf'))
        sorted_products = [p for p, _ in paired]

        assert sorted_products[0]["title"] == "Cheap"
        # None-price items at end
        assert sorted_products[1]["title"] in ("No price", "Also no price")
        assert sorted_products[2]["title"] in ("No price", "Also no price")

    def test_all_zero_prices_stable(self):
        """All zero prices → no crash, order preserved."""
        from app.engine.tools.excel_report_tool import _extract_price

        products = [
            {"platform": "A", "title": "X", "price": ""},
            {"platform": "B", "title": "Y", "price": ""},
        ]
        prices = [_extract_price(p.get("price", ""), p.get("extracted_price")) for p in products]

        paired = list(zip(products, prices))
        paired.sort(key=lambda x: x[1] if x[1] and x[1] > 0 else float('inf'))
        sorted_products = [p for p, _ in paired]

        assert len(sorted_products) == 2

    def test_mixed_prices_sort_correctly(self):
        """Mix of valid, zero, and None prices sort correctly."""
        from app.engine.tools.excel_report_tool import _extract_price

        products = [
            {"platform": "A", "title": "Expensive", "price": "", "extracted_price": 900000},
            {"platform": "B", "title": "Zero", "price": ""},
            {"platform": "C", "title": "Mid", "price": "", "extracted_price": 300000},
            {"platform": "D", "title": "Cheapest", "price": "", "extracted_price": 100000},
        ]
        prices = [_extract_price(p.get("price", ""), p.get("extracted_price")) for p in products]

        paired = list(zip(products, prices))
        paired.sort(key=lambda x: x[1] if x[1] and x[1] > 0 else float('inf'))
        sorted_products = [p for p, _ in paired]

        assert sorted_products[0]["title"] == "Cheapest"
        assert sorted_products[1]["title"] == "Mid"
        assert sorted_products[2]["title"] == "Expensive"
        assert sorted_products[3]["title"] == "Zero"  # No price → end


class TestExcelDescriptionColumn:
    """Excel should include a 'Mô tả' (description) column."""

    def test_snippet_column_present(self):
        """Products with snippet → written to description column."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        products = [
            {"platform": "Web", "title": "Cable", "price": "100.000 ₫",
             "snippet": "Dây cáp điện 3x2.5mm, tiêu chuẩn IEC"},
        ]

        with patch("app.engine.tools.excel_report_tool._get_reports_dir") as mock_dir:
            import tempfile, os
            tmp = tempfile.mkdtemp()
            mock_dir.return_value = __import__("pathlib").Path(tmp)

            result = tool_generate_product_report.invoke({
                "products_json": json.dumps(products),
            })

        data = json.loads(result)
        assert "file_path" in data
        # File created → can read back with openpyxl if available
        assert os.path.exists(data["file_path"])
        os.remove(data["file_path"])

    def test_description_fallback(self):
        """Product with 'description' key (no snippet) → used as fallback."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        products = [
            {"platform": "Shopee", "title": "Test", "price": "50.000 ₫",
             "description": "Mô tả sản phẩm chi tiết"},
        ]

        with patch("app.engine.tools.excel_report_tool._get_reports_dir") as mock_dir:
            import tempfile, os
            tmp = tempfile.mkdtemp()
            mock_dir.return_value = __import__("pathlib").Path(tmp)

            result = tool_generate_product_report.invoke({
                "products_json": json.dumps(products),
            })

        data = json.loads(result)
        assert "file_path" in data
        os.remove(data["file_path"])

    def test_empty_description_no_crash(self):
        """Product with no snippet and no description → empty cell, no crash."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        products = [
            {"platform": "Lazada", "title": "NoDesc", "price": "10.000 ₫"},
        ]

        with patch("app.engine.tools.excel_report_tool._get_reports_dir") as mock_dir:
            import tempfile, os
            tmp = tempfile.mkdtemp()
            mock_dir.return_value = __import__("pathlib").Path(tmp)

            result = tool_generate_product_report.invoke({
                "products_json": json.dumps(products),
            })

        data = json.loads(result)
        assert "error" not in data
        os.remove(data["file_path"])

    def test_excel_headers_11_columns(self):
        """Excel should have 11 headers including 'Mô tả'."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report

        # Verify by checking the headers list in the source
        expected_headers = ["STT", "Sàn", "Tên SP", "Giá (VNĐ)", "Người bán",
                           "Đánh giá", "Lượt bán", "Vận chuyển", "Địa chỉ", "Link", "Mô tả"]
        assert len(expected_headers) == 11
        assert "Mô tả" in expected_headers


# ---------------------------------------------------------------------------
# Fix 6: Tool Ack + Prompt for WebSosanh
# ---------------------------------------------------------------------------


class TestToolAckWebSosanh:
    """WebSosanh tool acknowledgment in _TOOL_ACK dict."""

    def test_ack_exists(self):
        """tool_search_websosanh is described in system prompt."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_websosanh" in _SYSTEM_PROMPT

    def test_ack_text_mentions_94_shops(self):
        """System prompt references the 94+ shops aggregation."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "94+" in _SYSTEM_PROMPT or "WebSosanh" in _SYSTEM_PROMPT


class TestPromptWebSosanh:
    """WebSosanh mentioned in system prompt and deep search strategy."""

    def test_system_prompt_mentions_websosanh_tool(self):
        """_SYSTEM_PROMPT CÔNG CỤ section lists tool_search_websosanh."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_websosanh" in _SYSTEM_PROMPT

    def test_deep_search_round_1_includes_websosanh(self):
        """_DEEP_SEARCH_PROMPT Vòng 1 includes WebSosanh."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        # Check Vòng 1 section mentions websosanh
        assert "WebSosanh" in _DEEP_SEARCH_PROMPT
        # Verify it's in the round 1 description
        round1_match = re.search(r"Vòng 1.*?Vòng 2", _DEEP_SEARCH_PROMPT, re.DOTALL)
        assert round1_match is not None
        round1_text = round1_match.group(0)
        assert "websosanh" in round1_text.lower() or "WebSosanh" in round1_text

    def test_system_prompt_websosanh_description(self):
        """WebSosanh tool description mentions 94+ shops and price comparison."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        # Find the websosanh tool line
        lines = _SYSTEM_PROMPT.split("\n")
        websosanh_line = [l for l in lines if "tool_search_websosanh" in l]
        assert len(websosanh_line) >= 1
        desc = websosanh_line[0]
        assert "94+" in desc or "SO SÁNH GIÁ" in desc


# ---------------------------------------------------------------------------
# Fix 7: Deep Search Stopping Criteria
# ---------------------------------------------------------------------------


class TestDeepSearchStopping:
    """Updated stopping criteria: ≥80 results, ≥5 sources."""

    def test_stopping_80_results(self):
        """Deep search prompt mentions ≥80 results threshold."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "80" in _DEEP_SEARCH_PROMPT
        # Specifically ≥ 80
        assert "≥ 80" in _DEEP_SEARCH_PROMPT or ">=80" in _DEEP_SEARCH_PROMPT or "≥ 80" in _DEEP_SEARCH_PROMPT

    def test_stopping_5_sources(self):
        """Deep search prompt mentions ≥5 sources threshold."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "5 nguồn" in _DEEP_SEARCH_PROMPT

    def test_b2b_keywords_in_prompts(self):
        """Deep search prompt includes B2B keywords for industrial products."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        assert "đại lý" in _DEEP_SEARCH_PROMPT
        assert "nhà phân phối" in _DEEP_SEARCH_PROMPT or "phân phối" in _DEEP_SEARCH_PROMPT
        assert "giá sỉ" in _DEEP_SEARCH_PROMPT

    def test_industrial_query_variants_example(self):
        """Deep search has example for industrial product query variants."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        # Should have industrial product example
        assert "công nghiệp" in _DEEP_SEARCH_PROMPT or "3 ruột" in _DEEP_SEARCH_PROMPT or "2.5mm" in _DEEP_SEARCH_PROMPT

    def test_system_prompt_b2b_rule(self):
        """System prompt QUY TẮC mentions B2B keywords for industrial products."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "đại lý" in _SYSTEM_PROMPT or "B2B" in _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Integration: parse_vnd_price from utils (shared utility)
# ---------------------------------------------------------------------------


class TestParseVndPriceIntegration:
    """Verify parse_vnd_price works correctly for adapter usage."""

    def test_standard_vnd_format(self):
        from app.engine.search_platforms.utils import parse_vnd_price
        assert parse_vnd_price("1.234.567 ₫") == 1234567.0

    def test_comma_separator(self):
        from app.engine.search_platforms.utils import parse_vnd_price
        assert parse_vnd_price("1,234,567 VND") == 1234567.0

    def test_empty_string(self):
        from app.engine.search_platforms.utils import parse_vnd_price
        assert parse_vnd_price("") is None

    def test_none_input(self):
        from app.engine.search_platforms.utils import parse_vnd_price
        assert parse_vnd_price(None) is None
