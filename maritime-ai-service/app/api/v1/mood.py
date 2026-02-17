"""
Mood / Emotional State API — Sprint 120
GET /api/v1/mood — returns current emotional state for the authenticated user.

Exposes the internal EmotionalStateManager to the desktop app.
Feature-gated: settings.enable_emotional_state (default: False)
"""
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mood", tags=["mood"])


class MoodResponse(BaseModel):
    """Current emotional state response."""
    positivity: float = Field(0.0, description="Positivity axis: -1 (sad) to +1 (happy)")
    energy: float = Field(0.5, description="Energy axis: 0 (calm) to 1 (active)")
    mood: str = Field("neutral", description="Derived mood: excited, warm, concerned, gentle, neutral")
    mood_hint: str = Field("", description="Vietnamese mood hint for context")
    enabled: bool = Field(False, description="Whether emotional state tracking is enabled")


@router.get("", response_model=MoodResponse)
@limiter.limit("60/minute")
async def get_mood(
    request: Request,
    auth: RequireAuth,
) -> MoodResponse:
    """
    Get current emotional state for the authenticated user.

    Returns the 2D mood vector (positivity, energy) and derived mood state.
    Feature-gated: returns neutral defaults when enable_emotional_state=False.
    """
    try:
        from app.core.config import settings
        if not settings.enable_emotional_state:
            return MoodResponse(enabled=False)

        from app.engine.emotional_state import get_emotional_state_manager
        manager = get_emotional_state_manager()
        state = manager.get_state(auth.user_id)

        return MoodResponse(
            positivity=round(state.positivity, 3),
            energy=round(state.energy, 3),
            mood=state.mood.value,
            mood_hint=state.mood_hint,
            enabled=True,
        )
    except Exception as e:
        logger.warning("[MOOD_API] Failed to get mood: %s", e)
        return MoodResponse(enabled=False)
