"""
Heartbeat Scheduler — Wiii's periodic autonomy engine.

Sprint 170: "Linh Hồn Sống"
Sprint 171: "Quyền Tự Chủ" — Safety-first autonomy.

Wakes Wiii at configurable intervals to:
1. Load soul and emotional state
2. Check active goals
3. Choose and execute an action (browse, learn, reflect, journal)
4. Enforce human approval gate for external actions (Sprint 171)
5. Update emotional state based on results
6. Save audit record for every cycle (Sprint 171)
7. Log experience for long-term memory

Safety features (Sprint 171):
    - Human approval gate: external actions queued when require_human_approval=True
    - Audit logging: every heartbeat cycle persisted to wiii_heartbeat_audit
    - Daily cycle cap: max 48 cycles/day (prevent runaway)
    - Search rate limit: max 3 web searches per heartbeat cycle

Design:
    - Reuses existing ScheduledTaskExecutor pattern (asyncio poll loop)
    - Active hours support (e.g., 08:00-23:00 UTC+7)
    - Uses LOCAL MODEL (Ollama) for zero API cost
    - Feature-gated: enable_living_agent=False by default
    - Non-blocking: all errors caught, never affects user chat
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import uuid4

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

# Actions that require human approval when require_human_approval=True
# Low-risk actions (no external I/O) are always auto-approved.
_APPROVAL_REQUIRED_ACTIONS = {ActionType.BROWSE_SOCIAL, ActionType.LEARN_TOPIC}


class HeartbeatScheduler:
    """Periodic autonomy engine for Wiii's living agent.

    Runs as a background asyncio task, waking Wiii at configured intervals
    during active hours. Each heartbeat cycle:
    1. Checks if within active hours
    2. Loads current emotional state + soul
    3. Plans actions based on mood, energy, and goals
    4. Enforces approval gate for external actions (Sprint 171)
    5. Executes actions (browse, learn, reflect, journal)
    6. Updates emotional state
    7. Saves snapshot + audit record

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
        self._daily_cycle_count = 0
        self._daily_reset_date: Optional[str] = None  # "YYYY-MM-DD" in UTC+7
        self._emotion_loaded = False  # Phase 1A: Track if emotion restored from DB
        self._graduation_checked_date: Optional[str] = None  # Sprint 208: daily graduation check

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def heartbeat_count(self) -> int:
        return self._heartbeat_count

    @property
    def daily_cycle_count(self) -> int:
        return self._daily_cycle_count

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
                    # Check daily cycle cap (Sprint 171)
                    if self._check_daily_limit():
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
                        logger.warning("[HEARTBEAT] Daily cycle limit reached, skipping")
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
        from app.core.config import settings
        from app.engine.living_agent.emotion_engine import get_emotion_engine
        from app.engine.living_agent.soul_loader import get_soul

        start_time = time.monotonic()
        self._heartbeat_count += 1
        self._daily_cycle_count += 1

        result = HeartbeatResult()

        try:
            # 1. Load current state
            soul = get_soul()
            engine = get_emotion_engine()

            # Phase 1A: Restore emotion from DB on first cycle
            if not self._emotion_loaded:
                await engine.load_state_from_db()
                self._emotion_loaded = True

            # Phase 2B: Apply circadian rhythm
            engine.apply_circadian_modifier()

            # Sprint 210c: Refresh known user cache + process aggregate interactions
            if getattr(settings, "enable_living_continuity", False):
                try:
                    from app.engine.living_agent.emotion_engine import refresh_known_user_cache
                    refresh_known_user_cache()
                except Exception as e:
                    logger.debug("[HEARTBEAT] Known user cache refresh failed: %s", e)

                try:
                    agg_stats = engine.process_aggregate()
                    if agg_stats.get("total_interactions", 0) > 0:
                        logger.info(
                            "[HEARTBEAT] Aggregate: %d interactions, %d unique users, ratio=%.2f",
                            int(agg_stats["total_interactions"]),
                            int(agg_stats["unique_users"]),
                            agg_stats["positive_ratio"],
                        )
                except Exception as e:
                    logger.debug("[HEARTBEAT] Aggregate processing failed: %s", e)

            # Signal wake-up
            engine.process_event(LifeEvent(
                event_type=LifeEventType.HEARTBEAT_WAKE,
                description="Heartbeat wake-up",
                importance=0.2,
            ))

            # 2. Plan actions based on mood and energy
            actions = await self._plan_actions(engine.mood.value, engine.energy)
            if not actions:
                result.is_noop = True
                result.duration_ms = int((time.monotonic() - start_time) * 1000)
                await self._save_heartbeat_audit(result)
                return result

            # 3. Sprint 171: Separate actions into auto-approved vs needs-approval
            require_approval = settings.living_agent_require_human_approval
            auto_actions: List[HeartbeatAction] = []
            pending_actions: List[HeartbeatAction] = []

            for action in actions:
                if require_approval and action.action_type in _APPROVAL_REQUIRED_ACTIONS:
                    pending_actions.append(action)
                else:
                    auto_actions.append(action)

            # 4. Queue actions needing approval
            if pending_actions:
                await self._queue_pending_actions(pending_actions)
                logger.info(
                    "[HEARTBEAT] Queued %d actions for human approval: %s",
                    len(pending_actions),
                    [a.action_type.value for a in pending_actions],
                )

            # 5. Execute auto-approved actions
            for action in auto_actions:
                try:
                    await self._execute_action(action, soul, engine)
                    result.actions_taken.append(action)
                    # Sprint 208: Record success for autonomy graduation
                    try:
                        from app.engine.living_agent.autonomy_manager import get_autonomy_manager
                        get_autonomy_manager().record_success()
                    except Exception as e:
                        logger.debug("[HEARTBEAT] Autonomy success recording failed: %s", e)
                except Exception as e:
                    logger.warning(
                        "[HEARTBEAT] Action %s failed: %s",
                        action.action_type.value, e,
                    )

            # 6. Take emotional snapshot
            engine.take_snapshot()

            # 7. Save emotional state to DB
            await self._save_emotional_snapshot(engine)

            # Phase 1A: Persist emotion to DB for restart resilience
            await engine.save_state_to_db()

            # Sprint 213: Broadcast heartbeat status via SoulBridge
            await self._broadcast_soul_bridge(engine, result)

            # Sprint 208: Daily autonomy graduation check
            await self._check_graduation_daily()

        except Exception as e:
            result.error = str(e)
            logger.error("[HEARTBEAT] Cycle failed: %s", e, exc_info=True)

        result.duration_ms = int((time.monotonic() - start_time) * 1000)

        # 8. Sprint 171: Save audit record
        await self._save_heartbeat_audit(result)

        return result

    async def execute_approved_action(self, action_id: str) -> HeartbeatResult:
        """Execute a previously approved pending action.

        Called by the API when a human approves a queued action.

        Args:
            action_id: The ID of the pending action in wiii_pending_actions.

        Returns:
            HeartbeatResult with the action execution outcome.
        """
        from app.engine.living_agent.emotion_engine import get_emotion_engine
        from app.engine.living_agent.soul_loader import get_soul

        start_time = time.monotonic()
        result = HeartbeatResult()

        try:
            # Load pending action from DB
            action_data = await self._load_pending_action(action_id)
            if not action_data:
                result.error = f"Pending action {action_id} not found or not approved"
                return result

            soul = get_soul()
            engine = get_emotion_engine()

            action = HeartbeatAction(
                action_type=ActionType(action_data["action_type"]),
                target=action_data.get("target", ""),
                priority=action_data.get("priority", 0.5),
            )

            await self._execute_action(action, soul, engine)
            result.actions_taken.append(action)

            # Mark as completed in DB
            await self._mark_action_completed(action_id)

        except Exception as e:
            result.error = str(e)
            logger.error("[HEARTBEAT] Approved action execution failed: %s", e)

        result.duration_ms = int((time.monotonic() - start_time) * 1000)
        return result

    async def _plan_actions(self, mood: str, energy: float) -> list:
        """Plan actions for this heartbeat based on mood and energy.

        Returns list of HeartbeatAction, max limited by config.
        Enhanced with Soul AGI phases: weather, briefing, reflection, goals.
        """
        from app.core.config import settings
        max_actions = settings.living_agent_max_actions_per_heartbeat

        candidates = []

        # Always available: check goals (low energy cost)
        candidates.append(HeartbeatAction(
            action_type=ActionType.CHECK_GOALS,
            priority=0.8,
        ))

        # Phase 1B: Weather check (morning hours, 05-07 UTC+7)
        if settings.living_agent_enable_weather and self._is_morning():
            candidates.append(HeartbeatAction(
                action_type=ActionType.CHECK_WEATHER,
                priority=0.95,
            ))

        # Phase 2A: Briefing delivery
        if settings.living_agent_enable_briefing and self._is_briefing_time():
            candidates.append(HeartbeatAction(
                action_type=ActionType.SEND_BRIEFING,
                priority=0.9,
            ))

        if energy > 0.5:
            # Good energy — can browse and learn
            if settings.living_agent_enable_social_browse:
                candidates.append(HeartbeatAction(
                    action_type=ActionType.BROWSE_SOCIAL,
                    target="auto",  # Phase 3A: smart topic selection
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

        # Sprint 177: Review skills due for spaced repetition
        if settings.living_agent_enable_skill_learning:
            try:
                from app.engine.living_agent.skill_learner import get_skill_learner
                learner = get_skill_learner()
                due_skills = learner.get_skills_due_for_review()
                if due_skills:
                    candidates.append(HeartbeatAction(
                        action_type=ActionType.REVIEW_SKILL,
                        target=due_skills[0].skill_name,
                        priority=0.75,
                        metadata={"due_count": len(due_skills)},
                    ))
            except Exception as e:
                logger.debug("[HEARTBEAT] Review check failed: %s", e)

        # Daily journal (once per day, evening)
        if settings.living_agent_enable_journal and self._is_journal_time():
            candidates.append(HeartbeatAction(
                action_type=ActionType.WRITE_JOURNAL,
                priority=0.9,
            ))

        # Phase 4A: Weekly deep reflection (Sunday 20:00)
        if self._is_reflection_time():
            candidates.append(HeartbeatAction(
                action_type=ActionType.DEEP_REFLECT,
                priority=0.95,
            ))

        # Sprint 208: Proactive re-engagement — check for inactive users
        if settings.living_agent_enable_proactive_messaging and energy > 0.4:
            try:
                from app.engine.living_agent.routine_tracker import get_routine_tracker
                tracker = get_routine_tracker()
                inactive = await tracker.get_inactive_users(days=2)
                if inactive:
                    candidates.append(HeartbeatAction(
                        action_type=ActionType.SEND_BRIEFING,
                        target=f"reengage:{inactive[0]}",
                        priority=0.55,
                        metadata={"trigger": "inactive_user", "user_id": inactive[0]},
                    ))
            except Exception as e:
                logger.debug("[HEARTBEAT] Inactive user check failed: %s", e)

        # Sort by priority descending, take top N
        candidates.sort(key=lambda a: a.priority, reverse=True)
        return candidates[:max_actions]

    async def _execute_action(self, action: HeartbeatAction, soul, engine) -> None:
        """Execute a single heartbeat action with timeout protection.

        Sprint 210: 60s timeout per action prevents Ollama CPU blocking.
        Each action type delegates to the appropriate subsystem.
        Extensible: add new action types by adding cases here.
        """
        try:
            async with asyncio.timeout(60):
                await self._dispatch_action(action, soul, engine)
        except asyncio.TimeoutError:
            logger.warning("[HEARTBEAT] Action %s timed out (60s)", action.action_type.value)
        except Exception as e:
            logger.warning("[HEARTBEAT] Action %s error: %s", action.action_type.value, e)

    async def _dispatch_action(self, action: HeartbeatAction, soul, engine) -> None:
        """Dispatch action to the appropriate handler (internal, called with timeout)."""
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

        elif action.action_type == ActionType.CHECK_WEATHER:
            await self._action_check_weather()

        elif action.action_type == ActionType.SEND_BRIEFING:
            # Sprint 208: Re-engagement via ProactiveMessenger
            if action.target and action.target.startswith("reengage:"):
                await self._action_reengage(action, engine)
            else:
                await self._action_send_briefing(engine)

        elif action.action_type == ActionType.DEEP_REFLECT:
            await self._action_deep_reflect(engine)

        elif action.action_type == ActionType.REVIEW_SKILL:
            await self._action_review_skill(action, engine)

        elif action.action_type == ActionType.QUIZ_SKILL:
            await self._action_quiz_skill(action, engine)

        elif action.action_type == ActionType.REST:
            # Rest = do nothing, let natural energy recovery happen
            logger.debug("[HEARTBEAT] Resting — energy recovery in progress")

    async def _action_check_goals(self, soul) -> None:
        """Check current goals and identify priorities.

        Sprint 210: Seeds initial goals from soul definition on first call.
        """
        from app.engine.living_agent.goal_manager import get_goal_manager
        manager = get_goal_manager()

        # Seed if empty (idempotent, once per process lifetime)
        if not hasattr(self, '_goals_seeded'):
            try:
                seeded = await manager.seed_initial_goals(soul)
                if seeded:
                    logger.info("[HEARTBEAT] Seeded %d initial goals from soul", seeded)
            except Exception as e:
                logger.debug("[HEARTBEAT] Goal seeding failed: %s", e)
            self._goals_seeded = True

        try:
            goals = await manager.get_active_goals()
            logger.debug("[HEARTBEAT] Active goals: %d", len(goals))
        except Exception:
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
                # Sprint 171b: Notify user of interesting discoveries
                await self._notify_discovery(high_relevance[:3], action.target)

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
        """Trigger self-reflection using the Reflector.

        Sprint 210: Actually calls Reflector.reflect() instead of just firing event.
        """
        from app.engine.living_agent.reflector import get_reflector
        reflector = get_reflector()
        try:
            entry = await reflector.reflect()
            if entry:
                engine.process_event(LifeEvent(
                    event_type=LifeEventType.REFLECTION_COMPLETED,
                    description=f"Reflection: {entry.content[:100]}",
                    importance=0.6,
                ))
            else:
                logger.debug("[HEARTBEAT] Reflection skipped (already reflected today or no data)")
        except Exception as e:
            logger.warning("[HEARTBEAT] Reflection failed: %s", e)
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

    async def _action_check_weather(self) -> None:
        """Check weather and cache for briefing use."""
        from app.engine.living_agent.weather_service import get_weather_service

        service = get_weather_service()
        weather = await service.get_current()
        if weather:
            logger.debug("[HEARTBEAT] Weather: %s, %.1f°C", weather.city, weather.temp)

    async def _action_send_briefing(self, engine) -> None:
        """Compose and deliver a scheduled briefing."""
        from app.engine.living_agent.briefing_composer import get_briefing_composer

        composer = get_briefing_composer()
        briefing = await composer.compose_for_time()
        if briefing:
            delivered = await composer.deliver(briefing)
            if delivered:
                logger.info("[HEARTBEAT] Briefing sent to %d users", len(delivered))

    async def _action_reengage(self, action: HeartbeatAction, engine) -> None:
        """Send a re-engagement proactive message to an inactive user.

        Sprint 208: Uses ProactiveMessenger with anti-spam guardrails.
        """
        user_id = action.target.removeprefix("reengage:")
        if not user_id:
            return

        try:
            from app.engine.living_agent.proactive_messenger import get_proactive_messenger

            messenger = get_proactive_messenger()
            content = (
                "Lâu rồi không thấy bạn ghé chơi! "
                "Mình có vài điều thú vị muốn chia sẻ. Quay lại nói chuyện với mình nhé? 😊"
            )
            channel = action.metadata.get("channel", "messenger") if action.metadata else "messenger"
            sent = await messenger.send(
                user_id=user_id,
                channel=channel,
                content=content,
                trigger="inactive_reengage",
                priority=0.4,
            )
            if sent:
                logger.info("[HEARTBEAT] Re-engagement sent to %s", user_id)
        except Exception as e:
            logger.debug("[HEARTBEAT] Re-engagement failed: %s", e)

    async def _action_deep_reflect(self, engine) -> None:
        """Perform weekly deep reflection and propose goals."""
        from app.engine.living_agent.reflector import get_reflector
        from app.engine.living_agent.goal_manager import get_goal_manager
        from app.core.config import settings

        reflector = get_reflector()
        entry = await reflector.weekly_reflection()

        if entry:
            engine.process_event(LifeEvent(
                event_type=LifeEventType.REFLECTION_COMPLETED,
                description="Weekly deep reflection completed",
                importance=0.7,
            ))

            # Phase 4B: Auto-propose goals from reflection
            if settings.living_agent_enable_dynamic_goals and entry.goals_next_week:
                manager = get_goal_manager()
                await manager.propose_from_reflection(entry.goals_next_week)

            # Review stale goals
            if settings.living_agent_enable_dynamic_goals:
                manager = get_goal_manager()
                await manager.review_stale_goals()

    async def _action_review_skill(self, action: HeartbeatAction, engine) -> None:
        """Review a skill due for spaced repetition — generate and self-evaluate quiz."""
        from app.engine.living_agent.skill_learner import get_skill_learner

        skill_name = action.target
        if not skill_name:
            return

        learner = get_skill_learner()
        logger.debug("[HEARTBEAT] Reviewing skill: %s", skill_name)

        # Generate quiz
        questions = await learner.generate_quiz(skill_name)
        if not questions:
            logger.debug("[HEARTBEAT] No quiz generated for %s", skill_name)
            return

        # Self-evaluate using local LLM (simulate answering)
        answers = await self._self_answer_quiz(questions)
        result = await learner.evaluate_quiz(skill_name, questions, answers)

        if result:
            event_type = LifeEventType.QUIZ_COMPLETED
            engine.process_event(LifeEvent(
                event_type=event_type,
                description=f"Quiz: {skill_name} — {result.questions_correct}/{result.questions_total}",
                importance=0.6,
            ))

    async def _action_quiz_skill(self, action: HeartbeatAction, engine) -> None:
        """Dedicated quiz action — same as review but explicitly requested."""
        await self._action_review_skill(action, engine)

    async def _self_answer_quiz(self, questions) -> list:
        """Use local LLM to self-answer quiz questions (simulate student)."""
        from app.engine.living_agent.local_llm import get_local_llm

        llm = get_local_llm()
        answers = []
        for q in questions:
            prompt = (
                f"Câu hỏi: {q.question}\n"
                f"Đáp án: {', '.join(q.options)}\n"
                f"Trả lời CHỈ bằng đáp án đúng (ví dụ: A hoặc B hoặc C hoặc D). "
                f"Không giải thích."
            )
            answer = await llm.generate(prompt, temperature=0.1, max_tokens=10)
            answers.append(answer.strip() if answer else "")
        return answers

    def _is_morning(self) -> bool:
        """Check if it's morning hours (05-07 UTC+7)."""
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return 5 <= now_vn.hour < 7

    def _is_briefing_time(self) -> bool:
        """Check if it's time for any briefing (morning/midday/evening)."""
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        hour = now_vn.hour
        return (5 <= hour < 7) or (11 <= hour < 13) or (17 <= hour < 19)

    def _is_reflection_time(self) -> bool:
        """Check if it's time for daily reflection (21:00-22:00 UTC+7).

        Sprint 210: Changed from Sunday-only (1h/week) to daily.
        """
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return 21 <= now_vn.hour <= 22

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

    # =========================================================================
    # Sprint 171: Approval gate helpers
    # =========================================================================

    async def _queue_pending_actions(self, actions: List[HeartbeatAction]) -> None:
        """Queue actions to wiii_pending_actions table for human approval."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory
            from app.core.org_filter import get_effective_org_id

            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                for action in actions:
                    session.execute(
                        text("""
                            INSERT INTO wiii_pending_actions
                            (id, action_type, target, priority, metadata, status,
                             organization_id, created_at)
                            VALUES (:id, :action_type, :target, :priority, :metadata,
                                    'pending', :org_id, NOW())
                        """),
                        {
                            "id": str(uuid4()),
                            "action_type": action.action_type.value,
                            "target": action.target,
                            "priority": action.priority,
                            "metadata": json.dumps(action.metadata, ensure_ascii=False),
                            "org_id": effective_org_id,
                        },
                    )
                session.commit()
        except Exception as e:
            logger.warning("[HEARTBEAT] Failed to queue pending actions: %s", e)

    async def _load_pending_action(self, action_id: str) -> Optional[dict]:
        """Load a pending action from DB if it has 'approved' status, scoped by org."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory
            from app.core.org_filter import get_effective_org_id, org_where_clause

            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT action_type, target, priority, metadata
                    FROM wiii_pending_actions
                    WHERE id = :id AND status = 'approved'
                """
                params: dict = {"id": action_id}

                org_clause = org_where_clause(effective_org_id)
                if org_clause:
                    query += org_clause
                    params["org_id"] = effective_org_id

                row = session.execute(text(query), params).fetchone()
                if row:
                    return {
                        "action_type": row[0],
                        "target": row[1],
                        "priority": row[2],
                        "metadata": row[3],
                    }
        except Exception as e:
            logger.warning("[HEARTBEAT] Failed to load pending action: %s", e)
        return None

    async def _mark_action_completed(self, action_id: str) -> None:
        """Mark a pending action as completed after execution, scoped by org."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory
            from app.core.org_filter import get_effective_org_id, org_where_clause

            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    UPDATE wiii_pending_actions
                    SET status = 'completed', resolved_at = NOW()
                    WHERE id = :id
                """
                params: dict = {"id": action_id}

                org_clause = org_where_clause(effective_org_id)
                if org_clause:
                    query += org_clause
                    params["org_id"] = effective_org_id

                session.execute(text(query), params)
                session.commit()
        except Exception as e:
            logger.warning("[HEARTBEAT] Failed to mark action completed: %s", e)

    # =========================================================================
    # Sprint 171: Audit logging
    # =========================================================================

    async def _save_heartbeat_audit(self, result: HeartbeatResult) -> None:
        """Persist heartbeat cycle result to wiii_heartbeat_audit table."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory
            from app.core.org_filter import get_effective_org_id

            effective_org_id = get_effective_org_id()

            actions_json = json.dumps(
                [
                    {"action_type": a.action_type.value, "target": a.target}
                    for a in result.actions_taken
                ],
                ensure_ascii=False,
            )

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_heartbeat_audit
                        (id, cycle_number, actions_taken, insights_gained, duration_ms,
                         error, organization_id, created_at)
                        VALUES (:id, :cycle_number, :actions_taken, :insights_gained,
                                :duration_ms, :error, :org_id, NOW())
                    """),
                    {
                        "id": str(result.cycle_id),
                        "cycle_number": self._heartbeat_count,
                        "actions_taken": actions_json,
                        "insights_gained": result.insights_gained,
                        "duration_ms": result.duration_ms,
                        "error": result.error,
                        "org_id": effective_org_id,
                    },
                )
                session.commit()
        except Exception as e:
            logger.warning("[HEARTBEAT] Failed to save audit record: %s", e)

    # =========================================================================
    # Sprint 171: Rate limiting
    # =========================================================================

    def _check_daily_limit(self) -> bool:
        """Check if daily cycle limit has been reached. Resets at midnight UTC+7."""
        from app.core.config import settings

        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        today_str = now_vn.strftime("%Y-%m-%d")

        # Reset counter at midnight
        if self._daily_reset_date != today_str:
            self._daily_reset_date = today_str
            self._daily_cycle_count = 0

        return self._daily_cycle_count < settings.living_agent_max_daily_cycles

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
        """Check if it's the right time for daily journal (morning or evening).

        Sprint 210: Expanded from evening-only to morning+evening windows.
        """
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    # =========================================================================
    # Sprint 208: Autonomy graduation daily check
    # =========================================================================

    async def _check_graduation_daily(self) -> None:
        """Check autonomy graduation once per day (idempotent)."""
        try:
            now_vn = datetime.now(timezone.utc) + _VN_OFFSET
            today = now_vn.strftime("%Y-%m-%d")
            if self._graduation_checked_date == today:
                return  # Already checked today

            self._graduation_checked_date = today

            from app.core.config import settings
            if not getattr(settings, "living_agent_enable_autonomy_graduation", False):
                return

            from app.engine.living_agent.autonomy_manager import get_autonomy_manager
            manager = get_autonomy_manager()
            upgraded = await manager.check_graduation()
            if upgraded:
                logger.info("[HEARTBEAT] Autonomy graduation proposed")
        except Exception as e:
            logger.debug("[HEARTBEAT] Graduation check failed: %s", e)

    # =========================================================================
    # Sprint 213: SoulBridge status broadcast
    # =========================================================================

    async def _broadcast_soul_bridge(self, engine, result: HeartbeatResult) -> None:
        """Broadcast heartbeat status to connected peer souls via SoulBridge."""
        try:
            from app.core.config import settings
            if not getattr(settings, "enable_soul_bridge", False):
                return

            from app.engine.soul_bridge import get_soul_bridge
            bridge = get_soul_bridge()
            if not bridge.is_initialized:
                return

            payload = {
                "cycle": self._heartbeat_count,
                "mood": engine.mood.value if hasattr(engine.mood, "value") else str(engine.mood),
                "energy": engine.energy,
                "actions_taken": len(result.actions_taken),
                "duration_ms": result.duration_ms,
            }
            await bridge.broadcast_status(payload)
        except Exception as e:
            logger.debug("[HEARTBEAT] SoulBridge broadcast failed: %s", e)

    # =========================================================================
    # Sprint 171b: Messenger notification for discoveries
    # =========================================================================

    async def _notify_discovery(self, items: list, topic: str) -> None:
        """Send notification about interesting discoveries via configured channel.

        Called when browsing finds high-relevance items (score > 0.7).
        Uses NotificationDispatcher to route to Messenger/WebSocket/Telegram.
        """
        try:
            from app.core.config import settings

            channel = settings.living_agent_notification_channel
            if channel == "websocket" and not settings.enable_websocket:
                return  # No point sending WS notification if WS is disabled

            # Format discovery message in Vietnamese
            lines = [f"Wiii tìm thấy {len(items)} nội dung thú vị về {topic}:"]
            for item in items[:3]:
                title = item.title[:100] if item.title else "Không có tiêu đề"
                url = item.url or ""
                score = f" ({item.relevance_score:.0%})" if item.relevance_score else ""
                lines.append(f"• {title}{score}")
                if url:
                    lines.append(f"  {url}")
            message = "\n".join(lines)

            from app.services.notification_dispatcher import get_notification_dispatcher
            dispatcher = get_notification_dispatcher()
            result = await dispatcher.notify_user(
                user_id="wiii_owner",
                message=message,
                channel=channel,
            )

            if result.get("delivered"):
                logger.info("[HEARTBEAT] Discovery notification sent via %s", channel)
            else:
                logger.debug(
                    "[HEARTBEAT] Discovery notification not delivered: %s",
                    result.get("detail", "unknown"),
                )

        except Exception as e:
            logger.debug("[HEARTBEAT] Discovery notification failed: %s", e)


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
