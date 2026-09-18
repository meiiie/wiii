"""Reproduce every result in results/ (about 15 minutes on one core).

    python3 run_all.py            # everything
    python3 run_all.py quick      # skip the process-crash studies (I1-I6)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def main() -> None:
    quick = "quick" in sys.argv[1:]
    steps = [
        [PY, "-m", "unittest", "discover", "-s", "tests"],
        [PY, "experiments/d1_regrouping.py"],
        [PY, "experiments/m1_faults.py"],
        [PY, "experiments/e_belief.py"],
    ]
    if not quick:
        steps.append([PY, "experiments/runtime_studies.py", "I1", "I2", "I3", "I4", "I5", "I6"])
    for cmd in steps:
        print("::", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=str(ROOT), check=True)


if __name__ == "__main__":
    main()
