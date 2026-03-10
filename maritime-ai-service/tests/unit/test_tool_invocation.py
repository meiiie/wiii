"""Tests for the shared tool invocation helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.engine.tools.invocation import invoke_tool_with_runtime
from app.engine.tools.runtime_context import (
    build_tool_runtime_context,
    get_current_tool_runtime_context,
)


class _AsyncTool:
    name = "tool_async_demo"

    async def ainvoke(self, tool_args):
        runtime = get_current_tool_runtime_context()
        assert runtime is not None
        assert runtime.tool_name == "tool_async_demo"
        assert runtime.tool_call_id == "tc-1"
        return f"ok:{tool_args['query']}"


class _SyncTool:
    name = "tool_sync_demo"

    def invoke(self, tool_args):
        runtime = get_current_tool_runtime_context()
        assert runtime is not None
        assert runtime.tool_name == "tool_sync_demo"
        assert runtime.tool_call_id == "tc-2"
        return f"sync:{tool_args['query']}"


class _FailingTool:
    name = "tool_failing_demo"

    async def ainvoke(self, tool_args):
        raise RuntimeError(f"boom:{tool_args['query']}")


@pytest.mark.asyncio
async def test_invoke_tool_with_runtime_records_success():
    runtime_context = build_tool_runtime_context(
        request_id="req-1",
        session_id="sess-1",
        organization_id="org-1",
        user_id="user-1",
        user_role="admin",
        node="tutor_agent",
        source="agentic_loop",
    )

    with patch("app.engine.skills.skill_tool_bridge.record_tool_usage") as mock_record:
        result = await invoke_tool_with_runtime(
            _AsyncTool(),
            {"query": "ports"},
            runtime_context_base=runtime_context,
            tool_call_id="tc-1",
            query_snippet="ports",
        )

    assert result == "ok:ports"
    mock_record.assert_called_once()
    call = mock_record.call_args.kwargs
    assert call["tool_name"] == "tool_async_demo"
    assert call["success"] is True
    assert call["organization_id"] == "org-1"
    assert call["query_snippet"] == "ports"


@pytest.mark.asyncio
async def test_invoke_tool_with_runtime_can_run_sync_tool_in_thread():
    runtime_context = build_tool_runtime_context(
        request_id="req-1",
        organization_id="org-1",
        source="agentic_loop",
    )

    with patch("app.engine.skills.skill_tool_bridge.record_tool_usage") as mock_record:
        result = await invoke_tool_with_runtime(
            _SyncTool(),
            {"query": "weather"},
            runtime_context_base=runtime_context,
            tool_call_id="tc-2",
            prefer_async=False,
            run_sync_in_thread=True,
        )

    assert result == "sync:weather"
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["success"] is True


@pytest.mark.asyncio
async def test_invoke_tool_with_runtime_records_failure():
    runtime_context = build_tool_runtime_context(
        request_id="req-1",
        organization_id="org-1",
        source="agentic_loop",
    )

    with patch("app.engine.skills.skill_tool_bridge.record_tool_usage") as mock_record:
        with pytest.raises(RuntimeError, match="boom:fail"):
            await invoke_tool_with_runtime(
                _FailingTool(),
                {"query": "fail"},
                runtime_context_base=runtime_context,
                tool_call_id="tc-3",
            )

    mock_record.assert_called_once()
    call = mock_record.call_args.kwargs
    assert call["tool_name"] == "tool_failing_demo"
    assert call["success"] is False
    assert "boom:fail" in call["error_message"]
