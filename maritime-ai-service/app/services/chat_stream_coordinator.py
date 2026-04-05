"""Service-level coordinator for chat streaming event orchestration."""

import asyncio
import logging
import time
from typing import AsyncGenerator, Mapping

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.engine.llm_runtime_metadata import resolve_runtime_llm_metadata
from app.services.llm_runtime_audit_service import record_llm_runtime_observation
from app.services.model_switch_prompt_service import (
    build_model_switch_prompt_for_failover,
    build_model_switch_prompt_for_unavailable,
)


logger = logging.getLogger(__name__)


def _source_to_payload(source):
    """Serialize Source-like objects for SSE transport."""
    if hasattr(source, "model_dump"):
        return source.model_dump(exclude_none=True)
    if hasattr(source, "dict"):
        return source.dict(exclude_none=True)
    return source


async def generate_stream_v3_events(
    *,
    chat_request,
    request_headers: Mapping[str, str],
    background_save,
    start_time: float,
    orchestrator=None,
    stream_fn=None,
) -> AsyncGenerator[str, None]:
    """Generate the authoritative event sequence for /chat/stream/v3.
    """
    from app.api.v1.chat_stream_presenter import (
        StreamPresentationState,
        emit_blocked_sse_events,
        emit_internal_error_sse_events,
        format_sse,
        serialize_stream_event,
    )
    from app.engine.multi_agent.stream_utils import (
        create_answer_event,
        create_done_event,
        create_error_event,
        create_metadata_event,
        create_sources_event,
        create_status_event,
    )

    yield "retry: 3000\n\n"
    event_counter = 0
    presentation_state = StreamPresentationState()

    event_counter += 1
    yield format_sse(
        "status",
        {
            "content": "Đang chuẩn bị lượt trả lời...",
            "step": "preparing",
            "node": "system",
            "details": {"visibility": "status_only"},
        },
        event_id=event_counter,
    )

    fb_cookie = request_headers.get("x-facebook-cookie", "")
    if fb_cookie and settings.enable_facebook_cookie:
        from app.engine.search_platforms.facebook_context import (
            set_facebook_cookie,
        )

        set_facebook_cookie(fb_cookie)

    try:
        request_id = str(request_headers.get("X-Request-ID") or request_headers.get("x-request-id") or "").strip() or None
        requested_provider = getattr(chat_request, "provider", None)
        if requested_provider and requested_provider != "auto":
            from app.services.llm_selectability_service import ensure_provider_is_selectable

            ensure_provider_is_selectable(requested_provider)

        if stream_fn is None:
            from app.engine.multi_agent.graph import (
                process_with_multi_agent_streaming,
            )

            stream_fn = process_with_multi_agent_streaming

        if orchestrator is None:
            from app.services.chat_service import get_chat_service

            chat_svc = get_chat_service()
            orchestrator = chat_svc._orchestrator

        prepared_turn = await orchestrator.prepare_turn(
            request=chat_request,
            background_save=background_save,
            persist_user_message_immediately=True,
        )
        resolved_org_id = prepared_turn.request_scope.organization_id
        resolved_domain_id = prepared_turn.request_scope.domain_id
        effective_session_id = prepared_turn.session_id
        effective_session_id_str = str(effective_session_id)

        if prepared_turn.validation.blocked:
            blocked_chunks, event_counter = (
                emit_blocked_sse_events(
                    blocked_response=prepared_turn.validation.blocked_response,
                    session_id=effective_session_id_str,
                    processing_time=time.time() - start_time,
                    event_counter=event_counter,
                )
            )
            for chunk in blocked_chunks:
                yield chunk
            return

        finalization_context = prepared_turn.chat_context
        use_multi_agent = getattr(
            orchestrator,
            "_use_multi_agent",
            getattr(settings, "use_multi_agent", True),
        )

        if not use_multi_agent:
            logger.warning("[STREAM-V3] Multi-Agent disabled, using sync fallback path")
            fallback_result = await orchestrator.process_without_multi_agent(
                finalization_context,
            )
            full_answer = fallback_result.message or ""
            processing_time = time.time() - start_time
            fallback_meta = dict(fallback_result.metadata or {})
            runtime_llm = resolve_runtime_llm_metadata(fallback_meta)
            fallback_thinking = (
                fallback_meta.get("thinking")
                or fallback_result.thinking
            )
            fallback_thinking_content = (
                fallback_meta.get("thinking_content")
                or fallback_thinking
                or ""
            )
            try:
                record_llm_runtime_observation(
                    provider=runtime_llm["provider"],
                    success=bool(runtime_llm["provider"]),
                    model_name=runtime_llm["model"],
                    note=None if runtime_llm["provider"] else "chat_stream:fallback: completed without authoritative runtime provider.",
                    error=None if runtime_llm["provider"] else "Missing authoritative runtime provider for fallback stream response.",
                    source="chat_stream:fallback",
                    failover=runtime_llm["failover"],
                )
            except Exception as exc:
                logger.debug("[STREAM-V3] Could not record fallback runtime observation: %s", exc)
            extra_meta = {
                key: value for key, value in fallback_meta.items()
                if key not in {
                    "agent_type",
                    "confidence",
                    "model",
                    "provider",
                    "processing_time",
                    "reasoning_trace",
                    "session_id",
                    "streaming_version",
                    "thinking",
                    "thinking_content",
                    "failover",
                    "routing_metadata",
                    "request_id",
                }
            }

            fallback_events = [
                await create_status_event(
                    "Đang tiếp tục trả lời...",
                    node="direct",
                    details={"mode": fallback_meta.get("mode", "fallback")},
                ),
                await create_answer_event(full_answer),
            ]

            if fallback_result.sources:
                fallback_events.append(
                    await create_sources_event(
                        [_source_to_payload(source) for source in fallback_result.sources]
                    )
                )

            fallback_events.extend(
                [
                    await create_metadata_event(
                        processing_time=processing_time,
                        agent_type=getattr(fallback_result.agent_type, "value", str(fallback_result.agent_type)),
                        model=runtime_llm["model"],
                        provider=runtime_llm["provider"],
                        failover=runtime_llm["failover"],
                        model_switch_prompt=build_model_switch_prompt_for_failover(
                            failover=runtime_llm["failover"],
                            requested_provider=getattr(chat_request, "provider", None),
                        ),
                        session_id=effective_session_id_str,
                        thinking=fallback_thinking,
                        thinking_content=fallback_thinking_content,
                        streaming_version=f"v3-{fallback_meta.get('mode', 'fallback')}",
                        request_id=request_id,
                        routing_metadata=fallback_meta.get("routing_metadata"),
                        **extra_meta,
                    ),
                    await create_done_event(processing_time),
                ]
            )

            for event in fallback_events:
                chunks, event_counter, should_stop = serialize_stream_event(
                    event=event,
                    event_counter=event_counter,
                    enable_artifacts=settings.enable_artifacts,
                    presentation_state=presentation_state,
                )
                for chunk in chunks:
                    yield chunk
                if should_stop:
                    return

            try:
                orchestrator.finalize_response_turn(
                    session_id=effective_session_id,
                    user_id=str(chat_request.user_id),
                    user_role=chat_request.role,
                    message=chat_request.message,
                    response_text=full_answer,
                    context=finalization_context,
                    domain_id=resolved_domain_id,
                    organization_id=resolved_org_id,
                    current_agent=(fallback_result.metadata or {}).get("current_agent", ""),
                    background_save=background_save,
                    save_response_immediately=True,
                    include_lms_insights=True,
                    continuity_channel="web",
                    transport_type="stream",
                )
            except Exception as finalize_err:
                logger.warning(
                    "[STREAM-V3] Fallback post-response finalization failed: %s",
                    finalize_err,
                )
            return

        _provider = requested_provider

        try:
            execution_input = await (
                orchestrator.build_multi_agent_execution_input(
                    request=chat_request,
                    prepared_turn=prepared_turn,
                    include_streaming_fields=True,
                    thinking_effort=getattr(
                        chat_request,
                        "thinking_effort",
                        None,
                    ),
                    provider=_provider,
                    request_id=request_id,
                )
            )
        except Exception as ctx_err:
            logger.warning(
                "[STREAM-V3] Full context build failed, using minimal: %s",
                ctx_err,
            )
            execution_input = (
                orchestrator.build_minimal_multi_agent_execution_input(
                    request=chat_request,
                    prepared_turn=prepared_turn,
                    thinking_effort=getattr(
                        chat_request,
                        "thinking_effort",
                        None,
                    ),
                    provider=_provider,
                    request_id=request_id,
                )
            )

        accumulated_answer: list[str] = []

        async for event in stream_fn(
            query=execution_input.query,
            user_id=execution_input.user_id,
            session_id=execution_input.session_id,
            context=execution_input.context,
            domain_id=execution_input.domain_id,
            thinking_effort=execution_input.thinking_effort,
            provider=execution_input.provider,
            model=getattr(execution_input, "model", None),
        ):
            if event.type == "answer":
                accumulated_answer.append(event.content)

            chunks, event_counter, should_stop = (
                serialize_stream_event(
                    event=event,
                    event_counter=event_counter,
                    enable_artifacts=settings.enable_artifacts,
                    presentation_state=presentation_state,
                )
            )
            if not chunks and event.type not in {"artifact"}:
                logger.warning(
                    "[STREAM-V3] Unknown event type: %s",
                    event.type,
                )

            for chunk in chunks:
                yield chunk

            if should_stop:
                return

            await asyncio.sleep(0.01)

        full_answer = "".join(accumulated_answer) if accumulated_answer else ""
        try:
            orchestrator.finalize_response_turn(
                session_id=effective_session_id,
                user_id=str(chat_request.user_id),
                user_role=chat_request.role,
                message=chat_request.message,
                response_text=full_answer,
                context=finalization_context,
                domain_id=resolved_domain_id,
                organization_id=resolved_org_id,
                current_agent="",
                background_save=background_save,
                save_response_immediately=True,
                include_lms_insights=True,
                continuity_channel="web",
                transport_type="stream",
            )
        except Exception as finalize_err:
            logger.warning(
                "[STREAM-V3] Post-response finalization failed: %s",
                finalize_err,
            )

        processing_time = time.time() - start_time
        logger.info(
            "[STREAM-V3] Completed in %.3fs (full graph)",
            processing_time,
        )

    except ProviderUnavailableError as exc:
        logger.warning(
            "[STREAM-V3] Requested provider unavailable: provider=%s reason=%s",
            exc.provider,
            exc.reason_code,
        )
        try:
            record_llm_runtime_observation(
                provider=exc.provider,
                success=False,
                error=exc.message,
                note=(
                    f"chat_stream:error: requested provider {exc.provider} unavailable"
                    f"{f' ({exc.reason_code})' if exc.reason_code else ''}."
                ),
                source="chat_stream:error",
            )
        except Exception as audit_exc:
            logger.debug("[STREAM-V3] Could not record unavailable provider audit: %s", audit_exc)
        error_event = await create_error_event(exc.message)
        error_event.content["provider"] = exc.provider
        error_event.content["reason_code"] = exc.reason_code
        error_event.content["model_switch_prompt"] = (
            build_model_switch_prompt_for_unavailable(
                provider=exc.provider,
                reason_code=exc.reason_code,
            )
        )
        error_chunks, event_counter, _ = serialize_stream_event(
            event=error_event,
            event_counter=event_counter,
            enable_artifacts=settings.enable_artifacts,
            presentation_state=presentation_state,
        )
        for chunk in error_chunks:
            yield chunk
        done_event = await create_done_event(time.time() - start_time)
        done_chunks, _, _ = serialize_stream_event(
            event=done_event,
            event_counter=event_counter + 1,
            enable_artifacts=settings.enable_artifacts,
            presentation_state=presentation_state,
        )
        for chunk in done_chunks:
            yield chunk
    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        logger.error("[STREAM-V3] Error: %s\n%s", exc, tb)
        error_chunks, _ = emit_internal_error_sse_events(
            processing_time=time.time() - start_time,
        )
        for chunk in error_chunks:
            yield chunk
