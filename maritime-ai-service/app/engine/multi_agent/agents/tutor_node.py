"""Tutor agent node for teaching flows with ReAct + RAG-backed tools."""

import json
import html
import logging
import re
from typing import Optional, List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.services.output_processor import extract_thinking_from_response
from app.engine.multi_agent.state import AgentState
from app.engine.agents import TUTOR_AGENT_CONFIG
from app.engine.tools.rag_tools import (
    tool_knowledge_search,
    get_last_retrieved_sources,
    get_last_native_thinking,  # CH? TH? S? 29 v9: Option B+ thinking propagation
    get_last_reasoning_trace,  # CH? TH? S? 31 v3: CRAG trace propagation
    get_last_confidence,  # SOTA 2025: Confidence-based early termination
    is_no_internal_match_observation,
    clear_retrieved_sources,
)
from app.engine.tools.utility_tools import tool_calculator, tool_current_datetime
from app.engine.tools.web_search_tools import tool_web_search
from app.engine.tools.think_tool import tool_think
from app.engine.tools.progress_tool import tool_report_progress
from app.engine.tools.invocation import get_tool_by_name, invoke_tool_with_runtime
from app.engine.multi_agent.visual_intent_resolver import (
    preferred_visual_tool_name,
    required_visual_tool_names,
    resolve_visual_intent,
)
from app.prompts.prompt_loader import get_prompt_loader
from app.engine.multi_agent.agents.tutor_response import (
    apply_quiz_socratic_guardrail,
    build_tutor_fallback_response,
    build_tutor_rescue_response,
    collect_tutor_model_message,
    collect_tutor_model_message_with_failover,
    extract_tutor_content_with_thinking,
    looks_like_tutor_placeholder_answer,
    normalize_tutor_answer_shape,
    recover_tutor_answer_from_messages,
)
from app.engine.multi_agent.agents.tutor_request_runtime import (
    build_tutor_tools,
    prepare_tutor_request,
)
from app.engine.multi_agent.agents.tutor_runtime import initialize_tutor_llm
from app.engine.multi_agent.agents.tutor_tool_dispatch_runtime import (
    dispatch_tutor_tool_call,
)
from app.engine.multi_agent.graph_surface_runtime import (
    get_effective_provider_impl as _get_effective_provider,
)
from app.engine.multi_agent.direct_prompts import (
    _resolve_tool_choice,
)
from app.engine.reasoning import (
    align_visible_thinking_language,
    capture_thinking_lifecycle_event,
    resolve_visible_thinking_from_lifecycle,
    record_thinking_snapshot,
    sanitize_public_tutor_thinking,
)
from app.prompts.prompt_context_utils import build_response_language_instruction
from app.engine.multi_agent.agents.tutor_surface import (
    LLM_CODE_GEN_VISUAL_INSTRUCTION,
    STRUCTURED_VISUAL_TOOL_INSTRUCTION,
    THINKING_CHAIN_INSTRUCTION,
    TOOL_INSTRUCTION,
    TOOL_INSTRUCTION_DEFAULT,
    _MAX_PHASE_TRANSITIONS,
    _infer_tutor_loop_phase,
    _iteration_beat,
    _iteration_label,
    _tool_acknowledgment,
    build_tutor_identity_grounding_prompt,
    build_tutor_living_stream_cues,
    build_tutor_system_prompt,
)
from app.engine.multi_agent.graph_runtime_helpers import _remember_runtime_target

logger = logging.getLogger(__name__)

_POST_TOOL_ADDRESS_MARKERS = (
    "chào bạn",
    "chao ban",
    "để mình",
    "de minh",
    "mình sẽ",
    "minh se",
    "bạn có",
    "ban co",
    "nếu cần",
    "neu can",
    "cứ hỏi",
    "cu hoi",
    "takeaway",
    "mẹo ghi nhớ",
    "meo ghi nho",
)

_POST_TOOL_SOCIAL_MARKERS = (
    "tuyệt vời",
    "tuyet voi",
    "rất ấn tượng",
    "rat an tuong",
    "đúng chuẩn",
    "dung chuan",
    "đúng không nào",
    "dung khong nao",
    "bạn biết đấy",
    "ban biet day",
    "wiii có thể giúp gì",
    "wiii co the giup gi",
    "hay là chúng ta",
    "hay la chung ta",
    "sẵn sàng đi sâu",
    "san sang di sau",
    "wiii đã sẵn sàng",
    "wiii da san sang",
    "muốn đi sâu",
    "muon di sau",
    "trò chuyện về việc đó",
    "tro chuyen ve viec do",
    "hoàn toàn chính xác",
    "hoan toan chinh xac",
    "màn mở đầu",
    "man mo dau",
    "bạn nhảy của nó",
    "ban nhay cua no",
)

_POST_TOOL_FACT_HINTS = (
    "áp dụng",
    "ap dung",
    "mạn phải",
    "man phai",
    "nhường đường",
    "nhuong duong",
    "tránh cắt",
    "tranh cat",
    "giữ hướng",
    "giu huong",
    "nguy cơ",
    "nguy co",
    "đâm va",
    "dam va",
    "hành động sớm",
    "hanh dong som",
    "điều kiện",
    "dieu kien",
    "stand-on",
    "give-way",
)

_POST_TOOL_TENSION_HINTS = (
    "không",
    "khong",
    "tránh",
    "tranh",
    "đừng",
    "dung",
    "dễ",
    "luu y",
    "lưu ý",
    "tuy nhiên",
    "tuy nhien",
    "nhưng",
    "nhung",
)


def _strip_post_tool_markup(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"</?answer>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"</?thinking>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<!--[\s\S]*?-->", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"`{3}[\s\S]*?`{3}", " ", cleaned)
    cleaned = re.sub(r"`+", " ", cleaned)
    cleaned = re.sub(r"[*_#>\[\]\{\}]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _split_post_tool_units(text: str) -> list[str]:
    if not text:
        return []
    units = re.split(r"(?<=[\.\!\?])\s+|\n+|\s+•\s+|\s+\*\s+|\s+-\s+", text)
    cleaned_units: list[str] = []
    seen: set[str] = set()
    for raw_unit in units:
        unit = " ".join(str(raw_unit or "").split()).strip(" -•")
        if len(unit) < 20:
            continue
        normalized = unit.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned_units.append(unit)
    return cleaned_units


def _looks_like_post_tool_address(unit: str) -> bool:
    lowered = str(unit or "").lower().strip()
    return any(marker in lowered for marker in _POST_TOOL_ADDRESS_MARKERS)


def _looks_like_post_tool_social_or_decorative(unit: str) -> bool:
    lowered = str(unit or "").lower().strip()
    if any(marker in lowered for marker in _POST_TOOL_SOCIAL_MARKERS):
        return True
    if lowered.count("!") >= 2:
        return True
    if "?" in lowered and any(
        marker in lowered
        for marker in (
            "ban",
            "bạn",
            "chung ta",
            "chúng ta",
            "wiii",
        )
    ):
        return True
    return False


def distill_post_tool_context(tool_result_text: str | None) -> str:
    """Extract non-answer-shaped cues from a raw tool result."""

    cleaned = _strip_post_tool_markup(str(tool_result_text or ""))
    if not cleaned:
        return ""
    if is_no_internal_match_observation(cleaned):
        return ""

    units = _split_post_tool_units(cleaned)
    if not units:
        return ""

    factual_units: list[str] = []
    tension_units: list[str] = []
    fallback_units: list[str] = []

    for unit in units:
        lowered = unit.lower()
        if _looks_like_post_tool_address(unit):
            continue
        if _looks_like_post_tool_social_or_decorative(unit):
            continue
        if any(marker in lowered for marker in _POST_TOOL_FACT_HINTS):
            factual_units.append(unit)
            continue
        if any(marker in lowered for marker in _POST_TOOL_TENSION_HINTS):
            tension_units.append(unit)
            continue
        fallback_units.append(unit)

    selected_factual: list[str] = []
    seen_factual: set[str] = set()
    for unit in factual_units + fallback_units:
        normalized = unit.lower()
        if normalized in seen_factual:
            continue
        seen_factual.add(normalized)
        selected_factual.append(unit)
        if len(selected_factual) >= 3:
            break

    selected_tension: list[str] = []
    for unit in tension_units:
        normalized = unit.lower()
        if normalized in seen_factual:
            continue
        if normalized in {item.lower() for item in selected_tension}:
            continue
        selected_tension.append(unit)
        if len(selected_tension) >= 2:
            break

    lines: list[str] = []
    if selected_factual:
        lines.append("Tin hieu vua lo ra:")
        lines.extend(f"- {unit}" for unit in selected_factual)
    if selected_tension:
        lines.append("Cho de nham hoac diem can canh:")
        lines.extend(f"- {unit}" for unit in selected_tension)

    return "\n".join(lines).strip()


def _extract_visual_html_cues(code_html: str | None) -> list[str]:
    raw_html = str(code_html or "").strip()
    if not raw_html:
        return []

    text = html.unescape(re.sub(r"<[^>]+>", "\n", raw_html))
    text = re.sub(r"\s+", " ", text)
    candidates = re.split(r"(?<=[\.\!\?])\s+|(?<=:)\s+|\n+", text)
    keyword_fragments = (
        "quy tắc",
        "quy tac",
        "colreg",
        "đối hướng",
        "doi huong",
        "cắt hướng",
        "cat huong",
        "mạn phải",
        "man phai",
        "nhường đường",
        "nhuong duong",
        "giữ hướng",
        "giu huong",
        "tránh cắt mũi",
        "tranh cat mui",
    )

    selected: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        line = " ".join(str(candidate or "").split()).strip(" -•")
        if len(line) < 18 or len(line) > 220:
            continue
        lowered = line.lower()
        if not any(fragment in lowered for fragment in keyword_fragments):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        selected.append(line)
        if len(selected) >= 4:
            break
    return selected


def distill_visual_tool_context(
    tool_result_text: str | None,
    *,
    tool_call_args: dict[str, Any] | None = None,
) -> str:
    """Extract compact visual signals from a structured visual tool result."""

    raw_text = str(tool_result_text or "").strip()
    tool_call_args = tool_call_args or {}
    html_cues = _extract_visual_html_cues(tool_call_args.get("code_html"))

    payload: dict[str, Any] | None = None
    if raw_text:
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = None

    def _pick(*keys: str) -> str:
        if not payload:
            return ""
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    claim = _pick("claim")
    title = _pick("title")
    pedagogical_role = _pick("pedagogical_role")
    visual_type = _pick("visual_type", "type")
    renderer_kind = _pick("renderer_kind")
    presentation_intent = _pick("presentation_intent")
    title_hint = str(tool_call_args.get("title") or "").strip()
    metadata_norm = " ".join(
        part.lower()
        for part in (claim, title, pedagogical_role, visual_type, renderer_kind, presentation_intent)
        if part
    )
    metadata_looks_generic = any(
        marker in metadata_norm
        for marker in ("benchmark", "chart_runtime", "chart", "thời gian thực thi", "thoi gian thuc thi")
    )

    def _append_unique(lines: list[str], value: str) -> None:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned:
            return
        lowered = cleaned.lower()
        if lowered in {line.lower() for line in lines}:
            return
        lines.append(cleaned)

    def _build_visual_signal_lines(
        *,
        primary_signal: str,
        anchor_signal: str = "",
        tension_signal: str = "",
    ) -> list[str]:
        lines: list[str] = ["Tin hieu vua lo ra tu visual:"]
        if primary_signal:
            _append_unique(lines, f"- Dieu nguoi hoc vua co the chot duoc: {primary_signal}")
        if anchor_signal:
            _append_unique(lines, f"- Moc nen giu de noi tiep: {anchor_signal}")
        if tension_signal:
            lines.append("Cho de nham:")
            _append_unique(lines, f"- {tension_signal}")
        lines.append(
            "- Sau khi co visual, visible thinking chi nen bam vao dieu nguoi hoc vua nhin ra duoc, cho de sot, va moc can giu de noi tiep."
        )
        return lines

    if html_cues and (metadata_looks_generic or not any((claim, title, pedagogical_role, visual_type, renderer_kind, presentation_intent))):
        primary_signal = html_cues[0] if html_cues else ""
        anchor_signal = title_hint if title_hint and title_hint.lower() not in {cue.lower() for cue in html_cues} else ""
        if not anchor_signal and len(html_cues) > 1:
            anchor_signal = html_cues[1]
        tension_index = 1 if anchor_signal == title_hint and len(html_cues) > 1 else 2
        tension_signal = html_cues[tension_index] if len(html_cues) > tension_index else ""
        lines = _build_visual_signal_lines(
            primary_signal=primary_signal,
            anchor_signal=anchor_signal,
            tension_signal=tension_signal,
        )
        return "\n".join(lines).strip()

    if not any((claim, title, pedagogical_role, visual_type, renderer_kind, presentation_intent)):
        return ""

    descriptor_parts = [
        part
        for part in (title_hint, title, pedagogical_role, visual_type, presentation_intent, renderer_kind)
        if part
    ]
    primary_signal = claim or (html_cues[0] if html_cues else "") or title or title_hint
    anchor_signal = ""
    for candidate in descriptor_parts:
        if candidate and str(candidate).strip().lower() != str(primary_signal or "").strip().lower():
            anchor_signal = str(candidate).strip()
            break
    tension_signal = ""
    if len(html_cues) > 1:
        tension_signal = html_cues[1]
    elif len(descriptor_parts) > 1:
        tension_signal = str(descriptor_parts[-1]).strip()
    lines = _build_visual_signal_lines(
        primary_signal=primary_signal,
        anchor_signal=anchor_signal,
        tension_signal=tension_signal,
    )
    return "\n".join(lines).strip()


def _extract_distilled_tool_signals(distilled_context: str | None) -> tuple[list[str], list[str]]:
    factual: list[str] = []
    tensions: list[str] = []
    bucket = factual
    for raw_line in str(distilled_context or "").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("tin hieu vua lo ra"):
            bucket = factual
            continue
        if lowered.startswith("cho de nham") or lowered.startswith("diem can canh"):
            bucket = tensions
            continue
        if line.startswith("-"):
            cleaned = line.lstrip("-").strip()
            if cleaned:
                bucket.append(cleaned)
    return factual, tensions


def _ensure_sentence(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _build_post_tool_fallback_continuation(
    *,
    tool_name: str,
    distilled_context: str | None,
) -> str | None:
    factual, tensions = _extract_distilled_tool_signals(distilled_context)
    if not factual and not tensions:
        return None

    lines: list[str] = []
    if tool_name == "tool_generate_visual":
        if factual:
            lines.append(
                _ensure_sentence(
                    f"Visual này khóa được một mốc khá sáng: {factual[0]}"
                )
            )
        if tensions:
            lines.append(
                _ensure_sentence(
                    f"Chỗ vẫn dễ bị nhìn lướt qua là {tensions[0]}"
                )
            )
        elif len(factual) > 1:
            lines.append(
                _ensure_sentence(
                    f"Điểm mình nên giữ tiếp theo là {factual[1]}"
                )
            )
        lines.append(
            "Mình nên giữ người học ở đúng cảnh này thêm một nhịp rồi mới mở tiếp."
        )
    else:
        if factual:
            lines.append(
                _ensure_sentence(
                    f"Mốc vừa lộ ra rõ nhất là {factual[0]}"
                )
            )
        if tensions:
            lines.append(
                _ensure_sentence(
                    f"Chỗ vẫn dễ lẫn là {tensions[0]}"
                )
            )
        elif len(factual) > 1:
            lines.append(
                _ensure_sentence(
                    f"Điều mình nên giữ câu trả lời bám vào tiếp theo là {factual[1]}"
                )
            )
        if len(factual) > 2:
            lines.append(
                _ensure_sentence(
                    f"Mình chỉ nên mở tiếp sang {factual[2]} khi mốc này đã đứng yên"
                )
            )
        lines.append(
            "Mình nên đặt câu đầu quanh mốc đó, rồi mới mở ra phần hành động hay ví dụ."
        )

    candidate = "\n\n".join(line for line in lines if line).strip()
    candidate = sanitize_public_tutor_thinking(candidate) or ""
    if len(candidate) < 40:
        return None
    return candidate or None

class TutorAgentNode:
    """Teaching specialist that explains, quizzes, and cites with tool support."""
    
    def __init__(self):
        """Initialize Tutor Agent with YAML-driven persona (SOTA 2025)."""
        self._prompt_loader = get_prompt_loader()  # SOTA: YAML persona
        self._llm = None
        self._llm_with_tools = None
        self._config = TUTOR_AGENT_CONFIG
        base_tools = [
            tool_knowledge_search, tool_web_search, tool_calculator,
            tool_current_datetime, tool_report_progress, tool_think,
        ]
        self._tools, self._character_tools_enabled = build_tutor_tools(
            base_tools=base_tools,
            settings_obj=settings,
            logger_obj=logger,
        )

        self._init_llm()
        logger.info("TutorAgentNode initialized with YAML persona, tools: %d", len(self._tools))
    
    def _init_llm(self):
        """Initialize teaching LLM with tools and native thinking."""
        self._llm, self._llm_with_tools = initialize_tutor_llm(
            tools=self._tools,
            logger=logger,
        )
    
    def _build_system_prompt(self, context: dict, query: str) -> str:
        """Build the tutor system prompt via the extracted tutor surface helper."""
        return build_tutor_system_prompt(
            prompt_loader=self._prompt_loader,
            prompt_loader_factory=get_prompt_loader,
            character_tools_enabled=self._character_tools_enabled,
            settings_obj=settings,
            resolve_visual_intent_fn=resolve_visual_intent,
            required_visual_tool_names_fn=required_visual_tool_names,
            preferred_visual_tool_name_fn=preferred_visual_tool_name,
            context=context,
            query=query,
            logger=logger,
        )

    async def process(self, state: AgentState) -> AgentState:
        """
        Process educational request with ReAct pattern.
        
        SOTA Pattern: Think â†’ Act â†’ Observe â†’ Repeat
        
        CHá»ˆ THá»Š Sá» 29 v9: Option B+ - Propagates thinking to state for API transparency.
        Combines thinking from:
        1. RAG tool (via get_last_native_thinking)
        2. Tutor LLM response (extracted in _react_loop)
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tutor output, sources, tools_used, and thinking
        """
        query = state.get("query", "")
        context = state.get("context", {})
        state["allow_authored_thinking_fallback"] = False
        state["allow_secondary_model_thinking"] = bool(
            state.get("allow_secondary_model_thinking", True)
        )
        learning_context = state.get("learning_context", {})

        try:
            # Sprint 69: Get event bus queue for intra-node streaming
            event_queue = None
            bus_id = state.get("_event_bus_id")
            if bus_id:
                from app.engine.multi_agent.graph_event_bus import _get_event_queue
                event_queue = _get_event_queue(bus_id)

            request_runtime = prepare_tutor_request(
                state=state,
                context=context,
                learning_context=learning_context,
                default_llm=self._llm,
                base_tools=self._tools,
                settings_obj=settings,
                logger_obj=logger,
                resolve_visual_intent_fn=resolve_visual_intent,
                required_visual_tool_names_fn=required_visual_tool_names,
                get_effective_provider_fn=_get_effective_provider,
                get_llm_fn=AgentConfigRegistry.get_llm,
                resolve_tool_choice_fn=_resolve_tool_choice,
            )
            _remember_runtime_target(state, request_runtime.llm_for_request)
            _remember_runtime_target(state, request_runtime.llm_with_tools_for_request)

            # Execute ReAct loop - now returns thinking + bus streaming flag
            response, sources, tools_used, thinking, _answer_streamed = await self._react_loop(
                query=query,
                context=request_runtime.merged_context,
                event_queue=event_queue,
                tools=request_runtime.active_tools,
                llm_with_tools=request_runtime.llm_with_tools_for_request,
                runtime_context_base=request_runtime.runtime_context_base,
                state=state,
            )

            # Update state with results
            state["tutor_output"] = response
            state["sources"] = sources
            state["tools_used"] = tools_used
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["tutor"] = response
            state["agent_outputs"]["tutor_tools_used"] = tools_used  # SOTA: Track tool usage
            state["current_agent"] = "tutor_agent"
            
            # CHá»ˆ THá»Š Sá» 29 v9: Set thinking in state for SOTA reasoning transparency
            # This follows the same pattern as rag_node.py
            if thinking:
                state["thinking"] = thinking
                state["thinking_content"] = thinking
                record_thinking_snapshot(
                    state,
                    thinking,
                    node="tutor_agent",
                    provenance=str(state.get("thinking_provenance") or "").strip() or "final_snapshot",
                )
                logger.info("[TUTOR_AGENT] Thinking propagated to state: %d chars", len(thinking))
            else:
                resolved_tutor_thinking = resolve_visible_thinking_from_lifecycle(
                    state,
                    fallback=state.get("thinking_content") or "",
                    default_node="tutor_agent",
                )
                if resolved_tutor_thinking:
                    state["thinking_content"] = resolved_tutor_thinking
                else:
                    state.pop("thinking", None)
                    state["thinking_content"] = ""
                    state.pop("thinking_provenance", None)
            
            # CHá»ˆ THá»Š Sá» 31 v3 SOTA: Propagate CRAG trace for synthesizer merge
            # This follows LangGraph shared state pattern
            crag_trace = get_last_reasoning_trace()
            if crag_trace:
                state["reasoning_trace"] = crag_trace
                logger.info("[TUTOR_AGENT] CRAG trace propagated: %d steps", crag_trace.total_steps)
            
            logger.info("[TUTOR_AGENT] ReAct complete: %d tool calls, %d sources", len(tools_used), len(sources))
            
        except Exception as e:
            logger.error("[TUTOR_AGENT] Error: %s", e)
            state["tutor_output"] = "Ã”i, Wiii váº¥p rá»“i! MÃ¬nh Ä‘ang cá»‘ láº¡i nhÃ©... Báº¡n thá»­ há»i láº¡i mÃ¬nh Ä‘Æ°á»£c khÃ´ng?"
            state["error"] = "tutor_error"
            state["sources"] = []
            state["tools_used"] = []
        
        return state
    
    async def _react_loop(
        self,
        query: str,
        context: dict,
        event_queue=None,
        tools=None,
        llm_with_tools=None,
        runtime_context_base=None,
        state: AgentState | None = None,
    ) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Optional[str], bool]:
        """
        Execute ReAct loop: Think â†’ Act â†’ Observe.

        SOTA Pattern from OpenAI Agents SDK / Anthropic Claude.

        CHá»‰ THá»Š Sá» 29 v9: Now returns thinking for SOTA reasoning transparency.
        Combines thinking from:
        1. RAG tool (get_last_native_thinking)
        2. Tutor LLM final response (extract_thinking_from_response)

        Args:
            query: User query
            context: Additional context
            event_queue: Sprint 69 asyncio.Queue for intra-node streaming

        Returns:
            Tuple of (response, sources, tools_used, thinking, answer_streamed_via_bus).
            The final answer is synthesized downstream for stream parity, so the
            answer-streamed flag is retained only for compatibility.
        """
        llm_with_tools = llm_with_tools or self._llm_with_tools

        if not llm_with_tools:
            return self._fallback_response(query), [], [], None, False

        allow_secondary_model_thinking = (
            True if state is None else bool(state.get("allow_secondary_model_thinking", False))
        )

        tools = tools or self._tools
        
        # Clear previous sources (also clears thinking)
        clear_retrieved_sources()
        response_language = context.get("response_language") or "vi"
        
        # SOTA 2025: Build dynamic prompt from YAML
        system_prompt = self._build_system_prompt(context, query)

        # Unified thinking enforcement at TOP
        try:
            from app.engine.reasoning.thinking_enforcement import get_thinking_enforcement
            system_prompt = get_thinking_enforcement() + "\n\n" + system_prompt
        except Exception:
            pass

        # Initialize messages â€” Sprint 77: inject conversation history
        messages = [SystemMessage(content=system_prompt)]
        lc_messages = context.get("langchain_messages", [])
        if lc_messages:
            messages.extend(lc_messages[-10:])  # Last 10 turns for tutor

        # Sprint 179: Multimodal content blocks when images are present
        images = context.get("images") or []
        if images:
            content_blocks = [{"type": "text", "text": query}]
            for img in images:
                if img.get("type") == "base64":
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img['media_type']};base64,{img['data']}",
                            "detail": img.get("detail", "auto"),
                        }
                    })
                elif img.get("type") == "url":
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {
                            "url": img["data"],
                            "detail": img.get("detail", "auto"),
                        }
                    })
            messages.append(HumanMessage(content=content_blocks))
        else:
            messages.append(HumanMessage(content=query))
        
        tools_used = []
        max_iterations = 4  # Sprint 103bâ†’fix: 2 â†’ 4 (need room for think + search + generate)
        final_response = ""
        llm_thinking = None  # Thinking from final LLM response
        _answer_streamed_via_bus = False  # Legacy compatibility only; tutor no longer streams final answer
        public_tutor_fragments: list[str] = []
        native_tutor_thoughts: list[str] = []
        streamed_native_tutor_public_text = ""
        streamed_native_tutor_reasoning_buffer = ""
        last_tool_result_text: str | None = None
        last_tool_args: dict[str, Any] | None = None
        last_tool_name_seen: str = ""
        used_secondary_public_reflection = False
        # Sprint 70: Sub-chunk size for smooth streaming (matches graph_streaming.py)
        _CHUNK_SIZE = 40  # ~8-10 words per sub-chunk (Sprint 103b: was 12)
        _CHUNK_DELAY = 0.008  # 8ms between sub-chunks (Sprint 103b: was 18ms)

        # Sprint 69: Helper for intra-node event push
        async def _push(evt):
            if state is not None:
                capture_thinking_lifecycle_event(state, evt, default_node="tutor_agent")
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception as exc:
                    logger.warning("[TUTOR_AGENT] Bus push failed: %s", exc)

        async def _push_thinking_deltas_raw(text: str):
            """Push thinking_delta events with sub-chunking for smooth streaming."""
            import asyncio
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({
                    "type": "thinking_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        async def _align_public_tutor_thinking(text: str | None) -> str | None:
            raw_text = str(text or "").strip()
            if not raw_text:
                return None
            public_text = raw_text.replace("<thinking>", "").replace("</thinking>", "").strip()
            if not public_text:
                return None
            aligned_text = await align_visible_thinking_language(
                public_text,
                target_language=response_language,
                llm=self._llm,
            )
            final_text = str(aligned_text or public_text).strip()
            sanitized_text = sanitize_public_tutor_thinking(final_text)
            return sanitized_text or None

        async def _remember_public_tutor_thinking(text: str) -> str | None:
            public_text = await _align_public_tutor_thinking(text)
            if not public_text:
                return None
            normalized = " ".join(public_text.lower().split())
            recent = {" ".join(item.lower().split()) for item in public_tutor_fragments[-6:]}
            if normalized not in recent:
                public_tutor_fragments.append(public_text)
            return public_text

        def _looks_like_answer_or_prompt_spill(text: str) -> bool:
            lowered = str(text or "").lower()
            if not lowered.strip():
                return True

            obvious_markers = (
                "<answer>",
                "</answer>",
                "<câu trả lời>",
                "</câu trả lời>",
                "## goi y dung tool",
                "## wiii continuation mode",
                "tool_generate_visual",
                "tool_knowledge_search",
                "tool_",
                "payload json",
                "wiii tutor",
                "my wiii tutor",
                "my approach",
                "reviewing past responses",
                "crafting the visual",
                "generating the visual elements",
                "structuring response now",
                "i'll ",
                "i will ",
                "let's ",
                "i'm now ",
                "i am now ",
                "**suy nghĩ của wiii",
                "suy nghĩ của wiii về",
                "wiii về quy tắc",
                "wiii ve quy tac",
            )
            if any(marker in lowered for marker in obvious_markers):
                return True

            answer_draft_markers = (
                "chào bạn",
                "chao ban",
                "để mình giải thích",
                "de minh giai thich",
                "mình xin giải thích",
                "minh xin giai thich",
                "chúng ta đã từng bàn",
                "mình sẽ chào",
                "mình sẽ giải thích",
                "mình sẽ dùng",
                "tôi sẽ chào",
                "tôi sẽ giải thích",
                "tôi sẽ dùng",
                "người dùng đã có kiến thức",
                "nguoi dung da co kien thuc",
                "mình có thể giúp gì",
                "minh co the giup gi",
                "hay là chúng ta",
                "hay la chung ta",
                "sẵn sàng đi sâu",
                "san sang di sau",
                "wiii đã sẵn sàng",
                "wiii da san sang",
                "hoàn toàn chính xác",
                "hoan toan chinh xac",
                "đúng không nào",
                "dung khong nao",
                "bạn biết đấy",
                "ban biet day",
            )
            return any(marker in lowered for marker in answer_draft_markers)

        def _should_surface_native_tutor_thought(
            text: str | None,
            *,
            stage: str,
        ) -> bool:
            candidate = str(text or "").strip()
            if len(candidate) < 40:
                return False
            if _looks_like_answer_or_prompt_spill(candidate):
                logger.debug(
                    "[TUTOR_AGENT] Suppressing %s tutor thought due to prompt/answer spill",
                    stage,
                )
                return False
            return True

        async def _push_public_tutor_thinking(text: str):
            public_text = await _remember_public_tutor_thinking(text)
            if not public_text:
                return
            await _push_thinking_deltas_raw(public_text)

        async def _push_public_tutor_fragments(fragments) -> None:
            if not fragments:
                return
            for fragment in fragments:
                if fragment and str(fragment).strip():
                    await _push_public_tutor_thinking(f"{str(fragment).strip()}\n\n")

        async def _push_live_native_tutor_reasoning(reasoning_delta: str) -> None:
            nonlocal streamed_native_tutor_public_text, streamed_native_tutor_reasoning_buffer
            if event_queue is None:
                return

            delta_text = str(reasoning_delta or "")
            if not delta_text.strip():
                return

            streamed_native_tutor_reasoning_buffer += delta_text
            public_text = await _align_public_tutor_thinking(streamed_native_tutor_reasoning_buffer)
            if not public_text:
                return
            if not _should_surface_native_tutor_thought(
                public_text,
                stage="pre_tool_native_stream",
            ):
                return

            emitted_delta = public_text
            if streamed_native_tutor_public_text and public_text.startswith(streamed_native_tutor_public_text):
                emitted_delta = public_text[len(streamed_native_tutor_public_text):]

            if emitted_delta.strip():
                await _push_thinking_deltas_raw(emitted_delta)
            streamed_native_tutor_public_text = public_text

        async def _capture_native_tutor_thinking(
            thinking_text: str | None,
            *,
            reopen_after_tool: bool = False,
            phase_label: str = "",
            stage: str = "captured_native",
        ) -> bool:
            nonlocal streamed_native_tutor_public_text, streamed_native_tutor_reasoning_buffer
            if not thinking_text:
                return False
            if not _should_surface_native_tutor_thought(
                str(thinking_text),
                stage=stage,
            ):
                return False
            native_tutor_thoughts.append(str(thinking_text))
            public_text = await _align_public_tutor_thinking(str(thinking_text))
            if not public_text:
                return False
            normalized = " ".join(public_text.lower().split())
            recent = {" ".join(item.lower().split()) for item in public_tutor_fragments[-6:]}
            if normalized in recent:
                return False
            if reopen_after_tool and event_queue is not None:
                await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})
                next_beat = await _iteration_beat_runtime(
                    query=query,
                    context=context,
                    iteration=iteration,
                    tools_used=tools_used,
                    phase_label=phase_label or "Đối chiếu kết quả",
                )
                await _push(
                    {
                        "type": "thinking_start",
                        "content": next_beat.label,
                        "node": "tutor_agent",
                        "summary": next_beat.summary,
                        "details": {
                            "phase": next_beat.phase,
                            "tone_mode": getattr(next_beat, "tone_mode", ""),
                        },
                    }
                )
            public_tutor_fragments.append(public_text)
            emitted_public_text = public_text
            if streamed_native_tutor_public_text and public_text.startswith(streamed_native_tutor_public_text):
                emitted_public_text = public_text[len(streamed_native_tutor_public_text):]
            streamed_native_tutor_public_text = public_text
            streamed_native_tutor_reasoning_buffer = str(thinking_text)
            if emitted_public_text.strip():
                await _push_thinking_deltas_raw(emitted_public_text)
            return True

        async def _generate_post_tool_native_continuation(
            *,
            tool_name: str,
            tool_result_text: str | None,
            tool_call_args: dict[str, Any] | None = None,
        ) -> str | None:
            result_text = str(tool_result_text or "").strip()
            if not result_text or result_text.lower().startswith("error:"):
                return None

            cleaned_result = re.sub(
                r"\s*<!--\s*confidence:[\s\S]*?-->",
                "",
                result_text,
                flags=re.I,
            ).strip()
            tool_turn_label = "ket qua tra cuu"
            distilled_context = ""
            if tool_name in ("tool_knowledge_search", "tool_maritime_search"):
                cleaned_result = normalize_tutor_answer_shape(cleaned_result, query=query) or cleaned_result
                distilled_context = distill_post_tool_context(cleaned_result)
                tool_turn_label = "ket qua tra cuu"
            elif tool_name == "tool_generate_visual":
                distilled_context = distill_visual_tool_context(
                    cleaned_result,
                    tool_call_args=tool_call_args,
                )
                tool_turn_label = "visual vua duoc tao"
            else:
                return None

            if not distilled_context:
                return None
            fallback_continuation = _build_post_tool_fallback_continuation(
                tool_name=tool_name,
                distilled_context=distilled_context,
            )
            conversation_summary = str(context.get("conversation_summary") or "").strip()
            mood_hint = str(context.get("mood_hint") or "").strip()
            language_contract = build_response_language_instruction(response_language)
            identity_grounding_prompt = build_tutor_identity_grounding_prompt(
                context=context,
                logger_obj=logger,
            )
            living_stream_cues = build_tutor_living_stream_cues(context)
            continuation_prompt = (
                "Ban la Wiii.\n"
                f"Day la luot tiep noi visible inner monologue sau khi vua xu ly {tool_turn_label}.\n\n"
                f"{identity_grounding_prompt}\n\n"
                f"{living_stream_cues}\n\n"
                f"{language_contract}\n\n"
                "## THONG NHAT DANH TINH WIII\n"
                "- Khong co mot nhan vat rieng ten 'Wiii Tutor'. Day van la Wiii.\n"
                "- Day hoc chi la cong viec hien tai cua Wiii trong turn nay, khong phai mot nhan cach moi.\n"
                "- Giu cung mot soul, continuity, va chat song cua Wiii. Neu mot net rieng nhu Bong thoang qua, no phai tu nhien va tiet che.\n\n"
                "## WIII CONTINUATION MODE\n"
                "- Giu chat Wiii: am, co hon, co su hien dien, nhung khong san khau hoa va khong roleplay.\n"
                "- Nhip cua Wiii o day nam o cach go roi, chot moc nhan thuc, va giu liem mach cho luot dang dien ra.\n"
                "- KHONG ke thua huong dan tool hay huong dan viet cau tra loi tu prompt lon cua tutor.\n"
                "- KHONG coi day la mot bai giang mini hay mot ban nhap answer.\n\n"
                "## NHIEM VU DUY NHAT\n"
                f"- Day la visible inner monologue cua Wiii ngay sau khi vua xu ly {tool_turn_label}.\n"
                "- Du lieu dau vao ben duoi da la cac moc duoc rut gon, khong phai mot cau tra loi hoan chinh.\n"
                f"- BAT BUOC nghi va viet bang ngon ngu cua user cho luot nay: response_language={response_language}.\n"
                "- Ban KHONG duoc tra loi nguoi dung trong luot nay.\n"
                "- Hay viet 2-4 doan ngan hoac 4-8 cau lien mach nhu mot dong suy nghi dang tiep dien.\n"
                "- Chi bam vao 3 viec: dieu ket qua vua lam ro, cho de hieu nham con lai, va diem neo nen giu de giai thich tiep.\n"
                "- Neu day la visual, uu tien noi dieu hinh vua giup nhin ra, cho nao van de bi nhin sot, va nhiet do giai thich tiep theo nen dat o dau.\n"
                "- Neu ket qua vua co co loi chao, dong vien, mo bai, ket bai, hay giong day hoc user, xem do chi la lop vo ngoai cua ket qua va BO QUA.\n"
                "- Khong chep lai nguyen van ket qua tra cuu.\n"
                "- KHONG lap dan y cau tra loi.\n"
                "- KHONG viet ke hoach kieu 'dau tien / sau do / cuoi cung', 'greeting', 'closing', 'drafting content', hay 'let's see the plan'.\n"
                "- KHONG noi toi viec se chao user, se mo bai, se ket bai, se dua vi du, se nhac Rule 17, hay se viet the nao.\n"
                "- KHONG dat tieu de markdown tieng Anh kieu '**My Approach...**'. Neu can nhan nhip, dung tieng Viet tu nhien.\n"
                "- Khong nhac toi prompt, system, pipeline, json, ham, tool, routing, hay 'toi se goi tool'.\n"
                "- Nhip cua Wiii o day nam o cach go roi va chot moc nhan thuc, khong nam o man san khau hoa hay tu bieu dien su de thuong.\n"
                "- Neu dang co xu huong noi voi user bang 'ban', lui lai mot nhip va chuyen thanh doc thoai noi tam ve nguoi hoc, cho de nham, va diem neo can giu.\n"
                "- Neu ban khong the giu dung dang inner monologue, dung tra ve gi khac ngoai mot <thinking> block that su inward.\n"
                "- VOI BAI TOAN TINH TOAN: hay nghi buoc buoc, so lieu cu the, goi an ro rang, tinh toan ngay trong thinking. Dung chi nghi ve pedagogy — hay thuc su GIAI bai toan trong thinking.\n"
                "\n## VI DU NHANH\n"
                "Tot (bai toan):\n"
                "<thinking>\n"
                "Goi v = toc do ban dau (dam/gio). Quang duong AB = 240 dam.\n"
                "Phan 1/3 dau: 80 dam voi toc do v, mat t1 = 80/v gio.\n"
                "Phan 2/3 sau: 160 dam voi toc do (2/3)v, mat t2 = 160/(2v/3) = 240/v gio.\n"
                "Tong thoi gian thuc te: t1 + t2 = 80/v + 240/v = 320/v.\n"
                "Thoi gian du kien neu khong hong: t0 = 240/v.\n"
                "Tre 4 gio: 320/v - 240/v = 4 => 80/v = 4 => v = 20 dam/gio.\n"
                "Kiem tra: du kien 240/20=12h, thuc te 80/20+160/(40/3)=4+12=16h, tre 4h. Dung.\n"
                "</thinking>\n\n"
                "Tot (giai thich kien thuc):\n"
                "<thinking>\n"
                "Nguoi hoc de truot o cho nham giua vi tri tiep can va quyen uu tien. Minh nen khoa lai moc 'man phai' truoc, roi moi noi toi hanh dong tranh va. Chat Wiii o day nam o nhip go roi nhe nha, khong nam o man vo ve.\n"
                "</thinking>\n\n"
                "Khong tot:\n"
                "<thinking>\n"
                "Ban dang to mo ve Rule 15 sao? De minh giai thich cho ban nhe! Dau tien minh se chao ban, roi minh noi tung muc mot cho de hieu.\n"
                "</thinking>\n\n"
                "Khong tot:\n"
                "<thinking>\n"
                "Day la Quy tac 15. Tau nao thay tau kia o man phai thi phai nhuong. Rule nay rat quan trong va ban can nho ky.\n"
                "</thinking>\n\n"
                "- Tra ve DUY NHAT mot khong gian suy nghi trong <thinking>...</thinking>."
            )
            continuation_messages = [
                SystemMessage(content=continuation_prompt),
                HumanMessage(
                    content=(
                        f"Cau hoi cua nguoi dung:\n{query}\n\n"
                        f"Tom tat hoi thoai hien tai:\n{conversation_summary or '(khong co)'}\n\n"
                        f"Mood hint hien tai:\n{mood_hint or '(khong co)'}\n\n"
                        f"Cac tin hieu vua lo ra tu {tool_turn_label}:\n{distilled_context}\n\n"
                        "Hay tiep tuc suy nghi noi tam cua Wiii ngay sau khi vua chot duoc cac tin hieu tren."
                    )
                ),
            ]
            try:
                continuation_response, continuation_stream_text, _ = await collect_tutor_model_message(
                    self._llm,
                    continuation_messages,
                    logger=logger,
                )
            except Exception as exc:
                logger.debug("[TUTOR_AGENT] Post-tool continuation generation failed: %s", exc)
                return fallback_continuation

            if continuation_response is None:
                return fallback_continuation

            continuation_text, continuation_thinking = extract_thinking_from_response(
                getattr(continuation_response, "content", ""),
            )
            candidate = str(continuation_thinking or continuation_text or "").strip()
            if not candidate:
                logger.debug(
                    "[TUTOR_AGENT] Discarding post-tool continuation without native/<thinking> payload"
                )
                return fallback_continuation
            candidate = sanitize_public_tutor_thinking(candidate) or ""
            if not candidate:
                return fallback_continuation
            if len(candidate) < 40:
                return fallback_continuation
            if not _should_surface_native_tutor_thought(
                candidate,
                stage="post_tool_continuation",
            ):
                return fallback_continuation
            return candidate

        async def _iteration_beat_runtime(**kwargs):
            return await _iteration_beat(
                **kwargs,
                llm=self._llm,
                recent_fragments=list(public_tutor_fragments),
            )

        async def _tool_acknowledgment_runtime(**kwargs):
            return await _tool_acknowledgment(
                **kwargs,
                llm=self._llm,
                recent_fragments=list(public_tutor_fragments),
            )

        async def _finalize_tutor_message_payload(message_obj: Any) -> tuple[str, Optional[str]]:
            _raw_final_text, raw_final_thinking = extract_thinking_from_response(
                getattr(message_obj, "content", ""),
            )
            if raw_final_thinking and _should_surface_native_tutor_thought(
                raw_final_thinking,
                stage="final_native",
            ):
                await _capture_native_tutor_thinking(
                    raw_final_thinking,
                    stage="final_native",
                )
            resolved_response, resolved_thinking = self._extract_content_with_thinking(
                getattr(message_obj, "content", ""),
                query=query,
            )
            if not resolved_thinking:
                resolved_thinking = raw_final_thinking
            return resolved_response, resolved_thinking

        async def _recover_final_tutor_response(
            *,
            note_internal_gap: bool,
            primary_error: Exception | None = None,
        ) -> tuple[str, Optional[str]]:
            failover_provider = str(getattr(self._llm, "_wiii_provider_name", "") or "").strip().lower() or None
            if primary_error is not None:
                logger.warning(
                    "[TUTOR_AGENT] Attempting final synthesis failover rescue after primary error: %s",
                    primary_error,
                )

            try:
                rescue_msg, _ignored_text, _used_streaming = await collect_tutor_model_message_with_failover(
                    self._llm,
                    messages,
                    logger=logger,
                    tier="moderate",
                    provider=failover_provider,
                )
                if rescue_msg is not None:
                    rescue_response, rescue_thinking = await _finalize_tutor_message_payload(
                        rescue_msg,
                    )
                    if rescue_response and not looks_like_tutor_placeholder_answer(rescue_response):
                        return rescue_response, rescue_thinking
            except Exception as rescue_exc:
                logger.warning(
                    "[TUTOR_AGENT] Final synthesis failover rescue failed: %s",
                    rescue_exc,
                )

            recovered_response = recover_tutor_answer_from_messages(
                messages,
                query=query,
            )
            if recovered_response:
                logger.warning(
                    "[TUTOR_AGENT] Recovered tutor answer from tool observation during final rescue"
                )
                return recovered_response, None

            return build_tutor_rescue_response(
                query,
                note_internal_gap=note_internal_gap,
            ), None

        # Sprint 148: Track phase transitions for rate limiting and double-close prevention
        _phase_transition_count = 0
        _last_tool_was_progress = False

        # ReAct Loop
        for iteration in range(max_iterations):
            logger.info("[TUTOR_AGENT] ReAct iteration %d/%d", iteration + 1, max_iterations)
            _last_tool_was_progress = False  # Reset at start of each iteration
            break_outer_loop = False

            # THINK: use one model-collection path for both sync and stream so
            # transport does not change the answer semantics.
            if event_queue is not None:
                # Sprint 146b: Context-aware label
                _beat = await _iteration_beat_runtime(
                    query=query,
                    context=context,
                    iteration=iteration,
                    tools_used=tools_used,
                )
                # Emit thinking_start for this iteration
                await _push({
                    "type": "thinking_start",
                    "content": _beat.label,
                    "node": "tutor_agent",
                    "summary": _beat.summary,
                    "details": {
                        "phase": _beat.phase,
                        "tone_mode": getattr(_beat, "tone_mode", ""),
                    },
                })
                beat_fragments = list(getattr(_beat, "fragments", []) or [])
                if allow_secondary_model_thinking and beat_fragments:
                    used_secondary_public_reflection = True
                    await _push_public_tutor_fragments(beat_fragments)
            response, pre_tool_stream_text, _used_streaming = await collect_tutor_model_message(
                llm_with_tools,
                messages,
                logger=logger,
                on_stream_reasoning_delta=(
                    _push_live_native_tutor_reasoning if event_queue is not None else None
                ),
            )
            if response is None:
                from langchain_core.messages import AIMessage as _AIMsg
                response = _AIMsg(content="")

            _raw_turn_text, raw_turn_thinking = extract_thinking_from_response(
                getattr(response, "content", ""),
            )
            if raw_turn_thinking and _should_surface_native_tutor_thought(
                raw_turn_thinking,
                stage="pre_tool_native",
            ):
                await _capture_native_tutor_thinking(
                    raw_turn_thinking,
                    stage="pre_tool_native",
                )

            # Check if LLM wants to call tools
            if not response.tool_calls:
                # Sprint 146b: Close thinking block when no tool calls needed
                if event_queue is not None:
                    await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})
                # No tool calls = LLM is done, extract final response AND thinking
                final_response, llm_thinking = self._extract_content_with_thinking(
                    response.content,
                    query=query,
                )
                if not llm_thinking:
                    llm_thinking = raw_turn_thinking
                logger.info("[TUTOR_AGENT] No more tool calls, generating final response")
                break

            if event_queue is not None and pre_tool_stream_text.strip():
                if raw_turn_thinking:
                    logger.debug(
                        "[TUTOR_AGENT] Keeping native tutor thought as authority over pre-tool text (%d chars suppressed)",
                        len(pre_tool_stream_text),
                    )
                elif not allow_secondary_model_thinking:
                    logger.debug(
                        "[TUTOR_AGENT] Suppressing pre-tool stream text because secondary model thinking is disabled (%d chars)",
                        len(pre_tool_stream_text),
                    )
                else:
                    if _should_surface_native_tutor_thought(
                        pre_tool_stream_text,
                        stage="pre_tool_stream",
                    ):
                        public_pre_tool = await _remember_public_tutor_thinking(pre_tool_stream_text)
                    else:
                        public_pre_tool = None
                    if public_pre_tool:
                        await _push_thinking_deltas_raw(public_pre_tool)
                    else:
                        logger.debug(
                            "[TUTOR_AGENT] Pre-tool text produced no visible raw thinking (%d chars)",
                            len(pre_tool_stream_text),
                        )

            # ACT: Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"call_{iteration}")

                # Sprint 69: Push tool_call event
                await _push({
                    "type": "tool_call",
                    "content": {"name": tool_name, "args": tool_args, "id": tool_id},
                    "node": "tutor_agent",
                })

                logger.info("[TUTOR_AGENT] Calling tool: %s with args: %s", tool_name, tool_args)
                
                async def _push_secondary_tutor_thinking(_text: str) -> None:
                    return None

                dispatch_result = await dispatch_tutor_tool_call(
                    tool_call=tool_call,
                    query=query,
                    context=context,
                    iteration=iteration,
                    tools_used=tools_used,
                    tools=tools,
                    messages=messages,
                    runtime_context_base=runtime_context_base,
                    push=_push,
                    push_thinking_deltas=(
                        _push_public_tutor_thinking
                        if allow_secondary_model_thinking
                        else _push_secondary_tutor_thinking
                    ),
                    iteration_beat_fn=_iteration_beat_runtime,
                    tool_acknowledgment_fn=_tool_acknowledgment_runtime,
                    get_tool_by_name_fn=get_tool_by_name,
                    invoke_tool_with_runtime_fn=invoke_tool_with_runtime,
                    get_last_confidence_fn=get_last_confidence,
                    knowledge_tool=tool_knowledge_search,
                    calculator_tool=tool_calculator,
                    datetime_tool=tool_current_datetime,
                    web_search_tool=tool_web_search,
                    max_iterations=max_iterations,
                    max_phase_transitions=_MAX_PHASE_TRANSITIONS,
                    phase_transition_count=_phase_transition_count,
                    logger_obj=logger,
                )
                _phase_transition_count = dispatch_result.phase_transition_count
                _last_tool_was_progress = dispatch_result.last_tool_was_progress
                last_tool_name_seen = str(tool_name or "")
                last_tool_result_text = getattr(dispatch_result, "tool_result_text", None)
                last_tool_args = getattr(dispatch_result, "tool_args", None)
                if tool_name in ("tool_knowledge_search", "tool_maritime_search"):
                    rag_tool_thought = get_last_native_thinking()
                    if event_queue is not None:
                        post_tool_emitted = await _capture_native_tutor_thinking(
                            rag_tool_thought,
                            reopen_after_tool=True,
                            phase_label="Đối chiếu kết quả",
                            stage="rag_tool_native",
                        )
                        if allow_secondary_model_thinking and not post_tool_emitted:
                            continuation_thought = await _generate_post_tool_native_continuation(
                                tool_name=tool_name,
                                tool_result_text=getattr(dispatch_result, "tool_result_text", None),
                                tool_call_args=getattr(dispatch_result, "tool_args", None),
                            )
                            if continuation_thought:
                                used_secondary_public_reflection = True
                                await _capture_native_tutor_thinking(
                                    continuation_thought,
                                    reopen_after_tool=True,
                                    phase_label="Đối chiếu kết quả",
                                    stage="post_tool_continuation",
                                )
                    else:
                        await _capture_native_tutor_thinking(
                            rag_tool_thought,
                            stage="rag_tool_native",
                        )
                elif (
                    allow_secondary_model_thinking
                    and tool_name == "tool_generate_visual"
                    and event_queue is not None
                ):
                    continuation_thought = await _generate_post_tool_native_continuation(
                        tool_name=tool_name,
                        tool_result_text=getattr(dispatch_result, "tool_result_text", None),
                        tool_call_args=getattr(dispatch_result, "tool_args", None),
                    )
                    if continuation_thought:
                        used_secondary_public_reflection = True
                        await _capture_native_tutor_thinking(
                            continuation_thought,
                            reopen_after_tool=True,
                            phase_label="Nhìn lại visual",
                            stage="post_visual_continuation",
                        )
                if dispatch_result.should_break_loop:
                    break_outer_loop = True
                    break
            # Sprint 146b: Close thinking block after all tool executions
            # Sprint 148: Don't double-close if tool_report_progress already closed the block
            if event_queue is not None and not _last_tool_was_progress:
                await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

            if break_outer_loop:
                logger.info("[TUTOR_AGENT] Breaking outer loop after tool-directed final synthesis handoff")
                break

            # SOTA 2025 Phase 2: Check if we should break outer loop
            confidence, is_complete = get_last_confidence()
            if is_complete and confidence >= 0.70:  # PHASE 2: Match inner loop threshold
                logger.info("[TUTOR_AGENT] Breaking outer loop - MEDIUM+ confidence achieved")
                break
        
        # If we exhausted iterations without final response, generate one
        if not final_response:
            # Sprint 148: Close any open thinking block from tool_report_progress
            if event_queue is not None and _last_tool_was_progress:
                await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})
            note_internal_gap = bool(last_tool_result_text) and is_no_internal_match_observation(
                str(last_tool_result_text or "")
            )
            try:
                final_msg, _ignored_text, _used_streaming = await collect_tutor_model_message(
                    self._llm,
                    messages,
                    logger=logger,
                    on_stream_reasoning_delta=(
                        _push_live_native_tutor_reasoning if event_queue is not None else None
                    ),
                )
                if final_msg is not None:
                    final_response, llm_thinking = await _finalize_tutor_message_payload(
                        final_msg,
                    )
                    if looks_like_tutor_placeholder_answer(final_response):
                        final_response, recovered_thinking = await _recover_final_tutor_response(
                            note_internal_gap=note_internal_gap,
                        )
                        if recovered_thinking and not llm_thinking:
                            llm_thinking = recovered_thinking
                else:
                    final_response, llm_thinking = await _recover_final_tutor_response(
                        note_internal_gap=note_internal_gap,
                    )
            except Exception as e:
                logger.error("[TUTOR_AGENT] Final generation error: %s", e)
                final_response, llm_thinking = await _recover_final_tutor_response(
                    note_internal_gap=note_internal_gap,
                    primary_error=e,
                )

        if tools_used and looks_like_tutor_placeholder_answer(final_response):
            recovered_response = recover_tutor_answer_from_messages(
                messages,
                query=query,
            )
            if recovered_response:
                logger.warning(
                    "[TUTOR_AGENT] Recovered tutor answer from tool observation after placeholder final generation"
                )
                final_response = recovered_response
            else:
                final_response = build_tutor_rescue_response(
                    query,
                    note_internal_gap=bool(last_tool_result_text)
                    and is_no_internal_match_observation(str(last_tool_result_text or "")),
                )

        final_response = apply_quiz_socratic_guardrail(
            final_response,
            context=context,
        )

        # Get sources from tool calls
        sources = get_last_retrieved_sources()

        # CHá»ˆ THá»Š Sá» 29 v9: Get RAG thinking from tool (Option B+)
        rag_thinking = get_last_native_thinking()
        if not _should_surface_native_tutor_thought(
            rag_thinking,
            stage="rag_tool_native",
        ):
            rag_thinking = None
        if not _should_surface_native_tutor_thought(
            llm_thinking,
            stage="final_native",
        ):
            llm_thinking = None

        public_tutor_thinking = await _align_public_tutor_thinking(
            "\n\n".join(public_tutor_fragments).strip() or None
        )
        public_rag_thinking = await _align_public_tutor_thinking(rag_thinking)
        public_llm_thinking = await _align_public_tutor_thinking(llm_thinking)

        last_tool_name = ""
        if tools_used:
            last_tool_name = str((tools_used[-1] or {}).get("name", "") or "")

        # Public thinking authority for sync metadata:
        # 1) native thought fragments already surfaced during the real tutor loop
        # 2) sanitized raw RAG/LLM native thinking as fallback only
        # 3) no authored tutor prose fallback on the live path
        combined_thinking = None
        if public_tutor_thinking:
            combined_thinking = public_tutor_thinking
        elif public_rag_thinking and public_llm_thinking:
            if public_rag_thinking == public_llm_thinking:
                combined_thinking = public_rag_thinking
            else:
                combined_thinking = f"{public_rag_thinking}\n\n{public_llm_thinking}"
        elif public_rag_thinking:
            combined_thinking = public_rag_thinking
        elif public_llm_thinking:
            combined_thinking = public_llm_thinking

        if combined_thinking:
            combined_thinking = await _align_public_tutor_thinking(combined_thinking) or combined_thinking

        if (
            allow_secondary_model_thinking
            and
            not combined_thinking
            and last_tool_name_seen in ("tool_knowledge_search", "tool_maritime_search", "tool_generate_visual")
            and last_tool_result_text
        ):
            fallback_continuation = await _generate_post_tool_native_continuation(
                tool_name=last_tool_name_seen,
                tool_result_text=last_tool_result_text,
                tool_call_args=last_tool_args,
            )
            if fallback_continuation:
                used_secondary_public_reflection = True
                combined_thinking = await _align_public_tutor_thinking(fallback_continuation)

        if combined_thinking:
            logger.info(
                "[TUTOR_AGENT] Combined thinking: %d chars (rag=%s, llm=%s)",
                len(combined_thinking),
                bool(rag_thinking),
                bool(llm_thinking),
            )
        if state is not None:
            if used_secondary_public_reflection:
                state["thinking_provenance"] = "public_reflection"
            elif combined_thinking and (public_tutor_thinking or public_rag_thinking or public_llm_thinking):
                state["thinking_provenance"] = "provider_native"
            else:
                state.pop("thinking_provenance", None)

        return final_response, sources, tools_used, combined_thinking, _answer_streamed_via_bus

    def _fallback_response(self, query: str) -> str:
        """Fallback when LLM unavailable."""
        return build_tutor_fallback_response(query)

    def _extract_content_with_thinking(
        self,
        content,
        *,
        query: str = "",
    ) -> tuple[str, Optional[str]]:
        """Delegate response/thinking extraction to the shared tutor helper."""
        return extract_tutor_content_with_thinking(
            content,
            logger=logger,
            extractor=extract_thinking_from_response,
            query=query,
        )
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None and self._llm_with_tools is not None


# Singleton
_tutor_node: Optional[TutorAgentNode] = None

def get_tutor_agent_node() -> TutorAgentNode:
    """Get or create TutorAgentNode singleton."""
    global _tutor_node
    if _tutor_node is None:
        _tutor_node = TutorAgentNode()
    return _tutor_node

