"""Phase 11c replay seed propagation — Runtime Migration #207.

Locks the ContextVar contract: set on a turn, read at LLM call site,
clear on turn boundary, never leaks across coroutines.
"""

from __future__ import annotations

import asyncio

import pytest

from app.engine.runtime.replay_context import (
    clear_replay_seed,
    get_replay_seed,
    get_replay_seed_int,
    replay_seed_scope,
    set_replay_seed,
)


def test_default_is_none():
    assert get_replay_seed() is None
    assert get_replay_seed_int() is None


def test_set_and_clear_roundtrip():
    token = set_replay_seed("42")
    try:
        assert get_replay_seed() == "42"
        assert get_replay_seed_int() == 42
    finally:
        clear_replay_seed(token)
    assert get_replay_seed() is None


def test_get_int_returns_none_for_unparseable():
    token = set_replay_seed("not-a-number")
    try:
        assert get_replay_seed() == "not-a-number"
        assert get_replay_seed_int() is None
    finally:
        clear_replay_seed(token)


def test_scope_context_manager_pairs_set_and_clear():
    assert get_replay_seed() is None
    with replay_seed_scope("99"):
        assert get_replay_seed() == "99"
    assert get_replay_seed() is None  # automatically cleared


def test_scope_clears_on_exception():
    assert get_replay_seed() is None
    with pytest.raises(RuntimeError):
        with replay_seed_scope("11"):
            assert get_replay_seed() == "11"
            raise RuntimeError("boom")
    assert get_replay_seed() is None


def test_nested_scopes_restore_outer_value():
    with replay_seed_scope("outer"):
        assert get_replay_seed() == "outer"
        with replay_seed_scope("inner"):
            assert get_replay_seed() == "inner"
        assert get_replay_seed() == "outer"
    assert get_replay_seed() is None


# ── async isolation ──

@pytest.mark.asyncio
async def test_seed_does_not_leak_across_concurrent_tasks():
    """ContextVar copy semantics — each task gets its own snapshot."""

    captured: dict[str, list[str | None]] = {"a": [], "b": []}

    async def task(label: str, seed: str, others: dict):
        with replay_seed_scope(seed):
            await asyncio.sleep(0)
            others[label].append(get_replay_seed())
            await asyncio.sleep(0)
            others[label].append(get_replay_seed())

    await asyncio.gather(task("a", "A", captured), task("b", "B", captured))
    # Each task only ever sees its own seed.
    assert captured["a"] == ["A", "A"]
    assert captured["b"] == ["B", "B"]


@pytest.mark.asyncio
async def test_unscoped_task_sees_none():
    """A task started outside any scope does not inherit a seed from its caller."""

    async def child() -> object:
        return get_replay_seed()

    with replay_seed_scope("parent-only"):
        # Task created inside the scope DOES inherit (ContextVar copy).
        assert await asyncio.create_task(child()) == "parent-only"
    # After the scope: no leak.
    assert await asyncio.create_task(child()) is None
