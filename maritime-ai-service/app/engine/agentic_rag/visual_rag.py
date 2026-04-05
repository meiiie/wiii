"""
Visual RAG — Query-time visual context enrichment.
Sprint 179+: "Mắt Thông Minh" — Understand charts/tables in documents.

When RAG retrieves documents that have image_url and visual content_type
(table, diagram_reference, formula), this module:
1. Fetches the page image from object storage
2. Uses Gemini Vision to analyze the visual content in context of the query
3. Appends the visual description to the document content
4. Returns enriched documents for generation

Feature-gated by enable_visual_rag in config.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.engine.vision_runtime import (
    analyze_image_for_query,
    fetch_image_as_base64,
)

logger = logging.getLogger(__name__)

# Visual content types that benefit from image analysis
VISUAL_CONTENT_TYPES = {"table", "diagram_reference", "formula"}

# Prompt for visual context analysis (Vietnamese-first)
VISUAL_ANALYSIS_PROMPT = """Bạn là chuyên gia phân tích tài liệu kỹ thuật.
Hãy mô tả chi tiết nội dung hình ảnh này trong ngữ cảnh câu hỏi của người dùng.

Câu hỏi: {query}

YÊU CẦU:
1. Mô tả cụ thể nội dung hình ảnh (bảng biểu, sơ đồ, biểu đồ, công thức).
2. Nếu là bảng biểu: liệt kê các cột, hàng quan trọng, số liệu chính.
3. Nếu là sơ đồ/biểu đồ: mô tả các thành phần, mối quan hệ, luồng dữ liệu.
4. Nếu là công thức: ghi lại công thức và giải thích các biến.
5. Liên hệ nội dung hình ảnh với câu hỏi nếu có thể.
6. Trả lời bằng tiếng Việt. Giữ nguyên thuật ngữ chuyên ngành bằng tiếng Anh.
7. CHỈ mô tả, KHÔNG trả lời câu hỏi.

Trả lời ngắn gọn, súc tích."""


@dataclass
class VisualAnalysisResult:
    """Result of visual analysis for a single document."""

    node_id: str
    description: str
    image_url: str
    content_type: str
    success: bool = True
    error: Optional[str] = None
    processing_time_ms: float = 0.0


@dataclass
class VisualEnrichmentResult:
    """Result of visual enrichment for all documents."""

    enriched_documents: List[Dict[str, Any]]
    visual_analyses: List[VisualAnalysisResult] = field(default_factory=list)
    total_images_analyzed: int = 0
    total_time_ms: float = 0.0


async def _fetch_image_as_base64(image_url: str, timeout: float = 10.0) -> Optional[str]:
    """Fetch image from URL and return as base64 string.

    Args:
        image_url: Public URL of the image (MinIO/S3).
        timeout: Request timeout in seconds.

    Returns:
        Base64-encoded image data, or None on failure.
    """
    return await fetch_image_as_base64(image_url, timeout=timeout)


async def _analyze_image_with_vision(
    image_base64: str,
    query: str,
    media_type: str = "image/jpeg",
) -> Optional[str]:
    """Use Gemini Vision to analyze an image in context of a query.

    Args:
        image_base64: Base64-encoded image data.
        query: User query for context.
        media_type: MIME type of the image.

    Returns:
        Visual description text, or None on failure.
    """
    result = await analyze_image_for_query(
        image_base64=image_base64,
        query=query,
        media_type=media_type,
    )
    if result.success and result.text:
        return result.text.strip()
    if result.error:
        logger.warning("[VisualRAG] Vision analysis error: %s", result.error)
    return None


def _select_visual_documents(
    documents: List[Dict[str, Any]],
    max_images: int = 3,
) -> List[Dict[str, Any]]:
    """Select documents that would benefit from visual analysis.

    Prioritizes documents with:
    1. Visual content types (table, diagram, formula)
    2. Non-empty image_url
    3. Higher relevance score

    Args:
        documents: Retrieved documents from hybrid search.
        max_images: Maximum number of images to analyze.

    Returns:
        Subset of documents eligible for visual analysis.
    """
    candidates = []
    for doc in documents:
        image_url = doc.get("image_url")
        if not image_url:
            continue

        content_type = doc.get("content_type", "text")
        # Priority: visual content types get score boost
        priority = 2.0 if content_type in VISUAL_CONTENT_TYPES else 1.0
        score = doc.get("score", 0) or 0
        candidates.append((priority * (score + 0.1), doc))

    # Sort by priority score descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in candidates[:max_images]]


async def enrich_documents_with_visual_context(
    documents: List[Dict[str, Any]],
    query: str,
    max_images: int = 3,
) -> VisualEnrichmentResult:
    """Enrich retrieved documents with visual context from page images.

    This is the main entry point for Visual RAG at query time.
    Feature-gated by enable_visual_rag in config.

    Args:
        documents: Retrieved documents from hybrid search (with image_url, content_type).
        query: User query for context-aware visual analysis.
        max_images: Maximum number of images to analyze per request.

    Returns:
        VisualEnrichmentResult with enriched documents and analysis metadata.
    """
    start = time.time()

    # Select candidates for visual analysis
    visual_docs = _select_visual_documents(documents, max_images)

    if not visual_docs:
        logger.debug("[VisualRAG] No documents eligible for visual analysis")
        return VisualEnrichmentResult(
            enriched_documents=documents,
            total_time_ms=(time.time() - start) * 1000,
        )

    logger.info("[VisualRAG] Analyzing %d images for visual context", len(visual_docs))

    # Build lookup for fast enrichment
    doc_node_ids = {doc.get("node_id"): doc for doc in visual_docs}

    # Fetch images in parallel
    fetch_tasks = {
        doc.get("node_id"): _fetch_image_as_base64(doc["image_url"])
        for doc in visual_docs
    }
    image_data = {}
    fetch_results = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)
    for node_id, result in zip(fetch_tasks.keys(), fetch_results):
        if isinstance(result, str):
            image_data[node_id] = result
        else:
            logger.debug("[VisualRAG] Failed to fetch image for %s: %s", node_id, result)

    if not image_data:
        logger.info("[VisualRAG] No images fetched successfully")
        return VisualEnrichmentResult(
            enriched_documents=documents,
            total_time_ms=(time.time() - start) * 1000,
        )

    # Analyze images in parallel
    analysis_tasks = {}
    for node_id, b64 in image_data.items():
        analysis_tasks[node_id] = _analyze_image_with_vision(b64, query)

    analysis_results_raw = await asyncio.gather(*analysis_tasks.values(), return_exceptions=True)

    analyses: List[VisualAnalysisResult] = []
    enrichment_map: Dict[str, str] = {}  # node_id → visual description

    for node_id, result in zip(analysis_tasks.keys(), analysis_results_raw):
        doc = doc_node_ids[node_id]
        t_start = time.time()
        if isinstance(result, str) and result:
            analyses.append(VisualAnalysisResult(
                node_id=node_id,
                description=result,
                image_url=doc.get("image_url", ""),
                content_type=doc.get("content_type", "text"),
                success=True,
                processing_time_ms=(time.time() - t_start) * 1000,
            ))
            enrichment_map[node_id] = result
        else:
            error_msg = str(result) if isinstance(result, Exception) else "No description generated"
            analyses.append(VisualAnalysisResult(
                node_id=node_id,
                description="",
                image_url=doc.get("image_url", ""),
                content_type=doc.get("content_type", "text"),
                success=False,
                error=error_msg,
            ))

    # Enrich documents by appending visual descriptions
    enriched = []
    for doc in documents:
        node_id = doc.get("node_id")
        if node_id in enrichment_map:
            enriched_doc = dict(doc)
            visual_desc = enrichment_map[node_id]
            enriched_doc["content"] = (
                doc.get("content", "")
                + f"\n\n[Mô tả hình ảnh trang {doc.get('page_number', '?')}]: {visual_desc}"
            )
            enriched_doc["visual_description"] = visual_desc
            enriched.append(enriched_doc)
        else:
            enriched.append(doc)

    total_ms = (time.time() - start) * 1000
    logger.info(
        "[VisualRAG] Enrichment complete: %d/%d images analyzed in %.0fms",
        len(enrichment_map),
        len(visual_docs),
        total_ms,
    )

    return VisualEnrichmentResult(
        enriched_documents=enriched,
        visual_analyses=analyses,
        total_images_analyzed=len(enrichment_map),
        total_time_ms=total_ms,
    )
