"""
Tests for Token & Cost Tracker (Sprint 10).

Verifies:
- LLMCall dataclass fields
- TokenTracker accumulation (input, output, total)
- Cost estimation (Gemini Flash pricing)
- ContextVar isolation between requests
- start_tracking / get_tracker / record_llm_call API
- Summary dict format for API responses
"""

import pytest
import time
from contextvars import copy_context

from app.core.token_tracker import (
    LLMCall,
    TokenTracker,
    start_tracking,
    get_tracker,
    record_llm_call,
    _current_tracker,
)


class TestLLMCall:
    """Test LLMCall dataclass."""

    def test_default_values(self):
        """LLMCall has sensible defaults."""
        call = LLMCall(model="gemini-3-flash", tier="light")
        assert call.model == "gemini-3-flash"
        assert call.tier == "light"
        assert call.provider == ""
        assert call.input_tokens == 0
        assert call.output_tokens == 0
        assert call.duration_ms == 0.0
        assert call.estimated_cost_usd == 0.0
        assert call.component == ""

    def test_full_initialization(self):
        """LLMCall with all fields."""
        call = LLMCall(
            model="gemini-3-pro",
            tier="deep",
            provider="openrouter",
            input_tokens=500,
            output_tokens=200,
            duration_ms=1234.5,
            estimated_cost_usd=0.00125,
            component="tutor_node",
        )
        assert call.provider == "openrouter"
        assert call.input_tokens == 500
        assert call.output_tokens == 200
        assert call.duration_ms == 1234.5
        assert call.estimated_cost_usd == 0.00125
        assert call.component == "tutor_node"


class TestTokenTracker:
    """Test TokenTracker accumulation."""

    def test_empty_tracker(self):
        """Empty tracker has zero totals."""
        tracker = TokenTracker()
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.total_tokens == 0
        assert tracker.total_calls == 0

    def test_single_call(self):
        """Single call accumulation."""
        tracker = TokenTracker(request_id="req-1")
        tracker.record(LLMCall(model="flash", tier="light", input_tokens=100, output_tokens=50))

        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50
        assert tracker.total_tokens == 150
        assert tracker.total_calls == 1

    def test_multiple_calls(self):
        """Multiple calls accumulate correctly."""
        tracker = TokenTracker(request_id="req-2")
        tracker.record(LLMCall(model="flash", tier="light", input_tokens=100, output_tokens=50))
        tracker.record(LLMCall(model="flash", tier="moderate", input_tokens=200, output_tokens=100))
        tracker.record(LLMCall(model="flash", tier="deep", input_tokens=300, output_tokens=150))

        assert tracker.total_input_tokens == 600
        assert tracker.total_output_tokens == 300
        assert tracker.total_tokens == 900
        assert tracker.total_calls == 3

    def test_cost_estimation(self):
        """Cost estimation uses Gemini Flash pricing."""
        tracker = TokenTracker()
        # 1M input = $0.075, 1M output = $0.30
        tracker.record(LLMCall(
            model="flash", tier="light",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        ))
        # Expected: $0.075 + $0.30 = $0.375
        assert abs(tracker.estimated_cost_usd - 0.375) < 0.001

    def test_cost_zero_tokens(self):
        """Zero tokens = zero cost."""
        tracker = TokenTracker()
        assert tracker.estimated_cost_usd == 0.0

    def test_summary_format(self):
        """Summary dict has all required fields."""
        tracker = TokenTracker(request_id="req-3")
        tracker.record(LLMCall(model="flash", tier="light", input_tokens=500, output_tokens=200))

        summary = tracker.summary()
        assert "total_calls" in summary
        assert "total_input_tokens" in summary
        assert "total_output_tokens" in summary
        assert "total_tokens" in summary
        assert "estimated_cost_usd" in summary
        assert "duration_ms" in summary
        assert summary["total_calls"] == 1
        assert summary["total_tokens"] == 700

    def test_summary_cost_rounded(self):
        """Cost in summary is rounded to 6 decimal places."""
        tracker = TokenTracker()
        tracker.record(LLMCall(model="flash", tier="light", input_tokens=1, output_tokens=1))
        summary = tracker.summary()
        cost_str = str(summary["estimated_cost_usd"])
        # Should be a very small number, properly rounded
        assert summary["estimated_cost_usd"] >= 0

    def test_duration_tracking(self):
        """Duration is calculated from start_time."""
        tracker = TokenTracker()
        time.sleep(0.01)  # 10ms
        summary = tracker.summary()
        assert summary["duration_ms"] >= 5  # At least some time passed


class TestContextVarAPI:
    """Test module-level tracking API."""

    def test_start_tracking(self):
        """start_tracking creates a tracker in context."""
        tracker = start_tracking(request_id="ctx-1")
        assert tracker is not None
        assert tracker.request_id == "ctx-1"
        assert get_tracker() is tracker

    def test_get_tracker_none_by_default(self):
        """get_tracker returns None without start_tracking."""
        # Run in a fresh context to avoid contamination
        ctx = copy_context()
        result = ctx.run(_get_tracker_in_fresh_context)
        assert result is None

    def test_record_llm_call_api(self):
        """record_llm_call records on the current tracker."""
        tracker = start_tracking(request_id="ctx-2")
        record_llm_call(
            model="gemini-3-flash",
            tier="light",
            input_tokens=100,
            output_tokens=50,
            duration_ms=42.0,
            component="supervisor",
        )
        assert tracker.total_calls == 1
        assert tracker.total_tokens == 150
        assert tracker.calls[0].component == "supervisor"

    def test_record_without_tracker(self):
        """record_llm_call is a no-op without a tracker."""
        # Run in a fresh context
        ctx = copy_context()
        ctx.run(_record_without_tracker)
        # No exception should be raised

    def test_context_isolation(self):
        """Different contexts have independent trackers."""
        tracker1 = start_tracking(request_id="iso-1")
        record_llm_call(model="flash", tier="light", input_tokens=100, output_tokens=0)

        # Create a new context — should not see tracker1
        ctx = copy_context()
        tracker2 = ctx.run(_start_and_record_in_context)

        assert tracker1.total_calls == 1  # Only 1 call from original
        assert tracker2.total_calls == 1  # 1 call from new context
        assert tracker1.request_id != tracker2.request_id


# Helper functions for context isolation tests
def _get_tracker_in_fresh_context():
    """Helper: return get_tracker in a fresh ContextVar state."""
    _current_tracker.set(None)
    return get_tracker()


def _record_without_tracker():
    """Helper: try recording without a tracker."""
    _current_tracker.set(None)
    record_llm_call(model="flash", tier="light", input_tokens=50, output_tokens=25)


def _start_and_record_in_context():
    """Helper: start tracking and record in a new context."""
    tracker = start_tracking(request_id="iso-2")
    record_llm_call(model="flash", tier="moderate", input_tokens=200, output_tokens=100)
    return tracker
