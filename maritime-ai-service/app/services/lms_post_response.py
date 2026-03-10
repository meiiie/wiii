"""LMS-specific post-response scheduling helpers.

This module isolates LMS insight scheduling from the broader Living continuity
contract so the Core-to-Living boundary can depend on a narrow helper rather
than importing LMS integrations directly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.living_continuity import PostResponseContinuityContext

logger = logging.getLogger(__name__)

__all__ = ["schedule_lms_insight_push"]


def schedule_lms_insight_push(
    context: "PostResponseContinuityContext",
    *,
    include_lms_insights: bool,
) -> bool:
    """Schedule LMS insight push when both caller and config allow it."""
    if not include_lms_insights:
        return False
    if not getattr(settings, "enable_lms_integration", False):
        return False

    try:
        from app.integrations.lms.insight_generator import (
            analyze_and_push_insights,
        )

        asyncio.ensure_future(
            analyze_and_push_insights(
                user_id=context.user_id,
                message=context.message,
                response=context.response_text,
            )
        )
        return True
    except Exception as exc:
        logger.debug("[LMS] Post-response insight schedule failed: %s", exc)
        return False
