"""Phase 10d edge endpoints — Runtime Migration #207.

Locks the OpenAI / Anthropic compat surface contract:
- 503 when ``enable_native_runtime`` is off (default).
- 200 with the upstream wire shape when on, derived from the existing
  ChatService output via the Phase 4 protocol adapters.
- 400 when the body has no user-role message.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.edge_endpoints import router as edge_router
from app.api.deps import require_auth
from app.models.schemas import (
    AgentType,
    InternalChatResponse,
)


@pytest.fixture
def fake_auth():
    """A minimal authenticated user double — only fields the router touches."""
    return SimpleNamespace(
        user_id="user-1",
        organization_id="org-1",
        role="student",
        auth_method="api_key",
    )


@pytest.fixture
def app(fake_auth):
    app = FastAPI()
    app.include_router(edge_router)
    app.dependency_overrides[require_auth] = lambda: fake_auth
    return app


@pytest.fixture
def fake_internal_response():
    return InternalChatResponse(
        message="Câu trả lời từ Wiii.",
        agent_type=AgentType.RAG,
        sources=None,
        metadata={"latency_ms": 42, "provider": "google", "model": "gemini-flash"},
    )


def _enable_runtime(monkeypatch):
    """Flip ``enable_native_runtime`` on for the duration of a test."""
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_native_runtime", True, raising=False
    )


# ── flag-off behaviour ──

@pytest.mark.asyncio
async def test_chat_completions_503_when_runtime_disabled(app, monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_native_runtime", False, raising=False
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["type"] == "service_unavailable"


@pytest.mark.asyncio
async def test_messages_503_when_runtime_disabled(app, monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_native_runtime", False, raising=False
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/messages",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert resp.status_code == 503


# ── happy paths ──

@pytest.mark.asyncio
async def test_openai_completions_returns_chat_completion_envelope(
    app, monkeypatch, fake_internal_response
):
    _enable_runtime(monkeypatch)
    fake_service = SimpleNamespace(
        process_message=AsyncMock(return_value=fake_internal_response)
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Chào Wiii"},
                    ],
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-4o-mini"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "Câu trả lời từ Wiii."
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["id"].startswith("chatcmpl-")
    # ChatService received exactly one call.
    fake_service.process_message.assert_awaited_once()
    chat_request = fake_service.process_message.await_args.args[0]
    assert chat_request.message == "Chào Wiii"
    assert chat_request.user_id == "user-1"
    assert chat_request.organization_id == "org-1"


@pytest.mark.asyncio
async def test_anthropic_messages_returns_message_envelope(
    app, monkeypatch, fake_internal_response
):
    _enable_runtime(monkeypatch)
    fake_service = SimpleNamespace(
        process_message=AsyncMock(return_value=fake_internal_response)
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-sonnet-4",
                    "system": "You are helpful.",
                    "messages": [
                        {"role": "user", "content": "Chào Wiii"},
                    ],
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["model"] == "claude-sonnet-4"
    assert body["content"] == [
        {"type": "text", "text": "Câu trả lời từ Wiii."}
    ]
    assert body["stop_reason"] == "end_turn"
    assert body["id"].startswith("msg_")


# ── error paths ──

@pytest.mark.asyncio
async def test_completions_rejects_no_user_message(app, monkeypatch):
    _enable_runtime(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "system", "content": "Hi only system."}]},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["type"] == "invalid_request"


@pytest.mark.asyncio
async def test_completions_rejects_non_dict_body(app, monkeypatch):
    _enable_runtime(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/chat/completions",
            json=["not", "a", "dict"],
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_messages_rejects_no_user_message(app, monkeypatch):
    _enable_runtime(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Anthropic messages with only assistant turn → no user content.
        resp = await client.post(
            "/v1/messages",
            json={
                "messages": [
                    {"role": "assistant", "content": "I'm ready."},
                ]
            },
        )
    assert resp.status_code == 400


# ── session bridging ──

@pytest.mark.asyncio
async def test_session_id_falls_back_to_user_when_omitted(
    app, monkeypatch, fake_internal_response
):
    _enable_runtime(monkeypatch)
    fake_service = SimpleNamespace(
        process_message=AsyncMock(return_value=fake_internal_response)
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
    assert resp.status_code == 200
    chat_request = fake_service.process_message.await_args.args[0]
    assert chat_request.session_id == "edge-user-1"


@pytest.mark.asyncio
async def test_explicit_session_id_propagates(
    app, monkeypatch, fake_internal_response
):
    _enable_runtime(monkeypatch)
    fake_service = SimpleNamespace(
        process_message=AsyncMock(return_value=fake_internal_response)
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "hi"}],
                    "session_id": "thread-42",
                },
            )
    assert resp.status_code == 200
    chat_request = fake_service.process_message.await_args.args[0]
    assert chat_request.session_id == "thread-42"
