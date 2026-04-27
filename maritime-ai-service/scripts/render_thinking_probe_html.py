"""Render standalone HTML viewers for Wiii probe reports.

Supports two report shapes:
- legacy flat sync_/stream_ probe reports
- golden-eval session reports with multi-turn flows
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


CASE_LABELS: dict[str, str] = {
    "rule15": "Giải thích Quy tắc 15 COLREGs",
    "visual_followup": "tạo visual cho mình xem được chứ?",
    "oke": "oke",
    "hehe_followup": "hẹ hẹ",
    "buon": "mình buồn quá",
    "wiii_identity": "Wiii là ai?",
}


def _default_prompt_for_case(case_key: str) -> str:
    for key, label in CASE_LABELS.items():
        if key in case_key:
            return label
    return case_key.replace("_", " ")


def _clamp_text(value: str, limit: int = 480) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_break = max(cut.rfind("\n"), cut.rfind(" "))
    if last_break > int(limit * 0.6):
        cut = cut[:last_break]
    return cut.rstrip() + "..."


def _summarize_tool_result(value: Any) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("result"), str):
            return _clamp_text(value["result"])
        return _clamp_text(json.dumps(value, ensure_ascii=False))
    return _clamp_text(str(value or ""))


def _extract_woven_thought(answer: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""

    italic_match = re.match(r"^\*{1,2}(?P<thought>.+?)\*{1,2}(?:\s+|$)", text, flags=re.DOTALL)
    if italic_match:
        thought = italic_match.group("thought").strip()
        if 20 <= len(thought) <= 420:
            return thought

    paren_match = re.match(r"^\((?P<thought>.+?)\)(?:\s+|$)", text, flags=re.DOTALL)
    if paren_match:
        thought = paren_match.group("thought").strip()
        if 20 <= len(thought) <= 420:
            return thought

    return ""


def _parse_stream_tool_trace(raw_path: str | None) -> list[dict[str, str]]:
    if not raw_path:
        return []
    path = Path(raw_path)
    if not path.exists():
        return []

    trace: list[dict[str, str]] = []
    current_event: str | None = None
    data_lines: list[str] = []

    def _commit() -> None:
        nonlocal current_event, data_lines
        if not current_event:
            return
        raw_data = "\n".join(data_lines)
        if current_event in {"tool_call", "tool_result", "action_text"}:
            try:
                payload = json.loads(raw_data)
            except Exception:
                payload = raw_data
            if current_event == "tool_call" and isinstance(payload, dict):
                content = payload.get("content") or {}
                trace.append(
                    {
                        "kind": "call",
                        "title": str(content.get("name") or "tool"),
                        "body": _clamp_text(json.dumps(content.get("args") or {}, ensure_ascii=False, indent=2)),
                    }
                )
            elif current_event == "tool_result" and isinstance(payload, dict):
                content = payload.get("content") or {}
                trace.append(
                    {
                        "kind": "result",
                        "title": str(content.get("name") or "tool"),
                        "body": _summarize_tool_result(content.get("result")),
                    }
                )
            elif current_event == "action_text" and isinstance(payload, dict):
                trace.append(
                    {
                        "kind": "action",
                        "title": str(payload.get("node") or "action"),
                        "body": _clamp_text(str(payload.get("content") or "")),
                    }
                )
            else:
                trace.append(
                    {
                        "kind": current_event,
                        "title": current_event,
                        "body": _clamp_text(str(payload)),
                    }
                )
        current_event = None
        data_lines = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("event:"):
            _commit()
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
        elif not line.strip():
            _commit()
    _commit()
    return trace


def _build_sync_tool_trace(tools_used: list[dict[str, Any]]) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    for tool in tools_used or []:
        trace.append(
            {
                "kind": "call",
                "title": str(tool.get("name") or "tool"),
                "body": str(tool.get("description") or ""),
            }
        )
    return trace


def _extract_sync_case(payload: dict[str, Any], case_key: str) -> dict[str, Any]:
    response_json = payload.get("json") or {}
    data = response_json.get("data") or {}
    metadata = response_json.get("metadata") or {}
    answer = data.get("answer") or ""
    thinking = metadata.get("thinking_content") or metadata.get("thinking") or payload.get("thinking") or ""
    return {
        "transport": "sync",
        "prompt": payload.get("prompt") or _default_prompt_for_case(case_key),
        "answer": answer,
        "thinking": thinking,
        "woven_thought": "" if thinking else _extract_woven_thought(answer),
        "agent_type": metadata.get("agent_type") or "",
        "processing_time": metadata.get("processing_time"),
        "tools_used": metadata.get("tools_used") or [],
        "tool_trace": _build_sync_tool_trace(metadata.get("tools_used") or []),
        "raw_path": payload.get("raw_path"),
        "metadata": metadata,
        "status_code": payload.get("status_code"),
        "runtime": {
            **_runtime_from_metadata(metadata, fallback_time=metadata.get("processing_time")),
            "status_code": payload.get("status_code"),
        },
    }


def _extract_stream_case(payload: dict[str, Any], case_key: str) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    payload_thinking = str(payload.get("thinking") or "").strip()
    metadata_thinking = str(
        metadata.get("thinking_content") or metadata.get("thinking") or ""
    ).strip()
    visible_thinking = metadata_thinking if metadata_thinking and len(metadata_thinking) > len(payload_thinking) else payload_thinking
    answer = payload.get("answer") or ""
    return {
        "transport": "stream",
        "prompt": payload.get("prompt") or _default_prompt_for_case(case_key),
        "answer": answer,
        "thinking": visible_thinking,
        "woven_thought": "" if visible_thinking else _extract_woven_thought(answer),
        "agent_type": metadata.get("agent_type") or "",
        "processing_time": metadata.get("processing_time"),
        "tools_used": metadata.get("tools_used") or [],
        "tool_trace": _parse_stream_tool_trace(payload.get("raw_path")),
        "raw_path": payload.get("raw_path"),
        "metadata": metadata,
        "event_count": payload.get("event_count"),
        "status_code": payload.get("status_code"),
        "runtime": {
            **_runtime_from_metadata(metadata, fallback_time=metadata.get("processing_time")),
            "status_code": payload.get("status_code"),
        },
    }


def _group_cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for key, payload in report.items():
        if key == "session_id" or not isinstance(payload, dict):
            continue
        if key.startswith("sync_"):
            stem = key[len("sync_") :]
            groups.setdefault(stem, {"id": stem, "sync": None, "stream": None})
            groups[stem]["sync"] = _extract_sync_case(payload, stem)
        elif key.startswith("stream_"):
            stem = key[len("stream_") :]
            groups.setdefault(stem, {"id": stem, "sync": None, "stream": None})
            groups[stem]["stream"] = _extract_stream_case(payload, stem)
    ordered = []
    for stem in CASE_LABELS:
        if stem in groups:
            ordered.append(groups.pop(stem))
    ordered.extend(groups.values())
    return ordered


def _badge(label: str, value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return (
        "<span class='badge'>"
        f"<span class='badge-label'>{html.escape(label)}</span>"
        f"<span class='badge-value'>{html.escape(str(value))}</span>"
        "</span>"
    )


def _tool_badges(tools_used: list[dict[str, Any]]) -> str:
    if not tools_used:
        return ""
    badges = []
    for tool in tools_used:
        name = tool.get("name") or "tool"
        badges.append(f"<span class='chip'>{html.escape(str(name))}</span>")
    return "<div class='chips'>" + "".join(badges) + "</div>"


def _runtime_from_metadata(metadata: dict[str, Any] | None, *, fallback_time: Any = None) -> dict[str, Any]:
    meta = metadata if isinstance(metadata, dict) else {}
    lifecycle = meta.get("thinking_lifecycle") if isinstance(meta.get("thinking_lifecycle"), dict) else {}
    failover = meta.get("failover") if isinstance(meta.get("failover"), dict) else {}
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
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "processing_time": meta.get("processing_time", fallback_time),
        "status_code": meta.get("status_code"),
        "thinking_final_length": lifecycle.get("final_length"),
        "thinking_live_length": lifecycle.get("live_length"),
        "phases": lifecycle.get("phases") or [],
        "provenance_mix": lifecycle.get("provenance_mix") or [],
        "failover_switched": bool(failover.get("switched")),
        "failover_reason_code": failover.get("last_reason_code"),
        "failover_route": route_tokens,
    }


def _runtime_block(case: dict[str, Any]) -> str:
    runtime = case.get("runtime") or {}
    items: list[str] = []
    if runtime.get("provider"):
        items.append(f"<span class='chip'>provider: {html.escape(str(runtime['provider']))}</span>")
    if runtime.get("model"):
        items.append(f"<span class='chip'>model: {html.escape(str(runtime['model']))}</span>")
    if runtime.get("status_code") not in (None, ""):
        items.append(f"<span class='chip'>status: {html.escape(str(runtime['status_code']))}</span>")
    if runtime.get("thinking_final_length") not in (None, ""):
        items.append(
            f"<span class='chip'>thinking: {html.escape(str(runtime['thinking_final_length']))} chars</span>"
        )
    if runtime.get("thinking_live_length") not in (None, ""):
        items.append(
            f"<span class='chip'>live: {html.escape(str(runtime['thinking_live_length']))} chars</span>"
        )
    if runtime.get("failover_reason_code"):
        items.append(
            f"<span class='chip chip-warn'>failover: {html.escape(str(runtime['failover_reason_code']))}</span>"
        )
    if runtime.get("phases"):
        items.append(
            f"<span class='chip'>phases: {html.escape(', '.join(str(item) for item in runtime['phases']))}</span>"
        )
    if runtime.get("provenance_mix"):
        items.append(
            f"<span class='chip'>provenance: {html.escape(', '.join(str(item) for item in runtime['provenance_mix']))}</span>"
        )
    if not items and not runtime.get("failover_route"):
        return ""

    route_line = ""
    if runtime.get("failover_route"):
        route_line = (
            "<div class='runtime-route'>"
            f"{html.escape(' -> '.join(runtime['failover_route']))}"
            "</div>"
        )

    return (
        "<div class='runtime-block'>"
        "<div class='runtime-label'>Runtime</div>"
        f"<div class='chips runtime-chips'>{''.join(items)}</div>"
        f"{route_line}"
        "</div>"
    )


def _render_evaluation_block(evaluation: dict[str, Any] | None) -> str:
    if not evaluation:
        return ""

    checks = evaluation.get("checks") or {}
    failures = evaluation.get("failures") or []
    passed = bool(evaluation.get("passed"))
    items = [f"<span class='chip {'chip-pass' if passed else 'chip-warn'}'>{'PASS' if passed else 'CHECK'}</span>"]
    for label, value in checks.items():
        if value in (None, "", [], {}):
            continue
        items.append(f"<span class='chip'>{html.escape(str(label))}: {html.escape(str(value))}</span>")
    for failure in failures:
        items.append(f"<span class='chip chip-fail'>{html.escape(str(failure))}</span>")
    return "<div class='chips eval-chips'>" + "".join(items) + "</div>"


def _render_lifecycle_block(metadata: dict[str, Any] | None) -> str:
    lifecycle = (metadata or {}).get("thinking_lifecycle")
    if not isinstance(lifecycle, dict):
        return _bubble("lifecycle", "Thinking Lifecycle", "", "Khong co lifecycle snapshot")

    chips: list[str] = [
        f"<span class='chip'>live={html.escape(str(lifecycle.get('live_length') or 0))}</span>",
        f"<span class='chip'>final={html.escape(str(lifecycle.get('final_length') or 0))}</span>",
        f"<span class='chip'>segments={html.escape(str(lifecycle.get('segment_count') or 0))}</span>",
    ]
    for phase in lifecycle.get("phases") or []:
        chips.append(f"<span class='chip'>{html.escape(str(phase))}</span>")
    for provenance in lifecycle.get("provenance_mix") or []:
        chips.append(f"<span class='chip'>{html.escape(str(provenance))}</span>")
    if lifecycle.get("has_tool_continuation"):
        chips.append("<span class='chip chip-pass'>tool_continuation</span>")

    final_text = str(lifecycle.get("final_text") or "").strip()
    return (
        "<article class='bubble bubble-lifecycle'>"
        "<div class='bubble-title'>Thinking Lifecycle</div>"
        f"<div class='chips'>{''.join(chips)}</div>"
        f"<pre>{html.escape(final_text) if final_text else ''}</pre>"
        "</article>"
    )


def _tool_trace_block(tool_trace: list[dict[str, str]]) -> str:
    if not tool_trace:
        return _bubble("tool", "Research Trace", "", "Không có research trace hiển thị")
    rows = []
    for item in tool_trace:
        kind = item.get("kind") or "tool"
        rows.append(
            "<div class='trace-item'>"
            f"<div class='trace-kind trace-kind-{html.escape(kind)}'>{html.escape(kind.upper())}</div>"
            f"<div class='trace-title'>{html.escape(item.get('title') or '')}</div>"
            f"<pre>{html.escape(item.get('body') or '')}</pre>"
            "</div>"
        )
    return (
        "<article class='bubble bubble-tool'>"
        "<div class='bubble-title'>Research Trace</div>"
        f"<div class='trace-list'>{''.join(rows)}</div>"
        "</article>"
    )


def _bubble(role: str, title: str, body: str, empty_hint: str) -> str:
    safe_body = html.escape(body.strip()) if body and body.strip() else ""
    content = f"<pre>{safe_body}</pre>" if safe_body else f"<div class='empty'>{html.escape(empty_hint)}</div>"
    return (
        f"<article class='bubble bubble-{role}'>"
        f"<div class='bubble-title'>{html.escape(title)}</div>"
        f"{content}"
        "</article>"
    )


def _render_transport_card(case: dict[str, Any] | None) -> str:
    if not case:
        return "<section class='transport-card missing'><div class='transport-head'>Thiếu dữ liệu</div></section>"

    thinking_title = "Thinking"
    lifecycle = (case.get("metadata") or {}).get("thinking_lifecycle")
    lifecycle_final = (
        str((lifecycle or {}).get("final_text") or "").strip()
        if isinstance(lifecycle, dict)
        else ""
    )
    thinking_body = lifecycle_final or case.get("thinking") or ""
    if not thinking_body and case.get("woven_thought"):
        thinking_title = "Thinking (Woven Into Answer)"
        thinking_body = case.get("woven_thought") or ""

    badges = [
        _badge("transport", case.get("transport")),
        _badge("agent", case.get("agent_type")),
    ]
    if case.get("status_code") is not None:
        badges.append(_badge("status", case.get("status_code")))
    runtime = case.get("runtime") or {}
    if runtime.get("provider"):
        badges.append(_badge("provider", runtime.get("provider")))
    if runtime.get("model"):
        badges.append(_badge("model", runtime.get("model")))
    if case.get("processing_time") is not None:
        badges.append(_badge("time", f"{case['processing_time']}s"))
    if case.get("event_count") is not None:
        badges.append(_badge("events", case["event_count"]))

    raw_path = case.get("raw_path")
    raw_link = ""
    if raw_path:
        raw_href = str(raw_path).replace("\\", "/")
        raw_link = f"<a class='raw-link' href='file:///{html.escape(raw_href, quote=True)}' target='_blank'>Mở raw</a>"

    return (
        "<section class='transport-card'>"
        "<div class='transport-head'>"
        f"<div class='transport-name'>{html.escape(str(case.get('transport') or '').upper())}</div>"
        f"<div class='transport-meta'>{''.join(b for b in badges if b)}</div>"
        f"{raw_link}"
        "</div>"
        f"{_tool_badges(case.get('tools_used') or [])}"
        f"{_render_evaluation_block(case.get('evaluation'))}"
        "<div class='chat-lane'>"
        f"{_bubble('user', 'User', case.get('prompt') or '', 'Không có prompt')}"
        f"{_bubble('thinking', thinking_title, thinking_body, 'Không có visible thinking')}"
        f"{_runtime_block(case)}"
        f"{_render_lifecycle_block(case.get('metadata'))}"
        f"{_tool_trace_block(case.get('tool_trace') or [])}"
        f"{_bubble('answer', 'Answer', case.get('answer') or '', 'Không có answer')}"
        "</div>"
        "</section>"
    )


def _base_styles() -> str:
    return """
    :root {
      --bg: #f4efe7;
      --panel: rgba(255,255,255,0.72);
      --ink: #172026;
      --muted: #62707c;
      --border: rgba(23,32,38,0.12);
      --accent: #0f766e;
      --accent-soft: rgba(15,118,110,0.12);
      --thinking: #eef1f4;
      --tool: #f1f7ff;
      --answer: #16252e;
      --answer-ink: #f7fbff;
      --user: #fff7e8;
      --shadow: 0 18px 40px rgba(18, 33, 43, 0.08);
      --radius: 22px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "SF Pro Text", "Inter", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.12), transparent 30%),
        radial-gradient(circle at top right, rgba(245,158,11,0.12), transparent 30%),
        linear-gradient(180deg, #fbf8f2 0%, var(--bg) 100%);
      min-height: 100vh;
    }
    .wrap {
      max-width: 1440px;
      margin: 0 auto;
      padding: 40px 24px 72px;
    }
    .hero {
      background: var(--panel);
      border: 1px solid var(--border);
      backdrop-filter: blur(16px);
      border-radius: 28px;
      padding: 28px 30px;
      box-shadow: var(--shadow);
      margin-bottom: 28px;
    }
    .eyebrow {
      color: var(--accent);
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0.12em;
      font-weight: 700;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0 0 10px;
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.05;
    }
    h2 {
      margin: 0;
      font-size: clamp(20px, 2vw, 28px);
      line-height: 1.25;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 960px;
      font-size: 15px;
      line-height: 1.65;
    }
    .hero-meta {
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 12px;
      background: white;
      border: 1px solid var(--border);
      font-size: 12px;
    }
    .badge-label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
    }
    .badge-value {
      color: var(--ink);
      font-weight: 700;
    }
    .case-block, .turn-block {
      margin-bottom: 24px;
    }
    .session-block {
      background: rgba(255,255,255,0.36);
      border: 1px solid rgba(23,32,38,0.08);
      border-radius: 28px;
      padding: 22px 18px 8px;
      margin-bottom: 28px;
    }
    .session-head, .case-header {
      display: flex;
      align-items: baseline;
      gap: 14px;
      margin: 0 0 14px;
    }
    .case-index {
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }
    .session-goal, .turn-notes {
      color: var(--muted);
      margin-bottom: 12px;
      font-size: 14px;
      line-height: 1.6;
    }
    .turn-notes {
      font-size: 13px;
      margin-top: -4px;
    }
    .transport-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .transport-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
      min-height: 420px;
    }
    .transport-card.missing {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
    }
    .transport-head {
      display: flex;
      align-items: center;
      gap: 10px;
      justify-content: space-between;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .transport-name {
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.12em;
      color: var(--accent);
    }
    .transport-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      flex: 1;
    }
    .raw-link {
      text-decoration: none;
      color: var(--ink);
      border: 1px solid var(--border);
      background: white;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      background: white;
      border: 1px solid var(--border);
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
    }
    .chip-pass {
      background: rgba(15,118,110,0.12);
      color: #0f766e;
      border-color: rgba(15,118,110,0.18);
    }
    .chip-warn {
      background: rgba(245,158,11,0.12);
      color: #b45309;
      border-color: rgba(245,158,11,0.18);
    }
    .chip-fail {
      background: rgba(220,38,38,0.12);
      color: #b91c1c;
      border-color: rgba(220,38,38,0.18);
    }
    .runtime-block {
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(15,118,110,0.18);
      background: rgba(15,118,110,0.05);
    }
    .runtime-label {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
      color: var(--accent);
    }
    .runtime-chips {
      margin-bottom: 6px;
    }
    .runtime-route {
      font-size: 13px;
      color: var(--muted);
      word-break: break-word;
    }
    .chat-lane {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .bubble {
      padding: 14px 16px;
      border-radius: 20px;
      border: 1px solid var(--border);
      overflow: hidden;
    }
    .bubble-title {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .bubble-user { background: var(--user); }
    .bubble-thinking { background: var(--thinking); }
    .bubble-tool { background: var(--tool); }
    .bubble-answer {
      background: var(--answer);
      color: var(--answer-ink);
      border-color: rgba(255,255,255,0.08);
    }
    .bubble-answer .bubble-title { color: rgba(255,255,255,0.74); }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "Consolas", "SF Mono", monospace;
      font-size: 13px;
      line-height: 1.65;
    }
    .empty {
      color: var(--muted);
      font-style: italic;
      font-size: 14px;
    }
    .trace-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .trace-item {
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.7);
      border-radius: 16px;
      padding: 12px;
    }
    .trace-kind {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .trace-kind-call {
      background: rgba(15,118,110,0.12);
      color: #0f766e;
    }
    .trace-kind-result, .trace-kind-action {
      background: rgba(30,64,175,0.12);
      color: #1d4ed8;
    }
    .trace-title {
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 8px;
    }
    @media (max-width: 980px) {
      .transport-grid { grid-template-columns: 1fr; }
      .wrap { padding: 24px 16px 48px; }
      .hero { padding: 22px 20px; }
      .session-block { padding: 18px 14px 6px; }
    }
    """


def _render_legacy_cases(report: dict[str, Any], source_path: Path) -> str:
    groups = _group_cases(report)
    session_id = report.get("session_id", "")

    sections = []
    for idx, group in enumerate(groups, start=1):
        prompt = (
            (group.get("sync") or {}).get("prompt")
            or (group.get("stream") or {}).get("prompt")
            or _default_prompt_for_case(group["id"])
        )
        sections.append(
            "<section class='case-block'>"
            f"<div class='case-header'><div class='case-index'>Case {idx}</div><h2>{html.escape(prompt)}</h2></div>"
            "<div class='transport-grid'>"
            f"{_render_transport_card(group.get('sync'))}"
            f"{_render_transport_card(group.get('stream'))}"
            "</div>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wiii Thinking Review</title>
  <style>{_base_styles()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Wiii Thinking Review</div>
      <h1>Raw Thinking Viewer</h1>
      <p>
        Trang này hiển thị nguyên raw prompt, thinking, và answer theo dạng chat để dễ soi chất lượng hiện tại của Wiii.
        Mỗi case được đặt cạnh nhau giữa <strong>sync</strong> và <strong>stream</strong> để nhìn rõ chênh lệch.
      </p>
      <div class="hero-meta">
        {_badge("session", session_id)}
        {_badge("source", source_path.name)}
      </div>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>"""


def _render_golden_session_turn(turn: dict[str, Any], turn_index: int) -> str:
    prompt = turn.get("prompt") or turn.get("id") or f"Turn {turn_index}"
    notes = str(turn.get("notes") or "").strip()
    notes_block = f"<div class='turn-notes'>{html.escape(notes)}</div>" if notes else ""
    return (
        "<section class='case-block turn-block'>"
        f"<div class='case-header'><div class='case-index'>Turn {turn_index}</div><h2>{html.escape(prompt)}</h2></div>"
        f"{notes_block}"
        "<div class='transport-grid'>"
        f"{_render_transport_card(turn.get('sync'))}"
        f"{_render_transport_card(turn.get('stream'))}"
        "</div>"
        "</section>"
    )


def _render_golden_sessions(report: dict[str, Any], source_path: Path) -> str:
    sessions = report.get("sessions") or []
    summary = report.get("summary") or {}
    sections: list[str] = []

    for session_index, session in enumerate(sessions, start=1):
        coverage = session.get("coverage") or []
        coverage_block = (
            "<div class='chips'>"
            + "".join(f"<span class='chip'>{html.escape(str(item))}</span>" for item in coverage)
            + "</div>"
            if coverage
            else ""
        )
        turn_blocks = "".join(
            _render_golden_session_turn(turn, idx)
            for idx, turn in enumerate(session.get("turns") or [], start=1)
        )
        sections.append(
            "<section class='session-block'>"
            f"<div class='session-head'><div class='case-index'>Session {session_index}</div><h2>{html.escape(str(session.get('label') or session.get('id') or f'Session {session_index}'))}</h2></div>"
            f"<div class='session-goal'>{html.escape(str(session.get('goal') or ''))}</div>"
            f"{coverage_block}"
            f"{turn_blocks}"
            "</section>"
        )

    hero_badges = [
        _badge("source", source_path.name),
        _badge("profiles", ", ".join(report.get("selected_profiles") or [])),
        _badge("sessions", summary.get("session_count")),
        _badge("turns", summary.get("turn_count")),
        _badge("transports", summary.get("transport_count")),
        _badge("passes", summary.get("passed_transport_count")),
        _badge("checks", summary.get("failed_transport_count")),
        _badge("stream thinking", summary.get("stream_visible_thinking_turns")),
        _badge("tool trace", summary.get("stream_tool_trace_turns")),
    ]
    avg_times = summary.get("transport_avg_processing_time") or {}
    if avg_times.get("sync") is not None:
        hero_badges.append(_badge("avg sync", f"{avg_times['sync']}s"))
    if avg_times.get("stream") is not None:
        hero_badges.append(_badge("avg stream", f"{avg_times['stream']}s"))
    if summary.get("failover_switch_transports") is not None:
        hero_badges.append(_badge("failover", summary.get("failover_switch_transports")))

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wiii Golden Eval Review</title>
  <style>{_base_styles()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Wiii Golden Eval</div>
      <h1>Regression Review</h1>
      <p>
        Trang này hiển thị các session kiểm thử chuẩn của Wiii theo đúng flow chat thật: mỗi session có nhiều turn,
        mỗi turn đặt <strong>sync</strong> và <strong>stream</strong> cạnh nhau để soi answer, thinking, tool trace,
        continuity, và regression user-facing.
      </p>
      <div class="hero-meta">{''.join(badge for badge in hero_badges if badge)}</div>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>"""


def render_html(report: dict[str, Any], source_path: Path) -> str:
    if isinstance(report.get("sessions"), list):
        return _render_golden_sessions(report, source_path)
    return _render_legacy_cases(report, source_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a standalone HTML viewer from a probe JSON report.")
    parser.add_argument("--input", required=True, help="Path to the JSON report.")
    parser.add_argument("--output", required=True, help="Path to the output HTML file.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    report = json.loads(input_path.read_text(encoding="utf-8"))
    html_text = render_html(report, input_path)
    output_path.write_text(html_text, encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
