"""
Per-Platform Circuit Breaker — Encapsulated from product_search_tools.py

Sprint 149: "Cắm & Chạy" — Plugin Architecture for Product Search

Extracted from Sprint 148's module-level dict into a proper class.
Thread-safe, per-platform isolation, configurable threshold + recovery.
"""

import logging
import threading
import time
from typing import Dict

logger = logging.getLogger(__name__)


class PerPlatformCircuitBreaker:
    """
    Circuit breaker with per-platform isolation.

    After `threshold` consecutive failures, the circuit opens for `recovery_seconds`.
    After recovery period, the next call is allowed (half-open → closed on success).
    """

    def __init__(self, threshold: int = 3, recovery_seconds: float = 120.0):
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self._states: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def is_open(self, platform_id: str) -> bool:
        """Check if circuit breaker is open (blocking calls) for a platform."""
        with self._lock:
            state = self._states.get(platform_id)
            if state is None:
                return False
            if state["failures"] >= self.threshold:
                if time.time() - state["last_failure"] < self.recovery_seconds:
                    return True
                # Recovery period elapsed — allow half-open attempt
                state["failures"] = 0
            return False

    def record_failure(self, platform_id: str) -> None:
        """Record a failure for a platform."""
        with self._lock:
            state = self._states.setdefault(
                platform_id, {"failures": 0, "last_failure": 0.0}
            )
            state["failures"] += 1
            state["last_failure"] = time.time()

    def record_success(self, platform_id: str) -> None:
        """Record success — reset failure count."""
        with self._lock:
            if platform_id in self._states:
                self._states[platform_id]["failures"] = 0

    def reset(self, platform_id: str = None) -> None:
        """Reset circuit breaker state. If platform_id is None, reset all."""
        with self._lock:
            if platform_id is None:
                self._states.clear()
            elif platform_id in self._states:
                del self._states[platform_id]

    def get_failure_count(self, platform_id: str) -> int:
        """Get current failure count for a platform."""
        with self._lock:
            state = self._states.get(platform_id)
            return state["failures"] if state else 0
