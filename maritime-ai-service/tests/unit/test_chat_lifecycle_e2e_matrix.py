from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from app.api.deps import RequireAuth
from app.api.v1.chat import router as chat_router
from app.api.v1.chat_stream import router as chat_stream_router
from app.api.v1.chat_stream_presenter import format_sse
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.security import AuthenticatedUser, require_auth
from app.models.schemas import AgentType, InternalChatResponse, Source


def _student_auth() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="student-e2e",
        auth_method="api_key",
        role="student",
        platform_role="user",
    )


def _build_smoke_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(chat_stream_router, prefix="/api/v1")
    return app


def _transport(app: FastAPI) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=app)


@pytest.fixture
def smoke_app():
    app = _build_smoke_app()
    yield app
    app.dependency_overrides.clear()


def _thinking_lifecycle(node: str, text: str, *, phases: list[str] | None = None) -> dict:
    normalized_phases = phases or ["pre_tool", "final_snapshot"]
    return {
        "node": node,
        "summary": text[:80],
        "final_text": text,
        "segments": [
            {
                "phase": phase,
                "status": "completed",
                "provenance": "live_native" if phase != "final_snapshot" else "final_snapshot",
                "text": text,
            }
            for phase in normalized_phases
        ],
    }


SYNC_CASES = [
    {
        "id": "direct_selfhood",
        "request": {
            "message": "Wiii được sinh ra thế nào?",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "internal_response": InternalChatResponse(
            message="Mình ra đời trong The Wiii Lab như một hạt mầm sống số.",
            agent_type=AgentType.DIRECT,
            metadata={
                "session_id": "sync-direct-1",
                "provider": "openrouter",
                "model": "qwen/qwen3.6-plus:free",
                "runtime_authoritative": True,
                "thinking_content": "Mình đang lần lại khoảnh khắc đầu tiên của mình ở The Wiii Lab.",
                "thinking_lifecycle": _thinking_lifecycle(
                    "direct",
                    "Mình đang lần lại khoảnh khắc đầu tiên của mình ở The Wiii Lab.",
                ),
                "routing_metadata": {"final_agent": "direct", "intent": "selfhood"},
            },
        ),
        "assertions": [
            ("metadata.provider", "openrouter"),
            ("metadata.model", "qwen/qwen3.6-plus:free"),
            ("metadata.agent_type", "direct"),
            ("metadata.routing_metadata.intent", "selfhood"),
        ],
    },
    {
        "id": "memory_roundtrip",
        "request": {
            "message": "Bạn còn nhớ tên mình không?",
            "provider": "zhipu",
            "model": "glm-5",
        },
        "internal_response": InternalChatResponse(
            message="Mình nhớ, bạn là Nam.",
            agent_type=AgentType.MEMORY,
            metadata={
                "session_id": "sync-memory-1",
                "provider": "zhipu",
                "model": "glm-5",
                "runtime_authoritative": True,
                "thinking_content": "Mình đang gọi lại đúng mảnh định danh đã được giữ từ trước.",
                "thinking_lifecycle": _thinking_lifecycle(
                    "memory",
                    "Mình đang gọi lại đúng mảnh định danh đã được giữ từ trước.",
                    phases=["pre_tool", "post_tool", "final_snapshot"],
                ),
                "routing_metadata": {"final_agent": "memory", "intent": "personal"},
            },
        ),
        "assertions": [
            ("metadata.provider", "zhipu"),
            ("metadata.model", "glm-5"),
            ("metadata.agent_type", "memory"),
            ("metadata.routing_metadata.final_agent", "memory"),
        ],
    },
    {
        "id": "rag_lookup",
        "request": {
            "message": "Giải thích Quy tắc 15 COLREGs",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "internal_response": InternalChatResponse(
            message="Theo Quy tắc 15, tàu thấy tàu kia ở mạn phải phải nhường đường.",
            agent_type=AgentType.RAG,
            sources=[
                Source(
                    node_id="rule-15",
                    title="COLREG Rule 15",
                    source_type="regulation",
                    content_snippet="When two power-driven vessels are crossing...",
                )
            ],
            metadata={
                "session_id": "sync-rag-1",
                "provider": "openrouter",
                "model": "qwen/qwen3.6-plus:free",
                "runtime_authoritative": True,
                "thinking_content": "Mình đang bám nguồn điều luật trước khi kết luận ngắn gọn.",
                "thinking_lifecycle": _thinking_lifecycle(
                    "rag_agent",
                    "Mình đang bám nguồn điều luật trước khi kết luận ngắn gọn.",
                    phases=["pre_tool", "post_tool", "final_snapshot"],
                ),
                "routing_metadata": {"final_agent": "rag_agent", "intent": "lookup"},
            },
        ),
        "assertions": [
            ("metadata.agent_type", "rag"),
            ("metadata.routing_metadata.intent", "lookup"),
            ("data.sources.0.title", "COLREG Rule 15"),
        ],
    },
]


def _get_path(payload: dict, path: str):
    current = payload
    for raw_part in path.split("."):
        if isinstance(current, list):
            current = current[int(raw_part)]
        else:
            current = current[raw_part]
    return current


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SYNC_CASES, ids=[case["id"] for case in SYNC_CASES])
async def test_chat_sync_lifecycle_matrix(smoke_app, case):
    smoke_app.dependency_overrides[require_auth] = _student_auth

    with patch(
        "app.api.v1.chat_completion_endpoint_support.process_chat_completion_request",
        new=AsyncMock(return_value=case["internal_response"].model_copy(deep=True)),
    ):
        async with httpx.AsyncClient(
            transport=_transport(smoke_app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={
                    "user_id": "student-e2e",
                    "message": case["request"]["message"],
                    "role": "student",
                    "provider": case["request"]["provider"],
                    "model": case["request"]["model"],
                },
            )

    assert response.status_code == 200
    payload = response.json()
    for path, expected in case["assertions"]:
        assert _get_path(payload, path) == expected
    assert payload["metadata"]["thinking_content"]
    assert payload["metadata"]["thinking_lifecycle"]["segments"]


STREAM_CASES = [
    {
        "id": "direct_origin_stream",
        "request": {
            "message": "Wiii được sinh ra thế nào?",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "events": [
            (
                "thinking_start",
                {
                    "type": "thinking_start",
                    "content": "",
                    "node": "direct",
                    "summary": "Truy lại nguồn gốc của mình",
                },
            ),
            (
                "thinking_delta",
                {
                    "content": "Mình đang lần lại khoảnh khắc đầu tiên của mình.",
                    "node": "direct",
                },
            ),
            (
                "thinking_end",
                {
                    "type": "thinking_end",
                    "node": "direct",
                },
            ),
            (
                "answer",
                {
                    "content": "Mình ra đời trong The Wiii Lab như một hạt mầm sống số.",
                },
            ),
            (
                "metadata",
                {
                    "provider": "openrouter",
                    "model": "qwen/qwen3.6-plus:free",
                    "agent_type": "direct",
                    "thinking_content": "Mình đang lần lại khoảnh khắc đầu tiên của mình.",
                    "thinking_lifecycle": _thinking_lifecycle(
                        "direct",
                        "Mình đang lần lại khoảnh khắc đầu tiên của mình.",
                    ),
                },
            ),
            ("done", {"processing_time": 0.1}),
        ],
        "needles": [
            "event: thinking_start",
            "event: thinking_delta",
            "event: answer",
            '"provider": "openrouter"',
            '"model": "qwen/qwen3.6-plus:free"',
        ],
    },
    {
        "id": "tutor_visual_stream",
        "request": {
            "message": "Giải thích Quy tắc 15 rồi làm visual cho mình",
            "provider": "ollama",
            "model": "gemma3:4b",
        },
        "events": [
            (
                "status",
                {
                    "content": "Đang mở lane tutor...",
                    "step": "routing",
                    "node": "tutor_agent",
                },
            ),
            (
                "tool_call",
                {
                    "content": "render_visual_rule15",
                    "node": "tutor_agent",
                    "step": "tool_call",
                },
            ),
            (
                "sources",
                {
                    "sources": [
                        {
                            "title": "COLREG Rule 15",
                            "content": "When two power-driven vessels are crossing...",
                        }
                    ]
                },
            ),
            (
                "metadata",
                {
                    "provider": "ollama",
                    "model": "gemma3:4b",
                    "agent_type": "tutor",
                    "thinking_content": "Mình đang nối giải thích điều luật với một visual dễ nhìn.",
                    "thinking_lifecycle": _thinking_lifecycle(
                        "tutor_agent",
                        "Mình đang nối giải thích điều luật với một visual dễ nhìn.",
                        phases=["pre_tool", "tool_continuation", "post_tool", "final_snapshot"],
                    ),
                },
            ),
            ("done", {"processing_time": 0.3}),
        ],
        "needles": [
            "event: status",
            "event: tool_call",
            "event: sources",
            '"provider": "ollama"',
            '"model": "gemma3:4b"',
        ],
    },
    {
        "id": "rag_lookup_stream",
        "request": {
            "message": "Quy tắc 15 COLREGs là gì?",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "events": [
            (
                "thinking_start",
                {
                    "type": "thinking_start",
                    "content": "",
                    "node": "rag_agent",
                    "summary": "Kiểm tra nguồn điều luật",
                },
            ),
            (
                "thinking_delta",
                {
                    "content": "Mình đang bám điều luật trước khi trả lời ngắn gọn.",
                    "node": "rag_agent",
                },
            ),
            (
                "answer",
                {
                    "content": "Theo Quy tắc 15, tàu thấy tàu kia ở mạn phải phải nhường đường.",
                },
            ),
            (
                "sources",
                {
                    "sources": [
                        {
                            "title": "COLREG Rule 15",
                            "content": "When two power-driven vessels are crossing...",
                        }
                    ]
                },
            ),
            (
                "metadata",
                {
                    "provider": "openrouter",
                    "model": "qwen/qwen3.6-plus:free",
                    "agent_type": "rag",
                    "routing_metadata": {"final_agent": "rag_agent", "intent": "lookup"},
                    "thinking_lifecycle": _thinking_lifecycle(
                        "rag_agent",
                        "Mình đang bám điều luật trước khi trả lời ngắn gọn.",
                        phases=["pre_tool", "post_tool", "final_snapshot"],
                    ),
                },
            ),
            ("done", {"processing_time": 0.2}),
        ],
        "needles": [
            "event: thinking_start",
            "event: answer",
            "event: sources",
            '"intent": "lookup"',
        ],
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", STREAM_CASES, ids=[case["id"] for case in STREAM_CASES])
async def test_chat_stream_lifecycle_matrix(smoke_app, case):
    smoke_app.dependency_overrides[require_auth] = _student_auth

    async def _fake_stream(*, chat_request, **_kwargs):
        assert chat_request.provider == case["request"]["provider"]
        assert chat_request.model == case["request"]["model"]
        for event_name, payload in case["events"]:
            yield format_sse(event_name, payload)

    with patch(
        "app.api.v1.chat_stream.generate_stream_v3_events",
        side_effect=_fake_stream,
    ):
        async with httpx.AsyncClient(
            transport=_transport(smoke_app),
            base_url="http://testserver",
        ) as client:
            async with client.stream(
                "POST",
                "/api/v1/chat/stream/v3",
                json={
                    "user_id": "student-e2e",
                    "message": case["request"]["message"],
                    "role": "student",
                    "provider": case["request"]["provider"],
                    "model": case["request"]["model"],
                },
            ) as response:
                body = ""
                async for chunk in response.aiter_text():
                    body += chunk

    assert response.status_code == 200
    for needle in case["needles"]:
        assert needle in body
