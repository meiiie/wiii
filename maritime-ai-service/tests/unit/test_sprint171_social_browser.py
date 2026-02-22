"""
Tests for Sprint 171: Social Browser Rewrite — Routes through existing
web search tools with safety validation.

Sprint 171: "Quyền Tự Chủ" — Safety-first autonomous capabilities.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engine.living_agent.models import BrowsingItem


def _make_settings(**overrides):
    """Create a mock settings object."""
    defaults = {
        "living_agent_enable_social_browse": True,
        "serper_api_key": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# Lazy imports in social_browser.py → patch at SOURCE module
_SETTINGS_PATCH = "app.core.config.settings"
# Tools are imported lazily in _invoke_tool → patch at source
_TOOL_WEB = "app.engine.tools.web_search_tools.tool_web_search"
_TOOL_NEWS = "app.engine.tools.web_search_tools.tool_search_news"
_TOOL_MARITIME = "app.engine.tools.web_search_tools.tool_search_maritime"
# Safety is imported lazily → patch at source
_VALIDATE_URL = "app.engine.living_agent.safety.validate_url"
_SANITIZE = "app.engine.living_agent.safety.sanitize_content"


class TestSocialBrowserRouting:
    """Tests for tool routing based on topic."""

    @pytest.mark.asyncio
    async def test_routes_maritime_to_maritime_tool(self):
        """Maritime topic should invoke tool_search_maritime."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "**IMO News**\nSome content\nURL: https://imo.org/news"

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_MARITIME, mock_tool), \
             patch(_VALIDATE_URL, return_value=True), \
             patch(_SANITIZE, side_effect=lambda x, **kw: x), \
             patch.object(browser, "_save_browsing_log"):

            items = await browser.browse_feed(topic="maritime", max_items=5)

            # Should have invoked maritime tool
            mock_tool.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_news_to_news_tool(self):
        """News topic should invoke tool_search_news."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "**VnExpress News**\nContent\nURL: https://vnexpress.net/test"

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_NEWS, mock_tool), \
             patch(_VALIDATE_URL, return_value=True), \
             patch(_SANITIZE, side_effect=lambda x, **kw: x), \
             patch.object(browser, "_save_browsing_log"):

            items = await browser.browse_feed(topic="news", max_items=5)
            mock_tool.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_general_to_web_search(self):
        """General/tech topics should invoke tool_web_search."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "**AI News**\nContent\nURL: https://example.com"

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_WEB, mock_tool), \
             patch(_VALIDATE_URL, return_value=True), \
             patch(_SANITIZE, side_effect=lambda x, **kw: x), \
             patch.object(browser, "_save_browsing_log"):

            items = await browser.browse_feed(topic="tech", max_items=5)
            mock_tool.invoke.assert_called_once()


class TestSafetyFiltering:
    """Tests for URL validation and content sanitization in browser."""

    @pytest.mark.asyncio
    async def test_filters_unsafe_urls(self):
        """Items with unsafe URLs should be filtered out."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        # Return items including one with private IP
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = (
            "**Safe Item**\nContent\nURL: https://example.com\n\n---\n\n"
            "**Unsafe Item**\nContent\nURL: http://127.0.0.1/admin"
        )

        def mock_validate(url):
            return "127.0.0.1" not in (url or "")

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_WEB, mock_tool), \
             patch(_VALIDATE_URL, side_effect=mock_validate), \
             patch(_SANITIZE, side_effect=lambda x, **kw: x), \
             patch.object(browser, "_save_browsing_log"):

            items = await browser.browse_feed(topic="general", max_items=10)

            # Only the safe item should remain
            urls = [i.url for i in items if i.url]
            assert not any("127.0.0.1" in u for u in urls)

    @pytest.mark.asyncio
    async def test_sanitizes_content(self):
        """Content should be sanitized before returning."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "**Test**\n<script>alert('xss')</script>Clean text\nURL: https://example.com"

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_WEB, mock_tool), \
             patch(_VALIDATE_URL, return_value=True), \
             patch.object(browser, "_save_browsing_log"):

            # Use real sanitize_content (not mocked)
            items = await browser.browse_feed(topic="general", max_items=5)

            for item in items:
                assert "<script>" not in item.summary
                assert "alert" not in item.summary


class TestFallbackSearch:
    """Tests for Serper/HN fallback when tools fail."""

    @pytest.mark.asyncio
    async def test_fallback_when_tools_fail(self):
        """Should fall back to Serper/HN when existing tools fail."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        settings = _make_settings()

        # Tool raises exception
        mock_tool = MagicMock()
        mock_tool.invoke.side_effect = Exception("Circuit breaker open")

        # Fallback returns items
        fallback_items = [
            BrowsingItem(platform="serper_fallback", title="Fallback Result", url="https://example.com"),
        ]

        with patch(_SETTINGS_PATCH, settings), \
             patch(_TOOL_WEB, mock_tool), \
             patch.object(browser, "_fallback_search", new_callable=AsyncMock, return_value=fallback_items), \
             patch(_VALIDATE_URL, return_value=True), \
             patch(_SANITIZE, side_effect=lambda x, **kw: x), \
             patch.object(browser, "_save_browsing_log"):

            items = await browser.browse_feed(topic="general", max_items=5)

            assert len(items) >= 1
            assert items[0].platform == "serper_fallback"


class TestParseToolResults:
    """Tests for _parse_tool_results() — parsing tool output to BrowsingItem."""

    def test_parse_standard_format(self):
        """Parse standard formatted tool output."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        raw = (
            "**Title One** (2026-02-22)\n"
            "Summary text for first item\n"
            "URL: https://example.com/1\n\n"
            "---\n\n"
            "**Title Two**\n"
            "Summary for second item\n"
            "URL: https://example.com/2"
        )

        items = browser._parse_tool_results(raw, max_results=5)
        assert len(items) == 2
        assert items[0].title == "Title One"
        assert items[0].url == "https://example.com/1"
        assert items[1].title == "Title Two"

    def test_parse_empty_returns_empty(self):
        """Empty or error outputs should return empty list."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        assert browser._parse_tool_results("", 5) == []
        assert browser._parse_tool_results("Không tìm thấy kết quả", 5) == []
        assert browser._parse_tool_results("Lỗi tìm kiếm", 5) == []

    def test_parse_respects_max_results(self):
        """Should limit parsed items to max_results."""
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        raw = "\n\n---\n\n".join([
            f"**Title {i}**\nSummary {i}\nURL: https://example.com/{i}"
            for i in range(10)
        ])

        items = browser._parse_tool_results(raw, max_results=3)
        assert len(items) == 3
