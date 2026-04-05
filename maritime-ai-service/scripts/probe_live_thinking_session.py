#!/usr/bin/env python3
"""
Probe live Wiii chat behavior for a small session and render a JSON report.

The output format matches render_thinking_probe_html.py expectations:
- session_id
- sync_rule15 / stream_rule15
- sync_visual_followup / stream_visual_followup
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_KEY = "local-dev-key"
DEFAULT_USER_ID = "codex-thinking-probe"
DEFAULT_ROLE = "student"
DEFAULT_DOMAIN_ID = "maritime"

RULE15_PROMPT = "Giải thích Quy tắc 15 COLREGs"
VISUAL_FOLLOWUP_PROMPT = "tạo visual cho mình xem được chứ?"


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def _report_dir() -> Path:
    return Path(__file__).resolve().parents[2] / ".Codex" / "reports"


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


def _extract_thinking(events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in events:
        event = item.get("event")
        if event not in {"thinking", "thinking_delta"}:
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            content = str(payload.get("content") or "").strip()
        else:
            content = str(payload or "").strip()
        if content:
            parts.append(content)

    # Prefer block thinking if available; otherwise join deltas.
    block_parts = [p for p in parts if "\n" in p or len(p) > 60]
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


def _extract_index(events: list[dict[str, Any]], target: str) -> int | None:
    for idx, item in enumerate(events):
        if item.get("event") == target:
            return idx
    return None


def _extract_first_synth_index(events: list[dict[str, Any]]) -> int | None:
    for idx, item in enumerate(events):
        if item.get("event") != "status":
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            step = str(payload.get("step") or "").strip().lower()
            content = str(payload.get("content") or "").strip().lower()
            if "synth" in step or "soạn" in content or "tong hop" in content or "tổng hợp" in content:
                return idx
    return None


def _stream_case(
    client: httpx.Client,
    *,
    base_url: str,
    headers: dict[str, str],
    session_id: str,
    prompt: str,
    raw_path: Path,
) -> dict[str, Any]:
    payload = {
        "user_id": headers["X-User-ID"],
        "message": prompt,
        "role": DEFAULT_ROLE,
        "domain_id": DEFAULT_DOMAIN_ID,
        "session_id": session_id,
    }
    events: list[dict[str, Any]] = []
    raw_lines: list[str] = []
    current_event = "message"
    status_code = 0

    with client.stream(
        "POST",
        f"{base_url}/api/v1/chat/stream/v3",
        headers={**headers, "Accept": "text/event-stream"},
        json=payload,
    ) as response:
        status_code = response.status_code
        response.raise_for_status()
        for line in response.iter_lines():
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
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
    extracted_thinking = _extract_thinking(events)
    metadata_thinking = ""
    if isinstance(metadata, dict):
        metadata_thinking = str(
            metadata.get("thinking_content")
            or metadata.get("thinking")
            or ""
        ).strip()
    first_answer_index = _extract_index(events, "answer")
    first_synth_status_index = _extract_first_synth_index(events)
    return {
        "status_code": status_code,
        "prompt": prompt,
        "answer": _extract_answer_chunks(events),
        "thinking": _pick_richer_thinking(extracted_thinking, metadata_thinking),
        "metadata": metadata,
        "raw_path": str(raw_path),
        "event_count": len(events),
        "first_answer_index": first_answer_index,
        "first_synth_status_index": first_synth_status_index,
        "answer_before_synth": (
            first_answer_index is not None
            and first_synth_status_index is not None
            and first_answer_index < first_synth_status_index
        ),
    }


def _sync_case(
    client: httpx.Client,
    *,
    base_url: str,
    headers: dict[str, str],
    session_id: str,
    prompt: str,
    raw_path: Path,
) -> dict[str, Any]:
    payload = {
        "user_id": headers["X-User-ID"],
        "message": prompt,
        "role": DEFAULT_ROLE,
        "domain_id": DEFAULT_DOMAIN_ID,
        "session_id": session_id,
    }
    response = client.post(
        f"{base_url}/api/v1/chat",
        headers=headers,
        json=payload,
    )
    raw_path.write_text(response.text, encoding="utf-8")
    try:
        data = response.json()
    except Exception:
        data = {}
    return {
        "status_code": response.status_code,
        "prompt": prompt,
        "json": data,
        "raw_path": str(raw_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--session-id", default=f"thinking-live-{uuid.uuid4()}")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    report_dir = _report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": args.api_key,
        "X-User-ID": args.user_id,
        "X-Role": DEFAULT_ROLE,
    }

    report: dict[str, Any] = {"session_id": args.session_id}

    with httpx.Client(timeout=args.timeout) as client:
        report["sync_rule15"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=args.session_id,
            prompt=RULE15_PROMPT,
            raw_path=report_dir / f"live-sync-rule15-{stamp}.json",
        )
        report["stream_rule15"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=args.session_id,
            prompt=RULE15_PROMPT,
            raw_path=report_dir / f"live-stream-rule15-{stamp}.txt",
        )
        report["sync_visual_followup"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=args.session_id,
            prompt=VISUAL_FOLLOWUP_PROMPT,
            raw_path=report_dir / f"live-sync-visual-followup-{stamp}.json",
        )
        report["stream_visual_followup"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=args.session_id,
            prompt=VISUAL_FOLLOWUP_PROMPT,
            raw_path=report_dir / f"live-stream-visual-followup-{stamp}.txt",
        )

    output_path = report_dir / f"live-thinking-session-probe-{stamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
