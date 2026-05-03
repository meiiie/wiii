"""Subagent isolation — Anthropic-style Task delegation.

Phase 12 of the runtime migration epic (issue #207). The biggest
architectural gap from the brutal-honest assessment closed here:
parent agents that fan out work to child agents WITHOUT polluting their
own context window.

The pattern (lifted from Anthropic's Managed Agents API):

1. Parent decides "I need a subtask done" — e.g. RAG retrieval, tool
   chain, multi-step reasoning that takes 8 turns.
2. Parent calls ``SubagentRunner.run(SubagentTask(...))``.
3. Runner mints a child ``session_id`` derived from the parent's, kicks
   off a fresh session log scope, runs the child's loop to completion.
4. ONLY a ``SubagentResult`` (final summary + a few metadata fields)
   bubbles back to the parent. The child's user/assistant/tool turns
   stay inside the child's session log.

When the parent later ``wake()``s, its event log shows
``subagent_started`` + ``subagent_completed`` events, NOT 8 turns of
working memory. That is the entire point — context windows stay focused
on the parent's narrative while compute scales.

Feature-gated by ``enable_subagent_isolation`` (default False). The
``runner_callable`` parameter is injectable so this module is testable
in isolation; the default factory binds to ``ChatService.process_message``
when the flag flips on in production.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Optional

from app.engine.runtime.session_event_log import (
    SessionEventLog,
    get_session_event_log,
)

logger = logging.getLogger(__name__)


SubagentStatus = Literal["success", "max_steps_exceeded", "error", "disabled"]


@dataclass
class SubagentTask:
    """A self-contained unit of work the parent delegates to a child agent."""

    description: str
    """Natural-language goal — what the parent wants accomplished."""

    parent_session_id: str
    """Parent's session id. Used for provenance + child id derivation."""

    parent_org_id: Optional[str] = None
    """Multi-tenant scope. Mirrored to the child so the child's events
    cannot leak across orgs."""

    max_steps: int = 10
    """Hard cap on the child's ReAct steps. Bounds runaway recursion."""

    context_hints: dict = field(default_factory=dict)
    """Narrow context from parent — facts, recent docs, user profile.
    Deliberately NOT the parent's full conversation history; the whole
    point is to keep the child's window small."""

    metadata: dict = field(default_factory=dict)
    """Arbitrary tags for observability (parent intent, route, etc.)."""


@dataclass
class SubagentResult:
    """What bubbles back to the parent. Just the conclusion + provenance."""

    status: SubagentStatus
    summary: str = ""
    sources: list[dict] = field(default_factory=list)
    tool_calls_made: int = 0
    child_session_id: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    raw_output: Optional[str] = None
    """Full child response text — opt-in for parents that want the
    detail. Most parents should consume only ``summary``."""


# A runner is anything that turns a SubagentTask into a SubagentResult.
RunnerCallable = Callable[["SubagentTask", str], Awaitable["SubagentResult"]]


class SubagentRunner:
    """Spawns child agents in isolated session scopes.

    The runner is injectable: tests pass a fake; production wires the
    default factory which delegates to ``ChatService.process_message``.
    """

    def __init__(
        self,
        *,
        runner_callable: Optional[RunnerCallable] = None,
        event_log: Optional[SessionEventLog] = None,
    ) -> None:
        self._runner = runner_callable
        self._event_log = event_log

    @property
    def event_log(self) -> SessionEventLog:
        if self._event_log is None:
            self._event_log = get_session_event_log()
        return self._event_log

    @staticmethod
    def derive_child_session_id(parent_session_id: str) -> str:
        """Mint a deterministic-prefix child id so log queries can find siblings.

        Format: ``{parent}::sub::{8-char hex}``. The double-colon namespace
        marker is unlikely to appear in legitimate user-supplied ids.
        """
        suffix = uuid.uuid4().hex[:8]
        return f"{parent_session_id}::sub::{suffix}"

    async def run(self, task: SubagentTask) -> SubagentResult:
        """Run ``task`` in an isolated child session.

        Records ``subagent_started`` / ``subagent_completed`` events on
        the **parent's** session log so a wake() of the parent shows only
        the summary, not the child's working messages.
        """
        from app.core.config import settings

        if not settings.enable_subagent_isolation:
            return SubagentResult(
                status="disabled",
                error="enable_subagent_isolation is False",
            )

        if self._runner is None:
            return SubagentResult(
                status="error",
                error="SubagentRunner has no runner_callable bound",
            )

        child_session_id = self.derive_child_session_id(task.parent_session_id)
        await self.event_log.append(
            session_id=task.parent_session_id,
            event_type="subagent_started",
            payload={
                "child_session_id": child_session_id,
                "description": task.description,
                "metadata": task.metadata,
            },
            org_id=task.parent_org_id,
        )

        started = time.monotonic()
        try:
            result = await self._runner(task, child_session_id)
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            await self.event_log.append(
                session_id=task.parent_session_id,
                event_type="subagent_completed",
                payload={
                    "child_session_id": child_session_id,
                    "status": "error",
                    "duration_ms": duration_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                org_id=task.parent_org_id,
            )
            logger.exception("[SubagentRunner] runner raised: %s", exc)
            return SubagentResult(
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                child_session_id=child_session_id,
                duration_ms=duration_ms,
            )

        # Coerce the runner's return value into our shape so callers can
        # rely on the contract regardless of which runner is wired in.
        if not isinstance(result, SubagentResult):
            result = SubagentResult(
                status="success",
                summary=str(result),
                child_session_id=child_session_id,
            )
        if not result.child_session_id:
            result.child_session_id = child_session_id
        if result.duration_ms == 0:
            result.duration_ms = int((time.monotonic() - started) * 1000)

        await self.event_log.append(
            session_id=task.parent_session_id,
            event_type="subagent_completed",
            payload={
                "child_session_id": child_session_id,
                "status": result.status,
                "summary": result.summary,
                "tool_calls_made": result.tool_calls_made,
                "duration_ms": result.duration_ms,
                "error": result.error,
            },
            org_id=task.parent_org_id,
        )
        return result


_singleton: Optional[SubagentRunner] = None


def get_subagent_runner() -> SubagentRunner:
    """Default singleton — production binds the runner_callable lazily.

    Tests should construct ``SubagentRunner`` directly with a fake
    ``runner_callable`` rather than rely on this; the singleton exists so
    parent code paths can call ``get_subagent_runner().run(task)`` without
    wiring DI everywhere.
    """
    global _singleton
    if _singleton is None:
        _singleton = SubagentRunner()
    return _singleton


def _reset_for_tests() -> None:
    """Clear the singleton — test fixtures only."""
    global _singleton
    _singleton = None


__all__ = [
    "SubagentTask",
    "SubagentResult",
    "SubagentRunner",
    "SubagentStatus",
    "get_subagent_runner",
]
