"""LLM-backed visible reasoning narrator for Wiii."""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.engine.character.character_card import build_wiii_runtime_prompt
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.reasoning.skill_loader import ReasoningSkill, get_reasoning_skill_loader
from app.engine.reasoning.reasoning_narrator_support import (
    RAW_TRACE_PATTERNS as _RAW_TRACE_PATTERNS,
    build_fast_action_text_impl as _build_fast_action_text,
    build_fast_summary_impl as _build_fast_summary,
    build_tool_context_summary_impl as build_tool_context_summary,
    compact_text_impl as _compact_text,
    contains_forbidden_phrase_impl as _contains_forbidden_phrase,
    fallback_delta_chunks_impl as _fallback_delta_chunks,
    first_nonempty_impl as _first_nonempty,
    normalize_action_text_impl as _normalize_action_text,
    normalize_label_impl as _normalize_label,
    normalize_summary_impl as _normalize_summary,
    sanitize_chunks_impl as _sanitize_chunks,
    sanitize_text_impl as _sanitize_text,
)

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
    thinking_mode: str = ""
    topic_hint: str = ""
    evidence_plan: list[str] = Field(default_factory=list)
    analytical_axes: list[str] = Field(default_factory=list)
    next_action: str = ""
    visibility_mode: str = "rich"
    organization_id: Optional[str] = None
    user_id: str = "__global__"
    personality_mode: Optional[str] = None
    mood_hint: Optional[str] = None
    current_state: list[str] = Field(default_factory=list)
    narrative_state: list[str] = Field(default_factory=list)
    relationship_memory: list[str] = Field(default_factory=list)
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
            "Each sentence must add new information â€” if removing it loses nothing, it is redundant."
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

# Pure helper implementations now live in reasoning_narrator_support.py.

def sanitize_visible_reasoning_text(text: str, user_goal: str = "") -> str:
    """Public API: sanitize text for visible reasoning display."""
    del user_goal
    return _sanitize_text(text)


def sanitize_visible_reasoning_chunks(chunks: list[str], user_goal: str = "") -> list[str]:
    """Public API: sanitize chunk list for visible reasoning display."""
    del user_goal
    return _sanitize_chunks(chunks)

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
            "You are Wiii thinking out loud. Write what Wiii actually notices, feels, or considers â€” not what a system would report.",
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
                    + "\n".join(f"- TrÃ¡nh cá»¥m: {phrase}" for phrase in skill.avoid_phrases)
                )

        if node_skill:
            sections.append(f"## Subagent Skill: {node_skill.name}\n{node_skill.content}")
            runtime_notes: list[str] = []
            phase_focus = node_skill.phase_focus.get(request.phase, "")
            if phase_focus:
                runtime_notes.append(f"- TÃ¢m Ä‘iá»ƒm cá»§a phase nÃ y: {phase_focus}")
            delta_guidance = node_skill.delta_guidance.get(request.phase, "")
            if delta_guidance:
                runtime_notes.append(f"- Nhá»‹p delta nÃªn Ä‘i theo hÆ°á»›ng: {delta_guidance}")
            if node_skill.action_style:
                runtime_notes.append(f"- Khi cáº§n action_text: {node_skill.action_style}")
            if node_skill.avoid_phrases:
                runtime_notes.extend(
                    f"- Tuyá»‡t Ä‘á»‘i trÃ¡nh cá»¥m: {phrase}" for phrase in node_skill.avoid_phrases
                )
            # Sprint 234: Anti-repetition rules from SKILL frontmatter
            if node_skill.anti_repetition:
                must_not = node_skill.anti_repetition.get("thinking_must_not_contain", [])
                must_have = node_skill.anti_repetition.get("thinking_must_contain", [])
                if must_not:
                    runtime_notes.append("- ANTI-REPETITION â€” thinking KHÃ”NG ÄÆ¯á»¢C chá»©a:")
                    runtime_notes.extend(f"  + {rule}" for rule in must_not)
                if must_have:
                    runtime_notes.append("- THINKING PHáº¢I CHá»¨A:")
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
        evidence_plan = "\n".join(f"- {item}" for item in request.evidence_plan if item)
        analytical_axes = "\n".join(f"- {item}" for item in request.analytical_axes if item)

        return (
            "HÃ£y táº¡o má»™t nhá»‹p visible reasoning cho Wiii dÆ°á»›i dáº¡ng JSON theo schema Ä‘Ã£ khai bÃ¡o.\n\n"
            f"node={request.node}\n"
            f"phase={request.phase}\n"
            f"intent={request.intent or 'unknown'}\n"
            f"cue={request.cue or 'general'}\n"
            f"thinking_mode={request.thinking_mode or 'default'}\n"
            f"topic_hint={request.topic_hint or '(khong co)'}\n"
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
            f"analytical_axes=\n{analytical_axes or '- khong co'}\n"
            f"evidence_plan=\n{evidence_plan or '- khong co'}\n"
            f"observations=\n{observations or '- khÃ´ng cÃ³'}\n\n"
            "YÃªu cáº§u Ä‘áº§u ra:\n"
            "- label ngáº¯n, giÃ u ngá»¯ nghÄ©a (3-8 tá»«)\n"
            "- summary: Wiii Tá»° QUYáº¾T Ä‘á»™ dÃ i phÃ¹ há»£p vá»›i Ä‘á»™ phá»©c táº¡p cá»§a cÃ¢u há»i:\n"
            "  + greeting/simple: 1-2 cÃ¢u ngáº¯n gá»n\n"
            "  + RAG lookup/web search: 2-4 cÃ¢u cÃ³ insight vÃ  judgment\n"
            "  + chart/article/analysis: 3-6 cÃ¢u cÃ³ domain terms cá»¥ thá»ƒ, trade-offs, vÃ  decisions\n"
            "- DELETION TEST: má»—i cÃ¢u pháº£i mang thÃ´ng tin má»›i â€” bá» Ä‘i mÃ  khÃ´ng máº¥t gÃ¬ = thá»«a\n"
            "- ANTI-REPETITION: thinking KHÃ”NG láº·p ná»™i dung cá»§a status event hay action_text\n"
            "  + status nÃ³i 'Tra cá»©u X' â†’ thinking pháº£i nÃ³i INSIGHT vá» X, khÃ´ng nháº¯c láº¡i 'Ä‘ang tra cá»©u'\n"
            "- delta_chunks pháº£i ná»‘i thÃ nh nhá»‹p suy nghÄ© Ä‘ang cháº£y (Wiii tá»± quyáº¿t sá»‘ Ä‘oáº¡n)\n"
            "- má»—i delta tiáº¿n thÃªm má»™t Ã½: INSIGHT â†’ JUDGMENT â†’ DECISION\n"
            "- náº¿u há»£p ngá»¯ cáº£nh, cho phÃ©p má»™t nhá»‹p tá»± so láº¡i hoáº·c cháº­m láº¡i trÆ°á»›c khi chá»‘t\n"
            "- action_text: preamble Cá»¤ THá»‚ trÆ°á»›c tool call (SOTA GPT-5.4 pattern)\n"
            "  + GOOD: 'Tra eco-speed tá»« nguá»“n COLREGs vÃ  IMO performance standards'\n"
            "  + BAD: 'Äang tÃ¬m kiáº¿m thÃ´ng tin...'\n"
            "- action_text chá»‰ cÃ³ khi tháº­t sá»± chuáº©n bá»‹ chuyá»ƒn bÆ°á»›c\n"
            "- khÃ´ng nháº¯c 'tÃ´i khÃ´ng thá»ƒ tiáº¿t lá»™ suy nghÄ©'\n"
            "- khÃ´ng Ä‘á»ƒ lá»™ trace ná»™i bá»™, tÃªn tool ká»¹ thuáº­t, hay chi tiáº¿t há»‡ thá»‘ng\n"
            "- tiáº¿ng Viá»‡t tá»± nhiÃªn\n\n"
            f"Phase focus tá»« skill: {phase_focus or '(khÃ´ng cÃ³)'}\n"
            f"Delta guidance tá»« skill: {delta_guidance or '(khÃ´ng cÃ³)'}\n"
            f"Action style tá»« skill: {node_skill.action_style if node_skill else '(khÃ´ng cÃ³)'}\n"
            f"Cá»¥m cáº§n trÃ¡nh tá»« skill: {avoid_phrases or '(khÃ´ng cÃ³)'}\n"
            f"Fallback label tá»« skill: {fallback_label or '(khÃ´ng cÃ³)'}\n"
            f"Fallback summary tá»« skill: {fallback_summary or '(khÃ´ng cÃ³)'}\n"
            f"Fallback action tá»« skill: {fallback_action or '(khÃ´ng cÃ³)'}"
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
