"""
Tests for Sprint 54: TutorAgent coverage.

Tests the teaching state machine:
- TeachingPhase, AnswerEvaluation enums
- TeachingState (score, has_mastery, is_struggling)
- TutorAgent session lifecycle (start → intro → explanation → assessment → complete)
- Answer checking, error responses, mastery/struggling paths
- MaritimeDocumentParser (via rag_agent, but defined alongside tutor)
"""

import pytest
from datetime import datetime, timezone

from app.engine.tutor.tutor_agent import (
    TeachingPhase,
    AnswerEvaluation,
    TeachingState,
    TutorResponse,
    TutorAgent,
)
from app.models.schemas import utc_now


# ============================================================================
# Helpers
# ============================================================================


def _make_state(topic="solas", **overrides):
    """Create a TeachingState with overrides."""
    defaults = dict(topic=topic)
    defaults.update(overrides)
    return TeachingState(**defaults)


# ============================================================================
# Enums
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_teaching_phases(self):
        assert TeachingPhase.INTRODUCTION == "INTRODUCTION"
        assert TeachingPhase.EXPLANATION == "EXPLANATION"
        assert TeachingPhase.ASSESSMENT == "ASSESSMENT"
        assert TeachingPhase.COMPLETED == "COMPLETED"

    def test_answer_evaluation(self):
        assert AnswerEvaluation.CORRECT == "CORRECT"
        assert AnswerEvaluation.INCORRECT == "INCORRECT"
        assert AnswerEvaluation.PARTIAL == "PARTIAL"


# ============================================================================
# _utc_now
# ============================================================================


class TestUtcNow:
    """Test UTC time helper."""

    def test_returns_aware_datetime(self):
        result = utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None


# ============================================================================
# TeachingState
# ============================================================================


class TestTeachingState:
    """Test TeachingState model."""

    def test_defaults(self):
        state = _make_state()
        assert state.topic == "solas"
        assert state.current_phase == TeachingPhase.INTRODUCTION
        assert state.questions_asked == 0
        assert state.correct_answers == 0
        assert state.hints_given == 0
        assert state.current_question is None
        assert state.current_correct_answer is None
        assert state.awaiting_answer is False
        assert state.session_id  # auto-generated UUID

    def test_score_no_questions(self):
        state = _make_state()
        assert state.score == 0.0

    def test_score_calculation(self):
        state = _make_state(questions_asked=4, correct_answers=3)
        assert state.score == 75.0

    def test_score_100_percent(self):
        state = _make_state(questions_asked=3, correct_answers=3)
        assert state.score == 100.0

    def test_has_mastery_true(self):
        state = _make_state(questions_asked=3, correct_answers=3)
        assert state.has_mastery() is True

    def test_has_mastery_80_percent(self):
        state = _make_state(questions_asked=5, correct_answers=4)
        assert state.has_mastery() is True

    def test_has_mastery_false_low_score(self):
        state = _make_state(questions_asked=3, correct_answers=2)
        assert state.has_mastery() is False  # 66% < 80%

    def test_has_mastery_false_too_few_questions(self):
        state = _make_state(questions_asked=2, correct_answers=2)
        assert state.has_mastery() is False  # < 3 questions

    def test_is_struggling_true(self):
        state = _make_state(questions_asked=4, correct_answers=1)
        assert state.is_struggling() is True  # 25% < 50%

    def test_is_struggling_false_good_score(self):
        state = _make_state(questions_asked=3, correct_answers=2)
        assert state.is_struggling() is False  # 66% >= 50%

    def test_is_struggling_false_too_few_questions(self):
        state = _make_state(questions_asked=2, correct_answers=0)
        assert state.is_struggling() is False  # < 3 questions


# ============================================================================
# TutorResponse
# ============================================================================


class TestTutorResponse:
    """Test TutorResponse dataclass."""

    def test_defaults(self):
        state = _make_state()
        resp = TutorResponse(content="Hello", phase=TeachingPhase.INTRODUCTION, state=state)
        assert resp.hint_provided is False
        assert resp.assessment_complete is False
        assert resp.mastery_achieved is False

    def test_with_flags(self):
        state = _make_state()
        resp = TutorResponse(
            content="Done", phase=TeachingPhase.COMPLETED, state=state,
            assessment_complete=True, mastery_achieved=True
        )
        assert resp.assessment_complete is True
        assert resp.mastery_achieved is True


# ============================================================================
# TutorAgent — Session Lifecycle
# ============================================================================


class TestTutorAgentStartSession:
    """Test session creation."""

    def test_start_session(self):
        agent = TutorAgent()
        resp = agent.start_session("solas", "user1")

        assert resp.phase == TeachingPhase.INTRODUCTION
        assert "SOLAS" in resp.content
        assert resp.state.topic == "solas"
        assert resp.state.current_phase == TeachingPhase.INTRODUCTION

    def test_start_session_stores_state(self):
        agent = TutorAgent()
        agent.start_session("colregs", "user1")
        session = agent.get_session("user1_colregs")
        assert session is not None
        assert session.topic == "colregs"

    def test_start_session_custom_topic(self):
        agent = TutorAgent()
        resp = agent.start_session("fire_safety", "user2")
        assert resp.phase == TeachingPhase.INTRODUCTION
        assert "FIRE_SAFETY" in resp.content


class TestTutorAgentProcessResponse:
    """Test response processing through phases."""

    def test_introduction_to_explanation(self):
        agent = TutorAgent()
        agent.start_session("solas", "user1")

        resp = agent.process_response("ready", "user1_solas")
        assert resp.phase == TeachingPhase.EXPLANATION
        assert resp.state.current_phase == TeachingPhase.EXPLANATION

    def test_explanation_to_assessment(self):
        agent = TutorAgent()
        agent.start_session("solas", "user1")
        agent.process_response("ready", "user1_solas")  # → EXPLANATION

        resp = agent.process_response("ready", "user1_solas")  # → ASSESSMENT
        assert resp.phase == TeachingPhase.ASSESSMENT
        assert resp.state.awaiting_answer is True
        assert "Question 1" in resp.content

    def test_session_not_found(self):
        agent = TutorAgent()
        resp = agent.process_response("hello", "nonexistent")
        assert "Error" in resp.content
        assert resp.state.topic == "unknown"

    def test_completed_session_response(self):
        agent = TutorAgent()
        agent.start_session("solas", "user1")
        session = agent.get_session("user1_solas")
        session.current_phase = TeachingPhase.COMPLETED

        resp = agent.process_response("hello", "user1_solas")
        assert resp.phase == TeachingPhase.COMPLETED
        assert resp.assessment_complete is True
        assert "already completed" in resp.content


class TestTutorAgentAssessment:
    """Test assessment phase logic."""

    def _setup_assessment(self):
        """Set up agent in assessment phase."""
        agent = TutorAgent()
        agent.start_session("solas", "user1")
        agent.process_response("ready", "user1_solas")  # → EXPLANATION
        agent.process_response("ready", "user1_solas")  # → ASSESSMENT
        return agent

    def test_correct_answer(self):
        agent = self._setup_assessment()
        # Q1: "What does SOLAS stand for?" → "Safety of Life at Sea"
        resp = agent.process_response("Safety of Life at Sea", "user1_solas")
        state = agent.get_session("user1_solas")
        assert state.correct_answers == 1
        assert state.questions_asked == 1

    def test_incorrect_answer(self):
        agent = self._setup_assessment()
        resp = agent.process_response("wrong answer", "user1_solas")
        state = agent.get_session("user1_solas")
        assert state.correct_answers == 0
        assert state.questions_asked == 1
        assert state.hints_given == 1

    def test_partial_answer_contains(self):
        agent = self._setup_assessment()
        # "Safety of Life at Sea" contains "safety of life"
        resp = agent.process_response("It's about safety of life at sea", "user1_solas")
        state = agent.get_session("user1_solas")
        assert state.correct_answers == 1  # Contains correct answer

    def test_full_assessment_flow(self):
        agent = self._setup_assessment()
        # Answer all 3 SOLAS questions correctly
        agent.process_response("Safety of Life at Sea", "user1_solas")
        agent.process_response("1914", "user1_solas")
        # Q3 triggers completion after 3 questions if mastery
        resp = agent.process_response("maritime safety", "user1_solas")

        state = agent.get_session("user1_solas")
        assert state.questions_asked == 3
        assert state.correct_answers == 3
        assert state.has_mastery() is True
        assert resp.phase == TeachingPhase.COMPLETED
        assert resp.mastery_achieved is True

    def test_assessment_struggling(self):
        agent = self._setup_assessment()
        # Answer all 3 wrong
        agent.process_response("wrong", "user1_solas")
        agent.process_response("wrong", "user1_solas")
        agent.process_response("wrong", "user1_solas")

        state = agent.get_session("user1_solas")
        assert state.questions_asked == 3
        assert state.correct_answers == 0
        assert state.is_struggling() is True

    def test_not_awaiting_answer_asks_next(self):
        agent = self._setup_assessment()
        state = agent.get_session("user1_solas")
        state.awaiting_answer = False

        resp = agent.process_response("test", "user1_solas")
        # Should ask next question since not awaiting
        assert state.awaiting_answer is True


# ============================================================================
# TutorAgent — Check Answer
# ============================================================================


class TestCheckAnswer:
    """Test answer checking logic."""

    def test_exact_match(self):
        agent = TutorAgent()
        assert agent._check_answer("Safety of Life at Sea", "Safety of Life at Sea") is True

    def test_case_insensitive(self):
        agent = TutorAgent()
        assert agent._check_answer("safety of life at sea", "Safety of Life at Sea") is True

    def test_contains_match(self):
        agent = TutorAgent()
        assert agent._check_answer("I think it's red", "red") is True

    def test_reverse_contains(self):
        agent = TutorAgent()
        assert agent._check_answer("red", "The port side light is red") is True

    def test_no_match(self):
        agent = TutorAgent()
        assert agent._check_answer("blue", "red") is False

    def test_whitespace_handling(self):
        agent = TutorAgent()
        assert agent._check_answer("  red  ", "red") is True


# ============================================================================
# TutorAgent — Generate Introduction/Explanation
# ============================================================================


class TestGenerateContent:
    """Test content generation methods."""

    def test_introduction_contains_topic(self):
        agent = TutorAgent()
        intro = agent._generate_introduction("colregs")
        assert "COLREGS" in intro
        assert "Ready to begin" in intro

    def test_explanation_solas(self):
        agent = TutorAgent()
        exp = agent._generate_explanation("solas")
        assert "Safety of Life at Sea" in exp
        assert "Chapter" in exp

    def test_explanation_colregs(self):
        agent = TutorAgent()
        exp = agent._generate_explanation("colregs")
        assert "Collision Regulations" in exp
        assert "41 rules" in exp

    def test_explanation_unknown_topic(self):
        agent = TutorAgent()
        exp = agent._generate_explanation("unknown_topic")
        assert "Explanation for unknown_topic" in exp

    def test_colregs_assessment(self):
        """Test assessment with COLREGs questions."""
        agent = TutorAgent()
        agent.start_session("colregs", "u1")
        agent.process_response("ready", "u1_colregs")  # → EXPLANATION
        agent.process_response("ready", "u1_colregs")  # → ASSESSMENT

        state = agent.get_session("u1_colregs")
        assert state.current_question == "What does COLREGs stand for?"

    def test_unknown_topic_falls_back_to_solas_questions(self):
        """Unknown topic uses SOLAS questions as fallback."""
        agent = TutorAgent()
        agent.start_session("unknown", "u1")
        agent.process_response("ready", "u1_unknown")  # → EXPLANATION
        agent.process_response("ready", "u1_unknown")  # → ASSESSMENT

        state = agent.get_session("u1_unknown")
        # Should get SOLAS questions as default
        assert state.current_question == "What does SOLAS stand for?"


# ============================================================================
# TutorAgent — Get Session
# ============================================================================


class TestGetSession:
    """Test session retrieval."""

    def test_existing_session(self):
        agent = TutorAgent()
        agent.start_session("solas", "u1")
        assert agent.get_session("u1_solas") is not None

    def test_nonexistent_session(self):
        agent = TutorAgent()
        assert agent.get_session("nonexistent") is None
