"""
Emotional State Repository — Persistence for Wiii's emotional snapshots.

Sprint 170: "Linh Hồn Sống"

Stores and retrieves emotional state snapshots from PostgreSQL.
Uses the shared database engine (singleton pattern from database.py).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from app.core.database import get_shared_session_factory

logger = logging.getLogger(__name__)


class EmotionalStateRepository:
    """CRUD operations for wiii_emotional_snapshots table."""

    def save_snapshot(
        self,
        primary_mood: str,
        energy_level: float,
        social_battery: float,
        engagement: float,
        trigger_event: Optional[str] = None,
        state_json: Optional[dict] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Save an emotional state snapshot.

        Returns:
            The snapshot ID.
        """
        from sqlalchemy import text

        snapshot_id = str(uuid4())
        session_factory = get_shared_session_factory()

        try:
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_emotional_snapshots
                        (id, primary_mood, energy_level, social_battery, engagement,
                         trigger_event, snapshot_at, organization_id, state_json)
                        VALUES (:id, :mood, :energy, :social, :engagement,
                                :trigger, :snapshot_at, :org_id, :state)
                    """),
                    {
                        "id": snapshot_id,
                        "mood": primary_mood,
                        "energy": energy_level,
                        "social": social_battery,
                        "engagement": engagement,
                        "trigger": trigger_event,
                        "snapshot_at": datetime.now(timezone.utc),
                        "org_id": organization_id,
                        "state": json.dumps(state_json or {}, ensure_ascii=False),
                    },
                )
                session.commit()
                logger.debug("[EMOTION_REPO] Saved snapshot: mood=%s", primary_mood)
                return snapshot_id

        except Exception as e:
            logger.error("[EMOTION_REPO] Failed to save snapshot: %s", e)
            raise

    def get_latest(self, organization_id: Optional[str] = None) -> Optional[Dict]:
        """Get the most recent emotional snapshot.

        Returns:
            Dict with snapshot data, or None if no snapshots exist.
        """
        from sqlalchemy import text

        session_factory = get_shared_session_factory()

        try:
            with session_factory() as session:
                query = """
                    SELECT id, primary_mood, energy_level, social_battery, engagement,
                           trigger_event, snapshot_at, state_json
                    FROM wiii_emotional_snapshots
                    WHERE 1=1
                """
                params = {}
                if organization_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = organization_id

                query += " ORDER BY snapshot_at DESC LIMIT 1"

                result = session.execute(text(query), params).fetchone()
                if not result:
                    return None

                return {
                    "id": result[0],
                    "primary_mood": result[1],
                    "energy_level": result[2],
                    "social_battery": result[3],
                    "engagement": result[4],
                    "trigger_event": result[5],
                    "snapshot_at": result[6].isoformat() if result[6] else None,
                    "state_json": json.loads(result[7]) if result[7] else {},
                }

        except Exception as e:
            logger.error("[EMOTION_REPO] Failed to get latest snapshot: %s", e)
            return None

    def get_history(
        self,
        hours: int = 24,
        organization_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get emotional snapshots from the last N hours.

        Args:
            hours: Number of hours to look back.
            organization_id: Optional org filter.

        Returns:
            List of snapshot dicts, ordered by time ascending.
        """
        from sqlalchemy import text

        session_factory = get_shared_session_factory()

        try:
            with session_factory() as session:
                query = """
                    SELECT id, primary_mood, energy_level, social_battery, engagement,
                           trigger_event, snapshot_at
                    FROM wiii_emotional_snapshots
                    WHERE snapshot_at >= NOW() - INTERVAL ':hours hours'
                """
                params: dict = {"hours": hours}
                if organization_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = organization_id

                query += " ORDER BY snapshot_at ASC"

                # Use string interpolation for interval (parameterized interval not supported)
                actual_query = query.replace(":hours hours", f"{hours} hours")
                actual_params = {k: v for k, v in params.items() if k != "hours"}

                results = session.execute(text(actual_query), actual_params).fetchall()
                return [
                    {
                        "id": row[0],
                        "primary_mood": row[1],
                        "energy_level": row[2],
                        "social_battery": row[3],
                        "engagement": row[4],
                        "trigger_event": row[5],
                        "snapshot_at": row[6].isoformat() if row[6] else None,
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error("[EMOTION_REPO] Failed to get history: %s", e)
            return []

    def cleanup_old_snapshots(self, keep_days: int = 30) -> int:
        """Delete emotional snapshots older than N days.

        Returns:
            Number of deleted rows.
        """
        from sqlalchemy import text

        session_factory = get_shared_session_factory()

        try:
            with session_factory() as session:
                result = session.execute(
                    text(f"""
                        DELETE FROM wiii_emotional_snapshots
                        WHERE snapshot_at < NOW() - INTERVAL '{keep_days} days'
                    """),
                )
                session.commit()
                count = result.rowcount
                if count > 0:
                    logger.info("[EMOTION_REPO] Cleaned up %d old snapshots", count)
                return count

        except Exception as e:
            logger.error("[EMOTION_REPO] Failed to cleanup: %s", e)
            return 0
