"""
Living Agent System — Wiii's Autonomous Life Engine.

Sprint 170: "Linh Hồn Sống" — Autonomous Living Agent Architecture.
Sprint 176: "Wiii Soul AGI" — Weather, Briefing, Reflection, Goals, Autonomy.

Architecture:
    Layer 1 (Soul):       Immutable identity — core truths, boundaries, interests
    Layer 2 (Emotion):    Dynamic emotional state + circadian rhythm + DB persistence
    Layer 3 (Heartbeat):  Periodic autonomy — wake up, decide, act, sleep
    Layer 4 (Browser):    Content discovery — smart topic selection
    Layer 5 (Skills):     Self-improvement — discover, learn, practice, master
    Layer 6 (Journal):    Life narrative — daily entries, story, growth
    Layer 7 (Weather):    Environmental awareness — OpenWeatherMap integration
    Layer 8 (Briefing):   Scheduled briefings — morning/midday/evening via Messenger/Zalo
    Layer 9 (Routine):    User pattern learning — activity tracking
    Layer 10 (Reflection): Deep self-reflection — weekly insights
    Layer 11 (Goals):     Dynamic goal lifecycle — propose, track, complete
    Layer 12 (Proactive): Initiative communication — anti-spam guards
    Layer 13 (Autonomy):  Trust-level governance — graduated permissions

All autonomous features gated behind `enable_living_agent=False`.
Uses LOCAL MODEL (Ollama) for zero-cost 24/7 operation.
"""

from app.engine.living_agent.models import (
    # Core
    EmotionalState,
    EmotionEvent,
    MoodSnapshot,
    MoodType,
    LifeEvent,
    LifeEventType,
    WiiiSkill,
    SkillStatus,
    JournalEntry,
    BrowsingItem,
    HeartbeatResult,
    ActionType,
    SoulConfig,
    # Soul AGI additions
    WeatherInfo,
    WeatherForecast,
    BriefingType,
    Briefing,
    UserRoutine,
    ReflectionEntry,
    GoalStatus,
    GoalPriority,
    WiiiGoal,
    AutonomyLevel,
    ProactiveMessage,
    # Sprint 177: Skill Learning
    LearningMaterial,
    ReviewSchedule,
    QuizQuestion,
    QuizResult,
    # Sprint 207: Identity Core
    InsightCategory,
    IdentityInsight,
)

__all__ = [
    # Core
    "EmotionalState",
    "EmotionEvent",
    "MoodSnapshot",
    "MoodType",
    "LifeEvent",
    "LifeEventType",
    "WiiiSkill",
    "SkillStatus",
    "JournalEntry",
    "BrowsingItem",
    "HeartbeatResult",
    "ActionType",
    "SoulConfig",
    # Soul AGI
    "WeatherInfo",
    "WeatherForecast",
    "BriefingType",
    "Briefing",
    "UserRoutine",
    "ReflectionEntry",
    "GoalStatus",
    "GoalPriority",
    "WiiiGoal",
    "AutonomyLevel",
    "ProactiveMessage",
    # Sprint 177: Skill Learning
    "LearningMaterial",
    "ReviewSchedule",
    "QuizQuestion",
    "QuizResult",
    # Sprint 207: Identity Core
    "InsightCategory",
    "IdentityInsight",
]
