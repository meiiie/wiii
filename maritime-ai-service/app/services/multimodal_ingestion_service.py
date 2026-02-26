"""
Multimodal Ingestion Service for Vision-based RAG

CHI THI KY THUAT SO 26: Multimodal RAG Pipeline
Full pipeline: PDF -> Images -> Object Storage (MinIO) -> Vision -> Embeddings -> Database

**Feature: multimodal-rag-vision**
**Validates: Requirements 2.1, 7.1, 7.4, 7.5**

Orchestrator module - delegates to:
- pdf_processor.py: PDF rasterization and image conversion
- vision_processor.py: Page-level text extraction, chunking, storage, entity extraction
"""
import logging
import json
from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from pathlib import Path

if TYPE_CHECKING:
    import fitz

from app.core.config import settings
from app.services.object_storage import ObjectStorageClient, get_storage_client
from app.services.chunking_service import SemanticChunker, get_semantic_chunker
from app.engine.vision_extractor import VisionExtractor, get_vision_extractor
from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
from app.engine.page_analyzer import PageAnalyzer, get_page_analyzer
from app.engine.bounding_box_extractor import BoundingBoxExtractor, get_bounding_box_extractor
from app.engine.context_enricher import ContextEnricher, get_context_enricher
# GraphRAG entity extraction (Feature: document-kg)
from app.engine.multi_agent.agents.kg_builder_agent import KGBuilderAgentNode, get_kg_builder_agent
from app.repositories.neo4j_knowledge_repository import Neo4jKnowledgeRepository

# Delegate modules
from app.services.pdf_processor import PDFProcessor, USE_PYMUPDF
from app.services.vision_processor import VisionProcessor

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of PDF ingestion"""
    document_id: str
    total_pages: int
    successful_pages: int
    failed_pages: int
    errors: List[str] = field(default_factory=list)

    # Hybrid Text/Vision Detection tracking (Feature: hybrid-text-vision)
    vision_pages: int = 0      # Pages processed via Gemini Vision
    direct_pages: int = 0      # Pages processed via PyMuPDF direct extraction
    fallback_pages: int = 0    # Pages that fell back from direct to vision

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_pages == 0:
            return 0.0
        return (self.successful_pages / self.total_pages) * 100

    @property
    def api_savings_percent(self) -> float:
        """
        Calculate estimated API cost savings from hybrid detection.

        **Feature: hybrid-text-vision**
        **Property 8: Savings Calculation**
        """
        if self.total_pages == 0:
            return 0.0
        return (self.direct_pages / self.total_pages) * 100


@dataclass
class PageResult:
    """Result of single page processing"""
    page_number: int
    success: bool
    image_url: Optional[str] = None
    text_length: int = 0
    total_chunks: int = 0  # Number of semantic chunks created
    error: Optional[str] = None
    extraction_method: str = "vision"  # "direct" or "vision" (Feature: hybrid-text-vision)
    was_fallback: bool = False  # True if fell back from direct to vision


class MultimodalIngestionService:
    """
    Service for multimodal document ingestion.

    Pipeline:
    1. Rasterization: PDF -> High-quality images (pdf2image)
    2. Storage: Upload images to object storage
    3. Vision Extraction: Gemini Vision extracts text from images
    4. Indexing: Store text + embeddings + image_url in Neon

    Delegates to:
    - PDFProcessor: PDF rasterization and image conversion
    - VisionProcessor: Page-level text extraction, chunking, storage

    **Property 6: PDF Page Count Equals Image Count**
    **Property 13: Ingestion Logs Progress**
    **Property 14: Ingestion Summary Contains Counts**
    **Property 15: Resume From Last Successful Page**
    """

    DEFAULT_DPI = 150
    PROGRESS_FILE_SUFFIX = ".progress.json"

    def __init__(
        self,
        storage_client: Optional[ObjectStorageClient] = None,
        vision_extractor: Optional[VisionExtractor] = None,
        embedding_service: Optional[GeminiOptimizedEmbeddings] = None,
        chunker: Optional[SemanticChunker] = None,
        page_analyzer: Optional[PageAnalyzer] = None,
        bbox_extractor: Optional[BoundingBoxExtractor] = None,
        context_enricher: Optional[ContextEnricher] = None,
        kg_builder: Optional[KGBuilderAgentNode] = None,
        neo4j_repo: Optional[Neo4jKnowledgeRepository] = None
    ):
        """
        Initialize Multimodal Ingestion Service.

        Args:
            storage_client: Object storage client
            vision_extractor: Vision extraction service
            embedding_service: Embedding generation service
            chunker: Semantic chunking service
            page_analyzer: Page analyzer for hybrid detection (Feature: hybrid-text-vision)
            bbox_extractor: Bounding box extractor (Feature: source-highlight-citation)
            kg_builder: KG Builder Agent for entity extraction (Feature: document-kg)
            neo4j_repo: Neo4j repository for storing entities (Feature: document-kg)
        """
        self.storage = storage_client or get_storage_client()
        self.vision = vision_extractor or get_vision_extractor()
        self.embeddings = embedding_service or GeminiOptimizedEmbeddings()
        self.chunker = chunker or get_semantic_chunker()
        self.page_analyzer = page_analyzer or get_page_analyzer()
        self.bbox_extractor = bbox_extractor or get_bounding_box_extractor()
        self.context_enricher = context_enricher or get_context_enricher()

        # GraphRAG entity extraction (Feature: document-kg)
        self.kg_builder = kg_builder or get_kg_builder_agent()
        self.neo4j = neo4j_repo or Neo4jKnowledgeRepository()
        self.entity_extraction_enabled = settings.entity_extraction_enabled

        # Hybrid detection settings from config
        self.hybrid_detection_enabled = settings.hybrid_detection_enabled
        self.force_vision_mode = settings.force_vision_mode
        self.min_text_length = settings.min_text_length_for_direct

        # Initialize delegate processors
        self._pdf_processor = PDFProcessor()
        self._vision_processor = VisionProcessor(
            storage=self.storage,
            vision=self.vision,
            embeddings=self.embeddings,
            chunker=self.chunker,
            page_analyzer=self.page_analyzer,
            bbox_extractor=self.bbox_extractor,
            context_enricher=self.context_enricher,
            kg_builder=self.kg_builder,
            neo4j=self.neo4j,
            entity_extraction_enabled=self.entity_extraction_enabled,
            hybrid_detection_enabled=self.hybrid_detection_enabled,
            force_vision_mode=self.force_vision_mode,
            min_text_length=self.min_text_length
        )

        logger.info(
            "MultimodalIngestionService initialized: "
            "hybrid_detection=%s, "
            "force_vision=%s, "
            "contextual_rag=%s, "
            "entity_extraction=%s",
            self.hybrid_detection_enabled,
            self.force_vision_mode,
            settings.contextual_rag_enabled,
            self.entity_extraction_enabled,
        )

    # ── Progress Tracking ──────────────────────────────────────────────

    def _get_progress_file(self, document_id: str) -> Path:
        """Get path to progress tracking file (cross-platform)"""
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        return temp_dir / f"{document_id}{self.PROGRESS_FILE_SUFFIX}"

    def _load_progress(self, document_id: str) -> int:
        """
        Load last successful page from progress file.

        **Property 15: Resume From Last Successful Page**
        """
        progress_file = self._get_progress_file(document_id)
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_successful_page', 0)
            except Exception as e:
                logger.warning("Failed to load progress: %s", e)
        return 0

    def _save_progress(self, document_id: str, page_number: int):
        """Save progress to file for resume capability"""
        progress_file = self._get_progress_file(document_id)
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump({'last_successful_page': page_number}, f)
        except Exception as e:
            logger.warning("Failed to save progress: %s", e)

    def _clear_progress(self, document_id: str):
        """Clear progress file after successful completion"""
        progress_file = self._get_progress_file(document_id)
        if progress_file.exists():
            progress_file.unlink()

    # ── PDF Processing (delegated to PDFProcessor) ─────────────────────

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total page count without loading images into memory."""
        return self._pdf_processor.get_pdf_page_count(pdf_path)

    def convert_single_page(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int = DEFAULT_DPI
    ):
        """
        Convert a single PDF page to image.

        Memory-efficient: only one page in memory at a time.
        """
        return self._pdf_processor.convert_single_page(pdf_path, page_num, dpi)

    def convert_pdf_to_images(
        self,
        pdf_path: str,
        dpi: int = DEFAULT_DPI,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None
    ):
        """
        Convert PDF pages to high-quality images.

        **Property 6: PDF Page Count Equals Image Count**
        """
        return self._pdf_processor.convert_pdf_to_images(pdf_path, dpi, start_page, end_page)

    # ── Vision Processing (delegated to VisionProcessor) ───────────────

    def _extract_direct(self, page: "fitz.Page") -> str:
        """
        Extract text directly from PDF page using PyMuPDF.

        **Feature: hybrid-text-vision**
        """
        return self._vision_processor.extract_direct(page)

    async def _process_page(
        self,
        image,
        document_id: str,
        page_number: int,
        pdf_page=None,
        domain_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> PageResult:
        """
        Process a single page through the pipeline with semantic chunking.

        **Feature: semantic-chunking, hybrid-text-vision**
        """
        return await self._vision_processor.process_page(
            image=image,
            document_id=document_id,
            page_number=page_number,
            pdf_page=pdf_page,
            domain_id=domain_id or settings.default_domain,
            organization_id=organization_id
        )

    async def _store_chunk_in_database(
        self,
        document_id: str,
        page_number: int,
        chunk_index: int,
        content: str,
        contextual_content: Optional[str],
        embedding: List[float],
        image_url: str,
        content_type: str = 'text',
        confidence_score: float = 1.0,
        metadata: Optional[dict] = None,
        bounding_boxes: Optional[List[dict]] = None,
        domain_id: Optional[str] = None
    ):
        """
        Store a semantic chunk in Neon database.

        **Feature: semantic-chunking**
        """
        return await self._vision_processor.store_chunk_in_database(
            document_id=document_id,
            page_number=page_number,
            chunk_index=chunk_index,
            content=content,
            contextual_content=contextual_content,
            embedding=embedding,
            image_url=image_url,
            content_type=content_type,
            confidence_score=confidence_score,
            metadata=metadata,
            bounding_boxes=bounding_boxes,
            domain_id=domain_id
        )

    async def _extract_and_store_entities(
        self,
        text: str,
        document_id: str,
        page_number: int
    ):
        """
        Extract entities from page text and store in Neo4j.

        **Feature: document-kg**
        """
        return await self._vision_processor.extract_and_store_entities(
            text=text,
            document_id=document_id,
            page_number=page_number
        )

    # ── Main Pipeline ──────────────────────────────────────────────────

    async def ingest_pdf(
        self,
        pdf_path: str,
        document_id: str,
        resume: bool = True,
        max_pages: Optional[int] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        domain_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Full ingestion pipeline: PDF -> Images -> Vision -> Database.

        Args:
            pdf_path: Path to PDF file
            document_id: Unique identifier for the document
            resume: Whether to resume from last successful page
            max_pages: Maximum pages to process (for testing)
            start_page: Start from this page (1-indexed, for batch processing)
            end_page: Stop at this page (1-indexed, inclusive)

        Returns:
            IngestionResult with summary statistics

        **Property 13: Ingestion Logs Progress**
        **Property 14: Ingestion Summary Contains Counts**
        **Feature: hybrid-text-vision (batch processing support)**
        """
        domain_id = domain_id or settings.default_domain
        logger.info("Starting multimodal ingestion for document: %s", document_id)

        # Determine page range for batch processing BEFORE converting
        # start_page and end_page are 1-indexed from API
        batch_start = 0  # 0-indexed for internal use
        batch_end = None  # Will be set after knowing total_pages

        if start_page is not None and start_page > 0:
            batch_start = start_page - 1  # Convert to 0-indexed
            logger.info("Batch processing: starting from page %d", start_page)

        if end_page is not None and end_page > 0:
            batch_end = end_page  # Will be capped to total_pages later
            logger.info("Batch processing: ending at page %d", end_page)

        # Check for resume point (only if not using explicit start_page)
        if start_page is None and resume:
            resume_page = self._load_progress(document_id)
            if resume_page > 0:
                batch_start = resume_page
                logger.info("Resuming from page %d", resume_page + 1)

        # Convert ONLY the pages we need (optimized for batch processing)
        try:
            images, total_pages = self.convert_pdf_to_images(
                pdf_path,
                start_page=batch_start,
                end_page=batch_end
            )
        except Exception as e:
            logger.error("Failed to convert PDF: %s", e)
            return IngestionResult(
                document_id=document_id,
                total_pages=0,
                successful_pages=0,
                failed_pages=0,
                errors=[f"PDF conversion failed: {e}"]
            )

        # Finalize batch_end after knowing total_pages
        if batch_end is None:
            batch_end = total_pages
        else:
            batch_end = min(batch_end, total_pages)

        # Limit pages if max_pages is set (for testing)
        pages_to_process = batch_end - batch_start
        if max_pages is not None and max_pages > 0:
            pages_to_process = min(max_pages, pages_to_process)
            batch_end = batch_start + pages_to_process
            logger.info("Limiting to %d pages (test mode)", pages_to_process)

        successful_pages = 0
        failed_pages = 0
        errors = []

        # Hybrid detection tracking (Feature: hybrid-text-vision)
        vision_pages = 0
        direct_pages = 0
        fallback_pages = 0

        logger.info("Processing pages %d to %d of %d", batch_start + 1, batch_end, total_pages)

        # Open PDF for hybrid detection (need page objects)
        pdf_doc = None
        if self.hybrid_detection_enabled and USE_PYMUPDF:
            try:
                import fitz
                pdf_doc = fitz.open(pdf_path)
            except Exception as e:
                logger.warning("Could not open PDF for hybrid detection: %s", e)

        # Process each page in the batch
        # Note: images list now only contains pages from batch_start to batch_end
        # So enumerate index 0 = page batch_start, index 1 = page batch_start+1, etc.
        for idx in range(len(images)):
            # Get image and immediately remove from list to free memory
            image = images[idx]
            images[idx] = None  # Free memory immediately

            # Calculate actual page number (0-indexed)
            page_num = batch_start + idx

            # Log progress
            logger.info("Processing page %d of %d (batch: %d-%d)", page_num + 1, total_pages, batch_start + 1, batch_end)

            # Get PDF page for hybrid detection
            pdf_page = None
            if pdf_doc is not None:
                try:
                    pdf_page = pdf_doc.load_page(page_num)
                except Exception as e:
                    logger.warning("Could not load PDF page %d: %s", page_num, e)

            try:
                result = await self._process_page(
                    image=image,
                    document_id=document_id,
                    page_number=page_num + 1,  # 1-indexed
                    pdf_page=pdf_page,
                    domain_id=domain_id,
                    organization_id=organization_id
                )

                if result.success:
                    successful_pages += 1
                    self._save_progress(document_id, page_num + 1)

                    # Track extraction method (Feature: hybrid-text-vision)
                    if result.extraction_method == "vision":
                        vision_pages += 1
                    else:
                        direct_pages += 1

                    if result.was_fallback:
                        fallback_pages += 1
                else:
                    failed_pages += 1
                    if result.error:
                        errors.append(f"Page {page_num + 1}: {result.error}")

            except Exception as e:
                failed_pages += 1
                errors.append(f"Page {page_num + 1}: {str(e)}")
                logger.error("Failed to process page %d: %s", page_num + 1, e)
            finally:
                # Explicitly close and free image memory
                if image is not None:
                    try:
                        image.close()
                    except Exception as e:
                        logger.debug("Failed to close image: %s", e)
                        pass
                    del image

                # Force garbage collection after each page to prevent memory buildup
                import gc
                gc.collect()

        # Close PDF document
        if pdf_doc is not None:
            pdf_doc.close()

        # Clear progress file on completion
        self._clear_progress(document_id)

        # Log summary with hybrid detection stats
        result = IngestionResult(
            document_id=document_id,
            total_pages=total_pages,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            errors=errors,
            vision_pages=vision_pages,
            direct_pages=direct_pages,
            fallback_pages=fallback_pages
        )

        logger.info(
            "Ingestion complete: %d/%d pages successful "
            "(%.1f%%)",
            successful_pages, total_pages, result.success_rate,
        )

        # Log hybrid detection savings (Feature: hybrid-text-vision)
        if self.hybrid_detection_enabled:
            logger.info(
                "Hybrid detection: vision=%d, direct=%d, "
                "fallback=%d, API savings=%.1f%%",
                vision_pages, direct_pages, fallback_pages, result.api_savings_percent,
            )

        return result


# Singleton instance
_ingestion_service: Optional[MultimodalIngestionService] = None


def get_ingestion_service() -> MultimodalIngestionService:
    """Get or create singleton MultimodalIngestionService instance"""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = MultimodalIngestionService()
    return _ingestion_service
