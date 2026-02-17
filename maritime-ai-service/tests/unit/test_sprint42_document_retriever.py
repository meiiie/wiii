"""
Tests for Sprint 42: DocumentRetriever coverage.

Tests document retrieval logic including:
- HybridSearchResult to KnowledgeNode conversion
- Title hierarchy formatting
- Citation generation
- Document dict conversion
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# format_title_with_hierarchy
# ============================================================================


class TestFormatTitleWithHierarchy:
    """Test title formatting with document hierarchy."""

    def test_no_hierarchy(self):
        """Empty hierarchy returns original title."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = {}
        assert DocumentRetriever.format_title_with_hierarchy("Original", result) == "Original"

    def test_none_hierarchy(self):
        """None hierarchy returns original title."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = None
        assert DocumentRetriever.format_title_with_hierarchy("Original", result) == "Original"

    def test_article_hierarchy(self):
        """Article in hierarchy adds Dieu prefix."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = {"article": "15"}
        title = DocumentRetriever.format_title_with_hierarchy("Safety Rule", result)
        assert "15" in title
        assert "Safety Rule" in title

    def test_article_and_clause(self):
        """Article + clause in hierarchy."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = {"article": "15", "clause": "2"}
        title = DocumentRetriever.format_title_with_hierarchy("Rule", result)
        assert "15" in title
        assert "2" in title

    def test_rule_hierarchy(self):
        """Rule in hierarchy adds Rule prefix."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = {"rule": "19"}
        title = DocumentRetriever.format_title_with_hierarchy("Content", result)
        assert "Rule 19" in title

    def test_no_duplicate_hierarchy(self):
        """Doesn't add hierarchy if already in title."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        result = MagicMock()
        result.section_hierarchy = {"rule": "15"}
        title = DocumentRetriever.format_title_with_hierarchy("Rule 15 content", result)
        # Should not double-add
        assert title.count("Rule 15") == 1


# ============================================================================
# hybrid_results_to_nodes
# ============================================================================


class TestHybridResultsToNodes:
    """Test HybridSearchResult to KnowledgeNode conversion."""

    def _make_result(self, **overrides):
        """Create a HybridSearchResult mock."""
        from app.engine.rrf_reranker import HybridSearchResult
        defaults = {
            "node_id": "n1",
            "content": "Test content",
            "title": "Test Title",
            "source": "test.pdf",
            "category": "Regulation",
            "rrf_score": 0.8,
            "dense_score": 0.7,
            "sparse_score": 0.6,
            "search_method": "hybrid",
            "page_number": 1,
            "document_id": "doc1",
            "image_url": None,
            "content_type": "text",
            "confidence_score": 0.9,
            "chunk_index": 0,
            "section_hierarchy": {},
            "bounding_boxes": None,
        }
        defaults.update(overrides)
        return HybridSearchResult(**defaults)

    def test_basic_conversion(self):
        """Basic conversion from HybridSearchResult to KnowledgeNode."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [self._make_result()]
        nodes = DocumentRetriever.hybrid_results_to_nodes(results)
        assert len(nodes) == 1
        assert nodes[0].id == "n1"
        assert nodes[0].content == "Test content"

    def test_skips_empty_content(self):
        """Skips results with empty title or content."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [
            self._make_result(title="", content="valid"),
            self._make_result(title="valid", content=""),
            self._make_result(title="valid", content="valid"),
        ]
        nodes = DocumentRetriever.hybrid_results_to_nodes(results)
        assert len(nodes) == 1

    def test_metadata_preserved(self):
        """Metadata from search result is preserved in node."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [self._make_result(rrf_score=0.95, page_number=5)]
        nodes = DocumentRetriever.hybrid_results_to_nodes(results)
        assert nodes[0].metadata["rrf_score"] == 0.95
        assert nodes[0].metadata["page_number"] == 5

    def test_empty_results_returns_empty(self):
        """Empty input returns empty list."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        nodes = DocumentRetriever.hybrid_results_to_nodes([])
        assert nodes == []


# ============================================================================
# generate_hybrid_citations
# ============================================================================


class TestGenerateHybridCitations:
    """Test citation generation from hybrid results."""

    def _make_result(self, **overrides):
        from app.engine.rrf_reranker import HybridSearchResult
        defaults = {
            "node_id": "n1", "content": "Content", "title": "Title",
            "source": "source.pdf", "category": "Regulation", "rrf_score": 0.8,
            "dense_score": 0.7, "sparse_score": 0.6, "search_method": "hybrid",
            "page_number": 1, "document_id": "doc1", "image_url": None,
            "content_type": "text", "confidence_score": 0.9, "chunk_index": 0,
            "section_hierarchy": {}, "bounding_boxes": None,
        }
        defaults.update(overrides)
        return HybridSearchResult(**defaults)

    def test_basic_citation(self):
        """Basic citation generation."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [self._make_result(node_id="n1", source="doc.pdf", rrf_score=0.9)]
        citations = DocumentRetriever.generate_hybrid_citations(results)
        assert len(citations) == 1
        assert citations[0].node_id == "n1"
        assert citations[0].relevance_score == 0.9

    def test_table_content_type_emoji(self):
        """Table content type gets chart emoji in title."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [self._make_result(content_type="table")]
        citations = DocumentRetriever.generate_hybrid_citations(results)
        assert "\U0001F4CA" in citations[0].title  # chart emoji

    def test_heading_content_type_emoji(self):
        """Heading content type gets page emoji in title."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        results = [self._make_result(content_type="heading")]
        citations = DocumentRetriever.generate_hybrid_citations(results)
        assert "\U0001F4D1" in citations[0].title

    def test_empty_results(self):
        """Empty results produces no citations."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        citations = DocumentRetriever.generate_hybrid_citations([])
        assert citations == []


# ============================================================================
# documents_to_nodes and documents_to_citations
# ============================================================================


class TestDocumentConversions:
    """Test document dict to node/citation conversion."""

    def test_documents_to_nodes_basic(self):
        """Convert document dicts to KnowledgeNodes."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        docs = [
            {"node_id": "n1", "title": "Doc 1", "content": "Content 1", "document_id": "d1"},
            {"node_id": "n2", "title": "Doc 2", "content": "Content 2", "document_id": "d2"},
        ]
        nodes = DocumentRetriever.documents_to_nodes(docs)
        assert len(nodes) == 2
        assert nodes[0].id == "n1"
        assert nodes[1].content == "Content 2"

    def test_documents_to_nodes_defaults(self):
        """Documents with missing fields get defaults."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        docs = [{}]
        nodes = DocumentRetriever.documents_to_nodes(docs)
        assert len(nodes) == 1
        assert nodes[0].id == "doc_0"
        assert nodes[0].title == "Document 1"

    def test_documents_to_citations_basic(self):
        """Convert document dicts to Citations."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        docs = [
            {"node_id": "n1", "title": "Title", "score": 0.9, "document_id": "d1"},
        ]
        citations = DocumentRetriever.documents_to_citations(docs)
        assert len(citations) == 1
        assert citations[0].node_id == "n1"
        assert citations[0].relevance_score == 0.9

    def test_documents_to_citations_empty(self):
        """Empty docs list."""
        from app.engine.agentic_rag.document_retriever import DocumentRetriever
        assert DocumentRetriever.documents_to_citations([]) == []
