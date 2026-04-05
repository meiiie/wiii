"""Response/request models for living-agent API routes."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class EmotionalStateResponse(BaseModel):
    """Current emotional state of Wiii."""

    primary_mood: str = Field("neutral", description="Current mood")
    energy_level: float = Field(0.7, description="Energy 0-1")
    social_battery: float = Field(0.8, description="Social battery 0-1")
    engagement: float = Field(0.5, description="Engagement 0-1")
    mood_label: str = Field("bình thường", description="Vietnamese mood label")
    behavior_modifiers: dict = Field(default_factory=dict)
    last_updated: Optional[str] = None


class JournalEntryResponse(BaseModel):
    """A single journal entry."""

    id: str
    entry_date: str
    content: str
    mood_summary: str = ""
    energy_avg: float = 0.5
    notable_events: List[str] = Field(default_factory=list)
    learnings: List[str] = Field(default_factory=list)
    goals_next: List[str] = Field(default_factory=list)


class SkillResponse(BaseModel):
    """A tracked skill."""

    id: str
    skill_name: str
    domain: str = "general"
    status: str = "discovered"
    confidence: float = 0.0
    usage_count: int = 0
    success_rate: float = 0.0
    discovered_at: Optional[str] = None
    last_practiced: Optional[str] = None
    mastered_at: Optional[str] = None


class HeartbeatInfoResponse(BaseModel):
    """Heartbeat scheduler information."""

    is_running: bool = False
    heartbeat_count: int = 0
    interval_seconds: int = 1800
    active_hours: str = "08:00-23:00 UTC+7"


class LivingAgentStatusResponse(BaseModel):
    """Overall living agent status."""

    enabled: bool = False
    emotional_state: Optional[EmotionalStateResponse] = None
    heartbeat: Optional[HeartbeatInfoResponse] = None
    skills_count: int = 0
    journal_entries_count: int = 0
    soul_loaded: bool = False
    soul_name: str = ""


class HeartbeatTriggerResponse(BaseModel):
    """Result of manually triggering a heartbeat."""

    success: bool
    actions_taken: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


class BrowsingLogResponse(BaseModel):
    """A browsing log entry."""

    id: str
    platform: str
    url: str = ""
    title: str
    summary: str = ""
    relevance_score: float = 0.0
    browsed_at: str


class PendingActionResponse(BaseModel):
    """A pending action awaiting human approval."""

    id: str
    action_type: str
    target: str = ""
    priority: float = 0.5
    status: str = "pending"
    created_at: str
    resolved_at: Optional[str] = None
    approved_by: Optional[str] = None


class ResolveActionRequest(BaseModel):
    """Request body for resolving a pending action."""

    decision: str = Field(..., description="'approve' or 'reject'")


class HeartbeatAuditResponse(BaseModel):
    """A heartbeat audit log entry."""

    id: str
    cycle_number: int
    actions_taken: List[dict] = Field(default_factory=list)
    insights_gained: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    created_at: str


class GoalResponse(BaseModel):
    """A dynamic goal."""

    id: str
    title: str
    description: str = ""
    status: str = "proposed"
    priority: str = "medium"
    progress: float = 0.0
    source: str = "reflection"
    milestones: List[str] = Field(default_factory=list)
    completed_milestones: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    target_date: Optional[str] = None
    completed_at: Optional[str] = None


class CreateGoalRequest(BaseModel):
    """Request to create a new goal."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
    priority: str = Field(default="medium")
    milestones: List[str] = Field(default_factory=list)


class UpdateGoalProgressRequest(BaseModel):
    """Request to update goal progress."""

    progress: float = Field(..., ge=0.0, le=1.0)
    milestone: Optional[str] = None


class ReflectionResponse(BaseModel):
    """A reflection entry."""

    id: str
    content: str
    insights: List[str] = Field(default_factory=list)
    goals_next_week: List[str] = Field(default_factory=list)
    patterns_noticed: List[str] = Field(default_factory=list)
    emotion_trend: str = ""
    reflection_date: Optional[str] = None


class RoutineResponse(BaseModel):
    """User routine data."""

    user_id: str
    typical_active_hours: List[int] = Field(default_factory=list)
    preferred_briefing_time: int = 7
    conversation_frequency: float = 0.0
    common_topics: List[str] = Field(default_factory=list)
    total_messages: int = 0
    last_seen: Optional[str] = None


class AutonomyStatusResponse(BaseModel):
    """Autonomy level status."""

    level: int = 0
    level_name: str = "Giam sat hoan toan"
    allowed_actions: List[str] = Field(default_factory=list)
    needs_approval: List[str] = Field(default_factory=list)
    graduation_criteria: dict = Field(default_factory=dict)
