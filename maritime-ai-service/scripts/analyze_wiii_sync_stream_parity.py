#!/usr/bin/env python3
"""
Analyze sync-vs-stream visible thinking parity for Wiii golden-eval reports.

Typical usage:
    python scripts/analyze_wiii_sync_stream_parity.py ^
      --base ..\\.Codex\\reports\\wiii-golden-eval-2026-04-01-030533.json ^
      --overlay ..\\.Codex\\reports\\wiii-golden-eval-2026-04-01-042657.json ^
      --overlay ..\\.Codex\\reports\\wiii-golden-eval-2026-04-01-043218.json
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _turn_key(session_id: str, turn_id: str) -> str:
    return f"{session_id}::{turn_id}"


def _merge_reports(base: dict[str, Any], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    session_map = {
        str(session.get("id") or "").strip(): session
        for session in merged.get("sessions") or []
    }

    for overlay in overlays:
        for overlay_session in overlay.get("sessions") or []:
            session_id = str(overlay_session.get("id") or "").strip()
            if not session_id:
                continue
            target_session = session_map.get(session_id)
            if target_session is None:
                merged.setdefault("sessions", []).append(copy.deepcopy(overlay_session))
                session_map[session_id] = merged["sessions"][-1]
                continue

            target_session.update(
                {
                    "label": overlay_session.get("label", target_session.get("label")),
                    "profile": overlay_session.get("profile", target_session.get("profile")),
                    "coverage": overlay_session.get("coverage", target_session.get("coverage")),
                    "goal": overlay_session.get("goal", target_session.get("goal")),
                    "user_id": overlay_session.get("user_id", target_session.get("user_id")),
                    "sync_session_id": overlay_session.get("sync_session_id", target_session.get("sync_session_id")),
                    "stream_session_id": overlay_session.get("stream_session_id", target_session.get("stream_session_id")),
                }
            )

            target_turn_map = {
                str(turn.get("id") or "").strip(): turn
                for turn in target_session.get("turns") or []
            }
            for overlay_turn in overlay_session.get("turns") or []:
                turn_id = str(overlay_turn.get("id") or "").strip()
                if not turn_id:
                    continue
                target_turn = target_turn_map.get(turn_id)
                if target_turn is None:
                    target_session.setdefault("turns", []).append(copy.deepcopy(overlay_turn))
                    target_turn_map[turn_id] = target_session["turns"][-1]
                    continue
                target_turn.update(copy.deepcopy(overlay_turn))
    return merged


def _sse_event_counts(raw_path: str | None) -> dict[str, int]:
    if not raw_path:
        return {
            "thinking_events": 0,
            "tool_call_events": 0,
            "tool_result_events": 0,
            "action_text_events": 0,
            "answer_events": 0,
        }
    path = Path(raw_path)
    if not path.exists():
        return {
            "thinking_events": 0,
            "tool_call_events": 0,
            "tool_result_events": 0,
            "action_text_events": 0,
            "answer_events": 0,
        }

    counts = {
        "thinking_events": 0,
        "tool_call_events": 0,
        "tool_result_events": 0,
        "action_text_events": 0,
        "answer_events": 0,
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("event:"):
            continue
        event_name = line.split(":", 1)[1].strip().lower()
        if event_name in {"thinking", "thinking_delta", "thinking_start", "thinking_end"}:
            counts["thinking_events"] += 1
        elif event_name == "tool_call":
            counts["tool_call_events"] += 1
        elif event_name == "tool_result":
            counts["tool_result_events"] += 1
        elif event_name == "action_text":
            counts["action_text_events"] += 1
        elif event_name == "answer":
            counts["answer_events"] += 1
    return counts


def _classify_thinking_gap(sync_turn: dict[str, Any], stream_turn: dict[str, Any]) -> str:
    sync_metrics = sync_turn.get("thinking_metrics") or {}
    stream_metrics = stream_turn.get("thinking_metrics") or {}
    sync_len = int(sync_metrics.get("final_length") or len(str(sync_turn.get("thinking") or "").strip()))
    stream_len = int(stream_metrics.get("final_length") or len(str(stream_turn.get("thinking") or "").strip()))

    if sync_len and not stream_len:
        return "stream_missing_visible_thinking"
    if stream_len and not sync_len:
        return "sync_missing_visible_thinking"
    if not sync_len and not stream_len:
        return "both_missing_visible_thinking"
    if stream_len < int(sync_len * 0.7):
        return "stream_thinner_than_sync"
    if sync_len < int(stream_len * 0.7):
        return "stream_richer_than_sync"
    return "parity_close"


def _transport_status(transport: dict[str, Any]) -> str:
    evaluation = transport.get("evaluation") or {}
    failures = evaluation.get("failures") or []
    if failures:
        return "fail"
    return "pass"


def _transport_runtime(transport: dict[str, Any]) -> dict[str, Any]:
    metadata = transport.get("metadata") or {}
    failover = metadata.get("failover") if isinstance(metadata.get("failover"), dict) else {}
    route = failover.get("route") if isinstance(failover.get("route"), list) else []
    route_tokens: list[str] = []
    for hop in route:
        if not isinstance(hop, dict):
            continue
        from_provider = str(hop.get("from_provider") or "").strip()
        to_provider = str(hop.get("to_provider") or "").strip()
        if from_provider and to_provider:
            route_tokens.append(f"{from_provider}->{to_provider}")

    return {
        "provider": metadata.get("provider"),
        "model": metadata.get("model"),
        "processing_time": metadata.get("processing_time", transport.get("processing_time")),
        "failover_switched": bool(failover.get("switched")),
        "failover_reason_code": failover.get("last_reason_code"),
        "failover_route": route_tokens,
    }


def _analyze_report(report: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    by_lane: dict[str, dict[str, int]] = {}
    provider_counts: dict[str, dict[str, int]] = {"sync": {}, "stream": {}}
    model_counts: dict[str, dict[str, int]] = {"sync": {}, "stream": {}}
    processing_times: dict[str, list[float]] = {"sync": [], "stream": []}
    failover_reason_counts: dict[str, int] = {}
    failover_route_counts: dict[str, int] = {}

    def _bump(bucket: dict[str, int], key: str | None) -> None:
        token = str(key or "").strip()
        if not token:
            return
        bucket[token] = bucket.get(token, 0) + 1

    def _record_runtime(transport_name: str, runtime: dict[str, Any]) -> None:
        _bump(provider_counts[transport_name], runtime.get("provider"))
        _bump(model_counts[transport_name], runtime.get("model"))
        try:
            processing_time = float(runtime.get("processing_time"))
        except (TypeError, ValueError):
            processing_time = None
        if processing_time is not None and processing_time >= 0:
            processing_times[transport_name].append(processing_time)
        if runtime.get("failover_switched"):
            _bump(failover_reason_counts, runtime.get("failover_reason_code"))
            for route in runtime.get("failover_route") or []:
                _bump(failover_route_counts, route)

    for session in report.get("sessions") or []:
        session_id = str(session.get("id") or "").strip()
        for turn in session.get("turns") or []:
            turn_id = str(turn.get("id") or "").strip()
            sync_turn = dict(turn.get("sync") or {})
            stream_turn = dict(turn.get("stream") or {})
            if not sync_turn and not stream_turn:
                continue

            lane = str(
                stream_turn.get("agent_type")
                or sync_turn.get("agent_type")
                or ""
            ).strip().lower() or "unknown"
            sync_metrics = sync_turn.get("thinking_metrics") or {}
            stream_metrics = stream_turn.get("thinking_metrics") or {}
            sync_len = int(sync_metrics.get("final_length") or len(str(sync_turn.get("thinking") or "").strip()))
            stream_len = int(stream_metrics.get("final_length") or len(str(stream_turn.get("thinking") or "").strip()))
            stream_counts = _sse_event_counts(stream_turn.get("raw_path"))
            classification = _classify_thinking_gap(sync_turn, stream_turn)
            sync_runtime = _transport_runtime(sync_turn)
            stream_runtime = _transport_runtime(stream_turn)
            _record_runtime("sync", sync_runtime)
            _record_runtime("stream", stream_runtime)

            finding = {
                "session_id": session_id,
                "turn_id": turn_id,
                "prompt": turn.get("prompt") or "",
                "lane": lane,
                "sync_status": _transport_status(sync_turn),
                "stream_status": _transport_status(stream_turn),
                "sync_thinking_len": sync_len,
                "stream_thinking_len": stream_len,
                "classification": classification,
                "sync_provenance_mix": sync_metrics.get("provenance_mix") or [],
                "stream_provenance_mix": stream_metrics.get("provenance_mix") or [],
                "sync_has_tool_continuation": bool(sync_metrics.get("has_tool_continuation")),
                "stream_has_tool_continuation": bool(stream_metrics.get("has_tool_continuation")),
                "sync_rescued_by_final_snapshot": bool(sync_metrics.get("rescued_by_final_snapshot")),
                "stream_rescued_by_final_snapshot": bool(stream_metrics.get("rescued_by_final_snapshot")),
                "sync_failures": (sync_turn.get("evaluation") or {}).get("failures") or [],
                "stream_failures": (stream_turn.get("evaluation") or {}).get("failures") or [],
                "stream_event_counts": stream_counts,
                "stream_raw_path": stream_turn.get("raw_path"),
                "sync_raw_path": sync_turn.get("raw_path"),
                "sync_provider": sync_runtime.get("provider"),
                "stream_provider": stream_runtime.get("provider"),
                "sync_model": sync_runtime.get("model"),
                "stream_model": stream_runtime.get("model"),
                "sync_processing_time": sync_runtime.get("processing_time"),
                "stream_processing_time": stream_runtime.get("processing_time"),
                "sync_failover_switched": sync_runtime.get("failover_switched"),
                "stream_failover_switched": stream_runtime.get("failover_switched"),
                "sync_failover_reason_code": sync_runtime.get("failover_reason_code"),
                "stream_failover_reason_code": stream_runtime.get("failover_reason_code"),
                "sync_failover_route": sync_runtime.get("failover_route") or [],
                "stream_failover_route": stream_runtime.get("failover_route") or [],
            }
            findings.append(finding)

            lane_bucket = by_lane.setdefault(
                lane,
                {
                    "turns": 0,
                    "stream_missing_visible_thinking": 0,
                    "stream_thinner_than_sync": 0,
                    "stream_richer_than_sync": 0,
                    "parity_close": 0,
                    "both_missing_visible_thinking": 0,
                    "sync_missing_visible_thinking": 0,
                },
            )
            lane_bucket["turns"] += 1
            lane_bucket[classification] = lane_bucket.get(classification, 0) + 1

    findings.sort(key=lambda item: (item["lane"], item["session_id"], item["turn_id"]))

    def _mean(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    summary = {
        "turn_count": len(findings),
        "stream_missing_visible_thinking": sum(
            1 for item in findings if item["classification"] == "stream_missing_visible_thinking"
        ),
        "stream_thinner_than_sync": sum(
            1 for item in findings if item["classification"] == "stream_thinner_than_sync"
        ),
        "parity_close": sum(
            1 for item in findings if item["classification"] == "parity_close"
        ),
        "stream_richer_than_sync": sum(
            1 for item in findings if item["classification"] == "stream_richer_than_sync"
        ),
        "both_missing_visible_thinking": sum(
            1 for item in findings if item["classification"] == "both_missing_visible_thinking"
        ),
        "avg_processing_time": {
            "sync": _mean(processing_times["sync"]),
            "stream": _mean(processing_times["stream"]),
        },
        "provider_counts": provider_counts,
        "model_counts": model_counts,
        "failover_reason_counts": failover_reason_counts,
        "failover_route_counts": failover_route_counts,
    }

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "by_lane": by_lane,
        "findings": findings,
    }


def _render_markdown(
    *,
    base_path: Path,
    overlay_paths: list[Path],
    composite_path: Path,
    parity_json_path: Path,
    analysis: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Wiii Sync vs Stream Parity Audit")
    lines.append("")
    lines.append(f"- Generated: `{analysis['generated_at']}`")
    lines.append(f"- Base report: `{base_path}`")
    if overlay_paths:
        lines.append("- Overlays:")
        for path in overlay_paths:
            lines.append(f"  - `{path}`")
    lines.append(f"- Composite report: `{composite_path}`")
    lines.append(f"- Parity JSON: `{parity_json_path}`")
    lines.append("")
    lines.append("## Summary")
    summary = analysis.get("summary") or {}
    for key in (
        "turn_count",
        "stream_missing_visible_thinking",
        "stream_thinner_than_sync",
        "parity_close",
        "stream_richer_than_sync",
        "both_missing_visible_thinking",
    ):
        lines.append(f"- `{key}`: {summary.get(key, 0)}")
    avg_processing = summary.get("avg_processing_time") or {}
    lines.append(f"- `avg_processing_time.sync`: {avg_processing.get('sync')}")
    lines.append(f"- `avg_processing_time.stream`: {avg_processing.get('stream')}")
    provider_counts = summary.get("provider_counts") or {}
    model_counts = summary.get("model_counts") or {}
    lines.append(f"- `provider_counts.sync`: {provider_counts.get('sync', {})}")
    lines.append(f"- `provider_counts.stream`: {provider_counts.get('stream', {})}")
    lines.append(f"- `model_counts.sync`: {model_counts.get('sync', {})}")
    lines.append(f"- `model_counts.stream`: {model_counts.get('stream', {})}")
    lines.append(f"- `failover_reason_counts`: {summary.get('failover_reason_counts', {})}")
    lines.append(f"- `failover_route_counts`: {summary.get('failover_route_counts', {})}")
    lines.append("")
    lines.append("## Lane Breakdown")
    for lane, bucket in sorted((analysis.get("by_lane") or {}).items()):
        lines.append(f"- `{lane}`: turns={bucket.get('turns', 0)}, stream_missing={bucket.get('stream_missing_visible_thinking', 0)}, stream_thinner={bucket.get('stream_thinner_than_sync', 0)}, parity_close={bucket.get('parity_close', 0)}, stream_richer={bucket.get('stream_richer_than_sync', 0)}")
    lines.append("")
    lines.append("## Findings")
    for item in analysis.get("findings") or []:
        lines.append(
            f"- `{item['lane']}` / `{item['session_id']}` / `{item['turn_id']}`: "
            f"{item['classification']} "
            f"(sync={item['sync_thinking_len']}, stream={item['stream_thinking_len']}, "
            f"sync_status={item['sync_status']}, stream_status={item['stream_status']}, "
            f"sync_provider={item.get('sync_provider')}, stream_provider={item.get('stream_provider')}, "
            f"sync_time={item.get('sync_processing_time')}, stream_time={item.get('stream_processing_time')})"
        )
        if item.get("stream_failures"):
            lines.append(f"  stream_failures={item['stream_failures']}")
        if item.get("sync_failures"):
            lines.append(f"  sync_failures={item['sync_failures']}")
        if item.get("sync_failover_route") or item.get("stream_failover_route"):
            lines.append(
                "  "
                f"sync_failover={item.get('sync_failover_route', [])} "
                f"stream_failover={item.get('stream_failover_route', [])}"
            )
        counts = item.get("stream_event_counts") or {}
        lines.append(
            "  "
            f"stream_events(thinking={counts.get('thinking_events', 0)}, "
            f"tool_call={counts.get('tool_call_events', 0)}, "
            f"tool_result={counts.get('tool_result_events', 0)}, "
            f"action_text={counts.get('action_text_events', 0)}, "
            f"answer={counts.get('answer_events', 0)})"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base full-core golden report JSON")
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="Overlay session report JSON(s) to apply on top of base",
    )
    parser.add_argument(
        "--output-stem",
        default="sync-stream-parity-audit",
        help="Output stem inside .Codex/reports",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    base_path = Path(args.base).resolve()
    overlay_paths = [Path(item).resolve() for item in args.overlay]
    report_dir = Path(__file__).resolve().parents[2] / ".Codex" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    base_report = _load_report(base_path)
    overlay_reports = [_load_report(path) for path in overlay_paths]
    composite = _merge_reports(base_report, overlay_reports)
    analysis = _analyze_report(composite)

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    composite_path = report_dir / f"{args.output_stem}-composite-{stamp}.json"
    parity_json_path = report_dir / f"{args.output_stem}-{stamp}.json"
    parity_md_path = report_dir / f"{args.output_stem}-{stamp}.md"

    composite_path.write_text(json.dumps(composite, ensure_ascii=False, indent=2), encoding="utf-8")
    parity_json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    parity_md_path.write_text(
        _render_markdown(
            base_path=base_path,
            overlay_paths=overlay_paths,
            composite_path=composite_path,
            parity_json_path=parity_json_path,
            analysis=analysis,
        ),
        encoding="utf-8",
    )

    print(composite_path)
    print(parity_json_path)
    print(parity_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
