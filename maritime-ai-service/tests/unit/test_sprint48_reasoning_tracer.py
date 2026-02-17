"""
Tests for Sprint 48: ReasoningTracer coverage.

Tests reasoning trace explainability including:
- StepContext dataclass
- ReasoningTracer init, start_step, end_step
- end_step without active step
- Auto-close on start_step
- record_correction
- add_step (direct)
- build_trace (confidence avg, override, auto-close)
- build_thinking_summary (empty, steps, with correction)
- merge_trace (after_first, prepend, append, correction inheritance)
- reset
- StepNames constants
- Factory function
"""

import pytest
from unittest.mock import MagicMock, patch


# ============================================================================
# StepContext
# ============================================================================


class TestStepContext:
    """Test StepContext dataclass."""

    def test_defaults(self):
        from app.engine.reasoning_tracer import StepContext
        sc = StepContext(step_name="test", description="Test step", start_time_ms=1000)
        assert sc.confidence is None
        assert sc.result is None
        assert sc.details is None


# ============================================================================
# ReasoningTracer init
# ============================================================================


class TestReasoningTracerInit:
    """Test ReasoningTracer initialization."""

    def test_init(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        assert tracer._steps == []
        assert tracer._current_step is None
        assert tracer._was_corrected is False
        assert tracer._correction_reason is None


# ============================================================================
# start_step / end_step
# ============================================================================


class TestStartEndStep:
    """Test step tracking."""

    def test_start_end_step(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.start_step("retrieval", "Retrieving documents")
        assert tracer._current_step is not None
        tracer.end_step(result="Found 5 docs", confidence=0.9)
        assert tracer._current_step is None
        assert len(tracer._steps) == 1
        assert tracer._steps[0].step_name == "retrieval"
        assert tracer._steps[0].confidence == 0.9

    def test_end_step_no_active(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.end_step(result="No step")  # Should not raise
        assert len(tracer._steps) == 0

    def test_auto_close_previous(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.start_step("step1", "First step")
        tracer.start_step("step2", "Second step")
        # step1 should be auto-closed
        assert tracer._steps[0].step_name == "step1"
        assert tracer._steps[0].result == "Auto-closed"
        assert tracer._current_step.step_name == "step2"

    def test_duration_recorded(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.start_step("test", "Test")
        tracer.end_step(result="Done")
        assert tracer._steps[0].duration_ms >= 0

    def test_end_step_with_details(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.start_step("test", "Test")
        tracer.end_step(result="Done", details={"key": "value"})
        assert tracer._steps[0].details == {"key": "value"}


# ============================================================================
# record_correction
# ============================================================================


class TestRecordCorrection:
    """Test correction recording."""

    def test_record(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.record_correction("Query too vague, rewriting")
        assert tracer._was_corrected is True
        assert tracer._correction_reason == "Query too vague, rewriting"


# ============================================================================
# add_step
# ============================================================================


class TestAddStep:
    """Test direct step addition."""

    def test_add_step(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("routing", "Route query", "RAG agent selected", confidence=0.95, duration_ms=50)
        assert len(tracer._steps) == 1
        assert tracer._steps[0].step_name == "routing"
        assert tracer._steps[0].duration_ms == 50


# ============================================================================
# build_trace
# ============================================================================


class TestBuildTrace:
    """Test trace building."""

    def test_empty_trace(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        trace = tracer.build_trace()
        assert trace.total_steps == 0
        assert trace.final_confidence == 0.8  # Default when no steps

    def test_confidence_average(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step 1", "Done", confidence=0.8)
        tracer.add_step("s2", "Step 2", "Done", confidence=0.6)
        trace = tracer.build_trace()
        assert abs(trace.final_confidence - 0.7) < 0.001

    def test_confidence_override(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step 1", "Done", confidence=0.5)
        trace = tracer.build_trace(final_confidence=0.99)
        assert trace.final_confidence == 0.99

    def test_auto_close_open_step(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.start_step("open", "Open step")
        trace = tracer.build_trace()
        assert trace.total_steps == 1
        assert tracer._steps[0].result == "Auto-closed"

    def test_total_duration(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "Done")
        trace = tracer.build_trace()
        assert trace.total_duration_ms >= 0

    def test_correction_info(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.record_correction("Rewritten for clarity")
        trace = tracer.build_trace()
        assert trace.was_corrected is True
        assert trace.correction_reason == "Rewritten for clarity"


# ============================================================================
# build_thinking_summary
# ============================================================================


class TestBuildThinkingSummary:
    """Test thinking summary generation."""

    def test_empty(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        assert tracer.build_thinking_summary() == ""

    def test_with_steps(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("retrieval", "Tìm kiếm tài liệu", "Tìm thấy 5 tài liệu", confidence=0.9)
        summary = tracer.build_thinking_summary()
        assert "Tìm kiếm tài liệu" in summary
        assert "Tìm thấy 5 tài liệu" in summary
        assert "90%" in summary

    def test_with_correction(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "Done")
        tracer.record_correction("Query was rewritten")
        summary = tracer.build_thinking_summary()
        assert "Query was rewritten" in summary


# ============================================================================
# merge_trace
# ============================================================================


class TestMergeTrace:
    """Test trace merging."""

    def _make_trace(self, steps_data):
        from app.models.schemas import ReasoningStep, ReasoningTrace
        steps = [
            ReasoningStep(step_name=s[0], description=s[1], result=s[2])
            for s in steps_data
        ]
        return ReasoningTrace(
            total_steps=len(steps),
            total_duration_ms=100,
            was_corrected=False,
            final_confidence=0.8,
            steps=steps
        )

    def test_after_first(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("routing", "Route", "RAG")
        tracer.add_step("quality", "Quality", "Pass")
        other = self._make_trace([("retrieval", "Retrieve", "5 docs"), ("grading", "Grade", "Good")])
        tracer.merge_trace(other, position="after_first")
        names = [s.step_name for s in tracer._steps]
        assert names == ["routing", "retrieval", "grading", "quality"]

    def test_prepend(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("quality", "Quality", "Pass")
        other = self._make_trace([("retrieval", "Retrieve", "5 docs")])
        tracer.merge_trace(other, position="prepend")
        assert tracer._steps[0].step_name == "retrieval"

    def test_append(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("routing", "Route", "RAG")
        other = self._make_trace([("verification", "Verify", "OK")])
        tracer.merge_trace(other, position="append")
        assert tracer._steps[-1].step_name == "verification"

    def test_none_trace(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "Done")
        tracer.merge_trace(None)
        assert len(tracer._steps) == 1

    def test_correction_inherited(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        from app.models.schemas import ReasoningTrace, ReasoningStep
        tracer = ReasoningTracer()
        # Must have at least 1 step — empty steps triggers early return
        other = ReasoningTrace(
            total_steps=1, total_duration_ms=0,
            was_corrected=True, correction_reason="Rewritten",
            final_confidence=0.5,
            steps=[ReasoningStep(step_name="s", description="d", result="r")]
        )
        tracer.merge_trace(other)
        assert tracer._was_corrected is True
        assert tracer._correction_reason == "Rewritten"


# ============================================================================
# reset
# ============================================================================


class TestReset:
    """Test tracer reset."""

    def test_reset(self):
        from app.engine.reasoning_tracer import ReasoningTracer
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "Done")
        tracer.record_correction("Rewritten")
        tracer.reset()
        assert tracer._steps == []
        assert tracer._was_corrected is False
        assert tracer._current_step is None


# ============================================================================
# StepNames & factory
# ============================================================================


class TestStepNamesAndFactory:
    """Test constants and factory."""

    def test_step_names(self):
        from app.engine.reasoning_tracer import StepNames
        assert StepNames.QUERY_ANALYSIS == "query_analysis"
        assert StepNames.RETRIEVAL == "retrieval"
        assert StepNames.ROUTING == "routing"

    def test_factory(self):
        from app.engine.reasoning_tracer import get_reasoning_tracer
        t1 = get_reasoning_tracer()
        t2 = get_reasoning_tracer()
        # Factory creates new instances each time (not singleton)
        assert t1 is not t2
