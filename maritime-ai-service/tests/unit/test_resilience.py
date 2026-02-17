"""Tests for app.core.resilience — Circuit Breaker pattern."""

import asyncio
import time

import pytest

from app.core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    get_circuit_breaker,
    get_all_circuit_breakers,
    _registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear global registry between tests."""
    _registry.clear()
    yield
    _registry.clear()


class TestCircuitBreakerInit:
    """Test initialization and default state."""

    def test_default_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_default_available(self):
        cb = CircuitBreaker("test")
        assert cb.is_available() is True

    def test_custom_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=10, recovery_timeout=120.0)
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 120.0

    def test_retry_after_zero_when_closed(self):
        cb = CircuitBreaker("test")
        assert cb.retry_after == 0.0

    def test_get_stats(self):
        cb = CircuitBreaker("test_stats", failure_threshold=3, recovery_timeout=30.0)
        stats = cb.get_stats()
        assert stats["name"] == "test_stats"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_threshold"] == 3


class TestCircuitBreakerTransitions:
    """Test state transitions CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""

    @pytest.mark.asyncio
    async def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("t1", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 2

    @pytest.mark.asyncio
    async def test_opens_at_threshold(self):
        cb = CircuitBreaker("t2", failure_threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker("t3", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self):
        cb = CircuitBreaker("t4", failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()  # Opens circuit
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.is_available() is True  # Timeout passed

        await cb._check_and_acquire()
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        cb = CircuitBreaker("t5", failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb._check_and_acquire()  # -> HALF_OPEN
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("t6", failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb._check_and_acquire()  # -> HALF_OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self):
        cb = CircuitBreaker("t7", failure_threshold=1, recovery_timeout=60.0)
        await cb.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            await cb._check_and_acquire()
        assert exc_info.value.name == "t7"
        assert exc_info.value.retry_after > 0


class TestCircuitBreakerContextManager:
    """Test async context manager interface."""

    @pytest.mark.asyncio
    async def test_success_records_success(self):
        cb = CircuitBreaker("ctx1")
        async with cb:
            pass  # Simulates successful call
        assert cb._success_count == 1

    @pytest.mark.asyncio
    async def test_exception_records_failure(self):
        cb = CircuitBreaker("ctx2", failure_threshold=5)
        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("service error")
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_rejects_when_open(self):
        cb = CircuitBreaker("ctx3", failure_threshold=1, recovery_timeout=60.0)
        await cb.record_failure()
        with pytest.raises(CircuitOpenError):
            async with cb:
                pass


class TestCircuitBreakerDecorator:
    """Test the protect decorator."""

    @pytest.mark.asyncio
    async def test_decorated_function_works(self):
        cb = CircuitBreaker("dec1")

        @cb.protect
        async def my_fn():
            return 42

        result = await my_fn()
        assert result == 42
        assert cb._success_count == 1

    @pytest.mark.asyncio
    async def test_decorated_function_records_failure(self):
        cb = CircuitBreaker("dec2", failure_threshold=5)

        @cb.protect
        async def my_fn():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await my_fn()
        assert cb._failure_count == 1


class TestGlobalRegistry:
    """Test get_circuit_breaker and get_all_circuit_breakers."""

    def test_get_creates_new(self):
        cb = get_circuit_breaker("svc_a", failure_threshold=10)
        assert cb.name == "svc_a"
        assert cb.failure_threshold == 10

    def test_get_returns_same_instance(self):
        cb1 = get_circuit_breaker("svc_b")
        cb2 = get_circuit_breaker("svc_b")
        assert cb1 is cb2

    def test_get_all(self):
        get_circuit_breaker("alpha")
        get_circuit_breaker("beta")
        all_stats = get_all_circuit_breakers()
        assert "alpha" in all_stats
        assert "beta" in all_stats
        assert all_stats["alpha"]["state"] == "closed"
