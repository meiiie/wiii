"""Tests for code execution tools."""

from __future__ import annotations

from queue import Queue
from unittest.mock import patch

from app.engine.multi_agent.graph_streaming import _EVENT_QUEUES
from app.engine.tools.code_execution_tools import (
    FORBIDDEN_BUILTINS,
    FORBIDDEN_IMPORTS,
    _check_code_safety,
    get_code_execution_tools,
    tool_execute_python,
)
from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
from app.sandbox.models import SandboxArtifact, SandboxExecutionResult, SandboxWorkloadKind


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
        assert _check_code_safety("import json") is None

    def test_import_math_allowed(self):
        assert _check_code_safety("import math\nprint(math.pi)") is None

    def test_all_forbidden_imports_caught(self):
        for mod in FORBIDDEN_IMPORTS:
            result = _check_code_safety(f"import {mod}")
            assert result is not None, f"import {mod} should be caught"

    def test_all_forbidden_builtins_caught(self):
        for builtin in FORBIDDEN_BUILTINS:
            result = _check_code_safety(f"{builtin}('x')")
            assert result is not None, f"{builtin} should be caught"


class TestCodeExecution:
    """Test actual code execution across legacy and sandbox backends."""

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
        assert "Code chay thanh cong" in result

    def test_forbidden_import_rejected(self):
        result = tool_execute_python.invoke({"code": "import os\nos.system('ls')"})
        assert "Code khong an toan" in result

    def test_forbidden_eval_rejected(self):
        result = tool_execute_python.invoke({"code": "eval('2+2')"})
        assert "Code khong an toan" in result

    @patch("app.engine.tools.code_execution_tools.settings")
    def test_timeout_captured(self, mock_settings):
        mock_settings.code_execution_timeout = 1
        result = tool_execute_python.invoke(
            {"code": "import time\ntime.sleep(10)"}
        )
        assert "qua thoi gian" in result

    @patch("app.engine.tools.code_execution_tools.get_sandbox_execution_service")
    @patch("app.engine.tools.code_execution_tools.subprocess.run")
    @patch("app.engine.tools.code_execution_tools.settings")
    def test_routes_to_opensandbox_when_enabled(
        self,
        mock_settings,
        mock_subprocess_run,
        mock_get_sandbox_execution_service,
    ):
        class _Service:
            def execute_profile_sync(self, profile_id, **kwargs):
                assert profile_id == "python_exec"
                assert kwargs["timeout_seconds"] == 45
                assert kwargs["context"].tool_name == "tool_execute_python"
                return SandboxExecutionResult(
                    success=True,
                    stdout="Sandbox hello",
                )

        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.code_execution_timeout = 45
        mock_get_sandbox_execution_service.return_value = _Service()
        mock_subprocess_run.side_effect = AssertionError(
            "legacy subprocess must not be used"
        )

        result = tool_execute_python.invoke({"code": "print('hello')"})

        assert "Sandbox hello" in result

    @patch("app.engine.tools.code_execution_tools.get_sandbox_execution_service")
    @patch("app.engine.tools.code_execution_tools.settings")
    def test_opensandbox_context_includes_runtime_scope(
        self,
        mock_settings,
        mock_get_sandbox_execution_service,
    ):
        class _Service:
            def execute_profile_sync(self, profile_id, **kwargs):
                context = kwargs["context"]
                assert profile_id == "python_exec"
                assert context.source == "agentic_loop"
                assert context.organization_id == "org-1"
                assert context.user_id == "user-1"
                assert context.session_id == "sess-1"
                assert context.request_id == "req-1"
                assert context.metadata["mcp_call_id"] == "mcp-call-1"
                assert context.metadata["node"] == "tutor_agent"
                assert context.metadata["tool_call_id"] == "tc-1"
                return SandboxExecutionResult(success=True, stdout="Sandbox hello")

        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.code_execution_timeout = 45
        mock_get_sandbox_execution_service.return_value = _Service()

        with tool_runtime_scope(
            build_tool_runtime_context(
                event_bus_id="bus-1",
                request_id="req-1",
                session_id="sess-1",
                organization_id="org-1",
                user_id="user-1",
                user_role="admin",
                node="tutor_agent",
                source="agentic_loop",
                metadata={"mcp_call_id": "mcp-call-1"},
            ).for_tool("tool_execute_python", tool_call_id="tc-1")
        ):
            result = tool_execute_python.invoke({"code": "print('hello')"})

        assert "Sandbox hello" in result

    @patch("app.engine.tools.code_execution_tools.get_sandbox_execution_service")
    @patch("app.engine.tools.code_execution_tools.settings")
    def test_fails_closed_when_opensandbox_executor_missing(
        self,
        mock_settings,
        mock_get_sandbox_execution_service,
    ):
        class _Service:
            def execute_profile_sync(self, profile_id, **kwargs):
                return SandboxExecutionResult(
                    success=False,
                    error="No privileged sandbox executor is configured for this deployment.",
                )

        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.code_execution_timeout = 30
        mock_get_sandbox_execution_service.return_value = _Service()

        result = tool_execute_python.invoke({"code": "print('hello')"})

        assert "No privileged sandbox executor is configured" in result

    @patch("app.engine.tools.code_execution_tools.get_sandbox_execution_service")
    @patch("app.engine.tools.code_execution_tools.settings")
    def test_formats_failed_opensandbox_execution(
        self,
        mock_settings,
        mock_get_sandbox_execution_service,
    ):
        class _Service:
            def execute_profile_sync(self, profile_id, **kwargs):
                return SandboxExecutionResult(
                    success=False,
                    stdout="partial output",
                    stderr="traceback",
                    error="sandbox failed",
                    exit_code=1,
                )

        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.code_execution_timeout = 30
        mock_get_sandbox_execution_service.return_value = _Service()

        result = tool_execute_python.invoke({"code": "print('hello')"})

        assert "partial output" in result
        assert "traceback" in result
        assert "sandbox failed" in result
        assert "Exit code: 1" in result

    @patch("app.engine.tools.code_execution_tools.get_sandbox_execution_service")
    @patch("app.engine.tools.code_execution_tools.settings")
    def test_emits_artifact_events_for_opensandbox_outputs(
        self,
        mock_settings,
        mock_get_sandbox_execution_service,
    ):
        class _Service:
            def execute_profile_sync(self, profile_id, **kwargs):
                return SandboxExecutionResult(
                    success=True,
                    stdout="done",
                    sandbox_id="sandbox-123",
                    metadata={"execution_id": "exec-456"},
                    artifacts=[
                        SandboxArtifact(
                            name="landing-page.html",
                            content_type="text/html",
                            path="/home/appuser/.wiii/workspace/generated/landing-page_20260309.html",
                            url="/api/v1/generated-files/landing-page_20260309.html",
                            metadata={
                                "inline_content": "<html><body>Hello</body></html>",
                                "inline_encoding": "text",
                            },
                        ),
                        SandboxArtifact(
                            name="chart.png",
                            content_type="image/png",
                            path="/home/appuser/.wiii/workspace/generated/chart_20260309.png",
                            url="/api/v1/generated-files/chart_20260309.png",
                            metadata={
                                "inline_content": "YmFzZTY0",
                                "inline_encoding": "base64",
                            },
                        ),
                        SandboxArtifact(
                            name="report.xlsx",
                            content_type=(
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            ),
                            path="/home/appuser/.wiii/workspace/generated/report_20260309.xlsx",
                            url="/api/v1/generated-files/report_20260309.xlsx",
                        ),
                        SandboxArtifact(
                            name="brief.docx",
                            content_type=(
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            ),
                            path="/home/appuser/.wiii/workspace/generated/brief_20260309.docx",
                            url="/api/v1/generated-files/brief_20260309.docx",
                        ),
                    ],
                )

        mock_settings.enable_privileged_sandbox = True
        mock_settings.sandbox_provider = "opensandbox"
        mock_settings.code_execution_timeout = 30
        mock_get_sandbox_execution_service.return_value = _Service()

        bus_id = "bus-artifacts"
        queue = Queue()
        _EVENT_QUEUES[bus_id] = queue

        try:
            with tool_runtime_scope(
                build_tool_runtime_context(
                    event_bus_id=bus_id,
                    request_id="req-1",
                    session_id="sess-1",
                    organization_id="org-1",
                    user_id="user-1",
                    user_role="admin",
                    node="direct",
                    source="agentic_loop",
                ).for_tool("tool_execute_python", tool_call_id="tc-1")
            ):
                result = tool_execute_python.invoke({"code": "print('hello')"})
        finally:
            _EVENT_QUEUES.pop(bus_id, None)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        assert "Artifacts:" in result
        assert "landing-page.html" in result
        assert "chart.png" in result
        assert "report.xlsx" in result
        assert "brief.docx" in result

        assert len(events) == 4
        assert [event["type"] for event in events] == ["artifact", "artifact", "artifact", "artifact"]
        assert events[0]["content"]["artifact_type"] == "html"
        assert events[0]["content"]["content"] == "<html><body>Hello</body></html>"
        assert events[1]["content"]["artifact_type"] == "chart"
        assert events[1]["content"]["content"] == "YmFzZTY0"
        assert events[2]["content"]["artifact_type"] == "excel"
        assert events[2]["content"]["metadata"]["file_url"] == "/api/v1/generated-files/report_20260309.xlsx"
        assert events[3]["content"]["artifact_type"] == "document"
        assert "/home/appuser/.wiii/workspace/generated/brief_20260309.docx" in events[3]["content"]["content"]
        assert events[0]["content"]["metadata"]["request_id"] == "req-1"
        assert events[0]["content"]["metadata"]["tool_call_id"] == "tc-1"


class TestRegistration:
    def test_get_code_execution_tools(self):
        tools = get_code_execution_tools()
        assert len(tools) == 1
        assert tools[0].name == "tool_execute_python"
