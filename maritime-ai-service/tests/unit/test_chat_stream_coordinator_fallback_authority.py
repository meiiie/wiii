from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chat_stream_coordinator import generate_stream_v3_events


def _make_request(**overrides):
    base = {
        "user_id": "user-1",
        "message": "Phân tích giá dầu",
        "role": "student",
        "show_previews": False,
        "preview_types": [],
        "preview_max_count": 0,
        "thinking_effort": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_stream_fallback_metadata_prefers_thinking_content_from_metadata():
    orchestrator = MagicMock()
    orchestrator._use_multi_agent = False
    orchestrator.prepare_turn = AsyncMock(
        return_value=SimpleNamespace(
            request_scope=SimpleNamespace(organization_id="org-1", domain_id="maritime"),
            session_id="session-1",
            validation=SimpleNamespace(blocked=False),
            chat_context=SimpleNamespace(
                user_name="Minh",
                user_id="user-1",
                message="Phân tích giá dầu",
                user_role="student",
                session_id="session-1",
            ),
        )
    )
    orchestrator.process_without_multi_agent = AsyncMock(
        return_value=SimpleNamespace(
            message="Đây là câu trả lời fallback.",
            sources=[],
            thinking="Thinking ngắn ở object",
            agent_type=SimpleNamespace(value="direct"),
            metadata={
                "mode": "local_direct_llm",
                "model": "glm-5",
                "provider": "zhipu",
                "thinking": "Thinking trong metadata",
                "thinking_content": "Thinking content canon trong metadata",
            },
        )
    )

    chunks = []
    async for chunk in generate_stream_v3_events(
        chat_request=_make_request(),
        request_headers={},
        background_save=MagicMock(),
        start_time=0.0,
        orchestrator=orchestrator,
    ):
        chunks.append(chunk)

    metadata_chunk = next(chunk for chunk in chunks if "event: metadata" in chunk)
    assert '"thinking": "Thinking trong metadata"' in metadata_chunk
    assert '"thinking_content": "Thinking content canon trong metadata"' in metadata_chunk
