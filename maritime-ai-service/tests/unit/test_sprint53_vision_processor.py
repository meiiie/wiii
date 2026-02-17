"""
Tests for Sprint 53: VisionProcessor coverage.

Tests page-level text extraction and storage pipeline:
- VisionProcessor init
- extract_direct (success, error)
- process_page (upload-fail, vision-fail, direct-extraction, vision-extraction,
  chunking-error, entity-extraction, all-chunks-fail, contextual-rag)
- extract_and_store_entities (no-kg, no-neo4j, success, empty)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from PIL import Image


# ============================================================================
# Helpers
# ============================================================================


def _make_processor(**overrides):
    """Create VisionProcessor with all deps mocked."""
    defaults = dict(
        storage=MagicMock(),
        vision=MagicMock(),
        embeddings=MagicMock(),
        chunker=MagicMock(),
        page_analyzer=MagicMock(),
        bbox_extractor=MagicMock(),
        context_enricher=MagicMock(),
        kg_builder=MagicMock(),
        neo4j=MagicMock(),
        entity_extraction_enabled=False,
        hybrid_detection_enabled=False,
        force_vision_mode=False,
        min_text_length=100,
    )
    defaults.update(overrides)
    from app.services.vision_processor import VisionProcessor
    return VisionProcessor(**defaults)


# ============================================================================
# Init
# ============================================================================


class TestVisionProcessorInit:
    """Test VisionProcessor initialization."""

    def test_stores_all_deps(self):
        proc = _make_processor()
        assert proc.storage is not None
        assert proc.vision is not None
        assert proc.embeddings is not None
        assert proc.chunker is not None
        assert proc.entity_extraction_enabled is False
        assert proc.hybrid_detection_enabled is False
        assert proc.force_vision_mode is False
        assert proc.min_text_length == 100


# ============================================================================
# extract_direct
# ============================================================================


class TestExtractDirect:
    """Test direct text extraction from PDF pages."""

    def test_success(self):
        proc = _make_processor()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "  Line 1  \n\n  Line 2  \n  \n  Line 3  "

        result = proc.extract_direct(mock_page)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_cleans_whitespace(self):
        proc = _make_processor()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "   Hello   \n   World   "

        result = proc.extract_direct(mock_page)
        assert result == "Hello\nWorld"

    def test_error(self):
        proc = _make_processor()
        mock_page = MagicMock()
        mock_page.get_text.side_effect = Exception("Page error")

        result = proc.extract_direct(mock_page)
        assert result == ""


# ============================================================================
# process_page — upload failure
# ============================================================================


class TestProcessPageUploadFail:
    """Test process_page when upload fails."""

    @pytest.mark.asyncio
    async def test_upload_failure(self):
        proc = _make_processor()
        mock_upload = MagicMock()
        mock_upload.success = False
        mock_upload.error = "Storage unavailable"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            result = await proc.process_page(mock_image, "doc1", 1)

        assert result.success is False
        assert "Upload failed" in result.error


# ============================================================================
# process_page — vision extraction
# ============================================================================


class TestProcessPageVision:
    """Test process_page with vision extraction."""

    @pytest.mark.asyncio
    async def test_vision_success(self):
        proc = _make_processor()

        # Upload succeeds
        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        # Vision extraction succeeds
        mock_extraction = MagicMock()
        mock_extraction.success = True
        mock_extraction.text = "SOLAS Chapter III - Life-saving appliances"
        proc.vision.extract_from_image = AsyncMock(return_value=mock_extraction)
        proc.vision.validate_extraction.return_value = True

        # Chunking
        from app.services.chunking_service import ChunkResult
        mock_chunk = ChunkResult(
            chunk_index=0, content="SOLAS Chapter III - Life-saving appliances",
            content_type="text", confidence_score=0.95, metadata={}
        )
        proc.chunker.chunk_page_content = AsyncMock(return_value=[mock_chunk])

        # Embedding
        proc.embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

        # Store in DB
        proc.store_chunk_in_database = AsyncMock()

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            result = await proc.process_page(mock_image, "doc1", 1)

        assert result.success is True
        assert result.extraction_method == "vision"
        assert result.text_length > 0
        assert result.total_chunks == 1

    @pytest.mark.asyncio
    async def test_vision_extraction_failure(self):
        proc = _make_processor()

        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        mock_extraction = MagicMock()
        mock_extraction.success = False
        mock_extraction.error = "Vision API timeout"
        proc.vision.extract_from_image = AsyncMock(return_value=mock_extraction)

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            result = await proc.process_page(mock_image, "doc1", 1)

        assert result.success is False
        assert "Extraction failed" in result.error


# ============================================================================
# process_page — hybrid detection with direct extraction
# ============================================================================


class TestProcessPageDirect:
    """Test process_page with direct (PyMuPDF) extraction."""

    @pytest.mark.asyncio
    async def test_direct_extraction(self):
        proc = _make_processor(hybrid_detection_enabled=True)

        # Upload succeeds
        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        # Page analyzer says: don't use vision
        mock_analysis = MagicMock()
        mock_analysis.detection_reasons = ["High text density"]
        proc.page_analyzer.analyze_page.return_value = mock_analysis
        proc.page_analyzer.should_use_vision.return_value = False

        # Direct extraction gives enough text
        mock_pdf_page = MagicMock()
        mock_pdf_page.get_text.return_value = "A" * 200  # > min_text_length

        # Chunking
        from app.services.chunking_service import ChunkResult
        mock_chunk = ChunkResult(
            chunk_index=0, content="A" * 200,
            content_type="text", confidence_score=0.9, metadata={}
        )
        proc.chunker.chunk_page_content = AsyncMock(return_value=[mock_chunk])
        proc.embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)
        proc.store_chunk_in_database = AsyncMock()

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            result = await proc.process_page(mock_image, "doc1", 1, pdf_page=mock_pdf_page)

        assert result.success is True
        assert result.extraction_method == "direct"

    @pytest.mark.asyncio
    async def test_direct_too_short_falls_back_to_vision(self):
        proc = _make_processor(hybrid_detection_enabled=True, min_text_length=100)

        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        mock_analysis = MagicMock()
        proc.page_analyzer.analyze_page.return_value = mock_analysis
        proc.page_analyzer.should_use_vision.return_value = False

        # Direct extraction gives too little text
        mock_pdf_page = MagicMock()
        mock_pdf_page.get_text.return_value = "Short"  # < 100 chars

        # Vision extraction takes over
        mock_extraction = MagicMock()
        mock_extraction.success = True
        mock_extraction.text = "Vision extracted full page text with sufficient length"
        proc.vision.extract_from_image = AsyncMock(return_value=mock_extraction)
        proc.vision.validate_extraction.return_value = True

        from app.services.chunking_service import ChunkResult
        proc.chunker.chunk_page_content = AsyncMock(return_value=[
            ChunkResult(chunk_index=0, content="Vision text", content_type="text",
                       confidence_score=0.95, metadata={})
        ])
        proc.embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)
        proc.store_chunk_in_database = AsyncMock()

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            result = await proc.process_page(mock_image, "doc1", 1, pdf_page=mock_pdf_page)

        assert result.success is True
        assert result.extraction_method == "vision"
        assert result.was_fallback is True


# ============================================================================
# process_page — chunking error fallback
# ============================================================================


class TestProcessPageChunkingError:
    """Test chunking error fallback to single chunk."""

    @pytest.mark.asyncio
    async def test_chunking_fallback(self):
        proc = _make_processor()

        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        mock_extraction = MagicMock()
        mock_extraction.success = True
        mock_extraction.text = "Page content for test"
        proc.vision.extract_from_image = AsyncMock(return_value=mock_extraction)
        proc.vision.validate_extraction.return_value = True

        # Chunking raises
        proc.chunker.chunk_page_content = AsyncMock(side_effect=Exception("Chunking error"))

        proc.embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)
        proc.store_chunk_in_database = AsyncMock()

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            result = await proc.process_page(mock_image, "doc1", 1)

        assert result.success is True
        assert result.total_chunks == 1  # Fallback single chunk


# ============================================================================
# process_page — all chunks fail
# ============================================================================


class TestProcessPageAllChunksFail:
    """Test when all chunks fail to process."""

    @pytest.mark.asyncio
    async def test_all_chunks_fail(self):
        proc = _make_processor()

        mock_upload = MagicMock()
        mock_upload.success = True
        mock_upload.public_url = "https://storage.example.com/page1.png"
        proc.storage.upload_pil_image = AsyncMock(return_value=mock_upload)

        mock_extraction = MagicMock()
        mock_extraction.success = True
        mock_extraction.text = "Page content"
        proc.vision.extract_from_image = AsyncMock(return_value=mock_extraction)
        proc.vision.validate_extraction.return_value = True

        from app.services.chunking_service import ChunkResult
        proc.chunker.chunk_page_content = AsyncMock(return_value=[
            ChunkResult(chunk_index=0, content="chunk", content_type="text",
                       confidence_score=0.9, metadata={})
        ])

        # Embedding fails for all chunks
        proc.embeddings.aembed_query = AsyncMock(side_effect=Exception("Embedding error"))

        mock_image = MagicMock(spec=Image.Image)

        with patch("app.services.vision_processor.settings") as mock_settings:
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            result = await proc.process_page(mock_image, "doc1", 1)

        assert result.success is False
        assert "All chunks failed" in result.error


# ============================================================================
# extract_and_store_entities
# ============================================================================


class TestExtractAndStoreEntities:
    """Test entity extraction for GraphRAG."""

    @pytest.mark.asyncio
    async def test_kg_not_available(self):
        proc = _make_processor(entity_extraction_enabled=True)
        proc.kg_builder.is_available.return_value = False

        await proc.extract_and_store_entities("text", "doc1", 1)
        proc.kg_builder.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_neo4j_not_available(self):
        proc = _make_processor(entity_extraction_enabled=True)
        proc.kg_builder.is_available.return_value = True
        proc.neo4j.is_available.return_value = False

        await proc.extract_and_store_entities("text", "doc1", 1)
        proc.kg_builder.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_success(self):
        proc = _make_processor(entity_extraction_enabled=True)
        proc.kg_builder.is_available.return_value = True
        proc.neo4j.is_available.return_value = True

        mock_entity = MagicMock()
        mock_entity.id = "ent1"
        mock_entity.entity_type = "REGULATION"
        mock_entity.name = "SOLAS"
        mock_entity.name_vi = "SOLAS"
        mock_entity.description = "Safety of Life at Sea"

        mock_relation = MagicMock()
        mock_relation.source_id = "ent1"
        mock_relation.target_id = "ent2"
        mock_relation.relation_type = "PART_OF"
        mock_relation.description = "Chapter of convention"

        mock_extraction = MagicMock()
        mock_extraction.entities = [mock_entity]
        mock_extraction.relations = [mock_relation]
        proc.kg_builder.extract = AsyncMock(return_value=mock_extraction)
        proc.neo4j.create_entity = AsyncMock(return_value=True)
        proc.neo4j.create_entity_relation = AsyncMock(return_value=True)

        await proc.extract_and_store_entities("SOLAS text", "doc1", 1)

        proc.neo4j.create_entity.assert_called_once()
        proc.neo4j.create_entity_relation.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_entities(self):
        proc = _make_processor(entity_extraction_enabled=True)
        proc.kg_builder.is_available.return_value = True
        proc.neo4j.is_available.return_value = True

        mock_extraction = MagicMock()
        mock_extraction.entities = []
        proc.kg_builder.extract = AsyncMock(return_value=mock_extraction)

        await proc.extract_and_store_entities("Short text", "doc1", 1)
        proc.neo4j.create_entity.assert_not_called()
