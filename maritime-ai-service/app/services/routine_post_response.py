"""Routine-tracking post-response scheduling helpers.

This module isolates routine tracking scheduling from the broader Living
continuity contract so Core/Living orchestration depends on a narrow helper
instead of the routine tracker implementation details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.living_continuity import PostResponseContinuityContext

logger = logging.getLogger(__name__)

__all__ = ["schedule_routine_tracking"]


def schedule_routine_tracking(
    context: "PostResponseContinuityContext",
) -> bool:
    """Schedule routine tracking when the runtime flag enables it."""
    try:
        from app.core.config import get_settings as get_runtime_settings

        runtime_settings = get_runtime_settings()
        if not getattr(
            runtime_settings,
            "living_agent_enable_routine_tracking",
            False,
        ):
            return False

        from app.engine.living_agent.routine_tracker import get_routine_tracker

        tracker = get_routine_tracker()
        asyncio.ensure_future(
            tracker.record_interaction(
                user_id=context.user_id,
                channel=context.channel,
                topic=context.domain_id,
            )
        )
        return True
    except Exception as exc:
        logger.debug("[CONTINUITY] Routine tracking schedule failed: %s", exc)
        return False
