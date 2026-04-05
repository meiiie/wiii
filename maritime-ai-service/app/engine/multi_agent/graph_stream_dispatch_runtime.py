"""State-update dispatch helpers for graph_streaming."""

from __future__ import annotations

import logging
import time
from typing import Any


logger = logging.getLogger(__name__)


async def emit_state_update_events_impl(
    *,
    state_update: dict[str, dict[str, Any]],
    query: str,
    user_id: str,
    context: dict | None,
    initial_state: dict[str, Any],
    bus_streamed_nodes: set[str],
    bus_answer_nodes: set[str],
    preview_enabled: bool,
    preview_types: list[str] | None,
    preview_max: int,
    emitted_preview_ids: set[str],
    soul_emotion_emitted: bool,
    answer_emitted: bool,
    partial_answer_emitted: bool,
    rag_answer_text: str,
    pipeline_status_details: dict[str, Any],
    node_descriptions: dict[str, str],
    node_labels: dict[str, str],
    preview_snippet_max_length: int,
    emit_tool_call_events,
    emit_document_previews,
    emit_node_thinking,
    emit_web_previews,
    emit_product_previews,
    handle_direct_node,
    handle_product_search_node,
    extract_thinking_content,
    render_fallback_narration,
    create_status_event,
    create_tool_call_event,
    create_tool_result_event,
    create_thinking_start_event,
    create_thinking_delta_event,
    create_thinking_end_event,
    narration_delta_chunks,
    extract_and_stream_emotion_then_answer,
    create_preview_event,
    create_domain_notice_event,
    is_pipeline_summary,
    logger_obj,
) -> dict[str, Any]:
    """Convert one graph state update into stream events."""
    events: list[Any] = []
    final_state = None

    for node_name, node_output in state_update.items():
        logger_obj.debug("[STREAM] Node completed: %s", node_name)
        node_start = time.time()

        if node_name == "supervisor":
            logger_obj.info("[STREAM] Supervisor thinking SKIPPED (agent nodes handle it)")
            continue

        if node_name == "rag_agent":
            events.append(
                await create_status_event(
                    node_descriptions.get("rag_agent", "Đang tiếp tục tra cứu..."),
                    "rag_agent",
                    details=pipeline_status_details,
                )
            )

            async for event in emit_tool_call_events(
                tool_call_events=node_output.get("tool_call_events", []),
                node_name="rag_agent",
                lifecycle_state=node_output,
                create_tool_call_event=create_tool_call_event,
                create_tool_result_event=create_tool_result_event,
            ):
                events.append(event)

            tools_used = node_output.get("tools_used", [])
            sources = node_output.get("sources", [])
            if tools_used:
                tool_names = [
                    t.get("name", "tool") if isinstance(t, dict) else str(t)
                    for t in tools_used
                ]
                events.append(
                    await create_status_event(
                        f"Đã tra cứu: {', '.join(tool_names)}",
                        "rag_agent",
                        details=pipeline_status_details,
                    )
                )
            if sources:
                events.append(
                    await create_status_event(
                        f"Tìm thấy {len(sources)} nguồn tham khảo",
                        "rag_agent",
                        details=pipeline_status_details,
                    )
                )

            async for event in emit_document_previews(
                enabled=preview_enabled,
                preview_types=preview_types,
                preview_max=preview_max,
                sources=sources,
                emitted_preview_ids=emitted_preview_ids,
                snippet_max_length=preview_snippet_max_length,
                create_preview_event=create_preview_event,
            ):
                events.append(event)

            async for event in emit_node_thinking(
                streamed_nodes=bus_streamed_nodes,
                stream_node_name="rag_agent",
                node_label=node_labels.get("rag_agent", "Tra cứu tri thức"),
                node_output=node_output,
                node_start=node_start,
                phase="retrieve",
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                cue="retrieval",
                next_action="Giữ lại những đoạn thật sự đáng bám rồi ghép chúng thành câu trả lời grounded.",
                observations=[node_output.get("grader_feedback", "")],
                style_tags=["grounded", "retrieval"],
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                details={"phase": "retrieve"},
                confidence=float(node_output.get("grader_score") or 0.0),
                emit_narration_chunks_when_missing=False,
            ):
                events.append(event)

            agent_output_text = node_output.get("final_response", "")
            if not agent_output_text:
                agent_outputs = node_output.get("agent_outputs", {})
                if isinstance(agent_outputs, dict):
                    for val in agent_outputs.values():
                        if isinstance(val, str) and len(val) > 20:
                            agent_output_text = val
                            break
            if agent_output_text and not answer_emitted:
                if "rag_agent" not in bus_answer_nodes:
                    rag_answer_text = agent_output_text
                    async for event in extract_and_stream_emotion_then_answer(
                        agent_output_text,
                        soul_emotion_emitted,
                    ):
                        if event.type == "emotion":
                            soul_emotion_emitted = True
                        events.append(event)
                else:
                    rag_answer_text = agent_output_text
                    logger_obj.debug(
                        "[STREAM] RAG answer already streamed via bus, skipping bulk emission"
                    )
                partial_answer_emitted = True
            final_state = node_output
            continue

        if node_name == "tutor_agent":
            events.append(
                await create_status_event(
                    node_descriptions.get("tutor_agent", "Đang tiếp tục giải thích..."),
                    "tutor_agent",
                    details=pipeline_status_details,
                )
            )

            async for event in emit_tool_call_events(
                tool_call_events=node_output.get("tool_call_events", []),
                node_name="tutor_agent",
                lifecycle_state=node_output,
                create_tool_call_event=create_tool_call_event,
                create_tool_result_event=create_tool_result_event,
            ):
                events.append(event)

            tools_used = node_output.get("tools_used", [])
            if tools_used:
                events.append(
                    await create_status_event(
                        f"Đã đối chiếu {len(tools_used)} nguồn",
                        "tutor_agent",
                        details=pipeline_status_details,
                    )
                )

            tutor_already_streamed = "tutor_agent" in bus_streamed_nodes
            async for event in emit_node_thinking(
                streamed_nodes=bus_streamed_nodes,
                stream_node_name="tutor_agent",
                node_label=node_labels.get("tutor_agent", "Giảng dạy"),
                node_output=node_output,
                node_start=node_start,
                phase="synthesize",
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                cue="teaching",
                next_action="Viết lại phần cốt lõi theo nhịp dễ theo dõi hơn.",
                observations=[node_output.get("tutor_output", "")],
                style_tags=["teaching", "warm"],
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                details={"phase": "synthesize"},
                extra_already_streamed=tutor_already_streamed,
                emit_narration_chunks_when_missing=False,
            ):
                events.append(event)

            tutor_response = node_output.get("tutor_output", "")
            if not tutor_response:
                agent_outputs = node_output.get("agent_outputs", {})
                if isinstance(agent_outputs, dict):
                    tutor_response = agent_outputs.get("tutor", "")
            if not tutor_response:
                thinking_fallback = node_output.get("thinking", "")
                if (
                    thinking_fallback
                    and len(thinking_fallback) > 50
                    and not is_pipeline_summary(thinking_fallback)
                ):
                    logger_obj.warning(
                        "[STREAM] Tutor response empty, recovering from thinking field (%d chars)",
                        len(thinking_fallback),
                    )
                    tutor_response = thinking_fallback
            if tutor_response:
                logger_obj.debug(
                    "[STREAM] Holding tutor response for synthesizer authority (%d chars)",
                    len(tutor_response),
                )
            final_state = node_output
            continue

        if node_name == "synthesizer":
            events.append(
                await create_status_event(
                    node_descriptions.get("synthesizer", "Đang khâu lại phản hồi..."),
                    "synthesizer",
                    details=pipeline_status_details,
                )
            )

            final_response = node_output.get("final_response", "")
            if final_response and not answer_emitted:
                if partial_answer_emitted and final_response == rag_answer_text:
                    logger_obj.debug("[STREAM] Synthesizer pass-through, skipping re-emission")
                else:
                    async for event in extract_and_stream_emotion_then_answer(
                        final_response,
                        soul_emotion_emitted,
                    ):
                        if event.type == "emotion":
                            soul_emotion_emitted = True
                        events.append(event)
                answer_emitted = True

            final_state = node_output
            continue

        if node_name == "memory_agent":
            events.append(
                await create_status_event(
                    node_descriptions.get("memory_agent", "Đang gọi lại ngữ cảnh..."),
                    "memory_agent",
                    details=pipeline_status_details,
                )
            )

            async for event in emit_node_thinking(
                streamed_nodes=bus_streamed_nodes,
                stream_node_name="memory_agent",
                node_label=node_labels.get("memory_agent", "Truy xuat bo nho"),
                node_output=node_output,
                node_start=node_start,
                phase="retrieve",
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                cue="memory",
                next_action="Giữ lại những gì còn ích cho lượt trả lời này rồi nối lại với hiện tại.",
                observations=[node_output.get("memory_output", "")],
                style_tags=["memory", "continuity"],
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                details={"phase": "retrieve"},
                emit_narration_chunks_when_missing=False,
            ):
                events.append(event)

            memory_response = node_output.get("memory_output", "")
            if not memory_response:
                agent_outputs = node_output.get("agent_outputs", {})
                if isinstance(agent_outputs, dict):
                    memory_response = agent_outputs.get("memory", "")
            if memory_response and not answer_emitted:
                async for event in extract_and_stream_emotion_then_answer(
                    memory_response,
                    soul_emotion_emitted,
                ):
                    if event.type == "emotion":
                        soul_emotion_emitted = True
                    events.append(event)
                partial_answer_emitted = True
                answer_emitted = True
                final_state = node_output
            continue

        if node_name == "direct":
            direct_result = await handle_direct_node(
                node_output=node_output,
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                node_start=node_start,
                bus_streamed_nodes=bus_streamed_nodes,
                bus_answer_nodes=bus_answer_nodes,
                preview_enabled=preview_enabled,
                preview_types=preview_types,
                preview_max=preview_max,
                emitted_preview_ids=emitted_preview_ids,
                soul_emotion_emitted=soul_emotion_emitted,
                answer_emitted=answer_emitted,
                node_description=node_descriptions.get("direct", "Đang tiếp tục trả lời..."),
                node_label=node_labels.get("direct", "Trả lời trực tiếp"),
                pipeline_status_details=pipeline_status_details,
                create_status_event=create_status_event,
                create_domain_notice_event=create_domain_notice_event,
                emit_node_thinking=emit_node_thinking,
                emit_web_previews=emit_web_previews,
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                create_preview_event=create_preview_event,
                extract_and_stream_emotion_then_answer=extract_and_stream_emotion_then_answer,
            )
            events.extend(direct_result["events"])
            answer_emitted = direct_result["answer_emitted"]
            soul_emotion_emitted = direct_result["soul_emotion_emitted"]
            final_state = direct_result["final_state"]
            continue

        if node_name == "code_studio_agent":
            events.append(
                await create_status_event(
                    node_descriptions.get("code_studio_agent", "Dang che tac dau ra ky thuat..."),
                    "code_studio_agent",
                    details=pipeline_status_details,
                )
            )

            async for event in emit_node_thinking(
                streamed_nodes=bus_streamed_nodes,
                stream_node_name="code_studio_agent",
                node_label=node_labels.get("code_studio_agent", "Code Studio"),
                node_output=node_output,
                node_start=node_start,
                phase="synthesize",
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                cue="build",
                next_action="Chot cach thuc hien phu hop nhat roi gui answer kem output that.",
                observations=[],
                style_tags=["code-studio", "adaptive"],
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                details={"phase": "synthesize"},
                emit_narration_chunks_when_missing=False,
            ):
                events.append(event)

            if "code_studio_agent" in bus_answer_nodes:
                answer_emitted = True
            final_state = node_output
            continue

        if node_name == "product_search_agent":
            product_result = await handle_product_search_node(
                node_output=node_output,
                query=query,
                user_id=user_id,
                context=context,
                initial_state=initial_state,
                node_start=node_start,
                bus_streamed_nodes=bus_streamed_nodes,
                bus_answer_nodes=bus_answer_nodes,
                preview_enabled=preview_enabled,
                preview_types=preview_types,
                preview_max=preview_max,
                emitted_preview_ids=emitted_preview_ids,
                soul_emotion_emitted=soul_emotion_emitted,
                answer_emitted=answer_emitted,
                node_description=node_descriptions.get(
                    "product_search_agent",
                    "Đang tiếp tục đối chiếu...",
                ),
                node_label=node_labels.get("product_search_agent", "Tìm kiếm sản phẩm"),
                pipeline_status_details=pipeline_status_details,
                create_status_event=create_status_event,
                emit_node_thinking=emit_node_thinking,
                emit_product_previews=emit_product_previews,
                extract_thinking_content=extract_thinking_content,
                render_fallback_narration=render_fallback_narration,
                create_thinking_start_event=create_thinking_start_event,
                create_thinking_delta_event=create_thinking_delta_event,
                create_thinking_end_event=create_thinking_end_event,
                narration_delta_chunks=narration_delta_chunks,
                create_preview_event=create_preview_event,
                extract_and_stream_emotion_then_answer=extract_and_stream_emotion_then_answer,
            )
            events.extend(product_result["events"])
            answer_emitted = product_result["answer_emitted"]
            soul_emotion_emitted = product_result["soul_emotion_emitted"]
            final_state = product_result["final_state"]
            continue

        if node_name == "guardian":
            guardian_passed = node_output.get("guardian_passed")
            logger_obj.debug("[STREAM] Guardian passed: %s", guardian_passed)
            if not guardian_passed:
                guardian_reason = node_output.get("guardian_reason", "") or node_output.get(
                    "final_response",
                    "",
                )
                events.append(
                    await create_status_event(
                        f"⚠️ Nội dung không phù hợp: {guardian_reason[:100]}"
                        if guardian_reason
                        else "⚠️ Nội dung không phù hợp",
                        "guardian",
                    )
                )
            else:
                events.append(
                    await create_status_event(
                        "✓ Kiểm tra an toàn — Cho phép xử lý",
                        "guardian",
                        details=pipeline_status_details,
                    )
                )

    return {
        "events": events,
        "answer_emitted": answer_emitted,
        "partial_answer_emitted": partial_answer_emitted,
        "rag_answer_text": rag_answer_text,
        "soul_emotion_emitted": soul_emotion_emitted,
        "final_state": final_state,
    }
