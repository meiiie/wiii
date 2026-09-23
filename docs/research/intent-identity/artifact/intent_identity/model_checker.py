"""M1: finite-state fault exploration for one obligation.

Independent re-implementation of the v0.2 abstract model, extended with a
finite-retention transition. One obligation; two request generations (0 is
the original key, 1 is a fresh key); two senders per generation (the second
sender is a recovery worker after a crash); a one-crash budget.

The model checks safety, not liveness. It is not a refinement proof of the
Python/SQLite runtime. State counts are specific to this encoding and are not
comparable to the v0.2 numbers (480 states / 1,266 edges), which came from a
different encoding of the same informal model.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from typing import Callable, Iterator

GENS = (0, 1)
SENDERS = (0, 1)


@dataclass(frozen=True)
class State:
    created: frozenset[int] = frozenset({0})
    held: int | None = None
    sent: frozenset[tuple[int, int]] = frozenset()
    delivered: frozenset[tuple[int, int]] = frozenset()
    committed: frozenset[int] = frozenset()
    commit_count: int = 0
    receipts: frozenset[int] = frozenset()
    fenced: frozenset[int] = frozenset()
    lookup_negative: frozenset[int] = frozenset()
    certified_absent: frozenset[int] = frozenset()
    done: bool = False
    crashes: int = 0
    retention_expired: bool = False


@dataclass
class Config:
    """Which rules are in force. Every flag defaults to the safe configuration."""

    name: str = "safe"
    certify_requires_fence: bool = True
    fresh_key_requires_certificate: bool = True
    done_requires_receipt: bool = True
    sink_dedup: bool = True
    send_respects_retention: bool = True
    model_retention_expiry: bool = True
    fence_available: bool = True


def violations(s: State) -> list[str]:
    out = []
    if s.commit_count > 1:
        out.append("duplicate")
    if s.done and s.commit_count == 0:
        out.append("false success")
    return out


def successors(s: State, cfg: Config) -> Iterator[tuple[str, State]]:
    # Controller reserves authority for a generation that exists.
    for g in sorted(s.created):
        if s.held is None and g not in s.receipts:
            yield f"hold(g{g})", replace(s, held=g)

    # Send: sender 0 before any crash; sender 1 only as a recovery worker.
    for g in sorted(s.created):
        if s.held != g:
            continue
        for snd in SENDERS:
            if (g, snd) in s.sent:
                continue
            if snd == 1 and s.crashes == 0:
                continue
            if cfg.send_respects_retention and s.retention_expired and any(x == g for x, _ in s.sent):
                # Retention-aware controller: never re-send a key it may have
                # dispatched before the retention window lapsed; recovery must
                # go through the fence/lookup/certificate path instead.
                continue
            yield f"send(g{g},s{snd})", replace(s, sent=s.sent | {(g, snd)})

    # Network delivery of a queued request to the sink.
    for (g, snd) in sorted(s.sent):
        if (g, snd) in s.delivered:
            continue
        nxt = replace(s, delivered=s.delivered | {(g, snd)})
        if g in s.fenced:
            yield f"deliver(g{g},s{snd}):rejected-by-fence", nxt
            continue
        dedup_hit = cfg.sink_dedup and g in s.committed and not s.retention_expired
        if dedup_hit:
            yield f"deliver(g{g},s{snd}):dedup-receipt", nxt
        else:
            yield (
                f"deliver(g{g},s{snd}):commit",
                replace(nxt, committed=s.committed | {g}, commit_count=s.commit_count + 1),
            )

    # Controller receives a receipt for a delivered, committed generation.
    for g in sorted(s.committed):
        if g in s.receipts:
            continue
        if any(d[0] == g for d in s.delivered):
            yield f"receive-receipt(g{g})", replace(s, receipts=s.receipts | {g})

    # Point-in-time lookup at the sink.
    for g in sorted(s.created):
        if g in s.committed:
            if g not in s.receipts:
                yield f"lookup(g{g}):positive", replace(s, receipts=s.receipts | {g})
        elif g not in s.lookup_negative:
            yield f"lookup(g{g}):negative", replace(s, lookup_negative=s.lookup_negative | {g})

    # Fence an old generation at the sink (not offered by every provider).
    for g in sorted(s.created):
        if cfg.fence_available and g not in s.fenced:
            yield f"fence(g{g})", replace(s, fenced=s.fenced | {g})

    # No-effect certificate.
    for g in sorted(s.created):
        if g in s.certified_absent or g in s.committed:
            continue
        if cfg.certify_requires_fence:
            ok = g in s.fenced and g in s.lookup_negative
        else:
            ok = g in s.lookup_negative
        if ok:
            yield f"certify-absent(g{g})", replace(s, certified_absent=s.certified_absent | {g})

    # Create a fresh generation (fresh key) for the same obligation.
    if 1 not in s.created and s.held == 0:
        if cfg.fresh_key_requires_certificate:
            ok = 0 in s.certified_absent
        else:
            ok = 0 not in s.receipts
        if ok:
            yield "create-gen1", replace(s, created=s.created | {1}, held=None)

    # Mark the obligation done.
    if not s.done:
        if cfg.done_requires_receipt:
            ok = bool(s.receipts)
        else:
            ok = bool(s.receipts) or bool(s.lookup_negative)
        if ok:
            yield "mark-done", replace(s, done=True)

    # Crash (budget one). Trusted facts and queued requests are preserved.
    if s.crashes == 0:
        yield "crash", replace(s, crashes=1)

    # Retention window of the sink's dedup index lapses. The window is assumed
    # to be much longer than any network delay, so expiry only happens while
    # no request is in flight.
    if (
        cfg.model_retention_expiry
        and not s.retention_expired
        and s.committed
        and s.sent == s.delivered
    ):
        yield "retention-expires", replace(s, retention_expired=True)


@dataclass
class Result:
    name: str
    states: int
    edges: int
    witness: list[str] | None
    violation: str | None
    exhausted: bool


def explore(cfg: Config, stop_at_first: bool = True) -> Result:
    start = State()
    parent: dict[State, tuple[State, str] | None] = {start: None}
    queue = deque([start])
    edges = 0
    while queue:
        s = queue.popleft()
        for label, nxt in successors(s, cfg):
            edges += 1
            if nxt not in parent:
                parent[nxt] = (s, label)
                v = violations(nxt)
                if v and stop_at_first:
                    trace = []
                    cur = nxt
                    while parent[cur] is not None:
                        prev, lab = parent[cur]
                        trace.append(lab)
                        cur = prev
                    trace.reverse()
                    return Result(cfg.name, len(parent), edges, trace, v[0], False)
                queue.append(nxt)
    return Result(cfg.name, len(parent), edges, None, None, True)


def configurations(include_retention: bool = True) -> list[Config]:
    cfgs = [
        Config(name="safe", model_retention_expiry=include_retention),
        Config(name="absence-without-fence", certify_requires_fence=False, model_retention_expiry=include_retention),
        Config(name="fresh-key-retry", fresh_key_requires_certificate=False, model_retention_expiry=include_retention),
        Config(name="missing-as-success", done_requires_receipt=False, model_retention_expiry=include_retention),
        Config(name="no-sink-dedup", sink_dedup=False, model_retention_expiry=include_retention),
    ]
    if include_retention:
        cfgs.append(Config(name="retry-after-retention-expiry", send_respects_retention=False))
        cfgs.append(Config(name="safe-without-fence-capability", fence_available=False))
    return cfgs
