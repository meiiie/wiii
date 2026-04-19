"""WiiiRunner — Custom orchestrator replacing LangGraph StateGraph.

Inspired by OpenAI Agents SDK Runner pattern:
- Simple async execution loop (no framework dependency)
- Guardian → Supervisor → {Agent} → Synthesize
- Streaming via event bus (already custom, not LangGraph streaming)
- Agent-as-Tool support built-in
- Lifecycle hooks (P1): RunHooks + AgentHooks for observability

Design principles:
- All node functions are UNCHANGED (they take AgentState, return AgentState)
- No LangGraph imports — pure Python async orchestration
- Streaming format matches LangGraph's stream_mode="updates" for drop-in compat
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from app.core.config import settings
from app.engine.multi_agent.stream_events import make_graph_event, make_graph_done
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.guardrails import run_input_guardrails, run_output_guardrails

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (replace magic strings)
# ---------------------------------------------------------------------------

_NODE_GUARDIAN = "guardian"
_NODE_SUPERVISOR = "supervisor"
_NODE_SYNTHESIZER = "synthesizer"
_NODE_PARALLEL_DISPATCH = "parallel_dispatch"
_NODE_AGGREGATOR = "aggregator"

_MAX_DISPATCH_ITERATIONS = 2  # Safety limit for aggregator→supervisor loop


class WiiiRunner:
    """Custom orchestrator replacing LangGraph StateGraph.

    Instead of building a StateGraph → compile → invoke/astream,
    we directly call node functions in sequence:

        guardian → supervisor → {chosen_agent} → synthesizer

    This gives us:
    - Zero framework dependency (no langgraph)
    - Full control over execution flow
    - Simpler debugging (just function calls)
    - Same streaming behavior via event bus
    - Lifecycle hooks for observability, metrics, tracing
    """

    def __init__(self):
        self._nodes: dict[str, Callable] = {}
        self._feature_nodes: dict[str, tuple[Callable, Callable]] = {}
        self._hooks: Optional[HookDispatcher] = None

    def register_node(self, name: str, fn: Callable) -> None:
        """Register a node function: async (AgentState) -> AgentState."""
        self._nodes[name] = fn

    def register_feature_node(
        self,
        name: str,
        fn: Callable,
        gate_fn: Callable[[], bool],
    ) -> None:
        """Register a feature-gated node (only active when gate returns True)."""
        self._feature_nodes[name] = (fn, gate_fn)

    def set_hooks(self, dispatcher: Optional[HookDispatcher]) -> None:
        """Attach a HookDispatcher for lifecycle callbacks."""
        self._hooks = dispatcher

    def _get_node(self, name: str) -> Optional[Callable]:
        """Get a node function by name, checking feature gates."""
        if name in self._nodes:
            return self._nodes[name]
        if name in self._feature_nodes:
            fn, gate_fn = self._feature_nodes[name]
            if gate_fn():
                return fn
        return None

    # ------------------------------------------------------------------
    # Hook helpers
    # ------------------------------------------------------------------

    @property
    def hooks(self) -> Optional[HookDispatcher]:
        return self._hooks

    async def _emit_run_start(self, state: AgentState) -> None:
        if self._hooks:
            await self._hooks.emit_run_start(state)

    async def _emit_run_end(self, state: AgentState, duration_ms: float) -> None:
        if self._hooks:
            await self._hooks.emit_run_end(state, duration_ms)

    async def _emit_step_start(self, step_name: str, state: AgentState) -> None:
        if self._hooks:
            await self._hooks.emit_step_start(step_name, state)

    async def _emit_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None:
        if self._hooks:
            await self._hooks.emit_step_end(step_name, state, duration_ms)

    async def _emit_step_error(self, step_name: str, state: AgentState, error: Exception) -> None:
        if self._hooks:
            await self._hooks.emit_step_error(step_name, state, error)

    async def _emit_route(self, from_step: str, to_step: str, state: AgentState) -> None:
        if self._hooks:
            await self._hooks.emit_route(from_step, to_step, state)

    # ------------------------------------------------------------------
    # Sync execution (replaces graph.ainvoke)
    # ------------------------------------------------------------------

    async def run(self, state: AgentState) -> AgentState:
        """Execute: Guardian → Supervisor → Agent → Synthesize.

        This replaces ``graph.ainvoke(initial_state, config=invoke_config)``.
        """
        t_start = time.perf_counter()
        await self._emit_run_start(state)

        # 1. Guardian
        state = await self._run_step(_NODE_GUARDIAN, state)

        # 1b. Extended input guardrails (P5)

        guardian_passed = state.get("guardian_passed", True)
        passed, reason = await run_input_guardrails(state, guardian_passed=guardian_passed)
        if not passed:
            state["guardian_passed"] = False
            state["final_response"] = reason or "Nội dung không phù hợp."

        # 2. Guardian route
        from app.engine.multi_agent.graph import guardian_route

        route = guardian_route(state)
        await self._emit_route(_NODE_GUARDIAN, route, state)

        if route == _NODE_SYNTHESIZER:
            state["current_agent"] = _NODE_SYNTHESIZER
            state = await self._run_step(_NODE_SYNTHESIZER, state)
            # Output guardrails (P5)
            await run_output_guardrails(state)
            elapsed = (time.perf_counter() - t_start) * 1000
            await self._emit_run_end(state, elapsed)
            return state

        # 3. Supervisor
        state = await self._run_step(_NODE_SUPERVISOR, state)

        # 4. Supervisor routing decision
        from app.engine.multi_agent.graph_support import route_decision

        agent_name = route_decision(state)
        state["current_agent"] = agent_name
        await self._emit_route(_NODE_SUPERVISOR, agent_name, state)

        # Handle parallel dispatch → aggregator → (synthesizer | supervisor loop)
        if agent_name == _NODE_PARALLEL_DISPATCH:
            state = await self._run_parallel_dispatch(state)
            elapsed = (time.perf_counter() - t_start) * 1000
            await self._emit_run_end(state, elapsed)
            return state

        # 5. Execute chosen agent
        node_fn = self._get_node(agent_name)
        if node_fn:
            state = await self._run_step(agent_name, state)

        # 6. Synthesize
        state = await self._run_step(_NODE_SYNTHESIZER, state)

        # 7. Output guardrails (P5)
        await run_output_guardrails(state)

        elapsed = (time.perf_counter() - t_start) * 1000
        await self._emit_run_end(state, elapsed)
        return state

    # ------------------------------------------------------------------
    # Streaming execution (replaces graph.astream)
    # ------------------------------------------------------------------

    async def run_streaming(
        self,
        state: AgentState,
        *,
        merged_queue: Optional[asyncio.Queue] = None,
    ) -> AgentState:
        """Execute with streaming — push node updates to merged_queue.

        This replaces ``graph.astream(initial_state, config, stream_mode="updates")``.
        Each completed node produces an update ``{node_name: state_snapshot}``
        pushed to the merged_queue, matching LangGraph's "updates" format that
        ``graph_stream_merge_runtime.py`` expects.
        """
        t_start = time.perf_counter()
        await self._emit_run_start(state)

        # 1. Guardian
        state = await self._run_step(_NODE_GUARDIAN, state)
        if merged_queue:
            await merged_queue.put(make_graph_event(_NODE_GUARDIAN, dict(state)))

        # 2. Guardian route
        from app.engine.multi_agent.graph import guardian_route

        route = guardian_route(state)
        await self._emit_route(_NODE_GUARDIAN, route, state)

        if route == _NODE_SYNTHESIZER:
            state["current_agent"] = _NODE_SYNTHESIZER
            state = await self._run_step(_NODE_SYNTHESIZER, state)
            if merged_queue:
                await merged_queue.put(make_graph_event(_NODE_SYNTHESIZER, dict(state)))
            elapsed = (time.perf_counter() - t_start) * 1000
            await self._emit_run_end(state, elapsed)
            return state

        # 3. Supervisor
        state = await self._run_step(_NODE_SUPERVISOR, state)
        if merged_queue:
            await merged_queue.put(make_graph_event(_NODE_SUPERVISOR, dict(state)))

        # 4. Supervisor routing
        from app.engine.multi_agent.graph_support import route_decision

        agent_name = route_decision(state)
        state["current_agent"] = agent_name
        await self._emit_route(_NODE_SUPERVISOR, agent_name, state)

        # Handle parallel dispatch
        if agent_name == _NODE_PARALLEL_DISPATCH:
            state = await self._run_parallel_dispatch(state, merged_queue=merged_queue)
            elapsed = (time.perf_counter() - t_start) * 1000
            await self._emit_run_end(state, elapsed)
            return state

        # 5. Execute chosen agent
        node_fn = self._get_node(agent_name)
        if node_fn:
            state = await self._run_step(agent_name, state)
            if merged_queue:
                await merged_queue.put(make_graph_event(agent_name, dict(state)))

        # 6. Synthesize
        state = await self._run_step(_NODE_SYNTHESIZER, state)
        if merged_queue:
            await merged_queue.put(make_graph_event(_NODE_SYNTHESIZER, dict(state)))

        elapsed = (time.perf_counter() - t_start) * 1000
        await self._emit_run_end(state, elapsed)
        return state

    # ------------------------------------------------------------------
    # Parallel dispatch (replaces LangGraph conditional edges + aggregator)
    # ------------------------------------------------------------------

    async def _run_parallel_dispatch(
        self,
        state: AgentState,
        *,
        merged_queue: Optional[asyncio.Queue] = None,
    ) -> AgentState:
        """Handle parallel_dispatch → aggregator → (synthesizer | supervisor loop).

        Protected by _MAX_DISPATCH_ITERATIONS to prevent infinite loops
        if aggregator keeps routing back to supervisor.
        """
        # Run parallel_dispatch
        state = await self._run_step(_NODE_PARALLEL_DISPATCH, state)
        if merged_queue:
            await merged_queue.put(make_graph_event(_NODE_PARALLEL_DISPATCH, dict(state)))

        # Run aggregator
        state = await self._run_step(_NODE_AGGREGATOR, state)
        if merged_queue:
            await merged_queue.put(make_graph_event(_NODE_AGGREGATOR, dict(state)))

        # Aggregator route: synthesizer or back to supervisor (with loop limit)
        for _iteration in range(_MAX_DISPATCH_ITERATIONS):
            next_route = self._resolve_aggregator_route(state)
            await self._emit_route(_NODE_AGGREGATOR, next_route, state)

            if next_route != _NODE_SUPERVISOR:
                break

            # Loop back: supervisor → agent → (continue or break)
            state = await self._run_step(_NODE_SUPERVISOR, state)
            if merged_queue:
                await merged_queue.put(make_graph_event(_NODE_SUPERVISOR, dict(state)))

            from app.engine.multi_agent.graph_support import route_decision

            agent_name = route_decision(state)
            state["current_agent"] = agent_name
            await self._emit_route(_NODE_SUPERVISOR, agent_name, state)

            node_fn = self._get_node(agent_name)
            if node_fn:
                state = await self._run_step(agent_name, state)
                if merged_queue:
                    await merged_queue.put(make_graph_event(agent_name, dict(state)))

            # After agent execution, run aggregator again to decide next step
            state = await self._run_step(_NODE_AGGREGATOR, state)
            if merged_queue:
                await merged_queue.put(make_graph_event(_NODE_AGGREGATOR, dict(state)))

        return await self._run_step(_NODE_SYNTHESIZER, state)

    @staticmethod
    def _resolve_aggregator_route(state: AgentState) -> str:
        """Resolve aggregator routing decision with safe fallback."""
        try:
            from app.engine.multi_agent.subagents.aggregator import (
                aggregator_route as aggregator_route_impl,
            )
            return aggregator_route_impl(state)
        except Exception:
            return _NODE_SYNTHESIZER

    @staticmethod
    def _inject_tier_info(node_name: str, state: AgentState) -> None:
        """Inject tier info from AgentConfigRegistry into state for observability.

        Only injects for agent nodes (not infrastructure nodes like guardian/synthesizer).
        """
        if node_name in (_NODE_GUARDIAN, _NODE_SYNTHESIZER, _NODE_PARALLEL_DISPATCH, _NODE_AGGREGATOR):
            return
        try:
            from app.engine.multi_agent.agent_config import AgentConfigRegistry

            config = AgentConfigRegistry.get_config(node_name)
            state["_execution_tier"] = config.tier
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Single step execution (with hooks)
    # ------------------------------------------------------------------

    async def _run_step(self, name: str, state: AgentState) -> AgentState:
        """Run a single node function with error handling and lifecycle hooks.

        Critical nodes (guardian, supervisor, synthesizer) re-raise on failure.
        Agent nodes continue with error state, allowing graceful degradation.
        """
        node_fn = self._get_node(name)
        if node_fn is None:
            logger.warning("[RUNNER] Node %s not found, skipping", name)
            return state

        # Inject tier info for observability (P3)
        self._inject_tier_info(name, state)

        t_start = time.perf_counter()
        await self._emit_step_start(name, state)

        try:
            result = await node_fn(state)
            duration_ms = (time.perf_counter() - t_start) * 1000
            await self._emit_step_end(name, result, duration_ms)
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            await self._emit_step_error(name, state, exc)
            logger.error("[RUNNER] Node %s failed (%.1fms): %s", name, duration_ms, exc)
            # Critical infrastructure nodes re-raise; agent nodes degrade gracefully
            if name in (_NODE_GUARDIAN, _NODE_SUPERVISOR, _NODE_SYNTHESIZER):
                raise
            state["_runner_error"] = str(exc)
            state["_runner_error_node"] = name
            return state


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_RUNNER: Optional[WiiiRunner] = None


def get_wiii_runner() -> WiiiRunner:
    """Get or create the WiiiRunner singleton.

    The runner is configured with all the same node functions that
    the LangGraph graph uses. Node functions are imported lazily
    to avoid circular imports.
    """
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER

    from app.engine.multi_agent.graph import (
        guardian_node,
        supervisor_node,
        rag_node,
        tutor_node,
        memory_node,
        direct_response_node,
        code_studio_node,
        synthesizer_node,
        parallel_dispatch_node,
    )

    runner = WiiiRunner()

    # Core nodes (always active)
    runner.register_node(_NODE_GUARDIAN, guardian_node)
    runner.register_node(_NODE_SUPERVISOR, supervisor_node)
    runner.register_node("rag_agent", rag_node)
    runner.register_node("tutor_agent", tutor_node)
    runner.register_node("memory_agent", memory_node)
    runner.register_node("direct", direct_response_node)
    runner.register_node("code_studio_agent", code_studio_node)
    runner.register_node(_NODE_SYNTHESIZER, synthesizer_node)

    # Feature-gated nodes
    try:
        from app.engine.multi_agent.graph import (
            colleague_agent_node,
            product_search_node,
        )

        runner.register_feature_node(
            "colleague_agent",
            colleague_agent_node,
            lambda: bool(
                settings.enable_cross_soul_query and settings.enable_soul_bridge
            ),
        )

        runner.register_feature_node(
            "product_search_agent",
            product_search_node,
            lambda: bool(settings.enable_product_search),
        )

        runner.register_feature_node(
            _NODE_PARALLEL_DISPATCH,
            parallel_dispatch_node,
            lambda: bool(settings.enable_subagent_architecture),
        )
    except Exception as exc:
        logger.warning("[RUNNER] Feature nodes registration partial: %s", exc)

    # Aggregator (only for subagent architecture)
    try:
        from app.engine.multi_agent.subagents.aggregator import aggregator_node

        runner.register_feature_node(
            _NODE_AGGREGATOR,
            aggregator_node,
            lambda: bool(settings.enable_subagent_architecture),
        )
    except Exception as exc:
        logger.debug("[RUNNER] Aggregator node not available: %s", exc)

    # Lifecycle hooks (feature-gated)
    _attach_default_hooks(runner)

    _RUNNER = runner
    logger.info(
        "[RUNNER] WiiiRunner initialized with %d core + %d feature nodes",
        len(runner._nodes),
        len(runner._feature_nodes),
    )
    return runner


def _attach_default_hooks(runner: WiiiRunner) -> None:
    """Attach default hooks for observability and metrics.

    Feature-gated by ``enable_runner_hooks`` (default True).
    LoggingHooks (INFO): pipeline lifecycle visible in production logs.
    MetricsHooks: auto-collect duration/status per step via SubagentMetrics.
    """
    if not settings.enable_runner_hooks:
        return

    from app.engine.multi_agent.hooks import HookDispatcher, LoggingHooks, MetricsHooks

    dispatcher = HookDispatcher()
    dispatcher.add_run_hooks(LoggingHooks())  # INFO level — visible in production
    dispatcher.add_run_hooks(MetricsHooks())   # Auto metrics collection
    runner.set_hooks(dispatcher)


# Late import to avoid circular dependency
from app.engine.multi_agent.hooks import HookDispatcher  # noqa: E402
