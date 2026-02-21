"""
Living Agent System — Wiii's Autonomous Life Engine.

Sprint 170: "Linh Hồn Sống" — Autonomous Living Agent Architecture.

Inspired by:
    - OpenClaw (heartbeat, SOUL.md, skills, memory)
    - Stanford Generative Agents (reflection, experience streams)
    - Mem0 (production memory for AI agents)

Architecture:
    Layer 1 (Soul):     Immutable identity — core truths, boundaries, interests
    Layer 2 (Emotion):  Dynamic emotional state — mood, energy, engagement
    Layer 3 (Heartbeat): Periodic autonomy — wake up, decide, act, sleep
    Layer 4 (Browser):  Content discovery — news, social media, research
    Layer 5 (Skills):   Self-improvement — discover, learn, practice, master
    Layer 6 (Journal):  Life narrative — daily entries, story, growth

All autonomous features gated behind `enable_living_agent=False`.
Uses LOCAL MODEL (Ollama) for zero-cost 24/7 operation.
"""

from app.engine.living_agent.models import (
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
)

__all__ = [
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
]
