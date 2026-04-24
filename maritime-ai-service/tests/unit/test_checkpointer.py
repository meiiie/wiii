"""Tests for deprecated LangGraph checkpointer compatibility shims."""

import pytest


@pytest.mark.asyncio
async def test_open_checkpointer_yields_none():
    """WiiiRunner no longer uses LangGraph checkpoint persistence."""
    from app.engine.multi_agent import checkpointer as mod

    async with mod.open_checkpointer() as checkpointer:
        assert checkpointer is None


@pytest.mark.asyncio
async def test_get_checkpointer_returns_none():
    from app.engine.multi_agent import checkpointer as mod

    assert await mod.get_checkpointer() is None


@pytest.mark.asyncio
async def test_close_checkpointer_is_noop():
    from app.engine.multi_agent import checkpointer as mod

    assert await mod.close_checkpointer() is None


def test_reset_checkpointer_is_noop():
    from app.engine.multi_agent import checkpointer as mod

    assert mod.reset_checkpointer() is None
