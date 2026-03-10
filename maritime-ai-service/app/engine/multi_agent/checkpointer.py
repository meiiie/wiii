"""
LangGraph checkpointer helpers.

Uses a request-scoped AsyncPostgresSaver so concurrent graph requests do not
share the same psycopg async connection.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_setup_complete = False


async def _ensure_setup(checkpointer: Any) -> None:
    """Run LangGraph checkpoint migrations once per process."""
    global _setup_complete
    if _setup_complete or checkpointer is None or not hasattr(checkpointer, "setup"):
        return
    await checkpointer.setup()
    _setup_complete = True


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[Any | None]:
    """
    Open a request-scoped AsyncPostgresSaver.

    AsyncPostgresSaver.from_conn_string() yields a saver backed by a single
    AsyncConnection, so reusing one singleton saver across concurrent requests
    breaks with psycopg's "another command is already in progress" error.
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn_string = settings.postgres_url_sync
        saver_or_cm = AsyncPostgresSaver.from_conn_string(conn_string)

        if hasattr(saver_or_cm, "__aenter__"):
            async with saver_or_cm as checkpointer:
                await _ensure_setup(checkpointer)
                yield checkpointer
            return

        checkpointer = saver_or_cm
        await _ensure_setup(checkpointer)
        try:
            yield checkpointer
        finally:
            if hasattr(checkpointer, "conn") and checkpointer.conn is not None:
                await checkpointer.conn.close()

    except ImportError:
        if settings.environment == "development":
            logger.info(
                "langgraph-checkpoint-postgres not installed in local development - "
                "graph will run without persistence"
            )
        else:
            logger.warning(
                "langgraph-checkpoint-postgres not installed - "
                "graph will run without persistence"
            )
        yield None
    except Exception as exc:
        logger.warning(
            "Checkpointer initialization failed: %s - graph will run without persistence",
            exc,
        )
        yield None


async def get_checkpointer():
    """Deprecated compatibility shim. Use open_checkpointer() instead."""
    logger.warning(
        "get_checkpointer() is deprecated for request handling; use open_checkpointer()"
    )
    return None


async def close_checkpointer():
    """No-op: request-scoped checkpointers are closed by open_checkpointer()."""
    return None


def reset_checkpointer():
    """Reset process-local setup state (for tests only)."""
    global _setup_complete
    _setup_complete = False
