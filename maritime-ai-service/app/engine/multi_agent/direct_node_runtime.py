"""Direct node runtime extracted from the graph shell."""

from __future__ import annotations

import inspect
import logging
import re
import unicodedata
from typing import Any

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.engine.llm_failover_runtime import classify_failover_reason_impl
from app.engine.multi_agent.direct_intent import _looks_emotional_support_turn
from app.engine.multi_agent.direct_visible_thinking_cleanup import (
    looks_like_direct_selfhood_answer_draft_paragraph,
    looks_like_direct_selfhood_english_meta_paragraph,
    looks_like_direct_selfhood_meta_heading,
    looks_like_direct_selfhood_meta_intro,
    strip_direct_selfhood_filler_prefix,
)
from app.engine.multi_agent.direct_reasoning import _infer_direct_thinking_mode
from app.engine.multi_agent.direct_response_runtime import (
    resolve_direct_fallback_provider_allowlist_impl_wrapper,
    resolve_direct_answer_primary_timeout_impl,
)
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.visual_intent_resolver import merge_thinking_effort
from app.engine.reasoning import (
    align_visible_thinking_language,
    record_thinking_snapshot,
    resolve_visible_thinking_from_lifecycle,
    should_align_visible_thinking_language,
)
from app.engine.tools.runtime_context import build_tool_runtime_context
from app.engine.multi_agent.graph_runtime_helpers import (
    _copy_runtime_metadata,
    _extract_runtime_target,
    _is_native_runtime_handle,
)

logger = logging.getLogger(__name__)

_IDENTITY_LORE_MARKERS = (
    "the wiii lab",
    "2024",
    "ra doi",
    "dem mua",
    "bong",
)
_IDENTITY_ORIGIN_QUERY_MARKERS = (
    "ra doi",
    "duoc tao",
    "duoc sinh ra",
    "sinh ra",
    "nguon goc",
    "the wiii lab",
    "creator",
    "created by",
    "ai tao",
)
_DIRECT_WOVEN_THOUGHT_INTENTS = {
    "social",
    "personal",
    "off_topic",
    "emotional",
    "identity",
    "selfhood",
}
_DIRECT_ENGLISH_PLANNER_MARKERS = (
    "the goal is",
    "i'm focusing on",
    "i am focusing on",
    "i've just refined",
    "ive just refined",
    "i opted for",
    "registered the user's input",
    "registered the users input",
    "processing the sentiment",
    "warm, empathetic response",
    "natural, conversational reply",
    "because it sounds the most natural",
)
_DIRECT_INTERNAL_THOUGHT_MARKERS = (
    "living core card",
    "wiii living core card",
    "system prompt",
    "promptloader",
    "persona yaml",
    "yaml persona",
    "house prompt",
    "developer instruction",
    "instruction block",
)
_DIRECT_VISIBLE_THOUGHT_DRAFT_SPLITTERS = (
    "đây là kết quả tôi đã thực hiện",
    "day la ket qua toi da thuc hien",
    "here's the final",
    "here is the final",
    "here is the result",
    "this is the result i produced",
)
_DIRECT_VISIBLE_THOUGHT_TRAILING_SELF_EVAL = (
    "i think it sounds natural",
    "i'm excited for them to hear",
    "im excited for them to hear",
    "it follows the instructions",
    "it is not too robotic",
)
_DIRECT_CANONICAL_THINKING_EFFORT_ALIASES = {
    "light": "low",
    "low": "low",
    "moderate": "medium",
    "medium": "medium",
    "deep": "high",
    "high": "high",
    "max": "max",
}
_DIRECT_ANALYTICAL_THINKING_MODES = {
    "analytical_general",
    "analytical_market",
    "analytical_math",
}


def _fold_direct_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(stripped.lower().replace("đ", "d").split())


def _strip_direct_inline_private_asides(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned

    cleaned = re.sub(
        r"^\s*(\*{1,2})\s*(?:nghĩ thầm|nghi tham|visible thinking|suy nghĩ của wiii|suy nghi cua wiii)\s*:\s*",
        r"\1",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^\s*\((?:nghĩ thầm|nghi tham|visible thinking|suy nghĩ của wiii|suy nghi cua wiii)\s*:\s*",
        "(",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    changed = True
    while changed and cleaned:
        changed = False
        stripped = cleaned.lstrip()

        json_match = re.match(
            r"^\{\s*\"visible_thinking\"\s*:\s*\".*?\"\s*\}\s*",
            stripped,
            flags=re.DOTALL,
        )
        if json_match:
            cleaned = stripped[json_match.end() :].lstrip()
            changed = True
            continue

        if stripped.startswith("("):
            boundary = stripped.find(")\n\n")
            if boundary > 0 and boundary < 500:
                cleaned = stripped[boundary + 3 :].lstrip()
                changed = True
                continue

        if stripped.startswith("*"):
            boundary = stripped.find("*\n\n", 1)
            if boundary > 0 and boundary < 500:
                cleaned = stripped[boundary + 3 :].lstrip()
                changed = True
                continue
    return cleaned.strip()


def _compact_basic_identity_answer(value: str, *, query: str) -> str:
    cleaned = _strip_direct_inline_private_asides(value)
    if not cleaned:
        return cleaned

    folded_query = _fold_direct_text(query)
    if any(marker in folded_query for marker in _IDENTITY_ORIGIN_QUERY_MARKERS):
        return cleaned

    if len(cleaned) < 320 and not any(marker in _fold_direct_text(cleaned) for marker in _IDENTITY_LORE_MARKERS):
        return cleaned

    kept: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            continue
        folded_line = _fold_direct_text(line)
        if any(marker in folded_line for marker in _IDENTITY_LORE_MARKERS):
            continue
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip()]
        for sentence in sentences:
            folded_sentence = _fold_direct_text(sentence)
            if any(marker in folded_sentence for marker in _IDENTITY_LORE_MARKERS):
                continue
            if sentence not in kept:
                kept.append(sentence)

    if not kept:
        return cleaned

    compact = " ".join(kept[:4]).strip()
    return compact or cleaned


def _extract_direct_woven_thought(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""

    italic_match = re.match(r"^\*{1,2}(?P<thought>.+?)\*{1,2}(?:\s+|$)", cleaned, flags=re.DOTALL)
    if italic_match:
        thought = italic_match.group("thought").strip()
        if 20 <= len(thought) <= 400:
            return thought

    paren_match = re.match(r"^\((?P<thought>.+?)\)(?:\s+|$)", cleaned, flags=re.DOTALL)
    if paren_match:
        thought = paren_match.group("thought").strip()
        if 20 <= len(thought) <= 400:
            return thought

    return ""


def _looks_like_direct_english_planner_thought(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    if len(lowered) < 40:
        return False
    return any(marker in lowered for marker in _DIRECT_ENGLISH_PLANNER_MARKERS)


def _contains_direct_internal_thought_leak(value: str) -> bool:
    folded = _fold_direct_text(value)
    if not folded:
        return False
    return any(marker in folded for marker in _DIRECT_INTERNAL_THOUGHT_MARKERS)


def _trim_direct_visible_thought_answer_draft(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""

    lowered = clean.lower()
    cut_at = len(clean)
    for marker in _DIRECT_VISIBLE_THOUGHT_DRAFT_SPLITTERS:
        idx = lowered.find(marker)
        if idx >= 0:
            cut_at = min(cut_at, idx)

    trimmed = clean[:cut_at].rstrip(" :\n\t") if cut_at < len(clean) else clean
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", trimmed) if part.strip()]
    while paragraphs:
        folded_tail = _fold_direct_text(paragraphs[-1])
        if any(marker in folded_tail for marker in _DIRECT_VISIBLE_THOUGHT_TRAILING_SELF_EVAL):
            paragraphs.pop()
            continue
        break
    return "\n\n".join(paragraphs).strip()


def _canonicalize_direct_thinking_effort(value: str | None) -> str | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    return _DIRECT_CANONICAL_THINKING_EFFORT_ALIASES.get(candidate)


def _resolve_direct_thinking_effort(
    *,
    query: str,
    state: AgentState,
    current_effort: str | None,
    is_identity_turn: bool,
    is_short_house_chatter: bool,
) -> str | None:
    canonical_effort = _canonicalize_direct_thinking_effort(current_effort)
    local_effort: str | None = None

    if is_short_house_chatter:
        local_effort = "low"
    else:
        folded_query = _fold_direct_text(query)
        if is_identity_turn:
            if any(marker in folded_query for marker in _IDENTITY_ORIGIN_QUERY_MARKERS):
                local_effort = "max"
            else:
                local_effort = "high"
        else:
            thinking_mode = _infer_direct_thinking_mode(query, state, [])
            if thinking_mode in _DIRECT_ANALYTICAL_THINKING_MODES:
                local_effort = "high"

    # Direct lane should be allowed to override generic routing defaults such as
    # medium/moderate, while still preserving explicit higher asks like max.
    if canonical_effort in {"high", "max"}:
        return merge_thinking_effort(local_effort, canonical_effort)
    if local_effort:
        return local_effort
    return canonical_effort


def _should_surface_direct_visible_thought(
    value: str,
    *,
    routing_intent: str = "",
    response: str = "",
) -> bool:
    clean = _strip_direct_inline_private_asides(value)
    if len(clean) < 20:
        return False
    normalized_intent = str(routing_intent or "").strip().lower()
    if normalized_intent not in _DIRECT_WOVEN_THOUGHT_INTENTS:
        return False
    if _extract_direct_woven_thought(response):
        return False
    if _contains_direct_internal_thought_leak(clean):
        return False
    if _looks_like_direct_english_planner_thought(clean):
        return False
    return True


async def _align_direct_visible_thought(
    value: str,
    *,
    response_language: str,
    llm,
) -> str:
    clean = _strip_direct_inline_private_asides(value)
    if not clean:
        return ""
    trimmed = _trim_direct_visible_thought_answer_draft(clean)
    if not trimmed:
        return ""

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", trimmed) if part.strip()]
    kept: list[str] = []
    for paragraph in paragraphs:
        normalized = paragraph.strip()
        if (
            looks_like_direct_selfhood_meta_intro(normalized)
            or looks_like_direct_selfhood_meta_heading(normalized)
            or looks_like_direct_selfhood_english_meta_paragraph(normalized)
            or looks_like_direct_selfhood_answer_draft_paragraph(normalized)
        ):
            continue
        normalized = strip_direct_selfhood_filler_prefix(normalized)
        if should_align_visible_thinking_language(
            normalized,
            target_language=response_language,
        ):
            aligned = await align_visible_thinking_language(
                normalized,
                target_language=response_language,
                llm=llm,
            )
            normalized = _strip_direct_inline_private_asides(aligned or normalized).strip()
            normalized = strip_direct_selfhood_filler_prefix(normalized)
        if (
            not normalized
            or looks_like_direct_selfhood_meta_intro(normalized)
            or looks_like_direct_selfhood_meta_heading(normalized)
            or looks_like_direct_selfhood_english_meta_paragraph(normalized)
            or looks_like_direct_selfhood_answer_draft_paragraph(normalized)
        ):
            continue
        if should_align_visible_thinking_language(
            normalized,
            target_language=response_language,
        ):
            continue
        kept.append(normalized)
    return "\n\n".join(kept).strip()


def _best_effort_direct_visible_thought_raw(value: str) -> str:
    clean = _strip_direct_inline_private_asides(value)
    if not clean:
        return ""
    trimmed = _trim_direct_visible_thought_answer_draft(clean)
    if not trimmed:
        return ""

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", trimmed) if part.strip()]
    kept: list[str] = []
    for paragraph in paragraphs:
        normalized = paragraph.strip()
        if (
            not normalized
            or looks_like_direct_selfhood_meta_intro(normalized)
            or looks_like_direct_selfhood_meta_heading(normalized)
            or looks_like_direct_selfhood_english_meta_paragraph(normalized)
            or looks_like_direct_selfhood_answer_draft_paragraph(normalized)
        ):
            continue
        normalized = strip_direct_selfhood_filler_prefix(normalized)
        if not normalized or _contains_direct_internal_thought_leak(normalized):
            continue
        kept.append(normalized)
    return "\n\n".join(kept).strip()


async def _build_emotional_rescue_visible_thought(
    *,
    query: str,
    state: AgentState,
    response: str,
    response_language: str,
    llm: Any,
    build_direct_reasoning_summary,
    tool_names: list[str] | None = None,
) -> str:
    """Backfill a tiny public thought when emotional turns return no native thought."""
    if not _looks_emotional_support_turn(query):
        return ""
    if not str(response or "").strip():
        return ""

    try:
        fallback = build_direct_reasoning_summary(query, state, tool_names or [])
        if inspect.isawaitable(fallback):
            fallback = await fallback
    except Exception as exc:
        logger.debug("[DIRECT] Emotional rescue summary skipped: %s", exc)
        return ""

    clean = _strip_direct_inline_private_asides(str(fallback or "")).strip()
    if len(clean) < 20:
        return ""
    if _contains_direct_internal_thought_leak(clean):
        return ""
    if _looks_like_direct_english_planner_thought(clean):
        return ""

    aligned = await _align_direct_visible_thought(
        clean,
        response_language=response_language,
        llm=llm,
    )
    if aligned and not _contains_direct_internal_thought_leak(
        aligned
    ) and not should_align_visible_thinking_language(
        aligned,
        target_language=response_language,
    ):
        return aligned
    return _best_effort_direct_visible_thought_raw(clean)


async def _salvage_direct_turn_from_final_result(
    *,
    llm_response: Any,
    messages: list[Any],
    extract_direct_response,
    sanitize_structured_visual_answer_text,
    sanitize_wiii_house_text,
    tool_call_events: list[dict[str, Any]],
    query: str,
    is_identity_turn: bool,
    routing_intent: str,
    response_language: str,
    llm: Any,
) -> tuple[str, str, list[dict[str, Any]]] | None:
    if llm_response is None:
        return None

    try:
        response, thinking_content, tools_used = extract_direct_response(llm_response, messages or [])
    except Exception as exc:
        logger.warning("[DIRECT] Salvage extraction failed: %s", exc)
        return None

    response = str(response or "").strip()
    if not response:
        return None

    try:
        response = sanitize_structured_visual_answer_text(
            response,
            tool_call_events=tool_call_events,
        )
    except Exception as exc:
        logger.debug("[DIRECT] Salvage skipped visual sanitize: %s", exc)

    try:
        response = sanitize_wiii_house_text(response, query=query)
    except Exception as exc:
        logger.debug("[DIRECT] Salvage skipped house sanitize: %s", exc)

    response = _strip_direct_inline_private_asides(response)
    if is_identity_turn:
        try:
            response = _compact_basic_identity_answer(response, query=query)
        except Exception as exc:
            logger.debug("[DIRECT] Salvage skipped identity compaction: %s", exc)

    response = str(response or "").strip()
    if not response:
        return None

    visible_thought = ""
    if _should_surface_direct_visible_thought(
        thinking_content,
        routing_intent=routing_intent,
        response=response,
    ):
        try:
            visible_thought = await _align_direct_visible_thought(
                thinking_content,
                response_language=response_language,
                llm=llm,
            )
        except Exception as exc:
            logger.debug("[DIRECT] Salvage alignment skipped: %s", exc)
        if not visible_thought:
            visible_thought = _best_effort_direct_visible_thought_raw(thinking_content)

    return response, visible_thought, tools_used


async def direct_response_node_impl(
    state: AgentState,
    *,
    direct_response_step_name,
    get_or_create_tracer,
    capture_public_thinking_event,
    get_domain_greetings,
    normalize_for_intent,
    looks_identity_selfhood_turn,
    needs_web_search,
    needs_datetime,
    resolve_visual_intent,
    recommended_visual_thinking_effort,
    get_active_code_studio_session,
    merge_thinking_effort,
    get_effective_provider,
    get_explicit_user_provider,
    collect_direct_tools,
    direct_required_tool_names,
    resolve_direct_answer_timeout_profile,
    bind_direct_tools,
    build_direct_system_messages,
    build_visual_tool_runtime_metadata,
    execute_direct_tool_rounds,
    extract_direct_response,
    sanitize_structured_visual_answer_text,
    sanitize_wiii_house_text,
    build_direct_reasoning_summary,
    direct_tool_names,
    should_surface_direct_thinking,
    resolve_public_thinking_content,
    get_phase_fallback,
) -> AgentState:
    """Direct response node - conversational responses without RAG."""
    query = state.get("query", "")

    event_queue = None
    bus_id = state.get("_event_bus_id")
    if bus_id:
        from app.engine.multi_agent.graph_event_bus import _get_event_queue

        event_queue = _get_event_queue(bus_id)

    async def push_event(event: dict):
        capture_public_thinking_event(state, event)
        if event_queue:
            try:
                event_queue.put_nowait(event)
            except Exception as queue_error:
                logger.debug("[DIRECT] Event queue push failed: %s", queue_error)

    tracer = get_or_create_tracer(state)
    tracer.start_step(direct_response_step_name, "Tao phan hoi truc tiep")

    use_natural = getattr(settings, "enable_natural_conversation", False) is True
    if not use_natural:
        greetings = get_domain_greetings(state.get("domain_id", settings.default_domain))
        query_lower = query.lower().strip()
        response = greetings.get(query_lower)
    else:
        query_lower = query.lower().strip()
        response = None
    response_type = "greeting" if response else ""

    domain_config = state.get("domain_config", {})
    domain_name_vi = domain_config.get("name_vi", "")
    if not domain_name_vi:
        domain_id = state.get("domain_id", settings.default_domain)
        domain_name_vi = {
            "maritime": "Hang hai",
            "traffic_law": "Luat Giao thong",
        }.get(domain_id, domain_id)

    if response:
        tracer.end_step(
            result=f"Direct fast response: {response[:50]}...",
            confidence=1.0,
            details={"response_type": response_type or "greeting", "query": query_lower},
        )
    else:
        explicit_user_provider: str | None = None
        llm = None
        llm_response = None
        messages: list[Any] = []
        tool_call_events: list[dict[str, Any]] = []
        response_language = "vi"
        routing_intent = ""
        is_identity_turn = False
        is_emotional_support_turn = False
        try:
            from app.engine.multi_agent.agent_config import AgentConfigRegistry

            ctx = state.get("context", {})
            response_language = str(ctx.get("response_language") or "vi").strip() or "vi"
            thinking_effort = state.get("thinking_effort")
            routing_meta = state.get("routing_metadata") or {}
            routing_hint = state.get("_routing_hint") if isinstance(state.get("_routing_hint"), dict) else {}
            routing_method = str(routing_meta.get("method") or "").strip().lower()
            routing_intent = str(routing_meta.get("intent") or "").strip().lower()
            hint_kind = str(routing_hint.get("kind") or "").strip().lower()
            hint_shape = str(routing_hint.get("shape") or "").strip().lower()
            normalized_query = normalize_for_intent(query)
            short_token_count = len([token for token in normalized_query.split() if token])
            is_identity_turn = (
                hint_kind == "identity_probe"
                or hint_kind == "selfhood_followup"
                or routing_intent in {"identity", "selfhood"}
                or looks_identity_selfhood_turn(query)
            )
            is_emotional_support_turn = _looks_emotional_support_turn(query)
            is_chatter_fast_path = (
                routing_method == "always_on_chatter_fast_path"
                or (hint_kind == "fast_chatter" and hint_shape in {"reaction", "vague_banter"})
            )
            is_social_fast_path = (
                routing_method == "always_on_social_fast_path"
                or (hint_kind == "fast_chatter" and hint_shape == "social")
            )
            visual_decision = resolve_visual_intent(query)
            is_short_house_chatter = (
                not is_identity_turn
                and (
                    is_chatter_fast_path
                    or is_social_fast_path
                    or (
                        routing_intent == "social"
                        and short_token_count <= 6
                        and not needs_web_search(query)
                        and not needs_datetime(query)
                        and not visual_decision.force_tool
                    )
                )
            )
            history_limit = 0 if is_short_house_chatter else 10
            tools_context_override = "" if is_short_house_chatter else None
            role_name = (
                "direct_chatter_agent"
                if (is_short_house_chatter or is_identity_turn)
                else "direct_agent"
            )
            if is_short_house_chatter:
                history_limit = 0
                tools_context_override = ""
            if is_identity_turn:
                history_limit = max(history_limit, 6)
            thinking_effort = _resolve_direct_thinking_effort(
                query=query,
                state=state,
                current_effort=thinking_effort,
                is_identity_turn=is_identity_turn,
                is_short_house_chatter=is_short_house_chatter,
            )

            visual_effort = recommended_visual_thinking_effort(
                query,
                active_code_session=get_active_code_studio_session(state),
            )
            if visual_effort:
                previous_effort = thinking_effort
                thinking_effort = merge_thinking_effort(
                    thinking_effort,
                    visual_effort,
                )
                if thinking_effort != previous_effort:
                    logger.info(
                        "[DIRECT] Visual intent detected -> upgrade thinking effort %s -> %s",
                        previous_effort or "default",
                        thinking_effort,
                    )

            preferred_provider = get_effective_provider(state)
            explicit_user_provider = get_explicit_user_provider(state)
            use_house_voice_direct = (
                routing_intent in {"social", "personal", "off_topic"}
                and not needs_web_search(query)
                and not needs_datetime(query)
                and not visual_decision.force_tool
            )
            direct_provider_override = explicit_user_provider or preferred_provider

            if is_short_house_chatter or is_identity_turn or is_emotional_support_turn:
                tools, force_tools = [], False
            else:
                tools, force_tools = collect_direct_tools(
                    query,
                    ctx.get("user_role", "student"),
                    state=state,
                )
                try:
                    from app.engine.skills.skill_recommender import select_runtime_tools

                    selected_tools = select_runtime_tools(
                        tools,
                        query=query,
                        intent=(state.get("routing_metadata") or {}).get("intent"),
                        user_role=ctx.get("user_role", "student"),
                        max_tools=min(len(tools), 7),
                        must_include=direct_required_tool_names(
                            query,
                            ctx.get("user_role", "student"),
                        ),
                    )
                    if selected_tools:
                        tools = selected_tools
                        logger.info(
                            "[DIRECT] Runtime-selected tools: %s",
                            [getattr(tool, "name", getattr(tool, "__name__", "unknown")) for tool in tools],
                        )
                except Exception as selection_error:
                    logger.debug("[DIRECT] Runtime tool selection skipped: %s", selection_error)

            direct_node_id = "direct_identity" if is_identity_turn else "direct"

            from app.engine.multi_agent.openai_stream_runtime import (
                _supports_native_answer_streaming_impl,
            )

            native_direct_possible = (
                not bool(ctx.get("images") or [])
                and not is_short_house_chatter
                and not is_identity_turn
                and not is_emotional_support_turn
                and not use_house_voice_direct
            )
            llm = None
            if native_direct_possible:
                llm = AgentConfigRegistry.get_native_llm(
                    direct_node_id,
                    effort_override=thinking_effort,
                    provider_override=direct_provider_override,
                    requested_model=state.get("model"),
                )
                if llm and not _supports_native_answer_streaming_impl(
                    getattr(llm, "_wiii_provider_name", None)
                ):
                    llm = None
            if llm is None:
                llm = AgentConfigRegistry.get_llm(
                    direct_node_id,
                    effort_override=thinking_effort,
                    provider_override=direct_provider_override,
                    requested_model=state.get("model"),
                )

            if (
                llm
                and getattr(settings, "enable_natural_conversation", False) is True
                and not _is_native_runtime_handle(llm)
            ):
                presence_penalty = getattr(settings, "llm_presence_penalty", 0.0)
                frequency_penalty = getattr(settings, "llm_frequency_penalty", 0.0)
                if presence_penalty or frequency_penalty:
                    try:
                        llm = _copy_runtime_metadata(
                            llm,
                            llm.bind(
                                presence_penalty=presence_penalty,
                                frequency_penalty=frequency_penalty,
                            ),
                        )
                    except Exception:
                        pass

            if llm:
                logger.warning(
                    "[DIRECT] tools=%d, force=%s, web=%s, dt=%s, query='%s'",
                    len(tools),
                    force_tools,
                    needs_web_search(query),
                    needs_datetime(query),
                    query[:60],
                )

                if visual_decision.force_tool and not force_tools and routing_intent not in ("learning", "lookup"):
                    has_visual_tool = any(getattr(tool, "name", getattr(tool, "__name__", "")) == "tool_generate_visual" for tool in tools)
                    if has_visual_tool:
                        force_tools = True
                        logger.info(
                            "[DIRECT] Visual intent -> force tool_choice='any' (visual_type=%s)",
                            visual_decision.visual_type,
                        )
                    else:
                        logger.warning(
                            "[DIRECT] Visual intent detected but tool_generate_visual not in tools list",
                        )

                bound_provider, bound_model = _extract_runtime_target(llm)
                bound_provider = bound_provider or state.get("provider")
                if bound_provider and str(bound_provider).strip().lower() != "auto":
                    state["_execution_provider"] = str(bound_provider)
                if bound_model:
                    state["_execution_model"] = str(bound_model)
                    state["model"] = str(bound_model)
                direct_answer_timeout_profile = resolve_direct_answer_timeout_profile(
                    provider_name=bound_provider or direct_provider_override or preferred_provider,
                    query=query,
                    state=state,
                    is_identity_turn=is_identity_turn,
                    is_short_house_chatter=is_short_house_chatter,
                    use_house_voice_direct=use_house_voice_direct,
                    tools_bound=bool(tools),
                )
                direct_answer_primary_timeout = resolve_direct_answer_primary_timeout_impl(
                    provider_name=bound_provider or direct_provider_override or preferred_provider,
                    query=query,
                    state=state,
                    is_identity_turn=is_identity_turn,
                    is_short_house_chatter=is_short_house_chatter,
                    use_house_voice_direct=use_house_voice_direct,
                    tools_bound=bool(tools),
                )
                direct_allowed_fallback_providers = None
                if not explicit_user_provider:
                    direct_allowed_fallback_providers = (
                        resolve_direct_fallback_provider_allowlist_impl_wrapper(
                            provider_name=bound_provider or direct_provider_override or preferred_provider,
                            query=query,
                            state=state,
                            is_identity_turn=is_identity_turn,
                            is_short_house_chatter=is_short_house_chatter,
                            use_house_voice_direct=use_house_voice_direct,
                            tools_bound=bool(tools),
                        )
                    )
                llm_with_tools, llm_auto, forced_tool_choice = bind_direct_tools(
                    llm,
                    tools,
                    force_tools,
                    provider=bound_provider,
                    include_forced_choice=True,
                )
                if force_tools:
                    logger.info(
                        "[DIRECT] Forced tool_choice (web=%s, dt=%s, visual=%s)",
                        needs_web_search(query),
                        needs_datetime(query),
                        visual_decision.force_tool,
                    )

                native_direct_messages = _is_native_runtime_handle(llm)
                messages = build_direct_system_messages(
                    state,
                    query,
                    domain_name_vi,
                    role_name=role_name,
                    tools_context_override=tools_context_override,
                    visual_decision=visual_decision,
                    history_limit=history_limit,
                    native_messages=native_direct_messages,
                )
                runtime_context_base = build_tool_runtime_context(
                    event_bus_id=bus_id,
                    request_id=ctx.get("request_id"),
                    session_id=state.get("session_id"),
                    organization_id=state.get("organization_id"),
                    user_id=state.get("user_id"),
                    user_role=ctx.get("user_role", "student"),
                    node="direct",
                    source="agentic_loop",
                    metadata=build_visual_tool_runtime_metadata(state, query),
                )

                llm_response, messages, tool_call_events = await execute_direct_tool_rounds(
                    llm_with_tools,
                    llm_auto,
                    messages,
                    tools,
                    push_event,
                    runtime_context_base=runtime_context_base,
                    query=query,
                    state=state,
                    provider=explicit_user_provider,
                    forced_tool_choice=forced_tool_choice,
                    llm_base=llm,
                    direct_answer_timeout_profile=direct_answer_timeout_profile,
                    direct_answer_primary_timeout=direct_answer_primary_timeout,
                    allowed_fallback_providers=direct_allowed_fallback_providers,
                    native_tool_messages=native_direct_messages,
                )

                if tool_call_events:
                    state["tool_call_events"] = tool_call_events

                response, thinking_content, tools_used = extract_direct_response(llm_response, messages)
                response = sanitize_structured_visual_answer_text(
                    response,
                    tool_call_events=tool_call_events,
                )
                response = sanitize_wiii_house_text(response, query=query)
                response = _strip_direct_inline_private_asides(response)
                if is_identity_turn:
                    response = _compact_basic_identity_answer(response, query=query)

                if _should_surface_direct_visible_thought(
                    thinking_content,
                    routing_intent=routing_intent,
                    response=response,
                ):
                    aligned_thinking = await _align_direct_visible_thought(
                        thinking_content,
                        response_language=response_language,
                        llm=llm,
                    )
                    if aligned_thinking and not _contains_direct_internal_thought_leak(
                        aligned_thinking
                    ) and not should_align_visible_thinking_language(
                        aligned_thinking,
                        target_language=response_language,
                    ):
                        state["thinking"] = aligned_thinking
                        state["thinking_content"] = aligned_thinking
                        record_thinking_snapshot(
                            state,
                            aligned_thinking,
                            node="direct",
                            provenance="aligned_cleanup",
                        )
                    else:
                        state.pop("thinking", None)
                        state["thinking_content"] = ""
                else:
                    state.pop("thinking", None)
                    state["thinking_content"] = ""
                if not str(state.get("thinking_content") or "").strip():
                    emotional_rescue = await _build_emotional_rescue_visible_thought(
                        query=query,
                        state=state,
                        response=response,
                        response_language=response_language,
                        llm=llm,
                        build_direct_reasoning_summary=build_direct_reasoning_summary,
                        tool_names=list(tools_used or []),
                    )
                    if emotional_rescue:
                        state["thinking"] = emotional_rescue
                        state["thinking_content"] = emotional_rescue
                        record_thinking_snapshot(
                            state,
                            emotional_rescue,
                            node="direct",
                            provenance="aligned_cleanup",
                        )
                if tools_used:
                    state["tools_used"] = tools_used

                tracer.end_step(
                    result=f"Phan hoi LLM: {len(response)} chars",
                    confidence=0.85,
                    details={
                        "response_type": "llm_generated",
                        "tools_bound": len(tools),
                        "force_tools": force_tools,
                    },
                )
            else:
                if explicit_user_provider:
                    raise ProviderUnavailableError(
                        provider=str(explicit_user_provider).strip().lower(),
                        reason_code="busy",
                        message="Provider được chọn hiện không sẵn sàng để xử lý yêu cầu này.",
                    )
                response = (
                    get_phase_fallback(state)
                    if getattr(settings, "enable_natural_conversation", False) is True
                    else "Xin chao! Toi co the giup gi cho ban?"
                )
                tracer.end_step(
                    result="Fallback (LLM unavailable)",
                    confidence=0.5,
                    details={"response_type": "fallback"},
                )
        except Exception as exc:
            salvaged = await _salvage_direct_turn_from_final_result(
                llm_response=llm_response,
                messages=messages,
                extract_direct_response=extract_direct_response,
                sanitize_structured_visual_answer_text=sanitize_structured_visual_answer_text,
                sanitize_wiii_house_text=sanitize_wiii_house_text,
                tool_call_events=tool_call_events,
                query=query,
                is_identity_turn=is_identity_turn,
                routing_intent=routing_intent,
                response_language=response_language,
                llm=llm,
            )
            if salvaged:
                response, salvaged_thinking, salvaged_tools = salvaged
                if salvaged_tools:
                    state["tools_used"] = salvaged_tools
                if salvaged_thinking:
                    state["thinking"] = salvaged_thinking
                    state["thinking_content"] = salvaged_thinking
                    record_thinking_snapshot(
                        state,
                        salvaged_thinking,
                        node="direct",
                        provenance="final_snapshot",
                    )
                logger.warning(
                    "[DIRECT] Post-processing failed but salvaged final result: %s",
                    exc,
                )
                tracer.end_step(
                    result="Salvaged direct response after post-processing error",
                    confidence=0.7,
                    details={
                        "response_type": "llm_salvaged",
                        "error_type": type(exc).__name__,
                    },
                )
            elif isinstance(exc, ProviderUnavailableError):
                raise
            elif explicit_user_provider:
                if isinstance(exc, ProviderUnavailableError):
                    raise
                classified = classify_failover_reason_impl(error=exc)
                raise ProviderUnavailableError(
                    provider=str(explicit_user_provider).strip().lower(),
                    reason_code=str(classified.get("reason_code") or "provider_unavailable"),
                    message="Provider được chọn hiện không sẵn sàng để xử lý yêu cầu này.",
                    details=classified.get("detail"),
                ) from exc
            else:
                logger.warning("[DIRECT] LLM generation failed: %s", exc)
                response = (
                    get_phase_fallback(state)
                    if getattr(settings, "enable_natural_conversation", False) is True
                    else "Xin chao! Toi co the giup gi cho ban?"
                )
                tracer.end_step(
                    result="Fallback (LLM generation error)",
                    confidence=0.5,
                    details={"response_type": "fallback"},
                )

    resolved_direct_thinking = resolve_public_thinking_content(
        state,
        fallback="",
    )
    if resolved_direct_thinking:
        state["thinking_content"] = resolved_direct_thinking
        record_thinking_snapshot(
            state,
            resolved_direct_thinking,
            node="direct",
            provenance=(
                "final_snapshot"
                if resolved_direct_thinking == str(state.get("thinking") or "").strip()
                else "aligned_cleanup"
            ),
        )

    state["final_response"] = response
    state["agent_outputs"] = {"direct": response}
    state["current_agent"] = "direct"

    routing_meta = state.get("routing_metadata", {})
    intent = routing_meta.get("intent", "") if routing_meta else ""
    if intent == "general":
        from app.core.config import settings as local_settings
        from app.core.org_context import get_current_org_id

        suppress = local_settings.enable_org_knowledge and bool(get_current_org_id())
        if not suppress:
            state["domain_notice"] = (
                f"Noi dung nay nam ngoai chuyen mon {domain_name_vi}. "
                f"De duoc ho tro chinh xac hon, hay hoi ve {domain_name_vi} nhe!"
            )

    logger.info("[DIRECT] Response prepared, tracer passed to synthesizer")
    return state
