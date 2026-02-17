"""
Tests for Sprint 26: Tool access control role restrictions.

Covers:
- tool_clear_all_memories is admin-only
- Scheduler tools are teacher/admin only
- get_tools_for_role filters correctly
- get_for_role returns subset based on role
- Student cannot access admin-only tools
"""

import pytest
from unittest.mock import MagicMock

from app.engine.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)


class TestToolAccessRestrictions:
    """Test Sprint 26 role-based tool restrictions."""

    def test_clear_all_memories_admin_only(self):
        """tool_clear_all_memories should only be available to admin."""
        registry = get_tool_registry()
        info = registry.get_info("tool_clear_all_memories")

        assert info is not None
        assert info.roles == ["admin"]
        assert info.access == ToolAccess.WRITE

    def test_clear_all_memories_not_in_student_tools(self):
        """Students should not have access to factory reset."""
        registry = get_tool_registry()
        student_tools = registry.get_for_role("student")
        student_tool_names = [
            t.name if hasattr(t, 'name') else t.__name__
            for t in student_tools
        ]

        assert "tool_clear_all_memories" not in student_tool_names

    def test_clear_all_memories_in_admin_tools(self):
        """Admins should have access to factory reset."""
        registry = get_tool_registry()
        admin_tools = registry.get_for_role("admin")
        admin_tool_names = [
            t.name if hasattr(t, 'name') else t.__name__
            for t in admin_tools
        ]

        assert "tool_clear_all_memories" in admin_tool_names

    def test_basic_memory_tools_available_to_all(self):
        """Basic memory tools should be available to all roles."""
        registry = get_tool_registry()

        for role in ["student", "teacher", "admin"]:
            role_tools = registry.get_for_role(role)
            tool_names = [
                t.name if hasattr(t, 'name') else t.__name__
                for t in role_tools
            ]
            assert "tool_save_user_info" in tool_names
            assert "tool_get_user_info" in tool_names
            assert "tool_remember" in tool_names

    def test_knowledge_search_available_to_all(self):
        """Knowledge search should be available to all roles."""
        registry = get_tool_registry()

        for role in ["student", "teacher", "admin"]:
            role_tools = registry.get_for_role(role)
            tool_names = [
                t.name if hasattr(t, 'name') else t.__name__
                for t in role_tools
            ]
            assert "tool_knowledge_search" in tool_names


class TestGetToolsForRole:
    """Test the get_tools_for_role convenience function."""

    def test_function_exists(self):
        """get_tools_for_role should be importable."""
        from app.engine.tools import get_tools_for_role
        assert callable(get_tools_for_role)

    def test_returns_list(self):
        """Should return a list of tools."""
        from app.engine.tools import get_tools_for_role
        tools = get_tools_for_role("student")
        assert isinstance(tools, list)

    def test_admin_has_more_tools_than_student(self):
        """Admin should have access to at least as many tools as student."""
        from app.engine.tools import get_tools_for_role
        admin_tools = get_tools_for_role("admin")
        student_tools = get_tools_for_role("student")

        assert len(admin_tools) >= len(student_tools)


class TestRegistryRoleFiltering:
    """Test ToolRegistry.get_for_role with custom registrations."""

    def test_role_filtering_basic(self):
        """get_for_role should respect roles list."""
        registry = ToolRegistry()
        tool_a = MagicMock()
        tool_a.name = "admin_tool"
        tool_a.description = "Admin only"

        tool_b = MagicMock()
        tool_b.name = "public_tool"
        tool_b.description = "All roles"

        registry.register(tool_a, ToolCategory.UTILITY, roles=["admin"])
        registry.register(tool_b, ToolCategory.UTILITY, roles=["student", "teacher", "admin"])

        admin_tools = registry.get_for_role("admin")
        student_tools = registry.get_for_role("student")

        assert len(admin_tools) == 2
        assert len(student_tools) == 1
        assert tool_b in student_tools
        assert tool_a not in student_tools

    def test_unknown_role_gets_nothing(self):
        """An unregistered role should get no tools."""
        registry = ToolRegistry()
        tool = MagicMock()
        tool.name = "test"
        tool.description = ""
        registry.register(tool, ToolCategory.UTILITY, roles=["admin"])

        tools = registry.get_for_role("unknown_role")
        assert tools == []
