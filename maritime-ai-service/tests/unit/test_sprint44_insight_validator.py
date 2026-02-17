"""
Tests for Sprint 44: InsightValidator coverage.

Tests insight validation including:
- ValidationResult dataclass
- Basic validation (length, behavioral check, category)
- is_behavioral content classification
- find_duplicate (embedding + Jaccard fallback)
- detect_contradiction
- Cosine similarity
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from uuid import uuid4


# ============================================================================
# ValidationResult
# ============================================================================


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        from app.engine.insight_validator import ValidationResult
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.reason is None
        assert result.action is None
        assert result.target_insight is None

    def test_rejected_result(self):
        from app.engine.insight_validator import ValidationResult
        result = ValidationResult(
            is_valid=False,
            reason="Too short",
            action="reject"
        )
        assert result.is_valid is False
        assert result.action == "reject"

    def test_merge_result(self):
        from app.engine.insight_validator import ValidationResult
        mock_insight = MagicMock()
        result = ValidationResult(
            is_valid=True,
            reason="Duplicate found",
            action="merge",
            target_insight=mock_insight,
            similarity_score=0.92
        )
        assert result.action == "merge"
        assert result.similarity_score == 0.92


# ============================================================================
# InsightValidator initialization
# ============================================================================


class TestInsightValidatorInit:
    """Test InsightValidator initialization."""

    def test_init_without_embeddings(self):
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        assert validator._embeddings is None
        assert validator._embedding_cache == {}

    def test_init_with_embeddings(self):
        from app.engine.insight_validator import InsightValidator
        mock_emb = MagicMock()
        validator = InsightValidator(embeddings=mock_emb)
        assert validator._embeddings is mock_emb


# ============================================================================
# is_behavioral
# ============================================================================


class TestIsBehavioral:
    """Test is_behavioral content classification."""

    @pytest.fixture
    def validator(self):
        from app.engine.insight_validator import InsightValidator
        return InsightValidator()

    def test_short_content_not_behavioral(self, validator):
        assert validator.is_behavioral("short") is False

    def test_atomic_fact_not_behavioral(self, validator):
        """Atomic facts (name, age) should not be behavioral."""
        assert validator.is_behavioral("User name is Minh and works at company X") is False

    def test_preference_is_behavioral(self, validator):
        """Preference patterns are behavioral."""
        assert validator.is_behavioral("User prefers visual learning and likes examples") is True

    def test_learning_pattern_is_behavioral(self, validator):
        """Learning patterns are behavioral."""
        assert validator.is_behavioral("User approaches problems by understanding theory first") is True

    def test_behavioral_with_tendency(self, validator):
        """Tendency patterns are behavioral."""
        assert validator.is_behavioral("User usually asks follow-up questions about details") is True

    def test_gap_pattern_is_behavioral(self, validator):
        """Knowledge gap patterns are behavioral."""
        assert validator.is_behavioral("User has difficulty with SOLAS fire safety regulations") is True

    def test_evolution_is_behavioral(self, validator):
        """Evolution/progress patterns are behavioral."""
        assert validator.is_behavioral("User has improved understanding of COLREGs since last session") is True

    def test_mixed_atomic_and_behavioral(self, validator):
        """Content with both atomic and behavioral returns False."""
        assert validator.is_behavioral("User name is Minh and prefers visual learning") is False

    def test_vietnamese_preference(self, validator):
        """Vietnamese preference patterns detected."""
        assert validator.is_behavioral("Sinh vien thich hoc theo cach nhin thay vi du") is True

    def test_vietnamese_gap(self, validator):
        """Vietnamese gap patterns detected."""
        assert validator.is_behavioral("Sinh vi\u00ean ch\u01b0a hi\u1ec3u r\u00f5 v\u1ec1 quy t\u1eafc tr\u00e1nh va COLREGs") is True


# ============================================================================
# Basic validation
# ============================================================================


class TestBasicValidation:
    """Test _validate_basic."""

    @pytest.fixture
    def validator(self):
        from app.engine.insight_validator import InsightValidator
        return InsightValidator()

    def _make_insight(self, content="User prefers detailed explanations with examples",
                      category="preference"):
        from app.models.semantic_memory import Insight, InsightCategory
        insight = MagicMock(spec=Insight)
        insight.content = content
        insight.category = InsightCategory(category)
        return insight

    def test_valid_insight(self, validator):
        result = validator._validate_basic(self._make_insight())
        assert result.is_valid is True

    def test_too_short_rejected(self, validator):
        result = validator._validate_basic(self._make_insight(content="short"))
        assert result.is_valid is False
        assert "short" in result.reason.lower()
        assert result.action == "reject"

    def test_atomic_fact_rejected(self, validator):
        """Atomic facts are rejected as non-behavioral."""
        result = validator._validate_basic(
            self._make_insight(content="User email is user@example.com and address is 123 Main St")
        )
        assert result.is_valid is False
        assert "atomic" in result.reason.lower()


# ============================================================================
# Cosine similarity
# ============================================================================


class TestCosineSimilarity:
    """Test _cosine_similarity."""

    @pytest.fixture
    def validator(self):
        from app.engine.insight_validator import InsightValidator
        return InsightValidator()

    def test_identical_vectors(self, validator):
        vec = np.array([1.0, 2.0, 3.0])
        assert abs(validator._cosine_similarity(vec, vec) - 1.0) < 0.001

    def test_orthogonal_vectors(self, validator):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        assert abs(validator._cosine_similarity(v1, v2)) < 0.001

    def test_opposite_vectors(self, validator):
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-1.0, 0.0])
        assert abs(validator._cosine_similarity(v1, v2) - (-1.0)) < 0.001

    def test_zero_vector(self, validator):
        v1 = np.array([0.0, 0.0, 0.0])
        v2 = np.array([1.0, 2.0, 3.0])
        assert validator._cosine_similarity(v1, v2) == 0.0

    def test_none_vectors(self, validator):
        assert validator._cosine_similarity(None, np.array([1.0])) == 0.0
        assert validator._cosine_similarity(np.array([1.0]), None) == 0.0


# ============================================================================
# Content similarity (embedding + Jaccard fallback)
# ============================================================================


class TestContentSimilarity:
    """Test _is_similar_content."""

    def test_jaccard_fallback_similar(self):
        """Jaccard similarity used when no embeddings."""
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        is_sim, score = validator._is_similar_content(
            "user prefers visual learning with examples",
            "user prefers visual learning with diagrams"
        )
        assert score > 0

    def test_jaccard_fallback_different(self):
        """Different content has low Jaccard."""
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        is_sim, score = validator._is_similar_content(
            "user prefers visual learning",
            "completely different topic about fire safety"
        )
        assert is_sim is False

    def test_jaccard_empty_after_stopwords(self):
        """Empty sets after removing common words."""
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        is_sim, score = validator._is_similar_content("the a an", "is has and")
        assert is_sim is False
        assert score == 0.0

    def test_embedding_based_similarity(self):
        """Embedding-based similarity when embeddings available."""
        from app.engine.insight_validator import InsightValidator
        mock_emb = MagicMock()
        mock_emb.embed_documents.side_effect = [
            [[1.0, 0.0, 0.0]],  # First call
            [[0.9, 0.1, 0.0]],  # Second call
        ]
        validator = InsightValidator(embeddings=mock_emb)
        is_sim, score = validator._is_similar_content("text1", "text2")
        assert score > 0

    def test_embedding_failure_falls_back(self):
        """Embedding failure falls back to Jaccard."""
        from app.engine.insight_validator import InsightValidator
        mock_emb = MagicMock()
        mock_emb.embed_documents.side_effect = Exception("API error")
        validator = InsightValidator(embeddings=mock_emb)
        is_sim, score = validator._is_similar_content(
            "user prefers visual learning examples",
            "user prefers visual learning examples"
        )
        # Falls back to Jaccard, should be high similarity
        assert score > 0.5


# ============================================================================
# find_duplicate
# ============================================================================


class TestFindDuplicate:
    """Test find_duplicate."""

    def _make_insight(self, content, category="preference", sub_topic=None):
        from app.models.semantic_memory import InsightCategory
        insight = MagicMock()
        insight.content = content
        insight.category = InsightCategory(category)
        insight.sub_topic = sub_topic
        return insight

    def test_no_existing_insights(self):
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        new = self._make_insight("User prefers detailed explanations with visual examples")
        dup, score = validator.find_duplicate(new, [])
        assert dup is None
        assert score == 0.0

    def test_different_category_no_match(self):
        """Different categories are never duplicates."""
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        new = self._make_insight("User prefers visual learning approach", category="preference")
        existing = [self._make_insight("User prefers visual learning approach", category="knowledge_gap")]
        dup, score = validator.find_duplicate(new, existing)
        assert dup is None

    def test_same_content_same_category_is_duplicate(self):
        """Identical content and category detected as duplicate."""
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        new = self._make_insight("user prefers visual learning with concrete examples")
        existing = [self._make_insight("user prefers visual learning with concrete examples")]
        dup, score = validator.find_duplicate(new, existing)
        assert dup is not None
        assert score > 0.5


# ============================================================================
# detect_contradiction
# ============================================================================


class TestDetectContradiction:
    """Test detect_contradiction."""

    def _make_insight(self, content, category="preference", sub_topic=None):
        from app.models.semantic_memory import InsightCategory
        insight = MagicMock()
        insight.content = content
        insight.category = InsightCategory(category)
        insight.sub_topic = sub_topic
        return insight

    @pytest.fixture
    def validator(self):
        from app.engine.insight_validator import InsightValidator
        return InsightValidator()

    def test_no_contradiction(self, validator):
        new = self._make_insight("User prefers visual learning", sub_topic="learning_style")
        existing = [self._make_insight("User likes hands-on approach", sub_topic="approach")]
        result = validator.detect_contradiction(new, existing)
        assert result is None

    def test_different_category_no_contradiction(self, validator):
        new = self._make_insight("User is good at navigation", category="preference", sub_topic="nav")
        existing = [self._make_insight("User is weak at navigation", category="knowledge_gap", sub_topic="nav")]
        result = validator.detect_contradiction(new, existing)
        assert result is None

    def test_contradiction_good_vs_weak(self, validator):
        """Good at vs weak at on same topic is contradiction."""
        new = self._make_insight("User is good at COLREGs navigation", sub_topic="navigation")
        existing = [self._make_insight("User is weak at COLREGs navigation", sub_topic="navigation")]
        result = validator.detect_contradiction(new, existing)
        assert result is not None

    def test_contradiction_like_vs_dislike(self, validator):
        """Like vs dislike on same topic is contradiction."""
        new = self._make_insight("User prefers theoretical approach", sub_topic="approach")
        existing = [self._make_insight("User avoids theoretical approach and prefers practical", sub_topic="approach")]
        result = validator.detect_contradiction(new, existing)
        assert result is not None

    def test_no_sub_topic_no_contradiction(self, validator):
        """No sub_topic means no contradiction check."""
        new = self._make_insight("User is good at math", sub_topic=None)
        existing = [self._make_insight("User is weak at math", sub_topic=None)]
        result = validator.detect_contradiction(new, existing)
        assert result is None


# ============================================================================
# Full validate pipeline
# ============================================================================


class TestValidatePipeline:
    """Test full validate() method."""

    def _make_insight(self, content, category="preference", sub_topic=None):
        from app.models.semantic_memory import InsightCategory
        insight = MagicMock()
        insight.content = content
        insight.category = InsightCategory(category)
        insight.sub_topic = sub_topic
        return insight

    def test_valid_new_insight(self):
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        insight = self._make_insight("User usually approaches problems by asking clarifying questions first")
        result = validator.validate(insight, [])
        assert result.is_valid is True
        assert result.action == "store"

    def test_invalid_too_short(self):
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        insight = self._make_insight("too short")
        result = validator.validate(insight, [])
        assert result.is_valid is False
        assert result.action == "reject"

    def test_duplicate_detected_triggers_merge(self):
        from app.engine.insight_validator import InsightValidator
        validator = InsightValidator()
        existing = self._make_insight("user prefers visual learning with concrete examples and diagrams")
        new = self._make_insight("user prefers visual learning with concrete examples and diagrams")
        result = validator.validate(new, [existing])
        assert result.action == "merge"

    def test_embedding_caching(self):
        """Embeddings are cached for repeated texts."""
        from app.engine.insight_validator import InsightValidator
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[1.0, 0.0, 0.0]]
        validator = InsightValidator(embeddings=mock_emb)

        # First call
        validator._compute_embedding("test text for caching")
        # Second call with same text
        validator._compute_embedding("test text for caching")
        # Should only call embed_documents once
        assert mock_emb.embed_documents.call_count == 1
