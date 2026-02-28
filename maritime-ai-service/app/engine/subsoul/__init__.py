"""
SubSoul Protocol — Event bus for cross-soul communication.

Retained from Sprint 211 SubSoul Framework after bro-subsoul separation.
Only protocol.py remains — used by soul_bridge for EventBus inter-soul messaging.
The full SubSoul ABC (base, emotion, heartbeat, manager) has been moved to
the standalone bro-subsoul project at E:\\Sach\\DuAn\\bro-subsoul.
"""

from app.engine.subsoul.protocol import (
    SubSoulEvent,
    SubSoulEventBus,
    EventPriority,
    EventType,
    get_event_bus,
    reset_event_bus,
)

__all__ = [
    "SubSoulEvent",
    "SubSoulEventBus",
    "EventPriority",
    "EventType",
    "get_event_bus",
    "reset_event_bus",
]
