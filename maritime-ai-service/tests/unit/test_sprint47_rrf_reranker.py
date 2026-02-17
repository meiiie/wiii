"""
Tests for Sprint 47: RRFReranker coverage.

Tests Reciprocal Rank Fusion including:
- HybridSearchResult dataclass (appears_in_both, has_document_hierarchy, has_bounding_boxes)
- RRFReranker init
- _calculate_rrf_score (dense only, sparse only, both, neither)
- _extract_query_keywords (rule numbers, topics, chapters)
- _calculate_title_match_boost (strong, medium, weak, no match)
- merge (basic, deduplication, title boost, sparse priority boost)
- merge_single_source (dense, sparse)
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# HybridSearchResult
# ============================================================================


class TestHybridSearchResult:
    """Test HybridSearchResult dataclass."""

    def test_default_values(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="Title", content="Content", source="KB", category="Knowledge")
        assert r.rrf_score == 0.0
        assert r.search_method == "hybrid"
        assert r.dense_score is None
        assert r.sparse_score is None

    def test_appears_in_both_true(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K",
                               dense_score=0.9, sparse_score=5.0)
        assert r.appears_in_both() is True

    def test_appears_in_both_false(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K",
                               dense_score=0.9, sparse_score=None)
        assert r.appears_in_both() is False

    def test_has_document_hierarchy(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K",
                               section_hierarchy={"article": "15"})
        assert r.has_document_hierarchy() is True

    def test_no_document_hierarchy(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K")
        assert r.has_document_hierarchy() is False

    def test_has_bounding_boxes(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K",
                               bounding_boxes=[{"x": 0, "y": 0}])
        assert r.has_bounding_boxes() is True

    def test_no_bounding_boxes(self):
        from app.engine.rrf_reranker import HybridSearchResult
        r = HybridSearchResult(node_id="n1", title="T", content="C", source="S", category="K")
        assert r.has_bounding_boxes() is False


# ============================================================================
# RRFReranker init
# ============================================================================


class TestRRFRerankerInit:
    """Test RRFReranker initialization."""

    def test_default_k(self):
        from app.engine.rrf_reranker import RRFReranker
        reranker = RRFReranker()
        assert reranker.k == 60

    def test_custom_k(self):
        from app.engine.rrf_reranker import RRFReranker
        reranker = RRFReranker(k=30)
        assert reranker.k == 30


# ============================================================================
# _calculate_rrf_score
# ============================================================================


class TestCalculateRRFScore:
    """Test RRF score calculation."""

    @pytest.fixture
    def reranker(self):
        from app.engine.rrf_reranker import RRFReranker
        return RRFReranker(k=60)

    def test_dense_only(self, reranker):
        score = reranker._calculate_rrf_score(dense_rank=1, sparse_rank=None, dense_weight=0.5, sparse_weight=0.5)
        assert abs(score - 0.5 / 61) < 0.0001

    def test_sparse_only(self, reranker):
        score = reranker._calculate_rrf_score(dense_rank=None, sparse_rank=1, dense_weight=0.5, sparse_weight=0.5)
        assert abs(score - 0.5 / 61) < 0.0001

    def test_both(self, reranker):
        score = reranker._calculate_rrf_score(dense_rank=1, sparse_rank=1, dense_weight=0.5, sparse_weight=0.5)
        expected = 0.5 / 61 + 0.5 / 61
        assert abs(score - expected) < 0.0001

    def test_neither(self, reranker):
        score = reranker._calculate_rrf_score(dense_rank=None, sparse_rank=None, dense_weight=0.5, sparse_weight=0.5)
        assert score == 0.0

    def test_higher_rank_lower_score(self, reranker):
        """Lower rank (higher number) should produce lower score."""
        score1 = reranker._calculate_rrf_score(dense_rank=1, sparse_rank=None, dense_weight=1.0, sparse_weight=0)
        score10 = reranker._calculate_rrf_score(dense_rank=10, sparse_rank=None, dense_weight=1.0, sparse_weight=0)
        assert score1 > score10


# ============================================================================
# _extract_query_keywords
# ============================================================================


class TestExtractQueryKeywords:
    """Test keyword extraction from queries."""

    @pytest.fixture
    def reranker(self):
        from app.engine.rrf_reranker import RRFReranker
        return RRFReranker()

    def test_rule_number(self, reranker):
        keywords = reranker._extract_query_keywords("What is Rule 15?")
        assert "15" in keywords
        assert "rule 15" in keywords

    def test_vn_rule(self, reranker):
        keywords = reranker._extract_query_keywords("quy tắc 19 là gì?")
        assert "19" in keywords

    def test_chapter(self, reranker):
        keywords = reranker._extract_query_keywords("chapter ii-1 requirements")
        assert "ii-1" in keywords

    def test_topic_keywords(self, reranker):
        keywords = reranker._extract_query_keywords("crossing situation rules")
        assert "crossing" in keywords

    def test_no_keywords(self, reranker):
        keywords = reranker._extract_query_keywords("hello")
        assert len(keywords) == 0


# ============================================================================
# _calculate_title_match_boost
# ============================================================================


class TestCalculateTitleMatchBoost:
    """Test title match boosting."""

    @pytest.fixture
    def reranker(self):
        from app.engine.rrf_reranker import RRFReranker
        return RRFReranker()

    def test_no_keywords(self, reranker):
        assert reranker._calculate_title_match_boost("Rule 15", set()) == 1.0

    def test_empty_title(self, reranker):
        assert reranker._calculate_title_match_boost("", {"15"}) == 1.0

    def test_strong_boost_digit(self, reranker):
        boost = reranker._calculate_title_match_boost("Rule 15 - Crossing", {"15", "crossing"})
        assert boost == 3.0  # Strong: digit + another match

    def test_medium_boost_single_digit(self, reranker):
        boost = reranker._calculate_title_match_boost("Rule 15", {"15"})
        assert boost == 1.5  # Medium: one digit match

    def test_proper_noun_boost(self, reranker):
        # "colregs" is proper noun (strong), "chapter" matches title (weak) → total=2, strong>=1 → 3.0
        boost = reranker._calculate_title_match_boost("COLREGs Chapter V", {"colregs", "chapter"})
        assert boost == 3.0  # Strong: proper noun + another match in title

    def test_weak_boost(self, reranker):
        boost = reranker._calculate_title_match_boost("Crossing situation and visibility", {"crossing", "visibility"})
        assert boost == 1.1  # Weak: two common words

    def test_no_match(self, reranker):
        boost = reranker._calculate_title_match_boost("Navigation lights", {"crossing"})
        assert boost == 1.0


# ============================================================================
# merge
# ============================================================================


class TestMerge:
    """Test RRF merge of dense and sparse results."""

    @pytest.fixture
    def reranker(self):
        from app.engine.rrf_reranker import RRFReranker
        return RRFReranker(k=60)

    def test_merge_basic(self, reranker):
        dense = [_make_dense_result("n1", "Content about Rule 15", 0.9)]
        sparse = [_make_sparse_result("n2", "Rule 15 Title", "Sparse content", 5.0)]
        results = reranker.merge(dense, sparse, limit=5)
        assert len(results) == 2

    def test_merge_deduplication(self, reranker):
        """Same node_id in both should merge."""
        dense = [_make_dense_result("n1", "Content", 0.9)]
        sparse = [_make_sparse_result("n1", "Title", "Content", 5.0)]
        results = reranker.merge(dense, sparse, limit=5)
        assert len(results) == 1
        assert results[0].appears_in_both()

    def test_merge_with_title_boost(self, reranker):
        dense = [
            _make_dense_result("n1", "Rule 15 crossing situation", 0.8),
            _make_dense_result("n2", "Navigation lights", 0.85),
        ]
        sparse = []
        results = reranker.merge(dense, sparse, dense_weight=1.0, sparse_weight=0, limit=5, query="Rule 15")
        # n1 should be boosted due to title match
        assert results[0].node_id == "n1"

    def test_merge_limit(self, reranker):
        dense = [_make_dense_result(f"n{i}", f"Content {i}", 0.9 - i * 0.01) for i in range(10)]
        sparse = []
        results = reranker.merge(dense, sparse, limit=3)
        assert len(results) == 3

    def test_merge_empty_inputs(self, reranker):
        results = reranker.merge([], [], limit=5)
        assert results == []

    def test_merge_sparse_priority_boost(self, reranker):
        """High sparse scores should get priority boost."""
        dense = [_make_dense_result("n1", "Content", 0.9)]
        sparse = [_make_sparse_result("n2", "Title", "Content", 20.0)]  # > SPARSE_PRIORITY_THRESHOLD
        results = reranker.merge(dense, sparse, limit=5)
        # n2 should get sparse priority boost
        boosted = [r for r in results if r.node_id == "n2"]
        assert len(boosted) == 1


# ============================================================================
# merge_single_source
# ============================================================================


class TestMergeSingleSource:
    """Test single-source conversion."""

    @pytest.fixture
    def reranker(self):
        from app.engine.rrf_reranker import RRFReranker
        return RRFReranker()

    def test_dense_source(self, reranker):
        dense = [_make_dense_result("n1", "Content about Rule 15", 0.9)]
        results = reranker.merge_single_source(dense, "dense", limit=5)
        assert len(results) == 1
        assert results[0].search_method == "dense_only"
        assert results[0].dense_score == 0.9
        assert results[0].sparse_score is None

    def test_sparse_source(self, reranker):
        sparse = [_make_sparse_result("n1", "Title", "Content", 5.0)]
        results = reranker.merge_single_source(sparse, "sparse", limit=5)
        assert len(results) == 1
        assert results[0].search_method == "sparse_only"
        assert results[0].sparse_score == 5.0
        assert results[0].rrf_score == 0.5  # 5.0 / 10

    def test_limit_applied(self, reranker):
        dense = [_make_dense_result(f"n{i}", f"Content {i}", 0.9) for i in range(10)]
        results = reranker.merge_single_source(dense, "dense", limit=3)
        assert len(results) == 3


# ============================================================================
# Helpers
# ============================================================================


def _make_dense_result(node_id, content, similarity):
    r = MagicMock()
    r.node_id = node_id
    r.content = content
    r.similarity = similarity
    r.content_type = "text"
    r.confidence_score = 1.0
    r.page_number = 0
    r.chunk_index = 0
    r.image_url = ""
    r.document_id = ""
    r.section_hierarchy = {}
    r.bounding_boxes = None
    return r


def _make_sparse_result(node_id, title, content, score):
    r = MagicMock()
    r.node_id = node_id
    r.title = title
    r.content = content
    r.source = "KB"
    r.category = "Knowledge"
    r.score = score
    r.image_url = ""
    r.page_number = 0
    r.document_id = ""
    r.bounding_boxes = None
    return r
