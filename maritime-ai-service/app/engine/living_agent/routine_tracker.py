"""
Routine Tracker — Learn user behavior patterns.

Sprint 176: "Wiii Soul AGI" — Phase 3B

Tracks when users are active, what they ask about, and their mood trends.
Used to optimize briefing timing and personalize proactive messages.

Design:
    - Updates on every user interaction (via webhook handlers)
    - Stored per-user in wiii_user_routines table
    - Feature-gated: living_agent_enable_routine_tracking
    - No LLM cost — pure statistical tracking
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.engine.living_agent.models import UserRoutine

logger = logging.getLogger(__name__)

_VN_OFFSET = timedelta(hours=7)


class RoutineTracker:
    """Tracks and learns user behavior patterns.

    Usage:
        tracker = RoutineTracker()
        await tracker.record_interaction(user_id, channel, topic)
        routine = await tracker.get_routine(user_id)
    """

    async def record_interaction(
        self,
        user_id: str,
        channel: str = "web",
        topic: str = "",
    ) -> None:
        """Record a user interaction for pattern learning.

        Called from webhook handlers and chat orchestrator.
        """
        from app.core.config import settings

        if not settings.living_agent_enable_routine_tracking:
            return

        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        hour = now_vn.hour

        try:
            routine = await self._load_routine(user_id)
            if routine is None:
                routine = UserRoutine(user_id=user_id)

            # Update active hours histogram
            if hour not in routine.typical_active_hours:
                routine.typical_active_hours.append(hour)
                # Keep sorted and deduplicated
                routine.typical_active_hours = sorted(set(routine.typical_active_hours))

            # Update topics
            if topic and topic not in routine.common_topics:
                routine.common_topics.append(topic)
                routine.common_topics = routine.common_topics[-20:]  # Keep last 20

            # Update counters
            routine.total_messages += 1
            routine.last_seen = datetime.now(timezone.utc)
            routine.updated_at = datetime.now(timezone.utc)

            # Compute preferred briefing time (hour with most interactions)
            if routine.typical_active_hours:
                hour_counts = Counter(routine.typical_active_hours)
                routine.preferred_briefing_time = hour_counts.most_common(1)[0][0]

            # Compute conversation frequency (messages per day, rolling 7-day window)
            routine.conversation_frequency = await self._compute_frequency(user_id)

            await self._save_routine(routine)

        except Exception as e:
            logger.warning("[ROUTINE] Failed to record interaction: %s", e)

    async def get_routine(self, user_id: str) -> Optional[UserRoutine]:
        """Get learned routine for a user."""
        return await self._load_routine(user_id)

    async def get_inactive_users(self, days: int = 3) -> List[str]:
        """Find users who haven't interacted in N days."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                rows = session.execute(
                    text("""
                        SELECT user_id FROM wiii_user_routines
                        WHERE last_seen < NOW() - INTERVAL '1 day' * :days
                        AND total_messages > 5
                        ORDER BY last_seen ASC
                    """),
                    {"days": days},
                ).fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.warning("[ROUTINE] Failed to query inactive users: %s", e)
            return []

    async def is_user_likely_active(self, user_id: str) -> bool:
        """Check if user is typically active at the current time."""
        routine = await self._load_routine(user_id)
        if not routine or not routine.typical_active_hours:
            return True  # Unknown — assume yes

        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return now_vn.hour in routine.typical_active_hours

    async def _compute_frequency(self, user_id: str) -> float:
        """Compute average messages per day over the last 7 days."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                row = session.execute(
                    text("""
                        SELECT total_messages, created_at FROM wiii_user_routines
                        WHERE user_id = :uid
                    """),
                    {"uid": user_id},
                ).fetchone()

                if row:
                    total = row[0] or 0
                    created = row[1]
                    if created:
                        days_active = max(1, (datetime.now(timezone.utc) - created).days)
                        return round(total / days_active, 2)
        except Exception:
            pass
        return 0.0

    async def _load_routine(self, user_id: str) -> Optional[UserRoutine]:
        """Load user routine from database."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                row = session.execute(
                    text("""
                        SELECT user_id, typical_active_hours, preferred_briefing_time,
                               conversation_frequency, common_topics, last_seen,
                               total_messages, updated_at
                        FROM wiii_user_routines
                        WHERE user_id = :uid
                    """),
                    {"uid": user_id},
                ).fetchone()

                if row:
                    return UserRoutine(
                        user_id=row[0],
                        typical_active_hours=json.loads(row[1]) if row[1] else [],
                        preferred_briefing_time=row[2] or 7,
                        conversation_frequency=float(row[3]) if row[3] else 0.0,
                        common_topics=json.loads(row[4]) if row[4] else [],
                        last_seen=row[5],
                        total_messages=row[6] or 0,
                        updated_at=row[7] or datetime.now(timezone.utc),
                    )
        except Exception as e:
            logger.warning("[ROUTINE] Failed to load routine: %s", e)
        return None

    async def _save_routine(self, routine: UserRoutine) -> None:
        """Upsert user routine to database."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_user_routines
                        (user_id, typical_active_hours, preferred_briefing_time,
                         conversation_frequency, common_topics, last_seen,
                         total_messages, updated_at, created_at)
                        VALUES (:uid, :hours, :briefing_time, :freq, :topics,
                                :last_seen, :total, NOW(), NOW())
                        ON CONFLICT (user_id)
                        DO UPDATE SET
                            typical_active_hours = :hours,
                            preferred_briefing_time = :briefing_time,
                            conversation_frequency = :freq,
                            common_topics = :topics,
                            last_seen = :last_seen,
                            total_messages = :total,
                            updated_at = NOW()
                    """),
                    {
                        "uid": routine.user_id,
                        "hours": json.dumps(routine.typical_active_hours),
                        "briefing_time": routine.preferred_briefing_time,
                        "freq": routine.conversation_frequency,
                        "topics": json.dumps(routine.common_topics, ensure_ascii=False),
                        "last_seen": routine.last_seen,
                        "total": routine.total_messages,
                    },
                )
                session.commit()
        except Exception as e:
            logger.warning("[ROUTINE] Failed to save routine: %s", e)


# =============================================================================
# Singleton
# =============================================================================

_tracker_instance: Optional[RoutineTracker] = None


def get_routine_tracker() -> RoutineTracker:
    """Get the singleton RoutineTracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = RoutineTracker()
    return _tracker_instance
