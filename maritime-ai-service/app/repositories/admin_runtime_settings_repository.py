"""
Admin runtime settings repository.

Stores persisted system-wide runtime policy snapshots in PostgreSQL.
Pattern matches the existing repository layer: shared SQLAlchemy engine,
raw SQL, and fail-soft behavior on database errors.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminRuntimeSettingsRecord:
    key: str
    settings: dict[str, Any]
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AdminRuntimeSettingsRepository:
    """CRUD access for the admin_runtime_settings table."""

    TABLE = "admin_runtime_settings"

    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            from app.core.database import get_shared_engine, get_shared_session_factory

            self._engine = get_shared_engine()
            self._session_factory = get_shared_session_factory()
            self._initialized = True
        except Exception as exc:
            logger.error("AdminRuntimeSettingsRepository init failed: %s", exc)

    def get_settings(self, key: str) -> Optional[AdminRuntimeSettingsRecord]:
        self._ensure_initialized()
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"SELECT key, settings, description, created_at, updated_at "
                        f"FROM {self.TABLE} WHERE key = :key"
                    ),
                    {"key": key},
                ).fetchone()
                if not row:
                    return None

                payload = row[1] or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)
                if not isinstance(payload, dict):
                    logger.warning(
                        "Ignoring non-dict admin runtime settings payload for %s",
                        key,
                    )
                    payload = {}

                return AdminRuntimeSettingsRecord(
                    key=row[0],
                    settings=payload,
                    description=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
        except Exception as exc:
            logger.warning("Failed to load admin runtime settings '%s': %s", key, exc)
            return None

    def upsert_settings(
        self,
        key: str,
        settings_payload: dict[str, Any],
        *,
        description: Optional[str] = None,
    ) -> Optional[AdminRuntimeSettingsRecord]:
        self._ensure_initialized()
        if not self._session_factory:
            return None

        now = datetime.now(timezone.utc)

        try:
            with self._session_factory() as session:
                row = session.execute(
                    text(
                        f"INSERT INTO {self.TABLE} "
                        f"(key, settings, description, created_at, updated_at) "
                        f"VALUES (:key, CAST(:settings AS jsonb), :description, :now, :now) "
                        f"ON CONFLICT (key) DO UPDATE SET "
                        f"settings = CAST(:settings AS jsonb), "
                        f"description = COALESCE(:description, {self.TABLE}.description), "
                        f"updated_at = :now "
                        f"RETURNING key, settings, description, created_at, updated_at"
                    ),
                    {
                        "key": key,
                        "settings": json.dumps(settings_payload, ensure_ascii=False),
                        "description": description,
                        "now": now,
                    },
                ).fetchone()
                session.commit()

                if not row:
                    return None

                payload = row[1] or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)

                return AdminRuntimeSettingsRecord(
                    key=row[0],
                    settings=payload if isinstance(payload, dict) else {},
                    description=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
        except Exception as exc:
            logger.error("Failed to upsert admin runtime settings '%s': %s", key, exc)
            return None

    def delete_settings(self, key: str) -> bool:
        self._ensure_initialized()
        if not self._session_factory:
            return False

        try:
            with self._session_factory() as session:
                result = session.execute(
                    text(f"DELETE FROM {self.TABLE} WHERE key = :key"),
                    {"key": key},
                )
                session.commit()
                return result.rowcount > 0
        except Exception as exc:
            logger.error("Failed to delete admin runtime settings '%s': %s", key, exc)
            return False


_runtime_settings_repository: Optional[AdminRuntimeSettingsRepository] = None


def get_admin_runtime_settings_repository() -> AdminRuntimeSettingsRepository:
    global _runtime_settings_repository
    if _runtime_settings_repository is None:
        _runtime_settings_repository = AdminRuntimeSettingsRepository()
    return _runtime_settings_repository
