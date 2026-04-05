"""Shared runtime state for lightweight heartbeat metrics."""

from __future__ import annotations

_current_heartbeat_count = 0


def get_current_heartbeat_count() -> int:
    return _current_heartbeat_count


def set_current_heartbeat_count(count: int) -> int:
    global _current_heartbeat_count
    _current_heartbeat_count = max(0, int(count))
    return _current_heartbeat_count
