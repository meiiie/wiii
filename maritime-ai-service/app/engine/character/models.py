"""
Character Models — Pydantic schemas for Wiii's living character state.

Sprint 93: Inspired by Letta/MemGPT Block model.

CharacterBlock:  A labeled, versioned text block that Wiii can self-edit.
                 Like Letta's "persona" block but with version tracking.
CharacterExperience: A logged experience event (milestone, learning, etc.)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Block Labels — What types of living state exist
# =============================================================================

class BlockLabel(str, Enum):
    """Labels for character state blocks."""

    LEARNED_LESSONS = "learned_lessons"
    FAVORITE_TOPICS = "favorite_topics"
    USER_PATTERNS = "user_patterns"
    SELF_NOTES = "self_notes"


# Default char limits per block (from identity YAML living_state config)
BLOCK_CHAR_LIMITS: Dict[str, int] = {
    BlockLabel.LEARNED_LESSONS: 1500,
    BlockLabel.FAVORITE_TOPICS: 800,
    BlockLabel.USER_PATTERNS: 800,
    BlockLabel.SELF_NOTES: 1000,
}


# =============================================================================
# Experience Types
# =============================================================================

class ExperienceType(str, Enum):
    """Types of experiences Wiii can log."""

    MILESTONE = "milestone"       # First time explaining a topic, etc.
    LEARNING = "learning"         # Something Wiii learned from a user
    FUNNY_MOMENT = "funny"        # A funny interaction
    USER_FEEDBACK = "feedback"    # Positive/negative feedback from user
    SELF_REFLECTION = "reflection"  # Wiii's own reflection


# =============================================================================
# CharacterBlock — Self-editable memory block
# =============================================================================

class CharacterBlock(BaseModel):
    """A labeled text block in Wiii's living character state.

    Follows Letta/MemGPT Block pattern:
    - Each block has a label (type), content (text), and char limit
    - Version field enables optimistic locking
    - is_core=True blocks cannot be auto-modified
    """

    id: UUID = Field(default_factory=uuid4)
    label: str = Field(..., description="Block label (learned_lessons, etc.)")
    content: str = Field(default="", description="Block content (Markdown text)")
    char_limit: int = Field(default=1000, description="Max characters for this block")
    version: int = Field(default=1, description="Version for optimistic locking")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def remaining_chars(self) -> int:
        """How many characters left before hitting limit."""
        return max(0, self.char_limit - len(self.content))

    def is_full(self) -> bool:
        """Whether block is at or over character limit."""
        return len(self.content) >= self.char_limit


class CharacterBlockCreate(BaseModel):
    """Schema for creating a new character block."""

    label: str
    content: str = ""
    char_limit: int = 1000
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CharacterBlockUpdate(BaseModel):
    """Schema for updating a character block.

    Supports two modes:
    - replace: Overwrite content entirely
    - append: Add text to existing content
    """

    content: Optional[str] = None
    append: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# CharacterExperience — Logged events
# =============================================================================

class CharacterExperience(BaseModel):
    """A logged experience event in Wiii's life."""

    id: UUID = Field(default_factory=uuid4)
    experience_type: str = Field(..., description="Type of experience")
    content: str = Field(..., description="What happened")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    user_id: Optional[str] = Field(default=None, description="Which user triggered this")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class CharacterExperienceCreate(BaseModel):
    """Schema for logging a new experience."""

    experience_type: str
    content: str
    importance: float = 0.5
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
