#!/usr/bin/env python3
"""
Run the Wiii golden evaluation manifest and emit a regression JSON report.

The report is designed for iterative quality review, not strict benchmarking:
- supports sync + stream
- preserves multi-turn session continuity
- carries raw paths for deep debugging
- adds light expectation checks (answer/thinking/tool-trace/duplication/agent hints)

Usage:
    python scripts/probe_wiii_golden_eval.py --profiles core
    python scripts/probe_wiii_golden_eval.py --profiles core,extended
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import httpx


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_KEY = "local-dev-key"
DEFAULT_USER_ID = "codex-wiii-golden"
DEFAULT_TRANSPORT_MODE = "asgi"
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "wiii_golden_eval_manifest.json"
_AGENT_CANONICAL_ALIASES = {
    "tutor_agent": "tutor",
    "memory_agent": "memory",
    "rag_agent": "rag",
    "product_search_agent": "product_search",
    "code_studio_agent": "code_studio",
}


def _slugify_eval_token(value: str) -> str:
    token = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or ""))
    compact = "-".join(part for part in token.split("-") if part)
    return compact or "session"


def _build_session_user_id(*, base_user_id: str, stamp: str, session_key: str) -> str:
    return f"{base_user_id}-{_slugify_eval_token(stamp)}-{_slugify_eval_token(session_key)}"


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def _report_dir() -> Path:
    return Path(__file__).resolve().parents[2] / ".Codex" / "reports"


def _write_report_snapshot(path: Path, report: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _raw_text_from_sse(lines: list[str]) -> str:
    return "\n".join(lines).strip() + ("\n" if lines else "")


def _extract_answer_chunks(events: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in events:
        if item.get("event") != "answer":
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            chunks.append(str(payload.get("content") or ""))
        else:
            chunks.append(str(payload or ""))
    return "".join(chunks).strip()


def _extract_answer_events(events: list[dict[str, Any]]) -> list[str]:
    chunks: list[str] = []
    for item in events:
        if item.get("event") != "answer":
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            chunks.append(str(payload.get("content") or ""))
        else:
            chunks.append(str(payload or ""))
    return [chunk for chunk in chunks if chunk]


def _extract_thinking(events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in events:
        if item.get("event") not in {"thinking", "thinking_delta"}:
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            content = str(payload.get("content") or "").strip()
        else:
            content = str(payload or "").strip()
        if content:
            parts.append(content)

    block_parts = [part for part in parts if "\n" in part or len(part) > 60]
    if block_parts:
        return "\n\n".join(block_parts).strip()
    return "".join(parts).strip()


def _extract_metadata(events: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(events):
        if item.get("event") == "metadata" and isinstance(item.get("data"), dict):
            return item["data"]
    return {}


def _pick_richer_thinking(primary: str | None, fallback: str | None) -> str:
    primary_text = str(primary or "").strip()
    fallback_text = str(fallback or "").strip()
    if not primary_text:
        return fallback_text
    if not fallback_text:
        return primary_text
    return fallback_text if len(fallback_text) > len(primary_text) else primary_text


def _extract_lifecycle_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    lifecycle = metadata.get("thinking_lifecycle")
    return lifecycle if isinstance(lifecycle, dict) else {}


def _thinking_from_metadata(metadata: dict[str, Any]) -> str:
    lifecycle = _extract_lifecycle_snapshot(metadata)
    lifecycle_text = str(lifecycle.get("final_text") or "").strip()
    if lifecycle_text:
        return lifecycle_text
    return str(metadata.get("thinking_content") or metadata.get("thinking") or "").strip()


def _lifecycle_metrics(metadata: dict[str, Any]) -> dict[str, Any]:
    lifecycle = _extract_lifecycle_snapshot(metadata)
    segments = lifecycle.get("segments") if isinstance(lifecycle.get("segments"), list) else []
    return {
        "segment_count": int(lifecycle.get("segment_count") or len(segments) or 0),
        "live_length": int(lifecycle.get("live_length") or 0),
        "final_length": int(lifecycle.get("final_length") or 0),
        "provenance_mix": list(lifecycle.get("provenance_mix") or []),
        "phases": list(lifecycle.get("phases") or []),
        "has_tool_continuation": bool(lifecycle.get("has_tool_continuation")),
        "rescued_by_final_snapshot": (
            int(lifecycle.get("final_length") or 0) > int(lifecycle.get("live_length") or 0)
        ),
    }


def _extract_stream_tool_trace(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    for item in events:
        event_name = str(item.get("event") or "").strip().lower()
        payload = item.get("data")
        if event_name == "tool_call" and isinstance(payload, dict):
            content = payload.get("content") or {}
            trace.append(
                {
                    "kind": "call",
                    "title": str(content.get("name") or "tool"),
                    "body": json.dumps(content.get("args") or {}, ensure_ascii=False, indent=2),
                }
            )
        elif event_name == "tool_result" and isinstance(payload, dict):
            content = payload.get("content") or {}
            trace.append(
                {
                    "kind": "result",
                    "title": str(content.get("name") or "tool"),
                    "body": str(content.get("result") or "").strip(),
                }
            )
        elif event_name == "action_text" and isinstance(payload, dict):
            trace.append(
                {
                    "kind": "action",
                    "title": str(payload.get("node") or "action"),
                    "body": str(payload.get("content") or "").strip(),
                }
            )
    return trace


def _extract_sync_tool_trace(metadata: dict[str, Any]) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    for tool in metadata.get("tools_used") or []:
        trace.append(
            {
                "kind": "call",
                "title": str(tool.get("name") or "tool"),
                "body": str(tool.get("description") or "").strip(),
            }
        )
    return trace


def _extract_first_index(events: list[dict[str, Any]], target_event: str) -> int | None:
    for idx, item in enumerate(events):
        if item.get("event") == target_event:
            return idx
    return None


def _extract_first_synth_index(events: list[dict[str, Any]]) -> int | None:
    for idx, item in enumerate(events):
        if item.get("event") != "status":
            continue
        payload = item.get("data")
        if not isinstance(payload, dict):
            continue
        step = str(payload.get("step") or "").strip().lower()
        content = str(payload.get("content") or "").strip().lower()
        if "synth" in step or "tong hop" in content or "tổng hợp" in content or "khâu lại" in content:
            return idx
    return None


def _detect_language(text: str) -> str | None:
    try:
        from app.prompts.prompt_context_utils import detect_message_language

        return detect_message_language(text)
    except Exception:
        return None


def _normalize_expectations(turn_def: dict[str, Any], transport: str) -> dict[str, Any]:
    expect = dict(turn_def.get("expect") or {})
    merged = dict(expect.get("common") or {})
    merged.update(expect.get(transport) or {})
    return merged


def _canonicalize_agent_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    return _AGENT_CANONICAL_ALIASES.get(normalized, normalized)


def _evaluate_turn(
    *,
    result: dict[str, Any],
    turn_def: dict[str, Any],
    transport: str,
) -> dict[str, Any]:
    expectations = _normalize_expectations(turn_def, transport)
    failures: list[str] = []
    checks: dict[str, Any] = {}

    answer = str(result.get("answer") or "").strip()
    thinking = str(result.get("thinking") or "").strip()
    tool_trace = result.get("tool_trace") or []
    agent_type = str(result.get("agent_type") or "").strip().lower()
    canonical_agent_type = _canonicalize_agent_label(agent_type)

    if expectations.get("should_have_answer"):
        checks["has_answer"] = bool(answer)
        if not checks["has_answer"]:
            failures.append("missing_answer")

    if expectations.get("should_have_visible_thinking"):
        checks["has_visible_thinking"] = bool(thinking)
        if not checks["has_visible_thinking"]:
            failures.append("missing_visible_thinking")

    if expectations.get("should_have_tool_trace"):
        checks["has_tool_trace"] = bool(tool_trace)
        if not checks["has_tool_trace"]:
            failures.append("missing_tool_trace")

    if expectations.get("should_not_duplicate_answer"):
        duplicate = bool(result.get("duplicate_answer_tail"))
        checks["duplicate_answer_tail"] = duplicate
        if duplicate:
            failures.append("duplicate_answer_tail")

    expected_agents = [
        _canonicalize_agent_label(str(item).strip().lower())
        for item in expectations.get("agent_any_of") or []
        if str(item).strip()
    ]
    if expected_agents:
        checks["agent_matches"] = canonical_agent_type in expected_agents
        if not checks["agent_matches"]:
            failures.append(f"agent_mismatch:{agent_type or 'none'}")

    checks["answer_language"] = _detect_language(answer)
    checks["thinking_language"] = _detect_language(thinking) if thinking else None

    return {
        "expectations": expectations,
        "checks": checks,
        "failures": failures,
        "passed": not failures,
    }


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Manifest must contain a non-empty 'sessions' list")
    return manifest


def select_sessions(
    manifest: dict[str, Any],
    *,
    profiles: list[str] | None = None,
    session_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    allowed_profiles = {item.strip().lower() for item in profiles or [] if item.strip()}
    allowed_ids = {item.strip() for item in session_ids or [] if item.strip()}

    for session in manifest.get("sessions") or []:
        session_id = str(session.get("id") or "").strip()
        profile = str(session.get("profile") or "core").strip().lower()
        if allowed_ids and session_id not in allowed_ids:
            continue
        if allowed_profiles and profile not in allowed_profiles:
            continue
        selected.append(session)
    return selected


def filter_session_turns(
    sessions: list[dict[str, Any]],
    *,
    turn_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    allowed_turn_ids = {item.strip() for item in turn_ids or [] if item.strip()}
    if not allowed_turn_ids:
        return sessions

    filtered_sessions: list[dict[str, Any]] = []
    for session in sessions:
        turns = [
            turn
            for turn in (session.get("turns") or [])
            if str(turn.get("id") or "").strip() in allowed_turn_ids
        ]
        if not turns:
            continue
        cloned = dict(session)
        cloned["turns"] = turns
        filtered_sessions.append(cloned)
    return filtered_sessions


def summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    total_turns = 0
    total_transports = 0
    passed_transports = 0
    failed_transports = 0
    duplicate_tail_count = 0
    stream_thinking_turns = 0
    stream_tool_trace_turns = 0
    lifecycle_rescue_turns = 0
    lifecycle_tool_continuation_turns = 0
    provider_counts: dict[str, dict[str, int]] = {"sync": {}, "stream": {}}
    model_counts: dict[str, dict[str, int]] = {"sync": {}, "stream": {}}
    processing_times: dict[str, list[float]] = {"sync": [], "stream": []}
    failover_reason_counts: dict[str, int] = {}
    failover_route_counts: dict[str, int] = {}
    failover_switch_transports = 0

    def _bump(bucket: dict[str, int], key: str | None) -> None:
        token = str(key or "").strip()
        if not token:
            return
        bucket[token] = bucket.get(token, 0) + 1

    def _record_processing_time(transport_name: str, transport: dict[str, Any]) -> None:
        raw_value = transport.get("processing_time")
        if raw_value is None:
            raw_value = (transport.get("metadata") or {}).get("processing_time")
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            return
        if numeric >= 0:
            processing_times[transport_name].append(numeric)

    def _record_runtime_metadata(transport_name: str, transport: dict[str, Any]) -> bool:
        metadata = transport.get("metadata") or {}
        _bump(provider_counts[transport_name], metadata.get("provider"))
        _bump(model_counts[transport_name], metadata.get("model"))
        failover = metadata.get("failover") if isinstance(metadata.get("failover"), dict) else {}
        if not failover:
            return False
        _bump(failover_reason_counts, failover.get("last_reason_code"))
        route = failover.get("route") if isinstance(failover.get("route"), list) else []
        for hop in route:
            if not isinstance(hop, dict):
                continue
            from_provider = str(hop.get("from_provider") or "").strip()
            to_provider = str(hop.get("to_provider") or "").strip()
            if from_provider and to_provider:
                _bump(failover_route_counts, f"{from_provider}->{to_provider}")
        return bool(failover.get("switched"))

    for session in report.get("sessions") or []:
        for turn in session.get("turns") or []:
            total_turns += 1
            for transport_name in ("sync", "stream"):
                transport = turn.get(transport_name) or {}
                evaluation = transport.get("evaluation") or {}
                if not transport:
                    continue
                total_transports += 1
                if evaluation.get("passed"):
                    passed_transports += 1
                else:
                    failed_transports += 1
                _record_processing_time(transport_name, transport)
                if _record_runtime_metadata(transport_name, transport):
                    failover_switch_transports += 1
                thinking_metrics = transport.get("thinking_metrics") or {}
                if thinking_metrics.get("rescued_by_final_snapshot"):
                    lifecycle_rescue_turns += 1
                if thinking_metrics.get("has_tool_continuation"):
                    lifecycle_tool_continuation_turns += 1
                if transport_name == "stream":
                    if transport.get("duplicate_answer_tail"):
                        duplicate_tail_count += 1
                    if str(transport.get("thinking") or "").strip():
                        stream_thinking_turns += 1
                    if transport.get("tool_trace"):
                        stream_tool_trace_turns += 1

    def _mean(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _max(values: list[float]) -> float | None:
        if not values:
            return None
        return round(max(values), 3)

    return {
        "session_count": len(report.get("sessions") or []),
        "turn_count": total_turns,
        "transport_count": total_transports,
        "passed_transport_count": passed_transports,
        "failed_transport_count": failed_transports,
        "stream_duplicate_answer_count": duplicate_tail_count,
        "stream_visible_thinking_turns": stream_thinking_turns,
        "stream_tool_trace_turns": stream_tool_trace_turns,
        "lifecycle_rescue_turns": lifecycle_rescue_turns,
        "lifecycle_tool_continuation_turns": lifecycle_tool_continuation_turns,
        "transport_avg_processing_time": {
            "sync": _mean(processing_times["sync"]),
            "stream": _mean(processing_times["stream"]),
        },
        "transport_max_processing_time": {
            "sync": _max(processing_times["sync"]),
            "stream": _max(processing_times["stream"]),
        },
        "provider_counts": provider_counts,
        "model_counts": model_counts,
        "failover_switch_transports": failover_switch_transports,
        "failover_reason_counts": failover_reason_counts,
        "failover_route_counts": failover_route_counts,
    }


@asynccontextmanager
async def _build_probe_client(
    *,
    transport_mode: str,
    base_url: str,
    timeout: float,
) -> AsyncIterator[tuple[httpx.AsyncClient, str, dict[str, Any]]]:
    if transport_mode == "http":
        async with httpx.AsyncClient(timeout=timeout) as client:
            yield client, base_url.rstrip("/"), {"transport_mode": "http"}
        return

    runtime_capture = io.StringIO()
    with contextlib.redirect_stdout(runtime_capture), contextlib.redirect_stderr(runtime_capture):
        from app.main import app as fastapi_app

        lifespan_cm = fastapi_app.router.lifespan_context(fastapi_app)
        await lifespan_cm.__aenter__()

    transport = httpx.ASGITransport(app=fastapi_app)
    diagnostics = {
        "transport_mode": "asgi",
        "runtime_capture": runtime_capture.getvalue(),
    }
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=timeout,
        ) as client:
            yield client, "http://testserver", diagnostics
    finally:
        with contextlib.redirect_stdout(runtime_capture), contextlib.redirect_stderr(runtime_capture):
            await lifespan_cm.__aexit__(None, None, None)


async def _sync_turn(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    headers: dict[str, str],
    session_id: str,
    turn_prompt: str,
    raw_path: Path,
    role: str,
    domain_id: str,
) -> dict[str, Any]:
    payload = {
        "user_id": headers["X-User-ID"],
        "message": turn_prompt,
        "role": role,
        "domain_id": domain_id,
        "session_id": session_id,
    }
    response = await client.post(f"{base_url}/api/v1/chat", headers=headers, json=payload)
    raw_path.write_text(response.text, encoding="utf-8")
    try:
        response_json = response.json()
    except Exception:
        response_json = {}

    data = response_json.get("data") or {}
    metadata = response_json.get("metadata") or {}
    answer = str(data.get("answer") or "").strip()
    thinking = _thinking_from_metadata(metadata)
    lifecycle_metrics = _lifecycle_metrics(metadata)

    return {
        "transport": "sync",
        "status_code": response.status_code,
        "prompt": turn_prompt,
        "answer": answer,
        "thinking": thinking,
        "agent_type": metadata.get("agent_type") or "",
        "processing_time": metadata.get("processing_time"),
        "metadata": metadata,
        "thinking_lifecycle": _extract_lifecycle_snapshot(metadata),
        "thinking_metrics": lifecycle_metrics,
        "tool_trace": _extract_sync_tool_trace(metadata),
        "raw_path": str(raw_path),
        "json": response_json,
        "duplicate_answer_tail": False,
    }


async def _stream_turn(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    headers: dict[str, str],
    session_id: str,
    turn_prompt: str,
    raw_path: Path,
    role: str,
    domain_id: str,
) -> dict[str, Any]:
    payload = {
        "user_id": headers["X-User-ID"],
        "message": turn_prompt,
        "role": role,
        "domain_id": domain_id,
        "session_id": session_id,
    }
    events: list[dict[str, Any]] = []
    raw_lines: list[str] = []
    current_event = "message"
    status_code = 0

    async with client.stream(
        "POST",
        f"{base_url}/api/v1/chat/stream/v3",
        headers={**headers, "Accept": "text/event-stream"},
        json=payload,
    ) as response:
        status_code = response.status_code
        response.raise_for_status()
        async for line in response.aiter_lines():
            line = line.rstrip("\n")
            raw_lines.append(line)
            if not line.strip():
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            data_str = line.split(":", 1)[1].lstrip()
            try:
                payload_obj = json.loads(data_str)
            except Exception:
                payload_obj = data_str
            events.append({"event": current_event, "data": payload_obj})

    raw_path.write_text(_raw_text_from_sse(raw_lines), encoding="utf-8")
    metadata = _extract_metadata(events)
    answer_events = _extract_answer_events(events)
    metadata_thinking = _thinking_from_metadata(metadata)
    extracted_thinking = _extract_thinking(events)
    first_answer_index = _extract_first_index(events, "answer")
    first_synth_index = _extract_first_synth_index(events)
    lifecycle_metrics = _lifecycle_metrics(metadata)

    return {
        "transport": "stream",
        "status_code": status_code,
        "prompt": turn_prompt,
        "answer": _extract_answer_chunks(events),
        "thinking": metadata_thinking or extracted_thinking,
        "agent_type": metadata.get("agent_type") or "",
        "processing_time": metadata.get("processing_time"),
        "metadata": metadata,
        "thinking_lifecycle": _extract_lifecycle_snapshot(metadata),
        "thinking_metrics": lifecycle_metrics,
        "tool_trace": _extract_stream_tool_trace(events),
        "raw_path": str(raw_path),
        "event_count": len(events),
        "answer_events": answer_events,
        "duplicate_answer_tail": (
            len(answer_events) >= 2
            and answer_events[-1] == "".join(answer_events[:-1]).strip()
        ),
        "first_answer_index": first_answer_index,
        "first_synth_status_index": first_synth_index,
        "answer_before_synth": (
            first_answer_index is not None
            and first_synth_index is not None
            and first_answer_index < first_synth_index
        ),
    }


async def _run_probe(args: argparse.Namespace) -> Path:
    manifest = load_manifest(args.manifest)
    selected_profiles = [item.strip().lower() for item in args.profiles.split(",") if item.strip()]
    selected_session_ids = [item.strip() for item in args.session_ids.split(",") if item.strip()] if args.session_ids else []
    selected_sessions = select_sessions(
        manifest,
        profiles=selected_profiles,
        session_ids=selected_session_ids,
    )
    selected_turn_ids = [item.strip() for item in args.turn_ids.split(",") if item.strip()]
    selected_sessions = filter_session_turns(
        selected_sessions,
        turn_ids=selected_turn_ids,
    )
    if not selected_sessions:
        raise ValueError("No sessions selected from manifest")

    report_dir = _report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()
    report: dict[str, Any] = {
        "schema": "wiii_golden_eval_v1",
        "generated_at": datetime.now().isoformat(),
        "manifest_path": str(Path(args.manifest).resolve()),
        "selected_profiles": selected_profiles,
        "selected_session_ids": selected_session_ids,
        "selected_turn_ids": selected_turn_ids,
        "sessions": [],
    }
    output_path = report_dir / f"wiii-golden-eval-{stamp}.json"

    async with _build_probe_client(
        transport_mode=args.transport_mode,
        base_url=args.base_url,
        timeout=args.timeout,
    ) as (client, resolved_base_url, diagnostics):
        report["probe_diagnostics"] = diagnostics
        report["resolved_base_url"] = resolved_base_url

        total_sessions = len(selected_sessions)
        for session_index, session in enumerate(selected_sessions, start=1):
            session_key = str(session.get("id") or "").strip()
            role = str(session.get("role") or manifest.get("default_role") or "student")
            domain_id = str(session.get("domain_id") or manifest.get("default_domain_id") or "maritime")
            session_user_id = _build_session_user_id(
                base_user_id=args.user_id,
                stamp=stamp,
                session_key=session_key,
            )
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": args.api_key,
                "X-User-ID": session_user_id,
                "X-Role": role,
            }
            sync_session_id = f"{args.session_prefix or 'golden'}-{session_key}-sync-{uuid.uuid4()}"
            stream_session_id = f"{args.session_prefix or 'golden'}-{session_key}-stream-{uuid.uuid4()}"

            session_report: dict[str, Any] = {
                "id": session_key,
                "label": session.get("label") or session_key,
                "profile": session.get("profile") or "core",
                "coverage": session.get("coverage") or [],
                "goal": session.get("goal") or "",
                "user_id": session_user_id,
                "sync_session_id": sync_session_id,
                "stream_session_id": stream_session_id,
                "turns": [],
            }
            print(
                f"[golden-eval] Session {session_index}/{total_sessions}: {session_key} "
                f"(user_id={session_user_id})",
                flush=True,
            )

            total_turns = len(session.get("turns") or [])
            for turn_index, turn in enumerate(session.get("turns") or [], start=1):
                turn_key = str(turn.get("id") or f"turn_{turn_index}").strip()
                prompt = str(turn.get("prompt") or "").strip()
                print(
                    f"[golden-eval]   Turn {turn_index}/{total_turns}: {turn_key}",
                    flush=True,
                )
                sync_raw_path = report_dir / f"golden-sync-{session_key}-{turn_key}-{stamp}.json"
                stream_raw_path = report_dir / f"golden-stream-{session_key}-{turn_key}-{stamp}.txt"

                sync_result = await _sync_turn(
                    client,
                    base_url=resolved_base_url,
                    headers=headers,
                    session_id=sync_session_id,
                    turn_prompt=prompt,
                    raw_path=sync_raw_path,
                    role=role,
                    domain_id=domain_id,
                )
                stream_result = await _stream_turn(
                    client,
                    base_url=resolved_base_url,
                    headers=headers,
                    session_id=stream_session_id,
                    turn_prompt=prompt,
                    raw_path=stream_raw_path,
                    role=role,
                    domain_id=domain_id,
                )

                sync_result["evaluation"] = _evaluate_turn(
                    result=sync_result,
                    turn_def=turn,
                    transport="sync",
                )
                stream_result["evaluation"] = _evaluate_turn(
                    result=stream_result,
                    turn_def=turn,
                    transport="stream",
                )

                session_report["turns"].append(
                    {
                        "id": turn_key,
                        "prompt": prompt,
                        "notes": turn.get("notes") or "",
                        "expect": turn.get("expect") or {},
                        "sync": sync_result,
                        "stream": stream_result,
                    }
                )

            report["sessions"].append(session_report)
            report["summary"] = summarize_report(report)
            report["progress"] = {
                "completed_session_count": len(report["sessions"]),
                "selected_session_count": total_sessions,
                "is_complete": len(report["sessions"]) == total_sessions,
            }
            _write_report_snapshot(output_path, report)

    report["summary"] = summarize_report(report)
    report["progress"] = {
        "completed_session_count": len(report.get("sessions") or []),
        "selected_session_count": len(selected_sessions),
        "is_complete": True,
    }
    _write_report_snapshot(output_path, report)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Wiii golden evaluation manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--profiles", default="core")
    parser.add_argument("--session-ids", default="")
    parser.add_argument("--turn-ids", default="")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--session-prefix", default="golden")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument(
        "--transport-mode",
        choices=["asgi", "http"],
        default=DEFAULT_TRANSPORT_MODE,
    )
    output_path = asyncio.run(_run_probe(parser.parse_args()))
    print(output_path)


if __name__ == "__main__":
    main()
