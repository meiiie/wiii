"""
Filesystem Tools — Sandboxed file operations for Wiii AI agent.

Provides read/write/list tools restricted to workspace_root to prevent
path traversal attacks. All paths are resolved and validated.

Sprint 13: Extended Tools & Self-Extending Skills.
"""

import logging
from pathlib import Path

from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_workspace_root() -> Path:
    """Get the resolved workspace root directory."""
    root = Path(getattr(settings, "workspace_root", "~/.wiii/workspace"))
    return root.expanduser().resolve()


def _resolve_safe_path(path_str: str) -> Path:
    """
    Resolve a path and verify it stays within workspace root.

    Prevents path traversal attacks (e.g., ../../etc/passwd).

    Args:
        path_str: User-provided path string

    Returns:
        Resolved absolute Path within workspace

    Raises:
        ValueError: If path escapes workspace root
    """
    workspace = _get_workspace_root()

    # Resolve the full path
    resolved = (workspace / path_str).resolve()

    # Check that resolved path is still within workspace
    try:
        resolved.relative_to(workspace)
    except ValueError:
        raise ValueError(
            f"Đường dẫn '{path_str}' nằm ngoài workspace. "
            f"Chỉ được truy cập trong: {workspace}"
        )

    return resolved


@tool
def tool_read_file(path: str) -> str:
    """
    Đọc nội dung file trong workspace.

    Args:
        path: Đường dẫn tương đối từ workspace root

    Returns:
        Nội dung file dạng text
    """
    try:
        resolved = _resolve_safe_path(path)

        if not resolved.exists():
            return f"❌ File không tồn tại: {path}"

        if not resolved.is_file():
            return f"❌ Không phải file: {path}"

        # Limit file size to 1MB
        size = resolved.stat().st_size
        if size > 1_048_576:
            return f"❌ File quá lớn ({size:,} bytes). Giới hạn: 1MB"

        content = resolved.read_text(encoding="utf-8", errors="replace")
        return content

    except ValueError as e:
        return f"❌ {e}"
    except Exception as e:
        logger.error("[FS_TOOLS] read_file error: %s", e)
        return f"❌ Lỗi đọc file: {e}"


@tool
def tool_write_file(path: str, content: str) -> str:
    """
    Ghi nội dung vào file trong workspace.

    Args:
        path: Đường dẫn tương đối từ workspace root
        content: Nội dung cần ghi

    Returns:
        Thông báo thành công hoặc lỗi
    """
    try:
        resolved = _resolve_safe_path(path)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding="utf-8")
        return f"✅ Đã ghi file: {path} ({len(content)} chars)"

    except ValueError as e:
        return f"❌ {e}"
    except Exception as e:
        logger.error("[FS_TOOLS] write_file error: %s", e)
        return f"❌ Lỗi ghi file: {e}"


@tool
def tool_list_directory(path: str = ".") -> str:
    """
    Liệt kê nội dung thư mục trong workspace.

    Args:
        path: Đường dẫn tương đối từ workspace root (mặc định: root)

    Returns:
        Danh sách files và thư mục
    """
    try:
        resolved = _resolve_safe_path(path)

        if not resolved.exists():
            return f"❌ Thư mục không tồn tại: {path}"

        if not resolved.is_dir():
            return f"❌ Không phải thư mục: {path}"

        entries = []
        for item in sorted(resolved.iterdir()):
            if item.is_dir():
                entries.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"📄 {item.name} ({size:,} bytes)")

        if not entries:
            return f"📂 Thư mục rỗng: {path}"

        return f"📂 {path} ({len(entries)} items):\n" + "\n".join(entries)

    except ValueError as e:
        return f"❌ {e}"
    except Exception as e:
        logger.error("[FS_TOOLS] list_directory error: %s", e)
        return f"❌ Lỗi liệt kê: {e}"


def get_filesystem_tools() -> list:
    """Get all filesystem tools (for registration)."""
    return [tool_read_file, tool_write_file, tool_list_directory]
