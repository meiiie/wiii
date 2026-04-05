"""Parser helpers for course generation uploads."""

from __future__ import annotations

import asyncio
import os


def try_build_docling_parser(*, settings_obj, logger):
    try:
        from app.adapters.docling_parser import DoclingConfig, DoclingParserAdapter

        return DoclingParserAdapter(
            DoclingConfig(
                vlm_backend=getattr(settings_obj, "docling_vlm_backend", "none"),
                vlm_api_url=getattr(settings_obj, "docling_vlm_api_url", "") or "",
                vlm_api_key=getattr(settings_obj, "docling_vlm_api_key", "") or "",
                vlm_model=getattr(
                    settings_obj,
                    "docling_vlm_model",
                    "gemini-3.1-flash-lite",
                ),
            )
        )
    except ImportError:
        logger.warning("Docling not installed, using pymupdf fallback where possible")
        return None


def ensure_docling_available(ext: str, *, settings_obj, logger) -> None:
    if try_build_docling_parser(settings_obj=settings_obj, logger=logger) is None:
        raise RuntimeError(
            f"{ext} uploads require Docling support. Install Docling or upload a PDF instead."
        )


class BasicPdfParser:
    """Fallback parser using pymupdf (already installed)."""

    async def parse(self, file_path: str, options: dict | None = None):
        from app.ports.document_parser import ParsedDocument

        def _extract():
            if os.path.splitext(file_path)[1].lower() != ".pdf":
                raise RuntimeError("Basic parser only supports PDF uploads")
            try:
                import pymupdf

                doc = pymupdf.open(file_path)
                pages = [page.get_text() for page in doc]
                markdown = "\n\n---\n\n".join(
                    f"<!-- page {i + 1} -->\n{text}" for i, text in enumerate(pages)
                )
                return ParsedDocument(
                    markdown=markdown,
                    page_count=len(pages),
                    metadata={"title": os.path.basename(file_path)},
                    section_map={},
                    images=[],
                )
            except ImportError:
                with open(file_path, "r", errors="ignore", encoding="utf-8") as handle:
                    text = handle.read()
                return ParsedDocument(
                    markdown=text,
                    page_count=1,
                    metadata={"title": os.path.basename(file_path)},
                    section_map={},
                    images=[],
                )

        return await asyncio.to_thread(_extract)

    def supported_formats(self):
        return ["pdf"]


def get_parser(file_path: str, *, settings_obj, logger):
    """Get document parser: Docling if enabled, pymupdf fallback."""
    ext = os.path.splitext(file_path)[1].lower()
    should_use_docling = getattr(settings_obj, "use_docling_for_course_gen", False) or ext in {
        ".docx",
        ".pptx",
    }
    if should_use_docling:
        parser = try_build_docling_parser(settings_obj=settings_obj, logger=logger)
        if parser is not None:
            return parser
        if ext in {".docx", ".pptx"}:
            raise RuntimeError(f"{ext} uploads require the Docling parser to be installed")

    return BasicPdfParser()
