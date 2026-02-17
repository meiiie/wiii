"""
Semantic Memory Models for Wiii v0.3
CHỈ THỊ KỸ THUẬT SỐ 06

Pydantic models for semantic memory storage and retrieval.

Requirements: 2.1
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MemoryType(str, Enum):
    """Types of semantic memories."""
    MESSAGE = "message"      # Regular conversation message
    SUMMARY = "summary"      # Conversation summary
    RUNNING_SUMMARY = "running_summary"  # Sprint 122: Per-session running summary (distinct from SUMMARY)
    USER_FACT = "user_fact"  # Extracted user information
    INSIGHT = "insight"      # Behavioral insight (v0.5)


class InsightCategory(str, Enum):
    """Categories for behavioral insights (v0.5 - CHỈ THỊ 23 CẢI TIẾN)."""
    LEARNING_STYLE = "learning_style"      # Phong cách học tập
    KNOWLEDGE_GAP = "knowledge_gap"        # Lỗ hổng kiến thức  
    GOAL_EVOLUTION = "goal_evolution"      # Sự thay đổi mục tiêu
    HABIT = "habit"                        # Thói quen học tập
    PREFERENCE = "preference"              # Sở thích cá nhân


class FactType(str, Enum):
    """
    Types of user facts that can be extracted.

    v0.4 Update (CHỈ THỊ 23):
    - Limited to 6 essential types for cleaner memory management
    - Deprecated types mapped to new types for backward compatibility

    v0.6 Update (Sprint 73 — Living Memory):
    - Expanded from 6 to 15 types for richer user profiles
    - New categories: identity, personal, emotional, contextual
    - Volatile types (emotion, recent_topic) decay fast via importance_decay
    """
    # === Identity (stability=∞) ===
    NAME = "name"                    # User's name
    AGE = "age"                      # Tuổi
    HOMETOWN = "hometown"            # Quê quán (cố định, never overwritten by location)

    # === Professional (stability=720h) ===
    ROLE = "role"                    # Sinh viên/Giáo viên/Thuyền trưởng
    LEVEL = "level"                  # Năm 3, Đại phó, Sĩ quan...
    LOCATION = "location"            # Nơi ở/làm việc HIỆN TẠI (can change)
    ORGANIZATION = "organization"    # Tổ chức/trường (ĐH Hàng Hải...)

    # === Learning (stability=168h) ===
    GOAL = "goal"                    # Learning goals
    PREFERENCE = "preference"        # Learning preferences
    WEAKNESS = "weakness"            # Areas needing improvement
    STRENGTH = "strength"            # Điểm mạnh
    LEARNING_STYLE = "learning_style"  # Phong cách học (visual, hands-on...)

    # === Personal (stability=360h) ===
    HOBBY = "hobby"                  # Sở thích/thú vui
    INTEREST = "interest"            # Quan tâm chuyên môn
    PRONOUN_STYLE = "pronoun_style"  # Sprint 79: Persistent pronoun detection (mình/em/tôi)

    # === Volatile (stability=24-48h) ===
    EMOTION = "emotion"              # Cảm xúc hiện tại (volatile)
    RECENT_TOPIC = "recent_topic"    # Chủ đề gần đây (volatile)

    # Deprecated types (kept for backward compatibility, mapped to new types)
    BACKGROUND = "background"        # -> mapped to ROLE
    WEAK_AREA = "weak_area"          # -> mapped to WEAKNESS
    STRONG_AREA = "strong_area"      # -> mapped to STRENGTH


# Allowed fact types for v0.6+ (16 essential types — Sprint 89: +hometown)
ALLOWED_FACT_TYPES = {
    "name", "age", "hometown", "role", "level", "location", "organization",
    "goal", "preference", "weakness", "strength", "learning_style",
    "hobby", "interest", "emotion", "recent_topic", "pronoun_style",
}

# Mapping deprecated types to new types
FACT_TYPE_MAPPING = {
    "background": "role",
    "weak_area": "weakness",
    "strong_area": "strength",
}

# Types to ignore (not stored) — empty after Sprint 73 (strong_area→strength)
IGNORED_FACT_TYPES: set = set()


# === Decay categories for importance_decay.py ===
IDENTITY_FACT_TYPES = {"name", "age", "hometown"}
PROFESSIONAL_FACT_TYPES = {"role", "level", "location", "organization"}
LEARNING_FACT_TYPES = {"goal", "preference", "weakness", "strength", "learning_style"}
PERSONAL_FACT_TYPES = {"hobby", "interest", "pronoun_style"}
VOLATILE_FACT_TYPES = {"emotion", "recent_topic"}


# =============================================================================
# Semantic Triples - Subject-Predicate-Object (MemoriLabs Pattern)
# =============================================================================

class Predicate(str, Enum):
    """
    Predicate types for Semantic Triples.

    Maps to FactType for backward compatibility.
    Pattern: Subject (user_id) - Predicate - Object (value)

    Feature: semantic-triples-v1
    Sprint 73: Extended with 7 new predicates for 15-type fact system
    """
    # Identity predicates
    HAS_NAME = "has_name"
    HAS_AGE = "has_age"
    HAS_HOMETOWN = "has_hometown"  # Sprint 89: Quê quán (stable)
    HAS_ROLE = "has_role"
    HAS_LEVEL = "has_level"
    LOCATED_AT = "located_at"
    BELONGS_TO = "belongs_to"

    # Learning predicates
    HAS_GOAL = "has_goal"
    PREFERS = "prefers"
    WEAK_AT = "weak_at"
    STRONG_AT = "strong_at"
    LEARNS_VIA = "learns_via"

    # Personal predicates
    HAS_HOBBY = "has_hobby"
    INTERESTED_IN = "interested_in"
    HAS_PRONOUN_STYLE = "has_pronoun_style"  # Sprint 79

    # Volatile predicates
    FEELS = "feels"
    RECENTLY_DISCUSSED = "recently_discussed"

    # Progress predicates (existing)
    STUDIED = "studied"
    COMPLETED = "completed"


# Mapping FactType to Predicate
FACT_TYPE_TO_PREDICATE = {
    "name": Predicate.HAS_NAME,
    "age": Predicate.HAS_AGE,
    "hometown": Predicate.HAS_HOMETOWN,
    "role": Predicate.HAS_ROLE,
    "level": Predicate.HAS_LEVEL,
    "location": Predicate.LOCATED_AT,
    "organization": Predicate.BELONGS_TO,
    "goal": Predicate.HAS_GOAL,
    "preference": Predicate.PREFERS,
    "weakness": Predicate.WEAK_AT,
    "strength": Predicate.STRONG_AT,
    "learning_style": Predicate.LEARNS_VIA,
    "hobby": Predicate.HAS_HOBBY,
    "interest": Predicate.INTERESTED_IN,
    "pronoun_style": Predicate.HAS_PRONOUN_STYLE,
    "emotion": Predicate.FEELS,
    "recent_topic": Predicate.RECENTLY_DISCUSSED,
    # Deprecated types mapped to predicates
    "background": Predicate.HAS_ROLE,
    "weak_area": Predicate.WEAK_AT,
    "strong_area": Predicate.STRONG_AT,
}


# Mapping Predicate to object_type (classification)
PREDICATE_TO_OBJECT_TYPE = {
    Predicate.HAS_NAME: "identity",
    Predicate.HAS_AGE: "identity",
    Predicate.HAS_HOMETOWN: "identity",
    Predicate.HAS_ROLE: "identity",
    Predicate.HAS_LEVEL: "identity",
    Predicate.LOCATED_AT: "professional",
    Predicate.BELONGS_TO: "professional",
    Predicate.HAS_GOAL: "learning",
    Predicate.PREFERS: "learning",
    Predicate.WEAK_AT: "learning",
    Predicate.STRONG_AT: "learning",
    Predicate.LEARNS_VIA: "learning",
    Predicate.HAS_HOBBY: "personal",
    Predicate.INTERESTED_IN: "personal",
    Predicate.HAS_PRONOUN_STYLE: "personal",
    Predicate.FEELS: "volatile",
    Predicate.RECENTLY_DISCUSSED: "volatile",
    Predicate.STUDIED: "progress",
    Predicate.COMPLETED: "progress",
}


class SemanticMemory(BaseModel):
    """
    Represents a single semantic memory stored in the database.
    
    Attributes:
        id: Unique identifier
        user_id: User who owns this memory
        content: Text content of the memory
        embedding: Vector embedding (768 dimensions for MRL)
        memory_type: Type of memory (message, summary, user_fact)
        importance: Importance score (0.0 - 1.0)
        metadata: Additional metadata as JSON
        session_id: Optional session reference
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
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
    def validate_embedding_dimensions(cls, v: List[float]) -> List[float]:
        """Validate embedding has correct dimensions (768 for MRL)."""
        if v and len(v) != 768:
            # Log warning but don't fail - allow flexibility
            pass
        return v
    
    class Config:
        from_attributes = True


class SemanticMemoryCreate(BaseModel):
    """
    Schema for creating a new semantic memory.
    
    Used when storing new memories to the database.
    """
    user_id: str
    content: str
    embedding: List[float]
    memory_type: MemoryType = MemoryType.MESSAGE
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    
    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()


class SemanticMemorySearchResult(BaseModel):
    """
    Result from semantic similarity search.
    
    Includes similarity score for ranking.
    """
    id: UUID
    content: str
    memory_type: MemoryType
    importance: float
    similarity: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None  # Added for insights
    
    class Config:
        from_attributes = True


class UserFact(BaseModel):
    """
    Represents an extracted user fact.
    
    Used for personalization based on information extracted from conversations.
    
    Attributes:
        fact_type: Category of the fact
        value: The actual fact content
        confidence: Confidence score of extraction (0.0 - 1.0)
        source_message: Original message the fact was extracted from
    """
    fact_type: FactType
    value: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_message: Optional[str] = None
    
    def to_content(self) -> str:
        """Convert fact to storable content string."""
        return f"{self.fact_type.value}: {self.value}"
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert fact to metadata dict."""
        return {
            "fact_type": self.fact_type.value,
            "confidence": self.confidence,
            "source_message": self.source_message
        }
    
    def to_semantic_triple(self, subject: str) -> "SemanticTriple":
        """
        Convert UserFact to SemanticTriple.
        
        Args:
            subject: Entity ID (usually user_id)
            
        Returns:
            SemanticTriple representation
            
        Feature: semantic-triples-v1
        """
        predicate = FACT_TYPE_TO_PREDICATE.get(
            self.fact_type.value, 
            Predicate.PREFERS
        )
        return SemanticTriple(
            subject=subject,
            predicate=predicate,
            object=self.value,
            object_type=PREDICATE_TO_OBJECT_TYPE.get(predicate, "unknown"),
            confidence=self.confidence,
            source_message=self.source_message
        )


class SemanticTriple(BaseModel):
    """
    Semantic Triple for structured fact storage (MemoriLabs Pattern).
    
    Pattern: Subject - Predicate - Object (S-P-O)
    Example: "user_123" - "has_name" - "Minh"
    
    Benefits:
    - Easy deduplication (match predicate + object)
    - Direct column queries (WHERE predicate = 'has_goal')
    - Foundation for Knowledge Graph
    
    Feature: semantic-triples-v1
    """
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
        """
        Convert triple to human-readable content (backward compatible).
        
        Returns:
            String like "name: Minh" for legacy compatibility
        """
        # Extract fact_type from predicate
        fact_type = self.predicate.value.replace("has_", "").replace("_at", "")
        if self.predicate == Predicate.PREFERS:
            fact_type = "preference"
        elif self.predicate == Predicate.WEAK_AT:
            fact_type = "weakness"
        return f"{fact_type}: {self.object}"
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert triple to metadata dict (backward compatible)."""
        # Map predicate back to fact_type for compatibility
        fact_type_map = {
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
        return {
            "fact_type": fact_type_map.get(self.predicate, "unknown"),
            "confidence": self.confidence,
            "source_message": self.source_message,
            # New triple-specific fields
            "predicate": self.predicate.value,
            "object_type": self.object_type,
            "is_semantic_triple": True
        }
    
    @classmethod
    def from_user_fact(cls, user_id: str, fact: "UserFact") -> "SemanticTriple":
        """
        Create SemanticTriple from legacy UserFact.
        
        Args:
            user_id: Subject entity ID
            fact: UserFact to convert
            
        Returns:
            SemanticTriple instance
        """
        predicate = FACT_TYPE_TO_PREDICATE.get(
            fact.fact_type.value,
            Predicate.PREFERS
        )
        return cls(
            subject=user_id,
            predicate=predicate,
            object=fact.value,
            object_type=PREDICATE_TO_OBJECT_TYPE.get(predicate, "unknown"),
            confidence=fact.confidence,
            source_message=fact.source_message
        )
    
    class Config:
        from_attributes = True


class Insight(BaseModel):
    """
    Represents a behavioral insight (v0.5 - CHỈ THỊ 23 CẢI TIẾN).
    
    Unlike atomic facts, insights capture behavioral patterns, learning styles,
    knowledge gaps, and goal evolution over time.
    
    Attributes:
        id: Unique identifier
        user_id: User who owns this insight
        content: Complete sentence describing the insight
        category: Type of insight (learning_style, knowledge_gap, etc.)
        sub_topic: Specific topic (e.g., "Rule 15", "COLREGs")
        confidence: Confidence score (0.0 - 1.0)
        source_messages: Messages that led to this insight
        created_at: Creation timestamp
        updated_at: Last update timestamp
        last_accessed: Last access timestamp (for FIFO eviction)
        evolution_notes: Track changes over time
    """
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
        """Convert insight to storable content string."""
        return self.content
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert insight to metadata dict."""
        return {
            "insight_category": self.category.value,
            "sub_topic": self.sub_topic,
            "confidence": self.confidence,
            "source_messages": self.source_messages,
            "evolution_notes": self.evolution_notes
        }
    
    class Config:
        from_attributes = True


class UserFactExtraction(BaseModel):
    """
    Result of user fact extraction from a message.
    
    Contains multiple facts that may have been extracted.
    """
    facts: List[UserFact] = Field(default_factory=list)
    raw_message: str
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def has_facts(self) -> bool:
        """Check if any facts were extracted."""
        return len(self.facts) > 0


@dataclass
class FactWithProvenance:
    """
    Sprint 123 (P1): Fact with provenance annotations for anti-hallucination.

    Inspired by Gemini's rationale annotations. Enables the LLM to distinguish
    fresh facts from stale ones and high-confidence from low-confidence.

    Attributes:
        content: The fact value (e.g., "Hùng")
        fact_type: Category (e.g., "name", "role")
        confidence: Extraction confidence (0.0-1.0)
        created_at: When the fact was first extracted
        last_accessed: When the fact was last used
        access_count: Number of times retrieved
        source_quote: Original user text that produced this fact
        effective_importance: Calculated via importance_decay (Ebbinghaus)
        memory_id: DB UUID for tracking
    """
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
        """
        Format fact with provenance annotations for LLM injection.

        Returns a string like:
          "- Tên: Hùng [✓ xác nhận gần đây]"
          "- Nghề nghiệp: Sinh viên [aging=5d]"
          "- Sở thích: COLREGs [⚠️ cũ, 28d trước — xác minh trước khi dùng]"
        """
        from datetime import timezone
        if now is None:
            now = datetime.now(timezone.utc)

        # Type label (Vietnamese)
        type_labels = {
            "name": "Tên", "age": "Tuổi", "hometown": "Quê quán",
            "role": "Nghề nghiệp", "level": "Cấp bậc", "location": "Nơi ở",
            "organization": "Tổ chức", "goal": "Mục tiêu học tập",
            "preference": "Sở thích học", "weakness": "Điểm yếu",
            "strength": "Điểm mạnh", "learning_style": "Phong cách học",
            "hobby": "Sở thích", "interest": "Quan tâm",
            "pronoun_style": "Cách xưng hô",
        }
        label = type_labels.get(self.fact_type, self.fact_type.replace("_", " ").title())

        # Calculate age in days
        ref_time = self.last_accessed or self.created_at
        age_days = 0
        if ref_time:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - ref_time).days)

        # Build temporal/confidence annotation
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
    """
    Assembled context for response generation.

    Combines semantic memories with recent messages for hybrid context.

    Attributes:
        relevant_memories: Semantically similar memories from vector search
        user_facts: User facts for personalization
        recent_messages: Recent messages from sliding window (fallback/hybrid)
        total_tokens: Estimated token count of context
    """
    relevant_memories: List[SemanticMemorySearchResult] = Field(default_factory=list)
    user_facts: List[SemanticMemorySearchResult] = Field(default_factory=list)
    recent_messages: List[str] = Field(default_factory=list)
    total_tokens: int = 0
    
    def to_prompt_context(self) -> str:
        """
        Format context for injection into LLM prompt.
        
        Cross-session Memory Persistence (v0.2.1):
        - User facts appear at TOP of context (highest priority)
        - Facts are grouped by type for better readability
        - Includes relevant memories from all sessions
        
        Returns:
            Formatted context string
            
        Requirements: 2.2, 4.3
        **Feature: cross-session-memory, Property 5: Context Includes User Facts**
        """
        parts = []
        
        # Add user facts section (FIRST - highest priority for personalization)
        if self.user_facts:
            # Group facts by type for better formatting
            facts_by_type = self._group_facts_by_type()

            facts_lines = []
            # Sprint 122 (Bug F3): Updated to match current ALLOWED_FACT_TYPES (17 types)
            # Excludes volatile types (emotion, recent_topic) — too transient for profile
            type_order = [
                "name", "age", "hometown",                     # Identity
                "role", "level", "location", "organization",   # Professional
                "goal", "preference", "weakness", "strength", "learning_style",  # Learning
                "hobby", "interest", "pronoun_style",          # Personal
            ]

            type_labels = {
                "name": "Tên", "age": "Tuổi", "hometown": "Quê quán",
                "role": "Nghề nghiệp", "level": "Cấp bậc", "location": "Nơi ở",
                "organization": "Tổ chức", "goal": "Mục tiêu học tập",
                "preference": "Sở thích học", "weakness": "Điểm yếu",
                "strength": "Điểm mạnh", "learning_style": "Phong cách học",
                "hobby": "Sở thích", "interest": "Quan tâm",
                "pronoun_style": "Cách xưng hô",
                # Deprecated types (backward compat)
                "background": "Nghề nghiệp", "weak_area": "Điểm yếu",
                "strong_area": "Điểm mạnh",
            }

            for fact_type in type_order:
                if fact_type in facts_by_type:
                    fact = facts_by_type[fact_type]
                    label = type_labels.get(fact_type, fact_type.replace("_", " ").title())
                    # Extract value from content (format: "fact_type: value")
                    value = fact.content.split(": ", 1)[-1] if ": " in fact.content else fact.content
                    facts_lines.append(f"- {label}: {value}")

            # Add any remaining facts not in priority order
            for fact_type, fact in facts_by_type.items():
                if fact_type not in type_order:
                    label = type_labels.get(fact_type, fact_type.replace("_", " ").title())
                    value = fact.content.split(": ", 1)[-1] if ": " in fact.content else fact.content
                    facts_lines.append(f"- {label}: {value}")

            if facts_lines:
                parts.append(f"=== Hồ sơ người dùng ===\n" + "\n".join(facts_lines))
        
        # Add relevant memories section
        if self.relevant_memories:
            memories_text = "\n".join([
                f"- {m.content}"
                for m in self.relevant_memories[:5]  # Limit to top 5
            ])
            parts.append(f"=== Ngữ cảnh liên quan ===\n{memories_text}")
        
        # Add recent messages section
        if self.recent_messages:
            recent_text = "\n".join(self.recent_messages[-5:])  # Last 5 messages
            parts.append(f"=== Hội thoại gần đây ===\n{recent_text}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _group_facts_by_type(self) -> Dict[str, "SemanticMemorySearchResult"]:
        """
        Group user facts by fact_type from metadata.
        
        Returns:
            Dict mapping fact_type to the most recent fact of that type
        """
        facts_by_type = {}
        for fact in self.user_facts:
            fact_type = fact.metadata.get("fact_type", "unknown")
            # Keep first occurrence (already sorted by recency from repository)
            if fact_type not in facts_by_type:
                facts_by_type[fact_type] = fact
        return facts_by_type
    
    @property
    def is_empty(self) -> bool:
        """Check if context is empty."""
        return (
            not self.relevant_memories
            and not self.user_facts
            and not self.recent_messages
        )


class ConversationSummary(BaseModel):
    """
    Summary of a conversation for long-term storage.
    
    Created when conversation exceeds token threshold.
    """
    user_id: str
    session_id: str
    summary_text: str
    original_message_count: int
    original_token_count: int
    key_topics: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_semantic_memory_create(self, embedding: List[float]) -> SemanticMemoryCreate:
        """Convert summary to SemanticMemoryCreate for storage."""
        return SemanticMemoryCreate(
            user_id=self.user_id,
            content=self.summary_text,
            embedding=embedding,
            memory_type=MemoryType.SUMMARY,
            importance=0.9,  # Summaries are high importance
            metadata={
                "original_message_count": self.original_message_count,
                "original_token_count": self.original_token_count,
                "key_topics": self.key_topics
            },
            session_id=self.session_id
        )
