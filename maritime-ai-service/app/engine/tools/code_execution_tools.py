"""
Code Execution Tool — Sandboxed Python execution for Wiii AI agent.

Runs user-provided Python code in a subprocess with:
- Timeout (default: 30s)
- Import blocklist (no os, subprocess, etc.)
- Stdout/stderr capture

Sprint 13: Extended Tools & Self-Extending Skills.
"""

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Forbidden imports — prevent code from accessing system resources
FORBIDDEN_IMPORTS = {
    "os", "subprocess", "shutil", "sys", "signal",
    "ctypes", "socket", "http", "urllib", "requests",
    "multiprocessing", "threading",
}

# Forbidden builtins
FORBIDDEN_BUILTINS = {"exec", "eval", "compile", "__import__", "open"}


def _check_code_safety(code: str) -> Optional[str]:
    """
    Static check for forbidden patterns in user code.

    Returns:
        None if safe, or error message string if unsafe
    """
    for forbidden in FORBIDDEN_IMPORTS:
        # Check for import statements
        if f"import {forbidden}" in code or f"from {forbidden}" in code:
            return f"Import cấm: '{forbidden}' không được phép vì lý do bảo mật."

    for forbidden in FORBIDDEN_BUILTINS:
        if f"{forbidden}(" in code:
            return f"Hàm cấm: '{forbidden}()' không được phép vì lý do bảo mật."

    return None


@tool
def tool_execute_python(code: str) -> str:
    """
    Chạy code Python trong sandbox an toàn.

    Code được chạy trong subprocess riêng biệt với timeout.
    Không thể truy cập hệ thống (os, subprocess, socket bị cấm).

    Args:
        code: Mã Python cần chạy

    Returns:
        Kết quả stdout hoặc thông báo lỗi
    """
    # Safety check
    safety_issue = _check_code_safety(code)
    if safety_issue:
        return f"❌ Code không an toàn: {safety_issue}"

    timeout = getattr(settings, "code_execution_timeout", 30)

    # Write code to temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_path = f.name

        # Run in subprocess with timeout
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )

        output_parts = []
        if result.stdout:
            output_parts.append(f"📤 Output:\n{result.stdout.strip()}")
        if result.stderr:
            output_parts.append(f"⚠️ Stderr:\n{result.stderr.strip()}")
        if result.returncode != 0:
            output_parts.append(f"❌ Exit code: {result.returncode}")

        if not output_parts:
            return "✅ Code chạy thành công (không có output)"

        return "\n\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"❌ Code chạy quá thời gian ({timeout}s). Kiểm tra vòng lặp vô hạn."

    except Exception as e:
        logger.error("[CODE_EXEC] Error: %s", e)
        return f"❌ Lỗi chạy code: {e}"

    finally:
        # Clean up temp file
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.debug("Temp file cleanup failed: %s", e)


def get_code_execution_tools() -> list:
    """Get all code execution tools (for registration)."""
    return [tool_execute_python]
