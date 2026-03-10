from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import UserRole
from app.services.chat_orchestrator import AgentType
from app.services.chat_orchestrator import RequestScope
from app.services.output_processor import ProcessingResult
from app.services.chat_stream_coordinator import generate_stream_v3_events


def _make_request(**overrides):
    base = {
        "user_id": "user-1",
        "message": "Explain Rule 5",
        "role": UserRole.STUDENT,
        "show_previews": False,
        "preview_types": [],
        "preview_max_count": 0,
        "thinking_effort": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_generate_stream_v3_events_emits_blocked_sequence():
    orchestrator = MagicMock()
    orchestrator.prepare_turn = AsyncMock(
        return_value=SimpleNamespace(
            request_scope=RequestScope("org-1", "maritime"),
            session_id="session-1",
            validation=SimpleNamespace(
                blocked=True,
                blocked_response=SimpleNamespace(
                    message="Blocked",
                    metadata={"blocked": True},
                ),
            ),
            chat_context=None,
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

    assert chunks[0] == "retry: 3000\n\n"
    assert "event: status" in chunks[1]
    assert "event: answer" in chunks[2]
    assert "event: metadata" in chunks[3]
    assert "event: done" in chunks[4]


@pytest.mark.asyncio
async def test_generate_stream_v3_events_finalizes_answer_after_stream():
    orchestrator = MagicMock()
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(user_name="Minh"),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)
    orchestrator.build_multi_agent_execution_input = AsyncMock(return_value=(
        SimpleNamespace(
            query="Explain Rule 5",
            user_id="user-1",
            session_id="session-1",
            context={"conversation_history": ""},
            domain_id="maritime",
            thinking_effort=None,
        )
    ))

    async def fake_stream_fn(**kwargs):
        assert kwargs["query"] == "Explain Rule 5"
        yield SimpleNamespace(type="answer", content="Hello ")
        yield SimpleNamespace(type="answer", content="world")
        yield SimpleNamespace(type="done", content={"processing_time": 0.5})

    chunks = []
    async for chunk in generate_stream_v3_events(
        chat_request=_make_request(),
        request_headers={},
        background_save=MagicMock(),
        start_time=0.0,
        orchestrator=orchestrator,
        stream_fn=fake_stream_fn,
    ):
        chunks.append(chunk)

    assert any("event: answer" in chunk for chunk in chunks)
    assert any("event: done" in chunk for chunk in chunks)
    orchestrator.finalize_response_turn.assert_called_once()
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs["response_text"]
        == "Hello world"
    )
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs[
            "include_lms_insights"
        ]
        is True
    )
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs[
            "transport_type"
        ]
        == "stream"
    )


@pytest.mark.asyncio
async def test_generate_stream_v3_events_uses_sync_fallback_when_multi_agent_disabled():
    orchestrator = MagicMock()
    orchestrator._use_multi_agent = False
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(
            user_name="Minh",
            user_id="user-1",
            message="Explain Rule 5",
            user_role=UserRole.STUDENT,
            session_id="session-1",
        ),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)
    orchestrator.process_without_multi_agent = AsyncMock(
        return_value=ProcessingResult(
            message="Fast local fallback response",
            agent_type=AgentType.DIRECT,
            metadata={
                "mode": "local_direct_llm",
                "model": "qwen3:4b-instruct-2507-q4_K_M",
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

    orchestrator.process_without_multi_agent.assert_awaited_once()
    orchestrator.build_multi_agent_execution_input.assert_not_called()
    assert any("Fast local fallback response" in chunk for chunk in chunks)
    assert any('"streaming_version": "v3-local_direct_llm"' in chunk for chunk in chunks)
    orchestrator.finalize_response_turn.assert_called_once()
