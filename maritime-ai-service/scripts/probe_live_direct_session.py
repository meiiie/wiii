#!/usr/bin/env python3
"""
Probe live direct-lane behavior for a short session and emit a review JSON.

Output matches render_thinking_probe_html.py expectations:
- sync_oke / stream_oke
- sync_hehe_followup / stream_hehe_followup
- sync_buon / stream_buon
- sync_wiii_identity / stream_wiii_identity
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_KEY = "local-dev-key"
DEFAULT_USER_ID = "codex-direct-probe"
DEFAULT_ROLE = "student"
DEFAULT_DOMAIN_ID = "maritime"

OKE_PROMPT = "oke"
# ASCII-safe probe prompts so live checks are not distorted by local shell encoding.
HEHE_FOLLOWUP_PROMPT = "he he"
BUON_PROMPT = "minh buon qua"
IDENTITY_PROMPT = "Wiii la ai?"
HEHE_FOLLOWUP_PROMPT = "hẹ hẹ"
BUON_PROMPT = "mình buồn quá"
IDENTITY_PROMPT = "Wiii là ai?"

# Final override so raw probes stay stable even when local shell/output mangles literals.
HEHE_FOLLOWUP_PROMPT = "he he"
BUON_PROMPT = "minh buon qua"
IDENTITY_PROMPT = "Wiii la ai?"


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
        if item.get("event") not in {"thinking", "thinking_delta"}:
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            content = str(payload.get("content") or "").strip()
        else:
            content = str(payload or "").strip()
        if content:
            parts.append(content)
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
    response = client.post(f"{base_url}/api/v1/chat", headers=headers, json=payload)
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
    return {
        "status_code": status_code,
        "prompt": prompt,
        "answer": _extract_answer_chunks(events),
        "thinking": _pick_richer_thinking(extracted_thinking, metadata_thinking),
        "metadata": metadata,
        "raw_path": str(raw_path),
        "event_count": len(events),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--session-id", default=f"direct-thinking-live-{uuid.uuid4()}")
    parser.add_argument("--timeout", type=float, default=120.0)
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
        oke_sync_session = f"{args.session_id}-oke-sync"
        oke_stream_session = f"{args.session_id}-oke-stream"
        report["sync_oke"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=oke_sync_session,
            prompt=OKE_PROMPT,
            raw_path=report_dir / f"live-sync-oke-{stamp}.json",
        )
        report["stream_oke"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=oke_stream_session,
            prompt=OKE_PROMPT,
            raw_path=report_dir / f"live-stream-oke-{stamp}.txt",
        )

        hehe_sync_session = f"{args.session_id}-hehe-sync"
        hehe_stream_session = f"{args.session_id}-hehe-stream"
        _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=hehe_sync_session,
            prompt=OKE_PROMPT,
            raw_path=report_dir / f"live-sync-hehe-prime-{stamp}.json",
        )
        report["sync_hehe_followup"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=hehe_sync_session,
            prompt=HEHE_FOLLOWUP_PROMPT,
            raw_path=report_dir / f"live-sync-hehe-followup-{stamp}.json",
        )
        _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=hehe_stream_session,
            prompt=OKE_PROMPT,
            raw_path=report_dir / f"live-stream-hehe-prime-{stamp}.txt",
        )
        report["stream_hehe_followup"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=hehe_stream_session,
            prompt=HEHE_FOLLOWUP_PROMPT,
            raw_path=report_dir / f"live-stream-hehe-followup-{stamp}.txt",
        )

        separate_session = f"{args.session_id}-separate"
        report["sync_buon"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=f"{separate_session}-buon-sync",
            prompt=BUON_PROMPT,
            raw_path=report_dir / f"live-sync-buon-{stamp}.json",
        )
        report["stream_buon"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=f"{separate_session}-buon-stream",
            prompt=BUON_PROMPT,
            raw_path=report_dir / f"live-stream-buon-{stamp}.txt",
        )
        report["sync_wiii_identity"] = _sync_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=f"{separate_session}-identity-sync",
            prompt=IDENTITY_PROMPT,
            raw_path=report_dir / f"live-sync-wiii-identity-{stamp}.json",
        )
        report["stream_wiii_identity"] = _stream_case(
            client,
            base_url=args.base_url,
            headers=headers,
            session_id=f"{separate_session}-identity-stream",
            prompt=IDENTITY_PROMPT,
            raw_path=report_dir / f"live-stream-wiii-identity-{stamp}.txt",
        )

    output_path = report_dir / f"live-direct-thinking-probe-{stamp}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
