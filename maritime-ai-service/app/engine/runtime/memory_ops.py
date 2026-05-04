"""Hierarchical memory operations — Letta / MemGPT self-edit pattern.

Phase 33e of the runtime migration epic (issue #207). Wiii's existing
``core_memory_block`` (Sprint 168) holds ~800 tokens of slow-changing
sticky facts about the user (name, preferences, role, recent goals).
Today that block is read-only from the LLM's perspective — Wiii sees
it but cannot edit it. The Letta / MemGPT paradigm exposes
``core_memory.replace`` and ``core_memory.append`` as tool calls so
the agent itself decides when a fact is stable enough to promote.

This module ships the primitive — pure functions over a memory
store interface. Wiring as actual tool definitions (so the LLM can
call them) lives in a follow-up commit so the primitive lands first
and the contract is reviewable on its own.

Out of scope:
- Tool registration in ToolRegistry (separate commit).
- LLM training so it knows when to call these (prompt engineering).
- Concurrency for multi-process writes (an asyncpg row-lock would
  cover it; the in-memory backend uses asyncio.Lock).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


# ── data ──


@dataclass(slots=True)
class MemoryEditResult:
    """Outcome of a self-edit op. Always returned, never raised — the
    LLM needs structured feedback to decide what to do next."""

    success: bool
    block_name: str
    new_content: str
    operation: str  # "replace" | "append" | "no_op"
    reason: Optional[str] = None


# ── store interface ──


class CoreMemoryStore(Protocol):
    """Backend that owns the actual core_memory_block bytes for a user.

    The Wiii production backend (Sprint 168) lives in a Postgres row
    keyed by user_id + block_name. Tests use ``InMemoryCoreMemoryStore``.
    """

    async def get_block(
        self, *, user_id: str, block_name: str
    ) -> Optional[str]: ...

    async def put_block(
        self, *, user_id: str, block_name: str, content: str
    ) -> None: ...


class InMemoryCoreMemoryStore:
    """Process-local store for tests + dev. Loses state on restart."""

    def __init__(self) -> None:
        self._blocks: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get_block(
        self, *, user_id: str, block_name: str
    ) -> Optional[str]:
        async with self._lock:
            return self._blocks.get((user_id, block_name))

    async def put_block(
        self, *, user_id: str, block_name: str, content: str
    ) -> None:
        async with self._lock:
            self._blocks[(user_id, block_name)] = content


# ── ops ──

DEFAULT_MAX_BLOCK_CHARS = 3200  # ~800 tokens at chars_per_token=4


async def replace_block(
    store: CoreMemoryStore,
    *,
    user_id: str,
    block_name: str,
    new_content: str,
    max_chars: int = DEFAULT_MAX_BLOCK_CHARS,
) -> MemoryEditResult:
    """Overwrite the named block with ``new_content``.

    Caps at ``max_chars`` to keep token budget predictable. When the
    new content already matches the existing block, returns a no_op
    result — saves a Postgres write under the typical "LLM re-states
    the same fact" flow.
    """
    if not user_id or not block_name:
        return MemoryEditResult(
            success=False,
            block_name=block_name,
            new_content="",
            operation="replace",
            reason="user_id and block_name are required",
        )

    cleaned = (new_content or "").strip()
    if len(cleaned) > max_chars:
        # Reserve 1 char for the ellipsis so total stays <= max_chars.
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"

    existing = await store.get_block(user_id=user_id, block_name=block_name)
    if existing == cleaned:
        return MemoryEditResult(
            success=True,
            block_name=block_name,
            new_content=cleaned,
            operation="no_op",
            reason="content unchanged",
        )

    try:
        await store.put_block(
            user_id=user_id, block_name=block_name, content=cleaned
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[memory_ops.replace] put_block raised for %s/%s: %s",
            user_id,
            block_name,
            exc,
        )
        return MemoryEditResult(
            success=False,
            block_name=block_name,
            new_content=cleaned,
            operation="replace",
            reason=f"put_block failed: {type(exc).__name__}",
        )

    return MemoryEditResult(
        success=True,
        block_name=block_name,
        new_content=cleaned,
        operation="replace",
    )


async def append_to_block(
    store: CoreMemoryStore,
    *,
    user_id: str,
    block_name: str,
    addition: str,
    separator: str = "\n",
    max_chars: int = DEFAULT_MAX_BLOCK_CHARS,
) -> MemoryEditResult:
    """Append ``addition`` to the named block.

    When the new total would exceed ``max_chars``, trims FROM THE
    FRONT (oldest content) so the most recent addition stays visible
    — matches the SOTA "memory pressure" behavior in MemGPT / Letta.
    Concretely: fact-amnesia is preferable to silently dropping the
    user's just-stated preference.
    """
    if not user_id or not block_name:
        return MemoryEditResult(
            success=False,
            block_name=block_name,
            new_content="",
            operation="append",
            reason="user_id and block_name are required",
        )

    addition_clean = (addition or "").strip()
    if not addition_clean:
        return MemoryEditResult(
            success=False,
            block_name=block_name,
            new_content="",
            operation="append",
            reason="empty addition",
        )

    existing = await store.get_block(
        user_id=user_id, block_name=block_name
    ) or ""

    if existing:
        combined = f"{existing}{separator}{addition_clean}"
    else:
        combined = addition_clean

    if len(combined) > max_chars:
        # Drop the oldest bytes (head) to make room. This is the
        # MemGPT "memory pressure" trade-off: prefer keeping recent
        # facts even if it means losing older ones.
        combined = "…" + combined[-(max_chars - 1):]

    try:
        await store.put_block(
            user_id=user_id, block_name=block_name, content=combined
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[memory_ops.append] put_block raised for %s/%s: %s",
            user_id,
            block_name,
            exc,
        )
        return MemoryEditResult(
            success=False,
            block_name=block_name,
            new_content=combined,
            operation="append",
            reason=f"put_block failed: {type(exc).__name__}",
        )

    return MemoryEditResult(
        success=True,
        block_name=block_name,
        new_content=combined,
        operation="append",
    )


async def read_block(
    store: CoreMemoryStore, *, user_id: str, block_name: str
) -> str:
    """Return the named block's content, or empty string when missing.

    Wraps ``store.get_block`` so callers (and tool definitions) get a
    consistent string-typed return without juggling Optional[str].
    """
    if not user_id or not block_name:
        return ""
    try:
        result = await store.get_block(
            user_id=user_id, block_name=block_name
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[memory_ops.read] get_block raised: %s", exc
        )
        return ""
    return result or ""


__all__ = [
    "CoreMemoryStore",
    "InMemoryCoreMemoryStore",
    "MemoryEditResult",
    "replace_block",
    "append_to_block",
    "read_block",
    "DEFAULT_MAX_BLOCK_CHARS",
]
