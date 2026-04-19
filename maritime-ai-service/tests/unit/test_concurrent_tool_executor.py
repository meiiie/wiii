"""Tests for concurrent tool executor (Phase 5)."""

import asyncio
import time

import pytest

from app.engine.multi_agent.concurrent_tool_executor import (
    ToolCallResult,
    _execute_concurrent,
    _execute_sequential,
    execute_tool_calls_concurrent,
    is_readonly_tool,
    is_state_modifying_tool,
)


class TestToolClassification:
    def test_readonly_tools(self):
        assert is_readonly_tool("tool_web_search") is True
        assert is_readonly_tool("tool_knowledge_search") is True
        assert is_readonly_tool("tool_search_news") is True
        assert is_readonly_tool("tool_search_legal") is True
        assert is_readonly_tool("tool_current_datetime") is True
        assert is_readonly_tool("tool_search_maritime") is True

    def test_state_modifying_tools(self):
        assert is_state_modifying_tool("tool_execute_python") is True
        assert is_state_modifying_tool("tool_generate_visual") is True
        assert is_state_modifying_tool("tool_create_visual_code") is True
        assert is_state_modifying_tool("handoff_to_agent") is True

    def test_unknown_tool_not_readonly(self):
        """Unknown tools should NOT be classified as read-only (conservative)."""
        assert is_readonly_tool("unknown_tool") is False

    def test_unknown_tool_not_state_modifying(self):
        assert is_state_modifying_tool("unknown_tool") is False

    def test_readonly_not_state_modifying(self):
        """Read-only tools should not be state-modifying."""
        assert is_state_modifying_tool("tool_web_search") is False
        assert is_state_modifying_tool("tool_current_datetime") is False


class TestSequentialExecution:
    @pytest.mark.asyncio
    async def test_sequential_order(self):
        """Results should be in the same order as input tool calls."""
        calls = [
            {"id": "1", "name": "tool_web_search", "args": {"q": "a"}},
            {"id": "2", "name": "tool_knowledge_search", "args": {"q": "b"}},
        ]
        call_order = []

        async def invoke(tc):
            call_order.append(tc["id"])
            return f"result_{tc['id']}"

        results = await _execute_sequential(calls, invoke)
        assert len(results) == 2
        assert results[0].tool_call_id == "1"
        assert results[0].result == "result_1"
        assert results[1].tool_call_id == "2"
        assert results[1].result == "result_2"
        assert call_order == ["1", "2"]

    @pytest.mark.asyncio
    async def test_sequential_error_handling(self):
        """Error in one tool should not cancel others."""
        calls = [
            {"id": "1", "name": "tool_a", "args": {}},
            {"id": "2", "name": "tool_b", "args": {}},
        ]
        call_count = 0

        async def invoke(tc):
            nonlocal call_count
            call_count += 1
            if tc["id"] == "1":
                raise ValueError("test error")
            return "ok"

        results = await _execute_sequential(calls, invoke)
        assert results[0].error is not None
        assert results[1].result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_sequential_empty(self):
        results = await _execute_sequential([], lambda tc: tc)
        assert results == []


class TestConcurrentExecution:
    @pytest.mark.asyncio
    async def test_concurrent_order_preserved(self):
        """Results should be in original order even if execution overlaps."""
        calls = [
            {"id": "1", "name": "tool_web_search", "args": {}},
            {"id": "2", "name": "tool_knowledge_search", "args": {}},
            {"id": "3", "name": "tool_current_datetime", "args": {}},
        ]

        async def invoke(tc):
            await asyncio.sleep(0.01)
            return f"result_{tc['id']}"

        results = await _execute_concurrent(calls, invoke)
        assert len(results) == 3
        assert results[0].tool_call_id == "1"
        assert results[1].tool_call_id == "2"
        assert results[2].tool_call_id == "3"

    @pytest.mark.asyncio
    async def test_concurrent_faster_than_sequential(self):
        """Concurrent execution should be faster for multiple tools."""
        calls = [{"id": str(i), "name": f"tool_{i}", "args": {}} for i in range(5)]

        async def slow_invoke(tc):
            await asyncio.sleep(0.05)
            return "ok"

        start = time.perf_counter()
        await _execute_concurrent(calls, slow_invoke, max_concurrent=10)
        concurrent_time = time.perf_counter() - start

        start = time.perf_counter()
        await _execute_sequential(calls, slow_invoke)
        sequential_time = time.perf_counter() - start

        # Concurrent should be at least 2x faster
        assert concurrent_time < sequential_time * 0.6

    @pytest.mark.asyncio
    async def test_concurrent_error_isolation(self):
        """Error in one tool should not cancel others."""
        calls = [
            {"id": "1", "name": "tool_a", "args": {}},
            {"id": "2", "name": "tool_b", "args": {}},
        ]

        async def invoke(tc):
            if tc["id"] == "1":
                raise RuntimeError("boom")
            return "ok"

        results = await _execute_concurrent(calls, invoke)
        assert results[0].error is not None
        assert results[1].result == "ok"


class TestFeatureGate:
    @pytest.mark.asyncio
    async def test_feature_disabled_uses_sequential(self):
        """When enable_concurrent_tool_execution=False, should use sequential."""
        import unittest.mock

        calls = [
            {"id": "1", "name": "tool_web_search", "args": {}},
            {"id": "2", "name": "tool_generate_visual", "args": {}},
        ]

        async def invoke(tc):
            return f"result_{tc['id']}"

        with unittest.mock.patch(
            "app.engine.multi_agent.concurrent_tool_executor.settings"
        ) as mock_settings:
            mock_settings.enable_concurrent_tool_execution = False
            results = await execute_tool_calls_concurrent(calls, invoke)
            assert len(results) == 2
            assert results[0].result == "result_1"
            assert results[1].result == "result_2"
