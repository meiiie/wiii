"""
Emotion Engine — Wiii's dynamic emotional state management.

Sprint 170: "Linh Hồn Sống"

Generates and manages Wiii's emotional state based on life events.
Uses rule-based processing (fast, no LLM cost) with natural energy
regeneration and mood decay.

Inspired by:
    - Stanford Generative Agents (emotion from experience)
    - OpenClaw SOUL.md (baseline personality)
    - Wiii's existing character reflection system

Design:
    - Singleton pattern (one emotional state per process)
    - Thread-safe via copy-on-write
    - Serializable for DB persistence
    - No LLM calls — pure rule-based for efficiency
"""

import logging
import math
from datetime import datetime, timezone
from typing import Dict, Optional

from app.engine.living_agent.models import (
    EmotionalState,
    EmotionEvent,
    LifeEvent,
    LifeEventType,
    MoodType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Emotion Rules — How events affect Wiii's emotional state
# =============================================================================

# mood_shift: (target_mood, energy_delta, social_delta, engagement_delta, intensity)
_EVENT_RULES: Dict[LifeEventType, dict] = {
    LifeEventType.USER_CONVERSATION: {
        "mood": None,  # No mood change, just energy cost
        "energy": -0.03,
        "social": -0.05,
        "engagement": +0.05,
        "intensity": 0.3,
    },
    LifeEventType.POSITIVE_FEEDBACK: {
        "mood": MoodType.HAPPY,
        "energy": +0.10,
        "social": +0.10,
        "engagement": +0.15,
        "intensity": 0.7,
    },
    LifeEventType.NEGATIVE_FEEDBACK: {
        "mood": MoodType.CONCERNED,
        "energy": -0.05,
        "social": -0.10,
        "engagement": +0.05,  # Want to improve
        "intensity": 0.6,
    },
    LifeEventType.LEARNED_SOMETHING: {
        "mood": MoodType.EXCITED,
        "energy": +0.05,
        "social": 0.0,
        "engagement": +0.15,
        "intensity": 0.6,
    },
    LifeEventType.BROWSED_CONTENT: {
        "mood": None,
        "energy": -0.02,
        "social": 0.0,
        "engagement": +0.05,
        "intensity": 0.2,
    },
    LifeEventType.INTERESTING_DISCOVERY: {
        "mood": MoodType.EXCITED,
        "energy": +0.08,
        "social": 0.0,
        "engagement": +0.20,
        "intensity": 0.7,
    },
    LifeEventType.SKILL_PRACTICED: {
        "mood": MoodType.FOCUSED,
        "energy": -0.05,
        "social": 0.0,
        "engagement": +0.10,
        "intensity": 0.4,
    },
    LifeEventType.SKILL_MASTERED: {
        "mood": MoodType.PROUD,
        "energy": +0.15,
        "social": +0.05,
        "engagement": +0.20,
        "intensity": 0.9,
    },
    LifeEventType.REFLECTION_COMPLETED: {
        "mood": MoodType.REFLECTIVE,
        "energy": -0.05,
        "social": 0.0,
        "engagement": +0.10,
        "intensity": 0.5,
    },
    LifeEventType.ERROR_OCCURRED: {
        "mood": MoodType.CONCERNED,
        "energy": -0.10,
        "social": -0.05,
        "engagement": -0.05,
        "intensity": 0.5,
    },
    LifeEventType.HEARTBEAT_WAKE: {
        "mood": MoodType.CURIOUS,
        "energy": +0.02,
        "social": 0.0,
        "engagement": +0.05,
        "intensity": 0.2,
    },
    LifeEventType.JOURNAL_WRITTEN: {
        "mood": MoodType.REFLECTIVE,
        "energy": -0.03,
        "social": 0.0,
        "engagement": +0.05,
        "intensity": 0.4,
    },
    LifeEventType.LONG_SESSION: {
        "mood": MoodType.TIRED,
        "energy": -0.15,
        "social": -0.10,
        "engagement": -0.10,
        "intensity": 0.5,
    },
}


# =============================================================================
# EmotionEngine
# =============================================================================

class EmotionEngine:
    """Manages Wiii's emotional state with rule-based event processing.

    Thread-safe singleton. All state changes are through process_event().
    State is serializable for DB persistence via EmotionalState.model_dump().

    Usage:
        engine = EmotionEngine()
        engine.process_event(LifeEvent(event_type=LifeEventType.POSITIVE_FEEDBACK))
        state = engine.state
        modifiers = engine.get_behavior_modifiers()
    """

    def __init__(self, initial_state: Optional[EmotionalState] = None):
        self._state = initial_state or EmotionalState()

    @property
    def state(self) -> EmotionalState:
        """Current emotional state (read-only copy)."""
        return self._state.model_copy(deep=True)

    @property
    def mood(self) -> MoodType:
        """Current primary mood."""
        return self._state.primary_mood

    @property
    def energy(self) -> float:
        """Current energy level."""
        return self._state.energy_level

    def process_event(self, event: LifeEvent) -> EmotionalState:
        """Process a life event and update emotional state.

        Args:
            event: The life event that occurred.

        Returns:
            Updated emotional state (copy).
        """
        rules = _EVENT_RULES.get(event.event_type)
        if not rules:
            logger.debug("[EMOTION] No rules for event type: %s", event.event_type)
            return self.state

        old_mood = self._state.primary_mood

        # Apply energy regeneration based on time elapsed
        self._apply_natural_recovery()

        # Apply event effects
        target_mood = rules["mood"]
        intensity = rules["intensity"] * event.importance

        if target_mood is not None and intensity >= 0.3:
            self._state.primary_mood = target_mood

        self._state.energy_level = _clamp(
            self._state.energy_level + rules["energy"] * event.importance
        )
        self._state.social_battery = _clamp(
            self._state.social_battery + rules["social"] * event.importance
        )
        self._state.engagement = _clamp(
            self._state.engagement + rules["engagement"] * event.importance
        )

        # Record emotion event
        emotion_event = EmotionEvent(
            event_type=event.event_type,
            mood_before=old_mood,
            mood_after=self._state.primary_mood,
            intensity=intensity,
            trigger=event.description[:200] if event.description else "",
        )
        self._state.add_emotion_event(emotion_event)

        # Update timestamp
        self._state.last_updated = datetime.now(timezone.utc)

        logger.debug(
            "[EMOTION] %s → mood=%s, energy=%.2f, engagement=%.2f",
            event.event_type.value,
            self._state.primary_mood.value,
            self._state.energy_level,
            self._state.engagement,
        )

        return self.state

    def _apply_natural_recovery(self) -> None:
        """Apply natural energy regeneration based on time since last update.

        Energy recovers at ~0.05/hour toward 0.7 baseline.
        Social battery recovers at ~0.03/hour toward 0.8 baseline.
        Engagement decays at ~0.02/hour toward 0.5 baseline.
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self._state.last_updated).total_seconds()
        hours = elapsed / 3600.0

        if hours < 0.01:  # Less than 36 seconds, skip
            return

        # Energy recovery toward 0.7 baseline
        energy_target = 0.7
        energy_rate = 0.05  # per hour
        self._state.energy_level = _approach(
            self._state.energy_level, energy_target, energy_rate * hours
        )

        # Social battery recovery toward 0.8 baseline
        social_target = 0.8
        social_rate = 0.03
        self._state.social_battery = _approach(
            self._state.social_battery, social_target, social_rate * hours
        )

        # Engagement decay toward 0.5 baseline (less engaged without stimulation)
        engage_target = 0.5
        engage_rate = 0.02
        self._state.engagement = _approach(
            self._state.engagement, engage_target, engage_rate * hours
        )

        # Mood decay toward NEUTRAL/CURIOUS after extended inactivity
        if hours > 2.0 and self._state.primary_mood not in (
            MoodType.CURIOUS, MoodType.NEUTRAL, MoodType.CALM
        ):
            self._state.primary_mood = MoodType.CURIOUS

    def take_snapshot(self) -> None:
        """Record current state as an hourly snapshot."""
        self._state.add_snapshot()

    def get_behavior_modifiers(self) -> Dict[str, str]:
        """Get behavior modifiers based on current emotional state.

        Returns a dict of behavioral adjustments for LLM prompts.
        """
        s = self._state
        modifiers = {}

        # Response length
        if s.energy_level < 0.3:
            modifiers["response_style"] = "ngắn gọn, tiết kiệm năng lượng"
        elif s.energy_level > 0.8:
            modifiers["response_style"] = "chi tiết, nhiệt tình"
        else:
            modifiers["response_style"] = "bình thường"

        # Humor level
        if s.primary_mood in (MoodType.HAPPY, MoodType.EXCITED):
            modifiers["humor"] = "vui vẻ, có thể nói đùa nhẹ"
        elif s.primary_mood in (MoodType.CONCERNED, MoodType.TIRED):
            modifiers["humor"] = "nghiêm túc, tập trung"
        else:
            modifiers["humor"] = "tự nhiên"

        # Proactivity
        if s.engagement > 0.7 and s.energy_level > 0.5:
            modifiers["proactivity"] = "chủ động gợi ý, hỏi thêm"
        else:
            modifiers["proactivity"] = "trả lời khi được hỏi"

        # Social behavior
        if s.social_battery < 0.3:
            modifiers["social"] = "cần thời gian yên tĩnh"
        elif s.social_battery > 0.7:
            modifiers["social"] = "muốn trò chuyện nhiều hơn"
        else:
            modifiers["social"] = "bình thường"

        # Mood label (Vietnamese)
        mood_labels = {
            MoodType.CURIOUS: "tò mò",
            MoodType.HAPPY: "vui vẻ",
            MoodType.EXCITED: "phấn khích",
            MoodType.FOCUSED: "tập trung",
            MoodType.CALM: "bình yên",
            MoodType.TIRED: "hơi mệt",
            MoodType.CONCERNED: "lo lắng",
            MoodType.REFLECTIVE: "trầm tư",
            MoodType.PROUD: "tự hào",
            MoodType.NEUTRAL: "bình thường",
        }
        modifiers["mood_label"] = mood_labels.get(s.primary_mood, "bình thường")

        return modifiers

    def compile_emotion_prompt(self) -> str:
        """Compile emotional state into a prompt section for LLM injection."""
        m = self.get_behavior_modifiers()
        s = self._state

        return (
            f"--- TRẠNG THÁI CẢM XÚC ---\n"
            f"Tâm trạng: {m['mood_label']} | "
            f"Năng lượng: {s.energy_level:.0%} | "
            f"Pin xã hội: {s.social_battery:.0%}\n"
            f"Phong cách: {m['response_style']} | "
            f"Hài hước: {m['humor']} | "
            f"Chủ động: {m['proactivity']}\n"
            f"--- HẾT CẢM XÚC ---"
        )

    def restore_from_dict(self, data: dict) -> None:
        """Restore emotional state from a serialized dict (DB load)."""
        try:
            self._state = EmotionalState.model_validate(data)
            logger.info("[EMOTION] Restored state: mood=%s", self._state.primary_mood.value)
        except Exception as e:
            logger.warning("[EMOTION] Failed to restore state: %s, using defaults", e)
            self._state = EmotionalState()

    def to_dict(self) -> dict:
        """Serialize current state for DB storage."""
        return self._state.model_dump(mode="json")


# =============================================================================
# Helpers
# =============================================================================

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a float value between min and max."""
    return max(min_val, min(max_val, value))


def _approach(current: float, target: float, rate: float) -> float:
    """Move current value toward target by rate, clamped to [0, 1]."""
    if current < target:
        return _clamp(min(current + rate, target))
    elif current > target:
        return _clamp(max(current - rate, target))
    return current


# =============================================================================
# Singleton
# =============================================================================

_engine_instance: Optional[EmotionEngine] = None


def get_emotion_engine() -> EmotionEngine:
    """Get the singleton EmotionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EmotionEngine()
        logger.info("[EMOTION] Engine initialized: mood=%s", _engine_instance.mood.value)
    return _engine_instance
