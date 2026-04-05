"""
Contracts for multimodal ingestion and vision processing.

Extracted from multimodal_ingestion_service to break the service <-> processor
import cycle while preserving the public imports from the service module.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IngestionResult:
    """Result of PDF ingestion."""

    document_id: str
    total_pages: int
    successful_pages: int
    failed_pages: int
    pages_processed: int = 0
    errors: List[str] = field(default_factory=list)
    vision_pages: int = 0
    direct_pages: int = 0
    fallback_pages: int = 0

    @property
    def success_rate(self) -> float:
        target = self.pages_processed if self.pages_processed > 0 else self.total_pages
        if target == 0:
            return 0.0
        return (self.successful_pages / target) * 100

    @property
    def api_savings_percent(self) -> float:
        if self.total_pages == 0:
            return 0.0
        return (self.direct_pages / self.total_pages) * 100


@dataclass
class PageResult:
    """Result of single page processing."""

    page_number: int
    success: bool
    image_url: Optional[str] = None
    text_length: int = 0
    total_chunks: int = 0
    error: Optional[str] = None
    extraction_method: str = "vision"
    was_fallback: bool = False


__all__ = [
    "IngestionResult",
    "PageResult",
]
