"""
Sprint 163: Subagent Foundation — Unit Tests.

Tests cover:
- SubagentResult (base + subclasses): validation, is_valid, is_retriable
- SubagentConfig: validation, bounds, defaults
- SubagentRegistry: singleton, register, get, list, reset
- execute_subagent: timeout, retry, fallback
- execute_parallel_subagents: concurrency, error isolation
- Feature flag gating
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.multi_agent.subagents.result import (
    SubagentResult,
    SubagentStatus,
    SearchSubagentResult,
    RAGSubagentResult,
    TutorSubagentResult,
)
from app.engine.multi_agent.subagents.config import (
    SubagentConfig,
    FallbackBehavior,
)
from app.engine.multi_agent.subagents.registry import SubagentRegistry
from app.engine.multi_agent.subagents.executor import (
    execute_subagent,
    execute_parallel_subagents,
)


# =========================================================================
# SubagentResult
# =========================================================================


class TestSubagentResult:
    """Base SubagentResult validation."""

    def test_default_values(self):
        r = SubagentResult()
        assert r.status == SubagentStatus.SUCCESS
        assert r.confidence == 0.0
        assert r.output == ""
        assert r.data == {}
        assert r.sources == []
        assert r.tools_used == []
        assert r.thinking is None
        assert r.error_message is None
        assert r.duration_ms == 0

    def test_is_valid_success(self):
        r = SubagentResult(status=SubagentStatus.SUCCESS)
        assert r.is_valid is True

    def test_is_valid_partial(self):
        r = SubagentResult(status=SubagentStatus.PARTIAL)
        assert r.is_valid is True

    def test_is_valid_error(self):
        r = SubagentResult(status=SubagentStatus.ERROR)
        assert r.is_valid is False

    def test_is_valid_timeout(self):
        r = SubagentResult(status=SubagentStatus.TIMEOUT)
        assert r.is_valid is False

    def test_is_valid_skipped(self):
        r = SubagentResult(status=SubagentStatus.SKIPPED)
        assert r.is_valid is False

    def test_is_retriable_timeout(self):
        r = SubagentResult(status=SubagentStatus.TIMEOUT)
        assert r.is_retriable is True

    def test_is_retriable_error(self):
        r = SubagentResult(status=SubagentStatus.ERROR)
        assert r.is_retriable is False

    def test_confidence_bounds_low(self):
        with pytest.raises(Exception):
            SubagentResult(confidence=-0.1)

    def test_confidence_bounds_high(self):
        with pytest.raises(Exception):
            SubagentResult(confidence=1.1)

    def test_confidence_valid_range(self):
        r = SubagentResult(confidence=0.85)
        assert r.confidence == 0.85

    def test_duration_ms_non_negative(self):
        with pytest.raises(Exception):
            SubagentResult(duration_ms=-1)

    def test_with_data(self):
        r = SubagentResult(
            status=SubagentStatus.SUCCESS,
            confidence=0.9,
            output="test output",
            data={"key": "value"},
            sources=[{"url": "http://example.com"}],
            tools_used=[{"name": "web_search"}],
            thinking="I thought about it",
            duration_ms=500,
        )
        assert r.is_valid
        assert r.output == "test output"
        assert r.data["key"] == "value"
        assert len(r.sources) == 1
        assert len(r.tools_used) == 1


class TestSearchSubagentResult:
    """SearchSubagentResult fields."""

    def test_default_values(self):
        r = SearchSubagentResult()
        assert r.products == []
        assert r.platforms_searched == []
        assert r.total_results == 0
        assert r.excel_path is None

    def test_with_products(self):
        r = SearchSubagentResult(
            products=[{"title": "Product A", "price": 100}],
            platforms_searched=["shopee", "lazada"],
            total_results=1,
            excel_path="/tmp/report.xlsx",
        )
        assert len(r.products) == 1
        assert "shopee" in r.platforms_searched
        assert r.total_results == 1
        assert r.excel_path == "/tmp/report.xlsx"

    def test_inherits_is_valid(self):
        r = SearchSubagentResult(status=SubagentStatus.SUCCESS)
        assert r.is_valid is True

    def test_total_results_non_negative(self):
        with pytest.raises(Exception):
            SearchSubagentResult(total_results=-1)


class TestRAGSubagentResult:
    """RAGSubagentResult fields."""

    def test_default_values(self):
        r = RAGSubagentResult()
        assert r.documents == []
        assert r.retrieval_confidence == 0.0
        assert r.correction_rounds == 0

    def test_with_documents(self):
        r = RAGSubagentResult(
            documents=[{"content": "doc1"}],
            retrieval_confidence=0.8,
            correction_rounds=2,
        )
        assert len(r.documents) == 1
        assert r.retrieval_confidence == 0.8
        assert r.correction_rounds == 2

    def test_retrieval_confidence_bounds(self):
        with pytest.raises(Exception):
            RAGSubagentResult(retrieval_confidence=1.5)

    def test_correction_rounds_non_negative(self):
        with pytest.raises(Exception):
            RAGSubagentResult(correction_rounds=-1)


class TestTutorSubagentResult:
    """TutorSubagentResult fields."""

    def test_default_values(self):
        r = TutorSubagentResult()
        assert r.phase_completed == ""
        assert r.pedagogical_approach is None

    def test_with_phase(self):
        r = TutorSubagentResult(
            phase_completed="generation",
            pedagogical_approach="socratic",
        )
        assert r.phase_completed == "generation"
        assert r.pedagogical_approach == "socratic"


# =========================================================================
# SubagentConfig
# =========================================================================


class TestSubagentConfig:
    """SubagentConfig validation."""

    def test_defaults(self):
        c = SubagentConfig(name="test")
        assert c.timeout_seconds == 60
        assert c.max_retries == 1
        assert c.fallback_behavior == FallbackBehavior.RETURN_EMPTY
        assert c.max_iterations == 15
        assert c.llm_tier == "moderate"
        assert c.streaming_enabled is True
        assert c.parallel_enabled is False
        assert c.max_parallel_workers == 3

    def test_name_required(self):
        with pytest.raises(Exception):
            SubagentConfig()

    def test_name_min_length(self):
        with pytest.raises(Exception):
            SubagentConfig(name="")

    def test_timeout_bounds_low(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", timeout_seconds=5)

    def test_timeout_bounds_high(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", timeout_seconds=500)

    def test_max_retries_bounds(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", max_retries=5)

    def test_max_iterations_bounds(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", max_iterations=100)

    def test_llm_tier_pattern(self):
        for tier in ("deep", "moderate", "light"):
            c = SubagentConfig(name="test", llm_tier=tier)
            assert c.llm_tier == tier

    def test_llm_tier_invalid(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", llm_tier="ultra")

    def test_fallback_behaviors(self):
        for fb in FallbackBehavior:
            c = SubagentConfig(name="test", fallback_behavior=fb)
            assert c.fallback_behavior == fb

    def test_parallel_config(self):
        c = SubagentConfig(
            name="test",
            parallel_enabled=True,
            max_parallel_workers=7,
        )
        assert c.parallel_enabled is True
        assert c.max_parallel_workers == 7

    def test_max_parallel_workers_bounds(self):
        with pytest.raises(Exception):
            SubagentConfig(name="test", max_parallel_workers=20)

    def test_metadata_dict(self):
        c = SubagentConfig(name="test", metadata={"key": "value"})
        assert c.metadata["key"] == "value"


# =========================================================================
# SubagentRegistry
# =========================================================================


class TestSubagentRegistry:
    """SubagentRegistry singleton."""

    def setup_method(self):
        SubagentRegistry.reset()

    def test_singleton(self):
        r1 = SubagentRegistry.get_instance()
        r2 = SubagentRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = SubagentRegistry.get_instance()
        SubagentRegistry.reset()
        r2 = SubagentRegistry.get_instance()
        assert r1 is not r2

    def test_register_and_get(self):
        reg = SubagentRegistry.get_instance()
        builder = MagicMock()
        config = SubagentConfig(name="test_agent")
        reg.register("test_agent", builder=builder, config=config, description="A test agent")

        entry = reg.get("test_agent")
        assert entry is not None
        assert entry["builder"] is builder
        assert entry["config"] is config
        assert entry["description"] == "A test agent"

    def test_get_missing(self):
        reg = SubagentRegistry.get_instance()
        assert reg.get("nonexistent") is None

    def test_get_builder(self):
        reg = SubagentRegistry.get_instance()
        builder = MagicMock()
        config = SubagentConfig(name="x")
        reg.register("x", builder=builder, config=config)
        assert reg.get_builder("x") is builder
        assert reg.get_builder("missing") is None

    def test_get_config(self):
        reg = SubagentRegistry.get_instance()
        config = SubagentConfig(name="y", timeout_seconds=90)
        reg.register("y", builder=MagicMock(), config=config)
        retrieved = reg.get_config("y")
        assert retrieved is not None
        assert retrieved.timeout_seconds == 90
        assert reg.get_config("missing") is None

    def test_has(self):
        reg = SubagentRegistry.get_instance()
        reg.register("z", builder=MagicMock(), config=SubagentConfig(name="z"))
        assert reg.has("z") is True
        assert reg.has("nope") is False

    def test_unregister(self):
        reg = SubagentRegistry.get_instance()
        reg.register("tmp", builder=MagicMock(), config=SubagentConfig(name="tmp"))
        assert reg.has("tmp")
        assert reg.unregister("tmp") is True
        assert not reg.has("tmp")
        assert reg.unregister("tmp") is False

    def test_list_subagents(self):
        reg = SubagentRegistry.get_instance()
        reg.register("a", builder=MagicMock(), config=SubagentConfig(name="a"), description="Agent A")
        reg.register("b", builder=MagicMock(), config=SubagentConfig(name="b"), description="Agent B")
        listing = reg.list_subagents()
        assert len(listing) == 2
        names = {item["name"] for item in listing}
        assert names == {"a", "b"}

    def test_count(self):
        reg = SubagentRegistry.get_instance()
        assert reg.count == 0
        reg.register("x", builder=MagicMock(), config=SubagentConfig(name="x"))
        assert reg.count == 1
        reg.register("y", builder=MagicMock(), config=SubagentConfig(name="y"))
        assert reg.count == 2

    def test_empty_after_reset(self):
        reg = SubagentRegistry.get_instance()
        reg.register("x", builder=MagicMock(), config=SubagentConfig(name="x"))
        SubagentRegistry.reset()
        reg2 = SubagentRegistry.get_instance()
        assert reg2.count == 0


# =========================================================================
# execute_subagent
# =========================================================================


class TestExecuteSubagent:
    """execute_subagent with timeout/retry/fallback."""

    @pytest.mark.asyncio
    async def test_success_returns_result(self):
        async def good_func(state):
            return SubagentResult(status=SubagentStatus.SUCCESS, output="done")

        config = SubagentConfig(name="test")
        result = await execute_subagent(good_func, config, {})
        assert result.status == SubagentStatus.SUCCESS
        assert result.output == "done"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_wraps_dict_result(self):
        async def dict_func(state):
            return {"key": "value"}

        config = SubagentConfig(name="test")
        result = await execute_subagent(dict_func, config, {})
        assert result.status == SubagentStatus.SUCCESS
        assert result.data["key"] == "value"

    @pytest.mark.asyncio
    async def test_wraps_string_result(self):
        async def str_func(state):
            return "hello"

        config = SubagentConfig(name="test")
        result = await execute_subagent(str_func, config, {})
        assert result.status == SubagentStatus.SUCCESS
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self):
        async def slow_func(state):
            await asyncio.sleep(10)
            return SubagentResult()

        config = SubagentConfig(name="slow", timeout_seconds=10, max_retries=0)
        # Use a very short timeout by patching
        config.timeout_seconds = 0.1  # type: ignore[assignment]
        result = await execute_subagent(slow_func, config, {})
        assert result.status == SubagentStatus.TIMEOUT
        assert "Timeout" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_error_returns_error_status(self):
        async def bad_func(state):
            raise ValueError("boom")

        config = SubagentConfig(name="bad", max_retries=0)
        result = await execute_subagent(bad_func, config, {})
        assert result.status == SubagentStatus.ERROR
        assert result.error_message == "Subagent processing error"

    @pytest.mark.asyncio
    async def test_retry_on_error(self):
        call_count = 0

        async def flaky_func(state):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("temporary")
            return SubagentResult(output="finally")

        config = SubagentConfig(name="flaky", max_retries=2)
        result = await execute_subagent(flaky_func, config, {})
        assert result.status == SubagentStatus.SUCCESS
        assert result.output == "finally"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        async def always_fail(state):
            raise RuntimeError("permanent")

        config = SubagentConfig(name="fail", max_retries=2)
        result = await execute_subagent(always_fail, config, {})
        assert result.status == SubagentStatus.ERROR
        assert result.error_message == "Subagent processing error"

    @pytest.mark.asyncio
    async def test_fallback_raise_error(self):
        async def bad_func(state):
            raise ValueError("boom")

        config = SubagentConfig(
            name="strict",
            max_retries=0,
            fallback_behavior=FallbackBehavior.RAISE_ERROR,
        )
        with pytest.raises(RuntimeError, match="strict"):
            await execute_subagent(bad_func, config, {})

    @pytest.mark.asyncio
    async def test_passes_kwargs(self):
        async def kw_func(state, extra=None):
            return SubagentResult(output=extra or "none")

        config = SubagentConfig(name="kw")
        result = await execute_subagent(kw_func, config, {}, extra="hello")
        assert result.output == "hello"


# =========================================================================
# execute_parallel_subagents
# =========================================================================


class TestExecuteParallelSubagents:
    """execute_parallel_subagents concurrency and error isolation."""

    @pytest.mark.asyncio
    async def test_parallel_success(self):
        async def good(state):
            return SubagentResult(output=state.get("id", ""))

        tasks = [
            (good, SubagentConfig(name=f"t{i}"), {"id": str(i)}, {})
            for i in range(3)
        ]
        results = await execute_parallel_subagents(tasks, max_concurrent=3)
        assert len(results) == 3
        assert all(r.status == SubagentStatus.SUCCESS for r in results)

    @pytest.mark.asyncio
    async def test_parallel_error_isolation(self):
        async def good(state):
            return SubagentResult(output="ok")

        async def bad(state):
            raise ValueError("fail")

        tasks = [
            (good, SubagentConfig(name="good", max_retries=0), {}, {}),
            (bad, SubagentConfig(name="bad", max_retries=0), {}, {}),
            (good, SubagentConfig(name="good2", max_retries=0), {}, {}),
        ]
        results = await execute_parallel_subagents(tasks, max_concurrent=5)
        assert len(results) == 3
        assert results[0].status == SubagentStatus.SUCCESS
        assert results[1].status == SubagentStatus.ERROR
        assert results[2].status == SubagentStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_parallel_concurrency_limit(self):
        active = 0
        max_active = 0

        async def tracked(state):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            return SubagentResult()

        tasks = [
            (tracked, SubagentConfig(name=f"t{i}"), {}, {})
            for i in range(10)
        ]
        results = await execute_parallel_subagents(tasks, max_concurrent=3)
        assert len(results) == 10
        assert max_active <= 3

    @pytest.mark.asyncio
    async def test_parallel_empty_tasks(self):
        results = await execute_parallel_subagents([], max_concurrent=5)
        assert results == []


# =========================================================================
# Feature Flag Integration
# =========================================================================


class TestFeatureFlag:
    """Feature flag gating for subagent architecture."""

    def test_config_default_disabled(self, monkeypatch):
        monkeypatch.delenv("ENABLE_SUBAGENT_ARCHITECTURE", raising=False)
        from app.core.config import Settings
        s = Settings(_env_file=None, google_api_key="test", api_key="test")
        assert s.enable_subagent_architecture is False
        assert s.subagent_default_timeout == 60
        assert s.subagent_max_parallel == 5

    def test_config_timeout_bounds(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(
                google_api_key="test",
                api_key="test",
                subagent_default_timeout=5,
            )

    def test_config_max_parallel_bounds(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(
                google_api_key="test",
                api_key="test",
                subagent_max_parallel=20,
            )


# =========================================================================
# SubagentStatus enum
# =========================================================================


class TestSubagentStatus:
    """SubagentStatus enum values."""

    def test_all_values(self):
        expected = {"success", "partial", "timeout", "error", "skipped"}
        actual = {s.value for s in SubagentStatus}
        assert actual == expected

    def test_string_comparison(self):
        assert SubagentStatus.SUCCESS == "success"
        assert SubagentStatus.TIMEOUT == "timeout"
