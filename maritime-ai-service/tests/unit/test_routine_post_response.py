"""Tests for the routine-tracking post-response scheduling helper."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.living_continuity import PostResponseContinuityContext
from app.services.routine_post_response import schedule_routine_tracking


def _make_context() -> PostResponseContinuityContext:
    return PostResponseContinuityContext(
        user_id="user-1",
        user_role="student",
        message="Explain Rule 5",
        response_text="Rule 5 is lookout.",
        domain_id="maritime",
        organization_id="org-1",
        channel="web",
    )


def _consume_scheduled_coroutine(coroutine):
    coroutine.close()
    return MagicMock()


def test_skips_routine_tracking_when_flag_disabled():
    runtime_settings = MagicMock(living_agent_enable_routine_tracking=False)

    with patch(
        "app.core.config.get_settings",
        return_value=runtime_settings,
    ), patch(
        "app.services.routine_post_response.asyncio.ensure_future",
        side_effect=_consume_scheduled_coroutine,
    ) as mock_ensure_future:
        scheduled = schedule_routine_tracking(_make_context())

    assert scheduled is False
    mock_ensure_future.assert_not_called()


def test_schedules_routine_tracking_when_flag_enabled():
    mock_tracker = MagicMock()
    mock_tracker.record_interaction = AsyncMock()
    runtime_settings = MagicMock(living_agent_enable_routine_tracking=True)

    with patch(
        "app.core.config.get_settings",
        return_value=runtime_settings,
    ), patch(
        "app.engine.living_agent.routine_tracker.get_routine_tracker",
        return_value=mock_tracker,
    ), patch(
        "app.services.routine_post_response.asyncio.ensure_future",
        side_effect=_consume_scheduled_coroutine,
    ) as mock_ensure_future:
        scheduled = schedule_routine_tracking(_make_context())

    assert scheduled is True
    mock_tracker.record_interaction.assert_called_once_with(
        user_id="user-1",
        channel="web",
        topic="maritime",
    )
    mock_ensure_future.assert_called_once()


def test_swallows_routine_tracking_scheduling_errors():
    mock_tracker = MagicMock()
    mock_tracker.record_interaction = AsyncMock()
    runtime_settings = MagicMock(living_agent_enable_routine_tracking=True)

    def _raise_after_closing(coroutine):
        coroutine.close()
        raise RuntimeError("scheduler offline")

    with patch(
        "app.core.config.get_settings",
        return_value=runtime_settings,
    ), patch(
        "app.engine.living_agent.routine_tracker.get_routine_tracker",
        return_value=mock_tracker,
    ), patch(
        "app.services.routine_post_response.asyncio.ensure_future",
        side_effect=_raise_after_closing,
    ):
        scheduled = schedule_routine_tracking(_make_context())

    assert scheduled is False
    mock_tracker.record_interaction.assert_called_once_with(
        user_id="user-1",
        channel="web",
        topic="maritime",
    )
