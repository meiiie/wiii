"""
Unit tests for Tool Registry.

Tests:
- ToolRegistry: register, get_all, get_by_category, get_read_only, get_mutating
- ToolCategory.UTILITY recognition
- Singleton pattern of get_tool_registry()
- summary() output format
"""

import pytest
from unittest.mock import MagicMock

from app.engine.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolAccess,
    ToolInfo,
    get_tool_registry,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def registry():
    """Create a fresh ToolRegistry for each test."""
    return ToolRegistry()


def _make_tool(name: str = "test_tool"):
    """Create a mock tool with a name attribute."""
    mock = MagicMock()
    mock.name = name
    mock.description = f"Description for {name}"
    return mock


# =============================================================================
# Tests: ToolCategory enum
# =============================================================================

class TestToolCategory:
    def test_rag_category_exists(self):
        assert ToolCategory.RAG.value == "rag"

    def test_memory_category_exists(self):
        assert ToolCategory.MEMORY.value == "memory"

    def test_utility_category_exists(self):
        """UTILITY category was added for non-domain tools."""
        assert ToolCategory.UTILITY.value == "utility"

    def test_all_categories_are_strings(self):
        for cat in ToolCategory:
            assert isinstance(cat.value, str)


# =============================================================================
# Tests: ToolRegistry
# =============================================================================

class TestToolRegistry:
    def test_register_tool(self, registry):
        tool = _make_tool("my_tool")
        registry.register(tool, ToolCategory.RAG)
        assert registry.count() == 1

    def test_register_multiple_tools(self, registry):
        for i in range(3):
            registry.register(_make_tool(f"tool_{i}"), ToolCategory.RAG)
        assert registry.count() == 3

    def test_get_all_returns_tools(self, registry):
        tool = _make_tool()
        registry.register(tool, ToolCategory.RAG)
        result = registry.get_all()
        assert len(result) == 1
        assert result[0] is tool

    def test_get_all_names(self, registry):
        registry.register(_make_tool("alpha"), ToolCategory.RAG)
        registry.register(_make_tool("beta"), ToolCategory.UTILITY)
        names = registry.get_all_names()
        assert "alpha" in names
        assert "beta" in names

    def test_get_by_category(self, registry):
        rag_tool = _make_tool("rag_tool")
        util_tool = _make_tool("util_tool")
        registry.register(rag_tool, ToolCategory.RAG)
        registry.register(util_tool, ToolCategory.UTILITY)

        rag_tools = registry.get_by_category(ToolCategory.RAG)
        assert len(rag_tools) == 1
        assert rag_tools[0] is rag_tool

        util_tools = registry.get_by_category(ToolCategory.UTILITY)
        assert len(util_tools) == 1
        assert util_tools[0] is util_tool

    def test_get_by_category_empty(self, registry):
        result = registry.get_by_category(ToolCategory.LEARNING)
        assert result == []

    def test_get_read_only(self, registry):
        read_tool = _make_tool("reader")
        write_tool = _make_tool("writer")
        registry.register(read_tool, ToolCategory.RAG, ToolAccess.READ)
        registry.register(write_tool, ToolCategory.MEMORY, ToolAccess.WRITE)

        read_only = registry.get_read_only()
        assert len(read_only) == 1
        assert read_only[0] is read_tool

    def test_get_mutating(self, registry):
        read_tool = _make_tool("reader")
        write_tool = _make_tool("writer")
        registry.register(read_tool, ToolCategory.RAG, ToolAccess.READ)
        registry.register(write_tool, ToolCategory.MEMORY, ToolAccess.WRITE)

        mutating = registry.get_mutating()
        assert len(mutating) == 1
        assert mutating[0] is write_tool

    def test_get_for_role(self, registry):
        admin_tool = _make_tool("admin_only")
        registry.register(admin_tool, ToolCategory.RAG, roles=["admin"])

        admin_tools = registry.get_for_role("admin")
        assert len(admin_tools) == 1

        student_tools = registry.get_for_role("student")
        assert len(student_tools) == 0

    def test_get_info(self, registry):
        tool = _make_tool("info_tool")
        registry.register(tool, ToolCategory.UTILITY, ToolAccess.READ, description="test desc")

        info = registry.get_info("info_tool")
        assert info is not None
        assert isinstance(info, ToolInfo)
        assert info.name == "info_tool"
        assert info.category == ToolCategory.UTILITY
        assert info.access == ToolAccess.READ
        assert info.description == "test desc"

    def test_get_info_nonexistent(self, registry):
        assert registry.get_info("nonexistent") is None

    def test_summary_structure(self, registry):
        registry.register(_make_tool("a"), ToolCategory.RAG, ToolAccess.READ)
        registry.register(_make_tool("b"), ToolCategory.UTILITY, ToolAccess.READ)
        registry.register(_make_tool("c"), ToolCategory.MEMORY, ToolAccess.WRITE)

        summary = registry.summary()
        assert summary["total"] == 3
        assert summary["read_only"] == 2
        assert summary["mutating"] == 1
        assert "categories" in summary
        assert summary["categories"]["rag"] == 1
        assert summary["categories"]["utility"] == 1
        assert summary["categories"]["memory"] == 1

    def test_register_tool_without_name_attribute(self, registry):
        """Test registering a plain function (no .name attribute)."""
        def plain_func():
            pass
        registry.register(plain_func, ToolCategory.RAG)
        assert registry.count() == 1
        assert registry.get_info("plain_func") is not None


# =============================================================================
# Tests: Singleton
# =============================================================================

class TestSingleton:
    def test_get_tool_registry_returns_same_instance(self):
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    def test_get_tool_registry_returns_tool_registry(self):
        r = get_tool_registry()
        assert isinstance(r, ToolRegistry)
