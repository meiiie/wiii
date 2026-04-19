"""Unit tests for P5: Guardrail decorator extensibility."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.guardrails import (
    GuardrailContext,
    GuardrailEntry,
    GuardrailRegistry,
    GuardrailResult,
    guardrail,
    run_input_guardrails,
    run_output_guardrails,
)
from app.engine.multi_agent.state import AgentState


# =========================================================================
# GuardrailResult
# =========================================================================


class TestGuardrailResult:
    def test_pass_default(self):
        r = GuardrailResult()
        assert r.passed is True
        assert r.reason == ""

    def test_block(self):
        r = GuardrailResult(passed=False, reason="URL blocked")
        assert r.passed is False
        assert r.reason == "URL blocked"


# =========================================================================
# GuardrailContext
# =========================================================================


class TestGuardrailContext:
    def test_from_state(self):
        state = {"query": "test", "domain_id": "maritime", "user_id": "u1"}
        ctx = GuardrailContext(
            query=state.get("query", ""),
            state=state,
            domain_id=state.get("domain_id", ""),
            user_id=state.get("user_id", ""),
        )
        assert ctx.query == "test"
        assert ctx.domain_id == "maritime"


# =========================================================================
# GuardrailRegistry
# =========================================================================


class TestGuardrailRegistry:
    def setup_method(self):
        GuardrailRegistry.reset()

    def test_empty_registry(self):
        assert GuardrailRegistry.get_input_guardrails() == []
        assert GuardrailRegistry.get_output_guardrails() == []

    def test_register_input(self):
        entry = GuardrailEntry(
            name="test_input",
            phase="input",
            fn=AsyncMock(return_value=GuardrailResult()),
        )
        GuardrailRegistry.register(entry)
        assert len(GuardrailRegistry.get_input_guardrails()) == 1

    def test_register_output(self):
        entry = GuardrailEntry(
            name="test_output",
            phase="output",
            fn=AsyncMock(return_value=GuardrailResult()),
        )
        GuardrailRegistry.register(entry)
        assert len(GuardrailRegistry.get_output_guardrails()) == 1

    def test_priority_sorting(self):
        e1 = GuardrailEntry(name="low", phase="input", fn=AsyncMock(), priority=100)
        e2 = GuardrailEntry(name="high", phase="input", fn=AsyncMock(), priority=1)
        GuardrailRegistry.register(e1)
        GuardrailRegistry.register(e2)
        guardrails = GuardrailRegistry.get_input_guardrails()
        assert guardrails[0].name == "high"

    def test_list_names(self):
        e1 = GuardrailEntry(name="g1", phase="input", fn=AsyncMock())
        e2 = GuardrailEntry(name="g2", phase="output", fn=AsyncMock())
        GuardrailRegistry.register(e1)
        GuardrailRegistry.register(e2)
        names = GuardrailRegistry.list_names()
        assert "g1" in names["input"]
        assert "g2" in names["output"]

    def test_reset(self):
        GuardrailRegistry.register(
            GuardrailEntry(name="g", phase="input", fn=AsyncMock())
        )
        GuardrailRegistry.reset()
        assert GuardrailRegistry.get_input_guardrails() == []

    def test_unknown_phase(self):
        entry = GuardrailEntry(name="bad", phase="invalid", fn=AsyncMock())
        GuardrailRegistry.register(entry)
        assert GuardrailRegistry.get_input_guardrails() == []
        assert GuardrailRegistry.get_output_guardrails() == []


# =========================================================================
# @guardrail decorator
# =========================================================================


class TestGuardrailDecorator:
    def setup_method(self):
        GuardrailRegistry.reset()

    @pytest.mark.asyncio
    async def test_decorator_registers_input(self):
        @guardrail(phase="input", name="test_guard", description="Test guardrail")
        async def my_guard(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=True)

        names = GuardrailRegistry.list_names()
        assert "test_guard" in names["input"]

    @pytest.mark.asyncio
    async def test_decorator_registers_output(self):
        @guardrail(phase="output", name="test_output_guard")
        async def my_output_guard(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=True)

        names = GuardrailRegistry.list_names()
        assert "test_output_guard" in names["output"]

    @pytest.mark.asyncio
    async def test_decorator_preserves_function(self):
        @guardrail(phase="input", name="preserved")
        async def my_guard(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=True)

        ctx = GuardrailContext(query="test")
        result = await my_guard(ctx)
        assert result.passed is True


# =========================================================================
# run_input_guardrails
# =========================================================================


class TestRunInputGuardrails:
    def setup_method(self):
        GuardrailRegistry.reset()

    @pytest.mark.asyncio
    async def test_no_guardrails_passes(self):
        state = {"query": "hello"}
        passed, reason = await run_input_guardrails(state)
        assert passed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_passing_guardrail(self):
        @guardrail(phase="input", name="pass_all")
        async def pass_all(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=True)

        state = {"query": "COLREG là gì?"}
        passed, reason = await run_input_guardrails(state)
        assert passed is True

    @pytest.mark.asyncio
    async def test_blocking_guardrail(self):
        @guardrail(phase="input", name="block_urls", run_parallel=False)
        async def block_urls(ctx: GuardrailContext) -> GuardrailResult:
            if "http://" in ctx.query or "https://" in ctx.query:
                return GuardrailResult(passed=False, reason="Chỉ chứa URL")
            return GuardrailResult(passed=True)

        state = {"query": "https://example.com"}
        passed, reason = await run_input_guardrails(state)
        assert passed is False
        assert reason == "Chỉ chứa URL"

    @pytest.mark.asyncio
    async def test_parallel_guardrail_blocks(self):
        @guardrail(phase="input", name="parallel_block", run_parallel=True)
        async def parallel_block(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=False, reason="Blocked in parallel")

        state = {"query": "test"}
        passed, reason = await run_input_guardrails(state)
        assert passed is False
        assert reason == "Blocked in parallel"

    @pytest.mark.asyncio
    async def test_erroring_guardrail_allows(self):
        """A guardrail that raises an error should allow the request through."""

        @guardrail(phase="input", name="error_guard", run_parallel=False)
        async def error_guard(ctx: GuardrailContext) -> GuardrailResult:
            raise RuntimeError("Guard crashed")

        state = {"query": "test"}
        passed, reason = await run_input_guardrails(state)
        assert passed is True  # Fail-open on error

    @pytest.mark.asyncio
    async def test_sequential_runs_before_parallel(self):
        """Sequential guardrails should block before parallel ones run."""

        @guardrail(phase="input", name="seq_block", run_parallel=False, priority=1)
        async def seq_block(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=False, reason="Sequential block")

        @guardrail(phase="input", name="par_block", run_parallel=True, priority=2)
        async def par_block(ctx: GuardrailContext) -> GuardrailResult:
            return GuardrailResult(passed=False, reason="Should not reach")

        state = {"query": "test"}
        passed, reason = await run_input_guardrails(state)
        assert reason == "Sequential block"


# =========================================================================
# run_output_guardrails
# =========================================================================


class TestRunOutputGuardrails:
    def setup_method(self):
        GuardrailRegistry.reset()

    @pytest.mark.asyncio
    async def test_no_output_guardrails(self):
        state = {"query": "test", "final_response": "ok"}
        passed, reason = await run_output_guardrails(state)
        assert passed is True

    @pytest.mark.asyncio
    async def test_output_guardrail_passes(self):
        @guardrail(phase="output", name="length_check")
        async def length_check(ctx: GuardrailContext) -> GuardrailResult:
            if len(ctx.response) < 5:
                return GuardrailResult(passed=False, reason="Quá ngắn")
            return GuardrailResult(passed=True)

        state = {"query": "test", "final_response": "Đây là câu trả lời đầy đủ"}
        passed, reason = await run_output_guardrails(state)
        assert passed is True

    @pytest.mark.asyncio
    async def test_output_guardrail_blocks(self):
        @guardrail(phase="output", name="empty_check")
        async def empty_check(ctx: GuardrailContext) -> GuardrailResult:
            if not ctx.response.strip():
                return GuardrailResult(passed=False, reason="Câu trả lời trống")
            return GuardrailResult(passed=True)

        state = {"query": "test", "final_response": ""}
        passed, reason = await run_output_guardrails(state)
        assert passed is False
        assert reason == "Câu trả lời trống"
