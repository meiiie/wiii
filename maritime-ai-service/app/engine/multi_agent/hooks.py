"""WiiiRunner Lifecycle Hooks — inspired by OpenAI Agents SDK RunHooksBase.

Design principles:
- Protocol-based (structural typing) — no inheritance required
- All callbacks optional (default no-op via mixin)
- Async-first, sync auto-wrapped
- Built-in timing — hooks receive duration_ms, nodes don't need manual timing
- LoggingHooks uses INFO level for visibility in production

Hook hierarchy:
1. RunHooks — global lifecycle (set on WiiiRunner instance)
2. AgentHooks — per-agent lifecycle (registered by agent name)

Callback flow per step:
    on_step_start → node execution → on_step_end
                                ┌─→ on_step_error (if exception)

Full pipeline flow:
    on_run_start
      on_step_start(guardian) → on_step_end(guardian)
      on_route(guardian → supervisor|synthesizer)
      on_step_start(supervisor) → on_step_end(supervisor)
      on_route(supervisor → {agent_name})
      on_step_start({agent}) → on_step_end({agent})
      on_step_start(synthesizer) → on_step_end(synthesizer)
    on_run_end
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Optional, Protocol, Union, runtime_checkable

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync/async callback helpers
# ---------------------------------------------------------------------------

async def _invoke_callback(cb: Callable, *args: Any) -> None:
    """Invoke a callback, handling both sync and async callables."""
    if cb is None:
        return
    result = cb(*args)
    if inspect.isawaitable(result):
        await result


# ---------------------------------------------------------------------------
# RunHooks — global pipeline lifecycle
# ---------------------------------------------------------------------------

@runtime_checkable
class RunHooksProtocol(Protocol):
    """Protocol for global pipeline lifecycle hooks.

    Implement only the callbacks you need — defaults are no-ops.
    """

    async def on_run_start(self, state: AgentState) -> None: ...
    async def on_run_end(self, state: AgentState, duration_ms: float) -> None: ...
    async def on_step_start(self, step_name: str, state: AgentState) -> None: ...
    async def on_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None: ...
    async def on_step_error(self, step_name: str, state: AgentState, error: Exception) -> None: ...
    async def on_route(self, from_step: str, to_step: str, state: AgentState) -> None: ...


class RunHooks:
    """Base class for global pipeline lifecycle hooks.

    Provides no-op defaults so subclasses only override what they need.
    Inspired by OpenAI Agents SDK ``RunHooksBase[TContext]``.
    """

    async def on_run_start(self, state: AgentState) -> None:
        """Called before the entire pipeline starts."""

    async def on_run_end(self, state: AgentState, duration_ms: float) -> None:
        """Called after the entire pipeline completes."""

    async def on_step_start(self, step_name: str, state: AgentState) -> None:
        """Called before each step (node) executes."""

    async def on_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None:
        """Called after each step (node) completes successfully."""

    async def on_step_error(self, step_name: str, state: AgentState, error: Exception) -> None:
        """Called when a step (node) raises an exception."""

    async def on_route(self, from_step: str, to_step: str, state: AgentState) -> None:
        """Called when the pipeline routes between steps."""


# ---------------------------------------------------------------------------
# AgentHooks — per-agent lifecycle
# ---------------------------------------------------------------------------

@runtime_checkable
class AgentHooksProtocol(Protocol):
    """Protocol for per-agent lifecycle hooks."""

    async def on_agent_start(self, agent_name: str, state: AgentState) -> None: ...
    async def on_agent_end(self, agent_name: str, state: AgentState, duration_ms: float) -> None: ...


class AgentHooks:
    """Base class for per-agent lifecycle hooks.

    Inspired by OpenAI Agents SDK ``AgentHooksBase[TContext]``.
    """

    async def on_agent_start(self, agent_name: str, state: AgentState) -> None:
        """Called before this specific agent starts."""

    async def on_agent_end(self, agent_name: str, state: AgentState, duration_ms: float) -> None:
        """Called after this specific agent completes."""


# ---------------------------------------------------------------------------
# Built-in hook implementations
# ---------------------------------------------------------------------------

class LoggingHooks(RunHooks):
    """Built-in: structured logging for every pipeline step.

    Uses INFO level by default so pipeline lifecycle is visible
    in production logs without needing DEBUG level.
    """

    def __init__(self, level: int = logging.INFO):
        self._level = level

    async def on_run_start(self, state: AgentState) -> None:
        query = state.get("query", "")[:60]
        user = state.get("user_id", "")
        domain = state.get("domain_id", "")
        logger.log(self._level,
                   "[HOOKS] Pipeline start | query=%r user=%s domain=%s",
                   query, user, domain)

    async def on_run_end(self, state: AgentState, duration_ms: float) -> None:
        agent = state.get("current_agent", "unknown")
        tier = state.get("_execution_tier", "-")
        provider = state.get("_execution_provider", "-")
        logger.info(
            "[HOOKS] Pipeline end | agent=%s tier=%s provider=%s duration=%.1fms",
            agent, tier, provider, duration_ms)

    async def on_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None:
        tier = state.get("_execution_tier", "")
        tier_info = f" tier={tier}" if tier else ""
        logger.log(self._level,
                   "[HOOKS] Step %s done%s | %.1fms",
                   step_name, tier_info, duration_ms)

    async def on_step_error(self, step_name: str, state: AgentState, error: Exception) -> None:
        logger.warning("[HOOKS] Step %s error | %s: %s", step_name, type(error).__name__, error)

    async def on_route(self, from_step: str, to_step: str, state: AgentState) -> None:
        logger.log(self._level, "[HOOKS] Route | %s -> %s", from_step, to_step)


class MetricsHooks(RunHooks, AgentHooks):
    """Built-in: automatic metrics collection via SubagentMetrics.

    Records duration, status (success/error), and confidence per agent step.
    Always active — zero overhead when SubagentMetrics has no consumers.
    """

    async def on_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None:
        try:
            from app.engine.multi_agent.subagents.metrics import SubagentMetrics

            m = SubagentMetrics.get_instance()
            confidence = state.get("crag_confidence") or state.get("grader_score") or 0.0
            m.record(step_name, duration_ms=duration_ms, status="success", confidence=confidence)
        except Exception as exc:
            logger.debug("[HOOKS] MetricsHooks.on_step_end failed: %s", exc)

    async def on_step_error(self, step_name: str, state: AgentState, error: Exception) -> None:
        try:
            from app.engine.multi_agent.subagents.metrics import SubagentMetrics

            m = SubagentMetrics.get_instance()
            m.record(step_name, duration_ms=0, status="error")
        except Exception as exc:
            logger.debug("[HOOKS] MetricsHooks.on_step_error failed: %s", exc)


# ---------------------------------------------------------------------------
# Hook dispatcher — manages hook invocation for WiiiRunner
# ---------------------------------------------------------------------------

class HookDispatcher:
    """Dispatches lifecycle callbacks to registered hooks.

    Centralizes error handling so one bad hook doesn't crash the pipeline.
    """

    def __init__(self):
        self._run_hooks: list[RunHooks] = []
        self._agent_hooks: dict[str, list[AgentHooks]] = {}

    # -- Registration --

    def add_run_hooks(self, hooks: RunHooks) -> None:
        """Register global pipeline hooks."""
        self._run_hooks.append(hooks)

    def add_agent_hooks(self, agent_name: str, hooks: AgentHooks) -> None:
        """Register per-agent hooks."""
        self._agent_hooks.setdefault(agent_name, []).append(hooks)

    # -- Dispatch methods (called by WiiiRunner) --

    async def emit_run_start(self, state: AgentState) -> None:
        for h in self._run_hooks:
            try:
                await h.on_run_start(state)
            except Exception as exc:
                logger.debug("[HOOKS] on_run_start error: %s", exc)

    async def emit_run_end(self, state: AgentState, duration_ms: float) -> None:
        for h in self._run_hooks:
            try:
                await h.on_run_end(state, duration_ms)
            except Exception as exc:
                logger.debug("[HOOKS] on_run_end error: %s", exc)

    async def emit_step_start(self, step_name: str, state: AgentState) -> None:
        for h in self._run_hooks:
            try:
                await h.on_step_start(step_name, state)
            except Exception as exc:
                logger.debug("[HOOKS] on_step_start error: %s", exc)
        # Per-agent hooks
        for h in self._agent_hooks.get(step_name, []):
            try:
                await h.on_agent_start(step_name, state)
            except Exception as exc:
                logger.debug("[HOOKS] on_agent_start(%s) error: %s", step_name, exc)

    async def emit_step_end(self, step_name: str, state: AgentState, duration_ms: float) -> None:
        for h in self._run_hooks:
            try:
                await h.on_step_end(step_name, state, duration_ms)
            except Exception as exc:
                logger.debug("[HOOKS] on_step_end error: %s", exc)
        for h in self._agent_hooks.get(step_name, []):
            try:
                await h.on_agent_end(step_name, state, duration_ms)
            except Exception as exc:
                logger.debug("[HOOKS] on_agent_end(%s) error: %s", step_name, exc)

    async def emit_step_error(self, step_name: str, state: AgentState, error: Exception) -> None:
        for h in self._run_hooks:
            try:
                await h.on_step_error(step_name, state, error)
            except Exception as exc:
                logger.debug("[HOOKS] on_step_error error: %s", exc)

    async def emit_route(self, from_step: str, to_step: str, state: AgentState) -> None:
        for h in self._run_hooks:
            try:
                await h.on_route(from_step, to_step, state)
            except Exception as exc:
                logger.debug("[HOOKS] on_route error: %s", exc)

    # -- Utility --

    @property
    def has_hooks(self) -> bool:
        return bool(self._run_hooks) or bool(self._agent_hooks)
