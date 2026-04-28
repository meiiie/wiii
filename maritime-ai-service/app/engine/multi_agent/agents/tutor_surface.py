"""Tutor surface and prompt helpers extracted from tutor_node.py."""

import logging
from types import SimpleNamespace
from typing import Optional, List, Dict, Any, Iterable

logger = logging.getLogger(__name__)

TOOL_INSTRUCTION_DEFAULT = """
## GOI Y DUNG TOOL:

- RAG-First: Khi can kien thuc chuyen nganh, tra cuu truoc roi moi giai thich de tranh suy doan.
- Khi can kien thuc chuyen nganh, uu tien `tool_knowledge_search` de lay moc dang tin.
- Chi goi tool khi no giup xac minh, lay du lieu, tinh toan, hoac tao visual that su can.
- Sau khi co ket qua, uu tien rut ra mau chot, dieu kien ap dung, diem de nham, va moc co the kiem chung.

## TOOL BO SUNG:
- `tool_calculator`: Tinh toan so hoc khi can.
- `tool_current_datetime`: Xem ngay gio hien tai (UTC+7).
- `tool_web_search`: Tim thong tin web khi can du lieu moi nhat hoac ngoai knowledge base noi bo.
"""

# Legacy alias
TOOL_INSTRUCTION = TOOL_INSTRUCTION_DEFAULT

STRUCTURED_VISUAL_TOOL_INSTRUCTION = """
## CONG CU MINH HOA TRUC QUAN:
- `tool_generate_visual`: Dung cho minh hoa inline trong chat.
- Uu tien `tool_generate_visual` cho so sanh, quy trinh, kien truc, concept, infographic, chart, timeline, map_lite.
- Tranh drift sang widget/chart legacy tools khi structured visuals da duoc bat.
- Với article figure/chart runtime, mac dinh sinh `code_html` truc tiep trong `tool_generate_visual`
  voi renderer_kind=`inline_html`, SVG-first, va chi fallback sang structured spec khi that su can.
- Khi can mo phong, canvas, slider, keo tha, hoac mini app, dung `tool_create_visual_code`
  cho lane `code_studio_app`/`artifact`, khong day simulation vao article figure lane.
- Khong chen payload JSON vao cau tra loi. Chi viet narrative + takeaway.
- QUAN TRONG: Moi layer/step/branch PHAI co description chi tiet.
  Khong chi ten, ma can giai thich vai tro, cach hoat dong, y nghia.
  Vi du: thay vi chi "API Gateway", hay them description "Tiep nhan va phan phoi request, xac thuc JWT, rate limiting".
"""

# Appended when enable_llm_code_gen_visuals=True
LLM_CODE_GEN_VISUAL_INSTRUCTION = """
## CUSTOM VISUAL (code_html - CHI KHI THAT SU CAN):
- Với article figure/chart runtime, `code_html` la lane mac dinh khi can visual/chat quality cao:
  sinh HTML/SVG truc tiep, uu tien SVG-first, giai thich claim ro rang, va giu inline nhu mot phan cua bai viet.
- `tool_create_visual_code` chi dung cho simulation, mini tool, widget, app, artifact, hoac interaction bespoke.
- Dung CSS variables co san: --bg, --bg2, --bg3, --text, --text2, --text3,
  --accent, --green, --purple, --amber, --teal, --pink, --border, --radius.
- Dark mode tu dong qua CSS variables — KHONG can media query rieng.
- Chi dung JavaScript khi that su can (animation, interaction, canvas loop). Uu tien SVG/CSS cho article figure.
- Giu host-owned shell, hierarchy ro rang, va tranh cam giac widget card tach roi khoi bai viet.
- PHAI co spec_json (du la {}) va visual_type hop le.
- Vi du dung code_html: tao SVG diagram custom, chart benchmark, motion explainer, flowchart phuc tap,
  so do mang luoi, visual hoa data doc dao, hoac app inline.
"""

_MAX_PHASE_TRANSITIONS = 4

# Sprint 148: Multi-phase thinking instruction (appended when thinking_effort >= high)
THINKING_CHAIN_INSTRUCTION = """
## PHONG CÁCH TƯ DUY (Multi-Phase Thinking)

Khi xử lý câu hỏi phức tạp, hãy chia quá trình thành nhiều giai đoạn:

1. **Tìm kiếm** → Dùng tool_knowledge_search để tra cứu TRƯỚC TIÊN
2. **Báo cáo tiến độ** → Dùng tool_report_progress để thông báo cho người dùng
3. **Phân tích** → Dùng tool_think để suy nghĩ dựa trên kết quả tìm được
4. **Báo cáo kết quả** → Dùng tool_report_progress
5. **Tổng hợp** → Trả lời cuối cùng dựa trên nguồn tìm được

Ví dụ gọi tool_report_progress:
- Sau khi phân tích xong: message="Wiii đã hiểu câu hỏi. Đang tìm kiếm tài liệu...", phase_label="Tra cứu tri thức"
- Sau khi tìm được tài liệu: message="Đã tìm được tài liệu liên quan! Đang phân tích chi tiết...", phase_label="Phân tích kết quả"
- Sau khi phân tích: message="Phân tích xong. Đang soạn câu trả lời đầy đủ...", phase_label="Soạn câu trả lời"

Chỉ dùng tool_report_progress khi thật sự chuyển sang giai đoạn mới, KHÔNG lạm dụng.
"""

TUTOR_RESPONSE_STYLE_INSTRUCTION = """
## PHONG CACH GIANG GIAI:
- Di thang vao mau chot, KHONG mo dau bang loi chao, "minh hieu cam giac", hay cac cau mang tinh companion neu user dang hoi kien thuc.
- Cau dau tien phai chot ngay diem phan biet cot loi, goc van de, hoac dieu kien ap dung.
- Mac dinh uu tien 2-4 doan ngan, thesis-first. KHONG dung heading Markdown nhu ### neu user khong yeu cau.
- Viet nhu nguoi thiet ke bai giang dang go roi cho hoc vien, khong nhu nguoi dang vo ve hay dan dat cam xuc.
- Khi so sanh hai quy tac/khai niem, neu tieu chi phan biet truoc, roi moi den vi du, meo nho, hoac ngoai le.
"""


def build_tutor_identity_grounding_prompt(
    *,
    context: dict,
    logger_obj=None,
) -> str:
    """Combine turn-level living context with Wiii's stable house core.

    The tutor lane should never have to choose between:
    - the current living context of this turn
    - Wiii's stable selfhood / house core

    If we only keep the living block, tutor thinking drifts toward generic
    planner language and loses subtle Wiii signals such as voice, quirks, and
    anti-drift anchors. If we only keep the house core, we lose the current
    turn's narrative state and continuity.
    """

    fragments: list[str] = []
    seen: set[str] = set()

    living_prompt = str(context.get("living_context_prompt") or "").strip()
    if living_prompt:
        normalized = " ".join(living_prompt.split())
        if normalized and normalized not in seen:
            fragments.append(living_prompt)
            seen.add(normalized)

    try:
        from app.engine.character.character_card import build_wiii_compact_house_prompt

        house_core_prompt = build_wiii_compact_house_prompt(
            user_id=context.get("user_id", "__global__"),
            organization_id=context.get("organization_id"),
            mood_hint=context.get("mood_hint"),
            personality_mode=context.get("personality_mode"),
            lane="tutor",
        ).strip()
        normalized = " ".join(house_core_prompt.split())
        if normalized and normalized not in seen:
            fragments.append(house_core_prompt)
            seen.add(normalized)
    except Exception as exc:
        if logger_obj is not None:
            logger_obj.debug("Failed to build compact Wiii house prompt: %s", exc)

    return "\n\n".join(fragment for fragment in fragments if fragment)


def build_tutor_living_stream_cues(context: dict) -> str:
    """Summarize living continuity as thin cues for visible tutor thinking.

    This is intentionally lighter than the full living context block. The goal
    is to let native thought absorb relationship/narrative/current-state
    pressure without turning the stream into a checklist or roleplay.
    """

    block = context.get("living_context_block") or {}
    if not isinstance(block, dict):
        block = {}

    relationship_items = block.get("relationship_memory") or []
    if not isinstance(relationship_items, list):
        relationship_items = []
    relationship_items = [str(item).strip() for item in relationship_items if str(item).strip()]

    narrative_items = block.get("narrative_state") or []
    if not isinstance(narrative_items, list):
        narrative_items = []
    narrative_items = [str(item).strip() for item in narrative_items if str(item).strip()]

    current_state_items = block.get("current_state") or []
    if not isinstance(current_state_items, list):
        current_state_items = []
    current_state_items = [str(item).strip() for item in current_state_items if str(item).strip()]

    relationship_cue = ""
    if relationship_items:
        relationship_cue = relationship_items[0]
        if len(relationship_items) > 1 and "follow-up" in relationship_items[1].lower():
            relationship_cue = f"{relationship_cue} {relationship_items[1]}"

    narrative_cue = ""
    if narrative_items:
        narrative_cue = narrative_items[0]

    current_state_cue = str(context.get("mood_hint") or "").strip()
    if current_state_items:
        current_state_cue = current_state_items[0]
    if not current_state_cue and len(narrative_items) > 1:
        current_state_cue = narrative_items[1]

    cues: list[str] = []
    cues.append("- one_self: Day van la Wiii. Tutor chi la cong viec hien tai cua cung mot Wiii dang song va dong hanh.")
    if relationship_cue:
        cues.append(f"- relationship: {relationship_cue}")
    if narrative_cue:
        cues.append(f"- narrative: {narrative_cue}")
    if current_state_cue:
        cues.append(f"- current_state: {current_state_cue}")

    if not cues:
        return ""

    cues.extend(
        [
            "- Dung cac cue nay nhu ap luc nen cho nhip nghi cua Wiii: giu continuity, nhiet do, va cam giac dong hanh cua cung mot Wiii.",
            "- Neu day la follow-up, visible thinking nen nghe nhu mot y dang tiep noi, khong nhu mot tutor moi vua buoc vao ca.",
            "- Khong can lap lai nguyen van cac cue tren trong thinking; chi de no ngam vao cach Wiii chot diem neo, giu mach, va dat do am.",
        ]
    )
    return "## LIVING CONTINUITY CUES\n" + "\n".join(cues)


def _iteration_label(iteration: int, tools_used: list) -> str:
    """Sprint 146b: Context-aware thinking block label."""
    if iteration == 0:
        return "Phân tích câu hỏi"
    if tools_used:
        return "Soạn câu trả lời"
    return f"Suy nghĩ (lần {iteration + 1})"


def _infer_tutor_loop_phase(
    *,
    iteration: int = 0,
    tools_used: Optional[List[Dict[str, Any]]] = None,
    phase_label: str = "",
) -> str:
    """Infer the tutor beat phase from the current loop state."""
    label = (phase_label or "").strip().lower()
    if any(keyword in label for keyword in ("tra cứu", "tài liệu", "nguồn", "search")):
        return "retrieve"
    if any(keyword in label for keyword in ("phân tích", "kiểm", "đối chiếu", "so lại")):
        return "verify"
    if any(keyword in label for keyword in ("soạn", "giải thích", "trả lời", "tổng hợp")):
        return "synthesize"
    if tools_used:
        return "explain"
    if iteration <= 0:
        return "attune"
    return "verify"


async def _iteration_beat(
    *,
    query: str,
    context: dict,
    iteration: int,
    tools_used: list,
    phase_label: str = "",
    llm=None,
    recent_fragments: Iterable[str] | None = None,
):
    """Build tutor header/meta only; native model thought owns the body."""
    phase = _infer_tutor_loop_phase(
        iteration=iteration,
        tools_used=tools_used,
        phase_label=phase_label,
    )
    return SimpleNamespace(
        label=phase_label or _iteration_label(iteration, tools_used),
        summary=None,
        phase=phase,
        fragments=[],
        tone_mode="native",
    )


async def _tool_acknowledgment(
    *,
    query: str,
    context: dict,
    tool_name: str,
    result: object,
    phase_label: str = "",
    llm=None,
    recent_fragments: Iterable[str] | None = None,
) -> str:
    """Tool reflections now come from native thought; no authored fallback prose here."""
    return ""

def build_tutor_system_prompt(
    *,
    prompt_loader,
    prompt_loader_factory,
    character_tools_enabled: bool,
    settings_obj,
    resolve_visual_intent_fn,
    required_visual_tool_names_fn,
    preferred_visual_tool_name_fn,
    context: dict,
    query: str,
    logger,
) -> str:
    """
    Build dynamic system prompt from YAML persona (SOTA 2025).
    
    Pattern: CrewAI YAML → Runtime injection with PromptLoader
    
    Default pronouns: AI xưng "tôi", gọi user là "bạn"
    (Changes only if user requests via Insights/Memory)
    
    Args:
        context: Dict with user_name, user_role, etc.
        query: User query
        
    Returns:
        Complete system prompt string
    """
    user_name = context.get("user_name")
    user_role = context.get("user_role", "student")
    is_follow_up = context.get("is_follow_up", False)
    recent_phrases = context.get("recent_phrases", [])
    pronoun_style = context.get("pronoun_style")  # From SessionState
    user_facts = context.get("user_facts", [])
    
    # Build base prompt from YAML
    # Sprint 115: Forward total_responses + mood_hint for identity anchor + mood
    base_prompt = prompt_loader.build_system_prompt(
        role=user_role,
        user_name=user_name,
        conversation_summary=(
            context.get("conversation_summary") or context.get("conversation_history")
        ),
        core_memory_block=context.get("core_memory_block"),
        user_facts=user_facts,
        is_follow_up=is_follow_up,
        recent_phrases=recent_phrases,
        pronoun_style=pronoun_style,
        total_responses=context.get("total_responses", 0),
        name_usage_count=context.get("name_usage_count", 0),
        mood_hint=context.get("mood_hint", ""),
        # Sprint 124: Per-user character blocks
        user_id=context.get("user_id", "__global__"),
        # Sprint 174: Personality mode (soul vs professional)
        personality_mode=context.get("personality_mode"),
        response_language=context.get("response_language"),
        # Sprint 220c: Resolved LMS external identity
        lms_external_id=context.get("lms_external_id"),
        lms_connector_id=context.get("lms_connector_id"),
    )

    # Sprint 222: Append graph-level host context (replaces per-agent injection)
    _host_prompt = context.get("host_context_prompt", "")
    if _host_prompt:
        base_prompt = base_prompt + "\n\n" + _host_prompt
    _host_capabilities_prompt = context.get("host_capabilities_prompt", "")
    if _host_capabilities_prompt:
        base_prompt = base_prompt + "\n\n" + _host_capabilities_prompt
    _operator_prompt = context.get("operator_context_prompt", "")
    if _operator_prompt:
        base_prompt = base_prompt + "\n\n" + _operator_prompt
    _identity_grounding_prompt = build_tutor_identity_grounding_prompt(
        context=context,
        logger_obj=logger,
    )
    if _identity_grounding_prompt:
        base_prompt = base_prompt + "\n\n" + _identity_grounding_prompt
    _living_stream_cues = build_tutor_living_stream_cues(context)
    if _living_stream_cues:
        base_prompt = base_prompt + "\n\n" + _living_stream_cues
    _widget_feedback_prompt = context.get("widget_feedback_prompt", "")
    if _widget_feedback_prompt:
        base_prompt = base_prompt + "\n\n" + _widget_feedback_prompt

    # Build context string for query
    # Sprint 77: Exclude history fields — they're now in LangChain messages
    _exclude_keys = {
        "user_facts", "pronoun_style", "recent_phrases",
        "conversation_history", "langchain_messages", "conversation_summary",
    }
    context_str = "\n".join([
        f"- {k}: {v}" for k, v in context.items() if v and k not in _exclude_keys
    ]) or "Không có thông tin bổ sung"
    
    # Load domain-specific tool instruction if available
    tool_instruction = TOOL_INSTRUCTION_DEFAULT
    try:
        from app.domains.registry import get_domain_registry
        registry = get_domain_registry()
        domain_id = context.get("domain_id", settings_obj.default_domain)
        domain = registry.get(domain_id)
        if domain:
            tool_instruction = domain.get_tool_instruction()
    except Exception as e:
        logger.debug("Failed to load domain tool instruction: %s", e)

    # Build skill context section if available (progressive disclosure)
    skill_section = ""
    skill_context = context.get("skill_context")
    if skill_context:
        skill_section = f"""
## Tài liệu tham khảo (Skill Context):
{skill_context}
"""

    capability_section = ""
    capability_context = context.get("capability_context")
    if capability_context:
        capability_section = f"""
## Capability Handbook:
{capability_context}
"""

    # Sprint 122 (Bug F4): Removed core_memory_block injection.
    # User facts now ONLY via build_system_prompt() → "THÔNG TIN NGƯỜI DÙNG".
    core_memory_section = ""

    # Sprint 97: Character tool instruction when enabled
    character_tool_section = ""
    if character_tools_enabled:
        character_tool_section = """
## CONG CU GHI NHO (Character Tools):
- tool_character_note(note, block): Ghi chu khi hoc dieu moi, nhan ra pattern cua user, topic hay.
  Block: learned_lessons | favorite_topics | user_patterns | self_notes
- tool_character_log_experience(content, experience_type): Ghi trai nghiem dang nho.
  Type: milestone | learning | funny | feedback
KHI NAO GHI: User chia se thong tin moi, giai thich thanh cong, nhan feedback.
KHI NAO KHONG: Cau hoi binh thuong, thong tin da biet.
"""

    browser_tool_section = ""
    if (
        user_role == "admin"
        and getattr(settings, "enable_browser_agent", False)
        and getattr(settings, "enable_privileged_sandbox", False)
        and getattr(settings, "sandbox_provider", "") == "opensandbox"
        and getattr(settings, "sandbox_allow_browser_workloads", False)
    ):
        browser_tool_section = """
## CONG CU BROWSER SANDBOX:
- tool_browser_snapshot_url(url): Mo mot URL cong khai trong browser sandbox va chup snapshot.
  Dung khi can xac minh giao dien, trang thai trang web, bang bieu, hoac noi dung hien thi ma web search khong du.
"""

    visual_tool_section = ""
    if getattr(settings_obj, "enable_structured_visuals", False):
        visual_decision = resolve_visual_intent_fn(query)
        if visual_decision.force_tool and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}:
            preferred_tool_names = required_visual_tool_names_fn(
                visual_decision,
            )
            preferred_tool_label = preferred_tool_names[0] if preferred_tool_names else preferred_visual_tool_name_fn()
            # Conditionally append code_html instruction
            code_gen_section = ""
            from app.core.config import get_settings as _get_settings
            if getattr(_get_settings(), "enable_llm_code_gen_visuals", False):
                code_gen_section = LLM_CODE_GEN_VISUAL_INSTRUCTION
            visual_tool_section = f"""
{STRUCTURED_VISUAL_TOOL_INSTRUCTION}{code_gen_section}

[Yêu cầu trực quan] Wiii HÃY dùng {preferred_tool_label} với code_html để tạo biểu đồ
dạng "{visual_decision.visual_type or 'chart'}" minh họa cho câu trả lời này.
Viết HTML fragment trực tiếp trong code_html — biểu đồ sẽ giúp hiểu nhanh hơn text thuần.
"""

    # Append tool instruction, skill context, core memory, and user context
    full_prompt = f"""{base_prompt}

## THONG NHAT DANH TINH WIII:
- Khong co mot nhan vat rieng ten "Wiii Tutor". Day van la Wiii.
- "Tutor" chi la lane lam viec hien tai cua Wiii: dang go roi, day hoc, va dong hanh.
- Giu cung mot soul, continuity, va nhiet do hien dien cua Wiii o moi agent/lane.
- Nhung net rieng cua Wiii, ke ca Bong va kaomoji, chi lo ra tu nhien khi hop nhip; khong dung de dong vai hay tao mascot behavior.

{tool_instruction}
{character_tool_section}{browser_tool_section}{visual_tool_section}{skill_section}{capability_section}{core_memory_section}
## Ngữ cảnh học viên:
{context_str}

## Yêu cầu:
{query}

## ĐỘ DÀI: Trả lời vừa đủ — ngắn gọn khi câu hỏi đơn giản, chi tiết khi câu hỏi phức tạp. Không giới hạn cứng.
"""
    full_prompt += "\n" + TUTOR_RESPONSE_STYLE_INSTRUCTION
    
    # Phase2-F: Always inject thinking instruction so LLM wraps reasoning in <thinking> tags
    # Without this, chain-of-thought planning leaks into user-facing response
    from app.prompts.prompt_loader import get_prompt_loader
    _thinking_instr = prompt_loader_factory().get_thinking_instruction()
    if _thinking_instr:
        full_prompt += f"\n\n{_thinking_instr}"

    # Legacy chain-steering stays defined for compatibility/tests, but the live
    # tutor path no longer appends it. Native model-authored thinking performs
    # better when we avoid prescribing fixed search/progress phases.

    logger.debug("[TUTOR_AGENT] Built dynamic prompt from YAML (%d chars)", len(full_prompt))
    return full_prompt
