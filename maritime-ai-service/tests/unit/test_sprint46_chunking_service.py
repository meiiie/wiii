"""
Tests for Sprint 46: SemanticChunker coverage.

Tests semantic chunking including:
- ChunkResult dataclass
- SemanticChunker initialization
- chunk_page_content (empty, basic, merge small chunks)
- _detect_content_type (text, table, heading, diagram, formula)
- _calculate_confidence (short, long, optimal, structured boost)
- _extract_document_hierarchy (article, clause, point, rule)
- _build_metadata (Vietnamese detection, page metadata)
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# ChunkResult
# ============================================================================


class TestChunkResult:
    """Test ChunkResult dataclass."""

    def test_default_values(self):
        from app.services.chunking_service import ChunkResult
        chunk = ChunkResult(chunk_index=0, content="Test content")
        assert chunk.chunk_index == 0
        assert chunk.content_type == "text"
        assert chunk.confidence_score == 1.0
        assert chunk.metadata == {}
        assert chunk.contextual_content is None

    def test_custom_values(self):
        from app.services.chunking_service import ChunkResult
        chunk = ChunkResult(
            chunk_index=3,
            content="Table data",
            content_type="table",
            confidence_score=0.85,
            metadata={"page": 1}
        )
        assert chunk.content_type == "table"
        assert chunk.confidence_score == 0.85


# ============================================================================
# SemanticChunker init
# ============================================================================


class TestSemanticChunkerInit:
    """Test SemanticChunker initialization."""

    def test_default_from_settings(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            chunker = SemanticChunker()
            assert chunker.chunk_size == 500
            assert chunker.chunk_overlap == 50
            assert chunker.min_chunk_size == 100

    def test_custom_params(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            chunker = SemanticChunker(chunk_size=1000, chunk_overlap=100, min_chunk_size=200)
            assert chunker.chunk_size == 1000
            assert chunker.chunk_overlap == 100
            assert chunker.min_chunk_size == 200

    def test_valid_content_types(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            chunker = SemanticChunker()
            assert "text" in chunker.VALID_CONTENT_TYPES
            assert "table" in chunker.VALID_CONTENT_TYPES
            assert "heading" in chunker.VALID_CONTENT_TYPES
            assert "diagram_reference" in chunker.VALID_CONTENT_TYPES
            assert "formula" in chunker.VALID_CONTENT_TYPES


# ============================================================================
# _detect_content_type
# ============================================================================


class TestDetectContentType:
    """Test content type detection."""

    @pytest.fixture
    def chunker(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            return SemanticChunker()

    def test_plain_text(self, chunker):
        assert chunker._detect_content_type("This is a normal paragraph of text.") == "text"

    def test_markdown_table(self, chunker):
        text = "| Header1 | Header2 |\n|---------|---------|"
        assert chunker._detect_content_type(text) == "table"

    def test_tab_separated_table(self, chunker):
        text = "Col1\tCol2\nVal1\tVal2\nVal3\tVal4"
        assert chunker._detect_content_type(text) == "table"

    def test_heading_article_vn(self, chunker):
        assert chunker._detect_content_type("Điều 15: Tình huống cắt nhau") == "heading"

    def test_heading_rule(self, chunker):
        assert chunker._detect_content_type("Rule 15 - Crossing Situation") == "heading"

    def test_heading_clause(self, chunker):
        assert chunker._detect_content_type("Khoản 3 quy định về tốc độ an toàn") == "heading"

    def test_diagram_reference(self, chunker):
        assert chunker._detect_content_type("Xem hình 5 để biết thêm chi tiết") == "diagram_reference"

    def test_diagram_figure(self, chunker):
        assert chunker._detect_content_type("See figure 3 for the navigation pattern") == "diagram_reference"

    def test_formula(self, chunker):
        assert chunker._detect_content_type("Tốc độ = 12 + 3 hải lý") == "formula"

    def test_formula_multiplication(self, chunker):
        assert chunker._detect_content_type("Kết quả: 5 × 3") == "formula"


# ============================================================================
# _calculate_confidence
# ============================================================================


class TestCalculateConfidence:
    """Test confidence score calculation."""

    @pytest.fixture
    def chunker(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            return SemanticChunker()

    def test_optimal_length_text(self, chunker):
        text = "x" * 200  # Between min_chunk_size and 1000
        assert chunker._calculate_confidence(text, "text") == 1.0

    def test_short_chunk_penalty(self, chunker):
        text = "x" * 50  # Below min_chunk_size
        assert chunker._calculate_confidence(text, "text") == 0.6

    def test_long_chunk_penalty(self, chunker):
        text = "x" * 1500  # Above 1000
        assert chunker._calculate_confidence(text, "text") == 0.7

    def test_heading_boost(self, chunker):
        text = "x" * 50  # Short but heading
        confidence = chunker._calculate_confidence(text, "heading")
        assert confidence == min(1.0, 0.6 * 1.2)  # 0.72

    def test_table_boost(self, chunker):
        text = "x" * 200
        confidence = chunker._calculate_confidence(text, "table")
        assert confidence == 1.0  # 1.0 * 1.2 capped at 1.0

    def test_confidence_bounds(self, chunker):
        """Confidence should always be between 0 and 1."""
        for content_type in ["text", "table", "heading", "diagram_reference", "formula"]:
            for length in [10, 100, 500, 2000]:
                text = "x" * length
                conf = chunker._calculate_confidence(text, content_type)
                assert 0.0 <= conf <= 1.0


# ============================================================================
# _extract_document_hierarchy
# ============================================================================


class TestExtractDocumentHierarchy:
    """Test maritime document hierarchy extraction."""

    @pytest.fixture
    def chunker(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            return SemanticChunker()

    def test_article_number(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Điều 15 quy định về tình huống cắt nhau")
        assert hierarchy["article"] == "15"

    def test_clause_number(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Khoản 3 của Điều 15")
        assert hierarchy["clause"] == "3"
        assert hierarchy["article"] == "15"

    def test_point_identifier(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Điểm a quy định chi tiết")
        assert hierarchy["point"] == "a"

    def test_rule_number(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Rule 15 - Crossing Situation")
        assert hierarchy["rule"] == "15"

    def test_no_hierarchy(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Just a regular paragraph.")
        assert hierarchy == {}

    def test_english_article(self, chunker):
        hierarchy = chunker._extract_document_hierarchy("Article 10 of COLREG")
        assert hierarchy["article"] == "10"


# ============================================================================
# _build_metadata
# ============================================================================


class TestBuildMetadata:
    """Test metadata building."""

    @pytest.fixture
    def chunker(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 500
            mock_settings.chunk_overlap = 50
            mock_settings.min_chunk_size = 100
            from app.services.chunking_service import SemanticChunker
            return SemanticChunker()

    def test_basic_metadata(self, chunker):
        metadata = chunker._build_metadata(
            "Simple text content",
            {"page_number": 5, "document_id": "doc1"},
            "text",
            {}
        )
        assert metadata["page_number"] == 5
        assert metadata["document_id"] == "doc1"
        assert metadata["content_type"] == "text"
        assert metadata["language"] == "en"
        assert metadata["word_count"] == 3

    def test_vietnamese_detection(self, chunker):
        metadata = chunker._build_metadata(
            "Điều 15 quy định về tình huống cắt nhau",
            {"page_number": 1},
            "heading",
            {"article": "15"}
        )
        assert metadata["language"] == "vi"
        assert metadata["section_hierarchy"]["article"] == "15"

    def test_source_type_default(self, chunker):
        metadata = chunker._build_metadata("text", {}, "text", {})
        assert metadata["source_type"] == "pdf"


# ============================================================================
# chunk_page_content
# ============================================================================


class TestChunkPageContent:
    """Test chunk_page_content method."""

    @pytest.fixture
    def chunker(self):
        with patch("app.services.chunking_service.settings") as mock_settings:
            mock_settings.chunk_size = 200
            mock_settings.chunk_overlap = 20
            mock_settings.min_chunk_size = 50
            from app.services.chunking_service import SemanticChunker
            return SemanticChunker()

    @pytest.mark.asyncio
    async def test_empty_text(self, chunker):
        result = await chunker.chunk_page_content("", {"page_number": 1})
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_text(self, chunker):
        result = await chunker.chunk_page_content("   ", {"page_number": 1})
        assert result == []

    @pytest.mark.asyncio
    async def test_basic_chunking(self, chunker):
        text = "This is a sample paragraph of text that should be chunked. " * 10
        result = await chunker.chunk_page_content(text, {"page_number": 1, "document_id": "doc1"})
        assert len(result) >= 1
        for chunk in result:
            assert chunk.content_type in chunker.VALID_CONTENT_TYPES
            assert 0.0 <= chunk.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_sequential_chunk_indices(self, chunker):
        text = "First paragraph. " * 20 + "\n\n" + "Second paragraph. " * 20
        result = await chunker.chunk_page_content(text, {"page_number": 1})
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    @pytest.mark.asyncio
    async def test_maritime_heading_detected(self, chunker):
        text = "Rule 15 - Crossing Situation\nWhen two power-driven vessels are crossing so as to involve risk of collision, the vessel which has the other on her own starboard side shall keep out of the way and shall, if the circumstances of the case admit, avoid crossing ahead of the other vessel."
        result = await chunker.chunk_page_content(text, {"page_number": 1})
        # At least one chunk should have heading type or contain Rule 15
        has_heading_or_rule = any(
            c.content_type == "heading" or "Rule 15" in c.content
            for c in result
        )
        assert has_heading_or_rule
