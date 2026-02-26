"""
Sprint 191: Skill Metrics Tracker Unit Tests

Tests the SkillMetricsTracker: in-memory metrics cache with EMA latency,
success rate tracking, top performers, and DB flush queue.

40 tests across 6 categories:
1. Recording invocations (8 tests)
2. EMA latency calculation (5 tests)
3. Query API (8 tests)
4. DB flush queue (6 tests)
5. Summary statistics (5 tests)
6. Singleton & edge cases (8 tests)
"""

import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.engine.skills.skill_manifest_v2 import SkillMetrics
from app.engine.skills.skill_metrics import (
    SkillMetricsTracker,
    get_skill_metrics_tracker,
    _EMA_ALPHA,
)
import app.engine.skills.skill_metrics as sm_module


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after every test."""
    sm_module._tracker_instance = None
    yield
    sm_module._tracker_instance = None


@pytest.fixture
def tracker():
    """Fresh tracker instance."""
    return SkillMetricsTracker()


@pytest.fixture
def populated_tracker():
    """Tracker with some recorded invocations."""
    t = SkillMetricsTracker()
    t.record_invocation("tool:tool_search_shopee", success=True, latency_ms=200)
    t.record_invocation("tool:tool_search_shopee", success=True, latency_ms=300)
    t.record_invocation("tool:tool_search_shopee", success=False, latency_ms=500)
    t.record_invocation("tool:tool_knowledge_search", success=True, latency_ms=100)
    t.record_invocation("tool:tool_knowledge_search", success=True, latency_ms=150)
    t.record_invocation("domain:maritime:colregs", success=True, latency_ms=50)
    return t


# ============================================================================
# 1. Recording Invocations (8 tests)
# ============================================================================


class TestRecordInvocation:
    """Test invocation recording."""

    def test_records_first_invocation(self, tracker):
        """First invocation creates metrics entry."""
        tracker.record_invocation("tool:test", success=True, latency_ms=100)
        m = tracker.get_metrics("tool:test")
        assert m is not None
        assert m.total_invocations == 1
        assert m.successful_invocations == 1

    def test_records_failure(self, tracker):
        """Failed invocation increments total but not successful."""
        tracker.record_invocation("tool:test", success=False, latency_ms=500)
        m = tracker.get_metrics("tool:test")
        assert m.total_invocations == 1
        assert m.successful_invocations == 0

    def test_accumulates_invocations(self, tracker):
        """Multiple invocations accumulate correctly."""
        for _ in range(5):
            tracker.record_invocation("tool:test", success=True, latency_ms=100)
        tracker.record_invocation("tool:test", success=False, latency_ms=200)
        m = tracker.get_metrics("tool:test")
        assert m.total_invocations == 6
        assert m.successful_invocations == 5

    def test_records_tokens(self, tracker):
        """Token usage accumulates."""
        tracker.record_invocation("tool:test", success=True, tokens_used=100)
        tracker.record_invocation("tool:test", success=True, tokens_used=200)
        m = tracker.get_metrics("tool:test")
        assert m.total_tokens_used == 300

    def test_records_cost(self, tracker):
        """Cost accumulates."""
        tracker.record_invocation("tool:test", success=True, cost_usd=0.001)
        tracker.record_invocation("tool:test", success=True, cost_usd=0.002)
        m = tracker.get_metrics("tool:test")
        assert m.cost_estimate_usd == pytest.approx(0.003)

    def test_updates_last_used(self, tracker):
        """last_used is updated on each invocation."""
        tracker.record_invocation("tool:test", success=True)
        m = tracker.get_metrics("tool:test")
        assert m.last_used is not None
        assert isinstance(m.last_used, datetime)

    def test_multiple_skills_independent(self, tracker):
        """Different skills have independent metrics."""
        tracker.record_invocation("tool:a", success=True, latency_ms=100)
        tracker.record_invocation("tool:b", success=False, latency_ms=200)
        a = tracker.get_metrics("tool:a")
        b = tracker.get_metrics("tool:b")
        assert a.total_invocations == 1
        assert a.successful_invocations == 1
        assert b.total_invocations == 1
        assert b.successful_invocations == 0

    def test_records_with_metadata(self, tracker):
        """Records include query snippet and error message."""
        tracker.record_invocation(
            "tool:test", success=False,
            query_snippet="test query",
            error_message="Connection timeout",
            organization_id="org-123",
        )
        assert tracker.pending_count == 1


# ============================================================================
# 2. EMA Latency Calculation (5 tests)
# ============================================================================


class TestEMALatency:
    """Test Exponential Moving Average latency calculation."""

    def test_first_invocation_ema(self, tracker):
        """First invocation: EMA = α * latency + (1-α) * 0."""
        tracker.record_invocation("tool:test", success=True, latency_ms=1000)
        m = tracker.get_metrics("tool:test")
        expected = _EMA_ALPHA * 1000  # 0.3 * 1000 = 300
        assert m.avg_latency_ms == pytest.approx(expected)

    def test_second_invocation_ema(self, tracker):
        """Second invocation: EMA = α * current + (1-α) * prev."""
        tracker.record_invocation("tool:test", success=True, latency_ms=1000)
        tracker.record_invocation("tool:test", success=True, latency_ms=1000)
        m = tracker.get_metrics("tool:test")
        first_ema = _EMA_ALPHA * 1000  # 300
        second_ema = _EMA_ALPHA * 1000 + (1 - _EMA_ALPHA) * first_ema  # 300 + 210 = 510
        assert m.avg_latency_ms == pytest.approx(second_ema)

    def test_ema_converges(self, tracker):
        """EMA converges toward consistent latency."""
        for _ in range(20):
            tracker.record_invocation("tool:test", success=True, latency_ms=500)
        m = tracker.get_metrics("tool:test")
        # After many iterations, should converge close to 500
        assert abs(m.avg_latency_ms - 500) < 50

    def test_ema_responds_to_change(self, tracker):
        """EMA adjusts when latency changes."""
        for _ in range(10):
            tracker.record_invocation("tool:test", success=True, latency_ms=100)
        # Sudden spike
        tracker.record_invocation("tool:test", success=True, latency_ms=10000)
        m = tracker.get_metrics("tool:test")
        # Should be significantly higher than 100 now
        assert m.avg_latency_ms > 100

    def test_zero_latency_not_applied(self, tracker):
        """Latency of 0 is not applied (guard)."""
        tracker.record_invocation("tool:test", success=True, latency_ms=500)
        tracker.record_invocation("tool:test", success=True, latency_ms=0)
        m = tracker.get_metrics("tool:test")
        # Should keep previous EMA, not drop to 0
        assert m.avg_latency_ms > 0


# ============================================================================
# 3. Query API (8 tests)
# ============================================================================


class TestQueryAPI:
    """Test metrics query methods."""

    def test_get_metrics_existing(self, populated_tracker):
        """get_metrics returns metrics for tracked skill."""
        m = populated_tracker.get_metrics("tool:tool_search_shopee")
        assert m is not None
        assert m.total_invocations == 3

    def test_get_metrics_missing(self, tracker):
        """get_metrics returns None for untracked skill."""
        assert tracker.get_metrics("tool:nonexistent") is None

    def test_get_all_metrics(self, populated_tracker):
        """get_all_metrics returns copy of all metrics."""
        all_m = populated_tracker.get_all_metrics()
        assert len(all_m) == 3
        assert "tool:tool_search_shopee" in all_m
        assert "tool:tool_knowledge_search" in all_m
        assert "domain:maritime:colregs" in all_m

    def test_get_top_performers(self, populated_tracker):
        """get_top_performers ranks by success_rate * sqrt(invocations)."""
        top = populated_tracker.get_top_performers(n=3)
        assert len(top) == 3
        # tool_knowledge_search: 100% * sqrt(2) = 1.414
        # domain:maritime:colregs: 100% * sqrt(1) = 1.0
        # tool_search_shopee: 66% * sqrt(3) = 1.155
        assert top[0][0] == "tool:tool_knowledge_search"

    def test_get_top_performers_limit(self, populated_tracker):
        """get_top_performers respects limit."""
        top = populated_tracker.get_top_performers(n=1)
        assert len(top) == 1

    def test_get_slow_tools(self, tracker):
        """get_slow_tools returns tools above threshold."""
        tracker.record_invocation("tool:slow", success=True, latency_ms=10000)
        tracker.record_invocation("tool:fast", success=True, latency_ms=100)
        slow = tracker.get_slow_tools(threshold_ms=1000)
        assert len(slow) == 1
        assert slow[0][0] == "tool:slow"

    def test_get_slow_tools_empty(self, tracker):
        """get_slow_tools returns empty when all are fast."""
        tracker.record_invocation("tool:fast", success=True, latency_ms=100)
        assert tracker.get_slow_tools(threshold_ms=5000) == []

    def test_success_rate_from_metrics(self, populated_tracker):
        """success_rate property calculates from recorded data."""
        m = populated_tracker.get_metrics("tool:tool_search_shopee")
        assert m.success_rate == pytest.approx(2 / 3)
        m2 = populated_tracker.get_metrics("tool:tool_knowledge_search")
        assert m2.success_rate == pytest.approx(1.0)


# ============================================================================
# 4. DB Flush Queue (6 tests)
# ============================================================================


class TestDBFlush:
    """Test pending record queue and flush behavior."""

    def test_records_queued_for_flush(self, tracker):
        """Invocations are queued as pending records."""
        tracker.record_invocation("tool:test", success=True)
        assert tracker.pending_count == 1

    def test_multiple_records_queued(self, populated_tracker):
        """Multiple invocations queued."""
        assert populated_tracker.pending_count == 6

    def test_flush_clears_pending(self, tracker):
        """flush_to_db clears pending records."""
        tracker.record_invocation("tool:test", success=True)
        assert tracker.pending_count == 1
        # Mock the DB write to avoid actual connection
        tracker._write_records_to_db = MagicMock()
        flushed = tracker.flush_to_db()
        assert flushed == 1
        assert tracker.pending_count == 0

    def test_flush_updates_timestamp(self, tracker):
        """flush_to_db updates last_flush_time."""
        tracker.record_invocation("tool:test", success=True)
        tracker._write_records_to_db = MagicMock()
        assert tracker.last_flush_time == 0.0
        tracker.flush_to_db()
        assert tracker.last_flush_time > 0.0

    def test_flush_empty_returns_zero(self, tracker):
        """flush_to_db with no pending records returns 0."""
        flushed = tracker.flush_to_db()
        assert flushed == 0

    def test_flush_failure_requeues(self, tracker):
        """DB write failure re-queues records."""
        tracker.record_invocation("tool:test", success=True)
        tracker._write_records_to_db = MagicMock(side_effect=RuntimeError("DB error"))
        flushed = tracker.flush_to_db()
        assert flushed == 0
        assert tracker.pending_count == 1  # Re-queued


# ============================================================================
# 5. Summary Statistics (5 tests)
# ============================================================================


class TestSummary:
    """Test summary statistics."""

    def test_summary_empty(self, tracker):
        """Summary of empty tracker."""
        summary = tracker.get_summary()
        assert summary["total_skills_tracked"] == 0
        assert summary["total_invocations"] == 0

    def test_summary_with_data(self, populated_tracker):
        """Summary reflects tracked data."""
        summary = populated_tracker.get_summary()
        assert summary["total_skills_tracked"] == 3
        assert summary["total_invocations"] == 6
        assert summary["pending_flush_records"] == 6

    def test_summary_avg_success_rate(self, populated_tracker):
        """Average success rate across all skills."""
        summary = populated_tracker.get_summary()
        # shopee: 2/3, knowledge: 2/2, colregs: 1/1
        # avg = (0.667 + 1.0 + 1.0) / 3 ≈ 0.889
        assert summary["avg_success_rate"] == pytest.approx(0.889, abs=0.01)

    def test_summary_tokens_and_cost(self, tracker):
        """Summary tracks total tokens and cost."""
        tracker.record_invocation("tool:a", success=True, tokens_used=100, cost_usd=0.001)
        tracker.record_invocation("tool:b", success=True, tokens_used=200, cost_usd=0.002)
        summary = tracker.get_summary()
        assert summary["total_tokens_used"] == 300
        assert summary["total_cost_usd"] == pytest.approx(0.003)

    def test_summary_pending_count(self, tracker):
        """Summary includes pending flush count."""
        tracker.record_invocation("tool:a", success=True)
        tracker.record_invocation("tool:a", success=True)
        summary = tracker.get_summary()
        assert summary["pending_flush_records"] == 2


# ============================================================================
# 6. Singleton & Edge Cases (8 tests)
# ============================================================================


class TestSingletonAndEdgeCases:
    """Test singleton pattern, reset, thread safety, and edge cases."""

    def test_singleton_returns_same_instance(self):
        """get_skill_metrics_tracker() returns same object."""
        t1 = get_skill_metrics_tracker()
        t2 = get_skill_metrics_tracker()
        assert t1 is t2

    def test_singleton_reset(self):
        """Resetting module-level instance creates new tracker."""
        t1 = get_skill_metrics_tracker()
        sm_module._tracker_instance = None
        t2 = get_skill_metrics_tracker()
        assert t1 is not t2

    def test_thread_safe_creation(self):
        """Concurrent threads get same singleton."""
        instances = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            instances.append(get_skill_metrics_tracker())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 5
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first

    def test_reset_clears_all(self, tracker):
        """reset() clears metrics and pending records."""
        tracker.record_invocation("tool:a", success=True, latency_ms=100)
        tracker.record_invocation("tool:b", success=False, latency_ms=200)
        assert len(tracker.get_all_metrics()) == 2
        assert tracker.pending_count == 2

        tracker.reset()
        assert len(tracker.get_all_metrics()) == 0
        assert tracker.pending_count == 0
        assert tracker.last_flush_time == 0.0

    def test_infer_skill_type_tool(self):
        """_infer_skill_type correctly identifies tool prefix."""
        assert SkillMetricsTracker._infer_skill_type("tool:test") == "tool"

    def test_infer_skill_type_domain(self):
        """_infer_skill_type correctly identifies domain prefix."""
        assert SkillMetricsTracker._infer_skill_type("domain:maritime:colregs") == "domain_knowledge"

    def test_infer_skill_type_living(self):
        """_infer_skill_type correctly identifies living prefix."""
        assert SkillMetricsTracker._infer_skill_type("living:skill_name") == "living_agent"

    def test_infer_skill_type_unknown(self):
        """_infer_skill_type returns 'unknown' for unrecognized prefix."""
        assert SkillMetricsTracker._infer_skill_type("random:thing") == "unknown"
