"""Concurrent execution of read-only tool calls within a single LLM turn.

Pattern from Claude Code: read-only tools run concurrently (max 10 by default),
state-modifying tools run serially. Results are returned in original tool_call order.

Feature-gated by ``settings.enable_concurrent_tool_execution`` (default: False).
When disabled, falls back to sequential execution (existing behavior).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Read-only tools: no side effects, safe to run concurrently
_READONLY_TOOL_PREFIXES = frozenset({
    "tool_web_search",
    "tool_knowledge_search",
    "tool_maritime_search",
    "tool_search_news",
    "tool_search_legal",
    "tool_current_datetime",
    "tool_calculator",
    "tool_think",
    "tool_report_progress",
    "tool_search_maritime",
})

# State-modifying tools: must run serially (generate output, modify state)
_STATE_MODIFYING_TOOL_PREFIXES = frozenset({
    "tool_execute_python",
    "tool_generate_visual",
    "tool_create_visual_code",
    "tool_generate_mermaid",
    "tool_generate_html_file",
    "tool_generate_excel_file",
    "tool_generate_word_document",
    "tool_generate_interactive_chart",
    "tool_browser_snapshot_url",
    "handoff_to_agent",
})


@dataclass
class ToolCallResult:
    """Result of a single tool call execution."""

    tool_call_id: str
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


def is_readonly_tool(tool_name: str) -> bool:
    """Check if a tool is read-only (safe for concurrent execution)."""
    return any(tool_name.startswith(p) or tool_name == p for p in _READONLY_TOOL_PREFIXES)


def is_state_modifying_tool(tool_name: str) -> bool:
    """Check if a tool modifies state (must run serially)."""
    return any(tool_name.startswith(p) or tool_name == p for p in _STATE_MODIFYING_TOOL_PREFIXES)


async def execute_tool_calls_concurrent(
    tool_calls: List[Dict[str, Any]],
    invoke_fn: Callable,
    *,
    max_concurrent: Optional[int] = None,
) -> List[ToolCallResult]:
    """Execute tool calls with read-only parallelism.

    Args:
        tool_calls: List of tool call dicts with 'id', 'name', 'args'.
        invoke_fn: Async callable ``invoke_fn(tool_call_dict) -> result``.
        max_concurrent: Override for max concurrent read-only tools.

    Returns:
        List of ToolCallResult in original tool_call order.
    """
    if not settings.enable_concurrent_tool_execution:
        # Feature disabled: sequential execution (existing behavior)
        return await _execute_sequential(tool_calls, invoke_fn)

    max_c = max_concurrent or getattr(settings, "concurrent_tool_max_workers", 10)

    # Partition into readonly and state-modifying batches
    readonly_indices: List[int] = []
    readonly_calls: List[Dict[str, Any]] = []
    state_modifying_indices: List[int] = []
    state_modifying_calls: List[Dict[str, Any]] = []

    for i, tc in enumerate(tool_calls):
        name = tc.get("name", "")
        if is_readonly_tool(name) and not is_state_modifying_tool(name):
            readonly_indices.append(i)
            readonly_calls.append(tc)
        else:
            state_modifying_indices.append(i)
            state_modifying_calls.append(tc)

    # Execute readonly tools concurrently
    readonly_results = await _execute_concurrent(readonly_calls, invoke_fn, max_concurrent=max_c)

    # Execute state-modifying tools sequentially
    state_modifying_results = await _execute_sequential(state_modifying_calls, invoke_fn)

    # Merge back in original order
    all_results: List[ToolCallResult] = [None] * len(tool_calls)  # type: ignore[list-item]
    for i, result in zip(readonly_indices, readonly_results):
        all_results[i] = result
    for i, result in zip(state_modifying_indices, state_modifying_results):
        all_results[i] = result

    return all_results


async def _execute_concurrent(
    tool_calls: List[Dict[str, Any]],
    invoke_fn: Callable,
    *,
    max_concurrent: int = 10,
) -> List[ToolCallResult]:
    """Execute multiple tool calls concurrently with bounded parallelism."""
    if not tool_calls:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_one(tc: Dict[str, Any]) -> ToolCallResult:
        tc_id = tc.get("id", "unknown")
        tc_name = tc.get("name", "unknown")
        async with semaphore:
            t_start = time.perf_counter()
            try:
                result = await invoke_fn(tc)
                duration_ms = (time.perf_counter() - t_start) * 1000
                return ToolCallResult(tool_call_id=tc_id, tool_name=tc_name, result=result, duration_ms=duration_ms)
            except Exception as e:
                duration_ms = (time.perf_counter() - t_start) * 1000
                return ToolCallResult(tool_call_id=tc_id, tool_name=tc_name, error=str(e), duration_ms=duration_ms)

    return await asyncio.gather(*[_run_one(tc) for tc in tool_calls])


async def _execute_sequential(
    tool_calls: List[Dict[str, Any]],
    invoke_fn: Callable,
) -> List[ToolCallResult]:
    """Execute tool calls sequentially (fallback / state-modifying path)."""
    results: List[ToolCallResult] = []
    for tc in tool_calls:
        tc_id = tc.get("id", "unknown")
        tc_name = tc.get("name", "unknown")
        t_start = time.perf_counter()
        try:
            result = await invoke_fn(tc)
            duration_ms = (time.perf_counter() - t_start) * 1000
            results.append(ToolCallResult(tool_call_id=tc_id, tool_name=tc_name, result=result, duration_ms=duration_ms))
        except Exception as e:
            duration_ms = (time.perf_counter() - t_start) * 1000
            results.append(ToolCallResult(tool_call_id=tc_id, tool_name=tc_name, error=str(e), duration_ms=duration_ms))
    return results
