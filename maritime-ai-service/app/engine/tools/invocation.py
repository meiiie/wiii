"""Helpers for consistent tool invocation across agent loops."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Iterable, Optional

from app.engine.tools.runtime_context import ToolRuntimeContext, tool_runtime_scope


def get_tool_by_name(tools: Iterable[Any], tool_name: str) -> Any | None:
    """Return the first tool whose public name matches."""
    for tool in tools:
        name = getattr(tool, "name", getattr(tool, "__name__", ""))
        if name == tool_name:
            return tool
    return None


def _query_snippet_from_args(tool_args: Any) -> str:
    """Extract a short human-readable query snippet for metrics."""
    if isinstance(tool_args, dict):
        for key in (
            "query",
            "expression",
            "url",
            "message",
            "content",
            "note",
            "code",
        ):
            value = tool_args.get(key)
            if value:
                return str(value)[:100]
        return str(tool_args)[:100]
    return str(tool_args)[:100]


def _record_tool_usage_safe(
    *,
    tool_name: str,
    success: bool,
    latency_ms: int,
    query_snippet: str,
    error_message: str,
    runtime_context: Optional[ToolRuntimeContext],
) -> None:
    """Bridge tool invocation telemetry into the skill metrics layer."""
    try:
        from app.engine.skills.skill_tool_bridge import record_tool_usage

        record_tool_usage(
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            query_snippet=query_snippet[:100],
            error_message=error_message[:200],
            organization_id=(runtime_context.organization_id or "") if runtime_context else "",
        )
    except Exception:
        # Telemetry must never break tool execution.
        pass


async def invoke_tool_with_runtime(
    tool: Any,
    tool_args: Any,
    *,
    tool_name: Optional[str] = None,
    runtime_context_base: Optional[ToolRuntimeContext] = None,
    tool_call_id: Optional[str] = None,
    query_snippet: Optional[str] = None,
    prefer_async: bool = True,
    run_sync_in_thread: bool = False,
) -> Any:
    """Invoke a tool under the current runtime scope and record usage metrics."""
    resolved_tool_name = tool_name or getattr(tool, "name", getattr(tool, "__name__", "tool"))
    runtime_context = (
        runtime_context_base.for_tool(resolved_tool_name, tool_call_id=tool_call_id)
        if runtime_context_base
        else None
    )
    snippet = (query_snippet or _query_snippet_from_args(tool_args))[:100]
    started_at = time.perf_counter()
    success = False
    error_message = ""

    try:
        if runtime_context is not None:
            with tool_runtime_scope(runtime_context):
                result = await _invoke_tool(
                    tool,
                    tool_args,
                    prefer_async=prefer_async,
                    run_sync_in_thread=run_sync_in_thread,
                )
        else:
            result = await _invoke_tool(
                tool,
                tool_args,
                prefer_async=prefer_async,
                run_sync_in_thread=run_sync_in_thread,
            )
        success = True
        return result
    except Exception as exc:
        error_message = str(exc)[:200]
        raise
    finally:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        _record_tool_usage_safe(
            tool_name=resolved_tool_name,
            success=success,
            latency_ms=latency_ms,
            query_snippet=snippet,
            error_message=error_message,
            runtime_context=runtime_context,
        )


async def _invoke_tool(
    tool: Any,
    tool_args: Any,
    *,
    prefer_async: bool,
    run_sync_in_thread: bool,
) -> Any:
    """Dispatch to the best available LangChain invocation path."""
    if prefer_async and hasattr(tool, "ainvoke"):
        return await tool.ainvoke(tool_args)
    if run_sync_in_thread:
        return await asyncio.to_thread(tool.invoke, tool_args)
    return tool.invoke(tool_args)
