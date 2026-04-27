"""Tool-round runtime extracted from direct_execution."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Optional

from app.core.config import settings
from app.engine.multi_agent.direct_opening_runtime import (
    finalize_direct_opening_phase_impl,
    start_direct_opening_phase_impl,
)
from app.engine.multi_agent.direct_prompts import _resolve_tool_choice, _tool_name
from app.engine.multi_agent.direct_reasoning import (
    _build_direct_analytical_axes,
    _build_direct_evidence_plan,
    _build_direct_tool_reflection,
    _infer_direct_reasoning_cue,
    _infer_direct_thinking_mode,
    _infer_direct_topic_hint,
)
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.visual_events import (
    _collect_active_visual_session_ids,
    _emit_visual_commit_events,
    _maybe_emit_host_action_event,
    _maybe_emit_visual_event,
    _summarize_tool_result_for_stream,
)
from app.engine.multi_agent.visual_intent_resolver import (
    required_visual_tool_names,
    resolve_visual_intent,
)


logger = logging.getLogger(__name__)


def _extract_direct_visible_text(content: Any) -> str:
    """Return the answer text that would be visible to the user."""
    try:
        from app.services.output_processor import extract_thinking_from_response

        text_content, _thinking_content = extract_thinking_from_response(content)
        return str(text_content or "").strip()
    except Exception:
        return str(content or "").strip()


def _build_direct_final_synthesis_instruction(
    query: str,
    state: AgentState,
    tool_names: list[str],
) -> str:
    """Build a mode-aware final synthesis instruction after tool rounds."""
    thinking_mode = _infer_direct_thinking_mode(query, state, tool_names)
    axes = _build_direct_analytical_axes(query, state, tool_names)
    plan = _build_direct_evidence_plan(query, state, tool_names)

    base = (
        "Du lieu da du cho luot nay. Khong goi them cong cu. "
        "Hay tong hop ngay thanh cau tra loi cuoi cung bang tieng Viet, "
        "dua tren cac ket qua cong cu da co."
    )

    if thinking_mode == "analytical_market":
        return (
            base
            + " Mo dau bang mot cau thesis ve mat bang thi truong hien tai, sau do tach cac luc keo chinh "
            + "(cung-cau, OPEC+, ton kho, dia chinh tri) thay vi liet ke tin tuc. "
            + "Neu cac tin hieu xung nhau, hay noi ro truc nao dang giu mat bang gia va truc nao chi tao nhieu ngan han. "
            + "Mac dinh uu tien 2-3 doan chat; chi dung bullet ngan neu can tach watchlist. "
            + "KHONG dung heading Markdown nhu #, ##, ###, va KHONG dung bullet/bold kieu ban tin tong hop. "
            + "Ket bang takeaway hoac dieu can theo doi tiep theo."
        )
    if thinking_mode == "analytical_math":
        return (
            base
            + " Mo dau bang mot cau thesis ve mo hinh dang dung, roi trinh bay theo nhip mo hinh/gia dinh -> phuong trinh hoac suy dan -> y nghia vat ly. "
            + "Noi ro cac gia dinh nhu "
            + (", ".join(axes[:3]) if axes else "mo hinh, goc nho, va phuong trinh")
            + ". Neu ket luan phu thuoc gan dung, noi ro pham vi ma gan dung do con hop le. "
            + "Mac dinh uu tien 2-3 doan chat; KHONG dung heading Markdown nhu #, ##, ### neu user khong yeu cau."
        )
    if thinking_mode == "analytical_general":
        plan_hint = ", ".join(plan[:2]) if plan else "cac bien so chinh va chung cu manh nhat"
        return (
            base
            + " Mo dau bang mot cau thesis co the kiem cheo, di thang vao luan diem, tach dieu chac khoi dieu con nhieu, va neo lai "
            + plan_hint
            + ". Neu co tin hieu trai chieu, noi ro cai nao dang nang ky hon. "
            + "Mac dinh uu tien 2-3 doan chat; chi dung bullet ngan khi user can tach checklist/watchlist. "
            + "KHONG dung heading Markdown nhu #, ##, ###."
        )
    return base


async def execute_direct_tool_rounds_impl(
    llm_with_tools,
    llm_auto,
    messages: list,
    tools: list,
    push_event,
    *,
    runtime_context_base=None,
    max_rounds: int = 3,
    query: str = "",
    state: Optional[AgentState] = None,
    provider: str | None = None,
    forced_tool_choice: str | None = None,
    llm_base=None,
    direct_answer_timeout_profile: str | None = None,
    direct_answer_primary_timeout: float | None = None,
    allowed_fallback_providers: tuple[str, ...] | list[str] | set[str] | None = None,
    ainvoke_with_fallback,
    stream_direct_answer_with_fallback,
    stream_direct_wait_heartbeats,
    push_status_only_progress,
):
    """Execute multi-round tool calling loop for direct response."""
    from langchain_core.messages import ToolMessage as _TM

    from app.engine.tools.invocation import (
        get_tool_by_name as _get_tool_by_name_impl,
        invoke_tool_with_runtime as _invoke_tool_with_runtime_impl,
    )
    from app.engine.multi_agent.direct_runtime_bindings import (
        _extract_runtime_target,
        _inject_widget_blocks_from_tool_results,
        _remember_runtime_target,
    )
    from app.engine.llm_pool import (
        FAILOVER_MODE_AUTO,
        FAILOVER_MODE_PINNED,
        TIMEOUT_PROFILE_BACKGROUND,
        TIMEOUT_PROFILE_STRUCTURED,
    )

    tool_call_events: list[dict] = []
    state = state or {}
    direct_thinking_stop = asyncio.Event()
    visual_decision = resolve_visual_intent(query)
    requires_visual_commit = (
        visual_decision.force_tool
        and visual_decision.presentation_intent in {"article_figure", "chart_runtime"}
    )
    initial_timeout_profile = (
        TIMEOUT_PROFILE_STRUCTURED if visual_decision.force_tool else None
    )
    followup_timeout_profile = (
        TIMEOUT_PROFILE_BACKGROUND
        if requires_visual_commit
        else TIMEOUT_PROFILE_STRUCTURED
    )
    visual_emitted_any = False
    request_failover_mode = (
        FAILOVER_MODE_PINNED
        if provider and str(provider).strip().lower() != "auto"
        else FAILOVER_MODE_AUTO
    )
    resolved_provider = _extract_runtime_target(llm_base or llm_auto or llm_with_tools)[0]
    graph_module = sys.modules.get("app.engine.multi_agent.graph")
    graph_ainvoke_with_fallback = getattr(
        graph_module,
        "_ainvoke_with_fallback",
        ainvoke_with_fallback,
    )
    graph_stream_direct_answer_with_fallback = getattr(
        graph_module,
        "_stream_direct_answer_with_fallback",
        stream_direct_answer_with_fallback,
    )
    graph_stream_direct_wait_heartbeats = getattr(
        graph_module,
        "_stream_direct_wait_heartbeats",
        stream_direct_wait_heartbeats,
    )
    graph_build_direct_tool_reflection = getattr(
        graph_module,
        "_build_direct_tool_reflection",
        _build_direct_tool_reflection,
    )
    graph_maybe_emit_host_action_event = getattr(
        graph_module,
        "_maybe_emit_host_action_event",
        _maybe_emit_host_action_event,
    )
    graph_maybe_emit_visual_event = getattr(
        graph_module,
        "_maybe_emit_visual_event",
        _maybe_emit_visual_event,
    )
    graph_emit_visual_commit_events = getattr(
        graph_module,
        "_emit_visual_commit_events",
        _emit_visual_commit_events,
    )
    graph_get_tool_by_name = getattr(
        graph_module,
        "get_tool_by_name",
        _get_tool_by_name_impl,
    )
    graph_invoke_tool_with_runtime = getattr(
        graph_module,
        "invoke_tool_with_runtime",
        _invoke_tool_with_runtime_impl,
    )

    def remember_execution_target(
        candidate_llm: Any,
        fallback_source: Any | None = None,
    ) -> tuple[str | None, str | None]:
        provider_name, model_name = _remember_runtime_target(state, candidate_llm)
        if (not provider_name or not model_name) and fallback_source is not None:
            fallback_provider, fallback_model = _remember_runtime_target(
                state,
                fallback_source,
            )
            provider_name = provider_name or fallback_provider
            model_name = model_name or fallback_model
        return provider_name, model_name

    def runtime_tier_for(
        candidate_llm: Any,
        fallback_source: Any | None = None,
    ) -> str:
        for source in (candidate_llm, fallback_source, llm_base, llm_auto, llm_with_tools):
            tier_value = getattr(source, "_wiii_tier_key", None) if source is not None else None
            if isinstance(tier_value, str) and tier_value.strip():
                return tier_value.strip().lower()
        return "moderate"

    opening_cue, direct_thinking_stop, initial_heartbeat, opening_thinking_started = await start_direct_opening_phase_impl(
        query=query,
        state=state,
        push_event=push_event,
        infer_direct_reasoning_cue=_infer_direct_reasoning_cue,
        stream_direct_wait_heartbeats=graph_stream_direct_wait_heartbeats,
    )
    streamed_direct_answer = False
    try:
        if tools and forced_tool_choice:
            # Forced tool choice — use ainvoke to ensure tool calls happen
            candidate_provider, _candidate_model = remember_execution_target(
                llm_with_tools,
                fallback_source=llm_base,
            )
            resolved_provider = candidate_provider or resolved_provider
            llm_response = await graph_ainvoke_with_fallback(
                llm_with_tools,
                messages,
                tools=tools,
                tool_choice=forced_tool_choice,
                tier=runtime_tier_for(llm_with_tools, llm_base),
                provider=provider,
                resolved_provider=resolved_provider,
                failover_mode=request_failover_mode,
                push_event=push_event,
                timeout_profile=initial_timeout_profile,
                state=state,
                allowed_fallback_providers=allowed_fallback_providers,
            )
        else:
            candidate_provider, _candidate_model = remember_execution_target(
                llm_with_tools,
                fallback_source=llm_base,
            )
            resolved_provider = candidate_provider or resolved_provider
            llm_response, streamed_direct_answer = await graph_stream_direct_answer_with_fallback(
                llm_with_tools,
                messages,
                push_event,
                provider=provider,
                resolved_provider=resolved_provider,
                failover_mode=request_failover_mode,
                thinking_stop_signal=direct_thinking_stop,
                thinking_block_opened=opening_thinking_started,
                state=state,
                primary_timeout=direct_answer_primary_timeout,
                timeout_profile=direct_answer_timeout_profile,
                allowed_fallback_providers=allowed_fallback_providers,
            )
    finally:
        await finalize_direct_opening_phase_impl(
            thinking_stop=direct_thinking_stop,
            heartbeat_task=initial_heartbeat,
            logger_obj=logger,
        )

    tool_calls = getattr(llm_response, "tool_calls", [])
    logger.warning(
        "[DIRECT] LLM response: tool_calls=%d, content_len=%d",
        len(tool_calls) if tool_calls else 0,
        len(str(llm_response.content)),
    )
    if not streamed_direct_answer and opening_thinking_started:
        await push_event({"type": "thinking_end", "content": "", "node": "direct"})

    for tool_round in range(max_rounds):
        if not (tools and hasattr(llm_response, "tool_calls") and llm_response.tool_calls):
            break
        round_tool_names = [
            str(tc.get("name", "unknown"))
            for tc in llm_response.tool_calls
            if tc.get("name")
        ]
        round_cue = _infer_direct_reasoning_cue(query, state, round_tool_names)
        messages.append(llm_response)
        visual_session_ids: list[str] = []
        active_visual_session_ids = _collect_active_visual_session_ids(state)
        for tc in llm_response.tool_calls:
            tc_id = tc.get("id", f"tc_{tool_round}")
            tc_name = tc.get("name", "unknown")
            await push_event(
                {
                    "type": "tool_call",
                    "content": {"name": tc_name, "args": tc.get("args", {}), "id": tc_id},
                    "node": "direct",
                }
            )
            tool_call_events.append(
                {
                    "type": "call",
                    "name": tc_name,
                    "args": tc.get("args", {}),
                    "id": tc_id,
                }
            )
            matched = graph_get_tool_by_name(tools, str(tc_name).strip())
            try:
                if matched:
                    result = await graph_invoke_tool_with_runtime(
                        matched,
                        tc["args"],
                        tool_name=tc_name,
                        runtime_context_base=runtime_context_base,
                        tool_call_id=tc_id,
                        query_snippet=str(tc.get("args", {}).get("query", ""))[:100],
                        prefer_async=False,
                        run_sync_in_thread=True,
                    )
                else:
                    result = "Unknown tool"
            except Exception as tool_error:
                logger.warning("[DIRECT] Tool %s failed: %s", tc_name, tool_error)
                result = "Tool unavailable"
            await push_event(
                {
                    "type": "tool_result",
                    "content": {
                        "name": tc_name,
                        "result": _summarize_tool_result_for_stream(tc_name, result),
                        "id": tc_id,
                    },
                    "node": "direct",
                }
            )
            await graph_maybe_emit_host_action_event(
                push_event=push_event,
                tool_name=tc_name,
                result=result,
                node="direct",
                tool_call_events=tool_call_events,
            )
            emitted_visual_session_ids, disposed_visual_session_ids = await graph_maybe_emit_visual_event(
                push_event=push_event,
                tool_name=tc_name,
                tool_call_id=tc_id,
                result=result,
                node="direct",
                tool_call_events=tool_call_events,
                previous_visual_session_ids=active_visual_session_ids,
            )
            if emitted_visual_session_ids:
                visual_session_ids.extend(emitted_visual_session_ids)
                active_visual_session_ids = list(dict.fromkeys(emitted_visual_session_ids))
                visual_emitted_any = True
            elif disposed_visual_session_ids:
                disposed = set(disposed_visual_session_ids)
                active_visual_session_ids = [
                    session_id
                    for session_id in active_visual_session_ids
                    if session_id not in disposed
                ]
            reflection = await graph_build_direct_tool_reflection(state, tc_name, result)
            if reflection:
                await push_status_only_progress(
                    push_event,
                    node="direct",
                    content=reflection,
                    subtype="tool_reflection",
                )
            tool_call_events.append(
                {
                    "type": "result",
                    "name": tc_name,
                    "result": str(result),
                    "id": tc_id,
                }
            )
            messages.append(_TM(content=str(result), tool_call_id=tc_id))

            # Phase 3: Detect handoff tool call and set state signal
            if state is not None and tc_name == "handoff_to_agent" and settings.enable_agent_handoffs:
                try:
                    from app.engine.multi_agent.handoff_tools import extract_handoff_target
                    target = extract_handoff_target(tc.get("args", {}))
                    if target:
                        state["_handoff_target"] = target
                        logger.info("[DIRECT] Agent handoff requested → %s", target)
                except Exception:
                    pass
        await graph_emit_visual_commit_events(
            push_event=push_event,
            node="direct",
            visual_session_ids=visual_session_ids,
            tool_call_events=tool_call_events,
        )
        post_tool_heartbeat = asyncio.create_task(
            graph_stream_direct_wait_heartbeats(
                push_event,
                query=query,
                phase="ground",
                cue=round_cue,
                tool_names=round_tool_names,
            )
        )
        try:
            # After the first forced call, keep tool declarations via llm_auto
            # but do not force another tool call; otherwise current/news turns
            # can loop through tools until max_rounds before synthesizing.
            followup_llm = llm_auto
            followup_tool_choice = None
            followup_tools = tools
            bind_source = None
            if requires_visual_commit and not visual_emitted_any:
                required_visual_tool_name_set = set(
                    required_visual_tool_names(visual_decision)
                )
                visual_only_tools = [
                    tool
                    for tool in tools
                    if _tool_name(tool) in required_visual_tool_name_set
                ]
                bind_source = (
                    llm_base
                    or (llm_auto if hasattr(llm_auto, "bind_tools") else None)
                    or (llm_with_tools if hasattr(llm_with_tools, "bind_tools") else None)
                )
                if bind_source is not None and visual_only_tools:
                    followup_tools = visual_only_tools
                    followup_tool_choice = _resolve_tool_choice(
                        True,
                        visual_only_tools,
                        resolved_provider or provider,
                    )
                    if followup_tool_choice:
                        followup_llm = bind_source.bind_tools(
                            visual_only_tools,
                            tool_choice=followup_tool_choice,
                        )
                    else:
                        followup_llm = bind_source.bind_tools(visual_only_tools)
            candidate_provider, _candidate_model = remember_execution_target(
                followup_llm,
                fallback_source=bind_source or llm_base,
            )
            resolved_provider = candidate_provider or resolved_provider
            llm_response = await graph_ainvoke_with_fallback(
                followup_llm,
                messages,
                tools=followup_tools,
                tool_choice=followup_tool_choice,
                tier=runtime_tier_for(followup_llm, bind_source or llm_base),
                provider=provider,
                resolved_provider=resolved_provider,
                failover_mode=request_failover_mode,
                push_event=push_event,
                timeout_profile=followup_timeout_profile,
                state=state,
                allowed_fallback_providers=allowed_fallback_providers,
            )
        finally:
            post_tool_heartbeat.cancel()
            try:
                await post_tool_heartbeat
            except asyncio.CancelledError:
                pass
            except Exception as heartbeat_error:
                logger.debug(
                    "[DIRECT] Post-tool heartbeat shutdown skipped: %s",
                    heartbeat_error,
                )
    if streamed_direct_answer and not tool_call_events:
        state["_answer_streamed_via_bus"] = True
        return llm_response, messages, tool_call_events

    remaining_tool_calls = bool(
        tools and hasattr(llm_response, "tool_calls") and llm_response.tool_calls
    )
    visible_response_text = _extract_direct_visible_text(
        getattr(llm_response, "content", "")
    )
    if tool_call_events and (remaining_tool_calls or not visible_response_text):
        from langchain_core.messages import HumanMessage as _HM

        logger.warning(
            "[DIRECT] Tool loop ended without final prose "
            "(remaining_tool_calls=%s, visible_len=%d) -> forcing no-tool synthesis",
            remaining_tool_calls,
            len(visible_response_text),
        )
        synthesis_tool_names = [
            str(event.get("name", ""))
            for event in tool_call_events
            if event.get("type") == "call"
        ]
        synthesis_messages = list(messages)
        synthesis_messages.append(
            _HM(
                content=_build_direct_final_synthesis_instruction(
                    query,
                    state,
                    synthesis_tool_names,
                )
            )
        )
        synthesis_llm = llm_base or llm_auto or llm_with_tools
        synthesis_heartbeat = asyncio.create_task(
            graph_stream_direct_wait_heartbeats(
                push_event,
                query=query,
                phase="synthesize",
                cue=synthesis_cue if "synthesis_cue" in locals() else "synthesis",
                tool_names=synthesis_tool_names if "synthesis_tool_names" in locals() else None,
            )
        )
        try:
            candidate_provider, _candidate_model = remember_execution_target(
                synthesis_llm,
                fallback_source=llm_base,
            )
            resolved_provider = candidate_provider or resolved_provider
            llm_response = await graph_ainvoke_with_fallback(
                synthesis_llm,
                synthesis_messages,
                tier=runtime_tier_for(synthesis_llm, llm_base),
                provider=provider,
                resolved_provider=resolved_provider,
                failover_mode=request_failover_mode,
                push_event=push_event,
                timeout_profile=followup_timeout_profile,
                state=state,
                allowed_fallback_providers=allowed_fallback_providers,
            )
            messages = synthesis_messages
        finally:
            synthesis_heartbeat.cancel()
            try:
                await synthesis_heartbeat
            except asyncio.CancelledError:
                pass
            except Exception as heartbeat_error:
                logger.debug(
                    "[DIRECT] Final synthesis heartbeat shutdown skipped: %s",
                    heartbeat_error,
                )

    llm_response = _inject_widget_blocks_from_tool_results(
        llm_response,
        tool_call_events,
        query=query,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )

    return llm_response, messages, tool_call_events
