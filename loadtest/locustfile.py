"""Locust load test scenarios for Wiii AI runtime endpoints.

Phase 17 of the runtime migration epic (issue #207). Establishes a
reproducible load profile so canary rollouts can compare p50/p99 against
a baseline before flipping ``enable_native_runtime`` for an org.

Coverage:
- ``/api/v1/chat`` — legacy LMS path (always live).
- ``/v1/chat/completions`` — OpenAI-compat edge (Phase 10d, gated).
- ``/v1/messages`` — Anthropic-compat edge (Phase 10d, gated).

The three tasks share a single Locust ``User`` so tail latency reports
are apples-to-apples — same client, same connection pool, same auth
header. Task weights tilt toward edge endpoints (3:1) when measuring
the new runtime; flip via ``WIII_LOAD_PROFILE`` to focus traffic.

Quickstart::

    pip install locust
    export WIII_HOST=http://localhost:8000
    export WIII_API_KEY=test-key
    export WIII_USER_ID=loadtest-1
    locust -f loadtest/locustfile.py --headless \\
        -u 50 -r 5 -t 2m --host $WIII_HOST

Profiles (set via ``WIII_LOAD_PROFILE``):
- ``smoke`` (default): all 3 endpoints, equal weight, short prompts.
- ``edge_only``: only /v1/* — for canary regression checks.
- ``legacy_only``: only /api/v1/chat — for baseline before/after compare.

Reads:
- ``WIII_HOST`` (default ``http://localhost:8000``) — Locust ``--host`` overrides.
- ``WIII_API_KEY`` (default ``test-key``).
- ``WIII_USER_ID`` (default ``loadtest-locust``).
- ``WIII_ORG_ID`` (optional, for canary org targeting).
- ``WIII_LOAD_PROFILE`` (default ``smoke``).
"""

from __future__ import annotations

import os
import random
import uuid
from typing import Optional

try:
    from locust import HttpUser, between, task
except ImportError as exc:  # noqa: F401 — locust is an ops-only dep
    raise SystemExit(
        "locust is not installed. Run `pip install locust` first."
    ) from exc


# ── deterministic-ish prompt corpus ──

_PROMPTS = [
    "Giải thích Rule 13 COLREGs trong tình huống vượt nhau.",
    "Tóm tắt MARPOL Annex VI về phát thải SOx.",
    "Quy tắc nào áp dụng khi hai tàu máy cắt hướng nhau?",
    "Liệt kê 3 đèn báo bắt buộc trên tàu chở hàng dưới 50m.",
    "Sự khác nhau giữa SOLAS và MARPOL là gì?",
    "Khi nào tàu phải phát tín hiệu sương mù?",
    "Mức ngưỡng oxy tối thiểu trong khoang kín là bao nhiêu?",
    "Trình tự kiểm tra trước khi vào cảng.",
]


def _profile() -> str:
    return os.environ.get("WIII_LOAD_PROFILE", "smoke").lower().strip()


def _api_key() -> str:
    return os.environ.get("WIII_API_KEY", "test-key")


def _user_id() -> str:
    return os.environ.get("WIII_USER_ID", "loadtest-locust")


def _org_id() -> Optional[str]:
    value = os.environ.get("WIII_ORG_ID")
    return value or None


def _auth_headers() -> dict:
    headers = {
        "X-API-Key": _api_key(),
        "X-User-ID": _user_id(),
        "X-Session-ID": f"loadtest-{uuid.uuid4().hex[:8]}",
        "X-Role": "student",
    }
    org = _org_id()
    if org:
        headers["X-Organization-ID"] = org
    return headers


def _pick_prompt() -> str:
    return random.choice(_PROMPTS)


# ── User class ──


class WiiiRuntimeUser(HttpUser):
    """A single virtual user driving the Wiii runtime under load."""

    # 0.5–2.0s think time keeps the per-user RPS in a realistic range
    # without becoming the bottleneck (tail-latency reports stay clean).
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.headers = _auth_headers()
        self.profile = _profile()

    # ── /api/v1/chat (legacy LMS path) ──

    @task(weight=2)
    def legacy_chat(self):
        if self.profile == "edge_only":
            return
        body = {
            "user_id": _user_id(),
            "message": _pick_prompt(),
            "role": "student",
        }
        with self.client.post(
            "/api/v1/chat",
            json=body,
            headers=self.headers,
            name="POST /api/v1/chat",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status={resp.status_code} body={resp.text[:200]}")

    # ── /v1/chat/completions (OpenAI-compat edge) ──

    @task(weight=3)
    def edge_openai_completions(self):
        if self.profile == "legacy_only":
            return
        body = {
            "model": "wiii-default",
            "messages": [{"role": "user", "content": _pick_prompt()}],
        }
        with self.client.post(
            "/v1/chat/completions",
            json=body,
            headers=self.headers,
            name="POST /v1/chat/completions",
            catch_response=True,
        ) as resp:
            # 503 is the legitimate "feature not enabled" response in
            # default config — treat as success so smoke tests don't
            # spuriously red the entire run when the canary is closed.
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"status={resp.status_code} body={resp.text[:200]}")

    # ── /v1/messages (Anthropic-compat edge) ──

    @task(weight=1)
    def edge_anthropic_messages(self):
        if self.profile == "legacy_only":
            return
        body = {
            "model": "claude-sonnet-4",
            "messages": [{"role": "user", "content": _pick_prompt()}],
        }
        with self.client.post(
            "/v1/messages",
            json=body,
            headers=self.headers,
            name="POST /v1/messages",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"status={resp.status_code} body={resp.text[:200]}")
