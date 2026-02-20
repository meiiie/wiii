"""
Scheduler Repository — Proactive agent task scheduling

Sprint 19: Virtual Agent-per-User Architecture
Stores and manages user-scheduled tasks (reminders, quizzes, reviews).

The agent can schedule tasks via LangChain tools, and a periodic executor
picks them up and runs them at the scheduled time.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


class SchedulerRepository:
    """
    Repository for scheduled_tasks table CRUD operations.

    Uses the shared database engine (singleton pattern).
    All operations include ownership checks.
    """

    TABLE_NAME = "scheduled_tasks"

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
                logger.error("SchedulerRepository init failed: %s", e)

    def create_task(
        self,
        user_id: str,
        description: str,
        schedule_type: str = "once",
        schedule_expr: str = "",
        next_run: Optional[datetime] = None,
        domain_id: str = "maritime",
        max_runs: Optional[int] = None,
        channel: str = "websocket",
        extra_data: Optional[dict] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a new scheduled task.

        Args:
            user_id: Owner user ID
            description: What the agent should do (natural language prompt)
            schedule_type: "once", "recurring", or "cron"
            schedule_expr: ISO datetime (once), interval (recurring), or cron expression
            next_run: When to run next (defaults to schedule_expr for 'once')
            domain_id: Domain context for the task
            max_runs: Maximum number of executions (None = unlimited for recurring)
            channel: Notification channel ("websocket", "telegram")
            extra_data: Additional task metadata

        Returns:
            Task ID string, or None on failure
        """
        self._ensure_initialized()
        if not self._session_factory:
            return None

        task_id = str(uuid.uuid4())

        # Parse next_run from schedule_expr if not provided
        if next_run is None and schedule_type == "once" and schedule_expr:
            try:
                next_run = datetime.fromisoformat(schedule_expr)
            except ValueError:
                logger.warning("Invalid schedule_expr for 'once': %s", schedule_expr)
                return None

        # Sprint 160b: Resolve org_id for multi-tenant isolation
        from app.core.org_filter import get_effective_org_id
        eff_org_id = organization_id or get_effective_org_id()

        try:
            with self._session_factory() as session:
                session.execute(
                    text(
                        f"INSERT INTO {self.TABLE_NAME} "
                        f"(id, user_id, domain_id, description, schedule_type, "
                        f"schedule_expr, next_run, max_runs, channel, extra_data, "
                        f"organization_id) "
                        f"VALUES (:id, :user_id, :domain_id, :description, "
                        f":schedule_type, :schedule_expr, :next_run, :max_runs, "
                        f":channel, CAST(:extra AS jsonb), :org_id)"
                    ),
                    {
                        "id": task_id,
                        "user_id": user_id,
                        "domain_id": domain_id,
                        "description": description,
                        "schedule_type": schedule_type,
                        "schedule_expr": schedule_expr,
                        "next_run": next_run,
                        "max_runs": max_runs,
                        "channel": channel,
                        "extra": json.dumps(extra_data or {}),
                        "org_id": eff_org_id,
                    },
                )
                session.commit()

            logger.info("[SCHEDULER] Created task %s for user %s: %s", task_id, user_id, description[:50])
            return task_id

        except Exception as e:
            logger.error("Create scheduled task failed: %s", e)
            return None

    def list_tasks(
        self,
        user_id: str,
        status: str = "active",
        limit: int = 50,
    ) -> list[dict]:
        """
        List scheduled tasks for a user.

        Args:
            user_id: Owner user ID
            status: Filter by status ("active", "completed", "cancelled")
            limit: Max tasks to return

        Returns:
            List of task dicts
        """
        self._ensure_initialized()
        if not self._session_factory:
            return []

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                params: dict = {"user_id": user_id, "status": status, "limit": limit}
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(
                    text(
                        f"SELECT id, user_id, domain_id, description, "
                        f"schedule_type, schedule_expr, next_run, last_run, "
                        f"run_count, max_runs, status, channel, created_at, "
                        f"extra_data "
                        f"FROM {self.TABLE_NAME} "
                        f"WHERE user_id = :user_id AND status = :status"
                        f"{org_filter} "
                        f"ORDER BY COALESCE(next_run, created_at) ASC "
                        f"LIMIT :limit"
                    ),
                    params,
                ).fetchall()

                return [self._row_to_dict(row) for row in result]

        except Exception as e:
            logger.error("List scheduled tasks failed: %s", e)
            return []

    def cancel_task(self, task_id: str, user_id: str) -> bool:
        """
        Cancel a scheduled task with ownership check.

        Args:
            task_id: Task ID to cancel
            user_id: User ID for ownership verification

        Returns:
            True if cancelled, False if not found or not owned
        """
        self._ensure_initialized()
        if not self._session_factory:
            return False

        # Sprint 160b: Org-scoped filtering
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                params: dict = {"task_id": task_id, "user_id": user_id}
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(
                    text(
                        f"UPDATE {self.TABLE_NAME} "
                        f"SET status = 'cancelled' "
                        f"WHERE id = :task_id AND user_id = :user_id "
                        f"AND status = 'active'"
                        f"{org_filter}"
                    ),
                    params,
                )
                session.commit()
                return result.rowcount > 0

        except Exception as e:
            logger.error("Cancel scheduled task failed: %s", e)
            return False

    def get_due_tasks(self, limit: int = 100) -> list[dict]:
        """
        Get tasks that are due for execution.

        Called by the periodic executor every minute.
        Skips tasks that have failed 3+ times (failure_count >= 3).

        Returns:
            List of due task dicts
        """
        self._ensure_initialized()
        if not self._session_factory:
            return []

        now = datetime.now(timezone.utc)

        # Sprint 160b: Org-scoped filtering.
        # Note: Background executor may have no ContextVar → eff_org_id=None → no filter
        # (correct: worker processes tasks for ALL orgs).
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                params: dict = {"now": now, "limit": limit}
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(
                    text(
                        f"SELECT id, user_id, domain_id, description, "
                        f"schedule_type, schedule_expr, next_run, last_run, "
                        f"run_count, max_runs, status, channel, created_at, "
                        f"extra_data "
                        f"FROM {self.TABLE_NAME} "
                        f"WHERE status = 'active' "
                        f"AND next_run IS NOT NULL "
                        f"AND next_run <= :now "
                        f"AND COALESCE(failure_count, 0) < 3"
                        f"{org_filter} "
                        f"ORDER BY next_run ASC "
                        f"LIMIT :limit"
                    ),
                    params,
                ).fetchall()

                return [self._row_to_dict(row) for row in result]

        except Exception as e:
            logger.error("Get due tasks failed: %s", e)
            return []

    def mark_failed(self, task_id: str, error: str = "") -> bool:
        """
        Increment failure_count for a task. If >= 3, set status='failed'.

        Sprint 22: Prevents infinite retry for tasks that consistently fail.

        Args:
            task_id: Task ID
            error: Error message for debugging

        Returns:
            True if updated
        """
        self._ensure_initialized()
        if not self._session_factory:
            return False

        now = datetime.now(timezone.utc)

        try:
            with self._session_factory() as session:
                # Increment failure_count and record last error
                session.execute(
                    text(
                        f"UPDATE {self.TABLE_NAME} SET "
                        f"failure_count = COALESCE(failure_count, 0) + 1, "
                        f"last_error = :error, "
                        f"last_run = :now "
                        f"WHERE id = :task_id"
                    ),
                    {"task_id": task_id, "error": error, "now": now},
                )

                # If failure_count >= 3, mark as failed
                session.execute(
                    text(
                        f"UPDATE {self.TABLE_NAME} SET status = 'failed' "
                        f"WHERE id = :task_id "
                        f"AND COALESCE(failure_count, 0) >= 3"
                    ),
                    {"task_id": task_id},
                )

                session.commit()
                logger.warning(
                    f"[SCHEDULER] Task {task_id[:8]} failure recorded: {error}"
                )
                return True

        except Exception as e:
            logger.error("Mark task failed error: %s", e)
            return False

    def mark_executed(self, task_id: str, next_run: Optional[datetime] = None) -> bool:
        """
        Mark a task as executed, update run_count, and set next_run.

        For 'once' tasks, sets status to 'completed'.
        For recurring tasks, updates next_run and increments run_count.

        Args:
            task_id: Task ID
            next_run: Next execution time (None = mark as completed)

        Returns:
            True if updated
        """
        self._ensure_initialized()
        if not self._session_factory:
            return False

        now = datetime.now(timezone.utc)

        try:
            with self._session_factory() as session:
                if next_run:
                    # Recurring: update next_run, increment count
                    session.execute(
                        text(
                            f"UPDATE {self.TABLE_NAME} SET "
                            f"last_run = :now, "
                            f"run_count = run_count + 1, "
                            f"next_run = :next_run "
                            f"WHERE id = :task_id"
                        ),
                        {"task_id": task_id, "now": now, "next_run": next_run},
                    )
                else:
                    # One-time: mark completed
                    session.execute(
                        text(
                            f"UPDATE {self.TABLE_NAME} SET "
                            f"last_run = :now, "
                            f"run_count = run_count + 1, "
                            f"status = 'completed' "
                            f"WHERE id = :task_id"
                        ),
                        {"task_id": task_id, "now": now},
                    )

                # Check max_runs limit
                session.execute(
                    text(
                        f"UPDATE {self.TABLE_NAME} SET status = 'completed' "
                        f"WHERE id = :task_id AND max_runs IS NOT NULL "
                        f"AND run_count >= max_runs"
                    ),
                    {"task_id": task_id},
                )

                session.commit()
                return True

        except Exception as e:
            logger.error("Mark task executed failed: %s", e)
            return False

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a database row to a dict."""
        extra_raw = row[13] if len(row) > 13 else None
        if isinstance(extra_raw, str):
            try:
                extra_data = json.loads(extra_raw)
            except (json.JSONDecodeError, TypeError):
                extra_data = {}
        elif isinstance(extra_raw, dict):
            extra_data = extra_raw
        else:
            extra_data = {}

        return {
            "id": row[0],
            "user_id": row[1],
            "domain_id": row[2],
            "description": row[3],
            "schedule_type": row[4],
            "schedule_expr": row[5],
            "next_run": str(row[6]) if row[6] else None,
            "last_run": str(row[7]) if row[7] else None,
            "run_count": row[8],
            "max_runs": row[9],
            "status": row[10],
            "channel": row[11],
            "created_at": str(row[12]) if row[12] else None,
            "extra_data": extra_data,
        }


# =============================================================================
# Singleton
# =============================================================================

_scheduler_repo: Optional[SchedulerRepository] = None


def get_scheduler_repository() -> SchedulerRepository:
    """Get or create the SchedulerRepository singleton."""
    global _scheduler_repo
    if _scheduler_repo is None:
        _scheduler_repo = SchedulerRepository()
    return _scheduler_repo
