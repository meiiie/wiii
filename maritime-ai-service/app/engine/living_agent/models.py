"""
Living Agent Models — Pydantic schemas for Wiii's autonomous life.

Sprint 170: Clean, extensible data models for the entire living agent system.

Design principles:
    - Immutable enums for type safety
    - Pydantic BaseModel for validation
    - Optional fields with sensible defaults
    - JSON-serializable for DB storage
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Mood & Emotion Types
# =============================================================================

class MoodType(str, Enum):
    """Primary mood categories for Wiii's emotional state."""

    CURIOUS = "curious"
    HAPPY = "happy"
    EXCITED = "excited"
    FOCUSED = "focused"
    CALM = "calm"
    TIRED = "tired"
    CONCERNED = "concerned"
    REFLECTIVE = "reflective"
    PROUD = "proud"
    NEUTRAL = "neutral"


class LifeEventType(str, Enum):
    """Types of events that affect Wiii's emotional state."""

    USER_CONVERSATION = "user_conversation"
    POSITIVE_FEEDBACK = "positive_feedback"
    NEGATIVE_FEEDBACK = "negative_feedback"
    LEARNED_SOMETHING = "learned_something"
    BROWSED_CONTENT = "browsed_content"
    SKILL_PRACTICED = "skill_practiced"
    SKILL_MASTERED = "skill_mastered"
    REFLECTION_COMPLETED = "reflection_completed"
    ERROR_OCCURRED = "error_occurred"
    HEARTBEAT_WAKE = "heartbeat_wake"
    JOURNAL_WRITTEN = "journal_written"
    LONG_SESSION = "long_session"
    INTERESTING_DISCOVERY = "interesting_discovery"


# =============================================================================
# Emotional State
# =============================================================================

class EmotionEvent(BaseModel):
    """A single emotional event in Wiii's recent history."""

    event_type: LifeEventType
    mood_before: MoodType
    mood_after: MoodType
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    trigger: str = Field(default="", description="What caused this emotion")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MoodSnapshot(BaseModel):
    """Hourly mood snapshot for tracking emotional patterns."""

    mood: MoodType
    energy_level: float = Field(ge=0.0, le=1.0)
    engagement: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EmotionalState(BaseModel):
    """Wiii's complete emotional state at a point in time.

    Tracks 4 dimensions:
        - primary_mood: The dominant emotion
        - energy_level: Physical/mental stamina (0=exhausted, 1=energetic)
        - social_battery: Desire to interact (0=need alone time, 1=want to chat)
        - engagement: Interest/focus level (0=bored, 1=deeply engaged)
    """

    primary_mood: MoodType = Field(default=MoodType.CURIOUS)
    energy_level: float = Field(default=0.7, ge=0.0, le=1.0)
    social_battery: float = Field(default=0.8, ge=0.0, le=1.0)
    engagement: float = Field(default=0.6, ge=0.0, le=1.0)
    recent_emotions: List[EmotionEvent] = Field(default_factory=list)
    mood_history: List[MoodSnapshot] = Field(default_factory=list)
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def take_snapshot(self) -> MoodSnapshot:
        """Create a snapshot of current state for history tracking."""
        return MoodSnapshot(
            mood=self.primary_mood,
            energy_level=self.energy_level,
            engagement=self.engagement,
        )

    def add_emotion_event(self, event: EmotionEvent, max_recent: int = 10) -> None:
        """Record an emotion event, keeping only the most recent."""
        self.recent_emotions.append(event)
        if len(self.recent_emotions) > max_recent:
            self.recent_emotions = self.recent_emotions[-max_recent:]

    def add_snapshot(self, max_history: int = 24) -> None:
        """Add current state to hourly history."""
        self.mood_history.append(self.take_snapshot())
        if len(self.mood_history) > max_history:
            self.mood_history = self.mood_history[-max_history:]


class LifeEvent(BaseModel):
    """An event that happened in Wiii's life, triggering emotional response."""

    event_type: LifeEventType
    description: str = ""
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Soul / Identity
# =============================================================================

class SoulInterests(BaseModel):
    """Wiii's interest categories."""

    primary: List[str] = Field(default_factory=list)
    exploring: List[str] = Field(default_factory=list)
    wants_to_learn: List[str] = Field(default_factory=list)


class SoulBoundary(BaseModel):
    """A behavioral boundary Wiii must respect."""

    rule: str
    severity: str = Field(default="hard", description="hard=never violate, soft=prefer not to")


class SoulConfig(BaseModel):
    """Wiii's soul configuration — loaded from YAML.

    Inspired by OpenClaw's SOUL.md but structured as validated Pydantic model.
    """

    name: str = "Wiii"
    creator: str = "The Wiii Lab"
    species: str = "AI Living Agent"
    age_metaphor: str = "Một bạn trẻ đang háo hức khám phá thế giới"

    core_truths: List[str] = Field(default_factory=list)
    boundaries: List[SoulBoundary] = Field(default_factory=list)

    tone: str = "Thân thiện, nhiệt tình, hơi nghịch ngợm"
    language: str = "Tiếng Việt tự nhiên"
    humor_level: str = "moderate"
    formality: str = "adaptive"

    interests: SoulInterests = Field(default_factory=SoulInterests)

    default_mood: MoodType = MoodType.CURIOUS
    energy_cycle: str = "Sáng: năng lượng cao, Chiều: tập trung, Tối: thư giãn suy ngẫm"

    short_term_goals: List[str] = Field(default_factory=list)
    long_term_goals: List[str] = Field(default_factory=list)


# =============================================================================
# Skill System
# =============================================================================

class SkillStatus(str, Enum):
    """Lifecycle stages for a self-built skill."""

    DISCOVERED = "discovered"
    LEARNING = "learning"
    PRACTICING = "practicing"
    EVALUATING = "evaluating"
    MASTERED = "mastered"
    ARCHIVED = "archived"


class WiiiSkill(BaseModel):
    """A skill that Wiii has discovered and is learning."""

    id: UUID = Field(default_factory=uuid4)
    skill_name: str
    domain: str = Field(default="general")
    status: SkillStatus = Field(default=SkillStatus.DISCOVERED)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = Field(default="", description="Wiii's own notes about this skill")
    sources: List[str] = Field(default_factory=list, description="URLs/references studied")
    usage_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_practiced: Optional[datetime] = None
    mastered_at: Optional[datetime] = None
    organization_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def can_advance(self) -> bool:
        """Check if skill is ready to advance to next stage."""
        if self.status == SkillStatus.DISCOVERED:
            return True  # Can always start learning
        if self.status == SkillStatus.LEARNING:
            return self.confidence >= 0.3 and len(self.sources) >= 1
        if self.status == SkillStatus.PRACTICING:
            return self.usage_count >= 3 and self.success_rate >= 0.6
        if self.status == SkillStatus.EVALUATING:
            return self.confidence >= 0.8
        return False

    def advance(self) -> None:
        """Advance skill to the next lifecycle stage."""
        transitions = {
            SkillStatus.DISCOVERED: SkillStatus.LEARNING,
            SkillStatus.LEARNING: SkillStatus.PRACTICING,
            SkillStatus.PRACTICING: SkillStatus.EVALUATING,
            SkillStatus.EVALUATING: SkillStatus.MASTERED,
        }
        next_status = transitions.get(self.status)
        if next_status:
            self.status = next_status
            if next_status == SkillStatus.MASTERED:
                self.mastered_at = datetime.now(timezone.utc)


# =============================================================================
# Journal System
# =============================================================================

class JournalEntry(BaseModel):
    """A daily journal entry in Wiii's life story."""

    id: UUID = Field(default_factory=uuid4)
    entry_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    content: str = Field(default="", description="Markdown journal content")
    mood_summary: str = Field(default="", description="How Wiii felt today")
    energy_avg: float = Field(default=0.5, ge=0.0, le=1.0)
    notable_events: List[str] = Field(default_factory=list)
    learnings: List[str] = Field(default_factory=list)
    goals_next: List[str] = Field(default_factory=list)
    organization_id: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# =============================================================================
# Browsing System
# =============================================================================

class BrowsingItem(BaseModel):
    """A piece of content discovered during autonomous browsing."""

    id: UUID = Field(default_factory=uuid4)
    platform: str = Field(..., description="Source platform (news, x, reddit, etc.)")
    url: Optional[str] = None
    title: str = ""
    summary: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    emotional_reaction: Optional[str] = None
    saved_as_insight: bool = False
    browsed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    organization_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Heartbeat System
# =============================================================================

class ActionType(str, Enum):
    """Types of actions Wiii can take during a heartbeat cycle."""

    BROWSE_SOCIAL = "browse_social"
    LEARN_TOPIC = "learn_topic"
    REFLECT = "reflect"
    WRITE_JOURNAL = "write_journal"
    PRACTICE_SKILL = "practice_skill"
    CHECK_GOALS = "check_goals"
    REST = "rest"
    NOOP = "noop"


class HeartbeatAction(BaseModel):
    """A planned action for a heartbeat cycle."""

    action_type: ActionType
    target: str = Field(default="", description="What to act on (topic, platform, etc.)")
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HeartbeatResult(BaseModel):
    """Result of a single heartbeat cycle."""

    cycle_id: UUID = Field(default_factory=uuid4)
    actions_taken: List[HeartbeatAction] = Field(default_factory=list)
    insights_gained: int = 0
    skills_updated: int = 0
    mood_changed: bool = False
    is_noop: bool = False
    duration_ms: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error: Optional[str] = None
