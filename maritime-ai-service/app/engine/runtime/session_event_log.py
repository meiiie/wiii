"""Append-only durable event log per chat session.

Phase 5 of the runtime migration epic (issue #207). Borrows the
Anthropic Managed Agents pattern: harness (stateless control loop) +
session (this module — append-only log outside the context window) +
sandbox (pluggable execution).

Two backends share a single interface so call sites stay agnostic:

- ``InMemorySessionEventLog`` — feature flag off (default) or test mode.
  Per-session deque guarded by a process-local lock. Loses data on
  restart; fine while ``enable_session_event_log = False``.
- ``PostgresSessionEventLog`` — feature flag on. Writes through the
  existing async SQLAlchemy session. Enforces monotonic ``seq`` per
  session and surfaces ``org_id`` for multi-tenant filtering.

Event types are not enumerated as an enum on purpose — phases 5/6 will
add new ones (``tool_call``, ``tool_result``, ``assistant_chunk``, ...)
and a closed enum would force migration churn. Keep them as opaque
strings; observers filter by type.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionEvent:
    """One immutable entry in a session's event log."""

    session_id: str
    event_type: str
    payload: dict
    seq: int
    org_id: Optional[str] = None


class SessionEventLog(Protocol):
    """Backend-agnostic interface every consumer depends on."""

    async def append(
        self,
        *,
        session_id: str,
        event_type: str,
        payload: dict,
        org_id: Optional[str] = None,
    ) -> SessionEvent:
        ...

    async def get_events(
        self,
        *,
        session_id: str,
        org_id: Optional[str] = None,
        since_seq: Optional[int] = None,
    ) -> list[SessionEvent]:
        ...

    async def latest_seq(
        self, *, session_id: str, org_id: Optional[str] = None
    ) -> int:
        ...


@dataclass
class _SessionState:
    seq: int = 0
    events: list[SessionEvent] = field(default_factory=list)


class InMemorySessionEventLog:
    """Process-local fallback used when the DB-backed log is disabled.

    Not durable across restarts. Suitable for tests and the default
    feature-flag-off path so consumers can call into the same interface
    without branching.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionState] = {}
        self._lock = asyncio.Lock()

    async def append(
        self,
        *,
        session_id: str,
        event_type: str,
        payload: dict,
        org_id: Optional[str] = None,
    ) -> SessionEvent:
        async with self._lock:
            state = self._sessions.setdefault(session_id, _SessionState())
            state.seq += 1
            event = SessionEvent(
                session_id=session_id,
                event_type=event_type,
                payload=dict(payload),
                seq=state.seq,
                org_id=org_id,
            )
            state.events.append(event)
            return event

    async def get_events(
        self,
        *,
        session_id: str,
        org_id: Optional[str] = None,
        since_seq: Optional[int] = None,
    ) -> list[SessionEvent]:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return []
            events = state.events
            if org_id is not None:
                events = [e for e in events if e.org_id == org_id]
            if since_seq is not None:
                events = [e for e in events if e.seq > since_seq]
            return list(events)

    async def latest_seq(
        self, *, session_id: str, org_id: Optional[str] = None
    ) -> int:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return 0
            if org_id is None:
                return state.seq
            # When filtering by org, return the highest matching seq.
            for event in reversed(state.events):
                if event.org_id == org_id:
                    return event.seq
            return 0


_singleton: Optional[SessionEventLog] = None


def get_session_event_log() -> SessionEventLog:
    """Return the configured event log instance.

    Phase 5 ships only the in-memory backend; the Postgres backend lands
    in Phase 5b alongside the wake/replay path. The feature flag
    ``enable_session_event_log`` will switch the default.
    """
    global _singleton
    if _singleton is None:
        _singleton = InMemorySessionEventLog()
    return _singleton


def _reset_for_tests() -> None:
    """Clear the singleton — test fixtures only."""
    global _singleton
    _singleton = None


__all__ = [
    "SessionEvent",
    "SessionEventLog",
    "InMemorySessionEventLog",
    "get_session_event_log",
]
