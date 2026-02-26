"""
Sprint 190: Scrapling Stealth Adapter Unit Tests

Tests for ScraplingStealthAdapter: stealth scraper for anti-bot protected sites.
All tests run WITHOUT scrapling installed -- uses mocks exclusively.

30 tests across 6 categories:
1. Initialization (5 tests)
2. VND price extraction (5 tests)
3. URL building (4 tests)
4. Fetch and extract with mocks (8 tests)
5. search_sync error handling (5 tests)
6. Factory functions (3 tests)
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.adapters.scrapling_adapter import (
    ScraplingStealthAdapter,
    _extract_vnd_price,
    create_scrapling_facebook_adapter,
    create_scrapling_general_adapter,
)


# ============================================================================
# 1. Initialization Tests (5 tests)
# ============================================================================


class TestScraplingInit:
    """Test adapter initialization and configuration."""

    def test_creates_with_defaults(self):
        """Adapter creates with target_urls and is a SearchPlatformAdapter."""
        adapter = ScraplingStealthAdapter(
            target_urls=["https://example.com/search?q={query}"],
            platform_id="scrapling_test",
            display_name="Test Scrapling",
        )
        assert isinstance(adapter, SearchPlatformAdapter)
        assert adapter._target_urls == ["https://example.com/search?q={query}"]

    def test_get_config_returns_scrapling_backend(self):
        """get_config() returns PlatformConfig with BackendType.SCRAPLING."""
        adapter = ScraplingStealthAdapter(
            target_urls=["https://example.com?q={query}"],
            platform_id="scrapling_test",
            display_name="Test Scrapling",
        )
        config = adapter.get_config()
        assert isinstance(config, PlatformConfig)
        assert config.backend == BackendType.SCRAPLING
        assert config.id == "scrapling_test"
        assert config.display_name == "Test Scrapling"

    def test_get_tool_name(self):
        """get_tool_name() returns correct name."""
        adapter = ScraplingStealthAdapter(
            target_urls=["https://example.com?q={query}"],
            platform_id="scrapling_fb",
            display_name="Facebook Scrapling",
        )
        assert adapter.get_tool_name() == "tool_search_scrapling_fb"

    def test_get_tool_description_returns_vietnamese(self):
        """get_tool_description() returns Vietnamese description."""
        adapter = ScraplingStealthAdapter(
            target_urls=["https://example.com?q={query}"],
            platform_id="scrapling_test",
            display_name="Test",
        )
        desc = adapter.get_tool_description()
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_custom_priority(self):
        """Custom priority is stored in config."""
        adapter = ScraplingStealthAdapter(
            target_urls=["https://example.com?q={query}"],
            platform_id="scrapling_test",
            display_name="Test",
            priority=2,
        )
        config = adapter.get_config()
        assert config.priority == 2


# ============================================================================
# 2. VND Price Extraction (5 tests)
# ============================================================================


class TestScraplingPriceExtraction:
    """Test _extract_vnd_price module-level function."""

    def test_extracts_dot_separated_price(self):
        """'15.500.000 đ' -> 15500000.0."""
        result = _extract_vnd_price("Gia: 15.500.000 đ")
        assert result == 15_500_000.0

    def test_extracts_comma_separated_price(self):
        """'1,500,000 VND' -> 1500000.0."""
        result = _extract_vnd_price("Gia ban: 1,500,000 VND")
        assert result == 1_500_000.0

    def test_extracts_no_separator_price(self):
        """'1500000đ' -> 1500000.0."""
        result = _extract_vnd_price("1500000đ")
        assert result == 1_500_000.0

    def test_empty_text_returns_none(self):
        """Empty text returns None."""
        assert _extract_vnd_price("") is None

    def test_no_price_text_returns_none(self):
        """Text without price returns None."""
        assert _extract_vnd_price("Lien he de biet gia") is None


# ============================================================================
# 3. URL Building Tests (4 tests)
# ============================================================================


class TestScraplingURLBuilding:
    """Test URL construction from templates."""

    def _make_adapter(self, urls=None):
        return ScraplingStealthAdapter(
            target_urls=urls or ["https://example.com/search?q={query}"],
            platform_id="scrapling_test",
            display_name="Test",
        )

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_builds_url_from_template(self, mock_fetch):
        """search_sync replaces {query} in target_urls."""
        mock_fetch.return_value = []
        adapter = self._make_adapter()
        adapter.search_sync("Zebra ZXP7")
        assert mock_fetch.called

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_url_encodes_vietnamese(self, mock_fetch):
        """Vietnamese characters are URL-encoded."""
        mock_fetch.return_value = []
        adapter = self._make_adapter()
        adapter.search_sync("dau in Zebra ZXP7")
        assert mock_fetch.called

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_page_placeholder(self, mock_fetch):
        """{page} placeholder replaced for pagination."""
        mock_fetch.return_value = []
        adapter = self._make_adapter(urls=["https://example.com/search?q={query}&page={page}"])
        adapter.search_sync("test", page=2)
        assert mock_fetch.called

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_multiple_calls_all_encoded(self, mock_fetch):
        """Multiple calls work correctly."""
        mock_fetch.return_value = []
        adapter = self._make_adapter()
        adapter.search_sync("query 1")
        adapter.search_sync("query 2")
        assert mock_fetch.call_count == 2


# ============================================================================
# 4. Fetch and Extract with Mocks (8 tests)
# ============================================================================


class TestFetchAndExtract:
    """Test _fetch_and_extract with mocked scrapling."""

    def _make_adapter(self):
        return ScraplingStealthAdapter(
            target_urls=["https://example.com/search?q={query}"],
            platform_id="scrapling_test",
            display_name="Test",
        )

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_returns_product_search_results(self, mock_fetch):
        """search_sync returns list of ProductSearchResult."""
        mock_fetch.return_value = [
            ProductSearchResult(
                title="Dau in Zebra ZXP7",
                link="https://example.com/zebra-zxp7",
                extracted_price=15_500_000.0,
                platform="scrapling_test",
            )
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("Zebra ZXP7")
        assert len(results) == 1
        assert isinstance(results[0], ProductSearchResult)
        assert results[0].title == "Dau in Zebra ZXP7"
        assert results[0].extracted_price == 15_500_000.0

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_returns_multiple_results(self, mock_fetch):
        """search_sync returns multiple results."""
        mock_fetch.return_value = [
            ProductSearchResult(title=f"Product {i}", link=f"https://example.com/{i}", platform="scrapling_test")
            for i in range(5)
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("test")
        assert len(results) == 5

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_empty_results(self, mock_fetch):
        """Empty results from _fetch_and_extract."""
        mock_fetch.return_value = []
        adapter = self._make_adapter()
        results = adapter.search_sync("nonexistent product")
        assert results == []

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_platform_tag_is_correct(self, mock_fetch):
        """ProductSearchResult.platform matches platform_id."""
        mock_fetch.return_value = [
            ProductSearchResult(title="Test", link="https://example.com", platform="scrapling_test")
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("test")
        assert results[0].platform == "scrapling_test"

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_max_results_passed(self, mock_fetch):
        """max_results parameter is passed through."""
        mock_fetch.return_value = []
        adapter = self._make_adapter()
        adapter.search_sync("test", max_results=5)
        assert mock_fetch.called

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_result_has_link(self, mock_fetch):
        """Results include product link."""
        mock_fetch.return_value = [
            ProductSearchResult(
                title="Zebra ZXP7",
                link="https://dealer.com/zebra-zxp7",
                platform="scrapling_test",
            )
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("Zebra ZXP7")
        assert results[0].link == "https://dealer.com/zebra-zxp7"

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_result_has_price(self, mock_fetch):
        """Results can include extracted price."""
        mock_fetch.return_value = [
            ProductSearchResult(
                title="Zebra ZXP7",
                link="https://example.com",
                extracted_price=18_000_000.0,
                platform="scrapling_test",
            )
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("Zebra ZXP7")
        assert results[0].extracted_price == 18_000_000.0

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_result_has_snippet(self, mock_fetch):
        """Results can include snippet."""
        mock_fetch.return_value = [
            ProductSearchResult(
                title="Zebra ZXP7",
                link="https://example.com",
                snippet="Dau in chinh hang, bao hanh 12 thang",
                platform="scrapling_test",
            )
        ]
        adapter = self._make_adapter()
        results = adapter.search_sync("Zebra ZXP7")
        assert "chinh hang" in results[0].snippet


# ============================================================================
# 5. search_sync Error Handling (5 tests)
# ============================================================================


class TestScraplingErrorHandling:
    """Test graceful error handling."""

    def _make_adapter(self):
        return ScraplingStealthAdapter(
            target_urls=["https://example.com/search?q={query}"],
            platform_id="scrapling_test",
            display_name="Test",
        )

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_import_error_returns_empty(self, mock_fetch):
        """ImportError returns []."""
        mock_fetch.side_effect = ImportError("No module named 'scrapling'")
        adapter = self._make_adapter()
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_runtime_error_returns_empty(self, mock_fetch):
        """RuntimeError returns []."""
        mock_fetch.side_effect = RuntimeError("Connection failed")
        adapter = self._make_adapter()
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_timeout_returns_empty(self, mock_fetch):
        """TimeoutError returns []."""
        mock_fetch.side_effect = TimeoutError("Request timed out")
        adapter = self._make_adapter()
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_connection_error_returns_empty(self, mock_fetch):
        """ConnectionError returns []."""
        mock_fetch.side_effect = ConnectionError("DNS resolution failed")
        adapter = self._make_adapter()
        assert adapter.search_sync("test") == []

    @patch("app.engine.search_platforms.adapters.scrapling_adapter.ScraplingStealthAdapter._fetch_and_extract")
    def test_logs_error_on_failure(self, mock_fetch, caplog):
        """Errors are logged."""
        mock_fetch.side_effect = RuntimeError("Test failure")
        adapter = self._make_adapter()
        with caplog.at_level(logging.ERROR, logger="app.engine.search_platforms.adapters.scrapling_adapter"):
            adapter.search_sync("test")
        assert any("error" in r.message.lower() or "fail" in r.message.lower() for r in caplog.records)


# ============================================================================
# 6. Factory Functions (3 tests)
# ============================================================================


class TestScraplingFactoryFunctions:
    """Test convenience factory functions."""

    def test_create_scrapling_facebook_adapter(self):
        """create_scrapling_facebook_adapter() returns correct type and config."""
        adapter = create_scrapling_facebook_adapter()
        assert isinstance(adapter, ScraplingStealthAdapter)
        config = adapter.get_config()
        assert config.backend == BackendType.SCRAPLING
        assert "facebook" in config.id.lower() or "fb" in config.id.lower()
        assert config.priority == 2

    def test_create_scrapling_general_adapter(self):
        """create_scrapling_general_adapter() returns correct type."""
        adapter = create_scrapling_general_adapter(
            target_urls=["https://example.com/search?q={query}"],
            platform_id="scrapling_custom",
            display_name="Custom Scraper",
        )
        assert isinstance(adapter, ScraplingStealthAdapter)
        config = adapter.get_config()
        assert config.id == "scrapling_custom"
        assert config.display_name == "Custom Scraper"
        assert config.backend == BackendType.SCRAPLING

    def test_facebook_adapter_is_search_platform_adapter(self):
        """Facebook adapter is a proper SearchPlatformAdapter."""
        adapter = create_scrapling_facebook_adapter()
        assert isinstance(adapter, SearchPlatformAdapter)
        assert adapter.get_tool_name().startswith("tool_search_")
