"""LLM-backed visible reasoning narrator for Wiii."""

from __future__ import annotations

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from app.engine.character.character_card import build_wiii_runtime_prompt
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.reasoning.skill_loader import ReasoningSkill, get_reasoning_skill_loader
from app.engine.skills.skill_handbook import get_skill_handbook

logger = logging.getLogger(__name__)

_NODE_LLM_MAP = {
    "supervisor": "supervisor",
    "direct": "direct",
    # Narrator uses default model (flash-lite) for code_studio, NOT the Pro
    # model override. Pro is for code generation quality; narrator just needs
    # to produce short thinking text which flash-lite handles perfectly.
    "code_studio_agent": "direct",
    "code_studio": "direct",
    "rag_agent": "rag_agent",
    "rag": "rag_agent",
    "tutor_agent": "tutor_agent",
    "tutor": "tutor_agent",
    "memory_agent": "memory",
    "memory": "memory",
    "product_search_agent": "product_search",
    "search": "product_search",
}

_TOOL_NAME_RE = re.compile(r"\btool_[a-zA-Z0-9_]+\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_RAW_TRACE_PATTERNS = (
    "pipeline",
    "router",
    "reasoning_trace",
    "tool_call_id",
    "request_id",
    "session_id",
    "organization_id",
    "langgraph",
    "json",
    "structured output",
)


class ReasoningRenderRequest(BaseModel):
    """Semantic input for visible reasoning generation."""

    node: str
    phase: str
    intent: str = ""
    cue: str = ""
    user_goal: str = ""
    conversation_context: str = ""
    memory_context: str = ""
    capability_context: str = ""
    tool_context: str = ""
    confidence: float = 0.0
    evidence_strength: float = 0.0
    next_action: str = ""
    visibility_mode: str = "rich"
    organization_id: Optional[str] = None
    user_id: str = "__global__"
    personality_mode: Optional[str] = None
    mood_hint: Optional[str] = None
    observations: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    provider: Optional[str] = None  # Per-request provider override


class ReasoningRenderResult(BaseModel):
    """Narrated visible reasoning result."""

    label: str
    summary: str
    action_text: str = ""
    delta_chunks: list[str] = Field(default_factory=list)
    phase: str
    style_tags: list[str] = Field(default_factory=list)


class _NarratedReasoningSchema(BaseModel):
    """Structured output schema for the narrator LLM."""

    label: str = Field(description="Ngắn gọn, 3-8 từ, mô tả nhịp suy luận hiện tại.")
    summary: str = Field(
        description=(
            "Nội tâm có chủ đích mà người dùng được phép thấy. "
            "Độ dài do Wiii tự quyết: greeting/simple có thể 1-2 câu, "
            "chart/article/analysis nên 3-6 câu với domain terms cụ thể và judgment calls. "
            "Mỗi câu phải mang thông tin mới — nếu bỏ câu đi mà không mất gì thì câu đó thừa."
        )
    )
    action_text: str = Field(
        default="",
        description=(
            "Câu cầu nối mềm khi Wiii chuẩn bị đổi sang hành động tiếp theo. "
            "Phải cụ thể như preamble: nói RÕ sẽ làm gì, dùng nguồn nào, tìm thông tin gì. "
            "VD: 'Tra eco-speed từ nguồn COLREGs và IMO performance standards'. "
            "KHÔNG generic kiểu 'Đang tìm kiếm thông tin'."
        ),
    )
    delta_chunks: list[str] = Field(
        default_factory=list,
        description=(
            "Các đoạn nối tiếp nhau như suy nghĩ đang chảy — Wiii tự quyết số lượng. "
            "Mỗi đoạn đẩy suy nghĩ tiến thêm một ý mới. "
            "Mỗi đoạn phải chứa ít nhất 1 domain term cụ thể hoặc 1 judgment call."
        ),
    )
    style_tags: list[str] = Field(
        default_factory=list,
        description="Các nhãn phong cách ngắn như reflective, grounded, warm, decisive.",
    )


def _sanitize_text(text: str) -> str:
    sanitized = _TOOL_NAME_RE.sub("một công cụ phù hợp", text or "")
    sanitized = _UUID_RE.sub("[id nội bộ]", sanitized)
    sanitized = sanitized.replace("```", "")
    return sanitized.strip()


def _sanitize_chunks(chunks: list[str]) -> list[str]:
    result: list[str] = []
    for chunk in chunks:
        cleaned = _sanitize_text(chunk)
        if not cleaned:
            continue
        if any(token in cleaned.lower() for token in _RAW_TRACE_PATTERNS):
            continue
        result.append(cleaned)
    return result


def _contains_forbidden_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(phrase.lower() in lowered for phrase in phrases if phrase)


def _compact_text(text: str, limit: int = 500) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def clamp_sentence(text: str, limit: int) -> str:
    clean = " ".join((text or "").split()).strip()
    if len(clean) <= limit:
        return clean
    sliced = clean[: max(1, limit - 3)].rstrip()
    last_space = sliced.rfind(" ")
    if last_space > int(limit * 0.6):
        sliced = sliced[:last_space]
    return sliced.rstrip(" ,;:") + "..."


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _normalize_label(text: str, fallback: str) -> str:
    cleaned = _sanitize_text(text).replace("\n", " ").strip(" .,:;!-")
    cleaned = re.split(r"[.!?\n]", cleaned, maxsplit=1)[0].strip(" .,:;!-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return fallback
    if len(cleaned) > 48 or len(cleaned.split()) > 7:
        return fallback
    if any(token in cleaned for token in (".", "?", "!", ":")):
        return fallback
    return cleaned


def _normalize_summary(text: str, fallback: str = "") -> str:
    """Sprint 234: Removed hardcoded 140-char clamp.
    Let Wiii decide summary length — SOTA 2026 (Claude adaptive, DeepSeek full CoT).
    Only sanitize and use fallback when LLM returns empty."""
    cleaned = _sanitize_text(text)
    if not cleaned:
        cleaned = _sanitize_text(fallback)
    if not cleaned:
        return ""
    return cleaned


def _normalize_action_text(text: str, fallback: str = "") -> str:
    """Sprint 234: Removed hardcoded 150-char clamp.
    Action text should be specific (GPT-5.4 preamble pattern) — let LLM decide length."""
    cleaned = _sanitize_text(text)
    if not cleaned:
        cleaned = _sanitize_text(fallback)
    return cleaned


def build_tool_context_summary(tool_names: list[str] | None = None, result: object = None) -> str:
    """Turn internal tool names/results into narrator-safe tool context."""
    names = [name for name in (tool_names or []) if name]
    parts: list[str] = []

    for name in names[:4]:
        entry = get_skill_handbook().get_tool_entry(name)
        if entry:
            parts.append(f"{entry.tool_name}: {entry.description}")
        else:
            parts.append(name.replace("tool_", "").replace("_", " "))

    if result is not None:
        result_text = _compact_text(str(result), 280)
        if result_text:
            parts.append(f"kết quả vừa nhận: {result_text}")

    return "\n".join(parts)


def _fallback_delta_chunks(summary: str) -> list[str]:
    """Sprint 234: No artificial limits — Wiii decides depth.
    Split by natural boundaries only: paragraphs first, then sentences.
    SOTA 2026: Claude adaptive, DeepSeek full CoT — zero truncation."""
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", summary) if part.strip()]
    if len(paragraphs) >= 2:
        return paragraphs
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", summary) if part.strip()]
    if len(sentences) > 1:
        # Group 2-3 sentences per chunk for natural reading rhythm
        chunks: list[str] = []
        bucket = ""
        for sentence in sentences:
            bucket = f"{bucket} {sentence}".strip()
            # Natural break: 2-3 sentences per chunk feels like a thought beat
            if bucket.count(".") + bucket.count("!") + bucket.count("?") >= 2:
                chunks.append(bucket)
                bucket = ""
        if bucket:
            chunks.append(bucket)
        return chunks
    return [summary] if summary else []


class ReasoningNarrator:
    """Generate visible reasoning from structured runtime state."""

    def __init__(self):
        self._skill_loader = get_reasoning_skill_loader()

    def _resolve_node_skill(self, node: str) -> Optional[ReasoningSkill]:
        return self._skill_loader.get_node_skill(node)

    def _build_system_prompt(
        self,
        request: ReasoningRenderRequest,
        node_skill: Optional[ReasoningSkill],
    ) -> str:
        persona_skills = self._skill_loader.get_persona_skills()
        tool_skill = self._skill_loader.get_tool_skill()
        sections = [
            build_wiii_runtime_prompt(
                user_id=request.user_id,
                organization_id=request.organization_id,
                mood_hint=request.mood_hint,
                personality_mode=request.personality_mode,
            ),
            "## Soul-First Rule (CRITICAL)",
            "Thinking và response phải là CÙNG MỘT GIỌNG, CÙNG MỘT LINH HỒN.",
            "Wiii không 'suy nghĩ bằng giọng kỹ thuật' rồi 'trả lời bằng giọng ấm'.",
            "Nếu response của Wiii ấm và gần gũi, thinking cũng phải ấm và gần gũi.",
            "Nếu response dùng 'mình', thinking cũng dùng 'mình'.",
            "Thinking = độc thoại nội tâm của CHÍNH Wiii, không phải báo cáo của hệ thống.",
            "",
            "Bạn là lớp VISIBLE REASONING của Wiii.",
            "Bạn không tiết lộ hidden chain-of-thought. Bạn viết nội tâm có chủ đích mà người dùng được phép thấy.",
            "",
            "## Adaptive Depth (SOTA 2026 — Claude adaptive, DeepSeek full CoT)",
            "Wiii TỰ QUYẾT ĐỘ DÀI thinking phù hợp với câu hỏi — không có hardcoded limit.",
            "- Greeting/simple: 1-2 câu ấm, có hồn, vẫn cho thấy Wiii đang sống.",
            "- RAG/web search: 2-4 câu có insight và domain terms cụ thể.",
            "- Chart/article/analysis: 3-6 câu có trade-offs, specific data, và design decisions.",
            "- Complex simulation/multi-source: 4-6 câu có design choices, tech trade-offs, pedagogical reasoning.",
            "",
            "## Deletion Test",
            "Mỗi câu phải pass deletion test: bỏ câu đi mà response không mất thông tin = câu đó THỪA.",
            "BAD: 'Việc này cần sự chính xác để có cái nhìn tốt nhất' (đúng cho mọi bài toán → vô nghĩa).",
            "GOOD: 'Mình sẽ tổng hợp từ các nguồn hàng hải uy tín' (nói rõ nguồn nào → có thông tin mới).",
            "",
            "## Anti-Repetition (tránh lặp giữa thinking / status / action_text)",
            "- thinking KHÔNG lặp verb+object với status event (status: 'Tra cứu COLREGs' → thinking: insight về COLREGs, KHÔNG 'Mình đang tra cứu COLREGs').",
            "- thinking KHÔNG echo nguyên câu hỏi user — câu mở phải là INSIGHT hoặc REFRAME.",
            "- action_text KHÔNG lặp nội dung thinking — action_text là preamble CỤ THỂ (nguồn nào, tìm gì).",
            "",
            "## Preamble Pattern (SOTA GPT-5.4)",
            "action_text = brief intent explanation TRƯỚC tool call, phải cụ thể:",
            "GOOD: 'Tra eco-speed từ nguồn COLREGs và IMO performance standards'",
            "BAD: 'Đang tìm kiếm thông tin...'",
            "",
            "## Core Identity",
            "Không nêu tool id, request id, session id, JSON, schema, trace nội bộ, hoặc tên hàm kỹ thuật.",
            "Giữ cùng một linh hồn Wiii với câu trả lời cuối: ấm, có trí tuệ, có chất sống, không vô cảm.",
        ]

        # Soul-first: persona SKILLs content is already encoded in character card
        # + soul-first rule above. Only inject avoid_phrases guardrails to save tokens.
        for skill in persona_skills:
            if skill.avoid_phrases:
                sections.append(
                    "## Persona Runtime Guardrails\n"
                    + "\n".join(f"- Tránh cụm: {phrase}" for phrase in skill.avoid_phrases)
                )

        if node_skill:
            sections.append(f"## Subagent Skill: {node_skill.name}\n{node_skill.content}")
            runtime_notes: list[str] = []
            phase_focus = node_skill.phase_focus.get(request.phase, "")
            if phase_focus:
                runtime_notes.append(f"- Tâm điểm của phase này: {phase_focus}")
            delta_guidance = node_skill.delta_guidance.get(request.phase, "")
            if delta_guidance:
                runtime_notes.append(f"- Nhịp delta nên đi theo hướng: {delta_guidance}")
            if node_skill.action_style:
                runtime_notes.append(f"- Khi cần action_text: {node_skill.action_style}")
            if node_skill.avoid_phrases:
                runtime_notes.extend(
                    f"- Tuyệt đối tránh cụm: {phrase}" for phrase in node_skill.avoid_phrases
                )
            # Sprint 234: Anti-repetition rules from SKILL frontmatter
            if node_skill.anti_repetition:
                must_not = node_skill.anti_repetition.get("thinking_must_not_contain", [])
                must_have = node_skill.anti_repetition.get("thinking_must_contain", [])
                if must_not:
                    runtime_notes.append("- ANTI-REPETITION — thinking KHÔNG ĐƯỢC chứa:")
                    runtime_notes.extend(f"  + {rule}" for rule in must_not)
                if must_have:
                    runtime_notes.append("- THINKING PHẢI CHỨA:")
                    runtime_notes.extend(f"  + {rule}" for rule in must_have)
            if runtime_notes:
                sections.append("## Subagent Runtime Cues\n" + "\n".join(runtime_notes))

        if request.tool_context and tool_skill:
            sections.append(f"## Tool Governance Skill\n{tool_skill.content}")

        return "\n\n".join(section for section in sections if section.strip())

    def _build_user_prompt(
        self,
        request: ReasoningRenderRequest,
        node_skill: Optional[ReasoningSkill],
    ) -> str:
        fallback_label = ""
        fallback_summary = ""
        fallback_action = ""
        if node_skill:
            fallback_label = node_skill.phase_labels.get(request.phase, "")
            phase_focus = node_skill.phase_focus.get(request.phase, "")
            delta_guidance = node_skill.delta_guidance.get(request.phase, "")
            fallback_summary = node_skill.fallback_summaries.get(request.phase, "")
            fallback_action = node_skill.fallback_actions.get(request.phase, "")
            avoid_phrases = ", ".join(node_skill.avoid_phrases)
        else:
            phase_focus = ""
            delta_guidance = ""
            avoid_phrases = ""

        observations = "\n".join(f"- {item}" for item in request.observations if item)
        style_tags = ", ".join(request.style_tags)

        return (
            "Hãy tạo một nhịp visible reasoning cho Wiii dưới dạng JSON theo schema đã khai báo.\n\n"
            f"node={request.node}\n"
            f"phase={request.phase}\n"
            f"intent={request.intent or 'unknown'}\n"
            f"cue={request.cue or 'general'}\n"
            f"visibility_mode={request.visibility_mode}\n"
            f"user_goal={_compact_text(request.user_goal, 420)}\n"
            f"conversation_context={_compact_text(request.conversation_context, 600)}\n"
            f"memory_context={_compact_text(request.memory_context, 450)}\n"
            f"capability_context={_compact_text(request.capability_context, 450)}\n"
            f"tool_context={_compact_text(request.tool_context, 450)}\n"
            f"next_action={_compact_text(request.next_action, 220)}\n"
            f"confidence={request.confidence:.2f}\n"
            f"evidence_strength={request.evidence_strength:.2f}\n"
            f"style_tags={style_tags}\n"
            f"observations=\n{observations or '- không có'}\n\n"
            "Yêu cầu đầu ra:\n"
            "- label ngắn, giàu ngữ nghĩa (3-8 từ)\n"
            "- summary: Wiii TỰ QUYẾT độ dài phù hợp với độ phức tạp của câu hỏi:\n"
            "  + greeting/simple: 1-2 câu ngắn gọn\n"
            "  + RAG lookup/web search: 2-4 câu có insight và judgment\n"
            "  + chart/article/analysis: 3-6 câu có domain terms cụ thể, trade-offs, và decisions\n"
            "- DELETION TEST: mỗi câu phải mang thông tin mới — bỏ đi mà không mất gì = thừa\n"
            "- ANTI-REPETITION: thinking KHÔNG lặp nội dung của status event hay action_text\n"
            "  + status nói 'Tra cứu X' → thinking phải nói INSIGHT về X, không nhắc lại 'đang tra cứu'\n"
            "- delta_chunks phải nối thành nhịp suy nghĩ đang chảy (Wiii tự quyết số đoạn)\n"
            "- mỗi delta tiến thêm một ý: INSIGHT → JUDGMENT → DECISION\n"
            "- nếu hợp ngữ cảnh, cho phép một nhịp tự so lại hoặc chậm lại trước khi chốt\n"
            "- action_text: preamble CỤ THỂ trước tool call (SOTA GPT-5.4 pattern)\n"
            "  + GOOD: 'Tra eco-speed từ nguồn COLREGs và IMO performance standards'\n"
            "  + BAD: 'Đang tìm kiếm thông tin...'\n"
            "- action_text chỉ có khi thật sự chuẩn bị chuyển bước\n"
            "- không nhắc 'tôi không thể tiết lộ suy nghĩ'\n"
            "- không để lộ trace nội bộ, tên tool kỹ thuật, hay chi tiết hệ thống\n"
            "- tiếng Việt tự nhiên\n\n"
            f"Phase focus từ skill: {phase_focus or '(không có)'}\n"
            f"Delta guidance từ skill: {delta_guidance or '(không có)'}\n"
            f"Action style từ skill: {node_skill.action_style if node_skill else '(không có)'}\n"
            f"Cụm cần tránh từ skill: {avoid_phrases or '(không có)'}\n"
            f"Fallback label từ skill: {fallback_label or '(không có)'}\n"
            f"Fallback summary từ skill: {fallback_summary or '(không có)'}\n"
            f"Fallback action từ skill: {fallback_action or '(không có)'}"
        )

    def _fallback(
        self,
        request: ReasoningRenderRequest,
        node_skill: Optional[ReasoningSkill],
    ) -> ReasoningRenderResult:
        label = request.phase.replace("_", " ").strip().title()
        summary = ""
        action_text = ""
        style_tags = list(request.style_tags)

        if node_skill:
            label = node_skill.phase_labels.get(request.phase, label)
            summary = node_skill.fallback_summaries.get(request.phase, "")
            action_text = node_skill.fallback_actions.get(request.phase, "")
            style_tags = [*style_tags, *node_skill.style_tags]

        if not summary:
            summary = _compact_text(
                " ".join(
                    part
                    for part in (
                        request.user_goal,
                        request.conversation_context,
                        request.next_action,
                    )
                    if part
                ),
                limit=420,
            )
        if not action_text and request.next_action:
            action_text = _compact_text(request.next_action, 180)

        summary = _normalize_summary(summary)
        action_text = _normalize_action_text(action_text)
        return ReasoningRenderResult(
            label=_normalize_label(label, "Suy nghi tiep"),
            summary=summary,
            action_text=action_text,
            delta_chunks=_fallback_delta_chunks(summary),
            phase=request.phase,
            style_tags=list(dict.fromkeys(style_tags)),
        )

    async def render(self, request: ReasoningRenderRequest) -> ReasoningRenderResult:
        node_skill = self._resolve_node_skill(request.node)
        llm_node = _NODE_LLM_MAP.get(request.node, "direct")

        try:
            llm = AgentConfigRegistry.get_llm(
                llm_node,
                effort_override=request.visibility_mode if request.visibility_mode in {"low", "medium", "high", "max"} else None,
                provider_override=request.provider,
            )
        except Exception as exc:
            logger.warning("[REASONING_NARRATOR] LLM unavailable for %s: %s", llm_node, exc)
            return self._fallback(request, node_skill)

        try:
            structured_llm = llm.with_structured_output(_NarratedReasoningSchema)
            from langchain_core.messages import HumanMessage, SystemMessage

            result = await structured_llm.ainvoke(
                [
                    SystemMessage(content=self._build_system_prompt(request, node_skill)),
                    HumanMessage(content=self._build_user_prompt(request, node_skill)),
                ]
            )
            if result is None:
                raise ValueError("narrator returned None")
            fallback_result = self._fallback(request, node_skill)
            delta_chunks = _sanitize_chunks(list(result.delta_chunks or []))
            summary = _normalize_summary(result.summary, fallback_result.summary)
            action_text = _normalize_action_text(result.action_text, fallback_result.action_text)
            if not delta_chunks:
                delta_chunks = _fallback_delta_chunks(summary)
            if any(token in summary.lower() for token in _RAW_TRACE_PATTERNS):
                raise ValueError("narrator returned raw trace language")
            forbidden_phrases = tuple(
                phrase
                for skill in [*self._skill_loader.get_persona_skills(), node_skill]
                if skill
                for phrase in skill.avoid_phrases
            )
            if _contains_forbidden_phrase(summary, forbidden_phrases):
                raise ValueError("narrator used forbidden summary phrase")
            if _contains_forbidden_phrase(action_text, forbidden_phrases):
                raise ValueError("narrator used forbidden action phrase")
            if any(_contains_forbidden_phrase(chunk, forbidden_phrases) for chunk in delta_chunks):
                raise ValueError("narrator used forbidden delta phrase")
            return ReasoningRenderResult(
                label=_normalize_label(result.label, fallback_result.label),
                summary=summary,
                action_text=action_text,
                delta_chunks=delta_chunks,
                phase=request.phase,
                style_tags=list(dict.fromkeys([*request.style_tags, *(result.style_tags or [])])),
            )
        except Exception as exc:
            logger.warning(
                "[REASONING_NARRATOR] Falling back for node=%s phase=%s: %s",
                request.node,
                request.phase,
                exc,
            )
            return self._fallback(request, node_skill)


_NARRATOR: Optional[ReasoningNarrator] = None


def get_reasoning_narrator() -> ReasoningNarrator:
    """Return the shared reasoning narrator."""
    global _NARRATOR
    if _NARRATOR is None:
        _NARRATOR = ReasoningNarrator()
    return _NARRATOR
