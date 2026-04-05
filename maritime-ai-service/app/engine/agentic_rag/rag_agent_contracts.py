"""Contracts and document parsing helpers for the RAG agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.knowledge_graph import Citation, KnowledgeNode


@dataclass
class EvidenceImage:
    """
    Evidence image reference for Multimodal RAG.

    CHỈ THỊ KỸ THUẬT SỐ 26: Evidence Images
    """

    url: str
    page_number: int
    document_id: str = ""


@dataclass
class RAGResponse:
    """
    Response from RAG Agent with citations.

    **Validates: Requirements 4.1**
    **Feature: multimodal-rag-vision** - Added evidence_images
    **Feature: document-kg** - Added entity_context for GraphRAG
    """

    content: str
    citations: list[Citation]
    is_fallback: bool = False
    disclaimer: Optional[str] = None
    evidence_images: list[EvidenceImage] = None
    entity_context: Optional[str] = None
    related_entities: list[str] = None
    native_thinking: Optional[str] = None

    def __post_init__(self):
        if self.evidence_images is None:
            self.evidence_images = []
        if self.related_entities is None:
            self.related_entities = []

    def has_citations(self) -> bool:
        return len(self.citations) > 0

    def has_evidence_images(self) -> bool:
        return len(self.evidence_images) > 0

    def has_entity_context(self) -> bool:
        return bool(self.entity_context)


class MaritimeDocumentParser:
    """
    Parser for maritime regulation documents.

    Extracts structured data from SOLAS, COLREGs, etc.
    """

    @staticmethod
    def parse_regulation(
        code: str,
        title: str,
        content: str,
        source: str = "",
    ) -> KnowledgeNode:
        """Parse a regulation into a KnowledgeNode."""
        from app.models.knowledge_graph import NodeType

        return KnowledgeNode(
            id=f"reg_{code.lower().replace('/', '_').replace('-', '_')}",
            node_type=NodeType.REGULATION,
            title=title,
            content=content,
            source=source,
            metadata={"code": code},
        )

    @staticmethod
    def serialize_to_document(node: KnowledgeNode) -> str:
        """Serialize a KnowledgeNode back to document format."""
        parts = []
        code = node.metadata.get("code", "")
        if code:
            parts.append(f"Code: {code}")

        parts.append(f"Title: {node.title}")
        parts.append(f"Content: {node.content}")

        if node.source:
            parts.append(f"Source: {node.source}")

        return "\n".join(parts)
