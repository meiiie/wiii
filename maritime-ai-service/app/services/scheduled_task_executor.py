"""
Scheduled Task Executor — Periodic poll loop for proactive agent tasks.

Sprint 20: Proactive Agent Activation.
Polls the scheduled_tasks table at configured intervals, executes due tasks
(notification or agent-invoke mode), and delivers results via NotificationDispatcher.

Uses asyncio.Task — no external worker dependencies (Taskiq/Celery).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ScheduledTaskExecutor:
    """
    Periodic executor for scheduled tasks.

    Polls get_due_tasks() every scheduler_poll_interval seconds,
    executes tasks concurrently (up to scheduler_max_concurrent),
    and delivers results to users via NotificationDispatcher.
    """

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the periodic poll loop as a background asyncio task."""
        if self._running:
            logger.warning("[EXECUTOR] Already running, skipping start")
            return

        self._shutdown_event.clear()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("[EXECUTOR] Scheduled task executor started")

    async def _poll_loop(self) -> None:
        """Main loop: poll for due tasks, execute, then wait for interval."""
        from app.core.config import settings

        while not self._shutdown_event.is_set():
            try:
                await self._execute_due_tasks()
            except Exception as e:
                logger.error("[EXECUTOR] Poll error: %s", e, exc_info=True)

            # Wait for interval or shutdown signal
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=settings.scheduler_poll_interval,
                )
                break  # Shutdown signalled
            except asyncio.TimeoutError:
                pass  # Interval elapsed, continue polling

        self._running = False
        logger.info("[EXECUTOR] Poll loop exited")

    async def _execute_due_tasks(self) -> None:
        """Fetch and execute all due tasks up to max_concurrent."""
        from app.core.config import settings
        from app.repositories.scheduler_repository import get_scheduler_repository
        from app.services.notification_dispatcher import get_notification_dispatcher

        repo = get_scheduler_repository()
        dispatcher = get_notification_dispatcher()

        due_tasks = repo.get_due_tasks(limit=settings.scheduler_max_concurrent)
        if not due_tasks:
            return

        logger.info("[EXECUTOR] Found %d due task(s)", len(due_tasks))

        for task in due_tasks:
            task_id_short = task["id"][:8] if task.get("id") else "unknown"
            try:
                result = await self._execute_single_task(task)

                # Notify user
                delivery = await dispatcher.notify_task_result(task, result)
                logger.info(
                    "[EXECUTOR] Task %s completed: "
                    "mode=%s, delivered=%s",
                    task_id_short, result.get('mode'), delivery.get('delivered'),
                )

                # Mark executed and calculate next_run for recurring
                next_run = (
                    self._calculate_next_run(task)
                    if task.get("schedule_type") != "once"
                    else None
                )
                repo.mark_executed(task["id"], next_run=next_run)

            except asyncio.TimeoutError:
                logger.error("[EXECUTOR] Task %s timed out", task_id_short)
                repo.mark_failed(task["id"], "timeout")
            except Exception as e:
                logger.error(
                    "[EXECUTOR] Task %s execution failed: %s",
                    task_id_short, e,
                    exc_info=True,
                )
                repo.mark_failed(task["id"], str(e)[:200])

    async def _execute_single_task(self, task: dict) -> dict:
        """
        Execute a single scheduled task.

        Two modes:
        - agent_invoke: Run through the multi-agent graph
        - notification (default): Just send the description as a reminder
        """
        from app.core.config import settings

        extra = task.get("extra_data") or {}

        if extra.get("agent_invoke"):
            # Agent mode: invoke the WiiiRunner-backed multi-agent runtime.
            from app.engine.multi_agent.runtime import run_wiii_turn
            from app.engine.multi_agent.runtime_contracts import (
                WiiiRunContext,
                WiiiTurnRequest,
            )

            turn_result = await asyncio.wait_for(
                run_wiii_turn(
                    WiiiTurnRequest(
                        query=task["description"],
                        run_context=WiiiRunContext(
                            user_id=task["user_id"],
                            session_id=f"scheduled_{task['id'][:8]}",
                            domain_id=task.get("domain_id", "maritime"),
                        ),
                    )
                ),
                timeout=settings.scheduler_agent_timeout,
            )
            result = turn_result.payload
            return {
                "mode": "agent",
                "response": result.get("response", ""),
            }
        else:
            # Notification mode (default): send description as reminder
            return {
                "mode": "notification",
                "response": task["description"],
            }

    @staticmethod
    def _calculate_next_run(task: dict) -> Optional[datetime]:
        """
        Calculate next_run for recurring tasks.

        For "recurring": parse interval from schedule_expr (e.g., "1h", "30m", "1d"),
        add to current time.
        For "cron": not yet supported, returns None (marks as completed).
        """
        schedule_type = task.get("schedule_type", "once")
        schedule_expr = task.get("schedule_expr", "")

        if schedule_type == "recurring" and schedule_expr:
            delta = _parse_interval(schedule_expr)
            if delta:
                return datetime.now(timezone.utc) + delta

        # Unknown type or unparseable expr → complete the task
        return None

    async def shutdown(self, timeout: float = 10) -> None:
        """Signal shutdown and wait for the poll loop to finish."""
        if not self._running:
            return

        logger.info("[EXECUTOR] Shutdown requested")
        self._shutdown_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
                logger.warning("[EXECUTOR] Forced cancel after timeout")

        self._running = False
        logger.info("[EXECUTOR] Shutdown complete")


def _parse_interval(expr: str) -> Optional[timedelta]:
    """
    Parse a human-readable interval string into a timedelta.

    Supported formats: "30m", "1h", "2d", "90s", "1h30m"
    """
    import re

    total = timedelta()
    pattern = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
    matches = pattern.findall(expr)

    if not matches:
        return None

    for value, unit in matches:
        v = int(value)
        if unit in ("s", "S"):
            total += timedelta(seconds=v)
        elif unit in ("m", "M"):
            total += timedelta(minutes=v)
        elif unit in ("h", "H"):
            total += timedelta(hours=v)
        elif unit in ("d", "D"):
            total += timedelta(days=v)

    return total if total > timedelta() else None


# =============================================================================
# Singleton
# =============================================================================

_executor: Optional[ScheduledTaskExecutor] = None


def get_scheduled_task_executor() -> ScheduledTaskExecutor:
    """Get or create the ScheduledTaskExecutor singleton."""
    global _executor
    if _executor is None:
        _executor = ScheduledTaskExecutor()
    return _executor
