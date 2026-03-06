"""
LangGraph Checkpointer — AsyncPostgresSaver Singleton.

Enables multi-turn conversation memory by persisting graph state
to PostgreSQL. Each session_id maps to a LangGraph thread_id.

SOTA 2026: LangGraph checkpointing with AsyncPostgresSaver.
Pattern: Singleton (mirrors app/engine/llm_pool.py).

Handles both old API (direct .setup()) and new API (async context manager)
for langgraph-checkpoint-postgres >=3.0.0.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_checkpointer = None
_context_manager = None
_initialized = False


async def get_checkpointer():
    """
    Get or create the AsyncPostgresSaver singleton.

    Uses the same PostgreSQL instance as the application.
    Handles both old API (.setup()) and new API (async context manager)
    for langgraph-checkpoint-postgres compatibility.

    Returns:
        AsyncPostgresSaver instance, or None if initialization fails.
    """
    global _checkpointer, _context_manager, _initialized

    if _initialized:
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn_string = settings.postgres_url_sync

        saver_or_cm = AsyncPostgresSaver.from_conn_string(conn_string)

        # New API (>=3.0.4): from_conn_string returns async context manager
        if hasattr(saver_or_cm, "__aenter__"):
            _context_manager = saver_or_cm
            _checkpointer = await _context_manager.__aenter__()
        else:
            # Old API: returns instance directly, call .setup()
            _checkpointer = saver_or_cm
            await _checkpointer.setup()

        _initialized = True
        logger.info("LangGraph checkpointer initialized (AsyncPostgresSaver)")
        return _checkpointer

    except ImportError:
        if settings.environment == "development":
            logger.info(
                "langgraph-checkpoint-postgres not installed in local development — "
                "graph will run without persistence"
            )
        else:
            logger.warning(
                "langgraph-checkpoint-postgres not installed — "
                "graph will run without persistence"
            )
        _initialized = True
        _checkpointer = None
        return None
    except Exception as e:
        logger.warning(
            "Checkpointer initialization failed: %s — "
            "graph will run without persistence", e
        )
        _initialized = True
        _checkpointer = None
        _context_manager = None
        return None


async def close_checkpointer():
    """Close checkpointer connection pool. Call during app shutdown."""
    global _checkpointer, _context_manager, _initialized

    if _checkpointer is not None:
        try:
            if _context_manager is not None:
                # New API: exit the context manager cleanly
                await _context_manager.__aexit__(None, None, None)
            elif hasattr(_checkpointer, "conn") and _checkpointer.conn is not None:
                # Old API: close connection directly
                await _checkpointer.conn.close()
            logger.info("Checkpointer connection closed")
        except Exception as e:
            logger.warning("Checkpointer close error: %s", e)

    _checkpointer = None
    _context_manager = None
    _initialized = False


def reset_checkpointer():
    """Reset singleton state (for testing only)."""
    global _checkpointer, _context_manager, _initialized
    _checkpointer = None
    _context_manager = None
    _initialized = False
