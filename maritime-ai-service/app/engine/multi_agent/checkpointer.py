"""
DEPRECATED: LangGraph checkpointer helpers.

LangGraph has been removed (De-LangGraphing Phase 3).
This file is preserved as a stub for any remaining imports.
The checkpointer is no longer needed — WiiiRunner has no checkpoint persistence.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[None]:
    """
    DEPRECATED — yields None.

    LangGraph checkpointer removed. WiiiRunner does not use checkpoints.
    """
    yield None


async def get_checkpointer():
    """DEPRECATED — always returns None."""
    return None


async def close_checkpointer():
    """No-op."""
    return None


def reset_checkpointer():
    """No-op."""
    pass
