"""
Tests for filesystem tools — sandboxed file operations.

Sprint 13: Extended Tools & Self-Extending Skills.
Tests path traversal prevention, read/write/list operations.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.engine.tools.filesystem_tools import (
    _resolve_safe_path,
    _get_workspace_root,
    tool_read_file,
    tool_write_file,
    tool_list_directory,
    get_filesystem_tools,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with patch("app.engine.tools.filesystem_tools.settings") as mock_settings:
        mock_settings.workspace_root = str(workspace)
        yield workspace


# ============================================================================
# Path Safety Tests
# ============================================================================


class TestPathSafety:
    """Test path traversal prevention."""

    def test_resolve_relative_path(self, temp_workspace):
        resolved = _resolve_safe_path("test.txt")
        assert str(temp_workspace) in str(resolved)

    def test_resolve_nested_path(self, temp_workspace):
        resolved = _resolve_safe_path("subdir/test.txt")
        assert str(temp_workspace) in str(resolved)

    def test_reject_path_traversal_dotdot(self, temp_workspace):
        with pytest.raises(ValueError, match="nằm ngoài workspace"):
            _resolve_safe_path("../../etc/passwd")

    def test_reject_absolute_path_outside(self, temp_workspace):
        with pytest.raises(ValueError, match="nằm ngoài workspace"):
            _resolve_safe_path("/etc/passwd")

    def test_reject_sneaky_traversal(self, temp_workspace):
        with pytest.raises(ValueError, match="nằm ngoài workspace"):
            _resolve_safe_path("subdir/../../..")


# ============================================================================
# Read File Tests
# ============================================================================


class TestReadFile:
    """Test tool_read_file."""

    def test_read_existing_file(self, temp_workspace):
        (temp_workspace / "test.txt").write_text("Hello Wiii", encoding="utf-8")
        result = tool_read_file.invoke({"path": "test.txt"})
        assert result == "Hello Wiii"

    def test_read_nonexistent_file(self, temp_workspace):
        result = tool_read_file.invoke({"path": "nonexistent.txt"})
        assert "không tồn tại" in result

    def test_read_directory_fails(self, temp_workspace):
        (temp_workspace / "subdir").mkdir()
        result = tool_read_file.invoke({"path": "subdir"})
        assert "Không phải file" in result

    def test_read_large_file_rejected(self, temp_workspace):
        # Create a file larger than 1MB
        large_file = temp_workspace / "large.txt"
        large_file.write_bytes(b"x" * (1_048_577))
        result = tool_read_file.invoke({"path": "large.txt"})
        assert "quá lớn" in result

    def test_read_traversal_blocked(self, temp_workspace):
        result = tool_read_file.invoke({"path": "../../etc/passwd"})
        assert "nằm ngoài workspace" in result


# ============================================================================
# Write File Tests
# ============================================================================


class TestWriteFile:
    """Test tool_write_file."""

    def test_write_new_file(self, temp_workspace):
        result = tool_write_file.invoke({"path": "output.txt", "content": "New content"})
        assert "Đã ghi file" in result
        assert (temp_workspace / "output.txt").read_text(encoding="utf-8") == "New content"

    def test_write_creates_directories(self, temp_workspace):
        result = tool_write_file.invoke({"path": "deep/nested/file.txt", "content": "deep"})
        assert "Đã ghi file" in result
        assert (temp_workspace / "deep" / "nested" / "file.txt").exists()

    def test_write_traversal_blocked(self, temp_workspace):
        result = tool_write_file.invoke({"path": "../../evil.txt", "content": "hack"})
        assert "nằm ngoài workspace" in result


# ============================================================================
# List Directory Tests
# ============================================================================


class TestListDirectory:
    """Test tool_list_directory."""

    def test_list_root(self, temp_workspace):
        (temp_workspace / "file1.txt").write_text("a")
        (temp_workspace / "file2.txt").write_text("b")
        result = tool_list_directory.invoke({"path": "."})
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_list_with_dirs(self, temp_workspace):
        (temp_workspace / "subdir").mkdir()
        (temp_workspace / "file.txt").write_text("x")
        result = tool_list_directory.invoke({"path": "."})
        assert "📁 subdir/" in result
        assert "📄 file.txt" in result

    def test_list_empty_directory(self, temp_workspace):
        (temp_workspace / "empty").mkdir()
        result = tool_list_directory.invoke({"path": "empty"})
        assert "rỗng" in result

    def test_list_nonexistent(self, temp_workspace):
        result = tool_list_directory.invoke({"path": "nonexistent"})
        assert "không tồn tại" in result

    def test_list_file_not_dir(self, temp_workspace):
        (temp_workspace / "file.txt").write_text("x")
        result = tool_list_directory.invoke({"path": "file.txt"})
        assert "Không phải thư mục" in result


# ============================================================================
# Registration Tests
# ============================================================================


class TestRegistration:
    """Test tool function list."""

    def test_get_filesystem_tools_returns_three(self):
        tools = get_filesystem_tools()
        assert len(tools) == 3

    def test_tools_have_names(self):
        tools = get_filesystem_tools()
        names = [t.name for t in tools]
        assert "tool_read_file" in names
        assert "tool_write_file" in names
        assert "tool_list_directory" in names
