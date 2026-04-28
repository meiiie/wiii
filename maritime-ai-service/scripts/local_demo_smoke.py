#!/usr/bin/env python3
"""Local demo smoke gate for Wiii.

This script verifies the same local JWT/dev-login path that the desktop app
uses for demos. It intentionally avoids API-key auth so stale browser API-key
state cannot mask the real demo contract.
"""

from __future__ import annotations

import argparse
import json
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
            detail = func()
        except SmokeFailure as exc:
            self.failed += 1
            print(f"[FAIL] {name} - {exc}")
            return False
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            self.failed += 1
            print(f"[FAIL] {name} - unexpected error: {exc}")
            return False
        elapsed = time.monotonic() - start
        suffix = f" - {detail}" if detail else ""
        print(f"[PASS] {name}{suffix} ({elapsed:.1f}s)")
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
        provider = metadata.get("provider", "unknown")
        model = metadata.get("model", "unknown")
        return f"provider={provider} model={model} answer_chars={len(answer)}"

    def check_stream_chat(self) -> str:
        response = request_bytes(
            "POST",
            self.api_url("/api/v1/chat/stream/v3"),
            headers={
                **self.auth_headers(),
                "Accept": "text/event-stream",
            },
            payload=self.chat_payload(session_suffix="stream"),
            timeout=self.args.stream_timeout,
        )
        events = parse_sse_events(response.text())
        event_names = [name for name, _data in events]
        if "error" in event_names:
            error_data = next(data for name, data in events if name == "error")
            raise SmokeFailure(f"stream emitted error event: {error_data}")
        if "done" not in event_names:
            raise SmokeFailure(f"stream did not emit done event; saw {event_names}")
        return f"events={','.join(dict.fromkeys(event_names))}"

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
    parser.add_argument("--session-id", default=f"local-demo-{int(time.time())}")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--chat-timeout", type=float, default=45.0)
    parser.add_argument("--stream-timeout", type=float, default=90.0)
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return DemoSmoke(args).run()


if __name__ == "__main__":
    sys.exit(main())
