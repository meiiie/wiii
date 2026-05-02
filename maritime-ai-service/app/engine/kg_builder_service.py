"""Shared KG builder extraction service decoupled from multi-agent adapters."""

from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.engine.messages import Message
from app.engine.messages_adapters import to_openai_dict

logger = logging.getLogger(__name__)


class EntityItem(BaseModel):
    """Entity extracted from text."""

    id: str = Field(..., description="Unique snake_case ID")
    entity_type: str = Field(
        ...,
        description="Type: ARTICLE, REGULATION, VESSEL_TYPE, MANEUVER, EQUIPMENT, CONCEPT",
    )
    name: str = Field(..., description="English name")
    name_vi: Optional[str] = Field(None, description="Vietnamese name")
    description: str = Field("", description="Brief description")


class RelationItem(BaseModel):
    """Relation between entities."""

    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relation_type: str = Field(
        ...,
        description="Type: REFERENCES, APPLIES_TO, REQUIRES, DEFINES, PART_OF",
    )
    description: str = Field("", description="Relation description")


class ExtractionOutput(BaseModel):
    """Structured output for KG extraction."""

    entities: List[EntityItem] = Field(default_factory=list)
    relations: List[RelationItem] = Field(default_factory=list)


SYSTEM_PROMPT = """Bạn là KG Builder Agent - chuyên gia xây dựng Knowledge Graph từ văn bản hàng hải.

Nhiệm vụ: Trích xuất entities và relations từ văn bản.

Entity Types:
- ARTICLE: Điều/khoản (Điều 15, Rule 7)
- REGULATION: Quy định (COLREGs, SOLAS)
- VESSEL_TYPE: Loại tàu (tàu máy, tàu buồm)
- MANEUVER: Thao tác (nhường đường, cắt hướng)
- EQUIPMENT: Thiết bị (radar, AIS)
- CONCEPT: Khái niệm (tốc độ an toàn)

Relation Types:
- REFERENCES: Tham chiếu
- APPLIES_TO: Áp dụng cho
- REQUIRES: Yêu cầu
- DEFINES: Định nghĩa
- PART_OF: Thuộc về

Quy tắc:
1. ID phải là snake_case
2. Điền cả name (tiếng Anh) và name_vi (tiếng Việt)
3. Chỉ trích xuất entities thực sự có trong văn bản"""


class KGBuilderService:
    """Neutral KG extraction service shared by GraphRAG and agent adapters."""

    def __init__(self):
        self._llm = None
        self._structured_llm = None
        self._init_llm()

    def _init_llm(self):
        """Initialize KG builder LLM from the shared pool."""
        try:
            from app.engine.llm_pool import get_llm_moderate

            self._llm = get_llm_moderate()
            self._structured_llm = None
            if self._llm and hasattr(self._llm, "with_structured_output"):
                try:
                    self._structured_llm = self._llm.with_structured_output(ExtractionOutput)
                except Exception as exc:
                    logger.debug("KG Builder structured wrapper unavailable: %s", exc)
            logger.info("KG Builder LLM initialized from shared pool")
        except Exception as exc:
            logger.error("Failed to initialize KG Builder LLM: %s", exc)
            self._llm = None
            self._structured_llm = None

    async def extract(self, text: str, source: Optional[str] = None) -> ExtractionOutput:
        """Extract entities and relations from text."""
        from app.core.config import settings

        if not getattr(settings, "enable_neo4j", False):
            logger.debug("KG Builder skipped - enable_neo4j=False")
            return ExtractionOutput()

        if not self._llm:
            logger.warning("KG Builder LLM not available")
            return ExtractionOutput()

        try:
            user_content = f"""Nguồn: {source or 'unknown'}

Nội dung:
{text[:2500]}

Trích xuất entities và relations."""

            messages = [
                to_openai_dict(Message(role="system", content=SYSTEM_PROMPT)),
                to_openai_dict(Message(role="user", content=user_content)),
            ]

            if self._structured_llm is not None:
                result: ExtractionOutput = await self._structured_llm.ainvoke(messages)
            else:
                from app.services.structured_invoke_service import StructuredInvokeService

                result = await StructuredInvokeService.ainvoke(
                    llm=self._llm,
                    schema=ExtractionOutput,
                    payload=messages,
                    tier="moderate",
                )

            logger.info(
                "Extracted %d entities, %d relations",
                len(result.entities),
                len(result.relations),
            )
            return result
        except Exception as exc:
            logger.error("KG extraction failed: %s", exc)
            return ExtractionOutput()

    def is_available(self) -> bool:
        """Check if the underlying LLM is available."""
        return self._structured_llm is not None


_kg_builder_service: Optional[KGBuilderService] = None


def get_kg_builder_service() -> KGBuilderService:
    """Get or create the shared KG builder extraction service."""
    global _kg_builder_service
    if _kg_builder_service is None:
        _kg_builder_service = KGBuilderService()
    return _kg_builder_service
