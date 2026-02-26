"""
Sprint 190: ChainedAdapter Unit Tests

Tests for the ChainedAdapter meta-adapter that implements priority-based
fallback across multiple search backends with per-backend circuit breaker.

31 tests across 5 categories:
1. TestInitialization - Constructor, priority sorting, defaults (5 tests)
2. TestSearchFallbackChain - Fallback logic: success, empty, exception (10 tests)
3. TestCircuitBreakerIntegration - Open/closed/half-open states (10 tests)
4. TestHelperMethods - get_adapter_count, get_backend_keys, edge cases (5 tests)
5. TestDefaultToolDescription - Tool description fallback (1 test)
"""

import logging
import time
import pytest
from unittest.mock import MagicMock, patch

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.chained_adapter import ChainedAdapter
from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker


# ============================================================================
# Helpers
# ============================================================================


def _make_results(n: int, platform: str = "test") -> list:
    """Create n ProductSearchResult instances."""
    return [
        ProductSearchResult(
            platform=platform,
            title=f"Product {i}",
            price=f"{(i + 1) * 100000} VND",
        )
        for i in range(n)
    ]


def _make_mock_adapter(
    pid: str = "mock",
    backend: BackendType = BackendType.SERPER,
    results=None,
    raises=None,
    priority: int = 5,
) -> MagicMock:
    """Create a mock SearchPlatformAdapter with configurable behavior."""
    adapter = MagicMock(spec=SearchPlatformAdapter)
    config = PlatformConfig(
        id=pid,
        display_name=pid.title(),
        backend=backend,
        priority=priority,
    )
    adapter.get_config.return_value = config
    if raises:
        adapter.search_sync.side_effect = raises
    elif results is not None:
        adapter.search_sync.return_value = results
    else:
        adapter.search_sync.return_value = []
    return adapter


# ============================================================================
# 1. TestInitialization
# ============================================================================


class TestInitialization:
    """Verify ChainedAdapter constructor, config, and priority sorting."""

    def test_creates_with_platform_id_and_display_name(self):
        """ChainedAdapter stores platform_id and display_name in config."""
        chain = ChainedAdapter("fb", "Facebook Marketplace", adapters=[])
        config = chain.get_config()
        assert config.id == "fb"
        assert config.display_name == "Facebook Marketplace"

    def test_backend_type_is_custom(self):
        """ChainedAdapter config has BackendType.CUSTOM."""
        chain = ChainedAdapter("test", "Test", adapters=[])
        assert chain.get_config().backend == BackendType.CUSTOM

    def test_sorts_adapters_by_priority_ascending(self):
        """Adapters are sorted: lower priority number = higher priority."""
        a_high = _make_mock_adapter("scrapling", BackendType.SCRAPLING, priority=1)
        a_low = _make_mock_adapter("serper", BackendType.SERPER, priority=10)
        a_mid = _make_mock_adapter("browser", BackendType.BROWSER, priority=5)

        chain = ChainedAdapter("fb", "FB", adapters=[a_low, a_high, a_mid])
        ordered = chain.get_adapters()

        assert ordered[0].get_config().priority == 1
        assert ordered[1].get_config().priority == 5
        assert ordered[2].get_config().priority == 10

    def test_default_circuit_breaker_created_if_none(self):
        """When no circuit_breaker passed, a default is created."""
        chain = ChainedAdapter("test", "Test", adapters=[])
        # Internal _cb should not be None
        assert chain._cb is not None

    def test_custom_circuit_breaker_used(self):
        """Custom PerPlatformCircuitBreaker is stored."""
        cb = PerPlatformCircuitBreaker(threshold=5, recovery_seconds=60)
        chain = ChainedAdapter("test", "Test", adapters=[], circuit_breaker=cb)
        assert chain._cb is cb


# ============================================================================
# 2. TestSearchFallbackChain
# ============================================================================


class TestSearchFallbackChain:
    """Verify fallback logic: first success wins, failures cascade."""

    def test_first_adapter_success_returns_immediately(self):
        """When first adapter returns results, second is not called."""
        results_a = _make_results(3, "scrapling")
        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=results_a, priority=0)
        a2 = _make_mock_adapter("serper", BackendType.SERPER, results=_make_results(1), priority=1)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2])
        out = chain.search_sync("test query")

        assert len(out) == 3
        assert out[0].platform == "scrapling"
        a1.search_sync.assert_called_once_with("test query", 20, 1)
        a2.search_sync.assert_not_called()

    def test_first_adapter_empty_tries_second(self):
        """Empty results from first adapter -> try second."""
        results_b = _make_results(2, "serper")
        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=[], priority=0)
        a2 = _make_mock_adapter("serper", BackendType.SERPER, results=results_b, priority=1)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2])
        out = chain.search_sync("iphone 15")

        assert len(out) == 2
        assert out[0].platform == "serper"

    def test_first_adapter_raises_exception_tries_second(self):
        """Exception from first adapter -> try second."""
        results_b = _make_results(5, "serper")
        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, raises=ConnectionError("Timeout"), priority=0)
        a2 = _make_mock_adapter("serper", BackendType.SERPER, results=results_b, priority=1)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2])
        out = chain.search_sync("laptop")

        assert len(out) == 5

    def test_all_adapters_fail_returns_empty(self):
        """All adapters raise -> return empty list."""
        a1 = _make_mock_adapter("a", BackendType.SCRAPLING, raises=RuntimeError("Blocked"), priority=0)
        a2 = _make_mock_adapter("b", BackendType.BROWSER, raises=TimeoutError("Timed out"), priority=1)
        a3 = _make_mock_adapter("c", BackendType.SERPER, raises=ValueError("API error"), priority=2)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3])
        assert chain.search_sync("query") == []

    def test_all_adapters_return_empty(self):
        """All adapters return [] -> final result is []."""
        a1 = _make_mock_adapter("a", BackendType.SCRAPLING, results=[], priority=0)
        a2 = _make_mock_adapter("b", BackendType.BROWSER, results=[], priority=1)
        a3 = _make_mock_adapter("c", BackendType.SERPER, results=[], priority=2)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3])
        assert chain.search_sync("nothing") == []
        a1.search_sync.assert_called_once()
        a2.search_sync.assert_called_once()
        a3.search_sync.assert_called_once()

    def test_first_two_fail_third_succeeds(self):
        """Skip two failing backends, use third."""
        results_c = _make_results(1, "serper")
        a1 = _make_mock_adapter("a", BackendType.SCRAPLING, raises=ConnectionError("fail"), priority=0)
        a2 = _make_mock_adapter("b", BackendType.BROWSER, raises=TimeoutError("fail"), priority=1)
        a3 = _make_mock_adapter("c", BackendType.SERPER, results=results_c, priority=2)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3])
        out = chain.search_sync("test")

        assert len(out) == 1
        assert out[0].platform == "serper"

    def test_mixed_exception_then_empty_then_success(self):
        """Exception, empty, then success."""
        results_c = _make_results(4, "serper")
        a1 = _make_mock_adapter("a", BackendType.SCRAPLING, raises=RuntimeError("Blocked"), priority=0)
        a2 = _make_mock_adapter("b", BackendType.BROWSER, results=[], priority=1)
        a3 = _make_mock_adapter("c", BackendType.SERPER, results=results_c, priority=2)

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3])
        out = chain.search_sync("mixed test")

        assert len(out) == 4

    def test_single_adapter_success(self):
        """Chain with one adapter: success."""
        results = _make_results(2, "only")
        a1 = _make_mock_adapter("only", BackendType.SERPER, results=results, priority=0)
        chain = ChainedAdapter("test", "Test", adapters=[a1])
        assert len(chain.search_sync("single")) == 2

    def test_single_adapter_failure(self):
        """Chain with one adapter: failure returns []."""
        a1 = _make_mock_adapter("only", BackendType.SERPER, raises=ConnectionError("down"), priority=0)
        chain = ChainedAdapter("test", "Test", adapters=[a1])
        assert chain.search_sync("single fail") == []

    def test_passes_max_results_and_page(self):
        """max_results and page are passed through."""
        results = _make_results(5, "test")
        a1 = _make_mock_adapter("a", BackendType.SERPER, results=results, priority=0)
        chain = ChainedAdapter("test", "Test", adapters=[a1])
        chain.search_sync("query", max_results=10, page=3)
        a1.search_sync.assert_called_once_with("query", 10, 3)


# ============================================================================
# 3. TestCircuitBreakerIntegration
# ============================================================================


class TestCircuitBreakerIntegration:
    """Verify circuit breaker integration with ChainedAdapter."""

    def test_skips_adapter_when_circuit_open(self):
        """Open circuit -> adapter skipped entirely."""
        cb = PerPlatformCircuitBreaker(threshold=2, recovery_seconds=300)
        results_b = _make_results(3, "serper")

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=_make_results(5), priority=0)
        a2 = _make_mock_adapter("serper", BackendType.SERPER, results=results_b, priority=1)

        # Trip the circuit
        cb.record_failure("fb_scrapling")
        cb.record_failure("fb_scrapling")

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2], circuit_breaker=cb)
        out = chain.search_sync("test")

        assert len(out) == 3
        a1.search_sync.assert_not_called()
        a2.search_sync.assert_called_once()

    def test_records_success_on_successful_adapter(self):
        """record_success called on successful search."""
        cb = MagicMock(spec=PerPlatformCircuitBreaker)
        cb.is_open.return_value = False

        results = _make_results(2, "serper")
        a1 = _make_mock_adapter("serper", BackendType.SERPER, results=results, priority=0)

        chain = ChainedAdapter("fb", "FB", adapters=[a1], circuit_breaker=cb)
        chain.search_sync("test")

        cb.record_success.assert_called_once_with("fb_serper")

    def test_records_failure_on_exception(self):
        """record_failure called on exception."""
        cb = MagicMock(spec=PerPlatformCircuitBreaker)
        cb.is_open.return_value = False

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, raises=RuntimeError("fail"), priority=0)

        chain = ChainedAdapter("fb", "FB", adapters=[a1], circuit_breaker=cb)
        chain.search_sync("test")

        cb.record_failure.assert_called_once_with("fb_scrapling")

    def test_backend_key_format(self):
        """backend_key is '{platform_id}_{backend.value}'."""
        cb = MagicMock(spec=PerPlatformCircuitBreaker)
        cb.is_open.return_value = False

        a1 = _make_mock_adapter("a", BackendType.CRAWL4AI, results=_make_results(1), priority=0)

        chain = ChainedAdapter("shopee", "Shopee", adapters=[a1], circuit_breaker=cb)
        chain.search_sync("test")

        cb.is_open.assert_any_call("shopee_crawl4ai")
        cb.record_success.assert_called_once_with("shopee_crawl4ai")

    def test_half_open_after_recovery(self):
        """After recovery period, circuit allows retry."""
        cb = PerPlatformCircuitBreaker(threshold=2, recovery_seconds=0.001)

        backend_key = "fb_scrapling"
        cb.record_failure(backend_key)
        cb.record_failure(backend_key)
        assert cb.is_open(backend_key) is True

        time.sleep(0.01)
        assert cb.is_open(backend_key) is False

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=_make_results(2, "scrapling"), priority=0)
        chain = ChainedAdapter("fb", "FB", adapters=[a1], circuit_breaker=cb)
        out = chain.search_sync("test")

        assert len(out) == 2
        a1.search_sync.assert_called_once()

    def test_circuit_open_for_first_closed_for_second(self):
        """First circuit open -> use second."""
        cb = PerPlatformCircuitBreaker(threshold=1, recovery_seconds=300)
        results_b = _make_results(3, "browser")

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=_make_results(5), priority=0)
        a2 = _make_mock_adapter("browser", BackendType.BROWSER, results=results_b, priority=1)

        cb.record_failure("fb_scrapling")

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2], circuit_breaker=cb)
        out = chain.search_sync("test")

        assert len(out) == 3
        a1.search_sync.assert_not_called()

    def test_all_circuits_open_returns_empty(self):
        """All circuits open -> no backends tried, returns []."""
        cb = PerPlatformCircuitBreaker(threshold=1, recovery_seconds=300)

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=_make_results(5), priority=0)
        a2 = _make_mock_adapter("browser", BackendType.BROWSER, results=_make_results(3), priority=1)
        a3 = _make_mock_adapter("serper", BackendType.SERPER, results=_make_results(2), priority=2)

        cb.record_failure("fb_scrapling")
        cb.record_failure("fb_browser")
        cb.record_failure("fb_serper")

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3], circuit_breaker=cb)
        assert chain.search_sync("test") == []
        a1.search_sync.assert_not_called()
        a2.search_sync.assert_not_called()
        a3.search_sync.assert_not_called()

    def test_mixed_circuits_open_and_closed(self):
        """Some circuits open, some closed."""
        cb = PerPlatformCircuitBreaker(threshold=1, recovery_seconds=300)
        results_b = _make_results(2, "browser")

        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, results=_make_results(5), priority=0)
        a2 = _make_mock_adapter("browser", BackendType.BROWSER, results=results_b, priority=1)
        a3 = _make_mock_adapter("serper", BackendType.SERPER, results=_make_results(1), priority=2)

        cb.record_failure("fb_scrapling")
        cb.record_failure("fb_serper")

        chain = ChainedAdapter("fb", "FB", adapters=[a1, a2, a3], circuit_breaker=cb)
        out = chain.search_sync("test")

        assert len(out) == 2
        a1.search_sync.assert_not_called()
        a2.search_sync.assert_called_once()
        a3.search_sync.assert_not_called()

    def test_record_failure_on_empty_results(self):
        """Sprint 195: record_failure IS called when adapter returns empty (soft failure)."""
        cb = MagicMock(spec=PerPlatformCircuitBreaker)
        cb.is_open.return_value = False

        a1 = _make_mock_adapter("serper", BackendType.SERPER, results=[], priority=0)

        chain = ChainedAdapter("fb", "FB", adapters=[a1], circuit_breaker=cb)
        chain.search_sync("test")

        cb.record_success.assert_not_called()
        cb.record_failure.assert_called_once()

    def test_empty_results_triggers_soft_failure(self):
        """Sprint 195: Empty results should trigger circuit breaker soft failure."""
        cb = MagicMock(spec=PerPlatformCircuitBreaker)
        cb.is_open.return_value = False

        a1 = _make_mock_adapter("a", BackendType.SERPER, results=[], priority=0)
        chain = ChainedAdapter("fb", "FB", adapters=[a1], circuit_breaker=cb)
        chain.search_sync("test")

        cb.record_failure.assert_called_once()


# ============================================================================
# 4. TestHelperMethods
# ============================================================================


class TestHelperMethods:
    """Verify helper methods and edge cases."""

    def test_get_adapter_count(self):
        """get_adapter_count() returns number of adapters."""
        adapters = [
            _make_mock_adapter("a", priority=0),
            _make_mock_adapter("b", priority=1),
            _make_mock_adapter("c", priority=2),
        ]
        chain = ChainedAdapter("test", "Test", adapters=adapters)
        assert chain.get_adapter_count() == 3

    def test_get_backend_keys(self):
        """get_backend_keys() returns formatted keys."""
        a1 = _make_mock_adapter("scrapling", BackendType.SCRAPLING, priority=0)
        a2 = _make_mock_adapter("browser", BackendType.BROWSER, priority=1)
        a3 = _make_mock_adapter("serper", BackendType.SERPER, priority=2)

        chain = ChainedAdapter("fb", "Facebook", adapters=[a1, a2, a3])
        keys = chain.get_backend_keys()

        assert keys == ["fb_scrapling", "fb_browser", "fb_serper"]

    def test_get_adapters_returns_copy(self):
        """get_adapters() returns a copy, not internal list."""
        a1 = _make_mock_adapter("a", BackendType.SERPER, priority=0)
        chain = ChainedAdapter("test", "Test", adapters=[a1])

        adapters = chain.get_adapters()
        adapters.append(_make_mock_adapter("b", BackendType.BROWSER))

        assert chain.get_adapter_count() == 1

    def test_zero_adapters_edge_case(self):
        """ChainedAdapter with 0 adapters returns empty."""
        chain = ChainedAdapter("empty", "Empty", adapters=[])

        assert chain.get_adapter_count() == 0
        assert chain.get_backend_keys() == []
        assert chain.search_sync("anything") == []

    def test_isinstance_search_platform_adapter(self):
        """ChainedAdapter is a SearchPlatformAdapter."""
        chain = ChainedAdapter("test", "Test", adapters=[])
        assert isinstance(chain, SearchPlatformAdapter)


# ============================================================================
# 5. TestDefaultToolDescription
# ============================================================================


class TestDefaultToolDescription:
    """Verify auto-generated tool_description_vi."""

    def test_default_tool_description_includes_display_name(self):
        """Default description includes display_name."""
        a1 = _make_mock_adapter("serper", BackendType.SERPER)
        chain = ChainedAdapter("shopee", "Shopee Vietnam", adapters=[a1])
        desc = chain.get_tool_description()
        assert "Shopee Vietnam" in desc
