"""Living sentiment post-response scheduling helpers.

This module isolates the scheduling of Living continuity sentiment work from
the broader continuity contract while preserving the sentiment analysis
implementation where legacy compatibility tests still expect it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.living_continuity import PostResponseContinuityContext

logger = logging.getLogger(__name__)

__all__ = ["schedule_living_sentiment_continuity"]


def schedule_living_sentiment_continuity(
    context: "PostResponseContinuityContext",
    *,
    analyze_and_process_sentiment: Callable[..., Awaitable[None]],
) -> bool:
    """Schedule Living continuity sentiment processing when enabled."""
    if not getattr(settings, "enable_living_continuity", False):
        return False

    try:
        asyncio.ensure_future(
            analyze_and_process_sentiment(
                user_id=context.user_id,
                user_role=context.user_role,
                message=context.message,
                response_text=context.response_text,
                organization_id=context.organization_id,
            )
        )
        return True
    except Exception as exc:
        logger.debug("[CONTINUITY] Living sentiment schedule failed: %s", exc)
        return False
