"""
SubSoul Event Bus — Async communication protocol between parent and SubSouls.

Handles:
    - SubSoul → Parent: ESCALATION, DAILY_REPORT, STATUS_UPDATE, DISCOVERY
    - Parent → SubSoul: COMMAND, KILL_SWITCH, CONFIG_UPDATE
    - Priority routing: CRITICAL→immediate, HIGH→next heartbeat, LOW→daily summary

Design:
    - Async queue-based (asyncio.Queue per subscriber)
    - Audit trail: every event logged to DB
    - Fire-and-forget: emitters never block
    - Multiple subscribers: parent + Telegram + audit logger
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Event Types and Priority
# =============================================================================


class EventType(str, Enum):
    """Types of events in the SubSoul communication protocol."""

    # SubSoul → Parent
    ESCALATION = "ESCALATION"           # Urgent: needs parent attention/action
    DAILY_REPORT = "DAILY_REPORT"       # End-of-day summary
    STATUS_UPDATE = "STATUS_UPDATE"     # Periodic status (mood, actions taken)
    DISCOVERY = "DISCOVERY"             # Interesting market pattern found
    ACTION_TAKEN = "ACTION_TAKEN"       # Log of a protective action executed
    MOOD_CHANGE = "MOOD_CHANGE"         # SubSoul mood transition

    # Parent → SubSoul
    COMMAND = "COMMAND"                 # Direct command from parent/human
    KILL_SWITCH = "KILL_SWITCH"         # Emergency stop
    CONFIG_UPDATE = "CONFIG_UPDATE"     # Runtime config change

    # Bridge (Sprint 213)
    BRIDGE_EVENT = "BRIDGE_EVENT"       # Event received via SoulBridge from remote peer

    # Consultation (Sprint 215)
    CONSULTATION = "CONSULTATION"                   # Cross-soul query request
    CONSULTATION_REPLY = "CONSULTATION_REPLY"       # Cross-soul query response


class EventPriority(str, Enum):
    """Priority levels for event routing."""

    CRITICAL = "CRITICAL"   # Immediate delivery (Telegram, parent wake-up)
    HIGH = "HIGH"           # Next parent heartbeat cycle
    NORMAL = "NORMAL"       # Batched for periodic summary
    LOW = "LOW"             # Daily report only


# =============================================================================
# Event Model
# =============================================================================


class SubSoulEvent(BaseModel):
    """A single event in the SubSoul communication protocol."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    priority: EventPriority = EventPriority.NORMAL
    subsoul_id: str
    source: str = ""        # "subsoul:bro", "parent:wiii", "human"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_log_dict(self) -> Dict[str, Any]:
        """Serializable dict for audit logging."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "priority": self.priority.value,
            "subsoul_id": self.subsoul_id,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Event Handlers
# =============================================================================

# Type alias for event handler coroutines
EventHandler = Callable[[SubSoulEvent], Coroutine[Any, Any, None]]


class EventSubscription(BaseModel):
    """A subscription to events from a specific SubSoul or all SubSouls."""

    class Config:
        arbitrary_types_allowed = True

    subscriber_id: str
    subsoul_filter: Optional[str] = None   # None = all SubSouls
    event_types: Optional[List[EventType]] = None  # None = all types
    min_priority: EventPriority = EventPriority.LOW


# =============================================================================
# Event Bus (Singleton)
# =============================================================================


class SubSoulEventBus:
    """Async event bus for parent↔SubSoul communication.

    Features:
    - Priority-based routing
    - Per-subscriber queues (no blocking between handlers)
    - Audit trail logging
    - Fire-and-forget emission (caller never blocks)
    - Kill switch support (immediate delivery, bypasses queue)
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[tuple[EventSubscription, EventHandler]]] = defaultdict(list)
        self._event_log: List[Dict[str, Any]] = []  # In-memory audit (recent 1000)
        self._max_log_size = 1000
        self._total_events = 0
        self._kill_switch_handlers: List[EventHandler] = []

    async def emit(self, event: SubSoulEvent) -> None:
        """Emit an event to all matching subscribers.

        Fire-and-forget: errors in handlers are logged, never propagated.
        """
        self._total_events += 1
        self._audit_log(event)

        logger.info(
            "[EVENT_BUS] %s from %s — priority=%s, type=%s",
            event.subsoul_id,
            event.source,
            event.priority.value,
            event.event_type.value,
        )

        # Kill switch bypasses normal routing
        if event.event_type == EventType.KILL_SWITCH:
            for handler in self._kill_switch_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error("[EVENT_BUS] Kill switch handler error: %s", e)
            return

        # Route to matching subscribers
        tasks = []
        for subscriber_id, subscriptions in self._handlers.items():
            for sub, handler in subscriptions:
                if self._matches(sub, event):
                    tasks.append(self._safe_deliver(handler, event, subscriber_id))

        if tasks:
            await asyncio.gather(*tasks)

    def subscribe(
        self,
        subscriber_id: str,
        handler: EventHandler,
        subsoul_filter: Optional[str] = None,
        event_types: Optional[List[EventType]] = None,
        min_priority: EventPriority = EventPriority.LOW,
    ) -> None:
        """Register an event handler.

        Args:
            subscriber_id: Unique ID for the subscriber (e.g., "parent_wiii", "telegram_bot")
            handler: Async callable receiving SubSoulEvent
            subsoul_filter: Only receive events from this SubSoul (None=all)
            event_types: Only receive these event types (None=all)
            min_priority: Minimum priority to deliver
        """
        subscription = EventSubscription(
            subscriber_id=subscriber_id,
            subsoul_filter=subsoul_filter,
            event_types=event_types,
            min_priority=min_priority,
        )
        self._handlers[subscriber_id].append((subscription, handler))
        logger.info(
            "[EVENT_BUS] Subscribed '%s' — filter=%s, types=%s, min_priority=%s",
            subscriber_id,
            subsoul_filter,
            event_types,
            min_priority.value,
        )

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove all subscriptions for a subscriber."""
        if subscriber_id in self._handlers:
            del self._handlers[subscriber_id]
            logger.info("[EVENT_BUS] Unsubscribed '%s'", subscriber_id)

    def register_kill_switch_handler(self, handler: EventHandler) -> None:
        """Register a handler that fires immediately on KILL_SWITCH events."""
        self._kill_switch_handlers.append(handler)

    def get_recent_events(
        self,
        subsoul_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent events from audit log (for API/debugging)."""
        events = self._event_log
        if subsoul_id:
            events = [e for e in events if e.get("subsoul_id") == subsoul_id]
        return events[-limit:]

    @property
    def total_events(self) -> int:
        return self._total_events

    @property
    def subscriber_count(self) -> int:
        return len(self._handlers)

    # ── Internal ──

    def _matches(self, sub: EventSubscription, event: SubSoulEvent) -> bool:
        """Check if an event matches a subscription filter."""
        # SubSoul filter
        if sub.subsoul_filter and event.subsoul_id != sub.subsoul_filter:
            return False

        # Event type filter
        if sub.event_types and event.event_type not in sub.event_types:
            return False

        # Priority filter
        priority_order = {
            EventPriority.LOW: 0,
            EventPriority.NORMAL: 1,
            EventPriority.HIGH: 2,
            EventPriority.CRITICAL: 3,
        }
        if priority_order.get(event.priority, 0) < priority_order.get(sub.min_priority, 0):
            return False

        return True

    async def _safe_deliver(
        self, handler: EventHandler, event: SubSoulEvent, subscriber_id: str
    ) -> None:
        """Deliver event to handler with error catching."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "[EVENT_BUS] Handler error for subscriber '%s': %s",
                subscriber_id,
                e,
                exc_info=True,
            )

    def _audit_log(self, event: SubSoulEvent) -> None:
        """Append event to in-memory audit log (capped)."""
        self._event_log.append(event.to_log_dict())
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]


# =============================================================================
# Singleton
# =============================================================================

_event_bus: Optional[SubSoulEventBus] = None


def get_event_bus() -> SubSoulEventBus:
    """Get or create the singleton SubSoulEventBus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = SubSoulEventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the singleton (for testing)."""
    global _event_bus
    _event_bus = None
