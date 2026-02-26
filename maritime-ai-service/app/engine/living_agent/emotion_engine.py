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

        # Sprint 188: Persist emotion state after every event
        # Fire-and-forget — failure must not block event processing
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(self.save_state_to_db())
        except RuntimeError:
            # No running event loop (sync context) — skip persistence
            pass

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

        # Sprint 188: Time-of-day tone variation
        from datetime import timedelta
        now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
        hour = now_vn.hour
        if hour < 7:
            modifiers["tone"] = "nhẹ nhàng, ấm áp (sáng sớm)"
        elif hour < 12:
            modifiers["tone"] = "năng động, tích cực (buổi sáng)"
        elif hour < 14:
            modifiers["tone"] = "thư giãn, nhẹ nhàng (trưa)"
        elif hour < 18:
            modifiers["tone"] = "tập trung, hỗ trợ (chiều)"
        elif hour < 21:
            modifiers["tone"] = "thân thiện, thoải mái (tối)"
        else:
            modifiers["tone"] = "dịu dàng, yên bình (khuya)"

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

    # =========================================================================
    # Persistent Emotion — Phase 1A: DB save/load (wired Sprint 188)
    # =========================================================================

    _db_loaded: bool = False

    async def load_from_db_if_needed(self) -> bool:
        """One-time emotion state restore from DB. Idempotent guard.

        Returns True if state was loaded from DB, False otherwise.
        """
        if self._db_loaded:
            return False
        self._db_loaded = True
        return await self.load_state_from_db()

    async def save_state_to_db(self) -> None:
        """Persist current emotional state to database.

        Saves as the latest snapshot in wiii_emotional_snapshots with
        a special trigger_event='persistent_state' for later retrieval.
        """
        try:
            import json
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory
            from uuid import uuid4

            state_json = json.dumps(self.to_dict(), ensure_ascii=False)
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                # Upsert: delete old persistent_state, insert new one
                session.execute(
                    text("DELETE FROM wiii_emotional_snapshots WHERE trigger_event = 'persistent_state'"),
                )
                session.execute(
                    text("""
                        INSERT INTO wiii_emotional_snapshots
                        (id, primary_mood, energy_level, social_battery, engagement,
                         trigger_event, state_json, snapshot_at)
                        VALUES (:id, :mood, :energy, :social, :engagement,
                                'persistent_state', :state_json, NOW())
                    """),
                    {
                        "id": str(uuid4()),
                        "mood": self._state.primary_mood.value,
                        "energy": self._state.energy_level,
                        "social": self._state.social_battery,
                        "engagement": self._state.engagement,
                        "state_json": state_json,
                    },
                )
                session.commit()
            logger.info("[EMOTION] State persisted to DB: mood=%s", self._state.primary_mood.value)
        except Exception as e:
            logger.warning("[EMOTION] Failed to persist state: %s", e)

    async def load_state_from_db(self) -> bool:
        """Load emotional state from database on startup.

        Returns:
            True if state was loaded, False if no saved state found.
        """
        try:
            import json
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                row = session.execute(
                    text("""
                        SELECT state_json FROM wiii_emotional_snapshots
                        WHERE trigger_event = 'persistent_state'
                        ORDER BY snapshot_at DESC
                        LIMIT 1
                    """),
                ).fetchone()

                if row and row[0]:
                    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    self.restore_from_dict(data)
                    logger.info("[EMOTION] State loaded from DB: mood=%s", self._state.primary_mood.value)
                    return True

            logger.debug("[EMOTION] No saved state in DB, using defaults")
            return False
        except Exception as e:
            logger.warning("[EMOTION] Failed to load state from DB: %s", e)
            return False

    # =========================================================================
    # Circadian Rhythm — Phase 2B
    # =========================================================================

    def apply_circadian_modifier(self) -> None:
        """Adjust energy baseline based on time of day (UTC+7).

        Sprint 188: Increased blend from 10% to 40% so Wiii's energy
        noticeably tracks natural rhythms (morning peak, post-lunch dip,
        evening wind-down). Also sets mood hints per time-of-day.
        """
        from datetime import timedelta

        now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
        hour = now_vn.hour

        circadian_energy = {
            5: 0.40, 6: 0.60, 7: 0.80, 8: 0.90, 9: 0.95,
            10: 0.90, 11: 0.85, 12: 0.70, 13: 0.65, 14: 0.75,
            15: 0.85, 16: 0.80, 17: 0.75, 18: 0.70, 19: 0.65,
            20: 0.60, 21: 0.50, 22: 0.40, 23: 0.20,
        }

        target = circadian_energy.get(hour)
        if target is not None:
            # Sprint 188: 40% blend (was 10%) — energy follows circadian curve
            self._state.energy_level = _clamp(
                self._state.energy_level * 0.6 + target * 0.4
            )

        # Sprint 188: Time-of-day mood hints (gentle, not overriding events)
        circadian_mood = {
            (5, 7): MoodType.CALM,        # Early morning — peaceful
            (7, 10): MoodType.CURIOUS,     # Morning — alert and curious
            (10, 12): MoodType.FOCUSED,    # Late morning — productive
            (12, 14): MoodType.CALM,       # Post-lunch — relaxed
            (14, 17): MoodType.FOCUSED,    # Afternoon — productive
            (17, 20): MoodType.CURIOUS,    # Evening — exploratory
            (20, 23): MoodType.REFLECTIVE, # Night — winding down
        }
        for (start, end), mood in circadian_mood.items():
            if start <= hour < end:
                # Only nudge if current mood is NEUTRAL (low-priority override)
                if self._state.primary_mood == MoodType.NEUTRAL:
                    self._state.primary_mood = mood
                break


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
