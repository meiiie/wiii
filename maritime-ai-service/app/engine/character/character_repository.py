"""
Character Repository — CRUD for Wiii's living character state.

Sprint 93: PostgreSQL storage for character blocks and experiences.
Follows existing repository patterns (lazy init, shared engine, session factory).

Sprint 124: Per-user isolation — all block queries now filter by user_id.
Each user gets their own set of character blocks. Default '__global__' for
backward compatibility.

Tables:
    wiii_character_blocks  — Self-editable memory blocks (per-user, Sprint 124)
    wiii_experiences       — Experience log (milestone, learning, feedback)
"""

import logging
from typing import List, Optional

from sqlalchemy import text

from app.engine.character.models import (
    BLOCK_CHAR_LIMITS,
    CharacterBlock,
    CharacterBlockCreate,
    CharacterBlockUpdate,
    CharacterExperience,
    CharacterExperienceCreate,
)

logger = logging.getLogger(__name__)


class CharacterRepository:
    """Repository for Wiii's character state (blocks + experiences)."""

    BLOCKS_TABLE = "wiii_character_blocks"
    EXPERIENCES_TABLE = "wiii_experiences"

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy init — load shared engine on first use."""
        if self._initialized:
            return
        try:
            from app.core.database import get_shared_engine, get_shared_session_factory
            self._engine = get_shared_engine()
            self._session_factory = get_shared_session_factory()
            self._initialized = True
            logger.info("CharacterRepository initialized with shared engine")
        except Exception as e:
            logger.warning("CharacterRepository init failed (DB may not be running): %s", e)

    # =========================================================================
    # CHARACTER BLOCKS — CRUD
    # =========================================================================

    def get_all_blocks(self, user_id: str = "__global__") -> List[CharacterBlock]:
        """Get all character blocks for a specific user.

        Args:
            user_id: User ID to filter by. Defaults to '__global__' for backward compat.
        """
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"""
                        SELECT id, label, content, char_limit, version,
                               metadata, created_at, updated_at
                        FROM {self.BLOCKS_TABLE}
                        WHERE user_id = :user_id
                        ORDER BY label
                    """),
                    {"user_id": user_id},
                )
                rows = result.fetchall()
                return [
                    CharacterBlock(
                        id=row.id,
                        label=row.label,
                        content=row.content,
                        char_limit=row.char_limit,
                        version=row.version,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error("Failed to get character blocks for user '%s': %s", user_id, e)
            return []

    def get_block(self, label: str, user_id: str = "__global__") -> Optional[CharacterBlock]:
        """Get a specific character block by label and user.

        Args:
            label: Block label (learned_lessons, etc.)
            user_id: User ID to filter by. Defaults to '__global__'.
        """
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"""
                        SELECT id, label, content, char_limit, version,
                               metadata, created_at, updated_at
                        FROM {self.BLOCKS_TABLE}
                        WHERE label = :label AND user_id = :user_id
                    """),
                    {"label": label, "user_id": user_id},
                )
                row = result.fetchone()
                if not row:
                    return None
                return CharacterBlock(
                    id=row.id,
                    label=row.label,
                    content=row.content,
                    char_limit=row.char_limit,
                    version=row.version,
                    metadata=row.metadata or {},
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
        except Exception as e:
            logger.error("Failed to get block '%s' for user '%s': %s", label, user_id, e)
            return None

    def create_block(self, create: CharacterBlockCreate, user_id: str = "__global__") -> Optional[CharacterBlock]:
        """Create a new character block for a specific user.

        Args:
            create: Block creation schema
            user_id: User ID. Defaults to '__global__'.
        """
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"""
                        INSERT INTO {self.BLOCKS_TABLE}
                            (label, content, char_limit, metadata, user_id)
                        VALUES (:label, :content, :char_limit, CAST(:metadata AS jsonb), :user_id)
                        ON CONFLICT (user_id, label) DO UPDATE
                            SET content = EXCLUDED.content,
                                char_limit = EXCLUDED.char_limit,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                        RETURNING id, label, content, char_limit, version,
                                  metadata, created_at, updated_at
                    """),
                    {
                        "label": create.label,
                        "content": create.content[:create.char_limit],
                        "char_limit": create.char_limit,
                        "metadata": "{}",
                        "user_id": user_id,
                    },
                )
                session.commit()
                row = result.fetchone()
                if row:
                    return CharacterBlock(
                        id=row.id,
                        label=row.label,
                        content=row.content,
                        char_limit=row.char_limit,
                        version=row.version,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                    )
        except Exception as e:
            logger.error("Failed to create block '%s' for user '%s': %s", create.label, user_id, e)
        return None

    def update_block(
        self,
        label: str,
        update: CharacterBlockUpdate,
        expected_version: Optional[int] = None,
        user_id: str = "__global__",
    ) -> Optional[CharacterBlock]:
        """Update a character block with optional optimistic locking.

        Args:
            label: Block label
            update: New content or append text
            expected_version: If set, only update if current version matches
            user_id: User ID to scope the update. Defaults to '__global__'.
        """
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                # Build update query
                if update.content is not None:
                    # Replace mode
                    char_limit = BLOCK_CHAR_LIMITS.get(label, 1000)
                    new_content = update.content[:char_limit]
                    if expected_version is not None:
                        result = session.execute(
                            text(f"""
                                UPDATE {self.BLOCKS_TABLE}
                                SET content = :content,
                                    version = version + 1,
                                    updated_at = NOW()
                                WHERE label = :label AND user_id = :user_id AND version = :version
                                RETURNING id, label, content, char_limit, version,
                                          metadata, created_at, updated_at
                            """),
                            {
                                "content": new_content,
                                "label": label,
                                "user_id": user_id,
                                "version": expected_version,
                            },
                        )
                    else:
                        result = session.execute(
                            text(f"""
                                UPDATE {self.BLOCKS_TABLE}
                                SET content = :content,
                                    version = version + 1,
                                    updated_at = NOW()
                                WHERE label = :label AND user_id = :user_id
                                RETURNING id, label, content, char_limit, version,
                                          metadata, created_at, updated_at
                            """),
                            {"content": new_content, "label": label, "user_id": user_id},
                        )
                elif update.append is not None:
                    # Append mode — respect char_limit
                    result = session.execute(
                        text(f"""
                            UPDATE {self.BLOCKS_TABLE}
                            SET content = LEFT(content || :append, char_limit),
                                version = version + 1,
                                updated_at = NOW()
                            WHERE label = :label AND user_id = :user_id
                            RETURNING id, label, content, char_limit, version,
                                      metadata, created_at, updated_at
                        """),
                        {"append": update.append, "label": label, "user_id": user_id},
                    )
                else:
                    return self.get_block(label, user_id=user_id)

                session.commit()
                row = result.fetchone()
                if row:
                    return CharacterBlock(
                        id=row.id,
                        label=row.label,
                        content=row.content,
                        char_limit=row.char_limit,
                        version=row.version,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                    )
                elif expected_version is not None:
                    logger.warning(
                        "Optimistic lock failed for block '%s' user '%s' (expected version %d)",
                        label, user_id, expected_version,
                    )
        except Exception as e:
            logger.error("Failed to update block '%s' for user '%s': %s", label, user_id, e)
        return None

    # =========================================================================
    # EXPERIENCES — Log and query
    # =========================================================================

    def log_experience(self, create: CharacterExperienceCreate) -> Optional[CharacterExperience]:
        """Log a new experience event."""
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"""
                        INSERT INTO {self.EXPERIENCES_TABLE}
                            (experience_type, content, importance, user_id, metadata)
                        VALUES (:type, :content, :importance, :user_id, CAST(:metadata AS jsonb))
                        RETURNING id, experience_type, content, importance,
                                  user_id, metadata, created_at
                    """),
                    {
                        "type": create.experience_type,
                        "content": create.content,
                        "importance": create.importance,
                        "user_id": create.user_id,
                        "metadata": "{}",
                    },
                )
                session.commit()
                row = result.fetchone()
                if row:
                    return CharacterExperience(
                        id=row.id,
                        experience_type=row.experience_type,
                        content=row.content,
                        importance=row.importance,
                        user_id=row.user_id,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                    )
        except Exception as e:
            logger.error("Failed to log experience: %s", e)
        return None

    def get_recent_experiences(
        self,
        limit: int = 20,
        experience_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[CharacterExperience]:
        """Get recent experiences, optionally filtered by type and user.

        Sprint 125: Added user_id filter for per-user isolation.
        """
        self._ensure_initialized()
        if not self._session_factory:
            return []

        try:
            with self._session_factory() as session:
                # Build WHERE conditions dynamically
                conditions = []
                params: dict = {"limit": limit}

                if experience_type:
                    conditions.append("experience_type = :type")
                    params["type"] = experience_type
                if user_id:
                    conditions.append("user_id = :user_id")
                    params["user_id"] = user_id

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                result = session.execute(
                    text(f"""
                        SELECT id, experience_type, content, importance,
                               user_id, metadata, created_at
                        FROM {self.EXPERIENCES_TABLE}
                        {where_clause}
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    params,
                )
                rows = result.fetchall()
                return [
                    CharacterExperience(
                        id=row.id,
                        experience_type=row.experience_type,
                        content=row.content,
                        importance=row.importance,
                        user_id=row.user_id,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error("Failed to get experiences: %s", e)
            return []

    def count_experiences(self) -> int:
        """Count total logged experiences."""
        self._ensure_initialized()
        if not self._session_factory:
            return 0

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"SELECT COUNT(*) FROM {self.EXPERIENCES_TABLE}")
                )
                return result.scalar() or 0
        except Exception as e:
            logger.error("Failed to count experiences: %s", e)
            return 0

    def cleanup_old_experiences(
        self,
        max_age_days: int = 90,
        keep_min: int = 100,
        user_id: Optional[str] = None,
    ) -> int:
        """Delete old experiences while keeping at least keep_min most recent.

        Sprint 98: Experience Log TTL — prevents unbounded growth of
        wiii_experiences table.
        Sprint 125: Added user_id scope for per-user isolation.

        Args:
            max_age_days: Delete experiences older than this many days
            keep_min: Always keep at least this many most recent experiences
            user_id: Scope cleanup to specific user (None = all users)

        Returns:
            Number of deleted experiences
        """
        self._ensure_initialized()
        if not self._session_factory:
            return 0

        try:
            with self._session_factory() as session:
                # Build user filter
                user_filter = "AND user_id = :user_id" if user_id else ""
                params: dict = {"days": str(max_age_days), "keep_min": keep_min}
                if user_id:
                    params["user_id"] = user_id

                # Check total count first
                total = session.execute(
                    text(f"SELECT COUNT(*) FROM {self.EXPERIENCES_TABLE} WHERE 1=1 {user_filter}"),
                    params,
                ).scalar() or 0

                if total <= keep_min:
                    logger.debug(
                        "[CLEANUP] Only %d experiences (min=%d), skipping",
                        total, keep_min,
                    )
                    return 0

                # Delete old experiences, but always keep the most recent keep_min
                result = session.execute(
                    text(f"""
                        DELETE FROM {self.EXPERIENCES_TABLE}
                        WHERE created_at < NOW() - CAST(:days || ' days' AS INTERVAL)
                          {user_filter}
                          AND id NOT IN (
                              SELECT id FROM {self.EXPERIENCES_TABLE}
                              WHERE 1=1 {user_filter}
                              ORDER BY created_at DESC
                              LIMIT :keep_min
                          )
                    """),
                    params,
                )
                session.commit()
                deleted = result.rowcount or 0

                if deleted > 0:
                    logger.info(
                        "[CLEANUP] Deleted %d old experiences (older than %d days, kept min %d, user=%s)",
                        deleted, max_age_days, keep_min, user_id or "all",
                    )
                return deleted

        except Exception as e:
            logger.error("Failed to cleanup old experiences: %s", e)
            return 0


# =============================================================================
# Singleton
# =============================================================================

_character_repo: Optional[CharacterRepository] = None


def get_character_repository() -> CharacterRepository:
    """Get or create CharacterRepository singleton."""
    global _character_repo
    if _character_repo is None:
        _character_repo = CharacterRepository()
    return _character_repo
