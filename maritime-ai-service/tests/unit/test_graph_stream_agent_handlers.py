from types import SimpleNamespace

import pytest

from app.engine.multi_agent.graph_stream_agent_handlers import handle_direct_node_impl


@pytest.mark.asyncio
async def test_handle_direct_node_replays_answer_when_bus_flag_has_no_confirmed_answer():
    async def _create_status_event(*_args, **_kwargs):
        return {"type": "status"}

    async def _create_domain_notice_event(_notice):
        return {"type": "domain_notice"}

    async def _emit_node_thinking(**_kwargs):
        if False:
            yield None

    async def _emit_web_previews(**_kwargs):
        if False:
            yield None

    async def _extract_and_stream_emotion_then_answer(text, *_args, **_kwargs):
        yield SimpleNamespace(type="answer", content=text)

    result = await handle_direct_node_impl(
        node_output={
            "final_response": "Minh la Wiii.",
            "_answer_streamed_via_bus": True,
            "thinking_content": "",
        },
        query="Wiii duoc sinh ra nhu the nao?",
        user_id="u1",
        context=None,
        initial_state={},
        node_start=0.0,
        bus_streamed_nodes=set(),
        bus_answer_nodes=set(),
        preview_enabled=False,
        preview_types=None,
        preview_max=3,
        emitted_preview_ids=set(),
        soul_emotion_emitted=False,
        answer_emitted=False,
        node_description="direct",
        node_label="direct",
        pipeline_status_details={"visibility": "status_only"},
        create_status_event=_create_status_event,
        create_domain_notice_event=_create_domain_notice_event,
        emit_node_thinking=_emit_node_thinking,
        emit_web_previews=_emit_web_previews,
        extract_thinking_content=lambda output: str(output.get("thinking_content") or ""),
        render_fallback_narration=None,
        create_thinking_start_event=None,
        create_thinking_delta_event=None,
        create_thinking_end_event=None,
        narration_delta_chunks=None,
        create_preview_event=None,
        extract_and_stream_emotion_then_answer=_extract_and_stream_emotion_then_answer,
    )

    assert result["answer_emitted"] is True
    assert result["events"] == [
        {"type": "status"},
        SimpleNamespace(type="answer", content="Minh la Wiii."),
    ]


@pytest.mark.asyncio
async def test_handle_direct_node_skips_replay_when_answer_already_emitted():
    async def _create_status_event(*_args, **_kwargs):
        return {"type": "status"}

    async def _create_domain_notice_event(_notice):
        return {"type": "domain_notice"}

    async def _emit_node_thinking(**_kwargs):
        if False:
            yield None

    async def _emit_web_previews(**_kwargs):
        if False:
            yield None

    async def _extract_and_stream_emotion_then_answer(*_args, **_kwargs):
        raise AssertionError("final_response should not be re-emitted after an answer event")
        if False:
            yield None

    result = await handle_direct_node_impl(
        node_output={
            "final_response": "Minh la Wiii.",
            "_answer_streamed_via_bus": True,
            "thinking_content": "",
        },
        query="Wiii duoc sinh ra nhu the nao?",
        user_id="u1",
        context=None,
        initial_state={},
        node_start=0.0,
        bus_streamed_nodes=set(),
        bus_answer_nodes={"direct"},
        preview_enabled=False,
        preview_types=None,
        preview_max=3,
        emitted_preview_ids=set(),
        soul_emotion_emitted=False,
        answer_emitted=True,
        node_description="direct",
        node_label="direct",
        pipeline_status_details={"visibility": "status_only"},
        create_status_event=_create_status_event,
        create_domain_notice_event=_create_domain_notice_event,
        emit_node_thinking=_emit_node_thinking,
        emit_web_previews=_emit_web_previews,
        extract_thinking_content=lambda output: str(output.get("thinking_content") or ""),
        render_fallback_narration=None,
        create_thinking_start_event=None,
        create_thinking_delta_event=None,
        create_thinking_end_event=None,
        narration_delta_chunks=None,
        create_preview_event=None,
        extract_and_stream_emotion_then_answer=_extract_and_stream_emotion_then_answer,
    )

    assert result["answer_emitted"] is True
    assert result["events"] == [{"type": "status"}]
