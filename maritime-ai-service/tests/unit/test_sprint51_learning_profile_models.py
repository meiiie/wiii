"""
Tests for Sprint 51: LearningProfile models coverage.

Tests learning profile domain models including:
- LearnerLevel enum
- LearningStyle enum
- Assessment (creation, validator)
- LearningProfile (defaults, add_assessment, get_topic_average_score, is_topic_weak, is_topic_mastered)
- create_default_profile
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.learning_profile import (
    LearnerLevel,
    LearningStyle,
    Assessment,
    LearningProfile,
    create_default_profile,
)
from app.models.schemas import utc_now


# ============================================================================
# Enums
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_learner_levels(self):
        assert LearnerLevel.CADET == "CADET"
        assert LearnerLevel.OFFICER == "OFFICER"
        assert LearnerLevel.CAPTAIN == "CAPTAIN"

    def test_learning_styles(self):
        assert LearningStyle.VISUAL == "VISUAL"
        assert LearningStyle.TEXTUAL == "TEXTUAL"
        assert LearningStyle.PRACTICAL == "PRACTICAL"


# ============================================================================
# Assessment
# ============================================================================


class TestAssessment:
    """Test Assessment model."""

    def test_valid_assessment(self):
        a = Assessment(
            topic="Rule 15",
            score=85.0,
            questions_asked=10,
            correct_answers=8,
        )
        assert a.topic == "Rule 15"
        assert a.score == 85.0
        assert a.questions_asked == 10
        assert a.correct_answers == 8
        assert a.timestamp is not None

    def test_perfect_score(self):
        a = Assessment(
            topic="COLREGS",
            score=100.0,
            questions_asked=5,
            correct_answers=5,
        )
        assert a.score == 100.0

    def test_zero_score(self):
        a = Assessment(
            topic="SOLAS",
            score=0.0,
            questions_asked=3,
            correct_answers=0,
        )
        assert a.correct_answers == 0

    def test_score_too_high(self):
        with pytest.raises(Exception):
            Assessment(
                topic="Rule 15",
                score=101.0,
                questions_asked=5,
                correct_answers=5,
            )

    def test_score_too_low(self):
        with pytest.raises(Exception):
            Assessment(
                topic="Rule 15",
                score=-1.0,
                questions_asked=5,
                correct_answers=0,
            )

    def test_correct_exceeds_total(self):
        with pytest.raises(ValueError, match="correct_answers cannot exceed"):
            Assessment(
                topic="Rule 15",
                score=50.0,
                questions_asked=5,
                correct_answers=6,
            )

    def test_empty_topic(self):
        with pytest.raises(Exception):
            Assessment(
                topic="",
                score=50.0,
                questions_asked=5,
                correct_answers=3,
            )

    def test_zero_questions(self):
        with pytest.raises(Exception):
            Assessment(
                topic="Rule 15",
                score=50.0,
                questions_asked=0,
                correct_answers=0,
            )


# ============================================================================
# LearningProfile
# ============================================================================


class TestLearningProfile:
    """Test LearningProfile model."""

    def test_defaults(self):
        uid = uuid4()
        profile = LearningProfile(user_id=uid)
        assert profile.user_id == uid
        assert profile.current_level == LearnerLevel.CADET
        assert profile.learning_style is None
        assert profile.weak_topics == []
        assert profile.completed_topics == []
        assert profile.assessment_history == []
        assert profile.created_at is not None
        assert profile.updated_at is not None

    def test_custom_values(self):
        uid = uuid4()
        profile = LearningProfile(
            user_id=uid,
            current_level=LearnerLevel.OFFICER,
            learning_style=LearningStyle.VISUAL,
            weak_topics=["Rule 15"],
            completed_topics=["Rule 7"],
        )
        assert profile.current_level == LearnerLevel.OFFICER
        assert profile.learning_style == LearningStyle.VISUAL
        assert len(profile.weak_topics) == 1
        assert len(profile.completed_topics) == 1


class TestAddAssessment:
    """Test assessment addition and topic categorization."""

    def _make_profile(self):
        return LearningProfile(user_id=uuid4())

    def test_low_score_adds_to_weak(self):
        p = self._make_profile()
        a = Assessment(topic="Rule 15", score=30.0, questions_asked=10, correct_answers=3)
        p.add_assessment(a)
        assert "Rule 15" in p.weak_topics
        assert "Rule 15" not in p.completed_topics
        assert len(p.assessment_history) == 1

    def test_high_score_adds_to_completed(self):
        p = self._make_profile()
        a = Assessment(topic="Rule 7", score=90.0, questions_asked=10, correct_answers=9)
        p.add_assessment(a)
        assert "Rule 7" in p.completed_topics
        assert "Rule 7" not in p.weak_topics

    def test_high_score_removes_from_weak(self):
        p = self._make_profile()
        p.weak_topics.append("Rule 15")
        a = Assessment(topic="Rule 15", score=85.0, questions_asked=10, correct_answers=8)
        p.add_assessment(a)
        assert "Rule 15" in p.completed_topics
        assert "Rule 15" not in p.weak_topics

    def test_medium_score_no_change(self):
        p = self._make_profile()
        a = Assessment(topic="Rule 15", score=65.0, questions_asked=10, correct_answers=6)
        p.add_assessment(a)
        assert "Rule 15" not in p.weak_topics
        assert "Rule 15" not in p.completed_topics

    def test_duplicate_weak_not_added_twice(self):
        p = self._make_profile()
        a1 = Assessment(topic="Rule 15", score=30.0, questions_asked=5, correct_answers=1)
        a2 = Assessment(topic="Rule 15", score=40.0, questions_asked=5, correct_answers=2)
        p.add_assessment(a1)
        p.add_assessment(a2)
        assert p.weak_topics.count("Rule 15") == 1

    def test_duplicate_completed_not_added_twice(self):
        p = self._make_profile()
        a1 = Assessment(topic="Rule 7", score=90.0, questions_asked=5, correct_answers=4)
        a2 = Assessment(topic="Rule 7", score=95.0, questions_asked=5, correct_answers=5)
        p.add_assessment(a1)
        p.add_assessment(a2)
        assert p.completed_topics.count("Rule 7") == 1

    def test_updates_timestamp(self):
        p = self._make_profile()
        old_updated = p.updated_at
        import time
        time.sleep(0.01)
        a = Assessment(topic="Rule 15", score=50.0, questions_asked=5, correct_answers=2)
        p.add_assessment(a)
        assert p.updated_at >= old_updated


class TestTopicQueries:
    """Test topic query methods."""

    def _make_profile_with_history(self):
        p = LearningProfile(user_id=uuid4())
        p.add_assessment(Assessment(topic="Rule 15", score=30.0, questions_asked=10, correct_answers=3))
        p.add_assessment(Assessment(topic="Rule 15", score=70.0, questions_asked=10, correct_answers=7))
        p.add_assessment(Assessment(topic="Rule 7", score=90.0, questions_asked=5, correct_answers=4))
        return p

    def test_get_topic_average_score(self):
        p = self._make_profile_with_history()
        avg = p.get_topic_average_score("Rule 15")
        assert avg == 50.0  # (30 + 70) / 2

    def test_get_topic_average_score_not_found(self):
        p = self._make_profile_with_history()
        assert p.get_topic_average_score("SOLAS") is None

    def test_get_topic_average_score_single(self):
        p = self._make_profile_with_history()
        avg = p.get_topic_average_score("Rule 7")
        assert avg == 90.0

    def test_is_topic_weak(self):
        p = self._make_profile_with_history()
        assert p.is_topic_weak("Rule 15") is True
        assert p.is_topic_weak("Rule 7") is False

    def test_is_topic_mastered(self):
        p = self._make_profile_with_history()
        assert p.is_topic_mastered("Rule 7") is True
        assert p.is_topic_mastered("Rule 15") is False


# ============================================================================
# create_default_profile
# ============================================================================


class TestCreateDefaultProfile:
    """Test factory function."""

    def test_creates_default(self):
        uid = uuid4()
        p = create_default_profile(uid)
        assert p.user_id == uid
        assert p.current_level == LearnerLevel.CADET
        assert p.learning_style is None
        assert p.weak_topics == []
        assert p.completed_topics == []
        assert p.assessment_history == []

    def test_different_uuids(self):
        p1 = create_default_profile(uuid4())
        p2 = create_default_profile(uuid4())
        assert p1.user_id != p2.user_id


# ============================================================================
# _utc_now helper
# ============================================================================


class TestUtcNow:
    """Test UTC now helper."""

    def test_returns_aware_datetime(self):
        now = utc_now()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc
