"""
Tutor Agent Node - Teaching Specialist (SOTA ReAct Pattern)

Handles educational interactions with tool-enabled RAG retrieval.

**SOTA 2026 Pattern:**
- Tool-Enabled Agent with ReAct Loop
- RAG-First approach via system prompt
- Utility tools: calculator, datetime, web search
- Uses CorrectiveRAG internally via tool_knowledge_search

**Integrated with agents/ framework for config and tracing.**
"""

import logging
from typing import Optional, List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from app.core.config import settings
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.reasoning import ReasoningRenderRequest, get_reasoning_narrator
from app.engine.reasoning.reasoning_narrator import build_tool_context_summary
from app.services.output_processor import extract_thinking_from_response
from app.engine.multi_agent.state import AgentState
from app.engine.agents import TUTOR_AGENT_CONFIG
from app.engine.tools.rag_tools import (
    tool_knowledge_search,
    get_last_retrieved_sources,
    get_last_native_thinking,  # CHỈ THỊ SỐ 29 v9: Option B+ thinking propagation
    get_last_reasoning_trace,  # CHỈ THỊ SỐ 31 v3: CRAG trace propagation
    get_last_confidence,  # SOTA 2025: Confidence-based early termination
    clear_retrieved_sources
)
from app.engine.tools.utility_tools import tool_calculator, tool_current_datetime
from app.engine.tools.web_search_tools import tool_web_search
from app.engine.tools.think_tool import tool_think
from app.engine.tools.progress_tool import tool_report_progress
from app.engine.tools.invocation import get_tool_by_name, invoke_tool_with_runtime
from app.engine.tools.runtime_context import (
    build_tool_runtime_context,
    filter_tools_for_role,
)
from app.engine.multi_agent.visual_intent_resolver import (
    filter_tools_for_visual_intent,
    preferred_visual_tool_name,
    required_visual_tool_names,
    resolve_visual_intent,
)
# SOTA 2025: PromptLoader for YAML-driven persona (CrewAI pattern)
from app.prompts.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL INSTRUCTION (Appended to YAML-driven prompt)
# =============================================================================

TOOL_INSTRUCTION_DEFAULT = """
## Gợi ý sử dụng Tools:

Khi gặp câu hỏi chuyên ngành, ưu tiên gọi `tool_knowledge_search` trước —
dữ liệu từ knowledge base chính xác hơn kiến thức chung, và user đánh giá cao
khi có sources kèm theo.

Tra cứu xong rồi suy nghĩ sẽ cho câu trả lời tốt hơn — vì có dữ liệu thật
để phân tích thay vì đoán từ kiến thức chung.

Trích dẫn nguồn giúp user tin tưởng và có thể verify. Với câu chào hỏi hoặc
tâm sự, không cần tra cứu — trò chuyện tự nhiên là đủ.

## TOOL BỔ SUNG:
- `tool_calculator`: Tính toán số học (cộng, trừ, nhân, chia, sqrt, sin, cos, log, v.v.)
- `tool_current_datetime`: Xem ngày giờ hiện tại (UTC+7)
- `tool_web_search`: Tìm kiếm thông tin trên web khi cần thông tin mới nhất hoặc ngoài cơ sở dữ liệu nội bộ
"""

# Legacy alias
TOOL_INSTRUCTION = TOOL_INSTRUCTION_DEFAULT

STRUCTURED_VISUAL_TOOL_INSTRUCTION = """
## CONG CU MINH HOA TRUC QUAN:
- `tool_generate_visual`: Dung cho minh hoa inline trong chat.
- Uu tien `tool_generate_visual` cho so sanh, quy trinh, kien truc, concept, infographic, chart, timeline, map_lite.
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
):
    """Build a tutor reasoning beat for the current loop phase."""
    phase = _infer_tutor_loop_phase(
        iteration=iteration,
        tools_used=tools_used,
        phase_label=phase_label,
    )
    return await get_reasoning_narrator().render(
        ReasoningRenderRequest(
            node="tutor_agent",
            phase=phase,
            cue=(phase_label or "general"),
            user_goal=query,
            conversation_context=str(context.get("conversation_summary", "")),
            capability_context=str(context.get("capability_context", "")),
            next_action="Tiếp tục giảng giải theo nhịp người dùng đang cần.",
            observations=[
                f"iteration={iteration}",
                f"tools_used={len(tools_used)}",
                phase_label,
            ],
            user_id=str(context.get("user_id", "__global__")),
            organization_id=context.get("organization_id"),
            personality_mode=context.get("personality_mode"),
            mood_hint=context.get("mood_hint"),
            visibility_mode="rich",
            style_tags=["tutor", phase],
        )
    )


async def _tool_acknowledgment(
    *,
    query: str,
    context: dict,
    tool_name: str,
    result: object,
    phase_label: str = "",
) -> str:
    """Narrate what a tool result means for the ongoing tutor flow."""
    narration = await get_reasoning_narrator().render(
        ReasoningRenderRequest(
            node="tutor_agent",
            phase="act",
            cue=phase_label or tool_name,
            user_goal=query,
            conversation_context=str(context.get("conversation_summary", "")),
            capability_context=str(context.get("capability_context", "")),
            tool_context=build_tool_context_summary([tool_name], result=result),
            next_action="Lồng kết quả vừa có vào mạch giải thích đang đi tiếp.",
            observations=[f"tool={tool_name}", str(result)[:260]],
            user_id=str(context.get("user_id", "__global__")),
            organization_id=context.get("organization_id"),
            personality_mode=context.get("personality_mode"),
            mood_hint=context.get("mood_hint"),
            visibility_mode="rich",
            style_tags=["tutor", "tool_reflection"],
        )
    )
    return narration.summary


class TutorAgentNode:
    """
    Tutor Agent - Teaching specialist with SOTA ReAct pattern.
    
    Responsibilities:
    - Explain concepts clearly with RAG-backed knowledge
    - Create quizzes and exercises
    - Adapt to learner level
    - Always cite sources
    
    SOTA Pattern: Tool-Enabled Agent with RAG-First approach
    """
    
    def __init__(self):
        """Initialize Tutor Agent with YAML-driven persona (SOTA 2025)."""
        self._prompt_loader = get_prompt_loader()  # SOTA: YAML persona
        self._llm = None
        self._llm_with_tools = None
        self._config = TUTOR_AGENT_CONFIG
        self._tools = [
            tool_knowledge_search, tool_web_search, tool_calculator,
            tool_current_datetime, tool_report_progress, tool_think,
        ]

        # Sprint 95: Conditionally add character tools
        self._character_tools_enabled = False
        try:
            from app.core.config import settings as _settings
            if _settings.enable_character_tools:
                from app.engine.character.character_tools import get_character_tools
                char_tools = get_character_tools()
                self._tools.extend(char_tools)
                self._character_tools_enabled = True
                logger.info("[TUTOR_AGENT] Character tools enabled: %d tools", len(char_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Character tools not available: %s", e)

        # Sprint 179: Chart tools (feature-gated by enable_chart_tools)
        try:
            from app.engine.tools.chart_tools import get_chart_tools
            chart_tools = get_chart_tools()
            if chart_tools:
                self._tools.extend(chart_tools)
                logger.info("[TUTOR_AGENT] Chart tools enabled: %d tools", len(chart_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Chart tools not available: %s", e)

        try:
            from app.engine.tools.visual_tools import get_visual_tools

            visual_tools = get_visual_tools()
            if visual_tools:
                self._tools.extend(visual_tools)
                logger.info("[TUTOR_AGENT] Visual tools enabled: %d tools", len(visual_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Visual tools not available: %s", e)

        try:
            from app.engine.tools.output_generation_tools import get_output_generation_tools

            output_tools = get_output_generation_tools()
            if output_tools:
                self._tools.extend(output_tools)
                logger.info("[TUTOR_AGENT] Output generation tools enabled: %d tools", len(output_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Output generation tools not available: %s", e)

        try:
            from app.core.config import settings as _settings

            if (
                _settings.enable_browser_agent
                and _settings.enable_privileged_sandbox
                and _settings.sandbox_provider == "opensandbox"
                and _settings.sandbox_allow_browser_workloads
            ):
                from app.engine.tools.browser_sandbox_tools import get_browser_sandbox_tools

                browser_tools = get_browser_sandbox_tools()
                if browser_tools:
                    self._tools.extend(browser_tools)
                    logger.info("[TUTOR_AGENT] Browser sandbox tools enabled: %d tools", len(browser_tools))
        except Exception as e:
            logger.debug("[TUTOR_AGENT] Browser sandbox tools not available: %s", e)

        self._init_llm()
        logger.info("TutorAgentNode initialized with YAML persona, tools: %d", len(self._tools))
    
    def _init_llm(self):
        """Initialize teaching LLM with tools and native thinking."""
        try:
            # Sprint 69: Use AgentConfigRegistry for per-node LLM config
            self._llm = AgentConfigRegistry.get_llm("tutor_agent")
            # Bind tools to LLM (SOTA pattern)
            self._llm_with_tools = self._llm.bind_tools(self._tools)
            logger.info("[TUTOR_AGENT] LLM bound with %d tools (via AgentConfigRegistry)", len(self._tools))
        except Exception as e:
            logger.error("Failed to initialize Tutor LLM: %s", e)
            self._llm = None
            self._llm_with_tools = None
    
    def _build_system_prompt(self, context: dict, query: str) -> str:
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
        base_prompt = self._prompt_loader.build_system_prompt(
            role=user_role,
            user_name=user_name,
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
            # Sprint 220c: Resolved LMS external identity
            lms_external_id=context.get("lms_external_id"),
            lms_connector_id=context.get("lms_connector_id"),
        )

        # Sprint 222: Append graph-level host context (replaces per-agent injection)
        _host_prompt = context.get("host_context_prompt", "")
        if _host_prompt:
            base_prompt = base_prompt + "\n\n" + _host_prompt
        _living_prompt = context.get("living_context_prompt", "")
        if _living_prompt:
            base_prompt = base_prompt + "\n\n" + _living_prompt
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
            domain_id = context.get("domain_id", settings.default_domain)
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
        if self._character_tools_enabled:
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
        if getattr(settings, "enable_structured_visuals", False):
            visual_decision = resolve_visual_intent(query)
            if visual_decision.force_tool and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}:
                preferred_tool_names = required_visual_tool_names(
                    visual_decision,
                )
                preferred_tool_label = preferred_tool_names[0] if preferred_tool_names else preferred_visual_tool_name(True)
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

{tool_instruction}
{character_tool_section}{browser_tool_section}{visual_tool_section}{skill_section}{capability_section}{core_memory_section}
## Ngữ cảnh học viên:
{context_str}

## Yêu cầu:
{query}

## ĐỘ DÀI: Trả lời vừa đủ — ngắn gọn khi câu hỏi đơn giản, chi tiết khi câu hỏi phức tạp. Không giới hạn cứng.
"""
        
        # Phase2-F: Always inject thinking instruction so LLM wraps reasoning in <thinking> tags
        # Without this, chain-of-thought planning leaks into user-facing response
        from app.prompts.prompt_loader import get_prompt_loader
        _thinking_instr = get_prompt_loader().get_thinking_instruction()
        if _thinking_instr:
            full_prompt += f"\n\n{_thinking_instr}"

        # Sprint 148: Append thinking chain instruction for complex queries (additional)
        thinking_effort = context.get("thinking_effort", "")
        if thinking_effort in ("high", "max") and settings.enable_thinking_chain:
            full_prompt += "\n" + THINKING_CHAIN_INSTRUCTION

        logger.debug("[TUTOR_AGENT] Built dynamic prompt from YAML (%d chars)", len(full_prompt))
        return full_prompt
    
    async def process(self, state: AgentState) -> AgentState:
        """
        Process educational request with ReAct pattern.
        
        SOTA Pattern: Think → Act → Observe → Repeat
        
        CHỈ THỊ SỐ 29 v9: Option B+ - Propagates thinking to state for API transparency.
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
        learning_context = state.get("learning_context", {})

        try:
            # Sprint 66: Per-request thinking effort override
            thinking_effort = state.get("thinking_effort")
            llm_for_request = self._llm

            # Visual Intelligence: upgrade to DEEP tier when visual intent detected
            visual_decision = resolve_visual_intent(query)
            if visual_decision.force_tool and not thinking_effort:
                thinking_effort = "high"
                logger.info("[TUTOR_AGENT] Visual intent detected → upgrade to high effort")

            provider_override = state.get("provider")
            if thinking_effort or (provider_override and provider_override != "auto"):
                llm_for_request = AgentConfigRegistry.get_llm(
                    "tutor_agent",
                    effort_override=thinking_effort,
                    provider_override=provider_override,
                )
                logger.info("[TUTOR_AGENT] LLM override: effort=%s provider=%s", thinking_effort, provider_override)

            # Sprint 69: Get event bus queue for intra-node streaming
            event_queue = None
            bus_id = state.get("_event_bus_id")
            if bus_id:
                from app.engine.multi_agent.graph_streaming import _get_event_queue
                event_queue = _get_event_queue(bus_id)

            # Merge context and inject skill_context from supervisor
            merged_context = {**context, **learning_context}
            skill_context = state.get("skill_context")
            if skill_context:
                merged_context["skill_context"] = skill_context
            capability_context = state.get("capability_context")
            if capability_context:
                merged_context["capability_context"] = capability_context
            # Sprint 222: Thread graph-level host context
            _host_ctx = state.get("host_context_prompt", "")
            if _host_ctx:
                merged_context["host_context_prompt"] = _host_ctx
            _living_ctx = state.get("living_context_prompt", "")
            if _living_ctx:
                merged_context["living_context_prompt"] = _living_ctx
            _widget_feedback_ctx = state.get("widget_feedback_prompt", "")
            if _widget_feedback_ctx:
                merged_context["widget_feedback_prompt"] = _widget_feedback_ctx
            # Sprint 148: Pass thinking_effort to context for prompt injection
            if thinking_effort:
                merged_context["thinking_effort"] = thinking_effort

            visual_decision = resolve_visual_intent(query)
            active_tools = filter_tools_for_role(
                self._tools,
                merged_context.get("user_role", "student"),
            )
            active_tools = filter_tools_for_visual_intent(
                active_tools,
                visual_decision,
                structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
            )
            try:
                from app.engine.skills.skill_recommender import select_runtime_tools

                must_include = [
                    "tool_knowledge_search",
                    "tool_think",
                    "tool_report_progress",
                ]
                must_include.extend(
                    required_visual_tool_names(
                        visual_decision,
                    )
                )
                selected_tools = select_runtime_tools(
                    active_tools,
                    query=query,
                    intent=(state.get("routing_metadata") or {}).get("intent") or "learning",
                    user_role=merged_context.get("user_role", "student"),
                    max_tools=min(len(active_tools), 6),
                    must_include=must_include,
                )
                if selected_tools:
                    active_tools = filter_tools_for_visual_intent(
                        selected_tools,
                        visual_decision,
                        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
                    )
                    logger.info(
                        "[TUTOR_AGENT] Runtime-selected tools: %s",
                        [getattr(tool, "name", getattr(tool, "__name__", "unknown")) for tool in active_tools],
                    )
            except Exception as selection_err:
                logger.debug("[TUTOR_AGENT] Runtime tool selection skipped: %s", selection_err)
            llm_with_tools_for_request = None
            if llm_for_request:
                # Visual Intelligence: force tool calling when resolver detects visual intent
                if visual_decision.force_tool:
                    visual_tools_only = [t for t in active_tools if getattr(t, "name", "") == "tool_generate_visual"]
                    if visual_tools_only:
                        from app.engine.multi_agent.graph import _resolve_tool_choice
                        forced_choice = _resolve_tool_choice(True, visual_tools_only, provider=provider_override)
                        llm_with_tools_for_request = llm_for_request.bind_tools(
                            visual_tools_only, tool_choice=forced_choice,
                        )
                        logger.info("[TUTOR_AGENT] Visual intent → force tool_choice=%r for tool_generate_visual", forced_choice)
                    else:
                        llm_with_tools_for_request = llm_for_request.bind_tools(active_tools)
                else:
                    llm_with_tools_for_request = (
                        llm_for_request.bind_tools(active_tools)
                        if active_tools
                        else llm_for_request
                    )
            runtime_context_base = build_tool_runtime_context(
                event_bus_id=bus_id,
                request_id=bus_id or state.get("session_id"),
                session_id=state.get("session_id"),
                organization_id=state.get("organization_id"),
                user_id=state.get("user_id"),
                user_role=merged_context.get("user_role", "student"),
                node="tutor_agent",
                source="agentic_loop",
            )

            # Execute ReAct loop - now returns thinking + bus streaming flag
            response, sources, tools_used, thinking, answer_streamed = await self._react_loop(
                query=query,
                context=merged_context,
                event_queue=event_queue,
                tools=active_tools,
                llm_with_tools=llm_with_tools_for_request,
                runtime_context_base=runtime_context_base,
            )

            # Sprint 74: Signal to graph_streaming whether answer was already streamed via bus
            if answer_streamed:
                state["_answer_streamed_via_bus"] = True

            # Update state with results
            state["tutor_output"] = response
            state["sources"] = sources
            state["tools_used"] = tools_used
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["tutor"] = response
            state["agent_outputs"]["tutor_tools_used"] = tools_used  # SOTA: Track tool usage
            state["current_agent"] = "tutor_agent"
            
            # CHỈ THỊ SỐ 29 v9: Set thinking in state for SOTA reasoning transparency
            # This follows the same pattern as rag_node.py
            if thinking:
                state["thinking"] = thinking
                logger.info("[TUTOR_AGENT] Thinking propagated to state: %d chars", len(thinking))
            
            # CHỈ THỊ SỐ 31 v3 SOTA: Propagate CRAG trace for synthesizer merge
            # This follows LangGraph shared state pattern
            crag_trace = get_last_reasoning_trace()
            if crag_trace:
                state["reasoning_trace"] = crag_trace
                logger.info("[TUTOR_AGENT] CRAG trace propagated: %d steps", crag_trace.total_steps)
            
            logger.info("[TUTOR_AGENT] ReAct complete: %d tool calls, %d sources", len(tools_used), len(sources))
            
        except Exception as e:
            logger.error("[TUTOR_AGENT] Error: %s", e)
            state["tutor_output"] = "Ôi, Wiii vấp rồi! Mình đang cố lại nhé... Bạn thử hỏi lại mình được không?"
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
    ) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Optional[str], bool]:
        """
        Execute ReAct loop: Think → Act → Observe.

        SOTA Pattern from OpenAI Agents SDK / Anthropic Claude.

        CHỉ THỊ SỐ 29 v9: Now returns thinking for SOTA reasoning transparency.
        Combines thinking from:
        1. RAG tool (get_last_native_thinking)
        2. Tutor LLM final response (extract_thinking_from_response)

        Args:
            query: User query
            context: Additional context
            event_queue: Sprint 69 asyncio.Queue for intra-node streaming

        Returns:
            Tuple of (response, sources, tools_used, thinking, answer_streamed_via_bus)
        """
        llm_with_tools = llm_with_tools or self._llm_with_tools

        if not llm_with_tools:
            return self._fallback_response(query), [], [], None, False

        tools = tools or self._tools
        
        # Clear previous sources (also clears thinking)
        clear_retrieved_sources()
        
        # SOTA 2025: Build dynamic prompt from YAML
        system_prompt = self._build_system_prompt(context, query)

        # Initialize messages — Sprint 77: inject conversation history
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
        max_iterations = 4  # Sprint 103b→fix: 2 → 4 (need room for think + search + generate)
        final_response = ""
        llm_thinking = None  # Thinking from final LLM response
        _answer_streamed_via_bus = False  # Sprint 74: Track if answer was streamed via bus

        # Sprint 70: Sub-chunk size for smooth streaming (matches graph_streaming.py)
        _CHUNK_SIZE = 40  # ~8-10 words per sub-chunk (Sprint 103b: was 12)
        _CHUNK_DELAY = 0.008  # 8ms between sub-chunks (Sprint 103b: was 18ms)

        # Sprint 69: Helper for intra-node event push
        async def _push(evt):
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception as exc:
                    logger.warning("[TUTOR_AGENT] Bus push failed: %s", exc)

        def _extract_chunk_text(content) -> str:
            """Extract text from LLM chunk content (handles str and Gemini list format)."""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        async def _push_thinking_deltas(text: str):
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

        async def _push_answer_deltas(text: str):
            """Sprint 74: Push answer_delta events with sub-chunking for real-time answer streaming."""
            import asyncio
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({
                    "type": "answer_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        _BULK_SIZE = 200  # Sprint 75: Large chunks for fast re-emission

        async def _push_answer_bulk(text: str):
            """Sprint 75: Push answer content in large chunks with no delay.

            Used when content was already shown via thinking_delta — the answer_delta
            is just for populating the answer section, no need for smooth streaming.
            Drops answer re-emission from ~7s to <0.5s.
            """
            for i in range(0, len(text), _BULK_SIZE):
                sub = text[i:i + _BULK_SIZE]
                await _push({
                    "type": "answer_delta",
                    "content": sub,
                    "node": "tutor_agent",
                })

        # Sprint 148: Track phase transitions for rate limiting and double-close prevention
        _phase_transition_count = 0
        _last_tool_was_progress = False

        # ReAct Loop
        for iteration in range(max_iterations):
            logger.info("[TUTOR_AGENT] ReAct iteration %d/%d", iteration + 1, max_iterations)
            _last_tool_was_progress = False  # Reset at start of each iteration

            # THINK: LLM reasons and decides action
            # Sprint 70: Stream LLM tokens for true interleaved thinking
            if event_queue is not None:
                # Sprint 146b: Context-aware label
                _beat = await _iteration_beat(
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
                    "details": {"phase": _beat.phase},
                })
                if _beat.summary:
                    await _push_thinking_deltas(f"{_beat.summary}\n\n")
                response = None
                chunk_count = 0
                pre_tool_stream_text = ""
                async for chunk in llm_with_tools.astream(messages):
                    chunk_count += 1
                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk
                    # Sprint 70: Extract text and sub-chunk for smooth streaming
                    text = _extract_chunk_text(chunk.content)
                    if text:
                        pre_tool_stream_text += text
                logger.debug("[TUTOR_AGENT] .astream() yielded %d chunks", chunk_count)
                if response is None:
                    # Empty response fallback
                    from langchain_core.messages import AIMessage as _AIMsg
                    response = _AIMsg(content="")
                # Sprint 146b: DO NOT emit thinking_end here — keep block open for tool execution
            else:
                response = await llm_with_tools.ainvoke(messages)

            # Check if LLM wants to call tools
            if not response.tool_calls:
                # Sprint 146b: Close thinking block when no tool calls needed
                if event_queue is not None:
                    await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})
                # No tool calls = LLM is done, extract final response AND thinking
                final_response, llm_thinking = self._extract_content_with_thinking(response.content)
                # Keep public thinking compact: summary stays in the thinking lane,
                # final prose only streams into the answer lane.
                if event_queue is not None:
                    _answer_streamed_via_bus = True
                    if final_response:
                        await _push_answer_bulk(final_response)
                logger.info("[TUTOR_AGENT] No more tool calls, generating final response")
                break

            if event_queue is not None and pre_tool_stream_text.strip():
                # If the model decided to call tools, surface the pre-tool draft as
                # a single reasoning beat instead of duplicating it into the answer.
                await _push_thinking_deltas(pre_tool_stream_text)

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
                
                if tool_name in ("tool_knowledge_search", "tool_maritime_search"):
                    try:
                        # Execute the tool
                        search_query = tool_args.get("query", query)
                        result = await invoke_tool_with_runtime(
                            tool_knowledge_search,
                            {"query": search_query},
                            tool_name=tool_name,
                            runtime_context_base=runtime_context_base,
                            tool_call_id=tool_id,
                            query_snippet=search_query,
                        )

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": f"Tra cứu: {search_query[:60]}..." if len(search_query) > 60 else f"Tra cứu: {search_query}",
                            "iteration": iteration + 1
                        })

                        # Sprint 69: Push tool_result event
                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        # Sprint 146b: Post-tool acknowledgment
                        _ack = await _tool_acknowledgment(
                            query=query,
                            context=context,
                            tool_name=tool_name,
                            result=result,
                        )
                        await _push_thinking_deltas(f"\n\n{_ack}")

                        # OBSERVE: Add result to conversation
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id
                        ))

                        logger.info("[TUTOR_AGENT] Tool result length: %d", len(str(result)))

                        # ============================================================
                        # SOTA 2025 Phase 2: Confidence-Based Early Termination
                        # Pattern: Focused ReAct (arXiv Oct 2024) - exit on first success
                        # Lowered threshold from 0.85 to 0.70 to match CRAG confidence
                        # ============================================================
                        confidence, is_complete = get_last_confidence()
                        if is_complete and confidence >= 0.70:  # PHASE 2: 0.85 → 0.70
                            logger.info("[TUTOR_AGENT] MEDIUM+ confidence (%.2f) - EARLY TERMINATION", confidence)
                            logger.info("[TUTOR_AGENT] Skipping %d remaining iterations (Focused ReAct)", max_iterations - iteration - 1)
                            break
                        elif confidence >= 0.50:
                            logger.info("[TUTOR_AGENT] LOW-MEDIUM confidence (%.2f) - one more try", confidence)
                        else:
                            logger.info("[TUTOR_AGENT] LOW confidence (%.2f) - will retry", confidence)

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] Tool error: %s", e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id
                        ))
                elif tool_name in ("tool_calculator", "tool_current_datetime", "tool_web_search"):
                    try:
                        # Execute utility/web tools
                        if tool_name == "tool_calculator":
                            tool_input = tool_args.get("expression", "")
                            result = await invoke_tool_with_runtime(
                                tool_calculator,
                                tool_input,
                                tool_name=tool_name,
                                runtime_context_base=runtime_context_base,
                                tool_call_id=tool_id,
                                query_snippet=tool_input,
                            )
                            desc = f"Tính toán: {tool_input[:60]}"
                        elif tool_name == "tool_current_datetime":
                            tool_input = tool_args.get("dummy", "")
                            result = await invoke_tool_with_runtime(
                                tool_current_datetime,
                                tool_input,
                                tool_name=tool_name,
                                runtime_context_base=runtime_context_base,
                                tool_call_id=tool_id,
                            )
                            desc = "Xem ngày giờ hiện tại"
                        else:  # tool_web_search
                            tool_input = tool_args.get("query", query)
                            result = await invoke_tool_with_runtime(
                                tool_web_search,
                                tool_input,
                                tool_name=tool_name,
                                runtime_context_base=runtime_context_base,
                                tool_call_id=tool_id,
                                query_snippet=tool_input,
                            )
                            desc = f"Tìm web: {tool_input[:60]}"

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": desc,
                            "iteration": iteration + 1
                        })

                        # Sprint 69: Push tool_result event
                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        # Sprint 146b: Post-tool acknowledgment
                        _ack = await _tool_acknowledgment(
                            query=query,
                            context=context,
                            tool_name=tool_name,
                            result=result,
                        )
                        await _push_thinking_deltas(f"\n\n{_ack}")

                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id
                        ))

                        logger.info("[TUTOR_AGENT] %s result length: %d", tool_name, len(str(result)))

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] %s error: %s", tool_name, e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id
                        ))

                elif tool_name == "tool_think":
                    # Sprint 148: Think tool → emit thought as thinking_delta, no tool card
                    thought = tool_args.get("thought", "")
                    if thought:
                        await _push_thinking_deltas(f"\n\n{thought}")
                    messages.append(AIMessage(content="", tool_calls=[tool_call]))
                    messages.append(ToolMessage(
                        content=f"[Thought recorded: {len(thought)} chars]",
                        tool_call_id=tool_id,
                    ))
                    logger.info("[TUTOR_AGENT] Think tool: %d chars", len(thought))

                elif tool_name == "tool_report_progress":
                    # Sprint 148: Phase transition — close block → action_text → open new block
                    progress_msg = tool_args.get("message", "")
                    next_beat = await _iteration_beat(
                        query=query,
                        context=context,
                        iteration=iteration,
                        tools_used=tools_used,
                        phase_label=tool_args.get("phase_label", ""),
                    )
                    next_label = tool_args.get("phase_label", "") or "Tiếp tục phân tích"

                    # Rate-limit: max _MAX_PHASE_TRANSITIONS per request
                    if _phase_transition_count < _MAX_PHASE_TRANSITIONS:
                        if event_queue is not None:
                            # 1. Close current thinking block
                            await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})
                            # 2. Emit bold narrative (action_text)
                            if progress_msg:
                                await _push({"type": "action_text", "content": progress_msg, "node": "tutor_agent"})
                            # 3. Open new thinking block with next phase label
                            await _push({
                                "type": "thinking_start",
                                "content": next_beat.label,
                                "node": "tutor_agent",
                                "summary": next_beat.summary,
                                "details": {"phase": next_beat.phase},
                            })
                            if next_beat.summary:
                                await _push_thinking_deltas(f"{next_beat.summary}\n\n")
                        _phase_transition_count += 1
                        _last_tool_was_progress = True
                    else:
                        logger.warning("[TUTOR_AGENT] Phase transition rate limit reached (%d)", _MAX_PHASE_TRANSITIONS)

                    messages.append(AIMessage(content="", tool_calls=[tool_call]))
                    messages.append(ToolMessage(
                        content=f"[Progress reported. Next phase: {next_label}]",
                        tool_call_id=tool_id,
                    ))
                    logger.info("[TUTOR_AGENT] Phase transition: '%s' -> '%s'", progress_msg, next_label)

                elif tool_name in ("tool_character_note", "tool_character_read"):
                    try:
                        # Sprint 95: Find matching character tool
                        char_tool = get_tool_by_name(tools, tool_name)
                        if char_tool:
                            result = await invoke_tool_with_runtime(
                                char_tool,
                                tool_args,
                                tool_name=tool_name,
                                runtime_context_base=runtime_context_base,
                                tool_call_id=tool_id,
                                run_sync_in_thread=True,
                            )
                            desc = f"Character: {tool_name.replace('tool_character_', '')}"
                        else:
                            result = f"Tool {tool_name} not available"
                            desc = tool_name

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": desc,
                            "iteration": iteration + 1,
                        })

                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        # Sprint 146b: Post-tool acknowledgment
                        _ack = await _tool_acknowledgment(
                            query=query,
                            context=context,
                            tool_name=tool_name,
                            result=result,
                        )
                        await _push_thinking_deltas(f"\n\n{_ack}")

                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        ))

                        logger.info("[TUTOR_AGENT] Character tool %s done", tool_name)

                    except Exception as e:
                        logger.error("[TUTOR_AGENT] Character tool %s error: %s", tool_name, e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                        ))

                else:
                    try:
                        matched_tool = get_tool_by_name(tools, tool_name)
                        if matched_tool is None:
                            raise ValueError(f"Tool {tool_name} not available")

                        result = await invoke_tool_with_runtime(
                            matched_tool,
                            tool_args,
                            tool_name=tool_name,
                            runtime_context_base=runtime_context_base,
                            tool_call_id=tool_id,
                            run_sync_in_thread=True,
                        )

                        tools_used.append({
                            "name": tool_name,
                            "args": tool_args,
                            "description": f"Tool: {tool_name}",
                            "iteration": iteration + 1,
                        })

                        await _push({
                            "type": "tool_result",
                            "content": {
                                "name": tool_name,
                                "result": str(result)[:500],
                                "id": tool_id,
                            },
                            "node": "tutor_agent",
                        })

                        _ack = await _tool_acknowledgment(
                            query=query,
                            context=context,
                            tool_name=tool_name,
                            result=result,
                        )
                        await _push_thinking_deltas(f"\n\n{_ack}")

                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        ))
                    except Exception as e:
                        logger.error("[TUTOR_AGENT] Generic tool %s error: %s", tool_name, e)
                        messages.append(AIMessage(content="", tool_calls=[tool_call]))
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                        ))

            # Sprint 146b: Close thinking block after all tool executions
            # Sprint 148: Don't double-close if tool_report_progress already closed the block
            if event_queue is not None and not _last_tool_was_progress:
                await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

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
            try:
                # Sprint 74: Stream final generation as answer_delta (not thinking_delta)
                # This gives real-time answer streaming — TTFT drops from ~36s to ~15s
                if event_queue is not None:
                    final_msg = None
                    async for chunk in self._llm.astream(messages):
                        if final_msg is None:
                            final_msg = chunk
                        else:
                            final_msg = final_msg + chunk
                        # Sprint 74: Stream as answer_delta for real-time answer display
                        text = _extract_chunk_text(chunk.content)
                        if text:
                            await _push_answer_deltas(text)
                    if final_msg is not None:
                        final_response, llm_thinking = self._extract_content_with_thinking(final_msg.content)
                        _answer_streamed_via_bus = True  # Sprint 74: answer already streamed
                    else:
                        final_response = "Hmm, có gì đó trục trặc rồi. Bạn thử hỏi lại mình nhé!"
                else:
                    final_msg = await self._llm.ainvoke(messages)
                    final_response, llm_thinking = self._extract_content_with_thinking(final_msg.content)
            except Exception as e:
                logger.error("[TUTOR_AGENT] Final generation error: %s", e)
                final_response = "Hmm, có gì đó trục trặc rồi. Bạn thử hỏi lại mình nhé!"
        
        # Get sources from tool calls
        sources = get_last_retrieved_sources()
        
        # CHỈ THỊ SỐ 29 v9: Get RAG thinking from tool (Option B+)
        rag_thinking = get_last_native_thinking()
        
        # Combine thinking: prioritize RAG thinking (deeper analysis) 
        # but include LLM thinking if RAG thinking unavailable
        combined_thinking = None
        if rag_thinking and llm_thinking:
            combined_thinking = f"[RAG Analysis]\n{rag_thinking}\n\n[Teaching Process]\n{llm_thinking}"
        elif rag_thinking:
            combined_thinking = rag_thinking
        elif llm_thinking:
            combined_thinking = llm_thinking
        
        if combined_thinking:
            logger.info("[TUTOR_AGENT] Combined thinking: %d chars (rag=%s, llm=%s)", len(combined_thinking), bool(rag_thinking), bool(llm_thinking))
        
        return final_response, sources, tools_used, combined_thinking, _answer_streamed_via_bus

    def _fallback_response(self, query: str) -> str:
        """Fallback when LLM unavailable."""
        return f"""Tôi sẽ giúp bạn với: "{query}"

Để học hiệu quả, bạn nên:
1. Đọc tài liệu gốc liên quan
2. Xem các ví dụ thực tế
3. Làm bài tập thực hành

Bạn muốn tôi giải thích khái niệm nào cụ thể?"""
    
    def _extract_content_with_thinking(self, content) -> tuple[str, Optional[str]]:
        """
        Extract text AND thinking from LLM response content.

        CHỈ THỊ SỐ 29 v9: Option B+ - Returns thinking for state propagation.
        This is the SOTA pattern for reasoning transparency (Anthropic/OpenAI).

        Sprint 64 fix: Gemini sometimes wraps entire response in <thinking> tags
        or returns empty text with content only in native thinking blocks.
        When text is empty but thinking is substantial, recover thinking as response.

        Args:
            content: Response content from LLM

        Returns:
            Tuple of (text, thinking) where thinking may be None
        """
        text, thinking = extract_thinking_from_response(content)
        clean_text = text.strip() if text else ""

        # Log thinking if extracted
        if thinking:
            logger.info("[TUTOR] Native thinking extracted: %d chars", len(thinking))

        # Gemini quirk: Sometimes model wraps entire response in <thinking> tags
        # or native thinking format returns empty text. Recover the response.
        if not clean_text and thinking and len(thinking) > 50:
            logger.warning(
                "[TUTOR] Response empty but thinking has content (%d chars), "
                "recovering thinking as response text",
                len(thinking),
            )
            return thinking.strip(), None

        return clean_text, thinking
    
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
