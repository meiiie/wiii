"""
Tests for Sprint 177 Feature A: Real Skill Learning via Browsing.

Covers:
- Config: New feature flags (skill learning, quiz, review)
- Models: LearningMaterial, ReviewSchedule, QuizQuestion, QuizResult
- SkillLearner: SM-2 spaced repetition, quiz generation, browsing pipeline
- SkillBuilder: New methods (learn_from_material, get_skills_for_review)
- SocialBrowser: Piping browse results to skill pipeline
- Heartbeat: REVIEW_SKILL/QUIZ_SKILL action planning and execution
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4


# =============================================================================
# Config Tests
# =============================================================================

class TestSkillLearningConfig:
    """Test new config flags for skill learning."""

    def test_skill_learning_flag_defaults(self):
        from app.core.config import Settings
        # Explicitly set to False to test code defaults (env may override)
        s = Settings(api_key="test", living_agent_enable_skill_learning=False)
        assert s.living_agent_enable_skill_learning is False
        assert s.living_agent_quiz_questions_per_session == 3
        assert s.living_agent_review_confidence_weight == 0.3

    def test_skill_learning_flag_enabled(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_enable_skill_learning=True,
            living_agent_quiz_questions_per_session=5,
            living_agent_review_confidence_weight=0.4,
        )
        assert s.living_agent_enable_skill_learning is True
        assert s.living_agent_quiz_questions_per_session == 5
        assert s.living_agent_review_confidence_weight == 0.4

    def test_cross_platform_memory_flag_defaults(self):
        from app.core.config import Settings
        # Explicitly set to False to test code defaults (env may override)
        s = Settings(api_key="test", enable_cross_platform_memory=False)
        assert s.enable_cross_platform_memory is False
        assert s.cross_platform_context_max_items == 3

    def test_cross_platform_memory_flag_enabled(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            enable_cross_platform_memory=True,
            cross_platform_context_max_items=5,
        )
        assert s.enable_cross_platform_memory is True
        assert s.cross_platform_context_max_items == 5

    def test_nested_config_synced(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_enable_skill_learning=True,
            living_agent_quiz_questions_per_session=7,
        )
        assert s.living_agent.enable_skill_learning is True
        assert s.living_agent.quiz_questions_per_session == 7

    def test_quiz_questions_bounds(self):
        from app.core.config import Settings
        s = Settings(api_key="test", living_agent_quiz_questions_per_session=1)
        assert s.living_agent_quiz_questions_per_session == 1
        s = Settings(api_key="test", living_agent_quiz_questions_per_session=10)
        assert s.living_agent_quiz_questions_per_session == 10


# =============================================================================
# Model Tests
# =============================================================================

class TestSkillLearningModels:
    """Test new Pydantic models for Sprint 177."""

    def test_learning_material_defaults(self):
        from app.engine.living_agent.models import LearningMaterial
        m = LearningMaterial()
        assert m.url == ""
        assert m.title == ""
        assert m.summary == ""
        assert m.deep_notes == ""
        assert m.relevance_score == 0.0

    def test_learning_material_with_data(self):
        from app.engine.living_agent.models import LearningMaterial
        m = LearningMaterial(
            url="https://example.com",
            title="Test Article",
            summary="Summary here",
            deep_notes="Deep notes here",
            relevance_score=0.85,
        )
        assert m.url == "https://example.com"
        assert m.relevance_score == 0.85

    def test_review_schedule_defaults(self):
        from app.engine.living_agent.models import ReviewSchedule
        r = ReviewSchedule()
        assert r.next_review_at is None
        assert r.interval_days == 1.0
        assert r.ease_factor == 2.5
        assert r.repetition_count == 0

    def test_review_schedule_with_data(self):
        from app.engine.living_agent.models import ReviewSchedule
        next_review = datetime.now(timezone.utc) + timedelta(days=3)
        r = ReviewSchedule(
            next_review_at=next_review,
            interval_days=3.0,
            ease_factor=2.6,
            repetition_count=2,
        )
        assert r.interval_days == 3.0
        assert r.ease_factor == 2.6

    def test_quiz_question_model(self):
        from app.engine.living_agent.models import QuizQuestion
        q = QuizQuestion(
            question="What is COLREGs Rule 14?",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            explanation="Head-on situation",
            difficulty="medium",
            source_url="https://example.com",
        )
        assert q.question == "What is COLREGs Rule 14?"
        assert len(q.options) == 4

    def test_quiz_result_model(self):
        from app.engine.living_agent.models import QuizResult
        r = QuizResult(
            skill_name="COLREGs",
            questions_total=3,
            questions_correct=2,
            score=0.67,
            quality_factor=0.67,
        )
        assert r.score == 0.67
        assert r.quality_factor == 0.67

    def test_action_type_review_skill(self):
        from app.engine.living_agent.models import ActionType
        assert ActionType.REVIEW_SKILL == "review_skill"
        assert ActionType.QUIZ_SKILL == "quiz_skill"

    def test_life_event_type_quiz_completed(self):
        from app.engine.living_agent.models import LifeEventType
        assert LifeEventType.QUIZ_COMPLETED == "quiz_completed"
        assert LifeEventType.REVIEW_COMPLETED == "review_completed"

    def test_models_exported_from_init(self):
        from app.engine.living_agent import (
            LearningMaterial,
            ReviewSchedule,
            QuizQuestion,
            QuizResult,
        )
        assert LearningMaterial is not None
        assert ReviewSchedule is not None


# =============================================================================
# SkillLearner — SM-2 Algorithm Tests
# =============================================================================

class TestSM2Algorithm:
    """Test SM-2 spaced repetition logic."""

    def _make_skill(self, confidence=0.5, notes="some notes", status="learning"):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        return WiiiSkill(
            skill_name="Test Skill",
            domain="general",
            status=SkillStatus(status),
            confidence=confidence,
            notes=notes,
            metadata={},
        )

    def test_update_review_schedule_success(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        learner.update_review_schedule(skill, quality=0.8)

        schedule = skill.metadata["review_schedule"]
        assert schedule["repetition_count"] == 1
        assert schedule["interval_days"] == 1.0
        assert schedule["ease_factor"] >= 1.3
        assert "next_review_at" in schedule

    def test_update_review_schedule_second_success(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        # First review
        learner.update_review_schedule(skill, quality=0.8)
        # Second review
        learner.update_review_schedule(skill, quality=0.9)

        schedule = skill.metadata["review_schedule"]
        assert schedule["repetition_count"] == 2
        assert schedule["interval_days"] == 3.0

    def test_update_review_schedule_third_success_uses_ease_factor(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        learner.update_review_schedule(skill, quality=0.8)
        learner.update_review_schedule(skill, quality=0.8)
        learner.update_review_schedule(skill, quality=0.8)

        schedule = skill.metadata["review_schedule"]
        assert schedule["repetition_count"] == 3
        # Third interval = 3.0 * ease_factor
        assert schedule["interval_days"] > 3.0

    def test_update_review_schedule_failure_resets(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        # Successful reviews
        learner.update_review_schedule(skill, quality=0.8)
        learner.update_review_schedule(skill, quality=0.8)

        # Failed review
        learner.update_review_schedule(skill, quality=0.3)

        schedule = skill.metadata["review_schedule"]
        assert schedule["repetition_count"] == 0
        assert schedule["interval_days"] == 1.0

    def test_ease_factor_minimum_1_3(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        # Repeated failures should not drop ease below 1.3
        for _ in range(10):
            learner.update_review_schedule(skill, quality=0.0)

        schedule = skill.metadata["review_schedule"]
        assert schedule["ease_factor"] >= 1.3

    def test_interval_capped_at_30_days(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        # Many successful reviews
        for _ in range(20):
            learner.update_review_schedule(skill, quality=1.0)

        schedule = skill.metadata["review_schedule"]
        assert schedule["interval_days"] <= 30.0

    def test_next_review_at_is_future(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        skill = self._make_skill()

        learner.update_review_schedule(skill, quality=0.7)

        schedule = skill.metadata["review_schedule"]
        next_review = datetime.fromisoformat(schedule["next_review_at"])
        assert next_review > datetime.now(timezone.utc)


# =============================================================================
# SkillLearner — Process Browsing Results
# =============================================================================

class TestProcessBrowsingResults:
    """Test browsing→skill pipeline."""

    def test_skips_low_relevance_items(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        learner = SkillLearner()
        items = [
            BrowsingItem(platform="web", title="Low relevance", relevance_score=0.3),
        ]

        # Patch the seam used by SkillLearner after the singleton registry split.
        mock_builder = MagicMock()
        with patch("app.engine.living_agent.skill_learner.get_skill_builder", return_value=mock_builder):
            result = learner.process_browsing_results(items, ["AI"])
            assert result == []

    def test_processes_high_relevance_items(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem, WiiiSkill

        learner = SkillLearner()
        items = [
            BrowsingItem(
                platform="web",
                title="COLREGs Rule 14 Explained",
                summary="Head-on situation rules",
                url="https://example.com/colregs",
                relevance_score=0.8,
            ),
        ]

        mock_skill = WiiiSkill(skill_name="COLREGs Rule 14 Explained", metadata={})
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.skill_learner.get_skill_builder", return_value=mock_builder):
            result = learner.process_browsing_results(items, ["maritime"])
            assert len(result) == 1
            assert "COLREGs Rule 14 Explained" in result[0]

    def test_discovers_new_skill_from_browsing(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem, WiiiSkill

        learner = SkillLearner()
        items = [
            BrowsingItem(
                platform="web",
                title="New Maritime Topic",
                summary="Interesting maritime content",
                url="https://example.com/new",
                relevance_score=0.9,
            ),
        ]

        new_skill = WiiiSkill(skill_name="New Maritime Topic", metadata={})
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = None
        mock_builder.discover.return_value = new_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.skill_learner.get_skill_builder", return_value=mock_builder):
            result = learner.process_browsing_results(items, ["maritime"])
            assert len(result) == 1
            mock_builder.discover.assert_called_once()

    def test_extract_skill_name_removes_noise(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        item = BrowsingItem(platform="web", title="Some Article - YouTube")
        name = SkillLearner._extract_skill_name(item)
        assert "YouTube" not in name
        assert name == "Some Article"

    def test_extract_skill_name_empty_title(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        item = BrowsingItem(platform="web", title="")
        name = SkillLearner._extract_skill_name(item)
        assert name == ""

    def test_match_domain_maritime(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        item = BrowsingItem(platform="web", title="COLREGs update 2026", summary="IMO regulations")
        domain = SkillLearner._match_domain(item, ["maritime"])
        assert domain == "maritime"

    def test_match_domain_tech(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        item = BrowsingItem(platform="web", title="Python AI framework", summary="machine learning tutorial")
        domain = SkillLearner._match_domain(item, ["tech"])
        assert domain == "tech"

    def test_match_domain_general_fallback(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import BrowsingItem

        item = BrowsingItem(platform="web", title="Random Article", summary="Nothing special")
        domain = SkillLearner._match_domain(item, [])
        assert domain == "general"


# =============================================================================
# SkillLearner — Learn from Content
# =============================================================================

class TestLearnFromContent:
    """Test content-based learning."""

    @pytest.mark.asyncio
    async def test_learn_from_content_generates_deep_notes(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import LearningMaterial, WiiiSkill, SkillStatus

        learner = SkillLearner()
        material = LearningMaterial(
            url="https://example.com/article",
            title="Deep Learning Basics",
            summary="Neural networks fundamentals",
            relevance_score=0.9,
        )

        mock_skill = WiiiSkill(
            skill_name="Deep Learning Basics",
            status=SkillStatus.LEARNING,
            confidence=0.2,
            notes="Previous notes",
            metadata={},
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="Detailed notes about deep learning")

        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.local_llm.get_local_llm", return_value=mock_llm), \
             patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch.object(SkillLearner, "_update_skill_metadata"):
            result = await learner.learn_from_content("Deep Learning Basics", material)

        assert result is True
        assert "Deep Learning Basics" in mock_skill.notes
        assert mock_skill.confidence > 0.2

    @pytest.mark.asyncio
    async def test_learn_from_content_skips_mastered(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import LearningMaterial, WiiiSkill, SkillStatus

        learner = SkillLearner()
        material = LearningMaterial(title="Test")

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.MASTERED,
        )

        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            result = await learner.learn_from_content("Test", material)

        assert result is False

    @pytest.mark.asyncio
    async def test_learn_from_content_transitions_discovered_to_learning(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import LearningMaterial, WiiiSkill, SkillStatus

        learner = SkillLearner()
        material = LearningMaterial(title="New Topic", relevance_score=0.7)

        mock_skill = WiiiSkill(
            skill_name="New Topic",
            status=SkillStatus.DISCOVERED,
            metadata={},
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="New notes")
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.local_llm.get_local_llm", return_value=mock_llm), \
             patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch.object(SkillLearner, "_update_skill_metadata"):
            await learner.learn_from_content("New Topic", material)

        assert mock_skill.status == SkillStatus.LEARNING

    @pytest.mark.asyncio
    async def test_learn_from_content_adds_source_url(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import LearningMaterial, WiiiSkill, SkillStatus

        learner = SkillLearner()
        material = LearningMaterial(url="https://example.com/new", title="Test")

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            sources=[],
            metadata={},
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="Notes")
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.local_llm.get_local_llm", return_value=mock_llm), \
             patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch.object(SkillLearner, "_update_skill_metadata"):
            await learner.learn_from_content("Test", material)

        assert "https://example.com/new" in mock_skill.sources


# =============================================================================
# SkillLearner — Quiz Generation
# =============================================================================

class TestQuizGeneration:
    """Test quiz generation and evaluation."""

    @pytest.mark.asyncio
    async def test_generate_quiz_returns_questions(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill

        learner = SkillLearner()
        mock_skill = WiiiSkill(skill_name="Test", notes="Some detailed notes about the topic")

        quiz_json = json.dumps([
            {"question": "Q1?", "options": ["A", "B", "C", "D"], "correct_answer": "A", "explanation": "Because A", "difficulty": "easy"},
            {"question": "Q2?", "options": ["A", "B", "C", "D"], "correct_answer": "B", "explanation": "Because B", "difficulty": "medium"},
        ])

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=quiz_json)
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill

        with patch("app.engine.living_agent.local_llm.get_local_llm", return_value=mock_llm), \
             patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_quiz_questions_per_session = 3
            questions = await learner.generate_quiz("Test", num_questions=2)

        assert len(questions) == 2
        assert questions[0].question == "Q1?"
        assert questions[0].correct_answer == "A"

    @pytest.mark.asyncio
    async def test_generate_quiz_empty_notes(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill

        learner = SkillLearner()
        mock_skill = WiiiSkill(skill_name="Test", notes="")

        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            questions = await learner.generate_quiz("Test")

        assert questions == []

    @pytest.mark.asyncio
    async def test_generate_quiz_no_skill(self):
        from app.engine.living_agent.skill_learner import SkillLearner

        learner = SkillLearner()
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = None

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            questions = await learner.generate_quiz("Nonexistent")

        assert questions == []

    def test_parse_quiz_response_valid_json(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill

        skill = WiiiSkill(skill_name="Test")
        raw = json.dumps([
            {"question": "Q?", "options": ["A", "B"], "correct_answer": "A"},
        ])
        questions = SkillLearner._parse_quiz_response(raw, skill)
        assert len(questions) == 1

    def test_parse_quiz_response_invalid_json(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill

        skill = WiiiSkill(skill_name="Test")
        raw = "Not valid JSON at all"
        questions = SkillLearner._parse_quiz_response(raw, skill)
        assert questions == []

    def test_parse_quiz_response_json_with_preamble(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill

        skill = WiiiSkill(skill_name="Test")
        raw = 'Here are the questions:\n[{"question": "Q?", "options": ["A", "B"], "correct_answer": "A"}]'
        questions = SkillLearner._parse_quiz_response(raw, skill)
        assert len(questions) == 1


# =============================================================================
# SkillLearner — Quiz Evaluation
# =============================================================================

class TestQuizEvaluation:
    """Test quiz evaluation and confidence updates."""

    @pytest.mark.asyncio
    async def test_evaluate_quiz_perfect_score(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import QuizQuestion, WiiiSkill, SkillStatus

        learner = SkillLearner()
        questions = [
            QuizQuestion(question="Q1?", options=["A", "B"], correct_answer="A"),
            QuizQuestion(question="Q2?", options=["A", "B"], correct_answer="B"),
        ]
        answers = ["A", "B"]

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            confidence=0.5,
            metadata={},
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch("app.core.config.settings") as mock_settings, \
             patch.object(SkillLearner, "_update_skill_metadata"):
            mock_settings.living_agent_review_confidence_weight = 0.3
            result = await learner.evaluate_quiz("Test", questions, answers)

        assert result is not None
        assert result.score == 1.0
        assert result.questions_correct == 2
        assert result.questions_total == 2

    @pytest.mark.asyncio
    async def test_evaluate_quiz_zero_score(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import QuizQuestion, WiiiSkill, SkillStatus

        learner = SkillLearner()
        questions = [
            QuizQuestion(question="Q1?", options=["A", "B"], correct_answer="A"),
        ]
        answers = ["B"]

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            confidence=0.5,
            metadata={},
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch("app.core.config.settings") as mock_settings, \
             patch.object(SkillLearner, "_update_skill_metadata"):
            mock_settings.living_agent_review_confidence_weight = 0.3
            result = await learner.evaluate_quiz("Test", questions, answers)

        assert result.score == 0.0
        assert result.questions_correct == 0

    @pytest.mark.asyncio
    async def test_evaluate_quiz_updates_confidence_ema(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import QuizQuestion, WiiiSkill, SkillStatus

        learner = SkillLearner()
        questions = [
            QuizQuestion(question="Q?", options=["A", "B"], correct_answer="A"),
        ]
        answers = ["A"]

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            confidence=0.4,
            metadata={},
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        alpha = 0.3
        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch("app.core.config.settings") as mock_settings, \
             patch.object(SkillLearner, "_update_skill_metadata"):
            mock_settings.living_agent_review_confidence_weight = alpha
            await learner.evaluate_quiz("Test", questions, answers)

        # EMA: alpha * 1.0 + (1-alpha) * 0.4 = 0.3 + 0.28 = 0.58
        expected = alpha * 1.0 + (1 - alpha) * 0.4
        assert abs(mock_skill.confidence - expected) < 0.01

    @pytest.mark.asyncio
    async def test_evaluate_quiz_records_history(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import QuizQuestion, WiiiSkill, SkillStatus

        learner = SkillLearner()
        questions = [
            QuizQuestion(question="Q?", options=["A", "B"], correct_answer="A"),
        ]
        answers = ["A"]

        mock_skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            confidence=0.5,
            metadata={},
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill
        mock_builder._update_skill.return_value = None

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder), \
             patch("app.core.config.settings") as mock_settings, \
             patch.object(SkillLearner, "_update_skill_metadata"):
            mock_settings.living_agent_review_confidence_weight = 0.3
            await learner.evaluate_quiz("Test", questions, answers)

        assert "quiz_history" in mock_skill.metadata
        assert len(mock_skill.metadata["quiz_history"]) == 1
        assert mock_skill.metadata["quiz_history"][0]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_quiz_empty_inputs(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        learner = SkillLearner()
        result = await learner.evaluate_quiz("Test", [], [])
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_quiz_no_skill_found(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import QuizQuestion

        learner = SkillLearner()
        questions = [QuizQuestion(question="Q?", options=["A"], correct_answer="A")]

        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = None

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            result = await learner.evaluate_quiz("Missing", questions, ["A"])

        assert result is None


# =============================================================================
# SkillLearner — Review Due Detection
# =============================================================================

class TestSkillsDueForReview:
    """Test review scheduling detection."""

    def test_no_schedule_with_notes_is_due(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill, SkillStatus

        learner = SkillLearner()
        skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.LEARNING,
            notes="Has notes",
            metadata={},
        )

        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            due = learner.get_skills_due_for_review()

        assert len(due) == 1

    def test_past_review_time_is_due(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill, SkillStatus

        learner = SkillLearner()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.PRACTICING,
            notes="Has notes",
            metadata={"review_schedule": {"next_review_at": past}},
        )

        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            due = learner.get_skills_due_for_review()

        assert len(due) == 1

    def test_future_review_time_not_due(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill, SkillStatus

        learner = SkillLearner()
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.PRACTICING,
            notes="Has notes",
            metadata={"review_schedule": {"next_review_at": future}},
        )

        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            due = learner.get_skills_due_for_review()

        assert len(due) == 0

    def test_mastered_skills_excluded(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill, SkillStatus

        learner = SkillLearner()
        skill = WiiiSkill(
            skill_name="Mastered",
            status=SkillStatus.MASTERED,
            notes="Done",
            metadata={},
        )

        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            due = learner.get_skills_due_for_review()

        assert len(due) == 0

    def test_discovered_skills_excluded(self):
        from app.engine.living_agent.skill_learner import SkillLearner
        from app.engine.living_agent.models import WiiiSkill, SkillStatus

        learner = SkillLearner()
        skill = WiiiSkill(
            skill_name="New",
            status=SkillStatus.DISCOVERED,
            notes="",
            metadata={},
        )

        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            due = learner.get_skills_due_for_review()

        assert len(due) == 0


# =============================================================================
# SkillBuilder — New Methods
# =============================================================================

class TestSkillBuilderNewMethods:
    """Test Sprint 177 additions to SkillBuilder."""

    @pytest.mark.asyncio
    async def test_learn_from_material_delegates(self):
        from app.engine.living_agent.skill_builder import SkillBuilder
        from app.engine.living_agent.models import LearningMaterial

        builder = SkillBuilder()
        material = LearningMaterial(title="Test", url="https://example.com")

        mock_learner = MagicMock()
        mock_learner.learn_from_content = AsyncMock(return_value=True)

        with patch("app.engine.living_agent.skill_learner.get_skill_learner", return_value=mock_learner):
            result = await builder.learn_from_material("Test Topic", material)

        assert result is True
        mock_learner.learn_from_content.assert_called_once_with("Test Topic", material)

    def test_get_skills_for_review_delegates(self):
        from app.engine.living_agent.skill_builder import SkillBuilder
        from app.engine.living_agent.models import WiiiSkill

        builder = SkillBuilder()
        mock_skills = [WiiiSkill(skill_name="Due Skill")]

        mock_learner = MagicMock()
        mock_learner.get_skills_due_for_review.return_value = mock_skills

        with patch("app.engine.living_agent.skill_learner.get_skill_learner", return_value=mock_learner):
            result = builder.get_skills_for_review()

        assert len(result) == 1
        assert result[0].skill_name == "Due Skill"


# =============================================================================
# SocialBrowser — Skill Pipeline Integration
# =============================================================================

class TestSocialBrowserSkillPipeline:
    """Test piping browse results to skill learning pipeline."""

    @pytest.mark.asyncio
    async def test_browse_feed_pipes_to_skill_learner_when_enabled(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="Test Item",
                summary="Content",
                relevance_score=0.8,
            ),
        ]

        mock_learner = MagicMock()
        mock_learner.process_browsing_results.return_value = ["Test Item"]

        mock_settings = MagicMock()
        mock_settings.living_agent_enable_social_browse = True
        mock_settings.living_agent_enable_skill_learning = True

        with patch("app.core.config.settings", mock_settings), \
             patch.object(browser, "_search_web", new_callable=AsyncMock, return_value=items), \
             patch.object(browser, "_score_relevance", new_callable=AsyncMock, return_value=items), \
             patch.object(browser, "_save_browsing_log"), \
             patch("app.engine.living_agent.skill_learner.get_skill_learner", return_value=mock_learner):
            await browser.browse_feed(topic="tech", interests=["AI"])

        mock_learner.process_browsing_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_browse_feed_skips_skill_learner_when_disabled(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(platform="web", title="Test", relevance_score=0.8),
        ]

        mock_settings = MagicMock()
        mock_settings.living_agent_enable_social_browse = True
        mock_settings.living_agent_enable_skill_learning = False

        with patch("app.core.config.settings", mock_settings), \
             patch.object(browser, "_search_web", new_callable=AsyncMock, return_value=items), \
             patch.object(browser, "_save_browsing_log"):
            result = await browser.browse_feed(topic="tech")

        assert len(result) > 0


# =============================================================================
# Heartbeat — REVIEW_SKILL Action
# =============================================================================

class TestHeartbeatReviewAction:
    """Test heartbeat integration with skill review."""

    @pytest.mark.asyncio
    async def test_plan_actions_includes_review_when_skills_due(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType, WiiiSkill, SkillStatus

        scheduler = HeartbeatScheduler()
        due_skill = WiiiSkill(skill_name="Due Skill", status=SkillStatus.LEARNING)

        mock_learner = MagicMock()
        mock_learner.get_skills_due_for_review.return_value = [due_skill]

        mock_settings = MagicMock()
        mock_settings.living_agent_max_actions_per_heartbeat = 5
        mock_settings.living_agent_enable_social_browse = False
        mock_settings.living_agent_enable_skill_building = False
        mock_settings.living_agent_enable_skill_learning = True
        mock_settings.living_agent_enable_journal = False
        mock_settings.living_agent_enable_weather = False
        mock_settings.living_agent_enable_briefing = False
        mock_settings.living_agent_enable_proactive_messaging = False

        with patch("app.core.config.settings", mock_settings), \
             patch("app.engine.living_agent.skill_learner.get_skill_learner", return_value=mock_learner):
            actions = await scheduler._plan_actions("curious", 0.7)

        action_types = [a.action_type for a in actions]
        assert ActionType.REVIEW_SKILL in action_types
        review = [a for a in actions if a.action_type == ActionType.REVIEW_SKILL][0]
        assert review.target == "Due Skill"
        assert review.priority == 0.75

    @pytest.mark.asyncio
    async def test_plan_actions_no_review_when_disabled(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType

        scheduler = HeartbeatScheduler()

        mock_settings = MagicMock()
        mock_settings.living_agent_max_actions_per_heartbeat = 5
        mock_settings.living_agent_enable_social_browse = False
        mock_settings.living_agent_enable_skill_building = False
        mock_settings.living_agent_enable_skill_learning = False
        mock_settings.living_agent_enable_journal = False
        mock_settings.living_agent_enable_weather = False
        mock_settings.living_agent_enable_briefing = False
        mock_settings.living_agent_enable_proactive_messaging = False

        with patch("app.core.config.settings", mock_settings):
            actions = await scheduler._plan_actions("curious", 0.7)

        action_types = [a.action_type for a in actions]
        assert ActionType.REVIEW_SKILL not in action_types

    @pytest.mark.asyncio
    async def test_execute_review_skill_action(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import (
            HeartbeatAction, ActionType, QuizQuestion, QuizResult,
        )

        scheduler = HeartbeatScheduler()
        action = HeartbeatAction(
            action_type=ActionType.REVIEW_SKILL,
            target="Test Skill",
        )

        mock_questions = [
            QuizQuestion(question="Q?", options=["A", "B"], correct_answer="A"),
        ]
        mock_result = QuizResult(
            skill_name="Test Skill",
            questions_total=1,
            questions_correct=1,
            score=1.0,
            quality_factor=1.0,
        )

        mock_learner = MagicMock()
        mock_learner.generate_quiz = AsyncMock(return_value=mock_questions)
        mock_learner.evaluate_quiz = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.process_event = MagicMock()

        with patch("app.engine.living_agent.skill_learner.get_skill_learner", return_value=mock_learner):
            scheduler._self_answer_quiz = AsyncMock(return_value=["A"])
            await scheduler._action_review_skill(action, mock_engine)

        mock_learner.generate_quiz.assert_called_once_with("Test Skill")
        mock_learner.evaluate_quiz.assert_called_once()
        mock_engine.process_event.assert_called_once()


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Test singleton pattern."""

    def test_get_skill_learner_singleton(self):
        from app.engine.living_agent import skill_learner
        # Reset singleton
        skill_learner._learner_instance = None
        instance1 = skill_learner.get_skill_learner()
        instance2 = skill_learner.get_skill_learner()
        assert instance1 is instance2
        skill_learner._learner_instance = None  # Cleanup
