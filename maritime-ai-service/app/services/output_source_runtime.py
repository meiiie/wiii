"""Source normalization and formatting helpers for output processing."""

from collections.abc import Mapping
from typing import Any, Dict, List

from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH
from app.models.schemas import Source


def coerce_source_mapping(source: Any) -> Dict[str, Any]:
    """Normalize citations/source objects into plain dictionaries."""
    if isinstance(source, Mapping):
        return dict(source)
    if hasattr(source, "model_dump"):
        return source.model_dump(exclude_none=True)
    if hasattr(source, "dict"):
        return source.dict(exclude_none=True)
    raise TypeError(f"Unsupported source type: {type(source)!r}")


def merge_same_page_sources(
    sources: List[Any],
    response_builder=None,
) -> List[Dict[str, Any]]:
    """Merge sources that point to the same document page."""
    normalized_sources = [coerce_source_mapping(source) for source in sources]

    if response_builder:
        return response_builder.merge_same_page_sources(normalized_sources)

    if not normalized_sources:
        return []

    page_groups: Dict[str, Dict[str, Any]] = {}

    for source in normalized_sources:
        doc_id = source.get("document_id")
        page_num = source.get("page_number")

        if doc_id and page_num:
            key = f"{doc_id}_{page_num}"
            if key not in page_groups:
                page_groups[key] = {
                    **source,
                    "bounding_boxes": [],
                }

            if source.get("bounding_boxes"):
                page_groups[key]["bounding_boxes"].extend(source["bounding_boxes"])
        else:
            key = source.get("node_id", str(len(page_groups)))
            if key not in page_groups:
                page_groups[key] = source

    return list(page_groups.values())


def format_sources(raw_sources: List[Any], response_builder=None) -> List[Source]:
    """Convert raw source payloads into API-facing Source models."""
    if not raw_sources:
        return []

    merged_sources = merge_same_page_sources(raw_sources, response_builder=response_builder)

    return [
        Source(
            node_id=source.get("node_id", ""),
            title=source.get("title", ""),
            source_type="knowledge_graph",
            content_snippet=source.get("content", "")[:MAX_CONTENT_SNIPPET_LENGTH],
            image_url=source.get("image_url"),
            page_number=source.get("page_number"),
            document_id=source.get("document_id"),
            bounding_boxes=source.get("bounding_boxes"),
        )
        for source in merged_sources
    ]
