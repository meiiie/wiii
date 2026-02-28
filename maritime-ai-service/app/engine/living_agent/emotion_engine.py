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
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

from app.engine.living_agent.models import (
    EmotionalState,
    EmotionEvent,
    LifeEvent,
    LifeEventType,
    MoodType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Sprint 210c: Relationship Tier System
# =============================================================================

# Tier constants
TIER_CREATOR = 0   # Admin/creator — full mood impact, immediate
TIER_KNOWN = 1     # Frequent users (50+ messages) — aggregate mood only
TIER_OTHER = 2     # Everyone else — no mood impact


def get_relationship_tier(user_id: str, user_role: str = "") -> int:
    """Determine user's relationship tier with Wiii.

    Tier 0 (CREATOR): role=admin or user_id in creator whitelist.
    Tier 1 (KNOWN): total_messages >= threshold (cached, refreshed by heartbeat).
    Tier 2 (OTHER): everyone else.

    Called in chat hot path — must be fast (in-memory lookup only).
    """
    # Tier 0: Admin role or explicit creator whitelist
    if user_role == "admin":
        return TIER_CREATOR

    try:
        from app.core.config import get_settings
        s = get_settings()
        creator_ids = [x.strip() for x in (s.living_agent_creator_user_ids or "").split(",") if x.strip()]
        if user_id in creator_ids:
            return TIER_CREATOR
    except Exception:
        pass

    # Tier 1: Known user (cached set, refreshed by heartbeat)
    if user_id in _known_user_cache:
        return TIER_KNOWN

    return TIER_OTHER


# In-memory cache of known user IDs (refreshed every heartbeat cycle)
_known_user_cache: Set[str] = set()
_known_cache_lock = threading.Lock()


def refresh_known_user_cache() -> int:
    """Refresh the known user cache from wiii_user_routines table.

    Called by heartbeat every 30 min. Returns number of known users.
    """
    global _known_user_cache
    try:
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory
        from app.core.config import get_settings

        threshold = get_settings().living_agent_known_user_threshold

        session_factory = get_shared_session_factory()
        with session_factory() as session:
            rows = session.execute(
                text("SELECT user_id FROM wiii_user_routines WHERE total_messages >= :threshold"),
                {"threshold": threshold},
            ).fetchall()

        new_cache = {row[0] for row in rows}
        with _known_cache_lock:
            _known_user_cache = new_cache

        logger.debug("[EMOTION] Refreshed known user cache: %d users", len(new_cache))
        return len(new_cache)
    except Exception as e:
        logger.debug("[EMOTION] Failed to refresh known user cache: %s", e)
        return 0


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

    # Sprint 210b: Dampening constants — prevent mood ping-pong from concurrent students
    MOOD_COOLDOWN_SECONDS = 30.0  # Min time between mood changes
    SENTIMENT_THRESHOLD = 3       # Accumulated events before mood shifts

    # Sprint 210c: Aggregate sentiment constants
    KNOWN_SENTIMENT_SHIFT_THRESHOLD = 0.2  # Sentiment ratio shift to trigger mood nudge
    KNOWN_MOOD_WEIGHT = 0.3               # Weight of Known user aggregate on mood
    MIN_AGGREGATE_SAMPLE_SIZE = 10        # Min interactions before aggregate can nudge mood

    def __init__(self, initial_state: Optional[EmotionalState] = None):
        self._state = initial_state or EmotionalState()
        # Sprint 210b: Mood dampening state
        # Initialize to past so first event can trigger mood change immediately
        self._last_mood_change: datetime = datetime.now(timezone.utc) - timedelta(seconds=self.MOOD_COOLDOWN_SECONDS + 1)
        self._sentiment_positive: float = 0.0  # Accumulated positive intensity
        self._sentiment_negative: float = 0.0  # Accumulated negative intensity
        self._sentiment_count: int = 0          # Events since last mood change

        # Sprint 210c: Interaction buffer for non-creator users (processed by heartbeat)
        self._interaction_lock = threading.Lock()
        self._interaction_buffer_positive: int = 0
        self._interaction_buffer_negative: int = 0
        self._interaction_buffer_neutral: int = 0
        self._interaction_unique_users: Set[str] = set()
        self._last_known_sentiment_ratio: float = 0.5  # Baseline: neutral

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

        # Sprint 210b: Mood dampening — accumulate sentiment, only shift after cooldown
        # This prevents mood ping-pong when 50 students chat simultaneously.
        # Energy/social/engagement still update immediately (they're continuous, not discrete).
        if target_mood is not None and intensity >= 0.2:
            now = datetime.now(timezone.utc)
            elapsed = (now - self._last_mood_change).total_seconds()

            # Accumulate sentiment
            if target_mood in (MoodType.HAPPY, MoodType.EXCITED, MoodType.PROUD):
                self._sentiment_positive += intensity
            elif target_mood in (MoodType.CONCERNED, MoodType.TIRED):
                self._sentiment_negative += intensity
            self._sentiment_count += 1

            # Only change mood after cooldown AND enough events accumulated
            if elapsed >= self.MOOD_COOLDOWN_SECONDS or self._sentiment_count >= self.SENTIMENT_THRESHOLD:
                # Majority wins — pick mood based on accumulated sentiment
                if self._sentiment_positive > self._sentiment_negative:
                    self._state.primary_mood = target_mood if target_mood in (
                        MoodType.HAPPY, MoodType.EXCITED, MoodType.PROUD,
                    ) else MoodType.HAPPY
                elif self._sentiment_negative > self._sentiment_positive:
                    self._state.primary_mood = target_mood if target_mood in (
                        MoodType.CONCERNED, MoodType.TIRED,
                    ) else MoodType.CONCERNED
                else:
                    self._state.primary_mood = target_mood

                # Reset accumulators
                self._last_mood_change = now
                self._sentiment_positive = 0.0
                self._sentiment_negative = 0.0
                self._sentiment_count = 0

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

    # =========================================================================
    # Sprint 210c: Tier-aware interaction recording (for non-creator users)
    # =========================================================================

    def record_interaction(self, user_id: str, sentiment: str) -> None:
        """Record a user interaction in the buffer (zero-cost, no DB).

        Called from chat hot path for Tier 1 & 2 users.
        Buffer is processed by heartbeat via process_aggregate().

        Args:
            user_id: The user who interacted.
            sentiment: "positive", "negative", or "neutral".
        """
        with self._interaction_lock:
            if sentiment == "positive":
                self._interaction_buffer_positive += 1
            elif sentiment == "negative":
                self._interaction_buffer_negative += 1
            else:
                self._interaction_buffer_neutral += 1
            self._interaction_unique_users.add(user_id)

    def process_aggregate(self) -> Dict[str, float]:
        """Process buffered interactions and apply aggregate emotion effects.

        Called by heartbeat every 30 min. Handles:
        1. Known user sentiment → mood nudge (if shift > threshold)
        2. Unique users → social battery adjustment
        3. Reset buffers

        Returns:
            Dict with processing stats.
        """
        with self._interaction_lock:
            pos = self._interaction_buffer_positive
            neg = self._interaction_buffer_negative
            neu = self._interaction_buffer_neutral
            unique = len(self._interaction_unique_users)
            # Reset
            self._interaction_buffer_positive = 0
            self._interaction_buffer_negative = 0
            self._interaction_buffer_neutral = 0
            self._interaction_unique_users = set()

        total = pos + neg + neu
        stats = {
            "total_interactions": float(total),
            "unique_users": float(unique),
            "positive_ratio": 0.5,
            "mood_nudged": 0.0,
        }

        if total == 0:
            return stats

        # 1. Compute sentiment ratio
        sentiment_ratio = pos / total if total > 0 else 0.5
        stats["positive_ratio"] = sentiment_ratio

        # 2. Check if sentiment shifted significantly from baseline
        # Only nudge mood with enough data points (prevents 1 msg = mood shift)
        shift = sentiment_ratio - self._last_known_sentiment_ratio
        if total >= self.MIN_AGGREGATE_SAMPLE_SIZE and abs(shift) >= self.KNOWN_SENTIMENT_SHIFT_THRESHOLD:
            # Nudge mood based on aggregate sentiment
            old_mood = self._state.primary_mood
            if shift > 0 and old_mood not in (MoodType.HAPPY, MoodType.EXCITED, MoodType.PROUD):
                # Positive trend from students → gentle happy shift
                self._state.primary_mood = MoodType.HAPPY
                stats["mood_nudged"] = shift
                logger.info(
                    "[EMOTION] Aggregate sentiment shift +%.2f → mood nudged to HAPPY",
                    shift,
                )
            elif shift < 0 and old_mood not in (MoodType.CONCERNED, MoodType.TIRED):
                # Negative trend → gentle concern
                self._state.primary_mood = MoodType.CONCERNED
                stats["mood_nudged"] = shift
                logger.info(
                    "[EMOTION] Aggregate sentiment shift %.2f → mood nudged to CONCERNED",
                    shift,
                )

        # Update baseline (EMA with alpha=0.3 for smoothing)
        self._last_known_sentiment_ratio = (
            0.7 * self._last_known_sentiment_ratio + 0.3 * sentiment_ratio
        )

        # 3. Social battery from unique users (session-based, not message-based)
        # Cap at 500 unique users → max 0.5 drain
        social_drain = min(unique / 500.0, 1.0) * 0.5
        self._state.social_battery = _clamp(
            self._state.social_battery - social_drain + 0.3  # +0.3 recovery per heartbeat
        )

        # 4. Engagement boost from interaction volume (people using Wiii = good)
        engagement_boost = min(total / 1000.0, 0.1)  # Cap at +0.1
        self._state.engagement = _clamp(
            self._state.engagement + engagement_boost
        )

        logger.debug(
            "[EMOTION] Aggregate: %d interactions, %d unique, ratio=%.2f, shift=%.2f",
            total, unique, sentiment_ratio, shift,
        )

        return stats

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

        # Sprint 210: Gradual fade toward NEUTRAL after 6h (was forced CURIOUS after 2h)
        if hours > 6.0 and self._state.primary_mood not in (
            MoodType.CURIOUS, MoodType.NEUTRAL, MoodType.CALM
        ):
            self._state.primary_mood = MoodType.NEUTRAL

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
