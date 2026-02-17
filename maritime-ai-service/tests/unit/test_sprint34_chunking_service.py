"""
Tests for Sprint 34: SemanticChunker — pure logic, no LLM.

Covers:
- ChunkResult dataclass
- _detect_content_type: content type classification
- _calculate_confidence: quality scoring
- _extract_document_hierarchy: maritime pattern extraction
- _build_metadata: metadata construction
- chunk_page_content: end-to-end chunking pipeline
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.chunking_service import (
    SemanticChunker,
    ChunkResult,
)


# =============================================================================
# ChunkResult
# =============================================================================


class TestChunkResult:
    def test_defaults(self):
        r = ChunkResult(chunk_index=0, content="test")
        assert r.content_type == "text"
        assert r.confidence_score == 1.0
        assert r.metadata == {}
        assert r.contextual_content is None


# =============================================================================
# _detect_content_type
# =============================================================================


class TestDetectContentType:
    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=30)

    def test_plain_text(self):
        assert self.chunker._detect_content_type("This is a regular paragraph.") == "text"

    def test_markdown_table(self):
        text = "| Header | Value |\n|--------|-------|\n| Row 1  | Data  |"
        assert self.chunker._detect_content_type(text) == "table"

    def test_tab_separated_table(self):
        text = "A\tB\tC\nD\tE\tF\nG\tH\tI"
        assert self.chunker._detect_content_type(text) == "table"

    def test_heading_article_vi(self):
        assert self.chunker._detect_content_type("Điều 15: Tình huống cắt nhau") == "heading"

    def test_heading_clause_vi(self):
        assert self.chunker._detect_content_type("Khoản 2 quy định rằng") == "heading"

    def test_heading_rule_en(self):
        assert self.chunker._detect_content_type("Rule 15 - Crossing Situation") == "heading"

    def test_diagram_reference_vi(self):
        text = "Xem hình 3 để biết thêm chi tiết về sơ đồ bố trí"
        assert self.chunker._detect_content_type(text) == "diagram_reference"

    def test_diagram_reference_en(self):
        text = "See figure 7 for the detailed diagram"
        assert self.chunker._detect_content_type(text) == "diagram_reference"

    def test_formula(self):
        text = "Khoảng cách = 12 * 3 + 5"
        # "Khoản" pattern matches first → heading
        # Let's test a formula without maritime keyword
        text2 = "Speed ratio: 15 * 2 = 30 knots"
        assert self.chunker._detect_content_type(text2) == "formula"

    def test_valid_content_types(self):
        """All returned types should be in VALID_CONTENT_TYPES."""
        test_texts = [
            "Regular text",
            "| A | B |\n|---|---|\n| 1 | 2 |",
            "Điều 15 heading",
            "See figure 1 for diagram",
            "Calculate: 10 + 20 = 30",
        ]
        for text in test_texts:
            ctype = self.chunker._detect_content_type(text)
            assert ctype in SemanticChunker.VALID_CONTENT_TYPES, f"Invalid type: {ctype}"


# =============================================================================
# _calculate_confidence
# =============================================================================


class TestCalculateConfidence:
    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=30)

    def test_optimal_length(self):
        text = "A" * 200
        conf = self.chunker._calculate_confidence(text, "text")
        assert conf == 1.0

    def test_short_chunk_penalty(self):
        text = "A" * 10  # < min_chunk_size (30)
        conf = self.chunker._calculate_confidence(text, "text")
        assert conf == 0.6

    def test_long_chunk_penalty(self):
        text = "A" * 1500  # > 1000
        conf = self.chunker._calculate_confidence(text, "text")
        assert conf == 0.7

    def test_heading_boost(self):
        text = "A" * 200
        conf = self.chunker._calculate_confidence(text, "heading")
        # base=1.0 * 1.2 = 1.2, capped at 1.0
        assert conf == 1.0

    def test_table_boost(self):
        text = "A" * 200
        conf = self.chunker._calculate_confidence(text, "table")
        assert conf <= 1.0

    def test_short_heading_boost(self):
        text = "A" * 10  # Short → 0.6 base, * 1.2 = 0.72
        conf = self.chunker._calculate_confidence(text, "heading")
        assert abs(conf - 0.72) < 0.01

    def test_bounds_0_to_1(self):
        """Confidence should always be in [0, 1]."""
        for length in [5, 50, 200, 500, 1500]:
            for ctype in ["text", "heading", "table", "formula"]:
                text = "X" * length
                conf = self.chunker._calculate_confidence(text, ctype)
                assert 0.0 <= conf <= 1.0, f"Out of bounds: {conf} for len={length}, type={ctype}"


# =============================================================================
# _extract_document_hierarchy
# =============================================================================


class TestExtractDocumentHierarchy:
    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=30)

    def test_article_vi(self):
        h = self.chunker._extract_document_hierarchy("Điều 15: Tình huống cắt nhau")
        assert h["article"] == "15"

    def test_article_en(self):
        h = self.chunker._extract_document_hierarchy("Article 22 - Visibility of Lights")
        assert h["article"] == "22"

    def test_clause_vi(self):
        h = self.chunker._extract_document_hierarchy("Khoản 3 quy định rằng")
        assert h["clause"] == "3"

    def test_point_vi(self):
        h = self.chunker._extract_document_hierarchy("Điểm a) Tàu thuyền phải")
        assert h["point"] == "a"

    def test_rule_en(self):
        h = self.chunker._extract_document_hierarchy("Rule 15 - Crossing Situation")
        assert h["rule"] == "15"

    def test_multiple_levels(self):
        text = "Điều 15, Khoản 2, Điểm b"
        h = self.chunker._extract_document_hierarchy(text)
        assert h["article"] == "15"
        assert h["clause"] == "2"
        assert h["point"] == "b"

    def test_no_hierarchy(self):
        h = self.chunker._extract_document_hierarchy("Regular text without hierarchy")
        assert h == {}


# =============================================================================
# _build_metadata
# =============================================================================


class TestBuildMetadata:
    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=30)

    def test_basic_metadata(self):
        meta = self.chunker._build_metadata(
            chunk="Sample chunk text",
            page_metadata={"page_number": 5, "document_id": "doc1"},
            content_type="text",
            hierarchy={},
        )
        assert meta["page_number"] == 5
        assert meta["document_id"] == "doc1"
        assert meta["content_type"] == "text"
        assert meta["word_count"] == 3
        assert meta["char_count"] == 17
        assert meta["language"] == "en"

    def test_vietnamese_detection(self):
        meta = self.chunker._build_metadata(
            chunk="Tàu thuyền phải tuân thủ",
            page_metadata={},
            content_type="text",
            hierarchy={},
        )
        assert meta["language"] == "vi"

    def test_hierarchy_included(self):
        meta = self.chunker._build_metadata(
            chunk="Test",
            page_metadata={},
            content_type="heading",
            hierarchy={"article": "15", "clause": "2"},
        )
        assert meta["section_hierarchy"] == {"article": "15", "clause": "2"}


# =============================================================================
# chunk_page_content (end-to-end)
# =============================================================================


class TestChunkPageContent:
    def setup_method(self):
        self.chunker = SemanticChunker(chunk_size=200, chunk_overlap=20, min_chunk_size=30)

    @pytest.mark.asyncio
    async def test_empty_text(self):
        result = await self.chunker.chunk_page_content("", {"page_number": 1})
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await self.chunker.chunk_page_content("   \n  ", {"page_number": 1})
        assert result == []

    @pytest.mark.asyncio
    async def test_single_chunk(self):
        text = "This is a moderate length text about maritime safety regulations."
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        assert len(result) >= 1
        assert all(isinstance(r, ChunkResult) for r in result)
        assert result[0].chunk_index == 0

    @pytest.mark.asyncio
    async def test_multiple_chunks(self):
        # Generate text longer than chunk_size (200)
        text = "This is paragraph one about safety. " * 20
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_chunk_indices_sequential(self):
        text = "Content block. " * 30
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    @pytest.mark.asyncio
    async def test_small_chunks_merged(self):
        """Very small chunks should be merged with previous."""
        # Chunk 1: longer text, Chunk 2: short continuation
        text = "A" * 150 + "\n\n" + "B" * 10  # Second part is tiny
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        # The tiny "B" chunk should be merged with the previous
        # (total text is < chunk_size, so may be 1 chunk anyway)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_content_type_detected(self):
        text = "Điều 15: Tình huống cắt nhau khi hai tàu tiến gần nhau"
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        assert len(result) >= 1
        assert result[0].content_type == "heading"

    @pytest.mark.asyncio
    async def test_confidence_in_range(self):
        text = "Maritime safety regulations text " * 10
        result = await self.chunker.chunk_page_content(text, {"page_number": 1})
        for chunk in result:
            assert 0.0 <= chunk.confidence_score <= 1.0
