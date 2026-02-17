"""
Resilience patterns for external service calls.

Provides circuit breaker pattern to prevent cascading failures
when external services (Gemini API, Supabase, LMS webhook) are degraded.

Extracted from cache_manager.py CircuitBreakerState and generalized.

Usage as decorator:
    @with_circuit_breaker("gemini", failure_threshold=5, recovery_timeout=60)
    async def call_gemini(...):
        ...

Usage as context manager:
    cb = get_circuit_breaker("supabase")
    async with cb:
        await do_upload()

Usage for manual check:
    cb = get_circuit_breaker("gemini")
    if cb.is_available():
        result = await call_llm()

Feature: resilience-circuit-breaker
"""

import asyncio
import functools
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation - requests flow through
    OPEN = "open"           # Failing - requests are blocked
    HALF_OPEN = "half_open" # Testing - single request allowed through


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and call is rejected."""

    def __init__(self, name: str, retry_after: float = 0.0):
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry after {retry_after:.1f}s."
        )


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    States:
    - CLOSED: Normal operation, requests flow through.
      Transitions to OPEN after `failure_threshold` consecutive failures.
    - OPEN: All requests are rejected immediately with CircuitOpenError.
      Transitions to HALF_OPEN after `recovery_timeout` seconds.
    - HALF_OPEN: One test request is allowed through.
      On success -> CLOSED. On failure -> OPEN (timer resets).

    Thread-safe via asyncio.Lock for state transitions.

    Usage:
        cb = CircuitBreaker("gemini", failure_threshold=5, recovery_timeout=60)

        # As decorator
        @cb.protect
        async def call_api():
            ...

        # As context manager
        async with cb:
            await call_api()

        # Manual check
        if cb.is_available():
            ...
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for logging (e.g. "gemini", "supabase")
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before half-open test
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    # =========================================================================
    # Public state queries
    # =========================================================================

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may be stale - use is_available() for checks)."""
        return self._state

    def is_available(self) -> bool:
        """
        Check if the circuit allows requests (non-blocking, no lock).

        Returns True for CLOSED and HALF_OPEN (after timeout).
        Returns False for OPEN (before timeout).
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed -> half-open
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                return True  # Will transition to HALF_OPEN on next call
            return False

        # HALF_OPEN - allow the test request
        return True

    @property
    def retry_after(self) -> float:
        """Seconds until the circuit breaker may allow requests again."""
        if self._state != CircuitState.OPEN:
            return 0.0
        remaining = self.recovery_timeout - (time.time() - self._last_failure_time)
        return max(0.0, remaining)

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "retry_after": round(self.retry_after, 1),
        }

    # =========================================================================
    # State transitions (locked)
    # =========================================================================

    async def record_success(self) -> None:
        """Record a successful call. Resets failure count, closes circuit."""
        async with self._lock:
            old_state = self._state
            self._failure_count = 0
            self._success_count += 1

            if old_state != CircuitState.CLOSED:
                self._state = CircuitState.CLOSED
                self._last_state_change = time.time()
                logger.warning(
                    f"[CIRCUIT_BREAKER] '{self.name}' CLOSED "
                    f"(recovered from {old_state.value})"
                )

    async def record_failure(self) -> None:
        """Record a failed call. May open the circuit."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Test request failed -> back to OPEN
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()
                logger.warning(
                    f"[CIRCUIT_BREAKER] '{self.name}' OPEN "
                    f"(half-open test failed, retry in {self.recovery_timeout}s)"
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()
                logger.warning(
                    f"[CIRCUIT_BREAKER] '{self.name}' OPEN "
                    f"after {self._failure_count} consecutive failures "
                    f"(blocking for {self.recovery_timeout}s)"
                )

    async def _check_and_acquire(self) -> None:
        """
        Check circuit state and acquire permission to make a call.

        Raises CircuitOpenError if the circuit is open.
        Transitions OPEN -> HALF_OPEN if recovery timeout has passed.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return  # All good

            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to HALF_OPEN, allow test request
                    self._state = CircuitState.HALF_OPEN
                    self._last_state_change = time.time()
                    logger.warning(
                        f"[CIRCUIT_BREAKER] '{self.name}' HALF_OPEN "
                        f"(allowing test request after {elapsed:.1f}s)"
                    )
                    return
                else:
                    # Still open, reject
                    remaining = self.recovery_timeout - elapsed
                    raise CircuitOpenError(self.name, retry_after=remaining)

            # HALF_OPEN - already allowing a test request
            # In a strict implementation we'd only allow one concurrent test,
            # but for simplicity we allow all requests through in half-open.
            return

    # =========================================================================
    # Context manager interface
    # =========================================================================

    async def __aenter__(self):
        """Acquire permission to make a call."""
        await self._check_and_acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record result based on whether an exception occurred."""
        if exc_type is None:
            await self.record_success()
        else:
            await self.record_failure()
        # Don't suppress exceptions
        return False

    # =========================================================================
    # Decorator interface
    # =========================================================================

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect an async function with this circuit breaker.

        Usage:
            cb = CircuitBreaker("my_service")

            @cb.protect
            async def call_service():
                ...
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await self._check_and_acquire()
            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except Exception:
                await self.record_failure()
                raise

        return wrapper


# =============================================================================
# Global circuit breaker registry
# =============================================================================

_registry: Dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """
    Get or create a named circuit breaker from the global registry.

    Circuit breakers are singletons by name - calling with the same name
    always returns the same instance (configuration from first call wins).

    Args:
        name: Unique name for the circuit breaker
        failure_threshold: Failures before opening (only used on creation)
        recovery_timeout: Seconds before half-open test (only used on creation)

    Returns:
        CircuitBreaker instance
    """
    if name not in _registry:
        _registry[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        logger.info(
            f"[CIRCUIT_BREAKER] Registered '{name}' "
            f"(threshold={failure_threshold}, timeout={recovery_timeout}s)"
        )
    return _registry[name]


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> Callable:
    """
    Decorator factory: protect an async function with a named circuit breaker.

    Usage:
        @with_circuit_breaker("gemini", failure_threshold=5, recovery_timeout=60)
        async def call_gemini_api(...):
            ...

    When the circuit is open, raises CircuitOpenError instead of calling
    the underlying function.

    Args:
        name: Circuit breaker name (shared across all uses of same name)
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before half-open test
    """
    def decorator(func: Callable) -> Callable:
        cb = get_circuit_breaker(name, failure_threshold, recovery_timeout)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await cb._check_and_acquire()
            try:
                result = await func(*args, **kwargs)
                await cb.record_success()
                return result
            except Exception:
                await cb.record_failure()
                raise

        # Attach circuit breaker reference for introspection
        wrapper.circuit_breaker = cb
        return wrapper

    return decorator


def get_all_circuit_breakers() -> Dict[str, Dict[str, Any]]:
    """
    Get stats for all registered circuit breakers.

    Returns:
        Dict mapping name -> stats dict
    """
    return {name: cb.get_stats() for name, cb in _registry.items()}


# =============================================================================
# Retry on Transient Errors (Sprint 68)
# Pattern: OpenAI Agents SDK / Google ADK retry behavior
# =============================================================================

import random as _random

TRANSIENT_ERRORS = (ConnectionError, TimeoutError, asyncio.TimeoutError)
TRANSIENT_HTTP_CODES = {429, 502, 503, 504}


def _is_transient(exc: Exception) -> bool:
    """Check if exception is transient (safe to retry)."""
    if isinstance(exc, TRANSIENT_ERRORS):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status and int(status) in TRANSIENT_HTTP_CODES:
        return True
    name = type(exc).__name__
    return name in ("ResourceExhausted", "RateLimitError", "ServiceUnavailable")


def retry_on_transient(max_attempts: int = 3, base_delay: float = 1.0,
                       max_delay: float = 8.0, jitter: bool = True) -> Callable:
    """Retry async function on transient errors with exponential backoff + jitter.

    Only retries ConnectionError, TimeoutError, HTTP 429/502/503/504.
    Does NOT retry ValidationError, ValueError, or other permanent failures.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if not _is_transient(exc) or attempt == max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + _random.random())
                    logger.warning(
                        "[RETRY] %s attempt %d/%d failed (%s), retrying in %.1fs",
                        func.__name__, attempt, max_attempts,
                        type(exc).__name__, delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        wrapper.retry_config = {"max_attempts": max_attempts, "base_delay": base_delay}  # type: ignore[attr-defined]
        return wrapper
    return decorator
