"""Canonical WiiiRunner-backed multi-agent runtime surface."""

from __future__ import annotations

from typing import Any


async def process_with_multi_agent(*args: Any, **kwargs: Any) -> dict:
    """Dispatch to the runner-backed sync entrypoint.

    The lazy import preserves legacy test patch paths while production callers
    move to the canonical runtime module name.
    """
    from app.engine.multi_agent.graph import process_with_multi_agent as process

    return await process(*args, **kwargs)

__all__ = ["process_with_multi_agent"]
