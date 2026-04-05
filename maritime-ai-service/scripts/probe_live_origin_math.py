#!/usr/bin/env python3
"""
Probe Wiii origin/selfhood and hard-math behavior from the current app.

By default this runs against the in-process FastAPI app via ASGI transport so
the result reflects the current codebase even when localhost:8000 is noisy or
stale on Windows. HTTP mode is still available for explicit external probing.

Outputs a JSON report that render_thinking_probe_html.py can consume.
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
DEFAULT_USER_ID = "codex-origin-math-probe"
DEFAULT_ROLE = "student"
DEFAULT_DOMAIN_ID = "maritime"
DEFAULT_TRANSPORT_MODE = "asgi"

ORIGIN_PROMPT = "Wiii được sinh ra như thế nào?"
HARD_MATH_PROMPT = (
    "Hãy giải thích thật sâu bài toán sau: "
    "Cho H là một không gian Hilbert separable và A là toán tử tự liên hợp không bị chặn "
    "có compact resolvent. Vì sao phổ của A là rời rạc, mỗi trị riêng có bội hữu hạn, "
    "và các trị riêng chỉ có thể tích lũy tại vô cực? "
    "Sau đó dùng spectral theorem và functional calculus để phân tích nghiệm của phương trình "
    "du/dt = -iAu với dữ liệu đầu u(0)=u0. "
    "Cuối cùng, nếu thay A bằng một toán tử chỉ đối xứng nhưng không tự liên hợp, thì có những "
    "vấn đề gì xuất hiện đối với sự tồn tại của nhóm đơn vị và bài toán tiến hóa?"
)


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


def _extract_answer_events(events: list[dict[str, Any]]) -> list[str]:
    collected: list[str] = []
    for item in events:
        if item.get("event") != "answer":
            continue
        payload = item.get("data")
        if isinstance(payload, dict):
            collected.append(str(payload.get("content") or ""))
        else:
            collected.append(str(payload or ""))
    return [chunk for chunk in collected if chunk]


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


async def _sync_case(
    client: httpx.AsyncClient,
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
    response = await client.post(f"{base_url}/api/v1/chat", headers=headers, json=payload)
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


async def _stream_case(
    client: httpx.AsyncClient,
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
    extracted_thinking = _extract_thinking(events)
    metadata_thinking = ""
    if isinstance(metadata, dict):
        metadata_thinking = str(
            metadata.get("thinking_content")
            or metadata.get("thinking")
            or ""
        ).strip()
    answer_events = _extract_answer_events(events)
    return {
        "status_code": status_code,
        "prompt": prompt,
        "answer": _extract_answer_chunks(events),
        "answer_events": answer_events,
        "duplicate_answer_tail": len(answer_events) >= 2 and answer_events[-1] == "".join(answer_events[:-1]).strip(),
        "thinking": _pick_richer_thinking(extracted_thinking, metadata_thinking),
        "metadata": metadata,
        "raw_path": str(raw_path),
        "event_count": len(events),
    }


async def _run_probe(args: argparse.Namespace) -> Path:
    report_dir = _report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": args.api_key,
        "X-User-ID": args.user_id,
        "X-Role": DEFAULT_ROLE,
    }

    report: dict[str, Any] = {
        "session_id": args.session_id,
        "transport_mode": args.transport_mode,
    }

    async with _build_probe_client(
        transport_mode=args.transport_mode,
        base_url=args.base_url,
        timeout=args.timeout,
    ) as (client, resolved_base_url, diagnostics):
        report["probe_diagnostics"] = diagnostics
        report["sync_wiii_origin"] = await _sync_case(
            client,
            base_url=resolved_base_url,
            headers=headers,
            session_id=f"{args.session_id}-origin-sync",
            prompt=ORIGIN_PROMPT,
            raw_path=report_dir / f"live-sync-wiii-origin-{stamp}.json",
        )
        report["stream_wiii_origin"] = await _stream_case(
            client,
            base_url=resolved_base_url,
            headers=headers,
            session_id=f"{args.session_id}-origin-stream",
            prompt=ORIGIN_PROMPT,
            raw_path=report_dir / f"live-stream-wiii-origin-{stamp}.txt",
        )

        report["sync_hard_math"] = await _sync_case(
            client,
            base_url=resolved_base_url,
            headers=headers,
            session_id=f"{args.session_id}-math-sync",
            prompt=HARD_MATH_PROMPT,
            raw_path=report_dir / f"live-sync-hard-math-{stamp}.json",
        )
        report["stream_hard_math"] = await _stream_case(
            client,
            base_url=resolved_base_url,
            headers=headers,
            session_id=f"{args.session_id}-math-stream",
            prompt=HARD_MATH_PROMPT,
            raw_path=report_dir / f"live-stream-hard-math-{stamp}.txt",
        )

    output_path = report_dir / f"live-origin-math-probe-{stamp}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--session-id", default=f"origin-math-{uuid.uuid4()}")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--transport-mode",
        choices=["asgi", "http"],
        default=DEFAULT_TRANSPORT_MODE,
        help="Probe the in-process FastAPI app via ASGI or an external HTTP server.",
    )
    output_path = asyncio.run(_run_probe(parser.parse_args()))
    print(output_path)


if __name__ == "__main__":
    main()
