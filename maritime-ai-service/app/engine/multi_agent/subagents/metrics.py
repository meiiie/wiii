"""Per-subagent metrics collection.

Tracks invocation count, latency, error rate, timeout rate, and confidence
distribution for each registered subagent.  Thread-safe via module-level
singleton.

Usage::

    tracker = SubagentMetrics.get_instance()
    tracker.record("deep_search", duration_ms=1200, status="success", confidence=0.85)
    summary = tracker.summary("deep_search")
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubagentMetrics:
    """Singleton metrics tracker for subagent executions."""

    _instance: Optional[SubagentMetrics] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> SubagentMetrics:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton — for tests only."""
        cls._instance = None

    def record(
        self,
        name: str,
        *,
        duration_ms: int = 0,
        status: str = "success",
        confidence: float = 0.0,
    ) -> None:
        """Record a subagent invocation."""
        if name not in self._data:
            self._data[name] = {
                "invocations": 0,
                "total_duration_ms": 0,
                "successes": 0,
                "errors": 0,
                "timeouts": 0,
                "confidence_sum": 0.0,
                "confidence_count": 0,
                "last_invoked": 0.0,
                "durations": [],  # last N for percentile
            }

        entry = self._data[name]
        entry["invocations"] += 1
        entry["total_duration_ms"] += duration_ms
        entry["last_invoked"] = time.monotonic()

        # Keep last 100 durations for percentile calculation
        entry["durations"].append(duration_ms)
        if len(entry["durations"]) > 100:
            entry["durations"] = entry["durations"][-100:]

        if status == "success":
            entry["successes"] += 1
        elif status == "timeout":
            entry["timeouts"] += 1
        else:
            entry["errors"] += 1

        if confidence > 0:
            entry["confidence_sum"] += confidence
            entry["confidence_count"] += 1

    def summary(self, name: str) -> Optional[Dict[str, Any]]:
        """Get summary metrics for a specific subagent."""
        entry = self._data.get(name)
        if entry is None:
            return None

        inv = entry["invocations"]
        avg_dur = entry["total_duration_ms"] / inv if inv > 0 else 0
        error_rate = (entry["errors"] + entry["timeouts"]) / inv if inv > 0 else 0
        timeout_rate = entry["timeouts"] / inv if inv > 0 else 0
        avg_conf = (
            entry["confidence_sum"] / entry["confidence_count"]
            if entry["confidence_count"] > 0
            else 0.0
        )

        # P50 and P95 from recent durations
        durations = sorted(entry["durations"])
        p50 = durations[len(durations) // 2] if durations else 0
        p95_idx = min(int(len(durations) * 0.95), len(durations) - 1)
        p95 = durations[p95_idx] if durations else 0

        return {
            "name": name,
            "invocations": inv,
            "avg_duration_ms": round(avg_dur),
            "p50_duration_ms": p50,
            "p95_duration_ms": p95,
            "success_rate": round(1 - error_rate, 3),
            "error_rate": round(error_rate, 3),
            "timeout_rate": round(timeout_rate, 3),
            "avg_confidence": round(avg_conf, 3),
        }

    def all_summaries(self) -> List[Dict[str, Any]]:
        """Get summaries for all tracked subagents."""
        return [self.summary(name) for name in sorted(self._data.keys())]

    def list_names(self) -> List[str]:
        """List all tracked subagent names."""
        return sorted(self._data.keys())

    @property
    def count(self) -> int:
        """Number of tracked subagents."""
        return len(self._data)
