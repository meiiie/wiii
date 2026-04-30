import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import UserRole
from app.core.exceptions import ProviderUnavailableError
from app.engine.multi_agent.runtime_contracts import WiiiStreamEvent, WiiiTurnRequest
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
            provider=None,
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
async def test_generate_stream_v3_events_fast_social_bypasses_graph_context():
    orchestrator = MagicMock()
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(user_name="Minh"),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)

    async def fail_stream_fn(**_kwargs):
        raise AssertionError("fast social path should not enter graph streaming")
        yield  # pragma: no cover

    chunks = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.llm_selectability_service.ensure_provider_is_selectable",
            lambda _provider: None,
        )
        async for chunk in generate_stream_v3_events(
            chat_request=_make_request(
                message="hello",
                provider="nvidia",
                model="deepseek-ai/deepseek-v4-flash",
            ),
            request_headers={"X-Request-ID": "req-fast-social"},
            background_save=MagicMock(),
            start_time=time.time(),
            orchestrator=orchestrator,
            stream_fn=fail_stream_fn,
        ):
            chunks.append(chunk)

    joined = "\n".join(chunks)
    assert "event: answer" in joined
    assert "Wiii" in joined
    assert '"streaming_version": "v3-fast-social"' in joined
    assert '"llm_invoked": false' in joined
    assert '"transport_fast_social_path"' in joined
    assert '"request_id": "req-fast-social"' in joined
    orchestrator.build_multi_agent_execution_input.assert_not_called()
    orchestrator.finalize_response_turn.assert_called_once()
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs["response_text"]
        != ""
    )


@pytest.mark.asyncio
async def test_generate_stream_v3_events_does_not_fast_path_pointy_questions():
    orchestrator = MagicMock()
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(user_name="Minh"),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)
    orchestrator.build_multi_agent_execution_input = AsyncMock(
        return_value=SimpleNamespace(
            query="Wiii oi, nut Kham pha khoa hoc o dau?",
            user_id="user-1",
            session_id="session-1",
            context={"conversation_history": ""},
            domain_id="maritime",
            thinking_effort=None,
            provider=None,
            model=None,
        )
    )

    async def fake_stream_fn(**kwargs):
        assert kwargs["query"] == "Wiii oi, nut Kham pha khoa hoc o dau?"
        yield SimpleNamespace(type="answer", content="Tool path stays active")
        yield SimpleNamespace(type="done", content={"processing_time": 0.1})

    chunks = []
    async for chunk in generate_stream_v3_events(
        chat_request=_make_request(
            message="Wiii oi, nut Kham pha khoa hoc o dau?"
        ),
        request_headers={},
        background_save=MagicMock(),
        start_time=time.time(),
        orchestrator=orchestrator,
        stream_fn=fake_stream_fn,
    ):
        chunks.append(chunk)

    joined = "\n".join(chunks)
    assert "Wiii đang gom ngữ cảnh và trí nhớ" in joined
    assert any("Tool path stays active" in chunk for chunk in chunks)
    orchestrator.build_multi_agent_execution_input.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_stream_v3_events_defaults_to_native_wiii_turn_stream():
    orchestrator = MagicMock()
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(user_name="Minh"),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)
    orchestrator.build_multi_agent_execution_input = AsyncMock(
        return_value=SimpleNamespace(
            query="Explain Rule 5",
            user_id="user-1",
            session_id="session-1",
            context={"conversation_history": ""},
            domain_id="maritime",
            thinking_effort="medium",
            provider="nvidia",
            model="deepseek-ai/deepseek-v3.1",
        )
    )

    captured = {}

    async def fake_stream_wiii_turn(request):
        captured["request"] = request
        yield WiiiStreamEvent(event_type="answer", payload="Native hello")
        yield WiiiStreamEvent(
            event_type="done",
            payload={"status": "complete", "total_time": 0.5},
        )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.llm_selectability_service.ensure_provider_is_selectable",
            lambda _provider: None,
        )
        mp.setattr(
            "app.engine.multi_agent.streaming_runtime.stream_wiii_turn",
            fake_stream_wiii_turn,
        )
        chunks = []
        async for chunk in generate_stream_v3_events(
            chat_request=_make_request(
                provider="nvidia",
                model="deepseek-ai/deepseek-v3.1",
                thinking_effort="medium",
            ),
            request_headers={},
            background_save=MagicMock(),
            start_time=0.0,
            orchestrator=orchestrator,
        ):
            chunks.append(chunk)

    turn_request = captured["request"]
    assert isinstance(turn_request, WiiiTurnRequest)
    assert turn_request.query == "Explain Rule 5"
    assert turn_request.run_context.user_id == "user-1"
    assert turn_request.run_context.session_id == "session-1"
    assert turn_request.run_context.domain_id == "maritime"
    assert turn_request.run_context.organization_id == "org-1"
    assert turn_request.run_context.thinking_effort == "medium"
    assert turn_request.run_context.provider == "nvidia"
    assert turn_request.run_context.model == "deepseek-ai/deepseek-v3.1"
    assert any("Native hello" in chunk for chunk in chunks)
    orchestrator.finalize_response_turn.assert_called_once()
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs["response_text"]
        == "Native hello"
    )


@pytest.mark.asyncio
async def test_generate_stream_v3_events_accepts_injected_native_wiii_turn_stream():
    orchestrator = MagicMock()
    prepared_turn = SimpleNamespace(
        request_scope=RequestScope("org-1", "maritime"),
        session_id="session-1",
        validation=SimpleNamespace(blocked=False),
        chat_context=SimpleNamespace(user_name="Minh"),
    )
    orchestrator.prepare_turn = AsyncMock(return_value=prepared_turn)
    orchestrator.build_multi_agent_execution_input = AsyncMock(
        return_value=SimpleNamespace(
            query="Explain Rule 5",
            user_id="user-1",
            session_id="session-1",
            context={"conversation_history": ""},
            domain_id="maritime",
            thinking_effort=None,
            provider=None,
            model=None,
        )
    )

    captured = {}

    async def fake_native_stream_fn(request):
        captured["request"] = request
        yield WiiiStreamEvent(event_type="answer", payload="Injected native")
        yield WiiiStreamEvent(
            event_type="done",
            payload={"status": "complete", "total_time": 0.5},
        )

    chunks = []
    async for chunk in generate_stream_v3_events(
        chat_request=_make_request(),
        request_headers={},
        background_save=MagicMock(),
        start_time=0.0,
        orchestrator=orchestrator,
        stream_fn=fake_native_stream_fn,
    ):
        chunks.append(chunk)

    assert isinstance(captured["request"], WiiiTurnRequest)
    assert any("Injected native" in chunk for chunk in chunks)
    assert (
        orchestrator.finalize_response_turn.call_args.kwargs["response_text"]
        == "Injected native"
    )


@pytest.mark.asyncio
async def test_generate_stream_v3_events_emits_done_when_stream_omits_final_event():
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
            provider=None,
        )
    ))

    async def fake_stream_fn(**_kwargs):
        yield SimpleNamespace(type="answer", content="Hello without explicit done")

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

    assert sum(1 for chunk in chunks if "event: done" in chunk) == 1
    orchestrator.finalize_response_turn.assert_called_once()


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
                "failover": {
                    "switched": True,
                    "switch_count": 1,
                    "initial_provider": "google",
                    "final_provider": "zhipu",
                    "last_reason_code": "auth_error",
                    "last_reason_category": "auth_error",
                    "last_reason_label": "Xac thuc provider that bai.",
                    "route": [
                        {
                            "from_provider": "google",
                            "to_provider": "zhipu",
                            "reason_code": "auth_error",
                            "reason_category": "auth_error",
                            "reason_label": "Xac thuc provider that bai.",
                        }
                    ],
                },
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

    joined = "\n".join(chunks)
    orchestrator.process_without_multi_agent.assert_awaited_once()
    orchestrator.build_multi_agent_execution_input.assert_not_called()
    assert "Wiii đang mở đường trả lời nhanh" in joined
    assert any("Fast local fallback response" in chunk for chunk in chunks)
    assert any('"streaming_version": "v3-local_direct_llm"' in chunk for chunk in chunks)
    assert any('"last_reason_code": "auth_error"' in chunk for chunk in chunks)
    orchestrator.finalize_response_turn.assert_called_once()


@pytest.mark.asyncio
async def test_generate_stream_v3_events_includes_request_id_and_routing_metadata_in_fallback_metadata():
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
            message="Hẹ hẹ~ chào bạn nè.",
            agent_type=AgentType.DIRECT,
            metadata={
                "mode": "local_direct_llm",
                "model": "glm-5",
                "routing_metadata": {
                    "method": "fallback_direct_path",
                    "intent": "teaching",
                },
            },
        )
    )

    chunks = []
    async for chunk in generate_stream_v3_events(
        chat_request=_make_request(message="Explain Rule 5"),
        request_headers={"X-Request-ID": "req-fast-social"},
        background_save=MagicMock(),
        start_time=0.0,
        orchestrator=orchestrator,
    ):
        chunks.append(chunk)

    metadata_chunks = [chunk for chunk in chunks if "event: metadata" in chunk]
    assert metadata_chunks
    metadata_chunk = metadata_chunks[0]
    assert '"request_id": "req-fast-social"' in metadata_chunk
    assert '"routing_metadata": {' in metadata_chunk
    assert '"fallback_direct_path"' in metadata_chunk


@pytest.mark.asyncio
async def test_generate_stream_v3_events_emits_model_switch_prompt_for_unavailable_provider():
    chunks = []

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.llm_selectability_service.ensure_provider_is_selectable",
            lambda _provider: (_ for _ in ()).throw(
                ProviderUnavailableError(
                    provider="google",
                    reason_code="rate_limit",
                    message="Provider tam thoi ban hoac da cham gioi han.",
                )
            ),
        )
        mp.setattr(
            "app.services.chat_stream_coordinator.build_model_switch_prompt_for_unavailable",
            lambda **_kwargs: {
                "trigger": "provider_unavailable",
                "recommended_provider": "zhipu",
            },
        )

        async for chunk in generate_stream_v3_events(
            chat_request=_make_request(provider="google"),
            request_headers={},
            background_save=MagicMock(),
            start_time=0.0,
            orchestrator=MagicMock(),
        ):
            chunks.append(chunk)

    joined = "\n".join(chunks)
    assert "event: error" in joined
    assert '"model_switch_prompt"' in joined
    assert '"recommended_provider"' in joined
