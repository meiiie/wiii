"""
Tests for ScheduledTaskExecutor — Periodic poll loop for proactive agent tasks.

Sprint 20: Proactive Agent Activation.

Verifies:
- Poll loop starts and stops
- Executes due tasks (notification mode)
- Executes due tasks (agent mode with mock)
- Handles execution errors gracefully
- Respects max_concurrent limit
- Calculates next_run for recurring tasks
- Graceful shutdown with timeout
- Interval parsing (_parse_interval)
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduled_task_executor import (
    ScheduledTaskExecutor,
    _parse_interval,
    get_scheduled_task_executor,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def executor():
    """Fresh ScheduledTaskExecutor instance."""
    return ScheduledTaskExecutor()


@pytest.fixture
def sample_task_once():
    """Sample one-time scheduled task."""
    return {
        "id": "task-once-12345678",
        "user_id": "user-1",
        "domain_id": "maritime",
        "description": "Nhắc ôn tập COLREGs Rule 13",
        "schedule_type": "once",
        "schedule_expr": "",
        "next_run": str(datetime.now(timezone.utc) - timedelta(minutes=1)),
        "last_run": None,
        "run_count": 0,
        "max_runs": None,
        "status": "active",
        "channel": "websocket",
        "created_at": str(datetime.now(timezone.utc)),
        "extra_data": {},
    }


@pytest.fixture
def sample_task_agent():
    """Sample agent-invoke scheduled task."""
    return {
        "id": "task-agent-87654321",
        "user_id": "user-2",
        "domain_id": "maritime",
        "description": "Quiz 5 câu hỏi về MARPOL Annex I",
        "schedule_type": "once",
        "schedule_expr": "",
        "next_run": str(datetime.now(timezone.utc) - timedelta(minutes=1)),
        "last_run": None,
        "run_count": 0,
        "max_runs": None,
        "status": "active",
        "channel": "websocket",
        "created_at": str(datetime.now(timezone.utc)),
        "extra_data": {"agent_invoke": True},
    }


@pytest.fixture
def sample_task_recurring():
    """Sample recurring scheduled task."""
    return {
        "id": "task-recur-11223344",
        "user_id": "user-1",
        "domain_id": "maritime",
        "description": "Nhắc ôn tập hàng ngày",
        "schedule_type": "recurring",
        "schedule_expr": "1d",
        "next_run": str(datetime.now(timezone.utc) - timedelta(minutes=1)),
        "last_run": None,
        "run_count": 0,
        "max_runs": 7,
        "status": "active",
        "channel": "websocket",
        "created_at": str(datetime.now(timezone.utc)),
        "extra_data": {},
    }


# =============================================================================
# _parse_interval
# =============================================================================

class TestParseInterval:

    def test_parse_seconds(self):
        assert _parse_interval("30s") == timedelta(seconds=30)

    def test_parse_minutes(self):
        assert _parse_interval("15m") == timedelta(minutes=15)

    def test_parse_hours(self):
        assert _parse_interval("2h") == timedelta(hours=2)

    def test_parse_days(self):
        assert _parse_interval("1d") == timedelta(days=1)

    def test_parse_combined(self):
        assert _parse_interval("1h30m") == timedelta(hours=1, minutes=30)

    def test_parse_invalid(self):
        assert _parse_interval("invalid") is None

    def test_parse_empty(self):
        assert _parse_interval("") is None

    def test_parse_zero(self):
        """Zero values return None (no timedelta)."""
        assert _parse_interval("0m") is None


# =============================================================================
# Start / Stop
# =============================================================================

class TestStartStop:

    @pytest.mark.asyncio
    async def test_start_sets_running(self, executor):
        """start() sets is_running and creates background task."""
        mock_settings = MagicMock()
        mock_settings.scheduler_poll_interval = 1

        with patch("app.core.config.settings", mock_settings):
            await executor.start()
            assert executor.is_running is True

            await executor.shutdown(timeout=2)
            assert executor.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, executor):
        """Calling start() twice doesn't create duplicate tasks."""
        mock_settings = MagicMock()
        mock_settings.scheduler_poll_interval = 1

        with patch("app.core.config.settings", mock_settings):
            await executor.start()
            task1 = executor._task

            await executor.start()  # Should be a no-op
            task2 = executor._task

            assert task1 is task2
            await executor.shutdown(timeout=2)

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self, executor):
        """Shutdown on non-running executor is a no-op."""
        await executor.shutdown()
        assert executor.is_running is False


# =============================================================================
# Execute notification mode
# =============================================================================

class TestExecuteNotificationMode:

    @pytest.mark.asyncio
    async def test_execute_notification_task(self, executor, sample_task_once):
        """Notification mode returns description as response."""
        result = await executor._execute_single_task(sample_task_once)

        assert result["mode"] == "notification"
        assert result["response"] == sample_task_once["description"]

    @pytest.mark.asyncio
    async def test_execute_due_tasks_notification(self, executor, sample_task_once):
        """Full pipeline: fetch → execute → notify → mark."""
        mock_repo = MagicMock()
        mock_repo.get_due_tasks.return_value = [sample_task_once]
        mock_repo.mark_executed.return_value = True

        mock_dispatcher = MagicMock()
        mock_dispatcher.notify_task_result = AsyncMock(
            return_value={"delivered": True, "channel": "websocket", "detail": "ok"}
        )

        mock_settings = MagicMock()
        mock_settings.scheduler_max_concurrent = 5

        with patch("app.core.config.settings", mock_settings), \
             patch("app.repositories.scheduler_repository.get_scheduler_repository", return_value=mock_repo), \
             patch("app.services.notification_dispatcher.get_notification_dispatcher", return_value=mock_dispatcher):
            await executor._execute_due_tasks()

        mock_repo.get_due_tasks.assert_called_once_with(limit=5)
        mock_dispatcher.notify_task_result.assert_called_once()
        # "once" task → next_run=None
        mock_repo.mark_executed.assert_called_once_with(
            sample_task_once["id"], next_run=None
        )


# =============================================================================
# Execute agent mode
# =============================================================================

class TestExecuteAgentMode:

    @pytest.mark.asyncio
    async def test_execute_agent_task(self, executor, sample_task_agent):
        """Agent mode calls process_with_multi_agent."""
        mock_settings = MagicMock()
        mock_settings.scheduler_agent_timeout = 30

        mock_result = {"response": "Đây là 5 câu hỏi MARPOL..."}

        with patch("app.core.config.settings", mock_settings), \
             patch(
                 "app.engine.multi_agent.graph.process_with_multi_agent",
                 new_callable=AsyncMock,
                 return_value=mock_result,
             ):
            result = await executor._execute_single_task(sample_task_agent)

        assert result["mode"] == "agent"
        assert "MARPOL" in result["response"]

    @pytest.mark.asyncio
    async def test_agent_task_timeout(self, executor, sample_task_agent):
        """Agent invocation timeout raises TimeoutError."""
        mock_settings = MagicMock()
        mock_settings.scheduler_agent_timeout = 0.01  # Very short

        async def slow_process(**kwargs):
            await asyncio.sleep(10)
            return {}

        with patch("app.core.config.settings", mock_settings), \
             patch(
                 "app.engine.multi_agent.graph.process_with_multi_agent",
                 side_effect=slow_process,
             ):
            with pytest.raises(asyncio.TimeoutError):
                await executor._execute_single_task(sample_task_agent)


# =============================================================================
# Error handling
# =============================================================================

class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_execution_error_doesnt_crash(self, executor):
        """Error in one task doesn't prevent processing others."""
        task_good = {
            "id": "good-task-00000000",
            "user_id": "user-1",
            "description": "Good task",
            "schedule_type": "once",
            "channel": "websocket",
            "extra_data": {},
        }
        task_bad = {
            "id": "bad-task-11111111",
            "user_id": "user-2",
            "description": "Bad task",
            "schedule_type": "once",
            "channel": "websocket",
            "extra_data": {"agent_invoke": True},
        }

        mock_repo = MagicMock()
        mock_repo.get_due_tasks.return_value = [task_bad, task_good]
        mock_repo.mark_executed.return_value = True

        mock_dispatcher = MagicMock()
        mock_dispatcher.notify_task_result = AsyncMock(
            return_value={"delivered": True, "channel": "websocket", "detail": "ok"}
        )

        mock_settings = MagicMock()
        mock_settings.scheduler_max_concurrent = 10
        mock_settings.scheduler_agent_timeout = 1

        with patch("app.core.config.settings", mock_settings), \
             patch("app.repositories.scheduler_repository.get_scheduler_repository", return_value=mock_repo), \
             patch("app.services.notification_dispatcher.get_notification_dispatcher", return_value=mock_dispatcher), \
             patch(
                 "app.engine.multi_agent.graph.process_with_multi_agent",
                 side_effect=RuntimeError("LLM unavailable"),
             ):
            # Should not raise
            await executor._execute_due_tasks()

        # Good task should still have been processed
        assert mock_repo.mark_executed.call_count == 1  # Only good task
        assert mock_dispatcher.notify_task_result.call_count == 1

    @pytest.mark.asyncio
    async def test_no_due_tasks(self, executor):
        """No due tasks = no-op."""
        mock_repo = MagicMock()
        mock_repo.get_due_tasks.return_value = []

        mock_settings = MagicMock()
        mock_settings.scheduler_max_concurrent = 5

        with patch("app.core.config.settings", mock_settings), \
             patch("app.repositories.scheduler_repository.get_scheduler_repository", return_value=mock_repo):
            await executor._execute_due_tasks()

        mock_repo.get_due_tasks.assert_called_once()


# =============================================================================
# Recurring task — next_run calculation
# =============================================================================

class TestRecurringNextRun:

    def test_calculate_next_run_once(self, executor, sample_task_once):
        """'once' task returns None (mark as completed)."""
        result = executor._calculate_next_run(sample_task_once)
        assert result is None

    def test_calculate_next_run_recurring(self, executor, sample_task_recurring):
        """Recurring task returns now + interval."""
        before = datetime.now(timezone.utc)
        result = executor._calculate_next_run(sample_task_recurring)
        after = datetime.now(timezone.utc)

        assert result is not None
        # Should be approximately now + 1 day
        expected = before + timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_calculate_next_run_invalid_expr(self, executor):
        """Invalid schedule_expr returns None."""
        task = {"schedule_type": "recurring", "schedule_expr": "invalid"}
        result = executor._calculate_next_run(task)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_recurring_sets_next_run(self, executor, sample_task_recurring):
        """Recurring task's mark_executed is called with a future next_run."""
        mock_repo = MagicMock()
        mock_repo.get_due_tasks.return_value = [sample_task_recurring]
        mock_repo.mark_executed.return_value = True

        mock_dispatcher = MagicMock()
        mock_dispatcher.notify_task_result = AsyncMock(
            return_value={"delivered": True, "channel": "websocket", "detail": "ok"}
        )

        mock_settings = MagicMock()
        mock_settings.scheduler_max_concurrent = 5

        with patch("app.core.config.settings", mock_settings), \
             patch("app.repositories.scheduler_repository.get_scheduler_repository", return_value=mock_repo), \
             patch("app.services.notification_dispatcher.get_notification_dispatcher", return_value=mock_dispatcher):
            await executor._execute_due_tasks()

        # Verify mark_executed was called with a next_run datetime
        call_args = mock_repo.mark_executed.call_args
        assert call_args[0][0] == sample_task_recurring["id"]
        next_run = call_args[1]["next_run"]
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:

    def test_get_scheduled_task_executor_singleton(self):
        """Singleton returns same instance."""
        import app.services.scheduled_task_executor as mod
        mod._executor = None  # Reset

        e1 = get_scheduled_task_executor()
        e2 = get_scheduled_task_executor()
        assert e1 is e2

        mod._executor = None  # Clean up
