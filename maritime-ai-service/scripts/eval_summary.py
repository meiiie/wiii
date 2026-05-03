"""Eval recordings summary — operational tool, not a test runner.

Reads the JSONL files written by ``EvalRecorder`` for a given day +
optional org and prints aggregate stats so an operator can spot-check
recording health without spinning up the chat stack.

Full replay (re-running ``ChatOrchestrator.process`` against each
record + diffing the response) lands once Phase 6's
``record=True`` integration ships. This script is the read side of the
contract.

Usage::

    python scripts/eval_summary.py --day 2026-05-03
    python scripts/eval_summary.py --day 2026-05-03 --org org-1
    python scripts/eval_summary.py --base-dir /var/wiii/eval --day 2026-05-03 --as-json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

# Make ``app.*`` importable when this script runs from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.runtime.eval_recorder import EvalRecorder  # noqa: E402


async def _summarise(base_dir: Path, day: str, org: str | None) -> dict:
    recorder = EvalRecorder(base_dir=base_dir)
    sessions = await recorder.list_sessions(org_id=org, day=day)

    total_records = 0
    response_lengths: list[int] = []
    latencies: list[float] = []
    tool_call_count = 0
    sources_count = 0

    per_session: list[dict] = []
    for session_id in sessions:
        records = await recorder.read_session(
            session_id=session_id, org_id=org, day=day
        )
        if not records:
            continue
        per_session.append(
            {
                "session_id": session_id,
                "record_count": len(records),
                "first_timestamp": records[0].timestamp,
                "last_timestamp": records[-1].timestamp,
            }
        )
        total_records += len(records)
        for r in records:
            if r.response:
                response_lengths.append(len(r.response))
            latency = r.metadata.get("latency_ms")
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))
            tool_call_count += len(r.tool_calls)
            sources_count += len(r.sources)

    summary: dict = {
        "base_dir": str(base_dir),
        "day": day,
        "org": org or "_personal",
        "session_count": len(per_session),
        "record_count": total_records,
        "tool_call_count": tool_call_count,
        "sources_count": sources_count,
        "response_length": _stats(response_lengths),
        "latency_ms": _stats(latencies),
        "sessions": per_session,
    }
    return summary


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None}
    sorted_values = sorted(values)
    p95_index = max(0, int(round(0.95 * (len(sorted_values) - 1))))
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "p95": round(sorted_values[p95_index], 2),
    }


def _print_human(summary: dict) -> None:
    print(f"Day: {summary['day']}  Org: {summary['org']}")
    print(f"Base dir: {summary['base_dir']}")
    print(
        f"Sessions: {summary['session_count']}  "
        f"Records: {summary['record_count']}  "
        f"Tool calls: {summary['tool_call_count']}  "
        f"Sources: {summary['sources_count']}"
    )
    if summary["response_length"]["n"]:
        rl = summary["response_length"]
        print(
            "Response length (chars): "
            f"mean={rl['mean']} median={rl['median']} p95={rl['p95']} (n={rl['n']})"
        )
    if summary["latency_ms"]["n"]:
        lat = summary["latency_ms"]
        print(
            "Latency (ms): "
            f"mean={lat['mean']} median={lat['median']} p95={lat['p95']} (n={lat['n']})"
        )
    if summary["sessions"]:
        print("\nSessions:")
        for s in summary["sessions"]:
            print(
                f"  {s['session_id']:32s}  "
                f"records={s['record_count']:4d}  "
                f"first={s['first_timestamp']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-dir",
        default="eval_recordings",
        help="Base directory containing eval JSONL partitions (default: eval_recordings).",
    )
    parser.add_argument(
        "--day",
        required=True,
        help="Partition day in YYYY-MM-DD form.",
    )
    parser.add_argument(
        "--org",
        default=None,
        help="Org ID to scope the summary; omit for the personal partition.",
    )
    parser.add_argument(
        "--as-json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        print(f"[eval_summary] base_dir does not exist: {base_dir}", file=sys.stderr)
        return 2

    summary = asyncio.run(_summarise(base_dir, args.day, args.org))

    if args.as_json:
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
