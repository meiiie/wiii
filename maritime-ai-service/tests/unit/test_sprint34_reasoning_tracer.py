"""
Tests for Sprint 34: ReasoningTracer — pure logic, no LLM.

Covers:
- StepContext dataclass
- start_step / end_step lifecycle
- add_step (direct)
- build_trace: step counting, confidence averaging, duration
- build_thinking_summary: prose generation
- merge_trace: position strategies
- record_correction
- reset
- StepNames constants
"""

import time
import pytest
from unittest.mock import patch

from app.engine.reasoning_tracer import (
    ReasoningTracer,
    StepContext,
    StepNames,
    get_reasoning_tracer,
)
from app.models.schemas import ReasoningStep, ReasoningTrace


# =============================================================================
# StepContext
# =============================================================================


class TestStepContext:
    def test_defaults(self):
        ctx = StepContext(step_name="test", description="desc", start_time_ms=1000)
        assert ctx.confidence is None
        assert ctx.result is None
        assert ctx.details is None


# =============================================================================
# StepNames constants
# =============================================================================


class TestStepNames:
    def test_core_names(self):
        assert StepNames.QUERY_ANALYSIS == "query_analysis"
        assert StepNames.RETRIEVAL == "retrieval"
        assert StepNames.GRADING == "grading"
        assert StepNames.GENERATION == "generation"
        assert StepNames.VERIFICATION == "verification"
        assert StepNames.ROUTING == "routing"


# =============================================================================
# start_step / end_step
# =============================================================================


class TestStartEndStep:
    def test_start_and_end(self):
        tracer = ReasoningTracer()
        tracer.start_step("test_step", "Test description")
        assert tracer._current_step is not None
        tracer.end_step(result="Done", confidence=0.9)
        assert tracer._current_step is None
        assert len(tracer._steps) == 1
        assert tracer._steps[0].step_name == "test_step"
        assert tracer._steps[0].confidence == 0.9

    def test_end_step_without_start(self):
        """end_step without active step should be no-op."""
        tracer = ReasoningTracer()
        tracer.end_step(result="orphan")
        assert len(tracer._steps) == 0

    def test_start_auto_closes_previous(self):
        """Starting a new step auto-closes any open step."""
        tracer = ReasoningTracer()
        tracer.start_step("step1", "First")
        tracer.start_step("step2", "Second")
        # step1 should be auto-closed
        assert len(tracer._steps) == 1
        assert tracer._steps[0].step_name == "step1"
        assert tracer._steps[0].result == "Auto-closed"
        # step2 is now current
        assert tracer._current_step.step_name == "step2"

    def test_duration_tracking(self):
        tracer = ReasoningTracer()
        tracer.start_step("slow", "Slow step")
        time.sleep(0.02)  # 20ms
        tracer.end_step(result="Done")
        assert tracer._steps[0].duration_ms >= 10  # At least some ms

    def test_end_step_with_details(self):
        tracer = ReasoningTracer()
        tracer.start_step("detailed", "Detailed step")
        tracer.end_step(result="OK", details={"key": "value"})
        assert tracer._steps[0].details == {"key": "value"}


# =============================================================================
# add_step (direct)
# =============================================================================


class TestAddStep:
    def test_add_complete_step(self):
        tracer = ReasoningTracer()
        tracer.add_step(
            step_name="direct",
            description="Direct step",
            result="Result",
            confidence=0.85,
            duration_ms=100,
        )
        assert len(tracer._steps) == 1
        assert tracer._steps[0].step_name == "direct"
        assert tracer._steps[0].duration_ms == 100

    def test_add_multiple_steps(self):
        tracer = ReasoningTracer()
        for i in range(5):
            tracer.add_step(f"step{i}", f"Step {i}", f"Result {i}")
        assert len(tracer._steps) == 5


# =============================================================================
# build_trace
# =============================================================================


class TestBuildTrace:
    def test_empty_trace(self):
        tracer = ReasoningTracer()
        trace = tracer.build_trace()
        assert isinstance(trace, ReasoningTrace)
        assert trace.total_steps == 0
        assert trace.final_confidence == 0.8  # Default when no steps

    def test_trace_with_steps(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step 1", "R1", confidence=0.9)
        tracer.add_step("s2", "Step 2", "R2", confidence=0.7)
        trace = tracer.build_trace()
        assert trace.total_steps == 2
        assert abs(trace.final_confidence - 0.8) < 1e-6  # avg(0.9, 0.7)

    def test_trace_override_confidence(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step 1", "R1", confidence=0.5)
        trace = tracer.build_trace(final_confidence=0.95)
        assert trace.final_confidence == 0.95

    def test_trace_auto_closes_open_step(self):
        tracer = ReasoningTracer()
        tracer.start_step("open", "Still open")
        trace = tracer.build_trace()
        assert trace.total_steps == 1
        assert trace.steps[0].result == "Auto-closed"

    def test_trace_duration(self):
        tracer = ReasoningTracer()
        time.sleep(0.01)
        trace = tracer.build_trace()
        assert trace.total_duration_ms >= 5

    def test_trace_correction_info(self):
        tracer = ReasoningTracer()
        tracer.record_correction("Query was ambiguous")
        trace = tracer.build_trace()
        assert trace.was_corrected is True
        assert trace.correction_reason == "Query was ambiguous"

    def test_trace_no_correction(self):
        tracer = ReasoningTracer()
        trace = tracer.build_trace()
        assert trace.was_corrected is False
        assert trace.correction_reason is None

    def test_confidence_avg_ignores_none(self):
        """Steps with None confidence should not affect average."""
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step 1", "R1", confidence=0.8)
        tracer.add_step("s2", "Step 2", "R2", confidence=None)
        tracer.add_step("s3", "Step 3", "R3", confidence=0.6)
        trace = tracer.build_trace()
        assert abs(trace.final_confidence - 0.7) < 1e-6  # avg(0.8, 0.6)


# =============================================================================
# build_thinking_summary
# =============================================================================


class TestBuildThinkingSummary:
    def test_empty_steps(self):
        tracer = ReasoningTracer()
        assert tracer.build_thinking_summary() == ""

    def test_single_step(self):
        tracer = ReasoningTracer()
        tracer.add_step("query", "Phân tích câu hỏi", "Câu hỏi về Điều 15")
        summary = tracer.build_thinking_summary()
        assert "Phân tích câu hỏi" in summary
        assert "Điều 15" in summary

    def test_step_with_confidence(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Test step", "Result", confidence=0.85)
        summary = tracer.build_thinking_summary()
        assert "85%" in summary

    def test_correction_note(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "Result")
        tracer.record_correction("Query rewritten for clarity")
        summary = tracer.build_thinking_summary()
        assert "Query rewritten for clarity" in summary

    def test_multiple_steps_numbered(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "First", "R1")
        tracer.add_step("s2", "Second", "R2")
        tracer.add_step("s3", "Third", "R3")
        summary = tracer.build_thinking_summary()
        assert "1." in summary
        assert "2." in summary
        assert "3." in summary


# =============================================================================
# merge_trace
# =============================================================================


class TestMergeTrace:
    def _make_trace(self, steps):
        return ReasoningTrace(
            total_steps=len(steps),
            total_duration_ms=100,
            steps=[
                ReasoningStep(step_name=s[0], description=s[1], result=s[2])
                for s in steps
            ],
        )

    def test_merge_after_first(self):
        tracer = ReasoningTracer()
        tracer.add_step("routing", "Route", "RAG")
        tracer.add_step("synthesis", "Synthesize", "Done")

        other = self._make_trace([
            ("retrieval", "Retrieve", "Found 5"),
            ("grading", "Grade", "3 relevant"),
        ])
        tracer.merge_trace(other, position="after_first")

        names = [s.step_name for s in tracer._steps]
        assert names == ["routing", "retrieval", "grading", "synthesis"]

    def test_merge_prepend(self):
        tracer = ReasoningTracer()
        tracer.add_step("final", "Final", "Done")

        other = self._make_trace([("prep", "Prepare", "Ready")])
        tracer.merge_trace(other, position="prepend")

        names = [s.step_name for s in tracer._steps]
        assert names == ["prep", "final"]

    def test_merge_append(self):
        tracer = ReasoningTracer()
        tracer.add_step("first", "First", "Done")

        other = self._make_trace([("last", "Last", "End")])
        tracer.merge_trace(other, position="append")

        names = [s.step_name for s in tracer._steps]
        assert names == ["first", "last"]

    def test_merge_none_trace(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "R")
        tracer.merge_trace(None)
        assert len(tracer._steps) == 1

    def test_merge_empty_trace(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "R")
        empty = self._make_trace([])
        tracer.merge_trace(empty)
        assert len(tracer._steps) == 1

    def test_merge_inherits_correction(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "R")

        other = ReasoningTrace(
            total_steps=1,
            total_duration_ms=50,
            was_corrected=True,
            correction_reason="Rewritten for precision",
            steps=[ReasoningStep(step_name="s2", description="S2", result="R2")],
        )
        tracer.merge_trace(other)
        assert tracer._was_corrected is True
        assert tracer._correction_reason == "Rewritten for precision"

    def test_merge_after_first_with_empty_steps(self):
        """after_first on empty tracer should append."""
        tracer = ReasoningTracer()
        other = self._make_trace([("s1", "Step", "R")])
        tracer.merge_trace(other, position="after_first")
        assert len(tracer._steps) == 1


# =============================================================================
# record_correction
# =============================================================================


class TestRecordCorrection:
    def test_record(self):
        tracer = ReasoningTracer()
        tracer.record_correction("Ambiguous query")
        assert tracer._was_corrected is True
        assert tracer._correction_reason == "Ambiguous query"


# =============================================================================
# reset
# =============================================================================


class TestReset:
    def test_reset_clears_state(self):
        tracer = ReasoningTracer()
        tracer.add_step("s1", "Step", "R", confidence=0.9)
        tracer.record_correction("Test")
        tracer.start_step("open", "Open")

        tracer.reset()
        assert len(tracer._steps) == 0
        assert tracer._current_step is None
        assert tracer._was_corrected is False
        assert tracer._correction_reason is None


# =============================================================================
# Factory function
# =============================================================================


class TestFactory:
    def test_get_reasoning_tracer_creates_new(self):
        t1 = get_reasoning_tracer()
        t2 = get_reasoning_tracer()
        assert isinstance(t1, ReasoningTracer)
        assert isinstance(t2, ReasoningTracer)
        # Factory creates new instances (not singleton)
        assert t1 is not t2
