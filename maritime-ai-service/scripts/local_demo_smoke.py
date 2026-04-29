#!/usr/bin/env python3
"""Local demo smoke gate for Wiii.

This script verifies the same local JWT/dev-login path that the desktop app
uses for demos. It intentionally avoids API-key auth so stale browser API-key
state cannot mask the real demo contract.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


DEFAULT_BACKEND_URL = "http://localhost:8080"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:1420"
DEFAULT_ORG_ID = "default"
DEFAULT_MESSAGE = "Xin chao Wiii, hay tra loi ngan gon de kiem tra demo local."
DEFAULT_DEMO_EMAIL = "dev@localhost"
DEFAULT_DEMO_NAME = "Dev User"
DEFAULT_DEMO_ROLE = "admin"
DEFAULT_EXPECTED_PLATFORM_ROLE = "platform_admin"


class SmokeFailure(RuntimeError):
    """Raised when a smoke check fails."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.text())
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"Invalid JSON from {self.url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise SmokeFailure(f"Expected JSON object from {self.url}")
        return payload


@dataclass(frozen=True)
class SseReadResult:
    events: list[tuple[str, str]]
    first_event_seconds: float | None
    first_answer_seconds: float | None
    total_seconds: float


def join_url(base_url: str, path: str) -> str:
    """Join a base URL and absolute path without importing extra deps."""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def request_bytes(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
    raise_http_errors: bool = True,
) -> HttpResponse:
    request_headers = {
        "User-Agent": "wiii-local-demo-smoke/1.0",
        **(headers or {}),
    }
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
                url=url,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if not raise_http_errors:
            return HttpResponse(
                status=exc.code,
                headers=dict(exc.headers.items()),
                body=body,
                url=url,
            )
        body_text = body.decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {url} -> HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"{method} {url} failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SmokeFailure(f"{method} {url} timed out after {timeout}s") from exc


def request_sse_events(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    idle_timeout: float = 10.0,
    max_total_seconds: float = 90.0,
) -> SseReadResult:
    request_headers = {
        "User-Agent": "wiii-local-demo-smoke/1.0",
        **(headers or {}),
    }
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method.upper(),
    )
    started_at = time.monotonic()
    events: list[tuple[str, str]] = []
    event_name = "message"
    data_lines: list[str] = []
    first_event_seconds: float | None = None
    first_answer_seconds: float | None = None

    def elapsed() -> float:
        return time.monotonic() - started_at

    def flush() -> None:
        nonlocal event_name, data_lines, first_event_seconds, first_answer_seconds
        if event_name != "message" or data_lines:
            data = "\n".join(data_lines)
            events.append((event_name, data))
            current_elapsed = elapsed()
            if first_event_seconds is None:
                first_event_seconds = current_elapsed
            if event_name == "answer" and data.strip() and first_answer_seconds is None:
                first_answer_seconds = current_elapsed
        event_name = "message"
        data_lines = []

    try:
        with urllib.request.urlopen(req, timeout=idle_timeout) as response:
            if response.status != 200:
                raise SmokeFailure(f"{method} {url} -> HTTP {response.status}")
            while True:
                if max_total_seconds and elapsed() > max_total_seconds:
                    raise SmokeFailure(
                        f"{method} {url} exceeded SSE total budget "
                        f"{max_total_seconds:.1f}s"
                    )
                raw_line = response.readline()
                if raw_line == b"":
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
                if not line:
                    flush()
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip() or "message"
                    continue
                if line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].lstrip())
                    continue
            flush()
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {url} -> HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"{method} {url} failed: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        if events:
            event_names = ",".join(dict.fromkeys(name for name, _data in events))
            raise SmokeFailure(
                f"{method} {url} SSE idle timeout after {idle_timeout:.1f}s "
                f"(events so far: {event_names})"
            ) from exc
        raise SmokeFailure(
            f"{method} {url} had no SSE data for {idle_timeout:.1f}s"
        ) from exc

    return SseReadResult(
        events=events,
        first_event_seconds=first_event_seconds,
        first_answer_seconds=first_answer_seconds,
        total_seconds=elapsed(),
    )


def parse_sse_events(text: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    event_name = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if event_name != "message" or data_lines:
            events.append((event_name, "\n".join(data_lines)))
        event_name = "message"
        data_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            flush()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
            continue

    flush()
    return events


def build_chat_payload(
    *,
    user: dict[str, Any],
    message: str,
    session_id: str,
    org_id: str,
    domain_id: str | None,
    provider: str | None,
    model: str | None,
) -> dict[str, Any]:
    role = user.get("role") if user.get("role") in {"student", "teacher", "admin"} else "admin"
    payload: dict[str, Any] = {
        "user_id": str(user.get("id") or "local-demo-user"),
        "message": message,
        "role": role,
        "session_id": session_id,
        "thread_id": "new",
        "organization_id": org_id,
    }
    if domain_id:
        payload["domain_id"] = domain_id
    if provider:
        payload["provider"] = provider
    if model:
        payload["model"] = model
    return payload


def decode_json_object(data: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_event_content(data: str) -> str:
    payload = decode_json_object(data)
    if payload is None:
        return data.strip()
    content = payload.get("content")
    if isinstance(content, str):
        return content.strip()
    return data.strip()


class DemoSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.passed = 0
        self.failed = 0
        self.token = ""
        self.user: dict[str, Any] = {}

    def run_check(self, name: str, func) -> bool:  # type: ignore[no-untyped-def]
        start = time.monotonic()
        try:
            func()
        except SmokeFailure as exc:
            self.failed += 1
            print(f"[FAIL] {name} - {exc}")
            return False
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            self.failed += 1
            print(f"[FAIL] {name} - unexpected error: {exc}")
            return False
        elapsed = time.monotonic() - start
        print(f"[PASS] {name} ({elapsed:.1f}s)")
        self.passed += 1
        return True

    def api_url(self, path: str) -> str:
        return join_url(self.args.backend_url, path)

    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            raise SmokeFailure("No access token available")
        headers = {"Authorization": f"Bearer {self.token}"}
        if self.args.org_id:
            headers["X-Organization-ID"] = self.args.org_id
        return headers

    def expected_provider(self) -> str | None:
        if self.args.expect_provider:
            return self.args.expect_provider
        if (
            self.args.provider
            and self.args.provider != "auto"
            and not self.args.allow_provider_failover
        ):
            return self.args.provider
        return None

    def expected_model(self) -> str | None:
        return self.args.expect_model or self.args.model

    def validate_runtime_metadata(self, metadata: dict[str, Any], *, source: str) -> str:
        provider = str(metadata.get("provider") or metadata.get("active_provider") or "").strip()
        model = str(metadata.get("model") or metadata.get("model_name") or "").strip()
        if not provider or provider == "unknown":
            raise SmokeFailure(f"{source} metadata did not include provider")
        if not model or model == "unknown":
            raise SmokeFailure(f"{source} metadata did not include model")

        expected_provider = self.expected_provider()
        if expected_provider and provider != expected_provider:
            raise SmokeFailure(
                f"{source} used provider={provider!r}; expected {expected_provider!r}"
            )
        expected_model = self.expected_model()
        if expected_model and model != expected_model:
            raise SmokeFailure(
                f"{source} used model={model!r}; expected {expected_model!r}"
            )
        return f"provider={provider} model={model}"

    def check_backend_health(self) -> str:
        statuses: list[str] = []
        for path in (
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/api/v1/health",
        ):
            response = request_bytes(
                "GET",
                self.api_url(path),
                timeout=self.args.timeout,
            )
            if response.status != 200:
                raise SmokeFailure(f"{path} returned HTTP {response.status}")
            statuses.append(path.rsplit("/", 1)[-1])
        return ", ".join(statuses)

    def check_frontend(self) -> str:
        response = request_bytes(
            "GET",
            self.args.frontend_url,
            timeout=self.args.timeout,
        )
        if response.status != 200:
            raise SmokeFailure(f"frontend returned HTTP {response.status}")
        return self.args.frontend_url

    def check_dev_login_status(self) -> str:
        payload = request_bytes(
            "GET",
            self.api_url("/api/v1/auth/dev-login/status"),
            timeout=self.args.timeout,
        ).json()
        if payload.get("enabled") is not True:
            raise SmokeFailure("dev-login is disabled; enable it for local demo")
        return "enabled"

    def check_dev_login(self) -> str:
        payload = request_bytes(
            "POST",
            self.api_url("/api/v1/auth/dev-login"),
            payload={
                "email": self.args.demo_email,
                "name": self.args.demo_name,
                "role": self.args.demo_role,
            },
            timeout=self.args.timeout,
        ).json()
        token = payload.get("access_token")
        user = payload.get("user")
        if not isinstance(token, str) or not token:
            raise SmokeFailure("dev-login did not return access_token")
        if not isinstance(user, dict):
            raise SmokeFailure("dev-login did not return user object")
        if user.get("email") != self.args.demo_email:
            raise SmokeFailure(
                f"dev-login returned unexpected email {user.get('email')!r}; "
                f"expected {self.args.demo_email!r}"
            )
        if user.get("role") != self.args.demo_role:
            raise SmokeFailure(
                f"dev-login returned unexpected role {user.get('role')!r}; "
                f"expected {self.args.demo_role!r}"
            )
        if user.get("platform_role") != self.args.expected_platform_role:
            raise SmokeFailure(
                f"dev-login returned unexpected platform_role "
                f"{user.get('platform_role')!r}; expected {self.args.expected_platform_role!r}"
            )
        self.token = token
        self.user = user
        role = user.get("role")
        platform_role = user.get("platform_role")
        return f"{user.get('email')} role={role} platform_role={platform_role}"

    def check_profile(self) -> str:
        payload = request_bytes(
            "GET",
            self.api_url("/api/v1/users/me"),
            headers=self.auth_headers(),
            timeout=self.args.timeout,
        ).json()
        if payload.get("id") != self.user.get("id"):
            raise SmokeFailure("profile user id does not match dev-login user")
        return f"{payload.get('email')} active_org={payload.get('active_organization_id')}"

    def check_admin_context(self) -> str:
        payload = request_bytes(
            "GET",
            self.api_url("/api/v1/users/me/admin-context"),
            headers=self.auth_headers(),
            timeout=self.args.timeout,
        ).json()
        if payload.get("is_system_admin") is not True:
            raise SmokeFailure("current user is not system admin")
        if payload.get("is_org_admin") is not True:
            raise SmokeFailure("current user is not org admin")
        return f"admin_org_ids={payload.get('admin_org_ids')}"

    def check_runtime_config(self) -> str:
        payload = request_bytes(
            "GET",
            self.api_url("/api/v1/admin/llm-runtime"),
            headers=self.auth_headers(),
            timeout=self.args.timeout,
        ).json()
        active_provider = str(payload.get("active_provider") or payload.get("provider") or "").strip()
        expected_provider = self.expected_provider()
        if expected_provider == "nvidia":
            if not payload.get("nvidia_base_url"):
                raise SmokeFailure("NVIDIA base URL is missing from runtime config")
            if not payload.get("nvidia_model"):
                raise SmokeFailure("NVIDIA flash model is missing from runtime config")
            if not payload.get("nvidia_model_advanced"):
                raise SmokeFailure("NVIDIA pro model is missing from runtime config")
            if payload.get("nvidia_api_key_configured") is not True:
                raise SmokeFailure("NVIDIA API key is not configured")

            nvidia_status = None
            for status in payload.get("provider_status") or []:
                if isinstance(status, dict) and status.get("provider") == "nvidia":
                    nvidia_status = status
                    break
            if not nvidia_status:
                raise SmokeFailure("NVIDIA provider is missing from provider_status")
            if nvidia_status.get("configured") is not True:
                raise SmokeFailure("NVIDIA provider is not configured")
            if nvidia_status.get("request_selectable") is not True:
                raise SmokeFailure("NVIDIA provider is not request-selectable")

        nvidia_key = payload.get("nvidia_api_key_configured")
        nvidia_model = payload.get("nvidia_model")
        return (
            f"active={active_provider or 'unknown'} "
            f"nvidia_key={nvidia_key} nvidia_model={nvidia_model}"
        )

    def check_org_permissions(self) -> str:
        response = request_bytes(
            "GET",
            self.api_url(f"/api/v1/organizations/{self.args.org_id}/permissions"),
            headers=self.auth_headers(),
            timeout=self.args.timeout,
            raise_http_errors=False,
        )
        if response.status == 404:
            payload = response.json()
            detail = str(payload.get("detail", ""))
            if "multi-tenant" in detail.lower():
                return "skipped: multi-tenant disabled"
            raise SmokeFailure(f"organization permissions returned HTTP 404: {detail}")
        if response.status != 200:
            raise SmokeFailure(
                f"organization permissions returned HTTP {response.status}: {response.text()}"
            )
        payload = response.json()
        org_role = payload.get("org_role")
        if org_role in {"owner", "admin"}:
            return f"{self.args.org_id} org_role={org_role}"
        platform_role = payload.get("platform_role")
        permission_role = payload.get("permission_role") or payload.get("role")
        if platform_role == "platform_admin" and permission_role == "admin":
            return f"{self.args.org_id} platform_role=platform_admin org_role={org_role or 'none'}"
        raise SmokeFailure(
            f"expected owner/admin org_role or platform_admin permission, "
            f"got org_role={org_role!r} platform_role={platform_role!r} "
            f"permission_role={permission_role!r}"
        )

    def chat_payload(self, *, session_suffix: str) -> dict[str, Any]:
        return build_chat_payload(
            user=self.user,
            message=self.args.message,
            session_id=f"{self.args.session_id}-{session_suffix}",
            org_id=self.args.org_id,
            domain_id=self.args.domain_id,
            provider=self.args.provider,
            model=self.args.model,
        )

    def check_sync_chat(self) -> str:
        payload = request_bytes(
            "POST",
            self.api_url("/api/v1/chat"),
            headers=self.auth_headers(),
            payload=self.chat_payload(session_suffix="sync"),
            timeout=self.args.chat_timeout,
        ).json()
        if payload.get("status") != "success":
            raise SmokeFailure(f"chat status is not success: {payload}")
        answer = ((payload.get("data") or {}).get("answer") or "").strip()
        if not answer:
            raise SmokeFailure("chat response did not include a non-empty answer")
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise SmokeFailure("chat response metadata is not an object")
        runtime_detail = self.validate_runtime_metadata(metadata, source="sync chat")
        return f"{runtime_detail} answer_chars={len(answer)}"

    def check_stream_chat(self) -> str:
        result = request_sse_events(
            "POST",
            self.api_url("/api/v1/chat/stream/v3"),
            headers={
                **self.auth_headers(),
                "Accept": "text/event-stream",
            },
            payload=self.chat_payload(session_suffix="stream"),
            idle_timeout=self.args.stream_idle_timeout,
            max_total_seconds=min(
                self.args.stream_timeout,
                self.args.max_stream_total_seconds,
            ),
        )
        events = result.events
        event_names = [name for name, _data in events]
        if "error" in event_names:
            error_data = next(data for name, data in events if name == "error")
            raise SmokeFailure(f"stream emitted error event: {error_data}")
        if "answer" not in event_names:
            raise SmokeFailure(f"stream did not emit answer event; saw {event_names}")
        if "metadata" not in event_names:
            raise SmokeFailure(f"stream did not emit metadata event; saw {event_names}")
        if "done" not in event_names:
            raise SmokeFailure(f"stream did not emit done event; saw {event_names}")

        if (
            result.first_event_seconds is None
            or result.first_event_seconds > self.args.max_first_event_seconds
        ):
            raise SmokeFailure(
                "stream first event exceeded budget: "
                f"{result.first_event_seconds}s > {self.args.max_first_event_seconds}s"
            )
        if (
            result.first_answer_seconds is None
            or result.first_answer_seconds > self.args.max_first_answer_seconds
        ):
            raise SmokeFailure(
                "stream first answer exceeded budget: "
                f"{result.first_answer_seconds}s > {self.args.max_first_answer_seconds}s"
            )

        answer_chars = sum(
            len(extract_event_content(data))
            for name, data in events
            if name == "answer"
        )
        if answer_chars <= 0:
            raise SmokeFailure("stream answer events were empty")

        metadata_payload = None
        for name, data in reversed(events):
            if name == "metadata":
                metadata_payload = decode_json_object(data)
                if metadata_payload is not None:
                    break
        if metadata_payload is None:
            raise SmokeFailure("stream metadata event was not a JSON object")
        runtime_detail = self.validate_runtime_metadata(
            metadata_payload,
            source="stream chat",
        )
        unique_events = ",".join(dict.fromkeys(event_names))
        return (
            f"{runtime_detail} events={unique_events} "
            f"first_event={result.first_event_seconds:.1f}s "
            f"first_answer={result.first_answer_seconds:.1f}s "
            f"total={result.total_seconds:.1f}s"
        )

    def run(self) -> int:
        print("=== Wiii Local Demo Smoke Gate ===")
        print(f"Backend:  {self.args.backend_url}")
        if not self.args.skip_frontend:
            print(f"Frontend: {self.args.frontend_url}")
        print(f"Org:      {self.args.org_id}")
        print("")

        self.run_check("backend health", self.check_backend_health)
        if not self.args.skip_frontend:
            self.run_check("frontend reachable", self.check_frontend)

        login_ready = self.run_check("dev-login status", self.check_dev_login_status)
        if login_ready and self.run_check("dev-login JWT", self.check_dev_login):
            self.run_check("authenticated profile", self.check_profile)
            self.run_check("admin context", self.check_admin_context)
            if not self.args.skip_runtime_config:
                self.run_check("runtime config", self.check_runtime_config)
            self.run_check("organization permissions", self.check_org_permissions)

            if not self.args.skip_chat:
                self.run_check("sync chat", self.check_sync_chat)
            if not self.args.skip_stream:
                self.run_check("stream v3 chat", self.check_stream_chat)

        print("")
        print(f"=== Results: {self.passed} passed, {self.failed} failed ===")
        if self.failed:
            print("Local demo is not ready. Fix the failed checks before presenting.")
            return 1
        print("Local demo contract is ready.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify local Wiii dev-login, admin, chat, stream, and frontend demo readiness.",
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--org-id", default=DEFAULT_ORG_ID)
    parser.add_argument("--demo-email", default=DEFAULT_DEMO_EMAIL)
    parser.add_argument("--demo-name", default=DEFAULT_DEMO_NAME)
    parser.add_argument("--demo-role", choices=("student", "teacher", "admin"), default=DEFAULT_DEMO_ROLE)
    parser.add_argument("--expected-platform-role", default=DEFAULT_EXPECTED_PLATFORM_ROLE)
    parser.add_argument("--domain-id", default="maritime")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--expect-provider", default=None)
    parser.add_argument("--expect-model", default=None)
    parser.add_argument("--allow-provider-failover", action="store_true")
    parser.add_argument("--session-id", default=f"local-demo-{int(time.time())}")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--chat-timeout", type=float, default=45.0)
    parser.add_argument("--stream-timeout", type=float, default=90.0)
    parser.add_argument("--stream-idle-timeout", type=float, default=20.0)
    parser.add_argument("--max-first-event-seconds", type=float, default=5.0)
    parser.add_argument("--max-first-answer-seconds", type=float, default=45.0)
    parser.add_argument("--max-stream-total-seconds", type=float, default=90.0)
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-runtime-config", action="store_true")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return DemoSmoke(args).run()


if __name__ == "__main__":
    sys.exit(main())
