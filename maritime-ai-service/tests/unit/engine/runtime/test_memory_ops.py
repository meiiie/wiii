"""Phase 33e hierarchical memory ops — Runtime Migration #207.

Locks the Letta / MemGPT self-edit contract:
- replace overwrites + caps at max_chars
- replace returns no_op when content unchanged
- append concatenates with separator
- append trims FROM THE FRONT under pressure (recent wins)
- read returns empty string for missing blocks
- All ops never raise — return MemoryEditResult with success=False
"""

from __future__ import annotations

import pytest

from app.engine.runtime.memory_ops import (
    DEFAULT_MAX_BLOCK_CHARS,
    InMemoryCoreMemoryStore,
    MemoryEditResult,
    append_to_block,
    read_block,
    replace_block,
)


@pytest.fixture
def store():
    return InMemoryCoreMemoryStore()


# ── replace_block ──

async def test_replace_writes_new_content(store):
    out = await replace_block(
        store, user_id="u1", block_name="profile",
        new_content="Tên: Hùng. Sở thích: COLREGs.",
    )
    assert out.success is True
    assert out.operation == "replace"
    assert out.new_content == "Tên: Hùng. Sở thích: COLREGs."

    # Persisted.
    assert (
        await store.get_block(user_id="u1", block_name="profile")
        == "Tên: Hùng. Sở thích: COLREGs."
    )


async def test_replace_trims_to_max_chars(store):
    long_content = "A" * (DEFAULT_MAX_BLOCK_CHARS + 200)
    out = await replace_block(
        store, user_id="u1", block_name="x", new_content=long_content
    )
    assert out.success
    assert len(out.new_content) <= DEFAULT_MAX_BLOCK_CHARS
    assert out.new_content.endswith("…")


async def test_replace_with_unchanged_content_returns_no_op(store):
    await replace_block(
        store, user_id="u1", block_name="b", new_content="same"
    )
    out = await replace_block(
        store, user_id="u1", block_name="b", new_content="same"
    )
    assert out.operation == "no_op"
    assert out.success is True
    assert "unchanged" in (out.reason or "")


async def test_replace_strips_whitespace(store):
    out = await replace_block(
        store, user_id="u1", block_name="b",
        new_content="   trimmed   \n",
    )
    assert out.new_content == "trimmed"


@pytest.mark.parametrize("user_id,block_name", [
    ("", "block"),
    ("user", ""),
    ("", ""),
])
async def test_replace_rejects_empty_user_or_block(
    store, user_id, block_name
):
    out = await replace_block(
        store, user_id=user_id, block_name=block_name,
        new_content="anything",
    )
    assert out.success is False
    assert "required" in (out.reason or "")


async def test_replace_returns_failure_on_store_exception():
    class BoomStore:
        async def get_block(self, **kw):
            return None

        async def put_block(self, **kw):
            raise RuntimeError("disk full")

    out = await replace_block(
        BoomStore(), user_id="u", block_name="b", new_content="x"
    )
    assert out.success is False
    assert out.operation == "replace"
    assert "RuntimeError" in (out.reason or "")


# ── append_to_block ──

async def test_append_to_empty_block_writes_addition(store):
    out = await append_to_block(
        store, user_id="u", block_name="b", addition="first fact"
    )
    assert out.success
    assert out.operation == "append"
    assert out.new_content == "first fact"


async def test_append_concatenates_with_separator(store):
    await append_to_block(
        store, user_id="u", block_name="b", addition="first"
    )
    out = await append_to_block(
        store, user_id="u", block_name="b", addition="second"
    )
    assert out.new_content == "first\nsecond"


async def test_append_custom_separator(store):
    await append_to_block(
        store, user_id="u", block_name="b", addition="a"
    )
    out = await append_to_block(
        store, user_id="u", block_name="b", addition="b", separator=" | "
    )
    assert out.new_content == "a | b"


async def test_append_empty_addition_no_op(store):
    out = await append_to_block(
        store, user_id="u", block_name="b", addition="   "
    )
    assert out.success is False
    assert "empty addition" in (out.reason or "")


async def test_append_under_pressure_trims_front(store):
    """Recent additions must survive when the block hits the cap —
    older content gets trimmed from the front (MemGPT pressure)."""
    cap = 100
    # Pre-fill with old content near the cap.
    await replace_block(
        store, user_id="u", block_name="b",
        new_content="OLD_" + "x" * 90, max_chars=cap,
    )
    out = await append_to_block(
        store, user_id="u", block_name="b",
        addition="NEW_FACT_KEEP_ME", max_chars=cap,
    )
    assert out.success
    assert len(out.new_content) <= cap
    # The recent addition is in the trimmed result.
    assert "NEW_FACT_KEEP_ME" in out.new_content
    # Old content trimmed.
    assert out.new_content.startswith("…")


@pytest.mark.parametrize("user_id,block_name", [
    ("", "b"),
    ("u", ""),
])
async def test_append_rejects_empty_user_or_block(store, user_id, block_name):
    out = await append_to_block(
        store, user_id=user_id, block_name=block_name, addition="x"
    )
    assert out.success is False
    assert "required" in (out.reason or "")


async def test_append_returns_failure_on_store_exception():
    class BoomStore:
        async def get_block(self, **kw):
            return "existing"

        async def put_block(self, **kw):
            raise RuntimeError("disk full")

    out = await append_to_block(
        BoomStore(), user_id="u", block_name="b", addition="more"
    )
    assert out.success is False
    assert out.operation == "append"


# ── read_block ──

async def test_read_returns_empty_string_for_missing(store):
    assert await read_block(store, user_id="u", block_name="missing") == ""


async def test_read_returns_existing_content(store):
    await replace_block(
        store, user_id="u", block_name="b", new_content="hello"
    )
    assert await read_block(store, user_id="u", block_name="b") == "hello"


@pytest.mark.parametrize("user_id,block_name", [
    ("", "b"),
    ("u", ""),
])
async def test_read_rejects_empty_user_or_block(user_id, block_name):
    """read_block must NOT raise — returns "" instead."""
    store = InMemoryCoreMemoryStore()
    assert (
        await read_block(store, user_id=user_id, block_name=block_name) == ""
    )


async def test_read_returns_empty_when_store_raises():
    class BoomStore:
        async def get_block(self, **kw):
            raise RuntimeError("DB down")

        async def put_block(self, **kw):
            pass

    assert await read_block(BoomStore(), user_id="u", block_name="b") == ""


# ── multi-user isolation ──

async def test_users_have_independent_blocks(store):
    await replace_block(
        store, user_id="alice", block_name="profile",
        new_content="Alice loves COLREGs",
    )
    await replace_block(
        store, user_id="bob", block_name="profile",
        new_content="Bob loves SOLAS",
    )
    assert (
        await read_block(store, user_id="alice", block_name="profile")
        == "Alice loves COLREGs"
    )
    assert (
        await read_block(store, user_id="bob", block_name="profile")
        == "Bob loves SOLAS"
    )


async def test_blocks_have_independent_namespaces(store):
    await replace_block(
        store, user_id="u", block_name="profile", new_content="A"
    )
    await replace_block(
        store, user_id="u", block_name="goals", new_content="B"
    )
    assert (
        await read_block(store, user_id="u", block_name="profile") == "A"
    )
    assert await read_block(store, user_id="u", block_name="goals") == "B"
