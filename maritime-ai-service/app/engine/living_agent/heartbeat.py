"""
Heartbeat Scheduler — Wiii's periodic autonomy engine.

Sprint 170: "Linh Hồn Sống"

Wakes Wiii at configurable intervals to:
1. Load soul and emotional state
2. Check active goals
3. Choose and execute an action (browse, learn, reflect, journal)
4. Update emotional state based on results
5. Log experience for long-term memory

Inspired by OpenClaw's heartbeat (30-min interval, HEARTBEAT.md, HEARTBEAT_OK).

Design:
    - Reuses existing ScheduledTaskExecutor pattern (asyncio poll loop)
    - Active hours support (e.g., 08:00-23:00 UTC+7)
    - Uses LOCAL MODEL (Ollama) for zero API cost
    - Feature-gated: enable_living_agent=False by default
    - Non-blocking: all errors caught, never affects user chat
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.engine.living_agent.models import (
    ActionType,
    HeartbeatAction,
    HeartbeatResult,
    LifeEvent,
    LifeEventType,
)

logger = logging.getLogger(__name__)

# UTC+7 offset for Vietnamese timezone
_VN_OFFSET = timedelta(hours=7)


class HeartbeatScheduler:
    """Periodic autonomy engine for Wiii's living agent.

    Runs as a background asyncio task, waking Wiii at configured intervals
    during active hours. Each heartbeat cycle:
    1. Checks if within active hours
    2. Loads current emotional state + soul
    3. Plans actions based on mood, energy, and goals
    4. Executes actions (browse, learn, reflect, journal)
    5. Updates emotional state
    6. Saves snapshot

    Usage:
        scheduler = HeartbeatScheduler()
        await scheduler.start()
        # ... runs in background ...
        await scheduler.stop()
    """

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._heartbeat_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def heartbeat_count(self) -> int:
        return self._heartbeat_count

    async def start(self) -> None:
        """Start the heartbeat loop as a background task."""
        if self._running:
            logger.warning("[HEARTBEAT] Already running, skipping start")
            return

        self._shutdown_event.clear()
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("[HEARTBEAT] Wiii's heartbeat started")

    async def stop(self) -> None:
        """Gracefully stop the heartbeat loop."""
        if not self._running:
            return

        self._shutdown_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        self._running = False
        logger.info("[HEARTBEAT] Wiii's heartbeat stopped (total: %d cycles)", self._heartbeat_count)

    async def _heartbeat_loop(self) -> None:
        """Main loop: sleep, check active hours, execute heartbeat."""
        from app.core.config import settings

        interval = settings.living_agent_heartbeat_interval

        while not self._shutdown_event.is_set():
            try:
                if self._is_active_hours():
                    result = await self._execute_heartbeat()
                    if result.error:
                        logger.warning("[HEARTBEAT] Cycle error: %s", result.error)
                    elif result.is_noop:
                        logger.debug("[HEARTBEAT] NOOP — nothing to do")
                    else:
                        logger.info(
                            "[HEARTBEAT] Cycle #%d complete: %d actions, %d insights, %dms",
                            self._heartbeat_count,
                            len(result.actions_taken),
                            result.insights_gained,
                            result.duration_ms,
                        )
                else:
                    logger.debug("[HEARTBEAT] Outside active hours, sleeping")
            except Exception as e:
                logger.error("[HEARTBEAT] Unexpected error: %s", e, exc_info=True)

            # Wait for interval or shutdown signal
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=interval,
                )
                break  # Shutdown signal received
            except asyncio.TimeoutError:
                pass  # Interval elapsed, continue

    async def _execute_heartbeat(self) -> HeartbeatResult:
        """Execute a single heartbeat cycle."""
        from app.engine.living_agent.emotion_engine import get_emotion_engine
        from app.engine.living_agent.soul_loader import get_soul

        start_time = time.monotonic()
        self._heartbeat_count += 1

        result = HeartbeatResult()

        try:
            # 1. Load current state
            soul = get_soul()
            engine = get_emotion_engine()

            # Signal wake-up
            engine.process_event(LifeEvent(
                event_type=LifeEventType.HEARTBEAT_WAKE,
                description="Heartbeat wake-up",
                importance=0.2,
            ))

            # 2. Plan actions based on mood and energy
            actions = self._plan_actions(engine.mood.value, engine.energy)
            if not actions:
                result.is_noop = True
                return result

            # 3. Execute actions
            for action in actions:
                try:
                    await self._execute_action(action, soul, engine)
                    result.actions_taken.append(action)
                except Exception as e:
                    logger.warning(
                        "[HEARTBEAT] Action %s failed: %s",
                        action.action_type.value, e,
                    )

            # 4. Take emotional snapshot
            engine.take_snapshot()

            # 5. Save emotional state to DB
            await self._save_emotional_snapshot(engine)

        except Exception as e:
            result.error = str(e)
            logger.error("[HEARTBEAT] Cycle failed: %s", e, exc_info=True)

        result.duration_ms = int((time.monotonic() - start_time) * 1000)
        return result

    def _plan_actions(self, mood: str, energy: float) -> list:
        """Plan actions for this heartbeat based on mood and energy.

        Returns list of HeartbeatAction, max limited by config.
        """
        from app.core.config import settings
        max_actions = settings.living_agent_max_actions_per_heartbeat

        candidates = []

        # Always available: check goals and reflect (low energy cost)
        candidates.append(HeartbeatAction(
            action_type=ActionType.CHECK_GOALS,
            priority=0.8,
        ))

        if energy > 0.5:
            # Good energy — can browse and learn
            if settings.living_agent_enable_social_browse:
                candidates.append(HeartbeatAction(
                    action_type=ActionType.BROWSE_SOCIAL,
                    target=random.choice(["news", "tech", "maritime"]),
                    priority=0.6,
                ))
            if settings.living_agent_enable_skill_building:
                candidates.append(HeartbeatAction(
                    action_type=ActionType.LEARN_TOPIC,
                    priority=0.5,
                ))
        elif energy > 0.3:
            # Medium energy — light tasks
            candidates.append(HeartbeatAction(
                action_type=ActionType.REFLECT,
                priority=0.7,
            ))
        else:
            # Low energy — rest
            candidates.append(HeartbeatAction(
                action_type=ActionType.REST,
                priority=0.9,
            ))

        # Daily journal (once per day, evening)
        if settings.living_agent_enable_journal and self._is_journal_time():
            candidates.append(HeartbeatAction(
                action_type=ActionType.WRITE_JOURNAL,
                priority=0.9,
            ))

        # Sort by priority descending, take top N
        candidates.sort(key=lambda a: a.priority, reverse=True)
        return candidates[:max_actions]

    async def _execute_action(self, action: HeartbeatAction, soul, engine) -> None:
        """Execute a single heartbeat action.

        Each action type delegates to the appropriate subsystem.
        Extensible: add new action types by adding cases here.
        """
        if action.action_type == ActionType.CHECK_GOALS:
            await self._action_check_goals(soul)

        elif action.action_type == ActionType.BROWSE_SOCIAL:
            await self._action_browse(action, soul, engine)

        elif action.action_type == ActionType.LEARN_TOPIC:
            await self._action_learn(soul, engine)

        elif action.action_type == ActionType.REFLECT:
            await self._action_reflect(engine)

        elif action.action_type == ActionType.WRITE_JOURNAL:
            await self._action_journal(engine)

        elif action.action_type == ActionType.REST:
            # Rest = do nothing, let natural energy recovery happen
            logger.debug("[HEARTBEAT] Resting — energy recovery in progress")

    async def _action_check_goals(self, soul) -> None:
        """Check current goals and identify priorities."""
        logger.debug(
            "[HEARTBEAT] Checking goals: %d short-term, %d long-term",
            len(soul.short_term_goals),
            len(soul.long_term_goals),
        )

    async def _action_browse(self, action, soul, engine) -> None:
        """Browse content based on interests. Delegates to social_browser."""
        from app.engine.living_agent.social_browser import get_social_browser

        browser = get_social_browser()
        items = await browser.browse_feed(
            topic=action.target,
            interests=soul.interests.primary + soul.interests.exploring,
            max_items=5,
        )

        if items:
            engine.process_event(LifeEvent(
                event_type=LifeEventType.BROWSED_CONTENT,
                description=f"Browsed {len(items)} items about {action.target}",
                importance=0.3,
            ))

            # Check for interesting discoveries
            high_relevance = [i for i in items if i.relevance_score > 0.7]
            if high_relevance:
                engine.process_event(LifeEvent(
                    event_type=LifeEventType.INTERESTING_DISCOVERY,
                    description=high_relevance[0].title[:200],
                    importance=0.7,
                ))

    async def _action_learn(self, soul, engine) -> None:
        """Learn about a topic from wants_to_learn list."""
        if not soul.interests.wants_to_learn:
            return

        topic = random.choice(soul.interests.wants_to_learn)
        logger.debug("[HEARTBEAT] Learning about: %s", topic)

        # Delegate to skill builder
        from app.engine.living_agent.skill_builder import get_skill_builder

        builder = get_skill_builder()
        learned = await builder.learn_step(topic)

        if learned:
            engine.process_event(LifeEvent(
                event_type=LifeEventType.LEARNED_SOMETHING,
                description=f"Studied: {topic}",
                importance=0.6,
            ))

    async def _action_reflect(self, engine) -> None:
        """Trigger self-reflection using the existing reflection engine."""
        engine.process_event(LifeEvent(
            event_type=LifeEventType.REFLECTION_COMPLETED,
            description="Periodic self-reflection during heartbeat",
            importance=0.5,
        ))

    async def _action_journal(self, engine) -> None:
        """Write daily journal entry."""
        from app.engine.living_agent.journal import get_journal_writer

        writer = get_journal_writer()
        entry = await writer.write_daily_entry(engine.state)

        if entry:
            engine.process_event(LifeEvent(
                event_type=LifeEventType.JOURNAL_WRITTEN,
                description="Daily journal entry written",
                importance=0.4,
            ))

    async def _save_emotional_snapshot(self, engine) -> None:
        """Persist current emotional state to database."""
        try:
            from app.repositories.emotional_state_repository import EmotionalStateRepository
            repo = EmotionalStateRepository()
            state = engine.state
            repo.save_snapshot(
                primary_mood=state.primary_mood.value,
                energy_level=state.energy_level,
                social_battery=state.social_battery,
                engagement=state.engagement,
                trigger_event="heartbeat_cycle",
                state_json=engine.to_dict(),
            )
        except Exception as e:
            logger.warning("[HEARTBEAT] Failed to save emotional snapshot: %s", e)

    def _is_active_hours(self) -> bool:
        """Check if current time is within configured active hours (UTC+7)."""
        from app.core.config import settings
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        hour = now_vn.hour
        start = settings.living_agent_active_hours_start
        end = settings.living_agent_active_hours_end

        if start <= end:
            return start <= hour < end
        else:
            # Wraps midnight (e.g., 22:00 - 06:00)
            return hour >= start or hour < end

    def _is_journal_time(self) -> bool:
        """Check if it's the right time for daily journal (evening)."""
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return 20 <= now_vn.hour <= 22


# =============================================================================
# Singleton
# =============================================================================

_scheduler_instance: Optional[HeartbeatScheduler] = None


def get_heartbeat_scheduler() -> HeartbeatScheduler:
    """Get the singleton HeartbeatScheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = HeartbeatScheduler()
    return _scheduler_instance
