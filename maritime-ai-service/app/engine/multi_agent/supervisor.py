"""
Supervisor Agent - Phase 8.2 + Sprint 71 + Sprint 103

Coordinator agent that routes queries to specialized agents.

Pattern: LangGraph Supervisor with tool-based handoffs

Sprint 103: LLM-First Routing (SOTA 2026)
- Structured output (_route_structured) is now the PRIMARY and ONLY LLM path
- _route_legacy() deleted, feature flag check removed
- LEARNING_KEYWORDS, LOOKUP_KEYWORDS, WEB_KEYWORDS deleted (~80 keywords)
- _rule_based_route() simplified to 4 guardrail checks (social, personal, domain, default)
- New web_search intent in RoutingDecision for news/legal/maritime search queries
- Off-topic + web_search intent override → DIRECT (prevents false domain_notices)

Sprint 71: SOTA Routing (foundation)
- Chain-of-thought reasoning prompt with few-shot Vietnamese examples
- Confidence-gated structured output (low confidence → rule-based override)
- Routing metadata for observability (intent, confidence, reasoning, method)

**Integrated with agents/ framework for config and tracing.**
"""

import logging
from typing import Optional
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.resilience import retry_on_transient
from app.engine.character.character_card import (
    build_supervisor_card_prompt,
    build_synthesis_card_prompt,
)
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)


def _store_capability_context(state: AgentState, capability_context: str) -> None:
    """Keep handbook guidance separate from domain skill content."""
    if capability_context:
        state["capability_context"] = capability_context


class AgentType(str, Enum):
    """Available agent types."""
    RAG = "rag_agent"
    TUTOR = "tutor_agent"
    MEMORY = "memory_agent"
    DIRECT = "direct"
    CODE_STUDIO = "code_studio_agent"
    PRODUCT_SEARCH = "product_search_agent"  # Sprint 148
    COLLEAGUE = "colleague_agent"            # Sprint 215


# =============================================================================
# Sprint 71: SOTA Routing Prompt with CoT and Few-Shot Examples
# =============================================================================

ROUTING_PROMPT_TEMPLATE = """Bạn là Supervisor Agent cho hệ thống {domain_name}.

**User Role:** {user_role}

## Phân tích theo bước:
1. Xác định intent: lookup (tra cứu) | learning (dạy/giải thích/quiz) | personal (cá nhân) | social (chào hỏi) | off_topic (không liên quan) | web_search (tìm kiếm web/tin tức/pháp luật) | product_search (tìm/so sánh sản phẩm/giá cả trên sàn TMĐT) | colleague_consult (hỏi Bro/đồng nghiệp về trading/crypto/rủi ro — CHỈ khi user_role=admin)
2. Xác định domain: có THỰC SỰ liên quan {domain_name} hay không? (Lưu ý: "tàu" có thể là tàu hỏa, không phải tàu thủy)
3. Chọn agent dựa trên intent + domain + user_role

## Agent Mapping:
- RAG_AGENT: intent=lookup VÀ CÓ domain keyword RÕ RÀNG → tra cứu quy định, luật, mức phạt. {rag_description}
- TUTOR_AGENT: intent=learning VÀ CÓ domain keyword → giải thích, quiz, ôn bài, dạy kiến thức. {tutor_description}
- MEMORY_AGENT: intent=personal → lịch sử học, preferences, nhớ thông tin
- CODE_STUDIO_AGENT: intent=code_execution → viết/chạy code, tạo biểu đồ/chart, tạo file (HTML/Excel/Word/PDF), chụp trang web, xử lý dữ liệu, tạo artifact kỹ thuật
- PRODUCT_SEARCH_AGENT: intent=product_search → tìm kiếm sản phẩm, so sánh giá, mua hàng trên sàn TMĐT (Shopee, Lazada, TikTok Shop, Google Shopping, Facebook Marketplace)
- COLLEAGUE_AGENT: intent=colleague_consult VÀ user_role=admin → hỏi ý kiến Bro về trading, crypto, rủi ro thị trường, liquidation
- DIRECT: intent=social HOẶC intent=off_topic HOẶC intent=web_search → chào hỏi, cảm ơn, tạm biệt, câu NGOÀI chuyên môn, tìm kiếm web/tin tức/pháp luật. DIRECT KHÔNG tạo file, KHÔNG chạy code, KHÔNG vẽ biểu đồ — những việc đó thuộc CODE_STUDIO_AGENT

## Quy tắc QUAN TRỌNG:
- "quiz/giải thích/dạy/ôn bài" + domain keyword → TUTOR_AGENT (NOT RAG_AGENT)
- "tra cứu/cho biết/nội dung/quy định" + domain keyword → RAG_AGENT
- Câu hỏi ngắn < 10 ký tự không có domain keyword → DIRECT
- "tên tôi là/tên mình là/nhớ giúp/bạn có nhớ" → MEMORY_AGENT
- "tìm sản phẩm/mua hàng/so sánh giá/tìm trên shopee/lazada/tiktok shop" → PRODUCT_SEARCH_AGENT (intent=product_search)
- "tìm trên web/mạng/internet", "search", "thông tin mới nhất", "tin tức" → DIRECT (intent=web_search, DIRECT có tool tìm kiếm web)
- "nghị định", "thông tư", "văn bản pháp luật" → DIRECT (intent=web_search, DIRECT có tool_search_legal)
- "tin tức hàng hải", "maritime news", "shipping news" → DIRECT (intent=web_search, DIRECT có tool_search_maritime)
- Câu hỏi KHÔNG liên quan {domain_name} → DIRECT (kể cả khi dài, kể cả khi có từ "tàu" nhưng ngữ cảnh không phải hàng hải)
- Từ "tàu" một mình CHƯA ĐỦ để xác định domain — cần thêm ngữ cảnh hàng hải (COLREGs, hải đồ, thuyền trưởng, v.v.)

## Ví dụ:
- "Điều 15 COLREGs nói gì?" → intent=lookup, agent=RAG_AGENT, confidence=0.95
- "Giải thích Điều 15 COLREGs" → intent=learning, agent=TUTOR_AGENT, confidence=0.95
- "Quiz về SOLAS" → intent=learning, agent=TUTOR_AGENT, confidence=0.90
- "Xin chào" → intent=social, agent=DIRECT, confidence=1.0
- "Tên tôi là Nam" → intent=personal, agent=MEMORY_AGENT, confidence=0.95
- "Mức phạt vượt đèn đỏ?" → intent=lookup, agent=RAG_AGENT, confidence=0.90
- "Dạy tôi về biển báo" → intent=learning, agent=TUTOR_AGENT, confidence=0.90
- "Trên tàu đói quá thì làm gì?" → intent=off_topic, agent=DIRECT, confidence=0.95 (nấu ăn, không phải hàng hải)
- "Nấu cơm trên tàu" → intent=off_topic, agent=DIRECT, confidence=0.90 (ẩm thực, không phải hàng hải)
- "Hôm nay thời tiết thế nào?" → intent=off_topic, agent=DIRECT, confidence=0.95 (không liên quan domain)
- "Python là gì?" → intent=off_topic, agent=DIRECT, confidence=0.95 (lập trình, không phải hàng hải)
- "Tìm trên web luật giao thông mới nhất" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có web search tool)
- "Search thông tin mới nhất về AI" → intent=web_search, agent=DIRECT, confidence=0.90
- "Nghị định 100 về phạt giao thông" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có tool_search_legal)
- "Tin tức hàng hải hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có tool_search_maritime)
- "Tàu thủy phải mang bao nhiêu áo phao?" → intent=lookup, agent=RAG_AGENT, confidence=0.95 (hàng hải rõ ràng)
- "Quy tắc nhường đường trên biển" → intent=lookup, agent=RAG_AGENT, confidence=0.95
- "Thời sự hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95
- "Giá vàng hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95
- "Tìm cuộn dây điện 3 ruột 2.5mm²" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "So sánh giá máy khoan Bosch trên Shopee và Lazada" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "Mua ốp lưng iPhone 16 ở đâu rẻ nhất?" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.90
- "Tìm trên shopee áo khoác nam" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "Hỏi Bro về BTC" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Tình hình liquidation thế nào Bro?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Bro ơi, thị trường crypto hôm nay sao?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Bro đánh giá rủi ro thế nào?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.90 (CHỈ khi user_role=admin)
- "Viết code Python tính diện tích tam giác" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Tạo biểu đồ so sánh doanh thu" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Xuất file Excel danh sách" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Tạo báo cáo Word" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.90
- "Chụp trang web https://example.com" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Vẽ chart thống kê" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95

**Query:** {query}

**User Context:** {context}"""

SYNTHESIS_PROMPT = """Tổng hợp các outputs từ agents thành câu trả lời cuối cùng cho HỌC VIÊN:

Query gốc: {query}

Outputs:
{outputs}

QUY TẮC:
- Trả lời trực tiếp cho học viên, KHÔNG viết ở ngôi thứ nhất về quá trình suy nghĩ
- KHÔNG bao gồm "tôi đang phân tích", "tôi nhận thấy", "tôi đang xem xét"
- KHÔNG bao gồm <thinking> tags hoặc nội dung suy luận nội bộ
- Giữ ngắn gọn (tối đa 500 từ), tự nhiên, thân thiện
- Trả lời bằng tiếng Việt
- KHÔNG bắt đầu bằng "Chào bạn", "Chào" hoặc lời chào nếu đây là cuộc trò chuyện đang diễn ra

Tạo câu trả lời:"""

# Sprint 203: Natural synthesis prompt (OpenClaw: soul-aligned, no artificial limits)
SYNTHESIS_PROMPT_NATURAL = """Tổng hợp các outputs từ agents thành câu trả lời cuối cùng.

Query gốc: {query}

Outputs:
{outputs}

PHONG CÁCH:
- Trả lời trực tiếp, tự nhiên, viết ở ngôi thứ hai
- Trả lời bằng tiếng Việt, giọng ấm áp thân thiện
- Độ dài tùy theo nội dung — ngắn khi đơn giản, chi tiết khi phức tạp
- Đi thẳng vào nội dung — thể hiện sự hiểu biết qua câu trả lời, không qua lời mở đầu

Tạo câu trả lời:"""


# =============================================================================
# Sprint 71: Keyword Lists for Intent-Aware Routing
# =============================================================================

SOCIAL_KEYWORDS = [
    "xin chào", "hello", "chào bạn", "chào",
    "cảm ơn", "thank", "thanks", "tạm biệt", "bye",
    "goodbye", "hẹn gặp lại",
]

PERSONAL_KEYWORDS = [
    "tên tôi", "tên mình", "my name",
    "nhớ giúp", "nhớ cho tôi", "remember",
    "lần trước", "last time", "hôm trước",
    "tôi tên là", "tên mình là", "mình tên là",
    "thông tin của tôi", "thông tin của mình",
    "bạn có nhớ", "bạn nhớ",
    "tuổi tôi", "tuổi mình", "nghề của tôi",
]

CODE_STUDIO_KEYWORDS = [
    "python", "code", "viet code", "chay code", "chay python",
    "javascript", "js", "typescript", "ts", "html", "css", "react",
    "landing page", "website", "web app", "microsite",
    "bieu do", "chart", "plot", "matplotlib", "pandas", "seaborn",
    "png", "svg", "canvas", "artifact", "sandbox",
    # Visual/simulation — route to code_studio for richer code generation
    "mo phong", "simulation", "simulate", "simulator",
    "animation", "animate", "animated",
    "interactive diagram", "tuong tac",
]


# Sprint 103: LEARNING_KEYWORDS, LOOKUP_KEYWORDS, WEB_KEYWORDS deleted.
# LLM structured routing (_route_structured) handles all nuanced decisions.
# Only SOCIAL_KEYWORDS and PERSONAL_KEYWORDS kept as guardrails.

# Confidence threshold for rule-based override
CONFIDENCE_THRESHOLD = 0.7

# Sprint 163 Phase 4: Parallel dispatch thresholds
_COMPLEX_QUERY_MIN_LENGTH = 80
_MIXED_INTENT_PAIRS = [
    # (lookup signal, learning signal) → needs both RAG and Tutor
    ("tra cứu", "giải thích"),
    ("nội dung", "dạy"),
    ("quy định", "giải thích"),
    ("luật", "quiz"),
    ("cho biết", "hướng dẫn"),
    ("thông tin", "phân tích"),
]


def _normalize_router_text(text: str) -> str:
    """Normalize routing text for capability guardrails."""
    return " ".join((text or "").lower().split())


def _needs_code_studio(query: str) -> bool:
    """Detect requests that should route to the code studio capability."""
    normalized = _normalize_router_text(query)
    return any(kw in normalized for kw in CODE_STUDIO_KEYWORDS)


class SupervisorAgent:
    """
    Supervisor Agent - Coordinates specialized agents.

    Sprint 71: SOTA routing with intent classification, confidence gate,
    and chain-of-thought reasoning.

    Responsibilities:
    - Analyze query intent (lookup/learning/personal/social)
    - Route to appropriate agent with confidence scoring
    - Synthesize final response
    - Quality control
    """

    def __init__(self):
        """Initialize Supervisor Agent."""
        self._llm = None
        self._init_llm()
        logger.info("SupervisorAgent initialized")

    def _init_llm(self):
        """Initialize LLM from shared pool for routing decisions."""
        try:
            # Sprint 69: Use AgentConfigRegistry for per-node LLM config
            self._llm = AgentConfigRegistry.get_llm("supervisor")
            logger.info("SupervisorAgent initialized (via AgentConfigRegistry)")
        except Exception as e:
            logger.error("Failed to initialize Supervisor LLM: %s", e)
            self._llm = None

    async def route(self, state: AgentState) -> str:
        """
        Determine which agent should handle the query.

        Sprint 71: Returns agent name and stores routing_metadata in state.

        Args:
            state: Current agent state

        Returns:
            Agent name to route to
        """
        query = state.get("query", "")
        context = state.get("context", {})
        domain_config = state.get("domain_config", {})

        if not self._llm:
            result = self._rule_based_route(query, domain_config)
            state["routing_metadata"] = {
                "intent": "unknown",
                "confidence": 1.0,
                "reasoning": "rule-based (no LLM)",
                "method": "rule_based",
            }
            return result

        # Build domain-aware routing prompt
        domain_name = domain_config.get("domain_name", "AI")
        rag_desc = domain_config.get("rag_description", "Tra cứu quy định, luật, thủ tục")
        tutor_desc = domain_config.get("tutor_description", "Giải thích, dạy học, quiz")

        try:
            # Sprint 103: Always use structured routing (no feature flag check)
            return await self._route_structured(query, context, domain_name, rag_desc, tutor_desc, domain_config, state)

        except Exception as e:
            logger.warning("LLM routing failed: %s", e)
            result = self._rule_based_route(query, domain_config)
            state["routing_metadata"] = {
                "intent": "unknown",
                "confidence": 1.0,
                "reasoning": "rule-based fallback (LLM routing unavailable)",
                "method": "rule_based",
            }
            return result

    @retry_on_transient()
    async def _route_structured(self, query: str, context: dict, domain_name: str,
                                 rag_desc: str, tutor_desc: str, domain_config: dict,
                                 state: AgentState) -> str:
        """Route using structured output with CoT and confidence gate (Sprint 71)."""
        from app.engine.structured_schemas import RoutingDecision

        structured_llm = self._llm.with_structured_output(RoutingDecision)

        # Sprint 77+78: Give supervisor last 3 exchanges + running summary for routing
        lc_messages = (context or {}).get("langchain_messages", [])
        conv_summary = (context or {}).get("conversation_summary", "")
        if lc_messages:
            recent_turns = "\n".join(
                f"{'User' if getattr(m, 'type', '') == 'human' else 'AI'}: {m.content[:200]}"
                for m in lc_messages[-6:]
            )
            context_str = f"Recent conversation:\n{recent_turns}"
            if conv_summary:
                context_str = f"Summary of earlier conversation:\n{conv_summary[:300]}\n\n{context_str}"
        else:
            context_str = str(context)[:500]

        capability_context = state.get("capability_context", "")
        if capability_context:
            context_str = f"{context_str}\n\n{capability_context}"

        # Sprint 215: Extract user_role for colleague routing
        user_role = (context or {}).get("user_role") or (context or {}).get("role") or "student"

        messages = [
            SystemMessage(content=build_supervisor_card_prompt()),
            SystemMessage(content="You are a query router. Analyze the query step by step, classify intent, choose agent, and provide confidence."),
            HumanMessage(content=ROUTING_PROMPT_TEMPLATE.format(
                domain_name=domain_name,
                rag_description=rag_desc,
                tutor_description=tutor_desc,
                query=query,
                context=context_str,
                user_role=user_role,
            ))
        ]

        result = await structured_llm.ainvoke(messages)

        agent_map = {
            "RAG_AGENT": AgentType.RAG.value,
            "TUTOR_AGENT": AgentType.TUTOR.value,
            "MEMORY_AGENT": AgentType.MEMORY.value,
            "DIRECT": AgentType.DIRECT.value,
            "CODE_STUDIO_AGENT": AgentType.CODE_STUDIO.value,
            "PRODUCT_SEARCH_AGENT": AgentType.PRODUCT_SEARCH.value,
            "COLLEAGUE_AGENT": AgentType.COLLEAGUE.value,
        }

        chosen_agent = agent_map.get(result.agent, AgentType.DIRECT.value)
        method = "structured"

        logger.info("[SUPERVISOR] CoT: %s → %s (conf=%.2f, intent=%s)",
                     result.reasoning, result.agent, result.confidence, result.intent)

        # Sprint 71: Confidence gate — if LLM is unsure, validate with rules
        if result.confidence < CONFIDENCE_THRESHOLD:
            rule_result = self._rule_based_route(query, domain_config)
            if rule_result != chosen_agent:
                logger.info("[SUPERVISOR] Low confidence override: %s → %s (conf=%.2f)",
                             result.agent, rule_result, result.confidence)
                chosen_agent = rule_result
                method = "structured+rule_override"

        # Sprint 80+103: Off-topic/web_search intent override — if LLM says off_topic or web_search but routed RAG/TUTOR
        if result.intent in ("off_topic", "web_search") and chosen_agent in (AgentType.RAG.value, AgentType.TUTOR.value):
            logger.info("[SUPERVISOR] Intent override (%s): %s → direct", result.intent, chosen_agent)
            chosen_agent = AgentType.DIRECT.value
            method = "structured+intent_override"

        if result.intent == "code_execution" and chosen_agent != AgentType.CODE_STUDIO.value:
            logger.info("[SUPERVISOR] Intent override (%s): %s -> code_studio_agent", result.intent, chosen_agent)
            chosen_agent = AgentType.CODE_STUDIO.value
            method = "structured+intent_override"

        if _needs_code_studio(query) and chosen_agent in (AgentType.DIRECT.value, AgentType.TUTOR.value):
            logger.info("[SUPERVISOR] Capability override: %s -> code_studio_agent", chosen_agent)
            chosen_agent = AgentType.CODE_STUDIO.value
            method = "structured+capability_override"

        # Visual code-gen override (LLM-first pattern): khi flag bật và query
        # có visual intent rõ ràng, upgrade tới code_studio cho model mạnh hơn.
        # Theo kiểu v0/Claude: LLM quyết output type, model mạnh sinh code đẹp.
        if chosen_agent in (AgentType.TUTOR.value, AgentType.RAG.value):
            from app.core.config import settings as _settings
            if getattr(_settings, "enable_code_gen_visuals", False):
                from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent
                _visual_decision = resolve_visual_intent(query)
                if _visual_decision.force_tool and _visual_decision.mode in ("inline_html", "app"):
                    logger.info(
                        "[SUPERVISOR] Visual code-gen upgrade: %s -> code_studio (mode=%s, reason=%s)",
                        chosen_agent, _visual_decision.mode, _visual_decision.reason,
                    )
                    chosen_agent = AgentType.CODE_STUDIO.value
                    method = "structured+visual_codegen_upgrade"

        # Sprint 148: Product search feature gate — fallback to DIRECT if disabled
        if chosen_agent == AgentType.PRODUCT_SEARCH.value:
            from app.core.config import settings as _settings
            if not _settings.enable_product_search:
                logger.info("[SUPERVISOR] Product search disabled, falling back to DIRECT")
                chosen_agent = AgentType.DIRECT.value
                method = "structured+product_search_disabled"

        # Sprint 215: Colleague agent gate — requires admin role + feature flags
        if chosen_agent == AgentType.COLLEAGUE.value:
            from app.core.config import settings as _settings
            if not _settings.enable_cross_soul_query or user_role != "admin" or not _settings.enable_soul_bridge:
                logger.info("[SUPERVISOR] Colleague query denied (role=%s, cross_soul=%s, bridge=%s), falling back to DIRECT",
                             user_role, _settings.enable_cross_soul_query, _settings.enable_soul_bridge)
                chosen_agent = AgentType.DIRECT.value
                method = "structured+colleague_denied"

        # Sprint 80: Domain keyword validation — catch false positives like "tàu đói"
        pre_validation = chosen_agent
        chosen_agent = self._validate_domain_routing(query, chosen_agent, domain_config)
        if chosen_agent != pre_validation:
            method = "structured+domain_validation"

        # Store routing metadata for observability
        state["routing_metadata"] = {
            "intent": result.intent,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "method": method,
        }

        return chosen_agent

    def _validate_domain_routing(self, query: str, chosen_agent: str,
                                   domain_config: dict = None) -> str:
        """Sprint 80: Post-routing validation — ensure RAG/TUTOR queries have domain signal.

        If LLM routes to RAG/TUTOR but query has NO domain keywords,
        override to DIRECT. This catches false positives like "tàu đói" being
        routed to maritime RAG because LLM sees "tàu".

        Sprint 214: When org knowledge is enabled and org context exists,
        skip keyword check — org KB may contain any topic.
        """
        if chosen_agent not in (AgentType.RAG.value, AgentType.TUTOR.value):
            return chosen_agent

        # Sprint 214: Org knowledge bypass — org users may have non-domain docs
        from app.core.config import settings as _settings
        if _settings.enable_org_knowledge:
            from app.core.org_context import get_current_org_id
            if get_current_org_id():
                logger.info(
                    "[SUPERVISOR] Org knowledge bypass: keeping %s "
                    "(org context present, org_knowledge enabled)", chosen_agent
                )
                return chosen_agent  # Trust LLM routing for org users

        domain_keywords = self._get_domain_keywords(domain_config)
        if not domain_keywords:
            return chosen_agent  # No keywords to validate against

        query_lower = query.lower()
        has_domain = any(kw in query_lower for kw in domain_keywords)

        if not has_domain:
            logger.info(
                "[SUPERVISOR] Domain validation override: %s → direct "
                "(no domain keywords in query)", chosen_agent
            )
            return AgentType.DIRECT.value

        return chosen_agent

    def _rule_based_route(self, query: str, domain_config: dict = None) -> str:
        """Minimal rule-based routing — guardrail fallback only (Sprint 103).

        Only handles trivially obvious cases when LLM is unavailable:
          1. Social (greetings, thanks) → DIRECT
          2. Personal (name, recall) → MEMORY
          3. Domain keyword present → RAG
          4. Default → DIRECT

        All nuanced decisions (learning vs lookup, web search intent, etc.)
        are handled by LLM structured routing (_route_structured).
        """
        query_lower = query.lower()

        # 1. Social intent → DIRECT
        if any(kw in query_lower for kw in SOCIAL_KEYWORDS):
            return AgentType.DIRECT.value

        # 2. Personal intent → MEMORY
        if any(kw in query_lower for kw in PERSONAL_KEYWORDS):
            return AgentType.MEMORY.value

        if _needs_code_studio(query):
            return AgentType.CODE_STUDIO.value

        # 3. Domain keyword → RAG
        domain_keywords = self._get_domain_keywords(domain_config)
        if any(kw in query_lower for kw in domain_keywords):
            return AgentType.RAG.value

        # 4. Default → DIRECT
        return AgentType.DIRECT.value

    def _get_domain_keywords(self, domain_config: dict = None) -> list:
        """Extract domain routing keywords from config or registry fallback."""
        domain_keywords = []
        if domain_config and domain_config.get("routing_keywords"):
            for kw_group in domain_config["routing_keywords"]:
                domain_keywords.extend(
                    k.strip().lower() for k in kw_group.split(",")
                )

        # Fallback: load from default domain plugin
        if not domain_keywords:
            try:
                from app.domains.registry import get_domain_registry
                from app.core.config import settings
                registry = get_domain_registry()
                domain = registry.get(settings.default_domain)
                if domain:
                    config = domain.get_config()
                    domain_keywords = [kw.lower() for kw in (config.routing_keywords or [])]
            except Exception as e:
                logger.debug("Failed to load domain keywords: %s", e)

        return domain_keywords

    async def synthesize(self, state: AgentState) -> str:
        """
        Synthesize final response from agent outputs.

        Args:
            state: State with agent outputs

        Returns:
            Final synthesized response
        """
        outputs = state.get("agent_outputs", {})

        # If only one output, return it directly
        if len(outputs) == 1:
            return list(outputs.values())[0]

        # If no outputs, return error
        if not outputs:
            return "Xin lỗi, tôi không thể xử lý yêu cầu này."

        # Synthesize multiple outputs
        if not self._llm:
            # Simple concatenation
            return "\n\n".join(outputs.values())

        try:
            output_text = "\n---\n".join([
                f"[{k}]: {v}" for k, v in outputs.items()
            ])

            # Sprint 203: Use natural prompt when enabled (no word limits)
            from app.core.config import get_settings as _get_synth_settings
            try:
                _synth_s = _get_synth_settings()
                _synth_prompt = SYNTHESIS_PROMPT_NATURAL if getattr(_synth_s, "enable_natural_conversation", False) is True else SYNTHESIS_PROMPT
            except Exception as e:
                logger.debug("Natural conversation config unavailable: %s", e)
                _synth_prompt = SYNTHESIS_PROMPT

            # Sprint 222: Include host context in synthesis
            _host_prompt = state.get("host_context_prompt", "")
            _host_suffix = f"\n\nHost Context:\n{_host_prompt}" if _host_prompt else ""
            _widget_feedback_prompt = state.get("widget_feedback_prompt", "")
            _widget_suffix = (
                f"\n\nWidget Feedback Context:\n{_widget_feedback_prompt}"
                if _widget_feedback_prompt else ""
            )

            messages = [
                SystemMessage(content=build_synthesis_card_prompt()),
                HumanMessage(content=_synth_prompt.format(
                    query=state.get("query", ""),
                    outputs=output_text
                ) + _host_suffix + _widget_suffix)
            ]

            response = await self._llm.ainvoke(messages)

            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, _ = extract_thinking_from_response(response.content)
            return text_content.strip()

        except Exception as e:
            logger.warning("Synthesis failed: %s", e)
            return list(outputs.values())[0]  # Return first output

    def _is_complex_query(self, query: str, routing_metadata: dict) -> bool:
        """Heuristic: does this query benefit from parallel dispatch?

        Returns True when the query is long AND shows mixed-intent signals
        (e.g., both lookup and learning keywords).  Short or single-intent
        queries should use the normal single-agent path.
        """
        if len(query) < _COMPLEX_QUERY_MIN_LENGTH:
            return False

        query_lower = query.lower()

        # Check for mixed intent signals
        for lookup_kw, learning_kw in _MIXED_INTENT_PAIRS:
            if lookup_kw in query_lower and learning_kw in query_lower:
                return True

        # Check routing metadata for borderline confidence
        confidence = routing_metadata.get("confidence", 1.0)
        if confidence < 0.75 and len(query) > 120:
            return True

        return False

    async def process(self, state: AgentState) -> AgentState:
        """
        Process state as supervisor node.

        Args:
            state: Current state

        Returns:
            Updated state with routing decision, skill context, and routing metadata
        """
        # Skill Activation: match query against domain skills (progressive disclosure)
        domain_id = state.get("domain_id", "")
        query = state.get("query", "")
        if domain_id and query:
            try:
                from app.domains.registry import get_domain_registry
                registry = get_domain_registry()
                domain_plugin = registry.get(domain_id)
                if domain_plugin:
                    matched_skills = domain_plugin.match_skills(query)
                    if matched_skills:
                        skill = matched_skills[0]  # Use top match
                        skill_content = domain_plugin.activate_skill(skill.id)
                        if skill_content:
                            state["skill_context"] = skill_content
                            logger.info("[SUPERVISOR] Skill activated: %s (%d chars)", skill.id, len(skill_content))
            except Exception as e:
                logger.debug("Skill activation skipped: %s", e)

        if query:
            try:
                from app.engine.skills.skill_handbook import get_skill_handbook

                capability_context = get_skill_handbook().summarize_for_query(query, max_entries=3)
                if capability_context:
                    _store_capability_context(state, capability_context)
            except Exception as e:
                logger.debug("Capability handbook summary skipped: %s", e)

        # Route to appropriate agent (also sets routing_metadata in state)
        next_agent = await self.route(state)

        try:
            from app.engine.skills.skill_handbook import get_skill_handbook

            routed_intent = (state.get("routing_metadata") or {}).get("intent")
            capability_context = get_skill_handbook().summarize_for_query(
                query,
                intent=routed_intent,
                max_entries=3,
            )
            if capability_context:
                _store_capability_context(state, capability_context)
        except Exception as e:
            logger.debug("Post-routing capability handbook summary skipped: %s", e)

        # Sprint 163 Phase 4: Parallel dispatch for complex queries
        try:
            from app.core.config import settings as _settings
            if (
                _settings.enable_subagent_architecture
                and next_agent in (
                    AgentType.RAG.value,
                    AgentType.TUTOR.value,
                    AgentType.PRODUCT_SEARCH.value,
                )
                and self._is_complex_query(query, state.get("routing_metadata") or {})
            ):
                from app.engine.multi_agent.orchestration_planner import plan_parallel_targets

                planned_targets = plan_parallel_targets(
                    query,
                    next_agent,
                    intent=(state.get("routing_metadata") or {}).get("intent"),
                    max_targets=2,
                )
                if len(planned_targets) > 1:
                    logger.info("[SUPERVISOR] Complex query detected → parallel_dispatch %s", planned_targets)
                    next_agent = "parallel_dispatch"
                    state["_parallel_targets"] = planned_targets
        except Exception as e:
            logger.debug("Parallel dispatch check failed: %s", e)

        state["next_agent"] = next_agent
        state["current_agent"] = "supervisor"

        metadata = state.get("routing_metadata", {})
        logger.info("[SUPERVISOR] Routing to: %s (method=%s, intent=%s, conf=%.2f)",
                     next_agent,
                     metadata.get("method", "unknown"),
                     metadata.get("intent", "unknown"),
                     metadata.get("confidence", 0.0))

        return state

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None


# Singleton
_supervisor: Optional[SupervisorAgent] = None

def get_supervisor_agent() -> SupervisorAgent:
    """Get or create SupervisorAgent singleton."""
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor
