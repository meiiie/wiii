"""
Tests for Sprint 48: ChatResponseBuilder coverage.

Tests response building including:
- FormattedResponse dataclass
- merge_same_page_sources (empty, single, merge, sort)
- format_sources_for_api
- build_response (basic, with sources, merge toggle, all fields)
- Singleton via singleton_factory
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# FormattedResponse
# ============================================================================


class TestFormattedResponse:
    """Test FormattedResponse dataclass."""

    def test_defaults(self):
        from app.services.chat_response_builder import FormattedResponse
        r = FormattedResponse(message="Hello")
        assert r.message == "Hello"
        assert r.sources == []
        assert r.suggested_questions == []
        assert r.tools_used == []
        assert r.topics == []


# ============================================================================
# merge_same_page_sources
# ============================================================================


class TestMergeSamePageSources:
    """Test source merging logic."""

    @pytest.fixture
    def builder(self):
        from app.services.chat_response_builder import ChatResponseBuilder
        return ChatResponseBuilder()

    def test_empty(self, builder):
        assert builder.merge_same_page_sources([]) == []

    def test_single_source(self, builder):
        sources = [{"title": "T", "content": "C", "page_number": 1, "document_id": "d1", "bounding_boxes": []}]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert result[0]["title"] == "T"

    def test_merge_same_page(self, builder):
        sources = [
            {"title": "T1", "content": "Content A", "page_number": 5, "document_id": "doc1",
             "bounding_boxes": [{"x": 0}], "image_url": "img1.png", "node_id": "n1"},
            {"title": "T2", "content": "Content B", "page_number": 5, "document_id": "doc1",
             "bounding_boxes": [{"x": 100}], "image_url": None, "node_id": "n2"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert "Content A" in result[0]["content"]
        assert "Content B" in result[0]["content"]
        assert len(result[0]["bounding_boxes"]) == 2
        assert result[0]["image_url"] == "img1.png"

    def test_different_pages_not_merged(self, builder):
        sources = [
            {"title": "T1", "content": "C1", "page_number": 1, "document_id": "d1", "bounding_boxes": []},
            {"title": "T2", "content": "C2", "page_number": 2, "document_id": "d1", "bounding_boxes": []},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 2

    def test_different_docs_not_merged(self, builder):
        sources = [
            {"title": "T1", "content": "C1", "page_number": 1, "document_id": "d1", "bounding_boxes": []},
            {"title": "T2", "content": "C2", "page_number": 1, "document_id": "d2", "bounding_boxes": []},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 2

    def test_sorted_by_doc_and_page(self, builder):
        sources = [
            {"title": "T", "content": "C", "page_number": 3, "document_id": "b", "bounding_boxes": []},
            {"title": "T", "content": "C", "page_number": 1, "document_id": "a", "bounding_boxes": []},
            {"title": "T", "content": "C", "page_number": 2, "document_id": "a", "bounding_boxes": []},
        ]
        result = builder.merge_same_page_sources(sources)
        pages = [(r["document_id"], r["page_number"]) for r in result]
        assert pages == [("a", 1), ("a", 2), ("b", 3)]

    def test_merge_uses_first_image(self, builder):
        """Second source's image_url fills in if first is None."""
        sources = [
            {"title": "T", "content": "C1", "page_number": 1, "document_id": "d1",
             "bounding_boxes": [], "image_url": None, "node_id": "n1"},
            {"title": "T", "content": "C2", "page_number": 1, "document_id": "d1",
             "bounding_boxes": [], "image_url": "img2.png", "node_id": "n2"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert result[0]["image_url"] == "img2.png"

    def test_merge_none_bounding_boxes(self, builder):
        sources = [
            {"title": "T", "content": "C", "page_number": 1, "document_id": "d1",
             "bounding_boxes": None, "image_url": None, "node_id": "n1"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert result[0]["bounding_boxes"] == []


# ============================================================================
# format_sources_for_api
# ============================================================================


class TestFormatSourcesForApi:
    """Test API source formatting."""

    @pytest.fixture
    def builder(self):
        from app.services.chat_response_builder import ChatResponseBuilder
        return ChatResponseBuilder()

    def test_formats_to_source_info(self, builder):
        sources = [
            {"title": "Title", "content": "Content", "page_number": 1,
             "document_id": "doc1", "image_url": "img.png", "bounding_boxes": [{"x": 0}]}
        ]
        result = builder.format_sources_for_api(sources)
        assert len(result) == 1
        from app.models.schemas import SourceInfo
        assert isinstance(result[0], SourceInfo)
        assert result[0].title == "Title"
        assert result[0].page_number == 1

    def test_empty_list(self, builder):
        result = builder.format_sources_for_api([])
        assert result == []

    def test_missing_fields_use_defaults(self, builder):
        sources = [{}]
        result = builder.format_sources_for_api(sources)
        assert result[0].title == ""
        assert result[0].page_number == 0


# ============================================================================
# build_response
# ============================================================================


class TestBuildResponse:
    """Test response building."""

    @pytest.fixture
    def builder(self):
        from app.services.chat_response_builder import ChatResponseBuilder
        return ChatResponseBuilder()

    def test_basic_response(self, builder):
        resp = builder.build_response(message="Hello world")
        assert resp.message == "Hello world"
        assert resp.sources == []
        assert resp.suggested_questions == []

    def test_with_sources_merged(self, builder):
        sources = [
            {"title": "T", "content": "C1", "page_number": 1, "document_id": "d1",
             "bounding_boxes": [], "image_url": None, "node_id": "n1"},
            {"title": "T", "content": "C2", "page_number": 1, "document_id": "d1",
             "bounding_boxes": [], "image_url": None, "node_id": "n2"},
        ]
        resp = builder.build_response(message="Answer", sources=sources, merge_sources=True)
        assert len(resp.sources) == 1  # Merged

    def test_with_sources_not_merged(self, builder):
        sources = [
            {"title": "T1", "content": "C1", "page_number": 1, "document_id": "d1"},
            {"title": "T2", "content": "C2", "page_number": 1, "document_id": "d1"},
        ]
        resp = builder.build_response(message="Answer", sources=sources, merge_sources=False)
        assert len(resp.sources) == 2

    def test_all_fields(self, builder):
        resp = builder.build_response(
            message="Answer",
            tools_used=[{"name": "search"}],
            topics=["colregs"],
            suggested_questions=["What about Rule 15?"]
        )
        assert resp.tools_used == [{"name": "search"}]
        assert resp.topics == ["colregs"]
        assert resp.suggested_questions == ["What about Rule 15?"]

    def test_no_sources_gives_empty_list(self, builder):
        resp = builder.build_response(message="Hi", sources=None)
        assert resp.sources == []


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton via singleton_factory."""

    def test_get_chat_response_builder(self):
        from app.services.chat_response_builder import get_chat_response_builder
        b1 = get_chat_response_builder()
        b2 = get_chat_response_builder()
        assert b1 is b2
