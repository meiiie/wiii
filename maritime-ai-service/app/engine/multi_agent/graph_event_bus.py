"""Shared event-bus state for multi-agent streaming."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_EVENT_QUEUES: Dict[str, asyncio.Queue] = {}
_EVENT_QUEUE_CREATED: Dict[str, float] = {}
_EVENT_QUEUE_MAX_AGE_SEC = 900


def _get_event_queue(bus_id: str) -> Optional[asyncio.Queue]:
    """Get event queue by bus ID (called from inside nodes)."""
    graph_streaming = sys.modules.get("app.engine.multi_agent.graph_streaming")
    patched_getter = getattr(graph_streaming, "_get_event_queue", None)
    if patched_getter is not None and patched_getter is not _get_event_queue:
        return patched_getter(bus_id)
    return _EVENT_QUEUES.get(bus_id)


def _register_event_queue(bus_id: str, queue: asyncio.Queue) -> None:
    _EVENT_QUEUES[bus_id] = queue
    _EVENT_QUEUE_CREATED[bus_id] = time.time()


def _discard_event_queue(bus_id: str | None) -> None:
    if not bus_id:
        return
    _EVENT_QUEUES.pop(bus_id, None)
    _EVENT_QUEUE_CREATED.pop(bus_id, None)


def _cleanup_stale_queues() -> int:
    """Remove event queues older than MAX_AGE to prevent memory leak."""
    now = time.time()
    stale = [
        bid
        for bid, created in _EVENT_QUEUE_CREATED.items()
        if now - created > _EVENT_QUEUE_MAX_AGE_SEC
    ]
    for bid in stale:
        _discard_event_queue(bid)
    if stale:
        logger.warning("[EVENT_BUS] Cleaned up %d stale queues", len(stale))
    return len(stale)
