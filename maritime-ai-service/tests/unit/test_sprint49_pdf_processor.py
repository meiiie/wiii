"""
Tests for Sprint 49: PDFProcessor coverage.

Tests PDF processing including:
- get_pdf_page_count (mock fitz)
- convert_single_page (success, out of bounds, error)
- convert_pdf_to_images (full range, subset, failed pages, page range edge cases)
- DEFAULT_DPI constant
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from PIL import Image
import io


# ============================================================================
# Helpers
# ============================================================================


def _mock_fitz_document(num_pages=5):
    """Create a mock fitz document."""
    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=num_pages)
    mock_doc.close = MagicMock()

    # Create a real tiny JPEG for Image.open to parse
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = jpeg_bytes
    mock_page.get_pixmap.return_value = mock_pix
    mock_doc.load_page.return_value = mock_page

    return mock_doc


# ============================================================================
# DEFAULT_DPI
# ============================================================================


class TestConstants:
    """Test class constants."""

    def test_default_dpi(self):
        from app.services.pdf_processor import PDFProcessor
        assert PDFProcessor.DEFAULT_DPI == 150


# ============================================================================
# get_pdf_page_count
# ============================================================================


class TestGetPdfPageCount:
    """Test page counting."""

    def test_returns_page_count(self):
        from app.services.pdf_processor import PDFProcessor

        mock_doc = _mock_fitz_document(num_pages=10)
        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            proc = PDFProcessor()
            count = proc.get_pdf_page_count("/path/to/doc.pdf")

        assert count == 10
        mock_doc.close.assert_called_once()

    def test_single_page(self):
        from app.services.pdf_processor import PDFProcessor

        mock_doc = _mock_fitz_document(num_pages=1)
        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            proc = PDFProcessor()
            count = proc.get_pdf_page_count("/path/to/single.pdf")

        assert count == 1


# ============================================================================
# convert_single_page
# ============================================================================


class TestConvertSinglePage:
    """Test single page conversion."""

    def test_success(self):
        from app.services.pdf_processor import PDFProcessor

        mock_doc = _mock_fitz_document(num_pages=5)
        mock_matrix = MagicMock()
        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = mock_matrix
            proc = PDFProcessor()
            result = proc.convert_single_page("/path/to/doc.pdf", 0)

        assert isinstance(result, Image.Image)
        mock_doc.close.assert_called_once()

    def test_out_of_bounds(self):
        from app.services.pdf_processor import PDFProcessor

        mock_doc = _mock_fitz_document(num_pages=3)
        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            proc = PDFProcessor()
            result = proc.convert_single_page("/path/to/doc.pdf", 5)

        assert result is None
        mock_doc.close.assert_called_once()

    def test_error(self):
        from app.services.pdf_processor import PDFProcessor

        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("Corrupt PDF")
            proc = PDFProcessor()
            result = proc.convert_single_page("/path/to/bad.pdf", 0)

        assert result is None

    def test_custom_dpi(self):
        from app.services.pdf_processor import PDFProcessor

        mock_doc = _mock_fitz_document(num_pages=1)
        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()
            proc = PDFProcessor()
            result = proc.convert_single_page("/path/to/doc.pdf", 0, dpi=300)

        assert isinstance(result, Image.Image)
        # Verify Matrix was called with zoom = 300/72
        expected_zoom = 300 / 72
        mock_fitz.Matrix.assert_called_with(expected_zoom, expected_zoom)


# ============================================================================
# convert_pdf_to_images (PyMuPDF path)
# ============================================================================


class TestConvertPdfToImages:
    """Test batch page conversion."""

    def test_full_range(self):
        from app.services.pdf_processor import PDFProcessor

        proc = PDFProcessor()
        mock_doc = _mock_fitz_document(num_pages=3)

        with patch("app.services.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()

            # Patch convert_single_page to return real images
            with patch.object(proc, "convert_single_page") as mock_convert:
                mock_convert.return_value = Image.new("RGB", (10, 10))
                with patch.object(proc, "get_pdf_page_count", return_value=3):
                    with patch("app.services.pdf_processor.USE_PYMUPDF", True):
                        images, total = proc.convert_pdf_to_images("/path/to/doc.pdf")

        assert total == 3
        assert len(images) == 3
        assert mock_convert.call_count == 3

    def test_page_range(self):
        from app.services.pdf_processor import PDFProcessor

        proc = PDFProcessor()
        with patch.object(proc, "convert_single_page") as mock_convert:
            mock_convert.return_value = Image.new("RGB", (10, 10))
            with patch.object(proc, "get_pdf_page_count", return_value=10):
                with patch("app.services.pdf_processor.USE_PYMUPDF", True):
                    images, total = proc.convert_pdf_to_images(
                        "/path/to/doc.pdf", start_page=2, end_page=5
                    )

        assert total == 10
        assert len(images) == 3  # Pages 2, 3, 4
        assert mock_convert.call_count == 3

    def test_failed_page_returns_none(self):
        from app.services.pdf_processor import PDFProcessor

        proc = PDFProcessor()

        def side_effect(path, page_num, dpi=150):
            if page_num == 1:
                return None  # Failed page
            return Image.new("RGB", (10, 10))

        with patch.object(proc, "convert_single_page", side_effect=side_effect):
            with patch.object(proc, "get_pdf_page_count", return_value=3):
                with patch("app.services.pdf_processor.USE_PYMUPDF", True):
                    images, total = proc.convert_pdf_to_images("/path/to/doc.pdf")

        assert total == 3
        assert len(images) == 3
        assert images[1] is None  # Failed page is None placeholder

    def test_end_page_clamped_to_total(self):
        from app.services.pdf_processor import PDFProcessor

        proc = PDFProcessor()
        with patch.object(proc, "convert_single_page") as mock_convert:
            mock_convert.return_value = Image.new("RGB", (10, 10))
            with patch.object(proc, "get_pdf_page_count", return_value=3):
                with patch("app.services.pdf_processor.USE_PYMUPDF", True):
                    images, total = proc.convert_pdf_to_images(
                        "/path/to/doc.pdf", end_page=100
                    )

        assert total == 3
        assert len(images) == 3  # Clamped to 3

    def test_empty_pdf(self):
        from app.services.pdf_processor import PDFProcessor

        proc = PDFProcessor()
        with patch.object(proc, "convert_single_page") as mock_convert:
            with patch.object(proc, "get_pdf_page_count", return_value=0):
                with patch("app.services.pdf_processor.USE_PYMUPDF", True):
                    images, total = proc.convert_pdf_to_images("/path/to/empty.pdf")

        assert total == 0
        assert images == []
        mock_convert.assert_not_called()
