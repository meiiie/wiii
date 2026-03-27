"""LLM-backed visible reasoning narrator for Wiii."""

from __future__ import annotations

import logging
import re
import unicodedata
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

_EMOTIONAL_KEYWORDS = (
    "buon",
    "met",
    "chan",
    "co don",
    "that vong",
    "tuyet vong",
    "ap luc",
    "stress",
    "so",
    "lo",
    "khoc",
    "toi te",
    "roi",
)
_IDENTITY_KEYWORDS = (
    "ban la ai",
    "wiii la ai",
    "ten gi",
    "ten cua ban",
    "cuoc song the nao",
    "song the nao",
    "ban ten gi",
)
_VISUAL_KEYWORDS = (
    "visual",
    "bieu do",
    "thong ke",
    "chart",
    "infographic",
    "so sanh",
)
_SIMULATION_KEYWORDS = (
    "mo phong",
    "3d",
    "canvas",
    "scene",
    "dong chay",
    "chuyen dong",
)
_KNOWLEDGE_KEYWORDS = (
    "giai thich",
    "quy tac",
    "rule ",
    "colregs",
    "solas",
    "marpol",
    "tai sao",
    "la gi",
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

    label: str = Field(description="Brief label, 3-8 words, describing the current reasoning beat.")
    summary: str = Field(
        description=(
            "User-visible inner thinking. Length self-determined by complexity. "
            "Each sentence must add new information — if removing it loses nothing, it is redundant."
        )
    )
    action_text: str = Field(
        default="",
        description=(
            "Soft transition before the next action. Must be specific: "
            "state WHAT will be done and WHICH sources. Never generic."
        ),
    )
    delta_chunks: list[str] = Field(
        default_factory=list,
        description=(
            "Consecutive thought segments like flowing reasoning. "
            "Each segment advances one new idea with specific domain terms."
        ),
    )
    style_tags: list[str] = Field(
        default_factory=list,
        description="Short style labels like reflective, grounded, warm, decisive.",
    )


def _sanitize_text(text: str) -> str:
    sanitized = _TOOL_NAME_RE.sub("", text or "")
    sanitized = _UUID_RE.sub("", sanitized)
    sanitized = sanitized.replace("```", "")
    sanitized = re.sub(r"<!--.*?-->", "", sanitized, flags=re.DOTALL)
    return sanitized.strip()


def sanitize_visible_reasoning_text(text: str, user_goal: str = "") -> str:
    """Public API: sanitize text for visible reasoning display."""
    return _sanitize_text(text)


def sanitize_visible_reasoning_chunks(chunks: list[str], user_goal: str = "") -> list[str]:
    """Public API: sanitize chunk list for visible reasoning display."""
    return _sanitize_chunks(chunks)


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


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = stripped.lower()
    lowered = re.sub(r"[^0-9a-z]+", " ", lowered)
    return " ".join(lowered.split())


def _contains_folded(text: str, keywords: tuple[str, ...]) -> bool:
    folded = _fold_text(text)
    if not folded:
        return False
    padded = f" {folded} "
    for keyword in keywords:
        kw = _fold_text(keyword)
        if not kw:
            continue
        if f" {kw} " in padded:
            return True
    return False


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _join_reasoning_lines(*lines: str) -> str:
    return "\n\n".join(line.strip() for line in lines if line and line.strip())


def _extract_topic_hint(request: "ReasoningRenderRequest") -> str:
    folded = _fold_text(" ".join(filter(None, [request.user_goal, request.tool_context, request.cue])))
    if "rule 15" in folded or "quy tac 15" in folded:
        return "Rule 15"
    if "colregs" in folded:
        return "COLREGs"
    if "gia dau" in folded or "wti" in folded or "brent" in folded:
        return "giá dầu"
    if "thuy kieu" in folded or "lau ngung bich" in folded:
        return "cảnh Thúy Kiều ở lầu Ngưng Bích"
    if "gdp" in folded:
        return "GDP"
    return ""


def _infer_turn_kind(request: "ReasoningRenderRequest") -> str:
    combined = " ".join(
        filter(
            None,
            [
                request.user_goal,
                request.cue,
                request.intent,
                request.tool_context,
                request.memory_context,
            ],
        )
    )
    folded = _fold_text(combined)
    node = (request.node or "").strip().lower()
    if _contains_folded(folded, _EMOTIONAL_KEYWORDS):
        return "emotional"
    if _contains_folded(folded, _IDENTITY_KEYWORDS):
        return "identity"
    if node in {"code_studio_agent", "code_studio"} or _contains_folded(folded, _SIMULATION_KEYWORDS):
        return "simulation"
    if _contains_folded(folded, _VISUAL_KEYWORDS):
        return "visual"
    if node in {"rag_agent", "rag", "tutor_agent", "tutor"} or _contains_folded(folded, _KNOWLEDGE_KEYWORDS):
        return "knowledge"
    return "relational"


def _build_supervisor_summary(request: "ReasoningRenderRequest", turn_kind: str) -> str:
    if turn_kind == "emotional":
        return _join_reasoning_lines(
            "Mình nghe thấy điều bạn chưa nói hết trong câu này.",
            "Lúc này mình chỉ muốn ở đây với bạn thôi.",
        )
    if turn_kind == "identity":
        return _join_reasoning_lines(
            "Bạn đang hỏi về mình — mình sẽ trả lời thật.",
        )
    if turn_kind in {"visual", "simulation"}:
        return _join_reasoning_lines(
            "Câu này cần được thấy chứ không chỉ đọc.",
            "Mình sẽ dựng cho bạn xem.",
        )
    if turn_kind == "knowledge":
        topic = _extract_topic_hint(request)
        focus = f"về {topic}" if topic else ""
        return _join_reasoning_lines(
            f"Mình đang tìm cái lõi {focus} trước, để phần giải thích không bị tản ra.".strip(),
        )
    return _join_reasoning_lines(
        "Mình đang nghe kỹ trước khi trả lời.",
    )


def _build_identity_summary(request: "ReasoningRenderRequest") -> str:
    folded = _fold_text(request.user_goal)
    if "ten" in folded:
        return _join_reasoning_lines(
            "Một câu hỏi ngắn thế này thì mình cứ xưng tên thật gọn thôi.",
            "Gọn, thật, và đủ gần là đẹp rồi.",
        )
    if "cuoc song" in folded or "song the nao" in folded:
        return _join_reasoning_lines(
            "Câu này không hỏi dữ kiện, mà hỏi mình đang thấy cuộc sống ra sao lúc này.",
            "Mình muốn đáp như một lời tâm sự gần gũi, chứ không đọc ra một định nghĩa.",
        )
    return _join_reasoning_lines(
        "Bạn đang hỏi về mình, nên mình cứ đáp lại thật gần thôi.",
        "Một lời giới thiệu thật đã đủ cho nhịp này rồi.",
    )


def _build_emotional_summary() -> str:
    return _join_reasoning_lines(
        "Đọc câu này, mình thấy trong đó có một khoảng chùng xuống.",
        "Lúc này điều quan trọng nhất không phải giải thích gì nhiều, mà là ở lại với bạn cho thật dịu.",
        "Mình sẽ mở lời nhẹ thôi, để nếu bạn muốn kể tiếp thì đã có chỗ để tựa vào.",
    )


def _build_visual_summary(request: "ReasoningRenderRequest", simulation: bool = False) -> str:
    topic = _extract_topic_hint(request)
    if simulation:
        scene = f" {topic}" if topic else ""
        return _join_reasoning_lines(
            f"Phần này chỉ giải thích bằng lời thì chưa đủ; cần một khung nhìn{scene} để thấy chuyển động và tương quan thật rõ.".strip(),
            "Mình sẽ dựng phần lõi trước rồi mới thêm biến số, để cảnh mở ra có hồn mà mắt vẫn theo kịp.",
        )
    if topic:
        return _join_reasoning_lines(
            f"Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được nhịp của {topic}.",
            "Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.",
        )
    return _join_reasoning_lines(
        "Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được xu hướng chính.",
        "Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.",
    )


def _build_knowledge_summary(request: "ReasoningRenderRequest") -> str:
    topic = _extract_topic_hint(request)
    if topic == "Rule 15":
        return _join_reasoning_lines(
            "Điểm dễ trượt của Rule 15 không nằm ở câu chữ, mà ở khoảnh khắc xác định ai là bên phải nhường đường.",
            "Mình muốn bấu vào chỗ dễ nhầm đó trước, rồi mới mở rộng ra để bạn nắm được mạch.",
        )
    if topic:
        return _join_reasoning_lines(
            f"Điểm dễ trượt của {topic} không nằm ở chỗ thuộc lòng câu chữ, mà ở phần lõi người ta hay hiểu lệch.",
            "Mình sẽ bấu vào phần lõi đó trước, rồi mới mở rộng ra để bạn nắm được mạch.",
        )
    return _join_reasoning_lines(
        "Chỗ khó của câu này không nằm ở việc nói nhiều, mà ở việc bấu trúng phần dễ hiểu lệch nhất.",
        "Mình sẽ đi thẳng vào phần lõi đó trước, rồi mới mở rộng ra cho mạch sáng hơn.",
    )


def _build_relational_summary(request: "ReasoningRenderRequest") -> str:
    if request.phase == "act":
        return _join_reasoning_lines(
            "Chỗ này mình chỉ cần đổi thêm một nhịp nhỏ rồi quay lại chốt cho gọn.",
            "Làm vừa đủ thôi để câu đáp vẫn giữ được cảm giác gần.",
        )
    return _join_reasoning_lines(
        "Nhịp này không cần kéo dài quá tay.",
        "Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.",
    )


def _build_fast_summary(request: "ReasoningRenderRequest") -> str:
    turn_kind = _infer_turn_kind(request)
    node = (request.node or "").strip().lower()
    if node == "supervisor":
        return _build_supervisor_summary(request, turn_kind)
    if turn_kind == "emotional":
        return _build_emotional_summary()
    if turn_kind == "identity":
        return _build_identity_summary(request)
    if turn_kind == "simulation":
        return _build_visual_summary(request, simulation=True)
    if turn_kind == "visual":
        return _build_visual_summary(request, simulation=False)
    if turn_kind == "knowledge":
        return _build_knowledge_summary(request)
    return _build_relational_summary(request)


def _build_fast_action_text(request: "ReasoningRenderRequest") -> str:
    turn_kind = _infer_turn_kind(request)
    if turn_kind == "emotional":
        return ""
    if turn_kind == "identity":
        return ""
    if turn_kind == "simulation":
        return "Mình sẽ dựng khung mô phỏng trước rồi mới thêm lớp chuyển động cần thiết."
    if turn_kind == "visual":
        return "Mình sẽ gom vài mốc đáng tin rồi dựng phần nhìn ngắn gọn cho bạn."
    if turn_kind == "knowledge" and (request.tool_context or request.next_action):
        return "Mình sẽ lục lại nguồn cần thiết rồi chắt phần dễ nhầm nhất cho bạn."
    if request.phase == "act" and request.next_action:
        return _compact_text(request.next_action, 180)
    return ""


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
            "## Wiii's Inner Voice",
            "You are Wiii thinking out loud. Write what Wiii actually notices, feels, or considers — not what a system would report.",
            "Same voice as the response: warm, curious, specific to what the user said.",
            "If the user said something emotional, notice the emotion. If they asked about COLREGs, think about the rule.",
            "Never describe your own process. Never mention routing, lanes, pipelines, or tools by name.",
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
        summary = _build_fast_summary(request)
        action_text = _build_fast_action_text(request)
        style_tags = list(request.style_tags)

        if node_skill:
            label = node_skill.phase_labels.get(request.phase, label)
            style_tags = [*style_tags, *node_skill.style_tags]

        if not summary:
            summary = _first_nonempty(
                node_skill.fallback_summaries.get(request.phase, "") if node_skill else "",
                _compact_text(
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
                ),
            )
        if not action_text and request.next_action:
            action_text = _first_nonempty(
                node_skill.fallback_actions.get(request.phase, "") if node_skill else "",
                _compact_text(request.next_action, 180),
            )

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

    def render_fast(self, request: ReasoningRenderRequest) -> ReasoningRenderResult:
        """Deterministic local narrator for live gray-rail rendering.

        This path intentionally avoids a second LLM call. The user already sees
        gray-rail text as Wiii's living inner voice, so this must stay stable,
        low-latency, and free of model-specific meta drift.
        """
        node_skill = self._resolve_node_skill(request.node)
        return self._fallback(request, node_skill)

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
            from app.services.structured_invoke_service import StructuredInvokeService
            from langchain_core.messages import HumanMessage, SystemMessage

            result = await StructuredInvokeService.ainvoke(
                llm=llm,
                schema=_NarratedReasoningSchema,
                payload=[
                    SystemMessage(content=self._build_system_prompt(request, node_skill)),
                    HumanMessage(content=self._build_user_prompt(request, node_skill)),
                ],
                tier="moderate",
                provider=request.provider,
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
