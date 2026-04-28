from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "local_demo_smoke.py"
SPEC = importlib.util.spec_from_file_location("local_demo_smoke", SCRIPT_PATH)
assert SPEC is not None
local_demo_smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = local_demo_smoke
SPEC.loader.exec_module(local_demo_smoke)


def test_join_url_normalizes_slashes():
    assert (
        local_demo_smoke.join_url("http://localhost:8080/", "/api/v1/health")
        == "http://localhost:8080/api/v1/health"
    )


def test_parse_sse_events_collects_named_events_and_multiline_data():
    text = (
        ": keepalive\n\n"
        "event: status\n"
        "data: {\"content\":\"Dang xu ly\"}\n\n"
        "event: answer\n"
        "data: dong 1\n"
        "data: dong 2\n\n"
        "event: done\n"
        "data: {\"processing_time\":0.1}\n\n"
    )

    assert local_demo_smoke.parse_sse_events(text) == [
        ("status", '{"content":"Dang xu ly"}'),
        ("answer", "dong 1\ndong 2"),
        ("done", '{"processing_time":0.1}'),
    ]


def test_build_chat_payload_uses_dev_login_identity_and_runtime_hints():
    payload = local_demo_smoke.build_chat_payload(
        user={"id": "dev-user-1", "role": "admin"},
        message="Xin chao",
        session_id="session-1",
        org_id="default",
        domain_id="maritime",
        provider="google",
        model="gemini-2.5-flash",
    )

    assert payload == {
        "user_id": "dev-user-1",
        "message": "Xin chao",
        "role": "admin",
        "session_id": "session-1",
        "thread_id": "new",
        "organization_id": "default",
        "domain_id": "maritime",
        "provider": "google",
        "model": "gemini-2.5-flash",
    }


def test_build_chat_payload_falls_back_to_admin_role_for_unknown_dev_role():
    payload = local_demo_smoke.build_chat_payload(
        user={"id": "dev-user-1", "role": "platform_admin"},
        message="Xin chao",
        session_id="session-1",
        org_id="default",
        domain_id=None,
        provider=None,
        model=None,
    )

    assert payload["role"] == "admin"
    assert "domain_id" not in payload
    assert "provider" not in payload
    assert "model" not in payload
