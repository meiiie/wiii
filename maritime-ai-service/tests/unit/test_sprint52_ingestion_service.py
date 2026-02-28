"""
Tests for Sprint 52: MultimodalIngestionService coverage.

Tests ingestion pipeline including:
- IngestionResult (success_rate, api_savings_percent)
- PageResult dataclass
- MultimodalIngestionService (init, progress tracking, pdf delegation, ingest_pdf)
- Singleton
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass


# ============================================================================
# IngestionResult
# ============================================================================


class TestIngestionResult:
    """Test IngestionResult dataclass."""

    def test_defaults(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(
            document_id="doc1",
            total_pages=10,
            successful_pages=8,
            failed_pages=2,
        )
        assert r.document_id == "doc1"
        assert r.total_pages == 10
        assert r.successful_pages == 8
        assert r.failed_pages == 2
        assert r.errors == []
        assert r.vision_pages == 0
        assert r.direct_pages == 0
        assert r.fallback_pages == 0

    def test_success_rate(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(document_id="doc1", total_pages=10, successful_pages=8, failed_pages=2)
        assert r.success_rate == 80.0

    def test_success_rate_zero_pages(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(document_id="doc1", total_pages=0, successful_pages=0, failed_pages=0)
        assert r.success_rate == 0.0

    def test_success_rate_perfect(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(document_id="doc1", total_pages=5, successful_pages=5, failed_pages=0)
        assert r.success_rate == 100.0

    def test_api_savings_percent(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(
            document_id="doc1", total_pages=10, successful_pages=10,
            failed_pages=0, direct_pages=6, vision_pages=4
        )
        assert r.api_savings_percent == 60.0

    def test_api_savings_zero_pages(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(document_id="doc1", total_pages=0, successful_pages=0, failed_pages=0)
        assert r.api_savings_percent == 0.0

    def test_with_errors(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(
            document_id="doc1", total_pages=5, successful_pages=3,
            failed_pages=2, errors=["Page 2: timeout", "Page 4: extraction failed"]
        )
        assert len(r.errors) == 2

    def test_hybrid_tracking(self):
        from app.services.multimodal_ingestion_service import IngestionResult
        r = IngestionResult(
            document_id="doc1", total_pages=10, successful_pages=10,
            failed_pages=0, vision_pages=3, direct_pages=6, fallback_pages=1
        )
        assert r.vision_pages == 3
        assert r.direct_pages == 6
        assert r.fallback_pages == 1


# ============================================================================
# PageResult
# ============================================================================


class TestPageResult:
    """Test PageResult dataclass."""

    def test_defaults(self):
        from app.services.multimodal_ingestion_service import PageResult
        r = PageResult(page_number=1, success=True)
        assert r.page_number == 1
        assert r.success is True
        assert r.image_url is None
        assert r.text_length == 0
        assert r.total_chunks == 0
        assert r.error is None
        assert r.extraction_method == "vision"
        assert r.was_fallback is False

    def test_all_fields(self):
        from app.services.multimodal_ingestion_service import PageResult
        r = PageResult(
            page_number=5,
            success=True,
            image_url="https://storage.example.com/page5.png",
            text_length=2500,
            total_chunks=3,
            extraction_method="direct",
            was_fallback=False,
        )
        assert r.text_length == 2500
        assert r.total_chunks == 3
        assert r.extraction_method == "direct"

    def test_failed_page(self):
        from app.services.multimodal_ingestion_service import PageResult
        r = PageResult(page_number=3, success=False, error="Vision API timeout")
        assert r.success is False
        assert r.error == "Vision API timeout"


# ============================================================================
# Progress Tracking
# ============================================================================


class TestProgressTracking:
    """Test progress file management."""

    def _make_service(self):
        """Create service with all deps mocked."""
        with patch("app.services.multimodal_ingestion_service.get_storage_client") as mock_storage, \
             patch("app.services.multimodal_ingestion_service.get_vision_extractor") as mock_vision, \
             patch("app.services.multimodal_ingestion_service.GeminiOptimizedEmbeddings") as mock_embed, \
             patch("app.services.multimodal_ingestion_service.get_semantic_chunker") as mock_chunk, \
             patch("app.services.multimodal_ingestion_service.get_page_analyzer") as mock_pa, \
             patch("app.services.multimodal_ingestion_service.get_bounding_box_extractor") as mock_bbox, \
             patch("app.services.multimodal_ingestion_service.get_context_enricher") as mock_ce, \
             patch("app.services.multimodal_ingestion_service.get_kg_builder_agent") as mock_kg, \
             patch("app.services.multimodal_ingestion_service.Neo4jKnowledgeRepository") as mock_neo4j, \
             patch("app.services.multimodal_ingestion_service.PDFProcessor") as mock_pdf, \
             patch("app.services.multimodal_ingestion_service.VisionProcessor") as mock_vp, \
             patch("app.services.multimodal_ingestion_service.settings") as mock_settings:
            mock_settings.entity_extraction_enabled = False
            mock_settings.hybrid_detection_enabled = False
            mock_settings.force_vision_mode = False
            mock_settings.min_text_length_for_direct = 100
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            from app.services.multimodal_ingestion_service import MultimodalIngestionService
            service = MultimodalIngestionService()
        return service

    def test_get_progress_file(self):
        service = self._make_service()
        path = service._get_progress_file("doc-123")
        assert "doc-123" in str(path)
        assert path.suffix == ".json"

    def test_save_and_load_progress(self):
        service = self._make_service()
        service._save_progress("test-doc", 5)
        result = service._load_progress("test-doc")
        assert result == 5
        # Cleanup
        service._clear_progress("test-doc")

    def test_load_no_progress(self):
        service = self._make_service()
        result = service._load_progress("nonexistent-doc-xyz")
        assert result == 0

    def test_clear_progress(self):
        service = self._make_service()
        service._save_progress("test-doc-clear", 3)
        service._clear_progress("test-doc-clear")
        result = service._load_progress("test-doc-clear")
        assert result == 0

    def test_clear_nonexistent_progress(self):
        service = self._make_service()
        # Should not raise
        service._clear_progress("nonexistent-doc-abc")

    def test_load_corrupted_progress(self):
        service = self._make_service()
        # Write corrupted file
        progress_file = service._get_progress_file("corrupted-doc")
        progress_file.write_text("not valid json", encoding="utf-8")
        result = service._load_progress("corrupted-doc")
        assert result == 0
        # Cleanup
        if progress_file.exists():
            progress_file.unlink()


# ============================================================================
# PDF Delegation
# ============================================================================


class TestPDFDelegation:
    """Test PDF processing delegation."""

    def _make_service(self):
        with patch("app.services.multimodal_ingestion_service.get_storage_client"), \
             patch("app.services.multimodal_ingestion_service.get_vision_extractor"), \
             patch("app.services.multimodal_ingestion_service.GeminiOptimizedEmbeddings"), \
             patch("app.services.multimodal_ingestion_service.get_semantic_chunker"), \
             patch("app.services.multimodal_ingestion_service.get_page_analyzer"), \
             patch("app.services.multimodal_ingestion_service.get_bounding_box_extractor"), \
             patch("app.services.multimodal_ingestion_service.get_context_enricher"), \
             patch("app.services.multimodal_ingestion_service.get_kg_builder_agent"), \
             patch("app.services.multimodal_ingestion_service.Neo4jKnowledgeRepository"), \
             patch("app.services.multimodal_ingestion_service.PDFProcessor") as mock_pdf_cls, \
             patch("app.services.multimodal_ingestion_service.VisionProcessor"), \
             patch("app.services.multimodal_ingestion_service.settings") as mock_settings:
            mock_settings.entity_extraction_enabled = False
            mock_settings.hybrid_detection_enabled = False
            mock_settings.force_vision_mode = False
            mock_settings.min_text_length_for_direct = 100
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            from app.services.multimodal_ingestion_service import MultimodalIngestionService
            service = MultimodalIngestionService()
            mock_pdf_instance = mock_pdf_cls.return_value
        return service, mock_pdf_instance

    def test_get_pdf_page_count(self):
        service, mock_pdf = self._make_service()
        mock_pdf.get_pdf_page_count.return_value = 15
        assert service.get_pdf_page_count("/path/to/doc.pdf") == 15
        mock_pdf.get_pdf_page_count.assert_called_once_with("/path/to/doc.pdf")

    def test_convert_single_page(self):
        service, mock_pdf = self._make_service()
        mock_pdf.convert_single_page.return_value = MagicMock()
        service.convert_single_page("/path/to/doc.pdf", 3)
        mock_pdf.convert_single_page.assert_called_once_with("/path/to/doc.pdf", 3, 150)

    def test_convert_pdf_to_images(self):
        service, mock_pdf = self._make_service()
        mock_pdf.convert_pdf_to_images.return_value = ([], 10)
        service.convert_pdf_to_images("/path/to/doc.pdf", dpi=200)
        mock_pdf.convert_pdf_to_images.assert_called_once()


# ============================================================================
# ingest_pdf
# ============================================================================


class TestIngestPdf:
    """Test main ingestion pipeline."""

    def _make_service(self):
        with patch("app.services.multimodal_ingestion_service.get_storage_client"), \
             patch("app.services.multimodal_ingestion_service.get_vision_extractor"), \
             patch("app.services.multimodal_ingestion_service.GeminiOptimizedEmbeddings"), \
             patch("app.services.multimodal_ingestion_service.get_semantic_chunker"), \
             patch("app.services.multimodal_ingestion_service.get_page_analyzer"), \
             patch("app.services.multimodal_ingestion_service.get_bounding_box_extractor"), \
             patch("app.services.multimodal_ingestion_service.get_context_enricher"), \
             patch("app.services.multimodal_ingestion_service.get_kg_builder_agent"), \
             patch("app.services.multimodal_ingestion_service.Neo4jKnowledgeRepository"), \
             patch("app.services.multimodal_ingestion_service.PDFProcessor") as mock_pdf_cls, \
             patch("app.services.multimodal_ingestion_service.VisionProcessor") as mock_vp_cls, \
             patch("app.services.multimodal_ingestion_service.settings") as mock_settings:
            mock_settings.entity_extraction_enabled = False
            mock_settings.hybrid_detection_enabled = False
            mock_settings.force_vision_mode = False
            mock_settings.min_text_length_for_direct = 100
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            from app.services.multimodal_ingestion_service import MultimodalIngestionService
            service = MultimodalIngestionService()
        return service

    @pytest.mark.asyncio
    async def test_pdf_conversion_error(self):
        service = self._make_service()
        service.get_pdf_page_count = MagicMock(return_value=5)
        service.convert_pdf_to_images = MagicMock(side_effect=Exception("PDF error"))

        result = await service.ingest_pdf("/bad/path.pdf", "doc1", resume=False)
        assert result.total_pages == 5
        assert len(result.errors) == 1
        assert "PDF conversion failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_empty_pdf(self):
        service = self._make_service()
        service.get_pdf_page_count = MagicMock(return_value=0)
        service.convert_pdf_to_images = MagicMock(return_value=([], 0))

        result = await service.ingest_pdf("/empty.pdf", "doc1", resume=False)
        assert result.total_pages == 0
        assert result.successful_pages == 0

    @pytest.mark.asyncio
    async def test_success_single_page(self):
        service = self._make_service()
        mock_image = MagicMock()
        service.get_pdf_page_count = MagicMock(return_value=1)
        service.convert_pdf_to_images = MagicMock(return_value=([mock_image], 1))

        from app.services.multimodal_ingestion_service import PageResult
        mock_page_result = PageResult(
            page_number=1, success=True, text_length=500,
            total_chunks=2, extraction_method="vision"
        )
        service._process_page = AsyncMock(return_value=mock_page_result)
        service._save_progress = MagicMock()
        service._clear_progress = MagicMock()

        result = await service.ingest_pdf("/test.pdf", "doc1", resume=False)
        assert result.successful_pages == 1
        assert result.failed_pages == 0
        assert result.vision_pages == 1

    @pytest.mark.asyncio
    async def test_page_processing_error(self):
        service = self._make_service()
        mock_image = MagicMock()
        service.get_pdf_page_count = MagicMock(return_value=1)
        service.convert_pdf_to_images = MagicMock(return_value=([mock_image], 1))
        service._process_page = AsyncMock(side_effect=Exception("Vision API error"))
        service._clear_progress = MagicMock()

        result = await service.ingest_pdf("/test.pdf", "doc1", resume=False)
        assert result.failed_pages == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_max_pages_limit(self):
        service = self._make_service()
        # get_pdf_page_count reports 5 pages total, but max_pages=2 limits processing
        # convert_pdf_to_images is called with batch_end=2 so it only returns 2 images
        images = [MagicMock() for _ in range(2)]
        service.get_pdf_page_count = MagicMock(return_value=5)
        service.convert_pdf_to_images = MagicMock(return_value=(images, 5))

        from app.services.multimodal_ingestion_service import PageResult
        service._process_page = AsyncMock(
            return_value=PageResult(page_number=1, success=True, extraction_method="vision")
        )
        service._save_progress = MagicMock()
        service._clear_progress = MagicMock()

        result = await service.ingest_pdf("/test.pdf", "doc1", resume=False, max_pages=2)
        assert result.successful_pages == 2

    @pytest.mark.asyncio
    async def test_direct_extraction_tracking(self):
        service = self._make_service()
        mock_image = MagicMock()
        service.get_pdf_page_count = MagicMock(return_value=1)
        service.convert_pdf_to_images = MagicMock(return_value=([mock_image], 1))

        from app.services.multimodal_ingestion_service import PageResult
        service._process_page = AsyncMock(
            return_value=PageResult(page_number=1, success=True, extraction_method="direct")
        )
        service._save_progress = MagicMock()
        service._clear_progress = MagicMock()

        result = await service.ingest_pdf("/test.pdf", "doc1", resume=False)
        assert result.direct_pages == 1
        assert result.vision_pages == 0


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton factory."""

    def test_singleton(self):
        import app.services.multimodal_ingestion_service as mod
        old = mod._ingestion_service
        mod._ingestion_service = None

        with patch("app.services.multimodal_ingestion_service.get_storage_client"), \
             patch("app.services.multimodal_ingestion_service.get_vision_extractor"), \
             patch("app.services.multimodal_ingestion_service.GeminiOptimizedEmbeddings"), \
             patch("app.services.multimodal_ingestion_service.get_semantic_chunker"), \
             patch("app.services.multimodal_ingestion_service.get_page_analyzer"), \
             patch("app.services.multimodal_ingestion_service.get_bounding_box_extractor"), \
             patch("app.services.multimodal_ingestion_service.get_context_enricher"), \
             patch("app.services.multimodal_ingestion_service.get_kg_builder_agent"), \
             patch("app.services.multimodal_ingestion_service.Neo4jKnowledgeRepository"), \
             patch("app.services.multimodal_ingestion_service.PDFProcessor"), \
             patch("app.services.multimodal_ingestion_service.VisionProcessor"), \
             patch("app.services.multimodal_ingestion_service.settings") as mock_settings:
            mock_settings.entity_extraction_enabled = False
            mock_settings.hybrid_detection_enabled = False
            mock_settings.force_vision_mode = False
            mock_settings.min_text_length_for_direct = 100
            mock_settings.default_domain = "maritime"
            mock_settings.contextual_rag_enabled = False
            r1 = mod.get_ingestion_service()
            r2 = mod.get_ingestion_service()
            assert r1 is r2

        mod._ingestion_service = old
