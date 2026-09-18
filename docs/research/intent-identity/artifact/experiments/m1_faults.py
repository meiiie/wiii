"""M1: bounded finite-state fault exploration with mutants (see model_checker)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent_identity.model_checker import configurations, explore  # noqa: E402


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for include_retention, label in ((False, "v0.2-model"), (True, "v0.3-model-with-retention")):
        rows = []
        for cfg in configurations(include_retention=include_retention):
            r = explore(cfg)
            rows.append(
                {
                    "configuration": r.name,
                    "states": r.states,
                    "edges": r.edges,
                    "exhausted": r.exhausted,
                    "violation": r.violation,
                    "witness_steps": None if r.witness is None else len(r.witness),
                    "witness": r.witness,
                }
            )
            print(
                f"[{label}] {r.name:32s} states={r.states:6d} edges={r.edges:6d} "
                f"exhausted={r.exhausted} violation={r.violation} "
                f"steps={None if r.witness is None else len(r.witness)}"
            )
            if r.witness:
                for step in r.witness:
                    print("      ", step)
        results[label] = rows
    (out_dir / "m1_faults.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results")
