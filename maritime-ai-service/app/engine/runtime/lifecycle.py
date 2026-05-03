"""Lifecycle hooks — formalised attach points for the runtime.

Phase 27 of the runtime migration epic (issue #207). Phase 25 shipped
the run-state machine; Phase 13/24 the metrics + tracing façades.
This module ties them together: a single ``Lifecycle`` registry where
extensions register hooks at named points, fired by the dispatcher /
SubagentRunner / native_dispatch when events of interest occur.

Hook points (named after the openai-agents-python convention):

- ``on_run_start`` — chat run begins, before any provider call.
- ``on_run_end`` — chat run completes (success or final failure).
- ``on_run_error`` — exception raised mid-run, BEFORE retry decision.
- ``on_tool_start`` — about to dispatch a tool call (after guardrails).
- ``on_tool_end`` — tool returned (success or error).
- ``on_subagent_start`` — SubagentRunner spawned a child.
- ``on_subagent_end`` — child returned, parent has the SubagentResult.

Design points:
- **Async hooks**. Hooks may want to write to the durable session log,
  forward telemetry, etc. Sync would force them to use threads.
- **Faulty hook does not break the request**. Each hook runs inside
  its own try/except; exceptions are logged at debug, never raised.
- **Order of registration is preserved** but two hooks at the same
  point are independent — one's failure doesn't skip the other.
- **Idempotent registration** — adding the same hook twice no-ops.
- **Per-hook-point unregister** keeps the registry tidy.

Out of scope today:
- Hook priority ordering — registration order is good enough.
- Conditional hooks (fire only for org X) — hooks themselves can
  filter on context; no need to bake it in.
- Persistent hook state — hooks are stateless or own their own state.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class HookPoint(StrEnum):
    """Named events the runtime fires at."""

    ON_RUN_START = "on_run_start"
    ON_RUN_END = "on_run_end"
    ON_RUN_ERROR = "on_run_error"
    ON_TOOL_START = "on_tool_start"
    ON_TOOL_END = "on_tool_end"
    ON_SUBAGENT_START = "on_subagent_start"
    ON_SUBAGENT_END = "on_subagent_end"


HookCallable = Callable[[dict], Awaitable[None]]
"""Hook signature: receives a single ``payload`` dict, returns nothing.

Payloads are documented per hook point at the call site (the
dispatcher); the registry doesn't validate shape because that would
slow the hot path. Hooks should treat the payload as read-only.
"""


class Lifecycle:
    """Registry of async hooks attached to ``HookPoint`` events."""

    def __init__(self) -> None:
        self._hooks: dict[HookPoint, list[HookCallable]] = {
            point: [] for point in HookPoint
        }

    def register(self, point: HookPoint, hook: HookCallable) -> None:
        """Add ``hook`` at ``point``. No-op if already registered."""
        bucket = self._hooks[point]
        if hook not in bucket:
            bucket.append(hook)

    def unregister(self, point: HookPoint, hook: HookCallable) -> bool:
        """Remove ``hook`` at ``point``. Returns True if anything was removed."""
        bucket = self._hooks[point]
        if hook in bucket:
            bucket.remove(hook)
            return True
        return False

    def hooks_at(self, point: HookPoint) -> list[HookCallable]:
        """Return a copy of the hooks registered at ``point``."""
        return list(self._hooks[point])

    async def fire(
        self, point: HookPoint, payload: Optional[dict[str, Any]] = None
    ) -> None:
        """Run every hook registered at ``point`` with ``payload``.

        Each hook runs in its own try/except so one bad hook cannot
        break the dispatcher. Hook exceptions are logged at debug —
        the request continues. If the dispatcher needs to KNOW a hook
        failed, register a wrapper that tracks success itself.
        """
        bucket = self._hooks[point]
        if not bucket:
            return
        data = payload or {}
        for hook in list(bucket):
            try:
                await hook(data)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "[lifecycle] hook %s at %s raised: %s",
                    getattr(hook, "__name__", repr(hook)),
                    point.value,
                    exc,
                )

    def reset(self) -> None:
        """Drop every registered hook. Tests + reload only."""
        for bucket in self._hooks.values():
            bucket.clear()


_lifecycle = Lifecycle()


def get_lifecycle() -> Lifecycle:
    """Return the process-global ``Lifecycle`` registry."""
    return _lifecycle


def _reset_for_tests() -> None:
    """Clear every hook on the singleton — test fixtures only."""
    _lifecycle.reset()


__all__ = [
    "HookPoint",
    "HookCallable",
    "Lifecycle",
    "get_lifecycle",
]
