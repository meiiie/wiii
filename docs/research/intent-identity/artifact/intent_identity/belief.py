"""Outcome-belief families over finalized old dispatches (manuscript section V).

A belief family ``B`` is a nonempty set of possible completed sets, each a
frozenset of item indices in ``range(n)``. The true completed set is in ``B``.

* ``P(B)`` possibly completed, ``D(B)`` definitely completed,
  ``F(B) = Omega \\ P(B)`` certainly absent, ``U(B) = P(B) \\ D(B)`` unresolved.
* Ternary projection keeps only per-item done/absent/unknown, i.e. it replaces
  ``B`` by the product family ``D(B) + 2^U(B)``.
* ``optimal_probe_cost`` is the exact adaptive unit-cost single-item query
  oracle under a uniform prior over worlds, memoized over reachable
  sub-families. It is exponential and is a research oracle, not a scalable
  implementation.

Batch semantics classes map a sent-but-unacknowledged request over ``n``
items to a belief family:

* ``independent``: any subset may have committed (per-entry outcomes);
* ``atomic``: all or nothing;
* ``prefix``: ordered processing that stops at the first failure, so the
  committed set is a prefix of the request order;
* ``exact_k``: a trustworthy aggregate says exactly ``k`` committed.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations
from math import comb, log2, ceil
from typing import Iterable

World = frozenset[int]
Family = frozenset[World]


def family(worlds: Iterable[Iterable[int]]) -> Family:
    return frozenset(frozenset(w) for w in worlds)


def possibly(B: Family) -> World:
    out: set[int] = set()
    for w in B:
        out |= w
    return frozenset(out)


def definitely(B: Family) -> World:
    it = iter(B)
    out = set(next(it))
    for w in it:
        out &= w
    return frozenset(out)


def certainly_absent(B: Family, n: int) -> World:
    return frozenset(range(n)) - possibly(B)


def unresolved(B: Family) -> World:
    return possibly(B) - definitely(B)


def ternary_projection(B: Family, n: int) -> tuple[str, ...]:
    d, p = definitely(B), possibly(B)
    return tuple("done" if i in d else ("absent" if i not in p else "unknown") for i in range(n))


def ternary_family(B: Family, n: int) -> Family:
    """The family a ternary journal effectively believes: D(B) + 2^U(B)."""
    d = definitely(B)
    u = sorted(unresolved(B))
    worlds = []
    for r in range(len(u) + 1):
        for sub in combinations(u, r):
            worlds.append(d | frozenset(sub))
    return frozenset(worlds)


def safe_fresh_dispatch_bruteforce(B: Family, S: World) -> bool:
    return all(not (S & w) for w in B)


def completes_all_worlds(B: Family, S: World, n: int) -> bool:
    omega = frozenset(range(n))
    return all((S | w) == omega and not (S & w) for w in B)


def condition(B: Family, item: int, committed: bool) -> Family:
    return frozenset(w for w in B if (item in w) == committed)


@lru_cache(maxsize=None)
def optimal_probe_cost(B: Family) -> float:
    """Expected number of unit-cost item probes to identify the world, uniform prior."""
    if len(B) == 1:
        return 0.0
    best = float("inf")
    for i in sorted(unresolved(B)):
        b1 = condition(B, i, True)
        b0 = condition(B, i, False)
        c = 1.0 + (len(b1) / len(B)) * optimal_probe_cost(b1) + (len(b0) / len(B)) * optimal_probe_cost(b0)
        best = min(best, c)
    return best


@lru_cache(maxsize=None)
def worst_case_probe_cost(B: Family) -> int:
    if len(B) == 1:
        return 0
    best = None
    for i in sorted(unresolved(B)):
        c = 1 + max(worst_case_probe_cost(condition(B, i, True)), worst_case_probe_cost(condition(B, i, False)))
        best = c if best is None else min(best, c)
    return best


# -- batch semantics classes -------------------------------------------------


def independent_family(n: int) -> Family:
    items = range(n)
    return frozenset(frozenset(s) for r in range(n + 1) for s in combinations(items, r))


def atomic_family(n: int) -> Family:
    return frozenset({frozenset(), frozenset(range(n))})


def prefix_family(n: int) -> Family:
    return frozenset(frozenset(range(k)) for k in range(n + 1))


def exact_k_family(n: int, k: int) -> Family:
    return frozenset(frozenset(s) for s in combinations(range(n), k))


def exact_k_expected_cost(n: int, k: int) -> float:
    """Closed form (v0.2 Proposition 5): n - (n-k)/(k+1) - k/(n-k+1)."""
    return n - (n - k) / (k + 1) - k / (n - k + 1)


def prefix_expected_cost(n: int) -> float:
    """Optimal binary search over N = n+1 equally likely prefixes.

    Complete binary decision tree with N leaves: E = ceil(log2 N) - (2^ceil(log2 N) - N)/N.
    """
    N = n + 1
    m = ceil(log2(N))
    return m - ((1 << m) - N) / N


def prefix_worst_cost(n: int) -> int:
    return ceil(log2(n + 1))


def prefix_fence_expected_cost(n: int) -> float:
    """Per-key finality for the prefix class.

    A probe is itself a fence, so probing an absent member is free relative to
    the fence that member needs before a fresh dispatch, while probing a
    committed member is pure overhead. Cost of a world is therefore
    ``|absent| + (probes that hit committed members)``. Scanning from the end
    of the request and stopping at the first committed member probes exactly
    one committed member whenever anything committed, and costs
    ``n/2 + n/(n+1)`` under a uniform prior. ``optimal_fence_cost`` confirms
    this is optimal for every ``n <= 10``. The worst case is ``n`` (nothing
    committed: every member must be fenced).
    """
    return n / 2 + n / (n + 1)


def atomic_fence_expected_cost(n: int) -> float:
    """One probe identifies the world. With probability 1/2 nothing committed
    and the remaining ``n-1`` members still need a fence: expected ``(n+1)/2``."""
    return (n + 1) / 2


@lru_cache(maxsize=None)
def optimal_fence_cost(B: Family, n: int, fenced: int = 0) -> float:
    """Expected per-key-finality calls (probes plus fences of absent members
    not already probed). ``fenced`` is a bitmask of items already probed."""
    if len(B) == 1:
        (world,) = B
        return float(sum(1 for i in range(n) if i not in world and not (fenced >> i) & 1))
    best = float("inf")
    for i in unresolved(B):
        bit = fenced | (1 << i)
        b1 = condition(B, i, True)
        b0 = condition(B, i, False)
        c = 1.0 + (len(b1) / len(B)) * optimal_fence_cost(b1, n, bit) + (len(b0) / len(B)) * optimal_fence_cost(b0, n, bit)
        if c < best:
            best = c
    return best


@lru_cache(maxsize=None)
def worst_case_fence_cost(B: Family, n: int, fenced: int = 0) -> int:
    if len(B) == 1:
        (world,) = B
        return sum(1 for i in range(n) if i not in world and not (fenced >> i) & 1)
    best = None
    for i in unresolved(B):
        bit = fenced | (1 << i)
        c = 1 + max(worst_case_fence_cost(condition(B, i, True), n, bit), worst_case_fence_cost(condition(B, i, False), n, bit))
        best = c if best is None else min(best, c)
    return best


def best_probe(B: Family, n: int, fenced: int, objective: str) -> int:
    """Next item to probe. Ties break toward the smallest index so that the
    atomic class, where every probe is equally good, stays deterministic."""
    best = None
    for i in sorted(unresolved(B)):
        b1 = condition(B, i, True)
        b0 = condition(B, i, False)
        if objective == "fence":
            bit = fenced | (1 << i)
            c = 1.0 + (len(b1) / len(B)) * optimal_fence_cost(b1, n, bit) + (len(b0) / len(B)) * optimal_fence_cost(b0, n, bit)
        elif objective == "probes":
            c = 1.0 + (len(b1) / len(B)) * optimal_probe_cost(b1) + (len(b0) / len(B)) * optimal_probe_cost(b0)
        else:
            raise ValueError(objective)
        if best is None or c < best[0] - 1e-12 or (abs(c - best[0]) <= 1e-12 and i < best[1]):
            best = (c, i)
    if best is None:
        raise ValueError("empty belief")
    return best[1]


def exact_k_count(n: int, k: int) -> int:
    return comb(n, k)
