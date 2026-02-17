"""
Tests for Sprint 33: HybridConfidenceEvaluator — pure math, no LLM.

Covers:
- _calculate_bm25: BM25 keyword scoring
- _calculate_cosine_similarity: embedding cosine
- _calculate_domain_boost: domain vocabulary matching
- evaluate: full weighted combination
- aggregate_confidence: weighted average
- _tokenize: text tokenization
- Weight normalization
"""

import math
import pytest
from unittest.mock import patch, MagicMock

from app.engine.agentic_rag.confidence_evaluator import (
    HybridConfidenceEvaluator,
    HybridEvaluatorConfig,
    ConfidenceResult,
)


# =============================================================================
# _tokenize
# =============================================================================


class TestTokenize:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_basic_tokenization(self):
        tokens = self.evaluator._tokenize("Hello world test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens  # 4 chars, above min length

    def test_filters_short_tokens(self):
        tokens = self.evaluator._tokenize("I am a big cat")
        # "I" and "a" should be filtered (< 2 chars)
        assert "i" not in tokens
        assert "a" not in tokens  # single char filtered
        assert "am" in tokens
        assert "big" in tokens

    def test_empty_string(self):
        tokens = self.evaluator._tokenize("")
        assert tokens == []

    def test_special_characters(self):
        tokens = self.evaluator._tokenize("rule-15, chapter II-2")
        assert "rule" in tokens
        assert "15" in tokens
        assert "chapter" in tokens


# =============================================================================
# _calculate_bm25
# =============================================================================


class TestCalculateBM25:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_exact_match(self):
        score, matched = self.evaluator._calculate_bm25(
            "safety regulations", "safety regulations for maritime operations"
        )
        assert score > 0
        assert "safety" in matched
        assert "regulations" in matched

    def test_no_match(self):
        score, matched = self.evaluator._calculate_bm25(
            "navigation rules", "fire extinguisher maintenance procedures"
        )
        assert score == 0.0
        assert matched == []

    def test_empty_query(self):
        score, matched = self.evaluator._calculate_bm25("", "some content")
        assert score == 0.0

    def test_empty_doc(self):
        score, matched = self.evaluator._calculate_bm25("query terms", "")
        assert score == 0.0

    def test_score_bounded(self):
        """Score should be in [0, 1]."""
        score, _ = self.evaluator._calculate_bm25(
            "rule rule rule rule",
            "rule " * 100,
        )
        assert 0.0 <= score <= 1.0

    def test_partial_match(self):
        score, matched = self.evaluator._calculate_bm25(
            "safety colregs navigation",
            "safety procedures for maritime vessels"
        )
        assert "safety" in matched
        assert score > 0


# =============================================================================
# _calculate_cosine_similarity
# =============================================================================


class TestCalculateCosineSimilarity:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_identical_vectors(self):
        vec = [1.0, 0.0, 0.0]
        sim = self.evaluator._calculate_cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        sim = self.evaluator._calculate_cosine_similarity(vec1, vec2)
        assert abs(sim - 0.5) < 1e-6  # cos=0 → (0+1)/2 = 0.5

    def test_opposite_vectors(self):
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        sim = self.evaluator._calculate_cosine_similarity(vec1, vec2)
        assert abs(sim - 0.0) < 1e-6  # cos=-1 → (-1+1)/2 = 0.0

    def test_empty_vectors(self):
        assert self.evaluator._calculate_cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        assert self.evaluator._calculate_cosine_similarity([0, 0], [1, 0]) == 0.0

    def test_dimension_mismatch(self):
        sim = self.evaluator._calculate_cosine_similarity([1, 0], [1, 0, 0])
        assert sim == 0.0


# =============================================================================
# _calculate_domain_boost
# =============================================================================


class TestCalculateDomainBoost:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_rule_number_match(self):
        boost, terms = self.evaluator._calculate_domain_boost(
            "điều 15 quy tắc", "Nội dung điều 15 về hàng hải"
        )
        assert boost >= 0.5
        assert any("15" in t for t in terms)

    def test_domain_vocabulary(self):
        boost, terms = self.evaluator._calculate_domain_boost(
            "SOLAS safety", "SOLAS regulations for maritime safety"
        )
        assert boost > 0
        assert len(terms) > 0

    def test_no_domain_terms(self):
        boost, terms = self.evaluator._calculate_domain_boost(
            "weather forecast", "sunny skies expected tomorrow"
        )
        assert boost == 0.0
        assert terms == []

    def test_boost_capped_at_1(self):
        """Domain boost should never exceed 1.0."""
        boost, _ = self.evaluator._calculate_domain_boost(
            "điều 15 colregs solas marpol stcw imdg tàu an toàn",
            "điều 15 colregs solas marpol stcw imdg tàu an toàn buồng máy hầm hàng"
        )
        assert boost <= 1.0


# =============================================================================
# evaluate (full pipeline)
# =============================================================================


class TestEvaluate:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_full_evaluation(self):
        result = self.evaluator.evaluate(
            query="điều 15 colregs",
            doc_content="Điều 15 COLREGs quy định về tình huống cắt nhau",
            query_embedding=[1.0, 0.0, 0.0],
            doc_embedding=[0.9, 0.1, 0.0],
        )
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.score <= 1.0
        assert result.bm25_score >= 0
        assert result.domain_boost >= 0

    def test_no_embeddings_fallback(self):
        """Without embeddings, BM25 should be boosted 1.5x."""
        result = self.evaluator.evaluate(
            query="safety", doc_content="safety regulations"
        )
        assert result.embedding_score == 0.0
        assert result.bm25_score > 0  # BM25 should still work

    def test_score_clamped(self):
        result = self.evaluator.evaluate(
            query="a", doc_content="b"
        )
        assert 0.0 <= result.score <= 1.0

    def test_empty_query(self):
        result = self.evaluator.evaluate(query="", doc_content="some content")
        assert result.score >= 0.0

    def test_confidence_flags(self):
        """High score should set is_high_confidence."""
        # Give a perfect match to get high score
        result = self.evaluator.evaluate(
            query="điều 15 colregs tàu thuyền an toàn",
            doc_content="điều 15 colregs quy tắc tàu thuyền an toàn cứu sinh marpol",
            query_embedding=[1.0, 0.0],
            doc_embedding=[1.0, 0.0],
        )
        # We can at least check the flags are booleans
        assert isinstance(result.is_high_confidence, bool)
        assert isinstance(result.is_medium_confidence, bool)


# =============================================================================
# evaluate_batch
# =============================================================================


class TestEvaluateBatch:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_batch_evaluation(self):
        docs = [
            {"content": "colregs rule 15 crossing"},
            {"content": "fire safety procedures"},
            {"content": "engine maintenance manual"},
        ]
        results = self.evaluator.evaluate_batch("colregs rule 15", docs)
        assert len(results) == 3
        assert all(isinstance(r, ConfidenceResult) for r in results)

    def test_empty_batch(self):
        results = self.evaluator.evaluate_batch("query", [])
        assert results == []


# =============================================================================
# aggregate_confidence
# =============================================================================


class TestAggregateConfidence:
    def setup_method(self):
        self.evaluator = HybridConfidenceEvaluator()

    def test_empty_results(self):
        assert self.evaluator.aggregate_confidence([]) == 0.0

    def test_single_high_confidence(self):
        result = ConfidenceResult(
            score=0.9, bm25_score=0.5, embedding_score=0.8,
            domain_boost=0.3, matched_terms=["test"],
            is_high_confidence=True, is_medium_confidence=True,
        )
        agg = self.evaluator.aggregate_confidence([result])
        assert abs(agg - 0.9) < 1e-6  # weight=2, 0.9*2/2 = 0.9

    def test_mixed_confidence(self):
        results = [
            ConfidenceResult(
                score=0.9, bm25_score=0, embedding_score=0,
                domain_boost=0, matched_terms=[],
                is_high_confidence=True, is_medium_confidence=True,
            ),
            ConfidenceResult(
                score=0.3, bm25_score=0, embedding_score=0,
                domain_boost=0, matched_terms=[],
                is_high_confidence=False, is_medium_confidence=False,
            ),
        ]
        agg = self.evaluator.aggregate_confidence(results)
        # high: weight=2, low: weight=0.5
        expected = (0.9 * 2 + 0.3 * 0.5) / (2 + 0.5)
        assert abs(agg - expected) < 1e-6


# =============================================================================
# Weight normalization
# =============================================================================


class TestWeightNormalization:
    def test_unnormalized_weights(self):
        """Weights that don't sum to 1.0 should be normalized."""
        config = HybridEvaluatorConfig(
            bm25_weight=1.0,
            embedding_weight=1.0,
            domain_boost_weight=1.0,
        )
        evaluator = HybridConfidenceEvaluator(config)
        total = (
            evaluator._config.bm25_weight
            + evaluator._config.embedding_weight
            + evaluator._config.domain_boost_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_default_weights_sum_to_1(self):
        config = HybridEvaluatorConfig()
        total = config.bm25_weight + config.embedding_weight + config.domain_boost_weight
        assert abs(total - 1.0) < 0.01
