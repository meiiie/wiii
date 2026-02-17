"""
Tests for code execution tools — sandboxed Python execution.

Sprint 13: Extended Tools & Self-Extending Skills.
Tests safe exec, timeout, forbidden imports, stdout capture.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.tools.code_execution_tools import (
    _check_code_safety,
    tool_execute_python,
    get_code_execution_tools,
    FORBIDDEN_IMPORTS,
    FORBIDDEN_BUILTINS,
)


# ============================================================================
# Code Safety Check Tests
# ============================================================================


class TestCodeSafety:
    """Test static code safety checks."""

    def test_safe_code_passes(self):
        assert _check_code_safety("print('hello')") is None

    def test_safe_math_code(self):
        assert _check_code_safety("x = 1 + 2\nprint(x)") is None

    def test_import_os_blocked(self):
        result = _check_code_safety("import os")
        assert result is not None
        assert "os" in result

    def test_from_os_import_blocked(self):
        result = _check_code_safety("from os import path")
        assert result is not None

    def test_import_subprocess_blocked(self):
        result = _check_code_safety("import subprocess")
        assert result is not None

    def test_import_socket_blocked(self):
        result = _check_code_safety("import socket")
        assert result is not None

    def test_eval_blocked(self):
        result = _check_code_safety("eval('2+2')")
        assert result is not None
        assert "eval" in result

    def test_exec_blocked(self):
        result = _check_code_safety("exec('print(1)')")
        assert result is not None

    def test_open_blocked(self):
        result = _check_code_safety("open('/etc/passwd')")
        assert result is not None

    def test_import_json_allowed(self):
        """json is not in the forbidden list."""
        assert _check_code_safety("import json") is None

    def test_import_math_allowed(self):
        assert _check_code_safety("import math\nprint(math.pi)") is None

    def test_all_forbidden_imports_caught(self):
        for mod in FORBIDDEN_IMPORTS:
            result = _check_code_safety(f"import {mod}")
            assert result is not None, f"import {mod} should be caught"


# ============================================================================
# Code Execution Tests
# ============================================================================


class TestCodeExecution:
    """Test actual code execution in sandbox."""

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_simple_print(self, mock_settings):
        mock_settings.code_execution_timeout = 10
        result = tool_execute_python.invoke({"code": "print('Hello Wiii')"})
        assert "Hello Wiii" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_math_calculation(self, mock_settings):
        mock_settings.code_execution_timeout = 10
        result = tool_execute_python.invoke({"code": "print(2 ** 10)"})
        assert "1024" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_syntax_error_captured(self, mock_settings):
        mock_settings.code_execution_timeout = 10
        result = tool_execute_python.invoke({"code": "print('unclosed"})
        assert "Stderr" in result or "Exit code" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_runtime_error_captured(self, mock_settings):
        mock_settings.code_execution_timeout = 10
        result = tool_execute_python.invoke({"code": "1/0"})
        assert "ZeroDivisionError" in result or "Stderr" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_no_output(self, mock_settings):
        mock_settings.code_execution_timeout = 10
        result = tool_execute_python.invoke({"code": "x = 42"})
        assert "thành công" in result

    def test_forbidden_import_rejected(self):
        result = tool_execute_python.invoke({"code": "import os\nos.system('ls')"})
        assert "không an toàn" in result

    def test_forbidden_eval_rejected(self):
        result = tool_execute_python.invoke({"code": "eval('2+2')"})
        assert "không an toàn" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_timeout_captured(self, mock_settings):
        """Code that runs too long should be killed."""
        mock_settings.code_execution_timeout = 2
        result = tool_execute_python.invoke({
            "code": "import time\ntime.sleep(10)"
        })
        assert "quá thời gian" in result


# ============================================================================
# Registration Tests
# ============================================================================


class TestRegistration:
    def test_get_code_execution_tools(self):
        tools = get_code_execution_tools()
        assert len(tools) == 1
        assert tools[0].name == "tool_execute_python"
