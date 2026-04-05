"""Reusable helpers for the OpenSandbox executor shell."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Optional

from app.core.generated_files import is_allowed_generated_file, persist_generated_file


async def build_execution_result_impl(
    *,
    execution: Any,
    sandbox: Any,
    request: Any,
    sdk: Any,
    sandbox_id: Optional[str],
    provider_metadata: dict[str, Any],
    collect_artifacts_fn: Any,
    result_cls: Any,
) -> Any:
    """Normalize a provider execution payload into Wiii's execution result."""
    stdout = "".join(
        message.text
        for message in getattr(execution.logs, "stdout", [])
        if message.text
    ).strip()
    stderr = "".join(
        message.text
        for message in getattr(execution.logs, "stderr", [])
        if message.text
    ).strip()
    result_text = "\n".join(
        item.text
        for item in getattr(execution, "result", [])
        if getattr(item, "text", None)
    ).strip()

    error = getattr(execution, "error", None)
    success = error is None
    exit_code = 0 if success else 1
    artifacts = await collect_artifacts_fn(
        execution=execution,
        sandbox=sandbox,
        request=request,
        sdk=sdk,
    )

    if result_text:
        stdout = "\n".join(
            part for part in [stdout, result_text] if part
        ).strip()

    if error is not None:
        error_lines = [f"{error.name}: {error.value}"]
        traceback_lines = [
            line for line in getattr(error, "traceback", []) if line
        ]
        if traceback_lines:
            error_lines.extend(traceback_lines)
        stderr = "\n".join(
            part for part in [stderr, "\n".join(error_lines)] if part
        ).strip()

    return result_cls(
        success=success,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        error=None if success else f"{error.name}: {error.value}",
        sandbox_id=sandbox_id,
        artifacts=artifacts,
        metadata={
            **provider_metadata,
            "sandbox_id": sandbox_id,
            "execution_id": getattr(execution, "id", None),
            "artifact_count": len(artifacts),
        },
    )


def publish_harvested_file_impl(
    filename: str,
    raw_content: Any,
) -> Optional[Path]:
    """Persist a harvested sandbox file into Wiii's generated workspace."""
    if raw_content is None or not is_allowed_generated_file(filename):
        return None
    if isinstance(raw_content, str):
        return persist_generated_file(filename, raw_content, prefix="sandbox")
    if isinstance(raw_content, (bytes, bytearray)):
        return persist_generated_file(filename, bytes(raw_content), prefix="sandbox")
    return None


def build_search_roots_impl(
    working_directory: Optional[str],
    normalize_path_fn: Any,
) -> list[str]:
    roots: list[str] = []
    for candidate in (working_directory, "/workspace", "/tmp"):
        normalized = normalize_path_fn(candidate)
        if normalized and normalized not in roots:
            roots.append(normalized)
    return roots


def build_search_entry_impl(
    path: str,
    pattern: str,
    sdk: Any,
) -> Any:
    search_entry_cls = getattr(sdk, "search_entry", None)
    if search_entry_cls is None:
        return {"path": path, "pattern": pattern}
    for kwargs in (
        {"path": path, "pattern": pattern, "recursive": True},
        {"path": path, "pattern": pattern},
    ):
        try:
            return search_entry_cls(**kwargs)
        except TypeError:
            continue
    return search_entry_cls(path=path, pattern=pattern)


def coerce_text_content_impl(raw_content: Any) -> Optional[str]:
    if raw_content is None:
        return None
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, (bytes, bytearray)):
        try:
            return bytes(raw_content).decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def normalize_path_impl(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(PurePosixPath(str(value)))


def read_field_impl(item: Any, *names: str) -> Any:
    if isinstance(item, dict):
        for name in names:
            if name in item:
                return item[name]
        return None

    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return None


def is_image_content_impl(content_type: str) -> bool:
    return content_type.startswith("image/") and content_type != "image/svg+xml"


async def cleanup_sandbox_impl(*, sandbox: Any, logger: Any) -> None:
    """Terminate remote sandbox resources and close local SDK transports."""
    if sandbox is None:
        return

    try:
        await sandbox.kill()
    except Exception as exc:
        logger.warning(
            "[OPENSANDBOX] failed to terminate sandbox %s: %s",
            getattr(sandbox, "id", None),
            exc,
        )

    try:
        await sandbox.close()
    except Exception as exc:
        logger.warning(
            "[OPENSANDBOX] failed to close sandbox %s: %s",
            getattr(sandbox, "id", None),
            exc,
        )
