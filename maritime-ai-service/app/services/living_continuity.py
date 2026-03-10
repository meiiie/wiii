"""Core-to-Living post-response continuity contract.

This module makes the boundary explicit between the synchronous response path
and the asynchronous continuity path that runs after the user-visible answer
has already been produced.

Core responsibilities end at response generation.
Living and adjacent post-response hooks are scheduled here so callers do not
 need to know about routine tracking, sentiment/emotion continuity, or LMS
 insight push internals.

See also: app/services/REQUEST_FLOW_CONTRACT.md
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.lms_post_response import schedule_lms_insight_push
from app.services.routine_post_response import schedule_routine_tracking
from app.services.sentiment_post_response import (
    schedule_living_sentiment_continuity,
)

logger = logging.getLogger(__name__)

HOOK_ROUTINE_TRACKING = "routine_tracking"
HOOK_LIVING_CONTINUITY = "living_continuity"
HOOK_LMS_INSIGHTS = "lms_insights"

__all__ = [
    "HOOK_ROUTINE_TRACKING",
    "HOOK_LIVING_CONTINUITY",
    "HOOK_LMS_INSIGHTS",
    "PostResponseContinuityContext",
    "schedule_post_response_continuity",
]


@dataclass(frozen=True)
class PostResponseContinuityContext:
    """Inputs needed after a response has been produced."""

    user_id: str
    user_role: str
    message: str
    response_text: str
    domain_id: str = ""
    organization_id: str | None = None
    channel: str = "web"


async def _analyze_and_process_sentiment(
    user_id: str,
    user_role: str,
    message: str,
    response_text: str,
    organization_id: str | None = None,
) -> None:
    """Fire-and-forget sentiment analysis for emotion and episodic memory."""
    try:
        from app.engine.living_agent.sentiment_analyzer import (
            get_sentiment_analyzer,
        )
        from app.engine.living_agent.emotion_engine import (
            TIER_CREATOR,
            TIER_KNOWN,
            get_emotion_engine,
            get_relationship_tier,
        )
        from app.engine.living_agent.models import LifeEvent, LifeEventType

        analyzer = get_sentiment_analyzer()
        result = await analyzer.analyze(message, response_text, user_id)

        engine = get_emotion_engine()
        tier = get_relationship_tier(user_id, user_role)
        event_type = getattr(
            LifeEventType,
            result.life_event_type,
            LifeEventType.USER_CONVERSATION,
        )

        if tier == TIER_CREATOR:
            engine.process_event(
                LifeEvent(
                    event_type=event_type,
                    description=result.episode_summary
                    or f"Creator {user_id}: {message[:100]}",
                    importance=result.importance,
                )
            )
        elif tier == TIER_KNOWN:
            engine.process_event(
                LifeEvent(
                    event_type=event_type,
                    description=result.episode_summary
                    or f"User {user_id}: {message[:100]}",
                    importance=result.importance * 0.6,
                )
            )
        else:
            sentiment_bucket = (
                "positive"
                if result.user_sentiment in ("positive", "grateful", "excited")
                else "negative"
                if result.user_sentiment
                in ("negative", "frustrated", "dismissive")
                else "neutral"
            )
            engine.record_interaction(user_id, sentiment_bucket)

        store_episode = (
            tier == TIER_CREATOR
            or (tier == TIER_KNOWN and result.importance >= 0.4)
            or result.importance >= 0.5
        )
        if store_episode:
            try:
                from uuid import uuid4

                from sqlalchemy import text

                from app.core.database import get_shared_session_factory

                episode = (
                    result.episode_summary
                    or f"User {user_id}: {message[:200]}"
                )
                session_factory = get_shared_session_factory()
                with session_factory() as db_session:
                    db_session.execute(
                        text(
                            """
                            INSERT INTO semantic_memories (
                                id,
                                user_id,
                                content,
                                memory_type,
                                importance,
                                metadata,
                                created_at
                            )
                            VALUES (
                                :id,
                                :user_id,
                                :content,
                                'episode',
                                :importance,
                                :metadata,
                                NOW()
                            )
                        """
                        ),
                        {
                            "id": str(uuid4()),
                            "user_id": user_id,
                            "content": episode[:2000],
                            "importance": result.importance,
                            "metadata": json.dumps(
                                {
                                    "organization_id": organization_id or "",
                                    "sentiment": result.user_sentiment,
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
                    db_session.commit()
            except Exception as episode_error:
                logger.debug(
                    "[SENTIMENT] Episodic memory storage failed: %s",
                    episode_error,
                )
    except Exception as exc:
        logger.debug("[SENTIMENT] Background analysis failed: %s", exc)


def _schedule_routine_tracking(
    context: PostResponseContinuityContext,
) -> str | None:
    """Schedule routine tracking through the routine-specific helper."""
    if not schedule_routine_tracking(context):
        return None
    return HOOK_ROUTINE_TRACKING


def _schedule_living_continuity(
    context: PostResponseContinuityContext,
) -> str | None:
    """Schedule Living continuity through the sentiment-specific helper."""
    if not schedule_living_sentiment_continuity(
        context,
        analyze_and_process_sentiment=_analyze_and_process_sentiment,
    ):
        return None
    return HOOK_LIVING_CONTINUITY


def _schedule_lms_insights(
    context: PostResponseContinuityContext,
    *,
    include_lms_insights: bool,
) -> str | None:
    """Schedule LMS insight push through the LMS-specific adapter."""
    if not schedule_lms_insight_push(
        context,
        include_lms_insights=include_lms_insights,
    ):
        return None
    return HOOK_LMS_INSIGHTS


def schedule_post_response_continuity(
    context: PostResponseContinuityContext,
    *,
    include_lms_insights: bool = True,
) -> tuple[str, ...]:
    """Schedule all asynchronous post-response hooks.

    The return value is a stable summary of which hooks were scheduled. This
    keeps the contract inspectable in tests and future diagnostics without
    affecting runtime behavior.
    """
    scheduled = tuple(
        hook_name
        for hook_name in (
            _schedule_routine_tracking(context),
            _schedule_living_continuity(context),
            _schedule_lms_insights(
                context,
                include_lms_insights=include_lms_insights,
            ),
        )
        if hook_name is not None
    )
    return scheduled
