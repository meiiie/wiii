from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "local_demo_smoke.py"
SPEC = importlib.util.spec_from_file_location("local_demo_smoke", SCRIPT_PATH)
assert SPEC is not None
local_demo_smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = local_demo_smoke
SPEC.loader.exec_module(local_demo_smoke)


def _demo_args(**overrides):
    defaults = {
        "backend_url": "http://localhost:8080",
        "frontend_url": "http://127.0.0.1:1420",
        "org_id": "default",
        "domain_id": "maritime",
        "provider": "auto",
        "model": None,
        "expect_provider": None,
        "expect_model": None,
        "allow_provider_failover": False,
        "session_id": "session-1",
        "message": "Xin chao",
        "timeout": 8.0,
        "chat_timeout": 45.0,
        "stream_timeout": 90.0,
        "stream_idle_timeout": 20.0,
        "max_first_event_seconds": 5.0,
        "max_first_answer_seconds": 45.0,
        "max_stream_total_seconds": 90.0,
        "skip_frontend": True,
        "skip_runtime_config": True,
        "skip_chat": True,
        "skip_stream": True,
        "demo_email": "dev@localhost",
        "demo_name": "Dev User",
        "demo_role": "admin",
        "expected_platform_role": "platform_admin",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _json_response(payload: dict, *, status: int = 200):
    return local_demo_smoke.HttpResponse(
        status=status,
        headers={"content-type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
        url="http://localhost/test",
    )


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
        model="gemini-3.1-flash-lite-preview",
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
        "model": "gemini-3.1-flash-lite-preview",
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


def test_check_dev_login_posts_and_validates_pinned_identity(monkeypatch):
    seen_payloads = []

    def fake_request_bytes(method, url, *, payload=None, **kwargs):
        seen_payloads.append(payload)
        return _json_response(
            {
                "access_token": "ACCESS",
                "user": {
                    "id": "dev-user-1",
                    "email": "dev@localhost",
                    "role": "admin",
                    "platform_role": "platform_admin",
                },
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args())
    detail = smoke.check_dev_login()

    assert seen_payloads == [
        {"email": "dev@localhost", "name": "Dev User", "role": "admin"}
    ]
    assert "dev@localhost" in detail
    assert smoke.user["platform_role"] == "platform_admin"


def test_check_dev_login_rejects_unexpected_platform_role(monkeypatch):
    def fake_request_bytes(method, url, *, payload=None, **kwargs):
        return _json_response(
            {
                "access_token": "ACCESS",
                "user": {
                    "id": "dev-user-1",
                    "email": "dev@localhost",
                    "role": "admin",
                    "platform_role": "user",
                },
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args())
    with pytest.raises(local_demo_smoke.SmokeFailure, match="platform_role"):
        smoke.check_dev_login()


def test_check_org_permissions_skips_when_multi_tenant_disabled(monkeypatch):
    def fake_request_bytes(method, url, *, raise_http_errors=True, **kwargs):
        assert raise_http_errors is False
        return _json_response({"detail": "Multi-tenant is not enabled"}, status=404)

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args())
    smoke.token = "ACCESS"
    detail = smoke.check_org_permissions()

    assert detail == "skipped: multi-tenant disabled"


def test_check_org_permissions_accepts_platform_admin_without_org_role(monkeypatch):
    def fake_request_bytes(method, url, *, raise_http_errors=True, **kwargs):
        assert raise_http_errors is False
        return _json_response(
            {
                "platform_role": "platform_admin",
                "permission_role": "admin",
                "org_role": None,
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args())
    smoke.token = "ACCESS"
    detail = smoke.check_org_permissions()

    assert detail == "default platform_role=platform_admin org_role=none"


def test_check_runtime_config_requires_pinned_nvidia_selectable(monkeypatch):
    def fake_request_bytes(method, url, *, headers=None, **kwargs):
        return _json_response(
            {
                "active_provider": "nvidia",
                "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
                "nvidia_model": "deepseek-ai/deepseek-v4-flash",
                "nvidia_model_advanced": "deepseek-ai/deepseek-v4-pro",
                "nvidia_api_key_configured": True,
                "provider_status": [
                    {
                        "provider": "nvidia",
                        "configured": True,
                        "request_selectable": True,
                    }
                ],
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args(provider="nvidia"))
    smoke.token = "ACCESS"
    detail = smoke.check_runtime_config()

    assert "active=nvidia" in detail
    assert "nvidia_key=True" in detail


def test_check_runtime_config_rejects_missing_nvidia_key(monkeypatch):
    def fake_request_bytes(method, url, *, headers=None, **kwargs):
        return _json_response(
            {
                "active_provider": "nvidia",
                "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
                "nvidia_model": "deepseek-ai/deepseek-v4-flash",
                "nvidia_model_advanced": "deepseek-ai/deepseek-v4-pro",
                "nvidia_api_key_configured": False,
                "provider_status": [
                    {
                        "provider": "nvidia",
                        "configured": False,
                        "request_selectable": False,
                    }
                ],
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(_demo_args(provider="nvidia"))
    smoke.token = "ACCESS"
    with pytest.raises(local_demo_smoke.SmokeFailure, match="NVIDIA API key"):
        smoke.check_runtime_config()


def test_check_sync_chat_enforces_provider_and_model_metadata(monkeypatch):
    def fake_request_bytes(method, url, *, payload=None, **kwargs):
        return _json_response(
            {
                "status": "success",
                "data": {"answer": "Chao ban."},
                "metadata": {
                    "provider": "nvidia",
                    "model": "deepseek-ai/deepseek-v4-flash",
                },
            }
        )

    monkeypatch.setattr(local_demo_smoke, "request_bytes", fake_request_bytes)

    smoke = local_demo_smoke.DemoSmoke(
        _demo_args(
            provider="nvidia",
            model="deepseek-ai/deepseek-v4-flash",
        )
    )
    smoke.user = {"id": "dev-user-1", "role": "admin"}
    smoke.token = "ACCESS"
    detail = smoke.check_sync_chat()

    assert "provider=nvidia" in detail
    assert "model=deepseek-ai/deepseek-v4-flash" in detail


def test_check_stream_chat_requires_answer_metadata_done_and_latency(monkeypatch):
    def fake_request_sse_events(method, url, *, payload=None, **kwargs):
        return local_demo_smoke.SseReadResult(
            events=[
                ("status", '{"content":"Dang chuan bi"}'),
                ("answer", '{"content":"Chao ban qua SSE"}'),
                (
                    "metadata",
                    (
                        '{"provider":"nvidia",'
                        '"model":"deepseek-ai/deepseek-v4-flash"}'
                    ),
                ),
                ("done", '{"processing_time":0.2}'),
            ],
            first_event_seconds=0.2,
            first_answer_seconds=0.8,
            total_seconds=1.0,
        )

    monkeypatch.setattr(local_demo_smoke, "request_sse_events", fake_request_sse_events)

    smoke = local_demo_smoke.DemoSmoke(
        _demo_args(
            provider="nvidia",
            model="deepseek-ai/deepseek-v4-flash",
        )
    )
    smoke.user = {"id": "dev-user-1", "role": "admin"}
    smoke.token = "ACCESS"
    detail = smoke.check_stream_chat()

    assert "provider=nvidia" in detail
    assert "first_answer=0.8s" in detail


def test_check_stream_chat_rejects_silent_answer_latency(monkeypatch):
    def fake_request_sse_events(method, url, *, payload=None, **kwargs):
        return local_demo_smoke.SseReadResult(
            events=[
                ("status", '{"content":"Dang chuan bi"}'),
                ("answer", '{"content":"Qua cham"}'),
                (
                    "metadata",
                    (
                        '{"provider":"nvidia",'
                        '"model":"deepseek-ai/deepseek-v4-flash"}'
                    ),
                ),
                ("done", '{"processing_time":72.0}'),
            ],
            first_event_seconds=0.1,
            first_answer_seconds=72.0,
            total_seconds=72.1,
        )

    monkeypatch.setattr(local_demo_smoke, "request_sse_events", fake_request_sse_events)

    smoke = local_demo_smoke.DemoSmoke(
        _demo_args(
            provider="nvidia",
            model="deepseek-ai/deepseek-v4-flash",
        )
    )
    smoke.user = {"id": "dev-user-1", "role": "admin"}
    smoke.token = "ACCESS"
    with pytest.raises(local_demo_smoke.SmokeFailure, match="first answer"):
        smoke.check_stream_chat()
