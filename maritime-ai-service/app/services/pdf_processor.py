"""
PDF Processor - PDF to Image conversion utilities.

Handles rasterization of PDF pages to high-quality images for Vision-based RAG.
Supports PyMuPDF (primary) with pdf2image fallback.

Split from multimodal_ingestion_service.py for single-responsibility.

**Feature: multimodal-rag-vision**
"""
import logging
import io
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

from PIL import Image

# Try PyMuPDF first (no external dependencies), fallback to pdf2image
try:
    import fitz  # PyMuPDF
    USE_PYMUPDF = True
except ImportError:
    from pdf2image import convert_from_path
    USE_PYMUPDF = False

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Handles PDF to image conversion with memory-efficient page-by-page processing.

    Supports two backends:
    - PyMuPDF (fitz): Primary, no external dependencies
    - pdf2image: Fallback, requires Poppler

    **Property 6: PDF Page Count Equals Image Count**
    """

    # Reduced DPI from 300 to 150 for memory savings on Render Free Tier
    # 150 DPI is sufficient for Gemini Vision text reading
    DEFAULT_DPI = 150

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total page count without loading images into memory."""
        doc = fitz.open(pdf_path)
        total = len(doc)
        doc.close()
        return total

    def convert_single_page(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int = DEFAULT_DPI
    ) -> Optional[Image.Image]:
        """
        Convert a single PDF page to image.

        Memory-efficient: only one page in memory at a time.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            dpi: Resolution for conversion

        Returns:
            PIL Image object or None on error
        """
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                doc.close()
                return None

            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=matrix)
            img_data = pix.tobytes("jpeg")
            img = Image.open(io.BytesIO(img_data))

            # Clean up PyMuPDF objects
            del pix
            doc.close()

            return img
        except Exception as e:
            logger.error("Failed to convert page %d: %s", page_num, e)
            return None

    def convert_pdf_to_images(
        self,
        pdf_path: str,
        dpi: int = DEFAULT_DPI,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None
    ) -> tuple[List[Image.Image], int]:
        """
        Convert PDF pages to high-quality images.

        MEMORY OPTIMIZED: Converts pages one at a time to reduce peak memory usage.

        Args:
            pdf_path: Path to PDF file
            dpi: Resolution for conversion (default 150 for memory efficiency)
            start_page: Start from this page (0-indexed, optional)
            end_page: End at this page (0-indexed, exclusive, optional)

        Returns:
            Tuple of (List of PIL Image objects, total_pages in PDF)

        **Property 6: PDF Page Count Equals Image Count**
        **Feature: hybrid-text-vision (optimized batch conversion)**
        """
        if USE_PYMUPDF:
            # Get total pages first
            total_pages = self.get_pdf_page_count(pdf_path)

            # Determine page range
            actual_start = start_page if start_page is not None else 0
            actual_end = end_page if end_page is not None else total_pages
            actual_end = min(actual_end, total_pages)

            logger.info("Converting pages %d-%d of %d at %d DPI", actual_start + 1, actual_end, total_pages, dpi)

            # Convert pages one at a time to minimize memory
            images = []
            for page_num in range(actual_start, actual_end):
                img = self.convert_single_page(pdf_path, page_num, dpi)
                if img is not None:
                    images.append(img)
                else:
                    # Append None placeholder to maintain index alignment
                    images.append(None)

            logger.info("Converted %d pages to images (PyMuPDF)", len([i for i in images if i]))
            return images, total_pages
        else:
            # Fallback to pdf2image (requires Poppler)
            # Note: pdf2image uses 1-indexed pages
            first_page = (start_page + 1) if start_page is not None else None
            last_page = end_page if end_page is not None else None

            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                fmt='jpeg',
                first_page=first_page,
                last_page=last_page
            )

            # Get total pages separately
            total_pages = self.get_pdf_page_count(pdf_path)

            logger.info("Converted %d pages to images (pdf2image)", len(images))
            return images, total_pages
