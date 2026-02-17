"""
Unit tests for web search tools.

Tests tool_web_search with mocked DuckDuckGo results.
No real web requests are made.
"""
import sys
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_ddgs():
    """Mock duckduckgo_search/ddgs module for all tests.

    _search_sync() tries `from ddgs import DDGS` first, falls back to
    `from duckduckgo_search import DDGS`.  Patch both so the mock wins
    regardless of which package is installed.
    """
    mock_module = MagicMock()
    with patch.dict(sys.modules, {"ddgs": mock_module, "duckduckgo_search": mock_module}):
        yield mock_module


class TestWebSearchTool:
    """Test tool_web_search function."""

    def test_successful_search(self, mock_ddgs):
        """Test that search results are formatted correctly."""
        mock_results = [
            {"title": "COLREGs Rule 15", "body": "Crossing situation", "href": "https://example.com/1"},
            {"title": "Maritime Law", "body": "Overview", "href": "https://example.com/2"},
        ]
        mock_ddgs.DDGS.return_value.text.return_value = mock_results

        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "COLREGs Rule 15"})

        assert "COLREGs Rule 15" in result
        assert "Crossing situation" in result

    def test_empty_results(self, mock_ddgs):
        """Test handling when no results found."""
        mock_ddgs.DDGS.return_value.text.return_value = []

        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "nonexistent query"})

        assert "Không tìm thấy" in result

    def test_search_exception(self, mock_ddgs):
        """Test handling of search API errors."""
        mock_ddgs.DDGS.return_value.text.side_effect = Exception("Connection timeout")

        from app.engine.tools.web_search_tools import tool_web_search
        result = tool_web_search.invoke({"query": "test"})

        assert "Lỗi" in result


class TestWebSearchRegistration:
    """Test tool registration."""

    @patch("app.engine.tools.web_search_tools.get_tool_registry")
    def test_init_registers_all_tools(self, mock_registry_fn):
        """init_web_search_tools should register all 4 search tools."""
        from app.engine.tools.web_search_tools import init_web_search_tools

        mock_registry = MagicMock()
        mock_registry_fn.return_value = mock_registry

        init_web_search_tools()

        # Sprint 102: Now registers 4 tools
        assert mock_registry.register.call_count == 4
        registered_names = [
            call[0][0].name for call in mock_registry.register.call_args_list
        ]
        assert "tool_web_search" in registered_names
        assert "tool_search_news" in registered_names
        assert "tool_search_legal" in registered_names
        assert "tool_search_maritime" in registered_names
