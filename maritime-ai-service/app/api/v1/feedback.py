"""
Feedback API — Sprint 107
POST /api/v1/feedback — stores user thumbs up/down feedback for AI messages.

Uses direct asyncpg for storage. Table auto-created if missing.
"""
import logging

from fastapi import APIRouter, Request
from app.api.deps import RequireAuth
from app.core.rate_limit import limiter
from app.models.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

# SQL for auto-creating the feedback table
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS message_feedback (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, session_id, message_id)
);
"""

_UPSERT_SQL = """
INSERT INTO message_feedback (user_id, session_id, message_id, rating, comment)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (user_id, session_id, message_id)
DO UPDATE SET rating = EXCLUDED.rating, comment = EXCLUDED.comment, created_at = NOW()
"""

_table_ensured = False


async def _ensure_table() -> None:
    """Create feedback table if it doesn't exist (once per process)."""
    global _table_ensured
    if _table_ensured:
        return
    try:
        from app.core.config import settings
        import asyncpg
        conn = await asyncpg.connect(settings.asyncpg_url)
        try:
            await conn.execute(_CREATE_TABLE_SQL)
        finally:
            await conn.close()
        _table_ensured = True
    except Exception as e:
        logger.warning("Could not ensure feedback table: %s", e)


@router.post("", response_model=FeedbackResponse)
@limiter.limit("120/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    auth: RequireAuth,
) -> FeedbackResponse:
    """
    Submit feedback (thumbs up/down) for an AI message.

    Upserts: if the user already rated this message, the rating is updated.
    """
    user_id = auth.user_id

    try:
        await _ensure_table()

        from app.core.config import settings
        import asyncpg

        conn = await asyncpg.connect(settings.asyncpg_url)
        try:
            await conn.execute(
                _UPSERT_SQL,
                user_id,
                body.session_id,
                body.message_id,
                body.rating.value,
                body.comment,
            )
        finally:
            await conn.close()

        logger.info(
            "Feedback: user=%s msg=%s rating=%s",
            user_id, body.message_id, body.rating.value,
        )
    except Exception as e:
        # Fire-and-forget: log but don't fail the response
        logger.warning("Failed to persist feedback: %s", e)

    return FeedbackResponse(
        status="success",
        message_id=body.message_id,
        rating=body.rating,
    )
