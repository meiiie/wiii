"""
Tests for Sprint 33: RRF Reranker — pure math/logic, no LLM.

Covers:
- _calculate_rrf_score: RRF formula
- _extract_query_keywords: keyword extraction
- _calculate_title_match_boost: boost multiplier logic
- HybridSearchResult helper methods
- merge: full merge pipeline
"""

import pytest
from dataclasses import dataclass
from typing import Optional
from app.engine.rrf_reranker import RRFReranker, HybridSearchResult


@dataclass
class _MockDenseResult:
    """Mock for DenseSearchResult objects."""
    node_id: str
    content: str
    similarity: float
    content_type: str = "text"
    confidence_score: float = 1.0
    page_number: int = 0
    chunk_index: int = 0
    image_url: str = ""
    document_id: str = ""
    section_hierarchy: dict = None
    bounding_boxes: list = None

    def __post_init__(self):
        if self.section_hierarchy is None:
            self.section_hierarchy = {}


@dataclass
class _MockSparseResult:
    """Mock for SparseSearchResult objects."""
    node_id: str
    title: str
    content: str
    source: str
    category: str
    score: float
    image_url: str = ""
    page_number: int = 0
    document_id: str = ""
    bounding_boxes: list = None


# =============================================================================
# HybridSearchResult
# =============================================================================


class TestHybridSearchResult:
    def test_appears_in_both(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
            dense_score=0.9, sparse_score=5.0,
        )
        assert r.appears_in_both() is True

    def test_not_in_both_dense_only(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
            dense_score=0.9, sparse_score=None,
        )
        assert r.appears_in_both() is False

    def test_has_document_hierarchy(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
            section_hierarchy={"chapter": "II"},
        )
        assert r.has_document_hierarchy() is True

    def test_no_document_hierarchy(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
        )
        assert r.has_document_hierarchy() is False

    def test_has_bounding_boxes(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
            bounding_boxes=[{"x": 0, "y": 0}],
        )
        assert r.has_bounding_boxes() is True

    def test_no_bounding_boxes(self):
        r = HybridSearchResult(
            node_id="1", title="t", content="c", source="s", category="cat",
        )
        assert r.has_bounding_boxes() is False


# =============================================================================
# _calculate_rrf_score
# =============================================================================


class TestCalculateRRFScore:
    def setup_method(self):
        self.reranker = RRFReranker(k=60)

    def test_both_ranks(self):
        score = self.reranker._calculate_rrf_score(
            dense_rank=1, sparse_rank=1,
            dense_weight=0.5, sparse_weight=0.5,
        )
        expected = 0.5 / (60 + 1) + 0.5 / (60 + 1)
        assert abs(score - expected) < 1e-10

    def test_dense_only(self):
        score = self.reranker._calculate_rrf_score(
            dense_rank=1, sparse_rank=None,
            dense_weight=0.5, sparse_weight=0.5,
        )
        assert score == 0.5 / 61

    def test_sparse_only(self):
        score = self.reranker._calculate_rrf_score(
            dense_rank=None, sparse_rank=1,
            dense_weight=0.5, sparse_weight=0.5,
        )
        assert score == 0.5 / 61

    def test_neither_rank(self):
        score = self.reranker._calculate_rrf_score(
            dense_rank=None, sparse_rank=None,
            dense_weight=0.5, sparse_weight=0.5,
        )
        assert score == 0.0

    def test_higher_rank_lower_score(self):
        """rank=1 should score higher than rank=10."""
        s1 = self.reranker._calculate_rrf_score(1, None, 1.0, 0.0)
        s10 = self.reranker._calculate_rrf_score(10, None, 1.0, 0.0)
        assert s1 > s10

    def test_custom_k(self):
        reranker = RRFReranker(k=10)
        score = reranker._calculate_rrf_score(1, None, 1.0, 0.0)
        assert score == 1.0 / 11


# =============================================================================
# _extract_query_keywords
# =============================================================================


class TestExtractQueryKeywords:
    def setup_method(self):
        self.reranker = RRFReranker()

    def test_extracts_rule_numbers(self):
        kws = self.reranker._extract_query_keywords("rule 15 and rule 16")
        assert "15" in kws
        assert "16" in kws

    def test_extracts_topic_keywords(self):
        kws = self.reranker._extract_query_keywords("crossing situation at sea")
        assert "crossing" in kws

    def test_empty_query(self):
        kws = self.reranker._extract_query_keywords("")
        assert isinstance(kws, set)

    def test_vietnamese_rule(self):
        kws = self.reranker._extract_query_keywords("quy tắc 15")
        assert "15" in kws


# =============================================================================
# _calculate_title_match_boost
# =============================================================================


class TestCalculateTitleMatchBoost:
    def setup_method(self):
        self.reranker = RRFReranker()

    def test_strong_boost_digit(self):
        boost = self.reranker._calculate_title_match_boost(
            "Rule 15 - Crossing Situation", {"15", "crossing"},
        )
        assert boost >= 1.5  # Strong: digit match

    def test_strong_boost_proper_noun(self):
        boost = self.reranker._calculate_title_match_boost(
            "SOLAS Chapter III", {"solas", "chapter"},
        )
        assert boost >= 1.5  # Strong: proper noun match

    def test_weak_boost(self):
        boost = self.reranker._calculate_title_match_boost(
            "Navigation at sea with good visibility", {"navigation", "visibility"},
        )
        assert boost >= 1.0

    def test_no_match(self):
        boost = self.reranker._calculate_title_match_boost(
            "Fire safety procedures", {"navigation", "crossing"},
        )
        assert boost == 1.0

    def test_empty_keywords(self):
        boost = self.reranker._calculate_title_match_boost("Some title", set())
        assert boost == 1.0


# =============================================================================
# merge (end-to-end)
# =============================================================================


class TestMerge:
    def setup_method(self):
        self.reranker = RRFReranker()

    def test_empty_inputs(self):
        results = self.reranker.merge([], [], query="test query")
        assert results == []

    def test_dense_only_results(self):
        dense = [_MockDenseResult(node_id="a", content="Some content", similarity=0.95)]
        results = self.reranker.merge(dense, [], query="test query")
        assert len(results) >= 1
        assert results[0].node_id == "a"

    def test_sparse_only_results(self):
        sparse = [
            _MockSparseResult(
                node_id="b", title="Title", content="Sparse content",
                source="KB", category="Knowledge", score=10.0,
            )
        ]
        results = self.reranker.merge([], sparse, query="test query")
        assert len(results) >= 1
        assert results[0].node_id == "b"

    def test_dedup_same_node_id(self):
        """Same node_id from both searches should appear once."""
        dense = [_MockDenseResult(node_id="x", content="Dense content", similarity=0.9)]
        sparse = [
            _MockSparseResult(
                node_id="x", title="Same", content="Same content",
                source="KB", category="Knowledge", score=8.0,
            )
        ]
        results = self.reranker.merge(dense, sparse, query="query")
        node_ids = [r.node_id for r in results]
        assert node_ids.count("x") == 1

    def test_limit_results(self):
        dense = [
            _MockDenseResult(node_id=f"d{i}", content=f"Dense {i}", similarity=0.9 - i * 0.01)
            for i in range(10)
        ]
        results = self.reranker.merge(dense, [], limit=3, query="query")
        assert len(results) <= 3

    def test_merge_single_source_dense(self):
        dense = [_MockDenseResult(node_id="s1", content="Content", similarity=0.9)]
        result = self.reranker.merge_single_source(dense, source="dense")
        assert len(result) >= 1
        assert result[0].search_method == "dense_only"

    def test_merge_single_source_sparse(self):
        sparse = [
            _MockSparseResult(
                node_id="s2", title="T", content="C",
                source="KB", category="K", score=8.0,
            )
        ]
        result = self.reranker.merge_single_source(sparse, source="sparse")
        assert len(result) >= 1
        assert result[0].search_method == "sparse_only"
