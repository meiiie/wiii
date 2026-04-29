"""Lane-specific streaming handlers for graph_streaming.

These helpers keep `graph_streaming.py` focused on queue orchestration while
the per-node UX rules for direct and product-search lanes live here.
"""

from typing import Any


async def handle_direct_node_impl(
    *,
    node_output: dict[str, Any],
    query: str,
    user_id: str,
    context: dict | None,
    initial_state: dict[str, Any],
    node_start: float,
    bus_streamed_nodes: set,
    bus_answer_nodes: set,
    preview_enabled: bool,
    preview_types: list[str] | None,
    preview_max: int,
    emitted_preview_ids: set,
    soul_emotion_emitted: bool,
    answer_emitted: bool,
    node_description: str,
    node_label: str,
    pipeline_status_details: dict,
    create_status_event,
    create_domain_notice_event,
    emit_node_thinking,
    emit_web_previews,
    extract_thinking_content,
    render_fallback_narration,
    create_thinking_start_event,
    create_thinking_delta_event,
    create_thinking_end_event,
    narration_delta_chunks,
    create_preview_event,
    extract_and_stream_emotion_then_answer,
) -> dict[str, Any]:
    """Emit stream events for the direct-response lane."""
    events: list[Any] = [
        await create_status_event(
            node_description,
            "direct",
            details=pipeline_status_details,
        )
    ]

    direct_already_streamed = "direct" in bus_streamed_nodes
    direct_thinking_content = extract_thinking_content(node_output)
    if direct_already_streamed or direct_thinking_content:
        async for event in emit_node_thinking(
            streamed_nodes=bus_streamed_nodes,
            stream_node_name="direct",
            node_label=node_label,
            node_output=node_output,
            node_start=node_start,
            phase="synthesize",
            query=query,
            user_id=user_id,
            context=context,
            initial_state=initial_state,
            cue=node_output.get("current_mode", "") or "direct",
            next_action="Chot cach dap gan va dung nhip roi tra loi thang cho nguoi dung.",
            observations=[node_output.get("domain_notice", "")],
            style_tags=["direct", "adaptive"],
            extract_thinking_content=extract_thinking_content,
            render_fallback_narration=render_fallback_narration,
            create_thinking_start_event=create_thinking_start_event,
            create_thinking_delta_event=create_thinking_delta_event,
            create_thinking_end_event=create_thinking_end_event,
            narration_delta_chunks=narration_delta_chunks,
            details={"phase": "synthesize"},
            extra_already_streamed=direct_already_streamed,
            emit_narration_chunks_when_missing=False,
        ):
            events.append(event)

    async for event in emit_web_previews(
        enabled=preview_enabled,
        preview_types=preview_types,
        preview_max=preview_max,
        tool_call_events=node_output.get("tool_call_events", []),
        emitted_preview_ids=emitted_preview_ids,
        create_preview_event=create_preview_event,
    ):
        events.append(event)

    final_response = node_output.get("final_response", "")
    if final_response and not answer_emitted:
        async for event in extract_and_stream_emotion_then_answer(
            final_response,
            soul_emotion_emitted,
        ):
            if event.type == "emotion":
                soul_emotion_emitted = True
            events.append(event)
        answer_emitted = True

    domain_notice = node_output.get("domain_notice")
    if domain_notice:
        events.append(await create_domain_notice_event(domain_notice))

    return {
        "events": events,
        "answer_emitted": answer_emitted,
        "soul_emotion_emitted": soul_emotion_emitted,
        "final_state": node_output,
    }


async def handle_product_search_node_impl(
    *,
    node_output: dict[str, Any],
    query: str,
    user_id: str,
    context: dict | None,
    initial_state: dict[str, Any],
    node_start: float,
    bus_streamed_nodes: set,
    bus_answer_nodes: set,
    preview_enabled: bool,
    preview_types: list[str] | None,
    preview_max: int,
    emitted_preview_ids: set,
    soul_emotion_emitted: bool,
    answer_emitted: bool,
    node_description: str,
    node_label: str,
    pipeline_status_details: dict,
    create_status_event,
    emit_node_thinking,
    emit_product_previews,
    extract_thinking_content,
    render_fallback_narration,
    create_thinking_start_event,
    create_thinking_delta_event,
    create_thinking_end_event,
    narration_delta_chunks,
    create_preview_event,
    extract_and_stream_emotion_then_answer,
) -> dict[str, Any]:
    """Emit stream events for the product-search lane."""
    events: list[Any] = [
        await create_status_event(
            node_description,
            "product_search_agent",
            details=pipeline_status_details,
        )
    ]

    async for event in emit_node_thinking(
        streamed_nodes=bus_streamed_nodes,
        stream_node_name="product_search_agent",
        node_label=node_label,
        node_output=node_output,
        node_start=node_start,
        phase="retrieve",
        query=query,
        user_id=user_id,
        context=context,
        initial_state=initial_state,
        cue="comparison",
        next_action="Giữ lại mặt bằng giá đáng tin rồi chuyển sang bước so và chốt.",
        observations=[node_output.get("search_summary", "")],
        style_tags=["product-search", "comparative"],
        extract_thinking_content=extract_thinking_content,
        render_fallback_narration=render_fallback_narration,
        create_thinking_start_event=create_thinking_start_event,
        create_thinking_delta_event=create_thinking_delta_event,
        create_thinking_end_event=create_thinking_end_event,
        narration_delta_chunks=narration_delta_chunks,
        details={"phase": "retrieve"},
    ):
        events.append(event)

    realtime_preview = False
    try:
        from app.core.config import get_settings as _gs200

        realtime_preview = _gs200().enable_product_preview_cards
    except Exception:
        pass

    async for event in emit_product_previews(
        enabled=preview_enabled,
        realtime_preview=realtime_preview,
        preview_types=preview_types,
        preview_max=preview_max,
        tool_call_events=node_output.get("tool_call_events", []),
        emitted_preview_ids=emitted_preview_ids,
        create_preview_event=create_preview_event,
    ):
        events.append(event)

    final_response = node_output.get("final_response", "")
    if final_response and not answer_emitted:
        async for event in extract_and_stream_emotion_then_answer(
            final_response,
            soul_emotion_emitted,
        ):
            if event.type == "emotion":
                soul_emotion_emitted = True
            events.append(event)
        answer_emitted = True

    return {
        "events": events,
        "answer_emitted": answer_emitted,
        "soul_emotion_emitted": soul_emotion_emitted,
        "final_state": node_output,
    }
