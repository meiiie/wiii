"""Tests for the Core-to-Living post-response continuity contract."""

from unittest.mock import MagicMock, patch

from app.services.living_continuity import (
    HOOK_LIVING_CONTINUITY,
    HOOK_LMS_INSIGHTS,
    HOOK_ROUTINE_TRACKING,
    PostResponseContinuityContext,
    schedule_post_response_continuity,
)


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


def test_schedules_routine_tracking_when_enabled():
    with patch(
        "app.services.living_continuity.schedule_routine_tracking",
        return_value=True,
    ), patch(
        "app.services.living_continuity.schedule_living_sentiment_continuity",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_lms_insight_push",
        return_value=False,
    ):
        scheduled = schedule_post_response_continuity(_make_context())

    assert scheduled == (HOOK_ROUTINE_TRACKING,)


def test_schedules_living_continuity_when_enabled():
    with patch(
        "app.services.living_continuity.schedule_routine_tracking",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_living_sentiment_continuity",
        return_value=True,
    ), patch(
        "app.services.living_continuity.schedule_lms_insight_push",
        return_value=False,
    ):
        scheduled = schedule_post_response_continuity(_make_context())

    assert scheduled == (HOOK_LIVING_CONTINUITY,)


def test_lms_insights_can_be_skipped_per_caller():
    with patch(
        "app.services.living_continuity.schedule_routine_tracking",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_living_sentiment_continuity",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_lms_insight_push",
        return_value=False,
    ):
        scheduled = schedule_post_response_continuity(
            _make_context(),
            include_lms_insights=False,
        )

    assert scheduled == ()


def test_schedules_lms_insights_when_enabled_for_caller():
    with patch(
        "app.services.living_continuity.schedule_routine_tracking",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_living_sentiment_continuity",
        return_value=False,
    ), patch(
        "app.services.living_continuity.schedule_lms_insight_push",
        return_value=True,
    ):
        scheduled = schedule_post_response_continuity(_make_context())

    assert scheduled == (HOOK_LMS_INSIGHTS,)


def test_schedules_hooks_in_stable_contract_order():
    with patch(
        "app.services.living_continuity.schedule_routine_tracking",
        return_value=True,
    ), patch(
        "app.services.living_continuity.schedule_living_sentiment_continuity",
        return_value=True,
    ), patch(
        "app.services.living_continuity.schedule_lms_insight_push",
        return_value=True,
    ):
        scheduled = schedule_post_response_continuity(_make_context())

    assert scheduled == (
        HOOK_ROUTINE_TRACKING,
        HOOK_LIVING_CONTINUITY,
        HOOK_LMS_INSIGHTS,
    )
