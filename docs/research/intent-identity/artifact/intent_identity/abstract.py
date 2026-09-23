"""Abstract (in-memory) sink and policies for exhaustive finite-domain studies.

Used by D1 (regrouping) and its v0.3 extension D1-TTL (retention expiry).
The sink records effects as ``(key, entry)`` rows. A row is the effect. A
repeated ``(key, entry)`` while the dedup index still retains it returns the
old receipt instead of inserting a new row.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations
from typing import Iterable, Sequence

Grouping = tuple[tuple[str, ...], ...]


def cut_patterns(n: int) -> list[tuple[int, ...]]:
    """All 2^(n-1) ways to cut an ordered sequence of n items into groups."""
    if n == 0:
        return [()]
    out = []
    for mask in range(1 << (n - 1)):
        sizes = []
        size = 1
        for i in range(n - 1):
            if mask >> i & 1:
                sizes.append(size)
                size = 1
            else:
                size += 1
        sizes.append(size)
        out.append(tuple(sizes))
    return out


def all_groupings(items: Sequence[str]) -> list[Grouping]:
    """All n! * 2^(n-1) ordered wrapper groupings of ``items``."""
    out: list[Grouping] = []
    for perm in permutations(items):
        for sizes in cut_patterns(len(items)):
            groups = []
            idx = 0
            for s in sizes:
                groups.append(tuple(perm[idx : idx + s]))
                idx += s
            out.append(tuple(groups))
    return out


def flat(grouping: Grouping) -> list[str]:
    return [m for g in grouping for m in g]


@dataclass
class AbstractSink:
    effects: list[tuple[str, str]] = field(default_factory=list)
    dedup: set[tuple[str, str]] = field(default_factory=set)
    calls: int = 0

    def execute(self, key: str, entry: str) -> None:
        self.calls += 1
        if (key, entry) in self.dedup:
            return
        self.dedup.add((key, entry))
        self.effects.append((key, entry))

    def expire_retention(self) -> None:
        """Model finite retention: dedup index reclaimed, effects remain real."""
        self.dedup.clear()

    def lookup(self, entry: str) -> bool:
        """Point-in-time evidence query: has an effect for this occurrence
        committed? A negative answer is not finality evidence."""
        self.calls += 1
        return any(e == entry for _, e in self.effects)

    def effect_counts(self) -> Counter:
        return Counter(entry for _, entry in self.effects)


def key_group(members: Iterable[str]) -> str:
    return "G:" + ",".join(sorted(members))


def key_occurrence(member: str) -> str:
    return "K:" + member


@dataclass
class Ledger:
    """Controller-side durable knowledge about each occurrence."""

    done: set[str] = field(default_factory=set)
    held: set[str] = field(default_factory=set)
    unresolved: set[str] = field(default_factory=set)


def run_source(
    grouping: Grouping,
    prefix: int,
    sink: AbstractSink,
    policy: str,
    last_state: str = "done",
) -> Ledger:
    """Execute the first ``prefix`` occurrences of the source plan, then crash.

    ``last_state`` describes the crash point for the last occurrence of the
    prefix:

    * ``done``: effect committed and durably confirmed by the controller;
    * ``held_committed``: effect committed at the sink, but the controller
      crashed before recording the receipt (lost acknowledgement);
    * ``held_uncommitted``: the controller reserved the occurrence and crashed
      before the sink committed anything.
    """
    ledger = Ledger()
    order = flat(grouping)
    committed = order[:prefix]
    if not committed:
        return ledger
    last = committed[-1]
    for group in grouping:
        for m in group:
            if m not in committed:
                return ledger
            if m == last and last_state == "held_uncommitted":
                ledger.held.add(m)
                return ledger
            key = key_group(group) if policy == "G" else key_occurrence(m)
            sink.execute(key, m)
            if m == last and last_state == "held_committed":
                ledger.held.add(m)
            else:
                ledger.done.add(m)
    return ledger


def run_destination(
    grouping: Grouping,
    sink: AbstractSink,
    policy: str,
    ledger: Ledger,
    retention_expired: bool = False,
) -> int:
    """Execute the regrouped destination plan after recovery. Returns calls made.

    ``retention_expired`` is the controller's own knowledge that the sink's
    documented retention window has elapsed since the held dispatch.
    """
    before = sink.calls
    for group in grouping:
        for m in group:
            if policy == "G":
                sink.execute(key_group(group), m)
            elif policy == "R":
                # Strong reference: stable occurrence key, resend everything,
                # rely on the sink's dedup index.
                sink.execute(key_occurrence(m), m)
            elif policy in ("R+", "V"):
                # R+: reference that also consults its own durable ledger.
                # V: verified residualization at plan level.
                # Both: cached completion for done, same-key retry otherwise.
                if m in ledger.done:
                    continue
                sink.execute(key_occurrence(m), m)
            elif policy == "Vr":
                # Retention-aware: a held occurrence whose retention window has
                # lapsed is no longer safely retryable under the same key. It
                # stays unresolved (P_O behaviour) rather than being re-sent.
                if m in ledger.done:
                    continue
                if m in ledger.held and retention_expired:
                    ledger.unresolved.add(m)
                    continue
                sink.execute(key_occurrence(m), m)
            elif policy == "Vr+E":
                # Retention-aware with a point-in-time evidence lookup for a
                # lapsed held occurrence: positive evidence confirms; negative
                # evidence is NOT finality, so the occurrence stays unresolved
                # (matches the runtime's aware/P_D(T) path).
                if m in ledger.done:
                    continue
                if m in ledger.held and retention_expired:
                    if sink.lookup(m):
                        ledger.done.add(m)
                    else:
                        ledger.unresolved.add(m)
                    continue
                sink.execute(key_occurrence(m), m)
            else:
                raise ValueError(policy)
    return sink.calls - before
