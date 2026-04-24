"""Unit tests for WiiiRunner lifecycle hooks (P1)."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.multi_agent.hooks import (
    AgentHooks,
    HookDispatcher,
    LoggingHooks,
    MetricsHooks,
    RunHooks,
)
from app.engine.multi_agent.state import AgentState


# =========================================================================
# RunHooks base class
# =========================================================================


class TestRunHooks:
    """RunHooks base class provides safe no-op defaults."""

    @pytest.mark.asyncio
    async def test_all_callbacks_are_noop(self):
        hooks = RunHooks()
        state = {"query": "test"}

        # None of these should raise
        await hooks.on_run_start(state)
        await hooks.on_run_end(state, 100.0)
        await hooks.on_step_start("guardian", state)
        await hooks.on_step_end("guardian", state, 50.0)
        await hooks.on_step_error("guardian", state, RuntimeError("boom"))
        await hooks.on_route("guardian", "supervisor", state)


# =========================================================================
# AgentHooks base class
# =========================================================================


class TestAgentHooks:
    @pytest.mark.asyncio
    async def test_all_callbacks_are_noop(self):
        hooks = AgentHooks()
        state = {"query": "test"}

        await hooks.on_agent_start("rag_agent", state)
        await hooks.on_agent_end("rag_agent", state, 30.0)


# =========================================================================
# HookDispatcher
# =========================================================================


class TestHookDispatcher:
    def test_empty_dispatcher_has_no_hooks(self):
        d = HookDispatcher()
        assert d.has_hooks is False

    def test_add_run_hooks_sets_flag(self):
        d = HookDispatcher()
        d.add_run_hooks(RunHooks())
        assert d.has_hooks is True

    def test_add_agent_hooks_sets_flag(self):
        d = HookDispatcher()
        d.add_agent_hooks("rag_agent", AgentHooks())
        assert d.has_hooks is True

    @pytest.mark.asyncio
    async def test_emit_run_start(self):
        d = HookDispatcher()
        mock = AsyncMock()
        hooks = RunHooks()
        hooks.on_run_start = mock
        d.add_run_hooks(hooks)

        state = {"query": "test"}
        await d.emit_run_start(state)

        mock.assert_awaited_once_with(state)

    @pytest.mark.asyncio
    async def test_emit_run_end(self):
        d = HookDispatcher()
        mock = AsyncMock()
        hooks = RunHooks()
        hooks.on_run_end = mock
        d.add_run_hooks(hooks)

        state = {"query": "test"}
        await d.emit_run_end(state, 150.0)

        mock.assert_awaited_once_with(state, 150.0)

    @pytest.mark.asyncio
    async def test_emit_step_start_calls_run_hooks_and_agent_hooks(self):
        d = HookDispatcher()
        run_mock = AsyncMock()
        agent_mock = AsyncMock()

        run_hooks = RunHooks()
        run_hooks.on_step_start = run_mock
        d.add_run_hooks(run_hooks)

        agent_hooks = AgentHooks()
        agent_hooks.on_agent_start = agent_mock
        d.add_agent_hooks("rag_agent", agent_hooks)

        state = {"query": "test"}
        await d.emit_step_start("rag_agent", state)

        run_mock.assert_awaited_once_with("rag_agent", state)
        agent_mock.assert_awaited_once_with("rag_agent", state)

    @pytest.mark.asyncio
    async def test_emit_step_end_calls_both_hook_types(self):
        d = HookDispatcher()
        run_mock = AsyncMock()
        agent_mock = AsyncMock()

        run_hooks = RunHooks()
        run_hooks.on_step_end = run_mock
        d.add_run_hooks(run_hooks)

        agent_hooks = AgentHooks()
        agent_hooks.on_agent_end = agent_mock
        d.add_agent_hooks("rag_agent", agent_hooks)

        state = {"query": "test"}
        await d.emit_step_end("rag_agent", state, 200.0)

        run_mock.assert_awaited_once_with("rag_agent", state, 200.0)
        agent_mock.assert_awaited_once_with("rag_agent", state, 200.0)

    @pytest.mark.asyncio
    async def test_emit_step_error(self):
        d = HookDispatcher()
        mock = AsyncMock()
        hooks = RunHooks()
        hooks.on_step_error = mock
        d.add_run_hooks(hooks)

        exc = RuntimeError("test error")
        await d.emit_step_error("rag_agent", {"query": "q"}, exc)

        mock.assert_awaited_once_with("rag_agent", {"query": "q"}, exc)

    @pytest.mark.asyncio
    async def test_emit_route(self):
        d = HookDispatcher()
        mock = AsyncMock()
        hooks = RunHooks()
        hooks.on_route = mock
        d.add_run_hooks(hooks)

        state = {"query": "test"}
        await d.emit_route("supervisor", "rag_agent", state)

        mock.assert_awaited_once_with("supervisor", "rag_agent", state)

    @pytest.mark.asyncio
    async def test_bad_hook_does_not_crash_pipeline(self):
        """A failing hook must not prevent other hooks or pipeline execution."""
        d = HookDispatcher()

        bad_hooks = RunHooks()
        bad_hooks.on_run_start = AsyncMock(side_effect=RuntimeError("hook broken"))
        d.add_run_hooks(bad_hooks)

        good_hooks = RunHooks()
        good_mock = AsyncMock()
        good_hooks.on_run_start = good_mock
        d.add_run_hooks(good_hooks)

        await d.emit_run_start({"query": "test"})
        good_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_agent_hooks(self):
        d = HookDispatcher()
        mock1 = AsyncMock()
        mock2 = AsyncMock()

        h1 = AgentHooks()
        h1.on_agent_start = mock1
        h2 = AgentHooks()
        h2.on_agent_start = mock2

        d.add_agent_hooks("rag_agent", h1)
        d.add_agent_hooks("rag_agent", h2)

        await d.emit_step_start("rag_agent", {"query": "test"})
        mock1.assert_awaited_once()
        mock2.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_agent_hooks_only_fire_for_matching_agent(self):
        d = HookDispatcher()
        rag_mock = AsyncMock()

        h = AgentHooks()
        h.on_agent_start = rag_mock
        d.add_agent_hooks("rag_agent", h)

        await d.emit_step_start("tutor_agent", {"query": "test"})
        rag_mock.assert_not_awaited()


# =========================================================================
# Built-in: LoggingHooks
# =========================================================================


class TestLoggingHooks:
    @pytest.mark.asyncio
    async def test_on_run_start_logs(self, caplog):
        hooks = LoggingHooks()
        with caplog.at_level(logging.INFO, logger="app.engine.multi_agent.hooks"):
            await hooks.on_run_start({"query": "COLREG", "user_id": "u1", "domain_id": "maritime"})
        assert any("Pipeline start" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_on_run_end_logs(self, caplog):
        hooks = LoggingHooks()
        with caplog.at_level(logging.INFO, logger="app.engine.multi_agent.hooks"):
            await hooks.on_run_end({"current_agent": "rag_agent", "_execution_tier": "moderate"}, 123.4)
        assert any("Pipeline end" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_on_step_end_logs_tier(self, caplog):
        hooks = LoggingHooks()
        with caplog.at_level(logging.INFO, logger="app.engine.multi_agent.hooks"):
            await hooks.on_step_end("rag_agent", {"_execution_tier": "moderate"}, 50.0)
        assert any("rag_agent done" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_on_step_error_logs_warning(self, caplog):
        hooks = LoggingHooks()
        with caplog.at_level(logging.WARNING, logger="app.engine.multi_agent.hooks"):
            await hooks.on_step_error(
                "rag_agent", {"query": "q"}, RuntimeError("DB down")
            )
        assert any("rag_agent error" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_on_route_logs(self, caplog):
        hooks = LoggingHooks()
        with caplog.at_level(logging.INFO, logger="app.engine.multi_agent.hooks"):
            await hooks.on_route("supervisor", "rag_agent", {"query": "q"})
        assert any("Route" in r.message for r in caplog.records)


# =========================================================================
# Built-in: MetricsHooks
# =========================================================================


class TestMetricsHooks:
    def setup_method(self):
        from app.engine.multi_agent.subagents.metrics import SubagentMetrics

        SubagentMetrics.reset()

    @pytest.mark.asyncio
    async def test_on_step_end_records_metrics(self):
        from app.engine.multi_agent.subagents.metrics import SubagentMetrics

        hooks = MetricsHooks()
        state = {"query": "test", "crag_confidence": 0.9}
        await hooks.on_step_end("rag_agent", state, 150.0)

        m = SubagentMetrics.get_instance()
        s = m.summary("rag_agent")
        assert s is not None
        assert s["invocations"] == 1
        assert s["avg_duration_ms"] == 150.0
        assert s["avg_confidence"] == pytest.approx(0.9, rel=0.01)

    @pytest.mark.asyncio
    async def test_on_step_error_records_error(self):
        from app.engine.multi_agent.subagents.metrics import SubagentMetrics

        hooks = MetricsHooks()
        await hooks.on_step_error("tutor_agent", {"query": "q"}, RuntimeError("fail"))

        m = SubagentMetrics.get_instance()
        s = m.summary("tutor_agent")
        assert s is not None
        assert s["error_rate"] == 1.0


# =========================================================================
# WiiiRunner integration with hooks
# =========================================================================


class TestWiiiRunnerHooks:
    """Test that WiiiRunner correctly invokes hooks during execution."""

    def setup_method(self):
        from app.engine.multi_agent.runner import _RUNNER, WiiiRunner
        # Reset the module-level singleton for test isolation
        import app.engine.multi_agent.runner as runner_mod
        runner_mod._RUNNER = None

    @pytest.mark.asyncio
    async def test_hooks_fire_on_run(self):
        from app.engine.multi_agent.runner import WiiiRunner
        from app.engine.multi_agent.hooks import HookDispatcher

        runner = WiiiRunner()

        # Register mock nodes
        async def mock_guardian(state):
            return state
        async def mock_supervisor(state):
            state["next_agent"] = "rag_agent"
            return state
        async def mock_rag(state):
            state["rag_output"] = "answer"
            state["final_response"] = "answer long enough to pass retry guard"
            return state
        async def mock_synthesizer(state):
            state["final_response"] = state.get("rag_output", "")
            return state

        runner.register_node("guardian", mock_guardian)
        runner.register_node("supervisor", mock_supervisor)
        runner.register_node("rag_agent", mock_rag)
        runner.register_node("synthesizer", mock_synthesizer)

        # Attach hooks
        dispatcher = HookDispatcher()
        start_mock = AsyncMock()
        end_mock = AsyncMock()
        step_start_mock = AsyncMock()
        step_end_mock = AsyncMock()
        route_mock = AsyncMock()

        hooks = RunHooks()
        hooks.on_run_start = start_mock
        hooks.on_run_end = end_mock
        hooks.on_step_start = step_start_mock
        hooks.on_step_end = step_end_mock
        hooks.on_route = route_mock
        dispatcher.add_run_hooks(hooks)
        runner.set_hooks(dispatcher)

        # Patch guardian_route and route_decision
        with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
             patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
            result = await runner.run({"query": "test"})

        # Verify hooks fired
        start_mock.assert_awaited_once()
        end_mock.assert_awaited_once()
        assert step_start_mock.await_count == 4  # guardian, supervisor, rag, synthesizer
        assert step_end_mock.await_count == 4
        assert route_mock.await_count >= 2  # guardian→supervisor, supervisor→rag

    @pytest.mark.asyncio
    async def test_step_error_hook_on_agent_failure(self):
        from app.engine.multi_agent.runner import WiiiRunner
        from app.engine.multi_agent.hooks import HookDispatcher

        runner = WiiiRunner()

        async def mock_guardian(state):
            return state
        async def mock_supervisor(state):
            state["next_agent"] = "rag_agent"
            return state
        async def mock_rag(state):
            raise RuntimeError("RAG failed")
        async def mock_synthesizer(state):
            state["final_response"] = "fallback"
            return state

        runner.register_node("guardian", mock_guardian)
        runner.register_node("supervisor", mock_supervisor)
        runner.register_node("rag_agent", mock_rag)
        runner.register_node("synthesizer", mock_synthesizer)

        dispatcher = HookDispatcher()
        error_mock = AsyncMock()
        hooks = RunHooks()
        hooks.on_step_error = error_mock
        dispatcher.add_run_hooks(hooks)
        runner.set_hooks(dispatcher)

        with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
             patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
            result = await runner.run({"query": "test"})

        error_mock.assert_awaited_once()
        call_args = error_mock.call_args
        assert call_args[0][0] == "rag_agent"
        assert isinstance(call_args[0][2], RuntimeError)

    @pytest.mark.asyncio
    async def test_no_hooks_no_crash(self):
        """Runner without hooks should work fine."""
        from app.engine.multi_agent.runner import WiiiRunner

        runner = WiiiRunner()

        async def mock_guardian(state):
            return state
        async def mock_synthesizer(state):
            state["final_response"] = "ok"
            return state

        runner.register_node("guardian", mock_guardian)
        runner.register_node("synthesizer", mock_synthesizer)

        with patch("app.engine.multi_agent.graph.guardian_route", return_value="synthesizer"):
            result = await runner.run({"query": "blocked"})

        assert result["final_response"] == "ok"

    @pytest.mark.asyncio
    async def test_agent_hooks_fire_for_specific_agent(self):
        from app.engine.multi_agent.runner import WiiiRunner
        from app.engine.multi_agent.hooks import HookDispatcher

        runner = WiiiRunner()

        async def mock_guardian(state):
            return state
        async def mock_supervisor(state):
            state["next_agent"] = "rag_agent"
            return state
        async def mock_rag(state):
            return state
        async def mock_tutor(state):
            return state
        async def mock_synthesizer(state):
            state["final_response"] = "ok"
            return state

        runner.register_node("guardian", mock_guardian)
        runner.register_node("supervisor", mock_supervisor)
        runner.register_node("rag_agent", mock_rag)
        runner.register_node("tutor_agent", mock_tutor)
        runner.register_node("synthesizer", mock_synthesizer)

        dispatcher = HookDispatcher()
        rag_start_mock = AsyncMock()
        rag_end_mock = AsyncMock()

        rag_hooks = AgentHooks()
        rag_hooks.on_agent_start = rag_start_mock
        rag_hooks.on_agent_end = rag_end_mock
        dispatcher.add_agent_hooks("rag_agent", rag_hooks)
        runner.set_hooks(dispatcher)

        with patch("app.engine.multi_agent.graph.guardian_route", return_value="supervisor"), \
             patch("app.engine.multi_agent.graph_support.route_decision", return_value="rag_agent"):
            await runner.run({"query": "test"})

        rag_start_mock.assert_awaited_once()
        # Verify agent name is "rag_agent" in first positional arg
        assert rag_start_mock.call_args[0][0] == "rag_agent"
        rag_end_mock.assert_awaited_once()


# Need logging import for LoggingHooks tests
import logging
