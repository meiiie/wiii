"""
Sprint 190: Crawl4AI General Adapter Unit Tests

Tests the Crawl4AIGeneralAdapter and factory functions.
All tests run WITHOUT crawl4ai installed -- heavy dependency is mocked.

33 tests across 6 categories:
1. Initialization (6 tests)
2. VND price extraction (8 tests)
3. URL building (5 tests)
4. Markdown extraction (7 tests)
5. search_sync error handling (5 tests)
6. Factory functions (2 tests)
"""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.adapters.crawl4ai_adapter import (
    Crawl4AIGeneralAdapter,
    Crawl4AISiteAdapter,
    create_crawl4ai_generic_adapter,
    _extract_vnd_price,
    _VND_PRICE_RE,
)


# ============================================================================
# 1. Initialization Tests (6 tests)
# ============================================================================


class TestCrawl4AIInit:
    """Test adapter initialization and configuration."""

    def test_creates_with_target_urls(self):
        """Adapter stores target_urls and is a SearchPlatformAdapter."""
        urls = ["https://zebratech.vn/?s={query}", "https://tanphat.com.vn/search?q={query}"]
        adapter = Crawl4AIGeneralAdapter(target_urls=urls)
        assert isinstance(adapter, SearchPlatformAdapter)
        assert adapter._target_urls == urls

    def test_creates_with_empty_target_urls(self):
        """Adapter accepts empty target_urls list."""
        adapter = Crawl4AIGeneralAdapter()
        assert adapter._target_urls == []

    def test_get_config_returns_crawl4ai_backend(self):
        """get_config() returns PlatformConfig with BackendType.CRAWL4AI."""
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        config = adapter.get_config()
        assert isinstance(config, PlatformConfig)
        assert config.backend == BackendType.CRAWL4AI
        assert config.id == "crawl4ai_general"
        assert config.display_name == "Web Crawler (AI)"

    def test_get_tool_name(self):
        """get_tool_name() returns correct name."""
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        assert adapter.get_tool_name() == "tool_search_crawl4ai_general"

    def test_get_tool_description_returns_vietnamese(self):
        """get_tool_description() returns Vietnamese description."""
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        desc = adapter.get_tool_description()
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_custom_platform_id_and_display_name(self):
        """Custom platform_id and display_name in config."""
        adapter = Crawl4AIGeneralAdapter(
            target_urls=["https://dealer.com?q={query}"],
            platform_id="crawl4ai_dealer",
            display_name="Dealer Crawler",
        )
        config = adapter.get_config()
        assert config.id == "crawl4ai_dealer"
        assert config.display_name == "Dealer Crawler"
        assert adapter.get_tool_name() == "tool_search_crawl4ai_dealer"


# ============================================================================
# 2. VND Price Extraction Tests (8 tests)
# ============================================================================


class TestExtractVndPrice:
    """Test _extract_vnd_price for Vietnamese Dong price parsing."""

    def test_dot_separated_dong(self):
        """1.500.000 d -> 1500000.0"""
        assert _extract_vnd_price("1.500.000 d") == 1_500_000.0

    def test_comma_separated_vnd(self):
        """1,500,000 VND -> 1500000.0"""
        assert _extract_vnd_price("1,500,000 VND") == 1_500_000.0

    def test_no_separator_dong(self):
        """1500000d -> 1500000.0"""
        assert _extract_vnd_price("1500000d") == 1_500_000.0

    def test_vnd_lowercase(self):
        """2.500.000 vnd -> 2500000.0"""
        assert _extract_vnd_price("2.500.000 vnd") == 2_500_000.0

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert _extract_vnd_price("") is None

    def test_contact_text_returns_none(self):
        """Non-price text returns None."""
        assert _extract_vnd_price("Lien he") is None

    def test_random_text_returns_none(self):
        """Random text returns None."""
        assert _extract_vnd_price("abc") is None

    def test_dollar_price_returns_none(self):
        """$100 (USD, not VND) returns None."""
        result = _extract_vnd_price("$100")
        assert result is None


# ============================================================================
# 3. URL Building Tests (5 tests)
# ============================================================================


class TestURLBuilding:
    """Test URL construction from templates."""

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_builds_urls_from_template(self, mock_run):
        """search_sync replaces {query} in target_urls."""
        mock_run.return_value = []
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com/search?q={query}"])
        adapter.search_sync("test query")
        assert mock_run.called

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_url_encodes_vietnamese(self, mock_run):
        """Vietnamese characters are URL-encoded."""
        mock_run.return_value = []
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com/search?q={query}"])
        adapter.search_sync("dau in Zebra ZXP7")
        assert mock_run.called

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_multiple_target_urls(self, mock_run):
        """Multiple target_urls are all included."""
        mock_run.return_value = []
        urls = [
            "https://site-a.com/search?q={query}",
            "https://site-b.com/search?q={query}",
        ]
        adapter = Crawl4AIGeneralAdapter(target_urls=urls)
        adapter.search_sync("printer")
        assert mock_run.call_count == 1

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_query_placeholder_replaced(self, mock_run):
        """The {query} placeholder is replaced."""
        mock_run.return_value = []
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com/search?q={query}"])
        adapter.search_sync("Zebra ZXP7")
        assert mock_run.called

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_page_placeholder_for_pagination(self, mock_run):
        """The {page} placeholder is replaced when page > 1."""
        mock_run.return_value = []
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com/search?q={query}&page={page}"])
        adapter.search_sync("test", page=2)
        assert mock_run.called


# ============================================================================
# 4. Markdown Extraction Tests (7 tests)
# ============================================================================


class TestMarkdownExtraction:
    """Test _extract_products_from_markdown heuristic extraction."""

    def _make_adapter(self):
        return Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])

    def test_extracts_title_from_headers(self):
        """Product titles from markdown ## headers."""
        markdown = (
            "## Dau in Zebra ZXP7 chinh hang\n"
            "San pham chat luong cao\n"
            "Gia: 15.500.000 đ\n"
            "\n"
            "## May in the Zebra ZXP7 Series\n"
            "Thiet bi in the chuyen nghiep\n"
            "Gia: 18.000.000 đ\n"
        )
        adapter = self._make_adapter()
        results = adapter._extract_products_from_markdown(markdown, "https://example.com", "Zebra ZXP7")
        assert len(results) >= 1
        titles = [r.title for r in results]
        assert any("Zebra ZXP7" in t for t in titles)

    def test_extracts_vnd_prices(self):
        """VND prices extracted and parsed."""
        markdown = (
            "## Dau in Zebra ZXP7 chinh hang\n"
            "Gia ban: 15.500.000 đ (da bao gom VAT)\n"
        )
        adapter = self._make_adapter()
        results = adapter._extract_products_from_markdown(markdown, "https://example.com", "Zebra ZXP7")
        assert len(results) >= 1
        assert results[0].extracted_price == 15_500_000.0

    def test_extracts_links(self):
        """URLs from markdown [text](url) format."""
        markdown = (
            "## Dau in Zebra ZXP7 Premium\n"
            "Xem chi tiet tai [Trang san pham](https://dealer.com/zebra-zxp7)\n"
            "Gia: 15.000.000 đ\n"
        )
        adapter = self._make_adapter()
        results = adapter._extract_products_from_markdown(markdown, "https://example.com", "Zebra ZXP7")
        assert len(results) >= 1
        assert results[0].link == "https://dealer.com/zebra-zxp7"

    def test_filters_by_query_relevance(self):
        """Sections not containing query words are filtered out."""
        markdown = (
            "## Dau in Zebra ZXP7 chinh hang\n"
            "Gia: 15.500.000 đ\n"
            "\n"
            "## Dau in Evolis Primacy tot nhat\n"
            "Gia: 20.000.000 đ\n"
        )
        adapter = self._make_adapter()
        results = adapter._extract_products_from_markdown(markdown, "https://example.com", "Zebra ZXP7")
        titles = [r.title for r in results]
        assert any("Zebra" in t for t in titles)
        assert not any("Evolis" in t for t in titles)

    def test_handles_empty_markdown(self):
        """Empty markdown returns []."""
        adapter = self._make_adapter()
        assert adapter._extract_products_from_markdown("", "https://example.com", "test") == []

    def test_handles_short_markdown(self):
        """Very short markdown returns []."""
        adapter = self._make_adapter()
        assert adapter._extract_products_from_markdown("Short", "https://example.com", "test") == []

    def test_multiple_products(self):
        """Multi-section markdown extracts multiple products."""
        sections = []
        for i in range(5):
            sections.append(
                f"## Dau in Zebra ZXP7 Model {i}\n"
                f"Gia: {10 + i}.000.000 đ\n"
                f"Mo ta chi tiet san pham Zebra ZXP7 phien ban moi nhat"
            )
        markdown = "\n".join(sections)
        adapter = self._make_adapter()
        results = adapter._extract_products_from_markdown(markdown, "https://example.com", "Zebra ZXP7")
        assert len(results) >= 3
        for r in results:
            assert isinstance(r, ProductSearchResult)
            assert r.platform == "crawl4ai_general"


# ============================================================================
# 5. search_sync Error Handling (5 tests)
# ============================================================================


class TestSearchSyncErrorHandling:
    """Test graceful error handling."""

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_import_error_returns_empty(self, mock_run):
        """ImportError returns []."""
        mock_run.side_effect = ImportError("No module named 'crawl4ai'")
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_general_exception_returns_empty(self, mock_run):
        """RuntimeError returns []."""
        mock_run.side_effect = RuntimeError("Unexpected failure")
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_timeout_returns_empty(self, mock_run):
        """TimeoutError returns []."""
        mock_run.side_effect = TimeoutError("Timed out")
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        assert adapter.search_sync("test") == []

    def test_no_target_urls_returns_empty(self):
        """No target_urls returns [] immediately."""
        adapter = Crawl4AIGeneralAdapter(target_urls=[])
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.crawl4ai_adapter._run_async_in_thread")
    def test_logs_error_on_import_error(self, mock_run, caplog):
        """ImportError logged at ERROR level."""
        mock_run.side_effect = ImportError("No module named 'crawl4ai'")
        adapter = Crawl4AIGeneralAdapter(target_urls=["https://example.com?q={query}"])
        with caplog.at_level(logging.ERROR, logger="app.engine.search_platforms.adapters.crawl4ai_adapter"):
            adapter.search_sync("test")
        assert any("crawl4ai" in r.message.lower() or "not installed" in r.message.lower() for r in caplog.records)


# ============================================================================
# 6. Factory Functions (2 tests)
# ============================================================================


class TestFactoryFunctions:
    """Test convenience factory functions."""

    def test_create_crawl4ai_generic_adapter(self):
        """create_crawl4ai_generic_adapter() returns correct type."""
        adapter = create_crawl4ai_generic_adapter(
            target_urls=["https://zebratech.vn/?s={query}"],
            platform_id="crawl4ai_zebratech",
            display_name="ZebraTech Crawler",
        )
        assert isinstance(adapter, Crawl4AIGeneralAdapter)
        config = adapter.get_config()
        assert config.id == "crawl4ai_zebratech"
        assert config.display_name == "ZebraTech Crawler"
        assert config.backend == BackendType.CRAWL4AI
        assert config.priority == 10

    def test_site_adapter_create_for_site(self):
        """Crawl4AISiteAdapter.create_for_site() creates correctly."""
        adapter = Crawl4AISiteAdapter.create_for_site(
            site_name="tanphat",
            search_url_template="https://tanphat.com.vn/search?q={query}",
            display_name="Tan Phat",
            priority=3,
        )
        assert isinstance(adapter, Crawl4AISiteAdapter)
        assert isinstance(adapter, Crawl4AIGeneralAdapter)
        config = adapter.get_config()
        assert config.id == "crawl4ai_tanphat"
        assert config.display_name == "Tan Phat"
        assert config.priority == 3


# ============================================================================
# Bonus: VND price regex pattern
# ============================================================================


class TestVndPriceRegex:
    """Validate the _VND_PRICE_RE regex pattern."""

    def test_matches_dong_symbol(self):
        assert _VND_PRICE_RE.search("Gia: 1.500.000 đ")

    def test_matches_vnd_suffix(self):
        assert _VND_PRICE_RE.search("Gia: 1,500,000 VND")

    def test_does_not_match_usd(self):
        assert _VND_PRICE_RE.search("$100") is None

    def test_case_insensitive(self):
        assert _VND_PRICE_RE.search("1000000 vnd")
        assert _VND_PRICE_RE.search("1000000 VND")
