"""
Emotional State Machine — 2D Mood with Decay

Sprint 115: SOTA Personality System — Improvement #4

Research: Charisma.ai 2D mood (positivity + energy) with decay toward neutral.
No LLM calls — purely keyword matching, fast and deterministic.

Feature-gated: settings.enable_emotional_state (default: False)

Architecture:
- positivity: -1 (sad/frustrated) to +1 (happy/excited)
- energy: 0 (low/calm) to 1 (high/active)
- MoodState derived from quadrant of (positivity, energy)
- Decay toward neutral (0, 0.5) each turn
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# MOOD STATE — Derived from 2D quadrants
# =============================================================================

class MoodState(str, Enum):
    """Mood quadrant derived from (positivity, energy)."""
    EXCITED = "excited"      # positivity > 0, energy > 0.5
    WARM = "warm"            # positivity > 0, energy <= 0.5
    CONCERNED = "concerned"  # positivity < 0, energy > 0.5
    GENTLE = "gentle"        # positivity < 0, energy <= 0.5
    NEUTRAL = "neutral"      # near origin


# =============================================================================
# EMOTIONAL STATE — 2D mood vector
# =============================================================================

@dataclass
class EmotionalState:
    """2D emotional state with positivity and energy axes."""
    positivity: float = 0.0   # -1 to +1
    energy: float = 0.5       # 0 to 1

    def clamp(self) -> "EmotionalState":
        """Clamp values to valid ranges."""
        self.positivity = max(-1.0, min(1.0, self.positivity))
        self.energy = max(0.0, min(1.0, self.energy))
        return self

    def decay(self, rate: float = 0.15) -> "EmotionalState":
        """Decay toward neutral (0, 0.5)."""
        self.positivity *= (1.0 - rate)
        self.energy += (0.5 - self.energy) * rate
        return self.clamp()

    @property
    def mood(self) -> MoodState:
        """Derive mood from quadrant."""
        if abs(self.positivity) < 0.15 and abs(self.energy - 0.5) < 0.15:
            return MoodState.NEUTRAL
        if self.positivity > 0:
            return MoodState.EXCITED if self.energy > 0.5 else MoodState.WARM
        return MoodState.CONCERNED if self.energy > 0.5 else MoodState.GENTLE

    @property
    def mood_hint(self) -> str:
        """Generate mood hint for system prompt injection."""
        mood = self.mood
        hints = {
            MoodState.EXCITED: "User đang phấn khích/vui — hãy năng lượng, nhiệt tình cùng họ!",
            MoodState.WARM: "User đang thoải mái/dễ chịu — giữ giọng ấm áp, thân thiện.",
            MoodState.CONCERNED: "User có vẻ lo lắng/bực bội — hãy bình tĩnh, đồng cảm, giải quyết vấn đề.",
            MoodState.GENTLE: "User có vẻ buồn/mệt — hãy nhẹ nhàng, đồng cảm, không ép buộc.",
            MoodState.NEUTRAL: "",
        }
        return hints.get(mood, "")


# =============================================================================
# SENTIMENT KEYWORDS — Vietnamese keyword → (positivity_delta, energy_delta)
# =============================================================================

_SENTIMENT_KEYWORDS: Dict[str, Tuple[float, float]] = {
    # Positive + High energy
    "tuyet voi": (0.5, 0.3),
    "hay qua": (0.4, 0.2),
    "yay": (0.5, 0.4),
    "wow": (0.4, 0.3),
    "haha": (0.3, 0.2),
    "hehe": (0.3, 0.1),
    "thich qua": (0.4, 0.2),
    "vui qua": (0.5, 0.3),
    "dau roi": (0.4, 0.3),  # đậu rồi (passed exam)
    "thanh cong": (0.5, 0.3),
    # Positive + Low energy
    "cam on": (0.3, -0.1),
    "hieu roi": (0.3, 0.0),
    "ok": (0.1, 0.0),
    "duoc": (0.1, 0.0),
    # Negative + High energy
    "buc qua": (-0.4, 0.3),
    "chan qua": (-0.3, 0.1),
    "nan qua": (-0.4, 0.2),
    "kho qua": (-0.3, 0.2),
    "sai roi": (-0.3, 0.2),
    "khong hieu": (-0.3, 0.1),
    "met qua": (-0.2, -0.3),
    # Negative + Low energy
    "buon qua": (-0.5, -0.3),
    "that vong": (-0.4, -0.2),
    "buon ngu": (-0.2, -0.4),
    "so qua": (-0.3, 0.2),
}


def _strip_diacritics(text: str) -> str:
    """Strip Vietnamese diacritics for keyword matching."""
    try:
        from app.engine.content_filter import TextNormalizer
        return TextNormalizer.strip_diacritics(text.lower().strip())
    except Exception:
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.lower().strip())
        return "".join(
            c for c in nfkd if not unicodedata.combining(c)
        ).replace("đ", "d").replace("Đ", "D")


# =============================================================================
# EMOTIONAL STATE MANAGER — Per-user singleton
# =============================================================================

class EmotionalStateManager:
    """Manages per-user emotional state with keyword detection and decay.

    Sprint 125: Added TTL eviction to prevent unbounded growth with many users.

    Usage:
        manager = get_emotional_state_manager()
        mood_hint = manager.detect_and_update("user123", "Hay quá, cảm ơn!")
    """

    # Evict users who haven't interacted in 2 hours (emotional state is transient)
    STATE_TTL_SECONDS: float = 7200.0
    MAX_CACHED_USERS: int = 500

    def __init__(self):
        self._states: Dict[str, EmotionalState] = {}
        self._last_access: Dict[str, float] = {}  # user_id -> timestamp

    def _evict_stale(self) -> None:
        """Remove emotional states for users who haven't interacted recently."""
        if len(self._states) <= self.MAX_CACHED_USERS:
            return

        now = time.time()
        stale_users = [
            uid for uid, ts in self._last_access.items()
            if now - ts > self.STATE_TTL_SECONDS
        ]
        for uid in stale_users:
            self._states.pop(uid, None)
            self._last_access.pop(uid, None)

        if stale_users:
            logger.debug(
                "[EMOTIONAL] Evicted %d stale emotional states", len(stale_users),
            )

    def get_state(self, user_id: str) -> EmotionalState:
        """Get or create emotional state for user."""
        self._last_access[user_id] = time.time()
        if user_id not in self._states:
            self._states[user_id] = EmotionalState()
        return self._states[user_id]

    def detect_and_update(self, user_id: str, message: str, decay_rate: float = 0.15) -> str:
        """Detect sentiment from message, update state, return mood hint.

        Args:
            user_id: User identifier
            message: User's message text
            decay_rate: Rate of decay toward neutral

        Returns:
            Mood hint string for system prompt (empty if neutral)
        """
        # Periodic eviction when cache is large
        self._evict_stale()

        state = self.get_state(user_id)

        # Decay toward neutral first
        state.decay(decay_rate)

        # Detect keywords
        normalized = _strip_diacritics(message)
        for keyword, (pos_delta, eng_delta) in _SENTIMENT_KEYWORDS.items():
            if keyword in normalized:
                state.positivity += pos_delta
                state.energy += eng_delta

        state.clamp()

        hint = state.mood_hint
        if hint:
            logger.debug(
                "[EMOTIONAL] user=%s mood=%s pos=%.2f eng=%.2f",
                user_id, state.mood.value, state.positivity, state.energy,
            )
        return hint

    def reset(self, user_id: str) -> None:
        """Reset emotional state for user."""
        self._states.pop(user_id, None)
        self._last_access.pop(user_id, None)

    @property
    def active_users(self) -> int:
        """Number of active emotional states."""
        return len(self._states)


# =============================================================================
# SINGLETON
# =============================================================================

_manager: Optional[EmotionalStateManager] = None


def get_emotional_state_manager() -> EmotionalStateManager:
    """Get or create EmotionalStateManager singleton."""
    global _manager
    if _manager is None:
        _manager = EmotionalStateManager()
    return _manager
