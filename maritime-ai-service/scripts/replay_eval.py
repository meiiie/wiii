"""Replay recorded eval JSONL turns against the live ChatOrchestrator.

Phase 10 of the runtime migration epic (issue #207). Reads JSONL turn
snapshots written by ``EvalRecorder`` (Phase 6) and re-issues each turn
through ``ChatOrchestrator.process()`` so the response is regenerated
with whatever code is on the current branch. Each replayed turn is
diffed against the original via ``diff_records`` and the totals are
written to a JSON or HTML report.

This is the moat tool from Anthropic's "Demystifying evals" piece:
production runtime + replay = regression net. Same code path runs the
production turn AND replays it, so there is no separate "eval system" to
drift from production behaviour.

Usage::

    # JSON report
    python scripts/replay_eval.py --day 2026-05-03 --report-out replay.json

    # HTML report
    python scripts/replay_eval.py --day 2026-05-03 --report-out replay.html

    # Filter by org and limit (for canary scope)
    python scripts/replay_eval.py --day 2026-05-03 --org org-1 --limit 50 \\
        --report-out canary-replay.html

    # Dry-run: read records + compute stats only, no live orchestrator call
    python scripts/replay_eval.py --day 2026-05-03 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Make ``app.*`` importable when this script runs from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.runtime.eval_recorder import (  # noqa: E402
    EvalRecord,
    EvalRecorder,
    diff_records,
)

logger = logging.getLogger("eval_replay")


REGRESSION_THRESHOLDS = {
    "token_jaccard_min": 0.85,
    "sources_overlap_min": 0.70,
    "latency_delta_max_ms": 5000,
}


async def _replay_one(
    record: EvalRecord, dry_run: bool
) -> dict[str, Any]:
    """Replay a single record. Returns a diff dict with metadata."""
    if dry_run:
        # Fake a perfect-match replay so the report exercise still works.
        replayed = {
            "response": record.response,
            "tool_calls": record.tool_calls,
            "sources": record.sources,
            "latency_ms": record.metadata.get("latency_ms", 0),
        }
        diff = diff_records(record, replayed)
        diff["_dry_run"] = True
        diff["record_id"] = record.record_id
        diff["session_id"] = record.session_id
        return diff

    try:
        from app.models.schemas import ChatRequest
        from app.services.chat_orchestrator import ChatOrchestrator
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to import ChatOrchestrator: %s", exc)
        return {
            "record_id": record.record_id,
            "session_id": record.session_id,
            "_error": f"import-failed: {type(exc).__name__}: {exc}",
        }

    request_payload = dict(record.request)
    request = ChatRequest(
        message=request_payload.get("message", ""),
        user_id=request_payload.get("user_id", record.session_id),
        role=request_payload.get("role", "student"),
        domain_id=request_payload.get("domain_id"),
        organization_id=request_payload.get("organization_id"),
    )

    orchestrator = ChatOrchestrator()
    started = time.monotonic()
    try:
        response = await orchestrator.process(request, record=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "record_id": record.record_id,
            "session_id": record.session_id,
            "_error": f"replay-failed: {type(exc).__name__}: {exc}",
        }

    latency_ms = int((time.monotonic() - started) * 1000)
    replayed = {
        "response": getattr(response, "response", "") or "",
        "tool_calls": (response.metadata or {}).get("tool_calls", []),
        "sources": [
            s.model_dump() if hasattr(s, "model_dump") else dict(s)
            for s in (getattr(response, "sources", None) or [])
        ],
        "latency_ms": latency_ms,
    }
    diff = diff_records(record, replayed)
    diff["record_id"] = record.record_id
    diff["session_id"] = record.session_id
    diff["replay_latency_ms"] = latency_ms
    return diff


def _flag_regressions(diffs: list[dict]) -> list[dict]:
    """Return only the diffs that fall outside the regression thresholds."""
    flagged: list[dict] = []
    for d in diffs:
        if "_error" in d:
            flagged.append(d)
            continue
        bad = []
        if d.get("token_jaccard", 1.0) < REGRESSION_THRESHOLDS["token_jaccard_min"]:
            bad.append("token_jaccard")
        if d.get("sources_overlap", 1.0) < REGRESSION_THRESHOLDS["sources_overlap_min"]:
            bad.append("sources_overlap")
        if d.get("latency_delta_ms", 0) > REGRESSION_THRESHOLDS["latency_delta_max_ms"]:
            bad.append("latency_delta_ms")
        if bad:
            flagged.append({**d, "_flags": bad})
    return flagged


def _aggregate(diffs: list[dict]) -> dict:
    jaccards = [d["token_jaccard"] for d in diffs if "token_jaccard" in d]
    overlaps = [d["sources_overlap"] for d in diffs if "sources_overlap" in d]
    latency_deltas = [
        d["latency_delta_ms"] for d in diffs if "latency_delta_ms" in d
    ]
    tool_match_count = sum(1 for d in diffs if d.get("tool_calls_match"))
    error_count = sum(1 for d in diffs if "_error" in d)

    return {
        "total_records": len(diffs),
        "errors": error_count,
        "tool_calls_match_rate": (
            round(tool_match_count / max(1, len(diffs) - error_count), 3)
            if diffs
            else 0.0
        ),
        "token_jaccard": _stats(jaccards),
        "sources_overlap": _stats(overlaps),
        "latency_delta_ms": _stats(latency_deltas),
    }


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    sorted_values = sorted(values)
    p95_index = max(0, int(round(0.95 * (len(sorted_values) - 1))))
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "p95": round(sorted_values[p95_index], 3),
    }


def _render_html(report: dict) -> str:
    agg = report["aggregate"]
    flags = report["flagged"]
    rows: list[str] = []
    for f in flags[:200]:
        rid = html.escape(str(f.get("record_id", "")))
        sid = html.escape(str(f.get("session_id", "")))
        if "_error" in f:
            rows.append(
                f"<tr class='err'><td>{sid}</td><td>{rid}</td>"
                f"<td colspan='4'>error: {html.escape(str(f['_error']))}</td></tr>"
            )
            continue
        flags_str = html.escape(",".join(f.get("_flags", [])))
        rows.append(
            "<tr>"
            f"<td>{sid}</td>"
            f"<td>{rid}</td>"
            f"<td>{f.get('token_jaccard', '?'):.3f}</td>"
            f"<td>{f.get('sources_overlap', '?'):.3f}</td>"
            f"<td>{f.get('latency_delta_ms', '?')}</td>"
            f"<td>{flags_str}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows) or "<tr><td colspan='6'>No regressions flagged.</td></tr>"

    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Wiii eval replay — {html.escape(report.get('day', '?'))}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; padding: 2rem; max-width: 1200px; margin: auto; }}
h1 {{ font-size: 1.4rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
th {{ background: #f5f5f5; }}
.summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1rem 0; }}
.card {{ border: 1px solid #ddd; padding: 1rem; border-radius: 4px; }}
.metric {{ font-size: 1.6rem; font-weight: bold; }}
.err td {{ background: #fff0f0; }}
</style>
</head>
<body>
<h1>Wiii eval replay — {html.escape(report.get('day', '?'))} (org={html.escape(report.get('org', '_personal'))})</h1>
<div class="summary">
  <div class="card"><div>Records</div><div class="metric">{agg['total_records']}</div></div>
  <div class="card"><div>Errors</div><div class="metric">{agg['errors']}</div></div>
  <div class="card"><div>Tool match rate</div><div class="metric">{agg['tool_calls_match_rate']:.0%}</div></div>
</div>
<h2>Token Jaccard (response similarity)</h2>
<pre>{html.escape(json.dumps(agg['token_jaccard'], indent=2))}</pre>
<h2>Sources overlap</h2>
<pre>{html.escape(json.dumps(agg['sources_overlap'], indent=2))}</pre>
<h2>Latency delta (ms)</h2>
<pre>{html.escape(json.dumps(agg['latency_delta_ms'], indent=2))}</pre>
<h2>Regressions ({len(flags)} flagged)</h2>
<table>
<tr><th>session_id</th><th>record_id</th><th>token_jaccard</th><th>sources_overlap</th><th>latency_Δ ms</th><th>flags</th></tr>
{rows_html}
</table>
<h2>Thresholds</h2>
<pre>{html.escape(json.dumps(REGRESSION_THRESHOLDS, indent=2))}</pre>
</body>
</html>
"""


async def _run(
    base_dir: Path,
    day: str,
    org: Optional[str],
    limit: Optional[int],
    dry_run: bool,
) -> dict:
    recorder = EvalRecorder(base_dir=base_dir)
    sessions = await recorder.list_sessions(org_id=org, day=day)

    diffs: list[dict] = []
    seen = 0
    for session_id in sessions:
        if limit is not None and seen >= limit:
            break
        records = await recorder.read_session(
            session_id=session_id, org_id=org, day=day
        )
        for record in records:
            if limit is not None and seen >= limit:
                break
            d = await _replay_one(record, dry_run=dry_run)
            diffs.append(d)
            seen += 1

    flagged = _flag_regressions(diffs)
    return {
        "base_dir": str(base_dir),
        "day": day,
        "org": org or "_personal",
        "dry_run": dry_run,
        "aggregate": _aggregate(diffs),
        "flagged": flagged,
        "all_diffs_count": len(diffs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-dir",
        default="eval_recordings",
        help="Base directory containing eval JSONL partitions.",
    )
    parser.add_argument(
        "--day",
        required=True,
        help="Partition day in YYYY-MM-DD form.",
    )
    parser.add_argument("--org", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max records to replay (canary scope).",
    )
    parser.add_argument(
        "--report-out",
        default="-",
        help="Output path for the report (.json or .html). Use '-' for stdout JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip live orchestrator call; pretend replays match the original.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit 1 if any record exceeds the regression thresholds.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        print(f"[replay_eval] base_dir does not exist: {base_dir}", file=sys.stderr)
        return 2

    report = asyncio.run(
        _run(base_dir, args.day, args.org, args.limit, args.dry_run)
    )

    out = args.report_out
    if out == "-":
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif out.endswith(".html"):
        Path(out).write_text(_render_html(report), encoding="utf-8")
        print(f"[replay_eval] HTML report written to {out}", file=sys.stderr)
    else:
        Path(out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[replay_eval] JSON report written to {out}", file=sys.stderr)

    if args.fail_on_regression and report["flagged"]:
        print(
            f"[replay_eval] {len(report['flagged'])} regression(s) flagged",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
