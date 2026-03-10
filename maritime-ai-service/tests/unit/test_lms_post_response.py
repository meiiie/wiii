"""Tests for LMS-specific post-response scheduling helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.living_continuity import PostResponseContinuityContext
from app.services.lms_post_response import schedule_lms_insight_push


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


def _close_then_raise(coroutine):
    coroutine.close()
    raise RuntimeError("boom")


def test_lms_post_response_can_be_skipped_by_caller():
    with patch(
        "app.services.lms_post_response.settings",
        MagicMock(enable_lms_integration=True),
    ), patch(
        "app.services.lms_post_response.asyncio.ensure_future",
        side_effect=_consume_scheduled_coroutine,
    ) as mock_ensure_future:
        scheduled = schedule_lms_insight_push(
            _make_context(),
            include_lms_insights=False,
        )

    assert scheduled is False
    mock_ensure_future.assert_not_called()


def test_lms_post_response_respects_feature_flag():
    with patch(
        "app.services.lms_post_response.settings",
        MagicMock(enable_lms_integration=False),
    ), patch(
        "app.services.lms_post_response.asyncio.ensure_future",
        side_effect=_consume_scheduled_coroutine,
    ) as mock_ensure_future:
        scheduled = schedule_lms_insight_push(
            _make_context(),
            include_lms_insights=True,
        )

    assert scheduled is False
    mock_ensure_future.assert_not_called()


def test_lms_post_response_schedules_insight_push_when_enabled():
    mock_analyze_and_push = AsyncMock()

    with patch(
        "app.services.lms_post_response.settings",
        MagicMock(enable_lms_integration=True),
    ), patch(
        "app.integrations.lms.insight_generator.analyze_and_push_insights",
        mock_analyze_and_push,
    ), patch(
        "app.services.lms_post_response.asyncio.ensure_future",
        side_effect=_consume_scheduled_coroutine,
    ) as mock_ensure_future:
        scheduled = schedule_lms_insight_push(
            _make_context(),
            include_lms_insights=True,
        )

    assert scheduled is True
    mock_analyze_and_push.assert_called_once_with(
        user_id="user-1",
        message="Explain Rule 5",
        response="Rule 5 is lookout.",
    )
    mock_ensure_future.assert_called_once()


def test_lms_post_response_swallows_schedule_errors():
    with patch(
        "app.services.lms_post_response.settings",
        MagicMock(enable_lms_integration=True),
    ), patch(
        "app.services.lms_post_response.asyncio.ensure_future",
        side_effect=_close_then_raise,
    ):
        scheduled = schedule_lms_insight_push(
            _make_context(),
            include_lms_insights=True,
        )

    assert scheduled is False
