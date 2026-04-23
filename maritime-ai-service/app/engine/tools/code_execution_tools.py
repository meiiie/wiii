"""Code execution tool for Wiii AI agent."""

from __future__ import annotations

import csv
import json
import logging
from io import StringIO
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from app.core.config import settings
from app.engine.tools.runtime_context import (
    build_sandbox_execution_context,
    emit_tool_bus_event,
)
from app.sandbox.models import (
    SandboxArtifact,
    SandboxExecutionResult,
    SandboxProvider,
)
from app.sandbox.service import get_sandbox_execution_service

logger = logging.getLogger(__name__)

# Forbidden imports prevent direct access to host resources even before the code
# reaches the remote sandbox.
FORBIDDEN_IMPORTS = {
    "os",
    "subprocess",
    "shutil",
    "sys",
    "signal",
    "ctypes",
    "socket",
    "http",
    "urllib",
    "requests",
    "multiprocessing",
    "threading",
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
        if f"import {forbidden}" in code or f"from {forbidden}" in code:
            return f"Import cam: '{forbidden}' khong duoc phep vi ly do bao mat."

    for forbidden in FORBIDDEN_BUILTINS:
        if f"{forbidden}(" in code:
            return f"Ham cam: '{forbidden}()' khong duoc phep vi ly do bao mat."

    return None


def _code_timeout_seconds() -> int:
    timeout = getattr(settings, "code_execution_timeout", 30)
    return timeout if isinstance(timeout, int) else 30


def _use_opensandbox() -> bool:
    enabled = getattr(settings, "enable_privileged_sandbox", False)
    provider = getattr(settings, "sandbox_provider", "disabled")
    return enabled is True and provider == SandboxProvider.OPENSANDBOX.value


def _format_execution_result(result: SandboxExecutionResult) -> str:
    """Keep the public tool response shape stable across execution providers."""
    output_parts = []

    if result.stdout:
        output_parts.append(f"Output:\n{result.stdout.strip()}")
    if result.stderr:
        output_parts.append(f"Stderr:\n{result.stderr.strip()}")
    if result.error:
        output_parts.append(f"Error: {result.error}")
    if result.exit_code not in (None, 0):
        output_parts.append(f"Exit code: {result.exit_code}")
    if result.artifacts:
        output_parts.append(
            "Artifacts:\n" + "\n".join(_summarize_artifact(artifact) for artifact in result.artifacts)
        )

    if result.success and not output_parts:
        return "Code chạy thành công (không có output)"

    return "\n\n".join(output_parts) if output_parts else "Code chạy thất bại."


def _summarize_artifact(artifact: SandboxArtifact) -> str:
    location = artifact.path or artifact.url or ""
    if location:
        return f"- {artifact.name} ({artifact.content_type}) -> {location}"
    return f"- {artifact.name} ({artifact.content_type})"


def _run_python_subprocess(code: str) -> SandboxExecutionResult:
    """Legacy host subprocess execution retained for non-sandbox deployments."""
    timeout = _code_timeout_seconds()
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(code)
            temp_path = handle.name

        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return SandboxExecutionResult(
            success=result.returncode == 0,
            stdout=(result.stdout or "").strip(),
            stderr=(result.stderr or "").strip(),
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SandboxExecutionResult(
            success=False,
            error=(
                f"Code chay qua thoi gian ({timeout}s). "
                "Kiem tra vong lap vo han."
            ),
            exit_code=124,
        )
    except Exception as exc:
        logger.error("[CODE_EXEC] Error: %s", exc)
        return SandboxExecutionResult(
            success=False,
            error=f"Lỗi chạy code: {exc}",
        )
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception as exc:
                logger.debug("Temp file cleanup failed: %s", exc)


def _run_python_in_opensandbox(code: str) -> SandboxExecutionResult:
    """Execute Python in the configured privileged sandbox."""
    service = get_sandbox_execution_service()
    try:
        result = service.execute_profile_sync(
            "python_exec",
            code=code,
            timeout_seconds=_code_timeout_seconds(),
            runtime_template=getattr(settings, "opensandbox_code_template", None) or None,
            context=build_sandbox_execution_context(
                "tool_execute_python",
                approval_scope="privileged_execution",
            ),
        )
        if isinstance(result, SandboxExecutionResult):
            return result
        return SandboxExecutionResult(
            success=False,
            error="OpenSandbox executor tra ve ket qua khong hop le.",
        )
    except Exception as exc:
        logger.error("[CODE_EXEC] OpenSandbox execution failed: %s", exc, exc_info=True)
        return SandboxExecutionResult(
            success=False,
            error=(
                "OpenSandbox duoc bat nhung execution service gap loi. "
                f"Chi tiet: {exc}"
            ),
        )


def _artifact_slug(value: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base[:48] or "artifact"


def _build_document_summary(artifact: SandboxArtifact) -> str:
    lines = [
        f"# {artifact.name}",
        "",
        f"- Content type: {artifact.content_type}",
    ]
    if artifact.path:
        lines.append(f"- Sandbox path: {artifact.path}")
    if artifact.url:
        lines.append(f"- Download URL: {artifact.url}")
    if artifact.metadata.get("content_truncated"):
        lines.append("- Inline preview was truncated for streaming safety")
    if artifact.metadata.get("size_bytes") is not None:
        lines.append(f"- Size bytes: {artifact.metadata['size_bytes']}")
    return "\n".join(lines)


def _build_table_payload(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    if not stripped:
        return None

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        pass

    try:
        reader = csv.DictReader(StringIO(stripped))
        rows = list(reader)
    except Exception as e:
        logger.debug("CSV parse failed: %s", e)
        return None

    if not rows:
        return None
    return json.dumps(rows, ensure_ascii=False)


def _artifact_event_payload(
    artifact: SandboxArtifact,
    *,
    index: int,
    result: SandboxExecutionResult,
) -> dict[str, object]:
    name = artifact.name or "artifact"
    slug = _artifact_slug(name)
    execution_id = str(result.metadata.get("execution_id") or result.sandbox_id or "sandbox")
    artifact_id = f"{execution_id}-{index}-{slug}"
    suffix = Path(name).suffix.lower()
    inline_content = artifact.metadata.get("inline_content")
    inline_encoding = artifact.metadata.get("inline_encoding")
    metadata = {
        "content_type": artifact.content_type,
        "file_path": artifact.path,
        "file_url": artifact.url,
        "sandbox_id": result.sandbox_id,
        "execution_id": result.metadata.get("execution_id"),
        "generated_via": "opensandbox",
        **artifact.metadata,
    }

    artifact_type = "document"
    content = _build_document_summary(artifact)
    language = ""

    if artifact.content_type == "text/html" or suffix in {".html", ".htm"}:
        artifact_type = "html"
        if isinstance(inline_content, str) and inline_content:
            content = inline_content
    elif artifact.content_type.startswith("image/") and artifact.content_type != "image/svg+xml":
        artifact_type = "chart"
        if isinstance(inline_content, str) and inline_content:
            content = inline_content
            if inline_encoding == "base64":
                metadata.setdefault("image_encoding", "base64")
    elif suffix == ".xlsx":
        artifact_type = "excel"
    elif suffix in {".json", ".csv"} and isinstance(inline_content, str):
        table_payload = _build_table_payload(inline_content)
        if table_payload:
            artifact_type = "table"
            content = table_payload
    elif suffix in {".py", ".js", ".ts", ".tsx", ".jsx"} and isinstance(inline_content, str):
        artifact_type = "code"
        content = inline_content
        language = suffix.lstrip(".")
    elif isinstance(inline_content, str) and inline_content and (
        artifact.content_type.startswith("text/") or suffix in {".md", ".txt"}
    ):
        content = inline_content

    return {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "title": name,
        "content": content,
        "language": language,
        "metadata": metadata,
    }


def _emit_execution_artifacts(result: SandboxExecutionResult) -> None:
    for index, artifact in enumerate(result.artifacts):
        emit_tool_bus_event(
            {
                "type": "artifact",
                "content": _artifact_event_payload(
                    artifact,
                    index=index,
                    result=result,
                ),
            }
        )


@tool
def tool_execute_python(code: str) -> str:
    """
    Run Python code with the configured execution backend.

    Args:
        code: Python source code to execute. If the task is a chart, plot, or
            visual output request, the code should save a real image file
            (prefer PNG via matplotlib/plotly) into the working directory so
            the sandbox can return it as an artifact.

    Returns:
        User-facing stdout/stderr/error summary.
    """
    safety_issue = _check_code_safety(code)
    if safety_issue:
        return f"Code khong an toan: {safety_issue}"

    if _use_opensandbox():
        result = _run_python_in_opensandbox(code)
        _emit_execution_artifacts(result)
        return _format_execution_result(result)

    return _format_execution_result(_run_python_subprocess(code))


def get_code_execution_tools() -> list:
    """Get all code execution tools (for registration)."""
    return [tool_execute_python]
