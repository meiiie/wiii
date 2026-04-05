"""
Tests for Sprint 27: Token tracking integration with LLM pool.

Covers:
- TokenTrackingCallback class
- TokenTrackingCallback.on_llm_end extracts token usage
- LLMPool._attach_tracking_callback method
- Integration: callback records to per-request tracker
"""

import pytest
from unittest.mock import MagicMock, patch
from contextvars import copy_context

from app.core.token_tracker import (
    TokenTracker,
    TokenTrackingCallback,
    start_tracking,
    get_tracker,
    record_llm_call,
    _current_tracker,
)


# =============================================================================
# TokenTrackingCallback — Standalone
# =============================================================================

class TestTokenTrackingCallback:
    """Test the new LangChain callback handler."""

    def test_callback_instantiation(self):
        """Should create with tier name."""
        cb = TokenTrackingCallback(tier="moderate")
        assert cb.tier == "moderate"

    def test_on_llm_end_no_tracker(self):
        """Should not error when no tracker is active."""
        cb = TokenTrackingCallback(tier="deep")

        # Reset tracker
        _current_tracker.set(None)

        mock_response = MagicMock()
        mock_response.generations = []

        # Should not raise
        cb.on_llm_end(mock_response)

    def test_on_llm_end_records_tokens_from_usage_metadata(self):
        """Should extract tokens from message.usage_metadata dict."""
        cb = TokenTrackingCallback(tier="moderate")

        tracker = start_tracking("test-req")

        mock_msg = MagicMock()
        mock_msg.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
        }
        mock_msg.response_metadata = {"model_name": "gemini-3.1-flash-lite-preview"}

        mock_gen = MagicMock()
        mock_gen.message = mock_msg

        mock_response = MagicMock()
        mock_response.generations = [[mock_gen]]
        mock_response.llm_output = None

        cb.on_llm_end(mock_response)

        assert tracker.total_calls == 1
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50

        # Cleanup
        _current_tracker.set(None)

    def test_on_llm_end_records_tokens_from_llm_output(self):
        """Should fallback to llm_output dict for token usage."""
        cb = TokenTrackingCallback(tier="light")

        tracker = start_tracking("test-req-2")

        mock_response = MagicMock()
        mock_response.generations = [[]]  # Empty generations
        mock_response.llm_output = {
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 80,
            },
            "model_name": "gpt-4o",
        }

        cb.on_llm_end(mock_response)

        assert tracker.total_calls == 1
        assert tracker.total_input_tokens == 200
        assert tracker.total_output_tokens == 80

        # Cleanup
        _current_tracker.set(None)

    def test_on_llm_end_infers_provider_from_prefixed_tier(self):
        """Provider-prefixed tracking tiers should normalize into provider+tier."""
        cb = TokenTrackingCallback(tier="openrouter_light")

        tracker = start_tracking("test-req-provider")

        mock_response = MagicMock()
        mock_response.generations = [[]]
        mock_response.llm_output = {
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 15,
            },
            "model_name": "qwen/qwen3.6-plus:free",
        }

        cb.on_llm_end(mock_response)

        assert tracker.total_calls == 1
        assert tracker.calls[0].provider == "openrouter"
        assert tracker.calls[0].tier == "light"

        _current_tracker.set(None)

    def test_on_llm_end_ignores_zero_tokens(self):
        """Should not record a call when both input and output tokens are 0."""
        cb = TokenTrackingCallback(tier="light")

        tracker = start_tracking("test-req-3")

        mock_response = MagicMock()
        mock_response.generations = []
        mock_response.llm_output = None

        cb.on_llm_end(mock_response)

        assert tracker.total_calls == 0

        # Cleanup
        _current_tracker.set(None)

    def test_on_llm_end_handles_exception_gracefully(self):
        """Should catch internal errors without raising."""
        cb = TokenTrackingCallback(tier="deep")

        tracker = start_tracking("test-req-4")

        # Pass something that will cause an error during extraction
        cb.on_llm_end(None)

        # Should not have recorded anything
        assert tracker.total_calls == 0

        # Cleanup
        _current_tracker.set(None)


# =============================================================================
# TokenTrackingCallback with attribute-based usage_metadata
# =============================================================================

class TestTokenTrackingCallbackAttrMeta:
    """Test extraction from attribute-based usage_metadata (Gemini style)."""

    def test_extracts_from_attr_based_metadata(self):
        """Gemini returns usage_metadata with attributes, not dict."""
        cb = TokenTrackingCallback(tier="deep")

        tracker = start_tracking("test-attr")

        mock_meta = MagicMock()
        mock_meta.input_tokens = 150
        mock_meta.output_tokens = 60

        mock_msg = MagicMock()
        mock_msg.usage_metadata = mock_meta
        mock_msg.response_metadata = {"model_name": "gemini-3.1-flash-lite-preview"}

        # Make isinstance check work: not a dict
        type(mock_meta).__contains__ = MagicMock(side_effect=TypeError)

        mock_gen = MagicMock()
        mock_gen.message = mock_msg

        mock_response = MagicMock()
        mock_response.generations = [[mock_gen]]
        mock_response.llm_output = None

        cb.on_llm_end(mock_response)

        assert tracker.total_input_tokens == 150
        assert tracker.total_output_tokens == 60

        _current_tracker.set(None)


# =============================================================================
# LLMPool._attach_tracking_callback
# =============================================================================

class TestLLMPoolTrackingIntegration:
    """Test that LLMPool attaches tracking callback to LLM instances."""

    def test_attach_tracking_callback_method_exists(self):
        """LLMPool should have _attach_tracking_callback class method."""
        from app.engine.llm_pool import LLMPool
        assert hasattr(LLMPool, "_attach_tracking_callback")
        assert callable(LLMPool._attach_tracking_callback)

    def test_attach_adds_callback_to_llm(self):
        """Should add TokenTrackingCallback to llm.callbacks."""
        from app.engine.llm_pool import LLMPool

        mock_llm = MagicMock()
        mock_llm.callbacks = None

        LLMPool._attach_tracking_callback(mock_llm, "moderate")

        assert mock_llm.callbacks is not None
        assert len(mock_llm.callbacks) == 1
        assert isinstance(mock_llm.callbacks[0], TokenTrackingCallback)
        assert mock_llm.callbacks[0].tier == "moderate"

    def test_attach_appends_to_existing_callbacks(self):
        """Should append to existing callbacks list."""
        from app.engine.llm_pool import LLMPool

        existing_callback = MagicMock()
        mock_llm = MagicMock()
        mock_llm.callbacks = [existing_callback]

        LLMPool._attach_tracking_callback(mock_llm, "deep")

        assert len(mock_llm.callbacks) == 2
        assert mock_llm.callbacks[0] is existing_callback
        assert isinstance(mock_llm.callbacks[1], TokenTrackingCallback)


# =============================================================================
# TokenTracker — Summary integration
# =============================================================================

class TestTokenTrackerSummary:
    """Test existing tracker functionality with new callback records."""

    def test_summary_after_multiple_calls(self):
        """Summary should aggregate all recorded calls."""
        tracker = start_tracking("req-summary")

        record_llm_call(
            model="gemini-3.1-flash-lite-preview",
            tier="moderate",
            input_tokens=100,
            output_tokens=50,
        )
        record_llm_call(
            model="gemini-3.1-flash-lite-preview",
            tier="light",
            input_tokens=30,
            output_tokens=15,
        )

        summary = tracker.summary()

        assert summary["total_calls"] == 2
        assert summary["total_input_tokens"] == 130
        assert summary["total_output_tokens"] == 65
        assert summary["total_tokens"] == 195
        assert "estimated_cost_usd" in summary
        assert "duration_ms" in summary

        _current_tracker.set(None)
