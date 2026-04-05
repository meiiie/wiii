from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from app.api.v1.chat import router as chat_router
from app.api.v1.chat_stream import router as chat_stream_router
from app.api.v1.chat_stream_presenter import format_sse
from app.core.exceptions import ProviderUnavailableError
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.security import AuthenticatedUser, require_auth
from app.models.schemas import AgentType, InternalChatResponse
from app.services.llm_selectability_service import ProviderSelectability


def _student_auth() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="student-failover",
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


def _selectable_snapshot() -> list[ProviderSelectability]:
    return [
        ProviderSelectability(
            provider="google",
            display_name="Gemini",
            state="disabled",
            reason_code="busy",
            reason_label="Provider tam thoi ban hoac da cham gioi han.",
            selected_model="gemini-3.1-flash-lite-preview",
            strict_pin=True,
            verified_at="2026-04-04T10:00:00+00:00",
            available=False,
            configured=True,
            request_selectable=True,
            is_primary=True,
            is_fallback=False,
        ),
        ProviderSelectability(
            provider="zhipu",
            display_name="Zhipu GLM",
            state="selectable",
            reason_code=None,
            reason_label=None,
            selected_model="glm-5",
            strict_pin=True,
            verified_at="2026-04-04T10:00:00+00:00",
            available=True,
            configured=True,
            request_selectable=True,
            is_primary=False,
            is_fallback=True,
        ),
        ProviderSelectability(
            provider="ollama",
            display_name="Ollama",
            state="selectable",
            reason_code=None,
            reason_label=None,
            selected_model="gemma3:4b",
            strict_pin=True,
            verified_at="2026-04-04T10:00:00+00:00",
            available=True,
            configured=True,
            request_selectable=True,
            is_primary=False,
            is_fallback=True,
        ),
    ]


@pytest.fixture
def smoke_app():
    app = _build_smoke_app()
    yield app
    app.dependency_overrides.clear()


SYNC_CASES = [
    {
        "id": "explicit_provider_unavailable",
        "request": {
            "message": "Xin chao",
            "provider": "google",
            "model": "gemini-3.1-flash-lite-preview",
        },
        "process_side_effect": ProviderUnavailableError(
            provider="google",
            reason_code="rate_limit",
            message="Provider tam thoi ban hoac da cham gioi han.",
        ),
        "expected_status": 503,
        "assertions": [
            ("error_code", "PROVIDER_UNAVAILABLE"),
            ("provider", "google"),
            ("reason_code", "rate_limit"),
            ("model_switch_prompt.trigger", "provider_unavailable"),
            ("model_switch_prompt.recommended_provider", "zhipu"),
        ],
    },
    {
        "id": "auto_failover_success_surface",
        "request": {
            "message": "Wiii duoc sinh ra the nao?",
            "provider": "auto",
            "model": None,
        },
        "process_return": InternalChatResponse(
            message="Minh da chuyen sang GLM de tiep tuc tro chuyen.",
            agent_type=AgentType.DIRECT,
            metadata={
                "session_id": "sync-failover-1",
                "provider": "zhipu",
                "model": "glm-5",
                "runtime_authoritative": True,
                "failover": {
                    "switched": True,
                    "switch_count": 1,
                    "initial_provider": "google",
                    "final_provider": "zhipu",
                    "last_reason_code": "rate_limit",
                    "last_reason_category": "rate_limit",
                    "last_reason_label": "Gemini dang cham quota.",
                    "route": [
                        {
                            "from_provider": "google",
                            "to_provider": "zhipu",
                            "reason_code": "rate_limit",
                            "reason_category": "rate_limit",
                            "reason_label": "Gemini dang cham quota.",
                        }
                    ],
                },
            },
        ),
        "expected_status": 200,
        "assertions": [
            ("status", "success"),
            ("metadata.provider", "zhipu"),
            ("metadata.model", "glm-5"),
            ("metadata.failover.switched", True),
            ("metadata.failover.final_provider", "zhipu"),
            ("metadata.failover.last_reason_code", "rate_limit"),
        ],
    },
]


STREAM_CASES = [
    {
        "id": "explicit_provider_unavailable_stream",
        "request": {
            "message": "Xin chao",
            "provider": "google",
            "model": "gemini-3.1-flash-lite-preview",
        },
        "selectable_side_effect": ProviderUnavailableError(
            provider="google",
            reason_code="busy",
            message="Provider tam thoi ban hoac da cham gioi han.",
        ),
        "needles": [
            "event: error",
            '"provider": "google"',
            '"reason_code": "busy"',
            '"recommended_provider": "zhipu"',
            "event: done",
        ],
    },
    {
        "id": "auto_failover_stream_surface",
        "request": {
            "message": "Wiii duoc sinh ra the nao?",
            "provider": "auto",
            "model": None,
        },
        "events": [
            (
                "metadata",
                {
                    "provider": "zhipu",
                    "model": "glm-5",
                    "agent_type": "direct",
                    "failover": {
                        "switched": True,
                        "initial_provider": "google",
                        "final_provider": "zhipu",
                        "last_reason_code": "rate_limit",
                    },
                    "model_switch_prompt": {
                        "trigger": "hard_failover",
                        "recommended_provider": "zhipu",
                    },
                },
            ),
            (
                "answer",
                {"content": "Minh da chuyen sang GLM de tiep tuc tro chuyen."},
            ),
            ("done", {"processing_time": 0.2}),
        ],
        "needles": [
            "event: metadata",
            '"provider": "zhipu"',
            '"model": "glm-5"',
            '"trigger": "hard_failover"',
            '"recommended_provider": "zhipu"',
            "event: done",
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
async def test_chat_sync_failover_matrix(smoke_app, case):
    smoke_app.dependency_overrides[require_auth] = _student_auth

    process_patch = patch(
        "app.api.v1.chat_completion_endpoint_support.process_chat_completion_request",
        new=AsyncMock(
            side_effect=case.get("process_side_effect"),
            return_value=case.get("process_return"),
        ),
    )
    snapshot_patch = patch(
        "app.services.model_switch_prompt_service.get_llm_selectability_snapshot",
        return_value=_selectable_snapshot(),
    )

    with process_patch, snapshot_patch:
        async with httpx.AsyncClient(
            transport=_transport(smoke_app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={
                    "user_id": "student-failover",
                    "message": case["request"]["message"],
                    "role": "student",
                    "provider": case["request"]["provider"],
                    "model": case["request"]["model"],
                },
            )

    assert response.status_code == case["expected_status"]
    payload = response.json()
    for path, expected in case["assertions"]:
        assert _get_path(payload, path) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("case", STREAM_CASES, ids=[case["id"] for case in STREAM_CASES])
async def test_chat_stream_failover_matrix(smoke_app, case):
    smoke_app.dependency_overrides[require_auth] = _student_auth

    snapshot_patch = patch(
        "app.services.model_switch_prompt_service.get_llm_selectability_snapshot",
        return_value=_selectable_snapshot(),
    )

    if "selectable_side_effect" in case:
        stream_patch = patch(
            "app.services.llm_selectability_service.ensure_provider_is_selectable",
            side_effect=case["selectable_side_effect"],
        )
    else:
        async def _fake_stream(*, chat_request, **_kwargs):
            assert chat_request.provider == case["request"]["provider"]
            assert chat_request.model == case["request"]["model"]
            for event_name, payload in case["events"]:
                yield format_sse(event_name, payload)

        stream_patch = patch(
            "app.api.v1.chat_stream.generate_stream_v3_events",
            side_effect=_fake_stream,
        )

    with snapshot_patch, stream_patch:
        async with httpx.AsyncClient(
            transport=_transport(smoke_app),
            base_url="http://testserver",
        ) as client:
            async with client.stream(
                "POST",
                "/api/v1/chat/stream/v3",
                json={
                    "user_id": "student-failover",
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
