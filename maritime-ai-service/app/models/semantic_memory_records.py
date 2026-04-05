"""
Semantic memory data models and prompt-facing helpers.

Extracted from app.models.semantic_memory to reduce ownership density in the
public facade module without breaking existing imports.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.semantic_memory_types import (
    FACT_TYPE_TO_PREDICATE,
    InsightCategory,
    FactType,
    MemoryType,
    PREDICATE_TO_OBJECT_TYPE,
    Predicate,
)


TRIPLE_TO_FACT_TYPE = {
    Predicate.HAS_NAME: "name",
    Predicate.HAS_AGE: "age",
    Predicate.HAS_HOMETOWN: "hometown",
    Predicate.HAS_ROLE: "role",
    Predicate.HAS_LEVEL: "level",
    Predicate.LOCATED_AT: "location",
    Predicate.BELONGS_TO: "organization",
    Predicate.HAS_GOAL: "goal",
    Predicate.PREFERS: "preference",
    Predicate.WEAK_AT: "weakness",
    Predicate.STRONG_AT: "strength",
    Predicate.LEARNS_VIA: "learning_style",
    Predicate.HAS_HOBBY: "hobby",
    Predicate.INTERESTED_IN: "interest",
    Predicate.HAS_PRONOUN_STYLE: "pronoun_style",
    Predicate.FEELS: "emotion",
    Predicate.RECENTLY_DISCUSSED: "recent_topic",
    Predicate.STUDIED: "progress",
    Predicate.COMPLETED: "progress",
}

PROMPT_FACT_TYPE_ORDER = [
    "name",
    "age",
    "hometown",
    "role",
    "level",
    "location",
    "organization",
    "goal",
    "preference",
    "weakness",
    "strength",
    "learning_style",
    "hobby",
    "interest",
    "pronoun_style",
]

PROMPT_FACT_TYPE_LABELS = {
    "name": "Tên",
    "age": "Tuổi",
    "hometown": "Quê quán",
    "role": "Nghề nghiệp",
    "level": "Cấp bậc",
    "location": "Nơi ở",
    "organization": "Tổ chức",
    "goal": "Mục tiêu học tập",
    "preference": "Sở thích học",
    "weakness": "Điểm yếu",
    "strength": "Điểm mạnh",
    "learning_style": "Phong cách học",
    "hobby": "Sở thích",
    "interest": "Quan tâm",
    "pronoun_style": "Cách xưng hô",
    "background": "Nghề nghiệp",
    "weak_area": "Điểm yếu",
    "strong_area": "Điểm mạnh",
}

PROVENANCE_FACT_TYPE_LABELS = {
    "name": "Tên",
    "age": "Tuổi",
    "hometown": "Quê quán",
    "role": "Nghề nghiệp",
    "level": "Cấp bậc",
    "location": "Nơi ở",
    "organization": "Tổ chức",
    "goal": "Mục tiêu học tập",
    "preference": "Sở thích học",
    "weakness": "Điểm yếu",
    "strength": "Điểm mạnh",
    "learning_style": "Phong cách học",
    "hobby": "Sở thích",
    "interest": "Quan tâm",
    "pronoun_style": "Cách xưng hô",
}


class SemanticMemory(BaseModel):
    """Represents a single semantic memory stored in the database."""

    id: UUID
    user_id: str
    content: str
    embedding: List[float] = Field(default_factory=list)
    memory_type: MemoryType = MemoryType.MESSAGE
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, value: List[float]) -> List[float]:
        """Validate embedding has correct dimensions (768 for MRL)."""
        if value and len(value) != 768:
            pass
        return value

    class Config:
        from_attributes = True


class SemanticMemoryCreate(BaseModel):
    """Schema for creating a new semantic memory."""

    user_id: str
    content: str
    embedding: List[float]
    memory_type: MemoryType = MemoryType.MESSAGE
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, value: str) -> str:
        """Ensure content is not empty."""
        if not value or not value.strip():
            raise ValueError("Content cannot be empty")
        return value.strip()


class SemanticMemorySearchResult(BaseModel):
    """Result from semantic similarity search."""

    id: UUID
    content: str
    memory_type: MemoryType
    importance: float
    similarity: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserFact(BaseModel):
    """Represents an extracted user fact."""

    fact_type: FactType
    value: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_message: Optional[str] = None

    def to_content(self) -> str:
        return f"{self.fact_type.value}: {self.value}"

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "fact_type": self.fact_type.value,
            "confidence": self.confidence,
            "source_message": self.source_message,
        }

    def to_semantic_triple(self, subject: str) -> "SemanticTriple":
        predicate = FACT_TYPE_TO_PREDICATE.get(self.fact_type.value, Predicate.PREFERS)
        return SemanticTriple(
            subject=subject,
            predicate=predicate,
            object=self.value,
            object_type=PREDICATE_TO_OBJECT_TYPE.get(predicate, "unknown"),
            confidence=self.confidence,
            source_message=self.source_message,
        )


class SemanticTriple(BaseModel):
    """Semantic Triple for structured fact storage."""

    subject: str = Field(..., description="Entity ID (user_id)")
    predicate: Predicate = Field(..., description="Relationship type")
    object: str = Field(..., description="Value/target of relationship")
    object_type: str = Field(default="unknown", description="Classification: identity, learning, progress")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    embedding: List[float] = Field(default_factory=list, description="768-dim vector for semantic search")
    source_message: Optional[str] = Field(default=None, description="Original message")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_content(self) -> str:
        fact_type = self.predicate.value.replace("has_", "").replace("_at", "")
        if self.predicate == Predicate.PREFERS:
            fact_type = "preference"
        elif self.predicate == Predicate.WEAK_AT:
            fact_type = "weakness"
        return f"{fact_type}: {self.object}"

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "fact_type": TRIPLE_TO_FACT_TYPE.get(self.predicate, "unknown"),
            "confidence": self.confidence,
            "source_message": self.source_message,
            "predicate": self.predicate.value,
            "object_type": self.object_type,
            "is_semantic_triple": True,
        }

    @classmethod
    def from_user_fact(cls, user_id: str, fact: UserFact) -> "SemanticTriple":
        predicate = FACT_TYPE_TO_PREDICATE.get(fact.fact_type.value, Predicate.PREFERS)
        return cls(
            subject=user_id,
            predicate=predicate,
            object=fact.value,
            object_type=PREDICATE_TO_OBJECT_TYPE.get(predicate, "unknown"),
            confidence=fact.confidence,
            source_message=fact.source_message,
        )

    class Config:
        from_attributes = True


class Insight(BaseModel):
    """Represents a behavioral insight."""

    id: Optional[UUID] = None
    user_id: str
    content: str
    category: InsightCategory
    sub_topic: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_messages: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    evolution_notes: List[str] = Field(default_factory=list)

    def to_content(self) -> str:
        return self.content

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "insight_category": self.category.value,
            "sub_topic": self.sub_topic,
            "confidence": self.confidence,
            "source_messages": self.source_messages,
            "evolution_notes": self.evolution_notes,
        }

    class Config:
        from_attributes = True


class UserFactExtraction(BaseModel):
    """Result of user fact extraction from a message."""

    facts: List[UserFact] = Field(default_factory=list)
    raw_message: str
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_facts(self) -> bool:
        return len(self.facts) > 0


@dataclass
class FactWithProvenance:
    """Fact with provenance annotations for anti-hallucination."""

    content: str
    fact_type: str
    confidence: float = 0.8
    created_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source_quote: Optional[str] = None
    effective_importance: float = 0.5
    memory_id: Optional[UUID] = None

    def format_for_prompt(self, now: Optional[datetime] = None) -> str:
        from datetime import timezone

        if now is None:
            now = datetime.now(timezone.utc)

        label = PROVENANCE_FACT_TYPE_LABELS.get(
            self.fact_type,
            self.fact_type.replace("_", " ").title(),
        )

        ref_time = self.last_accessed or self.created_at
        age_days = 0
        if ref_time:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - ref_time).days)

        annotations = []
        if age_days <= 3:
            annotations.append("✓ xác nhận gần đây")
        elif age_days <= 14:
            annotations.append(f"aging={age_days}d")
        else:
            annotations.append(f"⚠️ cũ, {age_days}d trước — xác minh trước khi dùng")

        if self.confidence < 0.7:
            annotations.append("độ tin cậy thấp — coi như chưa chắc chắn")

        annotation_str = ", ".join(annotations)
        return f"- {label}: {self.content} [{annotation_str}]"


class SemanticContext(BaseModel):
    """Assembled context for response generation."""

    relevant_memories: List[SemanticMemorySearchResult] = Field(default_factory=list)
    user_facts: List[SemanticMemorySearchResult] = Field(default_factory=list)
    recent_messages: List[str] = Field(default_factory=list)
    total_tokens: int = 0

    def to_prompt_context(self) -> str:
        parts = []

        if self.user_facts:
            facts_by_type = self._group_facts_by_type()
            facts_lines = []

            for fact_type in PROMPT_FACT_TYPE_ORDER:
                if fact_type in facts_by_type:
                    fact = facts_by_type[fact_type]
                    label = PROMPT_FACT_TYPE_LABELS.get(
                        fact_type,
                        fact_type.replace("_", " ").title(),
                    )
                    value = fact.content.split(": ", 1)[-1] if ": " in fact.content else fact.content
                    facts_lines.append(f"- {label}: {value}")

            for fact_type, fact in facts_by_type.items():
                if fact_type not in PROMPT_FACT_TYPE_ORDER:
                    label = PROMPT_FACT_TYPE_LABELS.get(
                        fact_type,
                        fact_type.replace("_", " ").title(),
                    )
                    value = fact.content.split(": ", 1)[-1] if ": " in fact.content else fact.content
                    facts_lines.append(f"- {label}: {value}")

            if facts_lines:
                parts.append("=== Hồ sơ người dùng ===\n" + "\n".join(facts_lines))

        if self.relevant_memories:
            memories_text = "\n".join(f"- {memory.content}" for memory in self.relevant_memories[:5])
            parts.append(f"=== Ngữ cảnh liên quan ===\n{memories_text}")

        if self.recent_messages:
            recent_text = "\n".join(self.recent_messages[-5:])
            parts.append(f"=== Hội thoại gần đây ===\n{recent_text}")

        return "\n\n".join(parts) if parts else ""

    def _group_facts_by_type(self) -> Dict[str, SemanticMemorySearchResult]:
        facts_by_type: Dict[str, SemanticMemorySearchResult] = {}
        for fact in self.user_facts:
            fact_type = fact.metadata.get("fact_type", "unknown")
            if fact_type not in facts_by_type:
                facts_by_type[fact_type] = fact
        return facts_by_type

    @property
    def is_empty(self) -> bool:
        return not self.relevant_memories and not self.user_facts and not self.recent_messages


class ConversationSummary(BaseModel):
    """Summary of a conversation for long-term storage."""

    user_id: str
    session_id: str
    summary_text: str
    original_message_count: int
    original_token_count: int
    key_topics: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_semantic_memory_create(self, embedding: List[float]) -> SemanticMemoryCreate:
        return SemanticMemoryCreate(
            user_id=self.user_id,
            content=self.summary_text,
            embedding=embedding,
            memory_type=MemoryType.SUMMARY,
            importance=0.9,
            metadata={
                "original_message_count": self.original_message_count,
                "original_token_count": self.original_token_count,
                "key_topics": self.key_topics,
            },
            session_id=self.session_id,
        )


__all__ = [
    "ConversationSummary",
    "FactWithProvenance",
    "Insight",
    "PROMPT_FACT_TYPE_LABELS",
    "PROMPT_FACT_TYPE_ORDER",
    "SemanticContext",
    "SemanticMemory",
    "SemanticMemoryCreate",
    "SemanticMemorySearchResult",
    "SemanticTriple",
    "TRIPLE_TO_FACT_TYPE",
    "UserFact",
    "UserFactExtraction",
]
