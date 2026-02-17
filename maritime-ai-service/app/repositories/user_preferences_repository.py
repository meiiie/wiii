"""
User Preferences Repository — Structured preferences for agent adaptation

Sprint 17: Virtual Agent-per-User Architecture
Stores structured user preferences that the agent uses to personalize interactions.

Unlike free-text semantic_memory facts, these are structured key-value preferences:
- learning_style: "quiz" | "visual" | "reading" | "mixed"
- difficulty: "beginner" | "intermediate" | "advanced"
- pronoun_style: "auto" | "formal" | "casual"
- etc.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Default preferences for new users
DEFAULT_PREFERENCES = {
    "preferred_domain": "maritime",
    "language": "vi",
    "pronoun_style": "auto",
    "learning_style": "mixed",
    "difficulty": "intermediate",
    "timezone": "Asia/Ho_Chi_Minh",
}

# Allowed values for structured fields
VALID_LEARNING_STYLES = {"quiz", "visual", "reading", "mixed", "interactive"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced", "expert"}
VALID_PRONOUN_STYLES = {"auto", "formal", "casual"}


class UserPreferencesRepository:
    """
    Repository for user_preferences table CRUD operations.

    Uses the shared database engine (singleton pattern).
    """

    TABLE_NAME = "user_preferences"

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization using shared database engine."""
        if not self._initialized:
            try:
                from app.core.database import get_shared_engine, get_shared_session_factory
                self._engine = get_shared_engine()
                self._session_factory = get_shared_session_factory()
                self._initialized = True
            except Exception as e:
                logger.error("UserPreferencesRepository init failed: %s", e)

    def get_preferences(self, user_id: str) -> dict:
        """
        Get user preferences, returning defaults for missing fields.

        Args:
            user_id: User ID

        Returns:
            Dict with all preference fields (defaults filled in)
        """
        self._ensure_initialized()
        if not self._session_factory:
            return {**DEFAULT_PREFERENCES, "user_id": user_id}

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(
                        f"SELECT user_id, display_name, preferred_domain, language, "
                        f"pronoun_style, learning_style, difficulty, timezone, extra_prefs "
                        f"FROM {self.TABLE_NAME} WHERE user_id = :user_id"
                    ),
                    {"user_id": user_id},
                ).fetchone()

                if not result:
                    return {**DEFAULT_PREFERENCES, "user_id": user_id}

                prefs = {
                    "user_id": result[0],
                    "display_name": result[1],
                    "preferred_domain": result[2] or DEFAULT_PREFERENCES["preferred_domain"],
                    "language": result[3] or DEFAULT_PREFERENCES["language"],
                    "pronoun_style": result[4] or DEFAULT_PREFERENCES["pronoun_style"],
                    "learning_style": result[5] or DEFAULT_PREFERENCES["learning_style"],
                    "difficulty": result[6] or DEFAULT_PREFERENCES["difficulty"],
                    "timezone": result[7] or DEFAULT_PREFERENCES["timezone"],
                    "extra_prefs": result[8] if result[8] else {},
                }
                return prefs

        except Exception as e:
            logger.error("Get preferences failed: %s", e)
            return {**DEFAULT_PREFERENCES, "user_id": user_id}

    def update_preference(self, user_id: str, key: str, value: str) -> bool:
        """
        Update a single preference field.

        Called by the agent's preference tool when it detects user preferences.

        Args:
            user_id: User ID
            key: Preference key (e.g., "learning_style", "difficulty")
            value: Preference value

        Returns:
            True if updated successfully
        """
        self._ensure_initialized()
        if not self._session_factory:
            return False

        # Validate known fields
        known_columns = {
            "display_name", "preferred_domain", "language",
            "pronoun_style", "learning_style", "difficulty", "timezone",
        }

        now = datetime.now(timezone.utc)

        try:
            with self._session_factory() as session:
                if key in known_columns:
                    # Validate specific fields
                    if key == "learning_style" and value not in VALID_LEARNING_STYLES:
                        logger.warning("Invalid learning_style: %s", value)
                        return False
                    if key == "difficulty" and value not in VALID_DIFFICULTIES:
                        logger.warning("Invalid difficulty: %s", value)
                        return False
                    if key == "pronoun_style" and value not in VALID_PRONOUN_STYLES:
                        logger.warning("Invalid pronoun_style: %s", value)
                        return False

                    # Upsert with known column
                    self._upsert_row(session, user_id, {key: value}, now)
                else:
                    # Store in extra_prefs JSONB
                    self._upsert_extra_pref(session, user_id, key, value, now)

                session.commit()
                logger.info("[PREF] Updated %s=%s for user %s", key, value, user_id)
                return True

        except Exception as e:
            logger.error("Update preference failed: %s", e)
            return False

    def set_preferences(self, user_id: str, prefs: dict) -> bool:
        """
        Set multiple preferences at once.

        Args:
            user_id: User ID
            prefs: Dict of preference key-value pairs

        Returns:
            True if all updated
        """
        success = True
        for key, value in prefs.items():
            if key == "user_id":
                continue
            if not self.update_preference(user_id, key, str(value)):
                success = False
        return success

    def _upsert_row(self, session, user_id: str, fields: dict, now: datetime) -> None:
        """Upsert a row with specific column values."""
        # Check if row exists
        exists = session.execute(
            text(f"SELECT 1 FROM {self.TABLE_NAME} WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).fetchone()

        if exists:
            set_clause = ", ".join(f"{k} = :{k}" for k in fields)
            session.execute(
                text(
                    f"UPDATE {self.TABLE_NAME} SET {set_clause}, updated_at = :now "
                    f"WHERE user_id = :user_id"
                ),
                {"user_id": user_id, "now": now, **fields},
            )
        else:
            columns = ["user_id", "updated_at"] + list(fields.keys())
            placeholders = [":user_id", ":now"] + [f":{k}" for k in fields]
            session.execute(
                text(
                    f"INSERT INTO {self.TABLE_NAME} ({', '.join(columns)}) "
                    f"VALUES ({', '.join(placeholders)})"
                ),
                {"user_id": user_id, "now": now, **fields},
            )

    def _upsert_extra_pref(
        self, session, user_id: str, key: str, value: str, now: datetime
    ) -> None:
        """Store a preference in the extra_prefs JSONB field."""
        exists = session.execute(
            text(f"SELECT 1 FROM {self.TABLE_NAME} WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).fetchone()

        extra_json = json.dumps({key: value})

        if exists:
            session.execute(
                text(
                    f"UPDATE {self.TABLE_NAME} SET "
                    f"extra_prefs = COALESCE(extra_prefs, '{{}}'::jsonb) || CAST(:extra AS jsonb), "
                    f"updated_at = :now "
                    f"WHERE user_id = :user_id"
                ),
                {"user_id": user_id, "extra": extra_json, "now": now},
            )
        else:
            session.execute(
                text(
                    f"INSERT INTO {self.TABLE_NAME} (user_id, extra_prefs, updated_at) "
                    f"VALUES (:user_id, CAST(:extra AS jsonb), :now)"
                ),
                {"user_id": user_id, "extra": extra_json, "now": now},
            )

    def format_for_prompt(self, user_id: str) -> str:
        """
        Format user preferences as a string for prompt injection.

        Used by InputProcessor to inject Layer 2 context.

        Returns:
            Formatted preference string, or empty string
        """
        prefs = self.get_preferences(user_id)

        parts = []
        if prefs.get("display_name"):
            parts.append(f"Tên: {prefs['display_name']}")
        if prefs.get("learning_style") != "mixed":
            style_vi = {
                "quiz": "thích làm quiz",
                "visual": "học qua hình ảnh",
                "reading": "đọc tài liệu",
                "interactive": "tương tác thực hành",
            }.get(prefs["learning_style"], prefs["learning_style"])
            parts.append(f"Phong cách học: {style_vi}")
        if prefs.get("difficulty") != "intermediate":
            parts.append(f"Mức độ: {prefs['difficulty']}")
        if prefs.get("pronoun_style") != "auto":
            parts.append(f"Xưng hô: {prefs['pronoun_style']}")

        return " | ".join(parts) if parts else ""


# =============================================================================
# Singleton
# =============================================================================

_prefs_repo: Optional[UserPreferencesRepository] = None


def get_user_preferences_repository() -> UserPreferencesRepository:
    """Get or create the UserPreferencesRepository singleton."""
    global _prefs_repo
    if _prefs_repo is None:
        _prefs_repo = UserPreferencesRepository()
    return _prefs_repo
