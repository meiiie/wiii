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
from app.models.schemas import AgentType, InternalChatResponse


def _student_auth() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="student-lifecycle",
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


def _get_path(payload: dict, path: str):
    current = payload
    for raw_part in path.split("."):
        if isinstance(current, list):
            current = current[int(raw_part)]
        else:
            current = current[raw_part]
    return current


SYNC_CASES = [
    {
        "id": "product_search_sync",
        "request": {
            "message": "Tìm tai nghe bluetooth dưới 1 triệu trên Shopee",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "internal_response": InternalChatResponse(
            message="Mình đã chốt được 2 mẫu tai nghe hợp tiêu chí để bạn cân nhắc nhanh.",
            agent_type=AgentType.CHAT,
            metadata={
                "session_id": "sync-product-1",
                "provider": "openrouter",
                "model": "qwen/qwen3.6-plus:free",
                "runtime_authoritative": True,
                "thinking_content": "Mình đang đối chiếu nhanh giữa tiêu chí giá, độ ổn và nguồn bán đáng tin.",
                "thinking_lifecycle": _thinking_lifecycle(
                    "product_search_agent",
                    "Mình đang đối chiếu nhanh giữa tiêu chí giá, độ ổn và nguồn bán đáng tin.",
                    phases=["pre_tool", "tool_continuation", "post_tool", "final_snapshot"],
                ),
                "routing_metadata": {"final_agent": "product_search_agent", "intent": "product_search"},
                "platforms_searched": ["Shopee", "Lazada"],
                "products_found": 2,
            },
        ),
        "assertions": [
            ("metadata.provider", "openrouter"),
            ("metadata.model", "qwen/qwen3.6-plus:free"),
            ("metadata.routing_metadata.final_agent", "product_search_agent"),
            ("metadata.routing_metadata.intent", "product_search"),
            ("metadata.agent_type", "chat"),
        ],
    },
    {
        "id": "code_studio_sync",
        "request": {
            "message": "Tạo một mô phỏng con lắc đơn để mình kéo thả thử",
            "provider": "ollama",
            "model": "gemma3:4b",
        },
        "internal_response": InternalChatResponse(
            message="Mình đã dựng xong một mô phỏng con lắc đơn để bạn kéo thả và quan sát chu kỳ.",
            agent_type=AgentType.CODE_STUDIO,
            metadata={
                "session_id": "sync-code-1",
                "provider": "ollama",
                "model": "gemma3:4b",
                "runtime_authoritative": True,
                "thinking_content": "Mình đang giữ mô phỏng đủ trực quan nhưng vẫn gọn để bạn tương tác ngay.",
                "thinking_lifecycle": _thinking_lifecycle(
                    "code_studio_agent",
                    "Mình đang giữ mô phỏng đủ trực quan nhưng vẫn gọn để bạn tương tác ngay.",
                    phases=["pre_tool", "tool_continuation", "post_tool", "final_snapshot"],
                ),
                "routing_metadata": {"final_agent": "code_studio_agent", "intent": "code_execution"},
                "requested_view": "code",
                "visual_payload": {
                    "id": "sim-1",
                    "type": "simulation",
                    "presentation_intent": "code_studio_app",
                },
            },
        ),
        "assertions": [
            ("metadata.provider", "ollama"),
            ("metadata.model", "gemma3:4b"),
            ("metadata.agent_type", "code_studio"),
            ("metadata.routing_metadata.final_agent", "code_studio_agent"),
            ("metadata.routing_metadata.intent", "code_execution"),
        ],
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SYNC_CASES, ids=[case["id"] for case in SYNC_CASES])
async def test_product_code_sync_lifecycle_matrix(smoke_app, case):
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
                    "user_id": "student-lifecycle",
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
        "id": "product_search_stream",
        "request": {
            "message": "Tìm tai nghe bluetooth dưới 1 triệu trên Shopee",
            "provider": "openrouter",
            "model": "qwen/qwen3.6-plus:free",
        },
        "events": [
            (
                "status",
                {
                    "content": "Đang mở lane product search...",
                    "step": "routing",
                    "node": "product_search_agent",
                },
            ),
            (
                "thinking_start",
                {
                    "type": "thinking_start",
                    "content": "",
                    "node": "product_search_agent",
                    "summary": "Đối chiếu tiêu chí sản phẩm",
                },
            ),
            (
                "tool_call",
                {
                    "content": "search_shopee_products",
                    "step": "tool_call",
                    "node": "product_search_agent",
                },
            ),
            (
                "thinking_delta",
                {
                    "content": "Mình đang gom các lựa chọn thật sát mức giá và giữ những shop đáng tin hơn.",
                    "node": "product_search_agent",
                },
            ),
            (
                "answer",
                {
                    "content": "Mình đã lọc ra 2 mẫu đáng cân nhắc để bạn so nhanh.",
                },
            ),
            (
                "metadata",
                {
                    "provider": "openrouter",
                    "model": "qwen/qwen3.6-plus:free",
                    "routing_metadata": {"final_agent": "product_search_agent", "intent": "product_search"},
                    "platforms_searched": ["Shopee", "Lazada"],
                    "thinking_lifecycle": _thinking_lifecycle(
                        "product_search_agent",
                        "Mình đang gom các lựa chọn thật sát mức giá và giữ những shop đáng tin hơn.",
                        phases=["pre_tool", "tool_continuation", "post_tool", "final_snapshot"],
                    ),
                },
            ),
            ("done", {"processing_time": 0.2}),
        ],
        "needles": [
            "event: status",
            "event: thinking_start",
            "event: tool_call",
            "event: answer",
            "\"final_agent\": \"product_search_agent\"",
        ],
    },
    {
        "id": "code_studio_stream",
        "request": {
            "message": "Tạo một mô phỏng con lắc đơn để mình kéo thả thử",
            "provider": "ollama",
            "model": "gemma3:4b",
        },
        "events": [
            (
                "status",
                {
                    "content": "Đang mở lane Code Studio...",
                    "step": "routing",
                    "node": "code_studio_agent",
                },
            ),
            (
                "thinking_start",
                {
                    "type": "thinking_start",
                    "content": "",
                    "node": "code_studio_agent",
                    "summary": "Chốt nhanh cấu trúc mô phỏng",
                },
            ),
            (
                "code_open",
                {
                    "session_id": "vs_pendulum_1",
                    "title": "Mô phỏng con lắc đơn",
                    "language": "html",
                    "version": 1,
                    "requested_view": "code",
                },
            ),
            (
                "code_delta",
                {
                    "session_id": "vs_pendulum_1",
                    "chunk": "<canvas id=\"pendulum\"></canvas>",
                    "chunk_index": 0,
                    "total_bytes": 31,
                },
            ),
            (
                "code_complete",
                {
                    "session_id": "vs_pendulum_1",
                    "full_code": "<canvas id=\"pendulum\"></canvas>",
                    "language": "html",
                    "version": 1,
                    "requested_view": "code",
                    "visual_payload": {
                        "id": "sim-1",
                        "type": "simulation",
                        "presentation_intent": "code_studio_app",
                    },
                },
            ),
            (
                "metadata",
                {
                    "provider": "ollama",
                    "model": "gemma3:4b",
                    "agent_type": "code_studio",
                    "requested_view": "code",
                    "routing_metadata": {"final_agent": "code_studio_agent", "intent": "code_execution"},
                    "thinking_lifecycle": _thinking_lifecycle(
                        "code_studio_agent",
                        "Mình đang giữ mô phỏng đủ trực quan nhưng vẫn gọn để bạn tương tác ngay.",
                        phases=["pre_tool", "tool_continuation", "post_tool", "final_snapshot"],
                    ),
                },
            ),
            ("done", {"processing_time": 0.3}),
        ],
        "needles": [
            "event: status",
            "event: thinking_start",
            "event: code_open",
            "event: code_complete",
            "\"requested_view\": \"code\"",
            "\"intent\": \"code_execution\"",
        ],
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", STREAM_CASES, ids=[case["id"] for case in STREAM_CASES])
async def test_product_code_stream_lifecycle_matrix(smoke_app, case):
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
                    "user_id": "student-lifecycle",
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
