"""
User Preferences API — Sprint 120
GET  /api/v1/preferences — get user preferences
PUT  /api/v1/preferences — update user preferences

Exposes the internal UserPreferencesRepository to the desktop app.
Users can only access their own preferences.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])

VALID_LEARNING_STYLES = {"quiz", "visual", "reading", "mixed", "interactive"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced", "expert"}
VALID_PRONOUN_STYLES = {"auto", "formal", "casual"}


class PreferencesResponse(BaseModel):
    """User preferences response."""
    preferred_domain: str = "maritime"
    language: str = "vi"
    pronoun_style: str = "auto"
    learning_style: str = "mixed"
    difficulty: str = "intermediate"
    timezone: str = "Asia/Ho_Chi_Minh"


class PreferencesUpdateRequest(BaseModel):
    """Update specific preference fields (partial update)."""
    preferred_domain: Optional[str] = None
    language: Optional[str] = None
    pronoun_style: Optional[str] = None
    learning_style: Optional[str] = None
    difficulty: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("learning_style")
    @classmethod
    def validate_learning_style(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_LEARNING_STYLES:
            raise ValueError(f"learning_style must be one of: {VALID_LEARNING_STYLES}")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {VALID_DIFFICULTIES}")
        return v

    @field_validator("pronoun_style")
    @classmethod
    def validate_pronoun_style(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PRONOUN_STYLES:
            raise ValueError(f"pronoun_style must be one of: {VALID_PRONOUN_STYLES}")
        return v


@router.get("", response_model=PreferencesResponse)
@limiter.limit("60/minute")
async def get_preferences(
    request: Request,
    auth: RequireAuth,
) -> PreferencesResponse:
    """
    Get preferences for the authenticated user.

    Returns defaults for fields not yet set.
    """
    try:
        from app.repositories.user_preferences_repository import get_user_preferences_repository
        repo = get_user_preferences_repository()
        prefs = repo.get_preferences(auth.user_id)
        return PreferencesResponse(**prefs)
    except Exception as e:
        logger.warning("[PREFERENCES_API] Failed to get preferences: %s", e)
        return PreferencesResponse()


@router.put("", response_model=PreferencesResponse)
@limiter.limit("30/minute")
async def update_preferences(
    request: Request,
    body: PreferencesUpdateRequest,
    auth: RequireAuth,
) -> PreferencesResponse:
    """
    Update preferences for the authenticated user.

    Only provided fields are updated (partial update).
    Returns the full updated preferences.
    """
    try:
        from app.repositories.user_preferences_repository import get_user_preferences_repository
        repo = get_user_preferences_repository()

        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        for key, value in updates.items():
            repo.update_preference(auth.user_id, key, value)

        prefs = repo.get_preferences(auth.user_id)
        logger.info("[PREFERENCES_API] Updated for user=%s: %s", auth.user_id, list(updates.keys()))
        return PreferencesResponse(**prefs)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("[PREFERENCES_API] Failed to update: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update preferences")
