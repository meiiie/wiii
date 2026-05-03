"""Replay seed propagation channel.

Phase 11c of the runtime migration epic (issue #207). Borrows the
Anthropic Managed Agents pattern for reproducible regression testing:
when an ``EvalRecord`` carries a ``replay_seed``, the same seed is
threaded through every LLM call in the turn so a replay produces the
same sampling decisions the original turn made.

Wire shape:
- ``replay_eval.py`` sets the seed before each replay turn via
  ``set_replay_seed(record.replay_seed)`` and clears it after.
- LLM call sites (``UnifiedLLMClient``, raw provider adapters) read the
  active value via ``get_replay_seed()`` and pass it through whatever
  provider-native parameter exists (OpenAI ``seed=``, etc.).
- Default is ``None`` — production traffic is non-deterministic.

ContextVar (not threading.local) because the entire runtime is async.
The token returned by ``set_replay_seed`` MUST be passed back to
``clear_replay_seed`` to avoid leaking state across turns; the
``replay_seed_scope`` context manager makes that pairing implicit.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator, Optional

_seed_var: ContextVar[Optional[str]] = ContextVar(
    "wiii_replay_seed", default=None
)


def get_replay_seed() -> Optional[str]:
    """Return the currently active replay seed, or ``None`` for live traffic."""
    return _seed_var.get()


def get_replay_seed_int() -> Optional[int]:
    """Coerce the active seed to ``int`` for providers that need numeric seeds.

    Returns ``None`` when no seed is set or when the seed string is not
    parseable. Callers that fail closed on coerce errors should check the
    return value rather than wrapping ``int(get_replay_seed())`` themselves.
    """
    raw = _seed_var.get()
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_replay_seed(seed: Optional[str]) -> Token:
    """Set the active seed and return the token for clearing it later."""
    return _seed_var.set(seed)


def clear_replay_seed(token: Token) -> None:
    """Restore the seed to its prior value using the token from ``set_replay_seed``."""
    _seed_var.reset(token)


@contextmanager
def replay_seed_scope(seed: Optional[str]) -> Generator[None, None, None]:
    """Apply ``seed`` for the duration of the ``with`` block.

    Pairs ``set_replay_seed`` + ``clear_replay_seed`` automatically so
    callers cannot leak state by forgetting to reset.
    """
    token = set_replay_seed(seed)
    try:
        yield
    finally:
        clear_replay_seed(token)


__all__ = [
    "get_replay_seed",
    "get_replay_seed_int",
    "set_replay_seed",
    "clear_replay_seed",
    "replay_seed_scope",
]
