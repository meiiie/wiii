"""SubagentRunner ↔ ChatService bridge.

Phase 15 of the runtime migration epic (issue #207). Phase 12 shipped
the isolation harness (``SubagentRunner``) but left ``runner_callable``
unbound — production parents that called ``run(task)`` got an
``error / "no runner_callable"`` result. This module fills that gap by
binding the existing battle-tested ``ChatService`` as the default runner.

Wire shape (intentionally minimal):

    SubagentTask(description="...", parent_session_id="p1") →
        chatservice_runner(task, child_session_id) →
            ChatRequest(message=task.description, session_id=child_session_id, ...) →
            ChatService.process_message(...) → InternalChatResponse →
        SubagentResult(status="success", summary=..., sources=..., tool_calls_made=...)

The bridge does NOT replay the parent's history — by design. The whole
point of subagent isolation is a clean child window scoped to the task
description + any explicit ``context_hints``. A parent that wants the
child to know more must encode it in ``description`` or ``context_hints``.

Failure modes:
- ChatService raises → SubagentRunner.run catches it and emits a
  ``subagent_completed`` event with ``status="error"``. We do NOT swallow
  exceptions here — let the runner's own error path own the protocol.
- Returned response is missing fields → fall back to safe defaults (empty
  summary, zero counts) rather than crashing.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.engine.runtime.subagent_runner import (
    SubagentResult,
    SubagentRunner,
    SubagentTask,
    get_subagent_runner,
)

logger = logging.getLogger(__name__)


def _format_description(task: SubagentTask) -> str:
    """Materialise the child's user-message body.

    Description is the primary signal. ``context_hints`` ride as a
    structured suffix so the LLM can see them without losing them in
    free-form prose.
    """
    lines = [task.description.strip()]
    if task.context_hints:
        lines.append("")
        lines.append("Context hints (do not echo verbatim):")
        for key, value in task.context_hints.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _count_tool_calls(internal_response) -> int:
    """Extract the tool-call count from whichever metadata shape is present."""
    metadata = getattr(internal_response, "metadata", None) or {}
    tools_used = metadata.get("tools_used")
    if isinstance(tools_used, list):
        return len(tools_used)
    raw = metadata.get("tool_calls")
    if isinstance(raw, list):
        return len(raw)
    return 0


def _coerce_sources(internal_response) -> list[dict]:
    """Return citation dicts; fall back to ``[]`` on any shape mismatch."""
    raw_sources = getattr(internal_response, "sources", None) or []
    sources: list[dict] = []
    for src in raw_sources:
        if hasattr(src, "model_dump"):
            try:
                sources.append(src.model_dump())
                continue
            except Exception:  # noqa: BLE001
                pass
        if isinstance(src, dict):
            sources.append(src)
    return sources


async def chatservice_subagent_runner(
    task: SubagentTask, child_session_id: str
) -> SubagentResult:
    """Default runner_callable: run a child agent through ChatService.

    Imports happen inside the function so this module's import is free of
    runtime side effects — call sites can register the bridge without
    pulling ChatService into module-load.
    """
    from app.models.schemas import ChatRequest, UserRole
    from app.services.chat_service import get_chat_service

    request = ChatRequest(
        user_id=f"subagent::{task.parent_session_id}",
        message=_format_description(task),
        role=UserRole.STUDENT,
        session_id=child_session_id,
        organization_id=task.parent_org_id,
    )

    response = await get_chat_service().process_message(request)
    summary = getattr(response, "message", "") or ""
    return SubagentResult(
        status="success",
        summary=summary,
        sources=_coerce_sources(response),
        tool_calls_made=_count_tool_calls(response),
        child_session_id=child_session_id,
        raw_output=summary,
    )


def wire_default_subagent_runner(
    runner: Optional[SubagentRunner] = None,
) -> SubagentRunner:
    """Bind ``chatservice_subagent_runner`` as the default callable.

    Idempotent: re-calling overwrites the binding. Tests should NOT call
    this — they construct ``SubagentRunner(runner_callable=fake)``
    directly. Production startup (or the first parent that calls
    ``get_subagent_runner()``) is the right place to wire the default.
    """
    target = runner or get_subagent_runner()
    if target._runner is None:  # noqa: SLF001 — explicit DI seam
        target._runner = chatservice_subagent_runner
    return target


__all__ = [
    "chatservice_subagent_runner",
    "wire_default_subagent_runner",
]
