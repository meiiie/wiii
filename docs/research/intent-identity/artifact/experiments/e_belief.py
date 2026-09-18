"""E1-E4: exploratory outcome-evidence studies (exact finite-domain checks).

E1  frontier rule vs brute force over all 65,535 nonempty belief families on
    four occurrences and all 16 fresh-dispatch sets (v0.2 reproduction).
E2  two-obligation correlation witness (v0.2 reproduction).
E3  exact-cardinality families n = 2..10: closed form vs enumeration vs DP
    oracle (v0.2 reproduction; oracle for n <= 8, here extended to n <= 10).
E4  (v0.3) batch-semantics classes: for a request over n items whose response
    was lost, compare the ternary-journal cost (n probes), the optimal cost
    given the retained request structure (atomic / prefix / exact-k), and the
    break-even cost of a single bulk list query.
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent_identity.belief import (  # noqa: E402
    atomic_family,
    certainly_absent,
    completes_all_worlds,
    exact_k_expected_cost,
    exact_k_family,
    family,
    independent_family,
    optimal_probe_cost,
    prefix_expected_cost,
    prefix_family,
    prefix_worst_cost,
    safe_fresh_dispatch_bruteforce,
    ternary_family,
    ternary_projection,
    worst_case_probe_cost,
)


def e1(n: int = 4) -> dict:
    items = list(range(n))
    all_worlds = [frozenset(s) for r in range(n + 1) for s in combinations(items, r)]
    all_sets = all_worlds
    checks = mismatches = completion_mismatch = nonempty_frontier = 0
    families = 0
    for mask in range(1, 1 << len(all_worlds)):
        B = frozenset(w for i, w in enumerate(all_worlds) if mask >> i & 1)
        families += 1
        F = certainly_absent(B, n)
        if F:
            nonempty_frontier += 1
        for S in all_sets:
            checks += 1
            rule = S <= F
            brute = safe_fresh_dispatch_bruteforce(B, S)
            if rule != brute:
                mismatches += 1
            # completion-iff-singleton: some fixed S completes every world iff |B| == 1
        exists = any(completes_all_worlds(B, S, n) for S in all_sets)
        if exists != (len(B) == 1):
            completion_mismatch += 1
    return {
        "n": n,
        "nonempty_families": families,
        "safety_checks": checks,
        "frontier_rule_mismatches": mismatches,
        "completion_iff_singleton_mismatches": completion_mismatch,
        "families_with_nonempty_safe_dispatch": nonempty_frontier,
    }


def e2() -> dict:
    B1 = family([{0}, {1}])
    B2 = family([set(), {0}, {1}, {0, 1}])
    return {
        "B1_projection": ternary_projection(B1, 2),
        "B2_projection": ternary_projection(B2, 2),
        "B1_optimal_probes": optimal_probe_cost(B1),
        "B2_optimal_probes": optimal_probe_cost(B2),
        "same_projection": ternary_projection(B1, 2) == ternary_projection(B2, 2),
        "same_safe_frontier": certainly_absent(B1, 2) == certainly_absent(B2, 2),
    }


def e3(max_n: int = 10, oracle_max_n: int = 10) -> list[dict]:
    rows = []
    for n in range(2, max_n + 1):
        for k in range(1, n):
            B = exact_k_family(n, k)
            closed = exact_k_expected_cost(n, k)
            row = {"n": n, "k": k, "worlds": len(B), "all_item_ablation": n, "closed_form": round(closed, 6)}
            if n <= oracle_max_n:
                row["oracle"] = round(optimal_probe_cost(B), 6)
                row["oracle_matches_closed_form"] = abs(row["oracle"] - closed) < 1e-6
            rows.append(row)
    return rows


def simulate_fence_accounting(B, n):
    """Run the min-expected-probe policy in every world of B (uniform); each
    probe is a per-key fence, and every absent member not yet fenced must be
    fenced before its fresh dispatch. Returns mean and max total fences."""
    from intent_identity.belief import condition, unresolved

    totals = []
    for world in B:
        cur = B
        fenced = set()
        while len(cur) > 1:
            best = None
            for i in sorted(unresolved(cur)):
                b1, b0 = condition(cur, i, True), condition(cur, i, False)
                c = 1.0 + (len(b1) / len(cur)) * optimal_probe_cost(b1) + (len(b0) / len(cur)) * optimal_probe_cost(b0)
                if best is None or c < best[0]:
                    best = (c, i)
            i = best[1]
            fenced.add(i)
            cur = condition(cur, i, i in world)
        absent = set(range(n)) - world
        totals.append(len(fenced) + len(absent - fenced))
    return sum(totals) / len(totals), max(totals)


def e4(max_n: int = 10) -> list[dict]:
    rows = []
    for n in range(1, max_n + 1):
        for name, B in (("atomic", atomic_family(n)), ("prefix", prefix_family(n)), ("independent", independent_family(n) if n <= 8 else None)):
            if B is None:
                continue
            T = ternary_family(B, n)
            row = {
                "n": n,
                "semantics": name,
                "worlds": len(B),
                "ternary_projection_all_unknown": all(x == "unknown" for x in ternary_projection(B, n)),
                "ternary_journal_expected_probes": optimal_probe_cost(T) if n <= 8 else float(n),
                "structured_journal_expected_probes": round(optimal_probe_cost(B), 6),
                "structured_journal_worst_probes": worst_case_probe_cost(B),
            }
            if name == "prefix":
                row["closed_form_expected"] = round(prefix_expected_cost(n), 6)
                row["closed_form_worst"] = prefix_worst_cost(n)
                row["closed_form_matches"] = abs(row["closed_form_expected"] - row["structured_journal_expected_probes"]) < 1e-9
            row["bulk_list_query_breakeven_cost"] = round(row["ternary_journal_expected_probes"] - row["structured_journal_expected_probes"], 6)
            mean_f, max_f = simulate_fence_accounting(B, n)
            row["structured_perkey_fence_expected_calls"] = round(mean_f, 6)
            row["structured_perkey_fence_worst_calls"] = max_f
            row["ternary_perkey_fence_calls"] = n
            rows.append(row)
    return rows


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"E1": e1(), "E2": e2(), "E3": e3(), "E4": e4()}
    (out_dir / "e_belief.json").write_text(json.dumps(res, indent=2, default=list))
    print("E1", res["E1"])
    print("E2", res["E2"])
    print("E3 (n,k,worlds,closed,oracle,match):")
    for r in res["E3"]:
        print("   ", r["n"], r["k"], r["worlds"], r["closed_form"], r.get("oracle"), r.get("oracle_matches_closed_form"))
    print("E4 (n,semantics,worlds,ternary,structured,worst,closed):")
    for r in res["E4"]:
        print("   ", r["n"], r["semantics"], r["worlds"], r["ternary_journal_expected_probes"], r["structured_journal_expected_probes"], r["structured_journal_worst_probes"], r.get("closed_form_expected"), r.get("closed_form_matches"), "fence-acct:", r["structured_perkey_fence_expected_calls"], r["structured_perkey_fence_worst_calls"])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results")
