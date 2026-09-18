"""D1: exhaustive finite regrouping comparison, plus D1-TTL retention extension.

D1 (v0.2 reproduction): for n = 1..4 enumerate every ordered wrapper grouping
as source and destination and every committed prefix of the source order.
Policies: G (group-scoped key), R (stable occurrence key, resend all),
R+ (R that also consults its own ledger), V (verified residualization).

D1-TTL (v0.3): the same cases, but the sink's dedup index is reclaimed
between crash and recovery (finite retention, as documented by commercial
idempotency contracts). Effects remain real. Two knowledge states for the
last committed occurrence: durably confirmed (done) or unconfirmed (held).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent_identity.abstract import (  # noqa: E402
    AbstractSink,
    all_groupings,
    run_destination,
    run_source,
)

POLICIES = ("G", "R", "R+", "V", "Vr", "Vr+E")
ITEMS = "abcd"


def run_case(src, dst, prefix, policy, expire, last_state):
    sink = AbstractSink()
    ledger = run_source(src, prefix, sink, policy, last_state=last_state)
    if expire:
        sink.expire_retention()
    calls = run_destination(dst, sink, policy, ledger, retention_expired=expire)
    counts = sink.effect_counts()
    n = len([m for g in src for m in g])
    duplicate = any(c > 1 for c in counts.values())
    incomplete = any(counts.get(m, 0) == 0 for m in ITEMS[:n])
    unresolved = bool(ledger.unresolved)
    return duplicate, incomplete, unresolved, calls, tuple(counts.get(m, 0) for m in ITEMS[:n])


def enumerate_study(expire: bool, last_state: str):
    summary = {}
    total_cases = 0
    for n in range(1, 5):
        groupings = all_groupings(ITEMS[:n])
        per_policy = {p: {"duplicate": 0, "incomplete": 0, "unresolved": 0, "calls": 0} for p in POLICIES}
        disagreements_R_V = 0
        disagreements_Rplus_V = 0
        cases = 0
        for src in groupings:
            for dst in groupings:
                for prefix in range(n + 1):
                    cases += 1
                    vectors = {}
                    for p in POLICIES:
                        dup, inc, unres, calls, vec = run_case(src, dst, prefix, p, expire, last_state)
                        per_policy[p]["duplicate"] += dup
                        per_policy[p]["incomplete"] += inc
                        per_policy[p]["unresolved"] += unres
                        per_policy[p]["calls"] += calls
                        vectors[p] = vec
                    disagreements_R_V += vectors["R"] != vectors["V"]
                    disagreements_Rplus_V += vectors["R+"] != vectors["V"]
        total_cases += cases
        summary[n] = {
            "plans": len(groupings),
            "cases": cases,
            "policies": per_policy,
            "R_vs_V_vector_disagreements": disagreements_R_V,
            "Rplus_vs_V_vector_disagreements": disagreements_Rplus_V,
        }
    summary["total_cases"] = total_cases
    return summary


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "D1": enumerate_study(expire=False, last_state="done"),
        "D1_lostack": enumerate_study(expire=False, last_state="held_committed"),
        "D1_reserved": enumerate_study(expire=False, last_state="held_uncommitted"),
        "D1_TTL_done": enumerate_study(expire=True, last_state="done"),
        "D1_TTL_lostack": enumerate_study(expire=True, last_state="held_committed"),
        "D1_TTL_reserved": enumerate_study(expire=True, last_state="held_uncommitted"),
    }
    (out_dir / "d1_regrouping.json").write_text(json.dumps(results, indent=2))
    for name, study in results.items():
        print(f"== {name}: total cases {study['total_cases']}")
        agg = Counter()
        for n in range(1, 5):
            row = study[n]
            for p in POLICIES:
                agg[(p, "duplicate")] += row["policies"][p]["duplicate"]
                agg[(p, "incomplete")] += row["policies"][p]["incomplete"]
                agg[(p, "unresolved")] += row["policies"][p]["unresolved"]
                agg[(p, "calls")] += row["policies"][p]["calls"]
            print(
                f"  n={n} plans={row['plans']} cases={row['cases']} "
                + " ".join(
                    f"{p}:dup={row['policies'][p]['duplicate']}" for p in POLICIES
                )
                + f" R!=V:{row['R_vs_V_vector_disagreements']}"
            )
        for p in POLICIES:
            print(
                f"  {p}: duplicates={agg[(p, 'duplicate')]} incomplete={agg[(p, 'incomplete')]} "
                f"calls={agg[(p, 'calls')]}"
            )


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results")
