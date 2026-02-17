"""
Tests for Sprint 38: CacheManager and CircuitBreakerState.

Covers:
- CircuitBreakerState lifecycle (closed → open → half-open → closed)
- CacheManager.get() with circuit breaker
- CacheManager.set() with circuit breaker
- CacheManager.get_stats()
- CacheManager.invalidate_document()
"""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cache.cache_manager import CircuitBreakerState


# ============================================================================
# CircuitBreakerState
# ============================================================================


class TestCircuitBreakerState:
    def test_initial_state(self):
        cb = CircuitBreakerState()
        assert cb.failure_count == 0
        assert cb.is_open is False
        assert cb.is_closed() is True

    def test_record_single_failure(self):
        cb = CircuitBreakerState()
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.is_open is False

    def test_opens_at_threshold(self):
        cb = CircuitBreakerState(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open is True
        assert cb.is_closed() is False

    def test_success_resets(self):
        cb = CircuitBreakerState(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_success_closes_open_circuit(self):
        cb = CircuitBreakerState(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        cb.record_success()
        assert cb.is_open is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreakerState(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.is_closed() is False

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.is_closed() is True  # Half-open

    def test_stays_open_before_timeout(self):
        cb = CircuitBreakerState(failure_threshold=2, recovery_timeout=60.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.is_closed() is False

    def test_failure_count_accumulates(self):
        cb = CircuitBreakerState(failure_threshold=10)
        for i in range(5):
            cb.record_failure()
        assert cb.failure_count == 5
        assert cb.is_open is False

    def test_custom_thresholds(self):
        cb = CircuitBreakerState(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.is_open is True


# ============================================================================
# CacheManager with mocked dependencies
# ============================================================================


class TestCacheManager:
    @pytest.fixture
    def mock_cache(self):
        """Create CacheManager with mocked underlying cache and invalidation."""
        with patch("app.cache.cache_manager.get_semantic_cache") as mock_get_cache, \
             patch("app.cache.cache_manager.get_invalidation_manager") as mock_get_inv:

            mock_response_cache = MagicMock()
            mock_response_cache.get = AsyncMock()
            mock_response_cache.set = AsyncMock()
            mock_response_cache.invalidate_by_document = AsyncMock()
            mock_response_cache.get_stats = MagicMock(return_value=MagicMock(
                to_dict=MagicMock(return_value={"hits": 10, "misses": 5})
            ))

            mock_inv = MagicMock()
            mock_inv.register_handler = MagicMock()
            mock_inv.on_document_updated = AsyncMock(return_value={"response": 3})
            mock_inv.get_health = MagicMock(return_value={"status": "ok"})

            mock_get_cache.return_value = mock_response_cache
            mock_get_inv.return_value = mock_inv

            from app.cache.cache_manager import CacheManager
            manager = CacheManager()
            yield manager, mock_response_cache, mock_inv

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        mock_response_cache.get.return_value = MagicMock(hit=True, value="cached answer")

        result = await manager.get("query", [0.1, 0.2])
        assert result.hit is True
        assert manager._total_requests == 1

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        mock_response_cache.get.return_value = MagicMock(hit=False)

        result = await manager.get("query", [0.1, 0.2])
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_get_circuit_open_bypasses(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        # Force circuit open
        manager._circuit.is_open = True
        manager._circuit.last_failure_time = time.time()
        manager._circuit.recovery_timeout = 60.0

        result = await manager.get("query", [0.1, 0.2])
        assert result.hit is False
        assert manager._cache_bypasses == 1
        mock_response_cache.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_exception_opens_circuit(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        manager._circuit.failure_threshold = 1
        mock_response_cache.get.side_effect = RuntimeError("DB error")

        result = await manager.get("query", [0.1, 0.2])
        assert result.hit is False
        assert manager._circuit.is_open is True

    @pytest.mark.asyncio
    async def test_set_success(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        result = await manager.set("query", [0.1], "response", ["doc1"])
        assert result is True
        mock_response_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_circuit_open(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        manager._circuit.is_open = True
        manager._circuit.last_failure_time = time.time()
        manager._circuit.recovery_timeout = 60.0

        result = await manager.set("query", [0.1], "response")
        assert result is False
        mock_response_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_exception(self, mock_cache):
        manager, mock_response_cache, _ = mock_cache
        manager._circuit.failure_threshold = 1
        mock_response_cache.set.side_effect = RuntimeError("fail")

        result = await manager.set("query", [0.1], "response")
        assert result is False
        assert manager._circuit.is_open is True

    @pytest.mark.asyncio
    async def test_invalidate_document(self, mock_cache):
        manager, _, mock_inv = mock_cache
        result = await manager.invalidate_document("doc1")
        assert result == {"response": 3}
        mock_inv.on_document_updated.assert_called_once_with("doc1", "")

    def test_get_stats(self, mock_cache):
        manager, _, _ = mock_cache
        stats = manager.get_stats()
        assert "total_requests" in stats
        assert "circuit_breaker" in stats
        assert "response_cache" in stats
        assert "invalidation" in stats

    def test_is_enabled(self, mock_cache):
        manager, _, _ = mock_cache
        assert isinstance(manager.is_enabled, bool)

    def test_circuit_is_open_property(self, mock_cache):
        manager, _, _ = mock_cache
        assert manager.circuit_is_open is False
        manager._circuit.is_open = True
        assert manager.circuit_is_open is True
