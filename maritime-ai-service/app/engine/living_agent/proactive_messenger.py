"""
Proactive Messenger — Wiii's initiative communication system.

Sprint 176: "Wiii Soul AGI" — Phase 5A

Sends proactive messages when Wiii has something valuable to share:
- Morning/evening briefings
- Interesting discoveries
- Weather alerts
- Skill mastery celebrations
- Re-engagement after inactivity

Design:
    - Hard anti-spam limits (max 3/day, min 4h between, quiet hours)
    - User opt-out via "dung nhan nua" command
    - Trigger-based with priority scoring
    - Feature-gated: living_agent_enable_proactive_messaging
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from app.engine.living_agent.models import ProactiveMessage

logger = logging.getLogger(__name__)

_VN_OFFSET = timedelta(hours=7)


class ProactiveMessenger:
    """Sends proactive messages with anti-spam guardrails.

    Usage:
        messenger = ProactiveMessenger()
        if await messenger.can_send(user_id):
            await messenger.send(user_id, "messenger", content, trigger="briefing")
    """

    def __init__(self):
        # In-memory tracking (per-session, backed by DB for persistence)
        self._daily_counts: Dict[str, int] = {}
        self._last_sent: Dict[str, datetime] = {}
        self._daily_reset_date: str = ""

    async def can_send(self, user_id: str) -> bool:
        """Check if we can send a proactive message to this user.

        Checks:
        1. Feature flag enabled
        2. Within quiet hours (23:00-05:00 = no send)
        3. Daily limit not exceeded
        4. Cooloff period since last message
        5. User hasn't opted out
        """
        from app.core.config import settings

        if not settings.living_agent_enable_proactive_messaging:
            return False

        # Quiet hours check
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        quiet_start = settings.living_agent_proactive_quiet_start
        quiet_end = settings.living_agent_proactive_quiet_end
        hour = now_vn.hour

        if quiet_start > quiet_end:
            # Wraps midnight (e.g. 23-05)
            if hour >= quiet_start or hour < quiet_end:
                return False
        elif quiet_start <= hour < quiet_end:
            return False

        # Daily limit check
        self._reset_daily_if_needed()
        count = self._daily_counts.get(user_id, 0)
        if count >= settings.living_agent_max_proactive_per_day:
            return False

        # Cooloff check (min 4 hours between proactive messages)
        last = self._last_sent.get(user_id)
        if last and (datetime.now(timezone.utc) - last).total_seconds() < 4 * 3600:
            return False

        # Opt-out check
        if await self._is_opted_out(user_id):
            return False

        return True

    async def send(
        self,
        user_id: str,
        channel: str,
        content: str,
        trigger: str = "general",
        priority: float = 0.5,
    ) -> bool:
        """Send a proactive message if allowed.

        Returns:
            True if message was delivered successfully.
        """
        if not await self.can_send(user_id):
            logger.debug("[PROACTIVE] Blocked for user %s (limits/opt-out)", user_id)
            return False

        # Deliver
        success = await self._deliver(user_id, channel, content)
        if not success:
            return False

        # Track
        self._daily_counts[user_id] = self._daily_counts.get(user_id, 0) + 1
        self._last_sent[user_id] = datetime.now(timezone.utc)

        # Persist
        msg = ProactiveMessage(
            user_id=user_id,
            channel=channel,
            content=content,
            trigger=trigger,
            priority=priority,
            delivered=True,
            delivered_at=datetime.now(timezone.utc),
        )
        await self._save_message(msg)

        logger.info(
            "[PROACTIVE] Sent to %s via %s (trigger=%s, daily=%d)",
            user_id, channel, trigger, self._daily_counts[user_id],
        )
        return True

    async def opt_out(self, user_id: str) -> None:
        """Opt user out of proactive messages."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_proactive_preferences (user_id, opted_out, updated_at)
                        VALUES (:uid, true, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET opted_out = true, updated_at = NOW()
                    """),
                    {"uid": user_id},
                )
                session.commit()
            logger.info("[PROACTIVE] User %s opted out", user_id)
        except Exception as e:
            logger.warning("[PROACTIVE] Failed to opt out: %s", e)

    async def opt_in(self, user_id: str) -> None:
        """Opt user back in to proactive messages."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_proactive_preferences (user_id, opted_out, updated_at)
                        VALUES (:uid, false, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET opted_out = false, updated_at = NOW()
                    """),
                    {"uid": user_id},
                )
                session.commit()
        except Exception as e:
            logger.warning("[PROACTIVE] Failed to opt in: %s", e)

    async def get_daily_stats(self) -> Dict[str, int]:
        """Get today's proactive message counts per user."""
        self._reset_daily_if_needed()
        return dict(self._daily_counts)

    # =========================================================================
    # Internal helpers
    # =========================================================================

    async def _deliver(self, user_id: str, channel: str, content: str) -> bool:
        """Deliver message via channel_sender (Sprint 188: DRY shared sender).

        Also emits PROACTIVE_MESSAGE life event on success.
        """
        try:
            from app.engine.living_agent.channel_sender import send_to_channel

            result = await send_to_channel(channel, user_id, content)
            if result.success:
                # Emit life event for emotion engine
                try:
                    from app.engine.living_agent.emotion_engine import get_emotion_engine
                    from app.engine.living_agent.models import LifeEvent, LifeEventType
                    get_emotion_engine().process_event(LifeEvent(
                        event_type=LifeEventType.USER_CONVERSATION,
                        description=f"Proactive message sent via {channel}",
                        importance=0.3,
                    ))
                except Exception:
                    pass
            return result.success
        except Exception as e:
            logger.warning("[PROACTIVE] Delivery failed: %s", e)
            return False

    async def _is_opted_out(self, user_id: str) -> bool:
        """Check if user has opted out of proactive messages."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                row = session.execute(
                    text("SELECT opted_out FROM wiii_proactive_preferences WHERE user_id = :uid"),
                    {"uid": user_id},
                ).fetchone()
                return bool(row and row[0])
        except Exception:
            return False  # Assume opted-in if DB fails

    async def _save_message(self, msg: ProactiveMessage) -> None:
        """Save proactive message record."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_proactive_messages
                        (id, user_id, channel, content, trigger, priority,
                         delivered, delivered_at, created_at)
                        VALUES (:id, :uid, :channel, :content, :trigger, :priority,
                                :delivered, :delivered_at, NOW())
                    """),
                    {
                        "id": str(msg.id),
                        "uid": msg.user_id,
                        "channel": msg.channel,
                        "content": msg.content[:2000],
                        "trigger": msg.trigger,
                        "priority": msg.priority,
                        "delivered": msg.delivered,
                        "delivered_at": msg.delivered_at,
                    },
                )
                session.commit()
        except Exception as e:
            logger.warning("[PROACTIVE] Failed to save message: %s", e)

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters at midnight UTC+7."""
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        today = now_vn.strftime("%Y-%m-%d")
        if self._daily_reset_date != today:
            self._daily_reset_date = today
            self._daily_counts.clear()


# =============================================================================
# Singleton
# =============================================================================

_messenger_instance: Optional[ProactiveMessenger] = None


def get_proactive_messenger() -> ProactiveMessenger:
    """Get the singleton ProactiveMessenger instance."""
    global _messenger_instance
    if _messenger_instance is None:
        _messenger_instance = ProactiveMessenger()
    return _messenger_instance
