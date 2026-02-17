"""
Tests for Sprint 30: ChatResponseBuilder coverage.

Covers:
- merge_same_page_sources: grouping, dedup, bounding boxes, content merge
- format_sources_for_api: conversion to SourceInfo
- build_response: full pipeline with merge/no-merge options
"""

import pytest
from app.services.chat_response_builder import ChatResponseBuilder, FormattedResponse


@pytest.fixture
def builder():
    return ChatResponseBuilder()


# =============================================================================
# merge_same_page_sources
# =============================================================================


class TestMergeSamePageSources:
    """Test source merging logic."""

    def test_empty_sources(self, builder):
        assert builder.merge_same_page_sources([]) == []

    def test_single_source_unchanged(self, builder):
        sources = [{"document_id": "doc1", "page_number": 1, "content": "Hello"}]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert result[0]["content"] == "Hello"

    def test_different_pages_not_merged(self, builder):
        sources = [
            {"document_id": "doc1", "page_number": 1, "content": "Page 1"},
            {"document_id": "doc1", "page_number": 2, "content": "Page 2"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 2

    def test_same_page_merged(self, builder):
        sources = [
            {"document_id": "doc1", "page_number": 5, "content": "First chunk"},
            {"document_id": "doc1", "page_number": 5, "content": "Second chunk"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert "First chunk" in result[0]["content"]
        assert "Second chunk" in result[0]["content"]

    def test_bounding_boxes_combined(self, builder):
        sources = [
            {"document_id": "d1", "page_number": 1, "content": "A",
             "bounding_boxes": [{"x": 0, "y": 0}]},
            {"document_id": "d1", "page_number": 1, "content": "B",
             "bounding_boxes": [{"x": 100, "y": 100}]},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert len(result[0]["bounding_boxes"]) == 2

    def test_image_url_from_first_valid(self, builder):
        sources = [
            {"document_id": "d1", "page_number": 1, "content": "A", "image_url": None},
            {"document_id": "d1", "page_number": 1, "content": "B", "image_url": "http://img.png"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert result[0]["image_url"] == "http://img.png"

    def test_different_documents_not_merged(self, builder):
        sources = [
            {"document_id": "doc1", "page_number": 1, "content": "Doc 1"},
            {"document_id": "doc2", "page_number": 1, "content": "Doc 2"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 2

    def test_sorted_by_document_then_page(self, builder):
        sources = [
            {"document_id": "b", "page_number": 3, "content": "B3"},
            {"document_id": "a", "page_number": 1, "content": "A1"},
            {"document_id": "a", "page_number": 2, "content": "A2"},
        ]
        result = builder.merge_same_page_sources(sources)
        assert result[0]["document_id"] == "a"
        assert result[0]["page_number"] == 1
        assert result[-1]["document_id"] == "b"

    def test_missing_fields_use_defaults(self, builder):
        sources = [{"content": "No doc or page"}]
        result = builder.merge_same_page_sources(sources)
        assert len(result) == 1
        assert result[0]["document_id"] == ""
        assert result[0]["page_number"] == 0

    def test_none_bounding_boxes_treated_as_empty(self, builder):
        sources = [
            {"document_id": "d1", "page_number": 1, "content": "A",
             "bounding_boxes": None},
        ]
        result = builder.merge_same_page_sources(sources)
        assert result[0]["bounding_boxes"] == []


# =============================================================================
# format_sources_for_api
# =============================================================================


class TestFormatSourcesForApi:
    """Test conversion to SourceInfo objects."""

    def test_empty_list(self, builder):
        assert builder.format_sources_for_api([]) == []

    def test_formats_single_source(self, builder):
        sources = [{"title": "T", "content": "C", "page_number": 1,
                     "document_id": "d1"}]
        result = builder.format_sources_for_api(sources)
        assert len(result) == 1
        assert result[0].title == "T"
        assert result[0].content == "C"
        assert result[0].page_number == 1

    def test_missing_fields_default(self, builder):
        sources = [{}]
        result = builder.format_sources_for_api(sources)
        assert result[0].title == ""
        assert result[0].page_number == 0


# =============================================================================
# build_response
# =============================================================================


class TestBuildResponse:
    """Test full response building."""

    def test_basic_message(self, builder):
        result = builder.build_response("Hello")
        assert isinstance(result, FormattedResponse)
        assert result.message == "Hello"
        assert result.sources == []
        assert result.suggested_questions == []

    def test_with_sources_merged(self, builder):
        sources = [
            {"document_id": "d1", "page_number": 1, "content": "A",
             "title": "Doc"},
            {"document_id": "d1", "page_number": 1, "content": "B",
             "title": "Doc"},
        ]
        result = builder.build_response("msg", sources=sources, merge_sources=True)
        assert len(result.sources) == 1

    def test_with_sources_no_merge(self, builder):
        sources = [
            {"document_id": "d1", "page_number": 1, "content": "A"},
            {"document_id": "d1", "page_number": 1, "content": "B"},
        ]
        result = builder.build_response("msg", sources=sources, merge_sources=False)
        assert len(result.sources) == 2

    def test_with_suggested_questions(self, builder):
        result = builder.build_response("msg",
                                        suggested_questions=["Q1?", "Q2?"])
        assert result.suggested_questions == ["Q1?", "Q2?"]

    def test_with_tools_and_topics(self, builder):
        result = builder.build_response(
            "msg",
            tools_used=[{"name": "search"}],
            topics=["colregs"],
        )
        assert result.tools_used == [{"name": "search"}]
        assert result.topics == ["colregs"]

    def test_none_sources(self, builder):
        result = builder.build_response("msg", sources=None)
        assert result.sources == []


# =============================================================================
# FormattedResponse dataclass
# =============================================================================


class TestFormattedResponse:
    """Test the response dataclass."""

    def test_defaults(self):
        resp = FormattedResponse(message="Hi")
        assert resp.message == "Hi"
        assert resp.sources == []
        assert resp.suggested_questions == []
        assert resp.tools_used == []
        assert resp.topics == []
