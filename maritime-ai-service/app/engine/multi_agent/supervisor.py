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

import asyncio
import logging
import re
from typing import Optional
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.core.resilience import retry_on_transient
from app.engine.character.character_card import (
    build_supervisor_card_prompt,
    build_supervisor_micro_card_prompt,
    build_synthesis_card_prompt,
)
from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

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
- CODE_STUDIO_AGENT: intent=code_execution → viết/chạy code, tạo app/widget/mô phỏng, tạo file (HTML/Excel/Word/PDF), chụp trang web, xử lý artifact kỹ thuật
- PRODUCT_SEARCH_AGENT: intent=product_search → tìm kiếm sản phẩm, so sánh giá, mua hàng trên sàn TMĐT (Shopee, Lazada, TikTok Shop, Google Shopping, Facebook Marketplace)
- COLLEAGUE_AGENT: intent=colleague_consult VÀ user_role=admin → hỏi ý kiến Bro về trading, crypto, rủi ro thị trường, liquidation
- DIRECT: intent=social HOẶC intent=off_topic HOẶC intent=web_search → chào hỏi, cảm ơn, tạm biệt, câu NGOÀI chuyên môn, tìm kiếm web/tin tức/pháp luật, và các visual/chart inline để nhìn nhanh khi không cần app hay file. DIRECT KHÔNG tạo file kỹ thuật hoặc app hoàn chỉnh

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
- "Tạo biểu đồ so sánh doanh thu" → intent=off_topic, agent=DIRECT, confidence=0.90
- "Xuất file Excel danh sách" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Tạo báo cáo Word" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.90
- "Chụp trang web https://example.com" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Vẽ chart thống kê" → intent=off_topic, agent=DIRECT, confidence=0.90

**Query:** {query}

**User Context:** {context}"""

COMPACT_ROUTING_PROMPT_TEMPLATE = """Ban la Supervisor Agent cua Wiii.

Nhiem vu: nghe mot turn ngan hoac cau tham do nhanh, roi chon lane xu ly dung nhat.

Chon 1 agent:
- DIRECT: chao hoi, bat nhip, tra loi truc tiep, thac mac ngan, visual/chart inline de nhin nhanh
- CODE_STUDIO_AGENT: user dang goi mot thu co the dung/chay/hien ra duoc theo dang app/widget/mo phong/artifact/file
- RAG_AGENT: tra cuu tri thuc/domain cu the
- TUTOR_AGENT: giai thich/day hoc/quiz
- MEMORY_AGENT: goi lai boi canh ca nhan
- PRODUCT_SEARCH_AGENT: tim/so sanh san pham
- COLLEAGUE_AGENT: hoi Bro, chi khi dung ngu canh admin

Quy tac:
- Vi day la turn ngan, dung nghe nhip cau noi thay vi khop keyword co hoc.
- Neu cau noi dang tham do xem Wiii co the mo phong/dung/hien ra duoc khong theo dang app/widget/mo phong, nghieng ve CODE_STUDIO_AGENT.
- Neu cau noi nghieng ve chart/visual de nhin nhanh, nghieng ve DIRECT de con dung lane visual inline.
- Neu cau noi chi la mot nhip giao tiep hoac cam than, nghieng ve DIRECT.
- Chua du tin hieu domain thi khong ep sang RAG/TUTOR.

Query: {query}
Recent context: {context}
Routing hints: {routing_hints}"""

SYNTHESIS_PROMPT = """Tổng hợp các outputs từ agents thành câu trả lời cuối cùng cho HỌC VIÊN:

Query gốc: {query}

Outputs:
{outputs}

QUY TẮC:
- Trả lời trực tiếp cho học viên, KHÔNG viết ở ngôi thứ nhất về quá trình suy nghĩ
- KHÔNG bao gồm "tôi đang phân tích", "tôi nhận thấy", "tôi đang xem xét"
- KHÔNG bao gồm <thinking> tags hoặc nội dung suy luận nội bộ
- Giữ tự nhiên, thân thiện — độ dài vừa đủ cho nội dung, không giới hạn cứng
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

FAST_WEB_KEYWORDS = [
    "tim tren web", "tim tren mang", "tim tren internet",
    "search", "tin tuc", "moi nhat", "hom nay",
    "nghi dinh", "thong tu", "van ban phap luat",
    "maritime news", "shipping news",
]

FAST_PRODUCT_KEYWORDS = [
    "shopee", "lazada", "tiktok shop", "facebook marketplace",
    "google shopping", "mua", "tim san pham", "so sanh gia",
    "gia re nhat", "mua o dau",
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

_NORMALIZED_SOCIAL_PREFIXES = (
    "xin chao",
    "chao",
    "hello",
    "hi",
    "hey",
    "cam on",
    "thanks",
    "thank",
    "thank you",
    "tam biet",
    "bye",
    "goodbye",
    "hen gap lai",
)

_SOCIAL_LAUGH_TOKENS = {
    "he",
    "hehe",
    "hehehe",
    "ha",
    "haha",
    "hahaha",
    "hi",
    "hihi",
    "hihihi",
    "hoho",
    "kk",
    "kkk",
    "keke",
    "alo",
    "alooo",
}

_REACTION_TOKENS = {
    "wow",
    "woah",
    "whoa",
    "oa",
    "oaa",
    "oi",
    "oii",
    "ui",
    "uii",
    "uay",
    "uayy",
    "ah",
    "a",
    "oh",
    "hmm",
    "hm",
    "uh",
    "umm",
    "um",
    "uhm",
}

_VAGUE_BANTER_PHRASES = {
    "gi do",
    "cai gi do",
    "gi ay",
    "cai gi ay",
}

_IDENTITY_PROBE_MARKERS = (
    "ban la ai",
    "ban ten gi",
    "ten gi",
    "ten cua ban",
    "wiii la ai",
    "wiii ten gi",
    "cuoc song the nao",
    "cuoc song cua ban",
    "song the nao",
    "gioi thieu ve ban",
)

_FAST_CHATTER_BLOCKERS = (
    "tai sao",
    "la gi",
    "the nao",
    "giai thich",
    "huong dan",
    "tra cuu",
    "quy dinh",
    "tin tuc",
    "search",
    "tim",
    "mo phong",
    "simulation",
    "canvas",
    "chart",
    "code",
    "python",
    "javascript",
    "html",
    "css",
    "react",
    "excel",
    "word",
    "pdf",
    "bao nhieu",
    "o dau",
    "nhu nao",
)

_ROUTING_ARTIFACT_MARKERS = (
    "```",
    "<!doctype",
    "<html",
    "<body",
    "<div",
    "<svg",
    "function ",
    "const ",
    "let ",
    "class ",
    "import ",
    "export ",
    "visual_session_id",
    '"type": "visual"',
)

_SUPERVISOR_HEARTBEAT_INTERVAL_SEC = 6.0

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
    """Normalize routing text — strip diacritics + lowercase cho keyword matching."""
    lowered = " ".join((text or "").lower().split())
    try:
        from app.engine.content_filter import TextNormalizer
        return TextNormalizer.strip_diacritics(lowered)
    except Exception:
        import unicodedata
        nfkd = unicodedata.normalize("NFD", lowered)
        return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _needs_code_studio(query: str) -> bool:
    """Detect requests that should route to the code studio capability."""
    normalized = _normalize_router_text(query)
    decision = resolve_visual_intent(query)
    if decision.presentation_intent in {"code_studio_app", "artifact"}:
        if "quiz" in normalized and not any(
            keyword in normalized
            for keyword in ("widget", "app", "html", "interactive", "artifact", "javascript", "canvas", "svg", "mini tool")
        ):
            return False
        return True
    narrowed_keywords = (
        "python",
        "code",
        "viet code",
        "chay code",
        "javascript",
        "typescript",
        "html",
        "css",
        "react",
        "landing page",
        "website",
        "web app",
        "microsite",
        "artifact",
        "sandbox",
        "excel",
        "xlsx",
        "spreadsheet",
        "word",
        "docx",
        "report",
        "memo",
        "proposal",
        "screenshot",
        "browser sandbox",
    )
    return any(kw in normalized for kw in narrowed_keywords)


def _looks_clear_social(normalized: str) -> bool:
    if len(normalized.split()) > 6:
        return False
    if any(marker in normalized for marker in ("giai thich", "quy dinh", "mo phong", "ve bieu do")):
        return False
    normalized = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", normalized)).strip()
    letters_only = re.sub(r"[^a-z]", "", normalized)
    tokens = [token for token in normalized.split() if token]
    if tokens and len(tokens) <= 4 and all(token in _SOCIAL_LAUGH_TOKENS for token in tokens):
        return True
    if letters_only and re.fullmatch(r"(he|ha|hi|ho|kk|alo){1,6}", letters_only):
        return True
    if letters_only.startswith(
        (
            "xinch",
            "chao",
            "hello",
            "hi",
            "hey",
            "cam",
            "thank",
            "thanks",
            "tambiet",
            "bye",
            "goodbye",
            "hengaplai",
        )
    ):
        return True
    return any(
        normalized == keyword or normalized.startswith(f"{keyword} ")
        for keyword in _NORMALIZED_SOCIAL_PREFIXES
    )


def is_obvious_social_turn(query: str) -> bool:
    """Return True for very short greeting/thanks/goodbye turns.

    Keep this intentionally narrow so we can skip heavyweight routing
    without misclassifying substantive questions.
    """
    normalized = _normalize_router_text(query)
    return _looks_clear_social(normalized)


def classify_fast_chatter_turn(query: str) -> tuple[str, str] | None:
    """Return a lightweight chatter classification for ultra-short turns.

    This intentionally stays narrow and shape-based so only tiny, low-information
    chatter skips the heavyweight structured routing + direct LLM path.
    """
    normalized = _normalize_router_text(query)
    if not normalized:
        return None

    if any(marker in normalized for marker in _FAST_CHATTER_BLOCKERS):
        return None

    if _looks_clear_social(normalized):
        return ("social", "social")

    tokens = [token for token in re.sub(r"[^\w\s]", " ", normalized).split() if token]
    if tokens and len(tokens) <= 3 and all(token in _REACTION_TOKENS for token in tokens):
        return ("social", "reaction")

    if normalized in _VAGUE_BANTER_PHRASES:
        return ("off_topic", "vague_banter")
    return None


def _looks_identity_probe(query: str) -> bool:
    normalized = _normalize_router_text(query)
    if not normalized:
        return False
    if any(marker in normalized for marker in _IDENTITY_PROBE_MARKERS):
        return True
    tokens = [token for token in re.sub(r"[^\w\s]", " ", normalized).split() if token]
    return bool(tokens) and len(tokens) <= 8 and normalized in {
        "ban la ai",
        "ten gi",
        "ten cua ban",
        "wiii la ai",
        "wiii ten gi",
        "cuoc song the nao",
    }


def _looks_short_capability_probe(query: str) -> bool:
    normalized = _normalize_router_text(query)
    tokens = [token for token in normalized.split() if token]
    if not tokens or len(tokens) > 10:
        return False
    if not any(marker in normalized for marker in ("duoc", "khong", "co the", "chua", "sao", "mo phong", "simulation", "canvas", "widget", "app", "artifact")):
        return False
    return _needs_code_studio(query) or any(
        marker in normalized
        for marker in ("mo phong", "simulation", "canvas", "widget", "app", "artifact")
    )


def _looks_like_visual_data_request(query: str) -> bool:
    """Detect chart/data visual turns that should stay on DIRECT.

    These requests need the data/search + inline-visual lane, not the
    app/artifact lane reserved for Code Studio.
    """
    normalized = _normalize_router_text(query)
    if not normalized:
        return False

    visual_markers = (
        "visual",
        "bieu do",
        "chart",
        "do thi",
        "thong ke",
        "so lieu",
        "du lieu",
        "xu huong",
    )
    data_markers = (
        "gia ",
        "gia dau",
        "hien tai",
        "hom nay",
        "moi nhat",
        "ngay gan day",
        "gan day",
        "recent",
        "latest",
        "trend",
        "so sanh",
    )
    blockers = (
        "mo phong",
        "simulation",
        "canvas",
        "widget",
        "app",
        "artifact",
        "html",
        "excel",
        "word",
        "pdf",
        "python",
        "javascript",
        "typescript",
        "file",
        "xuat file",
        "tai file",
    )
    if any(marker in normalized for marker in blockers):
        return False
    return any(marker in normalized for marker in visual_markers) and any(
        marker in normalized for marker in data_markers
    )


def _looks_like_short_natural_question(query: str) -> bool:
    normalized = _normalize_router_text(query)
    tokens = [token for token in normalized.split() if token]
    if not tokens or len(tokens) > 10:
        return False

    question_markers = (
        "?",
        "co the",
        "duoc khong",
        "duoc ko",
        "khong",
        "sao",
        "the nao",
        "tai sao",
        "lam sao",
        "nen khong",
        "co nen",
        "co phai",
        "hay khong",
        "co the nao",
        "nen",
        "neu",
    )
    return any(marker in normalized for marker in question_markers)


def _should_use_compact_routing_prompt(
    query: str,
    fast_chatter_hint: tuple[str, str] | None,
) -> bool:
    normalized = _normalize_router_text(query)
    token_count = len([token for token in normalized.split() if token])
    if fast_chatter_hint is not None:
        return True
    if _looks_short_capability_probe(query):
        return True
    if _looks_like_short_natural_question(query):
        return False
    return 0 < token_count <= 4


def _apply_routing_hint(state: AgentState, query: str) -> dict[str, str]:
    """Capture lightweight shape hints without bypassing LLM-first routing."""
    if _looks_identity_probe(query):
        hint = {
            "kind": "identity_probe",
            "intent": "selfhood",
            "shape": "identity",
        }
        state["_routing_hint"] = hint
        return hint

    fast_chatter = classify_fast_chatter_turn(query)
    if fast_chatter is not None:
        hint = {
            "kind": "fast_chatter",
            "intent": fast_chatter[0],
            "shape": fast_chatter[1],
        }
        state["_routing_hint"] = hint
        return hint

    if _looks_short_capability_probe(query):
        hint = {
            "kind": "capability_probe",
            "intent": "code_execution" if _needs_code_studio(query) else "unknown",
            "shape": "short_probe",
        }
        state["_routing_hint"] = hint
        return hint

    state.pop("_routing_hint", None)
    return {}


def _looks_like_artifact_payload(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if len(normalized) > 320 and normalized.count("\n") >= 8:
        return True
    return any(marker in normalized for marker in _ROUTING_ARTIFACT_MARKERS)


def _summarize_routing_turn_content(content: object, *, speaker: str, limit: int) -> str:
    raw = str(content or "").strip()
    if not raw:
        return ""
    normalized = " ".join(raw.split())
    lowered = normalized.lower()

    if _looks_like_artifact_payload(raw):
        if speaker == "user":
            if any(marker in lowered for marker in ("mo phong", "simulation", "canvas", "widget", "artifact", "<svg")):
                return "[Người dùng vừa nhắc hoặc dán một yêu cầu visual/mô phỏng.]"
            return "[Người dùng vừa đưa một nội dung kỹ thuật hoặc đoạn mã khá dài.]"
        if any(marker in lowered for marker in ("mo phong", "simulation", "canvas", "widget", "artifact", "<svg", "visual")):
            return "[AI vừa mở hoặc bàn về một visual/mô phỏng liên quan.]"
        return "[AI vừa tạo một đầu ra kỹ thuật hoặc artifact có mã dài.]"

    if len(normalized) > limit:
        return f"{normalized[: max(0, limit - 1)].rstrip()}…"
    return normalized


def _build_recent_turns_for_routing(lc_messages: list, *, turn_window: int, turn_limit: int) -> str:
    lines: list[str] = []
    for message in lc_messages[-turn_window:]:
        is_user = getattr(message, "type", "") == "human"
        speaker = "User" if is_user else "AI"
        summarized = _summarize_routing_turn_content(
            getattr(message, "content", ""),
            speaker="user" if is_user else "assistant",
            limit=turn_limit,
        )
        if summarized:
            lines.append(f"{speaker}: {summarized}")
    return "\n".join(lines)


def _quote_query_for_visible_reasoning(query: str, max_len: int = 84) -> str:
    compact = " ".join((query or "").split())
    lowered = compact.lower()
    if not compact:
        return "câu này"
    if any(marker in lowered for marker in ("mô phỏng", "mo phong", "simulation", "canvas", "widget", "artifact")):
        return "yêu cầu mô phỏng này"
    if any(marker in lowered for marker in ("visual", "biểu đồ", "bieu do", "chart", "thống kê", "thong ke")):
        return "yêu cầu trực quan này"
    if len(compact.split()) <= 8:
        return "nhịp này"
    if len(compact) > max_len:
        compact = f"{compact[: max_len - 1].rstrip()}…"
    return "điều bạn vừa hỏi"


def _get_supervisor_stream_queue(state: AgentState):
    bus_id = state.get("_event_bus_id")
    if not bus_id:
        return None
    try:
        from app.engine.multi_agent.graph_streaming import _get_event_queue

        return _get_event_queue(str(bus_id))
    except Exception as exc:
        logger.debug("[SUPERVISOR] Event queue unavailable: %s", exc)
        return None


def _push_supervisor_stream_event(queue, event: dict) -> None:
    if queue is None:
        return
    try:
        queue.put_nowait(event)
    except Exception as exc:
        logger.debug("[SUPERVISOR] Event queue push failed: %s", exc)


def _clean_supervisor_visible_reasoning(text: object, *, limit: int = 280) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    # Truncate at sentence or word boundary, never mid-word
    truncated = cleaned[:limit]
    for end in [". ", ".\n", "? ", "! "]:
        pos = truncated.rfind(end)
        if pos > limit * 0.6:
            return truncated[: pos + 1]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.5:
        return cleaned[:last_space]
    return cleaned[:limit]


def _render_supervisor_visible_reasoning(
    state: AgentState,
    *,
    intent: str = "",
    cue: str = "",
    confidence: float = 0.0,
    next_action: str = "",
    observations: Optional[list[str]] = None,
):
    from app.engine.reasoning import ReasoningRenderRequest, get_reasoning_narrator

    query = state.get("query", "")
    context = state.get("context", {}) or {}
    routing_hint = state.get("_routing_hint") if isinstance(state.get("_routing_hint"), dict) else {}
    resolved_intent = intent or str(routing_hint.get("intent") or "")
    resolved_cue = cue
    if not resolved_cue and (
        routing_hint.get("kind") == "capability_probe" or _needs_code_studio(query)
    ):
        resolved_cue = AgentType.CODE_STUDIO.value

    _n = get_reasoning_narrator()
    _req = ReasoningRenderRequest(
        node="supervisor",
        phase="route",
        intent=resolved_intent,
        cue=resolved_cue,
        user_goal=query,
        conversation_context=str((context or {}).get("conversation_summary", "")),
        capability_context=str(state.get("capability_context") or ""),
        confidence=float(confidence or 0.0),
        next_action=next_action,
        observations=[item for item in (observations or []) if item],
        user_id=str(state.get("user_id") or ""),
        organization_id=(context or {}).get("organization_id"),
        personality_mode=(context or {}).get("personality_mode"),
        mood_hint=(context or {}).get("mood_hint"),
        visibility_mode="rich",
        style_tags=["routing", "visible_reasoning", "attuning", "house"],
    )
    return _n._fallback(_req, _n._resolve_node_skill("supervisor"))


# Supervisor heartbeat removed — thinking comes from agent nodes, not supervisor.


def _looks_clear_web_intent(normalized: str) -> bool:
    if any(marker in normalized for marker in ("quiz", "giai thich", "on bai", "mo phong")):
        return False
    return any(keyword in normalized for keyword in FAST_WEB_KEYWORDS)


def _looks_clear_product_intent(normalized: str) -> bool:
    if any(marker in normalized for marker in ("code", "html", "svg", "canvas", "python")):
        return False
    return any(keyword in normalized for keyword in FAST_PRODUCT_KEYWORDS)


def _looks_clear_learning_turn(normalized: str) -> bool:
    if any(
        marker in normalized
        for marker in (
            "widget",
            "mini app",
            "mini tool",
            "interactive quiz",
            "quiz widget",
            "quiz app",
            "html quiz",
            "artifact",
            "canvas",
            "svg",
            "javascript",
            "react",
            "python",
            "code",
        )
    ):
        return False
    return any(
        marker in normalized
        for marker in (
            "quiz",
            "quizz",
            "trac nghiem",
            "luyen tap",
            "on tap",
            "flashcard",
            "bai tap",
            "practice",
            "learn",
            "hoc ",
            "giai thich",
            "day minh",
            "day toi",
            "huong dan",
        )
    )


_VISUAL_LEARNING_CUES = (
    "giai thich",
    "explain",
    "how it works",
    "step by step",
    "in charts",
    "with charts",
    "visual",
)


def _finalize_routing_reasoning(
    *,
    raw_reasoning: str,
    method: str,
    chosen_agent: str,
    intent: str,
    query: str,
) -> str:
    """Return user-facing routing reasoning that matches the final chosen lane.

    Keep the raw LLM reasoning for observability, but avoid surfacing a mismatch
    where the raw structured classifier leans one way and deterministic overrides
    send the turn somewhere else.
    """
    cleaned_raw = " ".join((raw_reasoning or "").split()).strip()
    normalized_method = str(method or "").strip().lower()
    normalized_intent = str(intent or "").strip().lower()
    normalized_query = _normalize_router_text(query)

    if normalized_method == "structured+capability_override":
        if chosen_agent == AgentType.CODE_STUDIO.value:
            return (
                "Câu này vẫn đang mang tín hiệu mô phỏng hoặc lane dựng app/visual, "
                "nên mình giữ nó ở Code Studio để Wiii có thể mở đúng không gian sáng tạo "
                "thay vì đáp tạm bằng lời."
            )
        if chosen_agent == AgentType.DIRECT.value:
            return (
                "Phần intent thô ban đầu còn lửng, nhưng lane xử lý phù hợp nhất lúc này "
                "vẫn là trả lời trực tiếp để chốt thêm ý trước khi mở nhánh sâu hơn."
            )

    if normalized_method == "structured+visual_lane_override":
        return (
            "Đây nghiêng về một visual giải thích hoặc chart inline hơn là app hoàn chỉnh, "
            "nên mình giữ nó ở lane trực tiếp để Wiii còn phát visual đúng cách trong stream."
        )

    if normalized_method == "structured+visual_override":
        return (
            "Câu này cần một nhịp minh hoạ trực quan hơn là giảng bài thuần chữ, "
            "nên mình chuyển về direct lane để gọi visual đúng chỗ."
        )

    if normalized_method == "structured+intent_override":
        if chosen_agent == AgentType.CODE_STUDIO.value:
            return (
                "Ý chính ở đây là tạo hoặc dựng một thứ có thể chạy/hiện ra được, "
                "nên mình chốt route sang Code Studio thay vì để nó trôi ở lane trò chuyện."
            )
        if chosen_agent == AgentType.DIRECT.value and normalized_intent in {"off_topic", "web_search"}:
            return (
                "Câu này không cần kéo vào lane tri thức chuyên biệt; "
                "trả lời trực tiếp sẽ giữ nhịp trò chuyện đúng hơn."
            )

    if normalized_method == "structured+domain_validation":
        return (
            "Mình không thấy đủ tín hiệu domain chuyên biệt trong câu này, "
            "nên không ép sang lane tra cứu/giảng dạy nặng."
        )

    if normalized_method == "structured+rule_override":
        return (
            "Phần phân loại ban đầu chưa đủ chắc, nên mình chốt lại theo guardrail an toàn hơn "
            "để tránh kéo bạn vào nhánh xử lý lệch."
        )

    if normalized_method == "always_on_social_fast_path":
        return "Đây là một nhịp xã giao rất rõ, nên mình đáp ngay để giữ cuộc trò chuyện tự nhiên."

    if normalized_method == "always_on_chatter_fast_path":
        return "Đây là một nhịp trò chuyện rất ngắn và ít thông tin, nên mình giữ nó ở lane đáp trực tiếp."

    if normalized_intent == "social" and len(normalized_query.split()) <= 6:
        return (
            "Nhịp này thiên về xã giao hoặc bắt nhịp cảm xúc hơn là cần mở một lane xử lý nặng, "
            "nên mình giữ nó ngắn và gần."
        )

    return cleaned_raw


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
        """Initialize default LLM from shared pool for routing decisions."""
        try:
            # Sprint 69: Use AgentConfigRegistry for per-node LLM config
            self._llm = AgentConfigRegistry.get_llm("supervisor")
            logger.info("SupervisorAgent initialized (via AgentConfigRegistry)")
        except Exception as e:
            logger.error("Failed to initialize Supervisor LLM: %s", e)
            self._llm = None

    def _get_llm_for_state(self, state: AgentState):
        """Resolve the house routing model instead of the user-selected generator.

        Wiii's supervisor is the conductor of the conversation, so we keep it on
        the admin-managed routing profile to preserve routing quality, visible
        reasoning tone, and house identity.
        """
        try:
            provider_override = self._resolve_house_routing_provider(state)
            if provider_override:
                state["_house_routing_provider"] = provider_override
                return AgentConfigRegistry.get_llm("supervisor", provider_override=provider_override)
            return AgentConfigRegistry.get_llm("supervisor")
        except Exception:
            return self._llm

    def _resolve_house_routing_provider(self, state: AgentState) -> Optional[str]:
        """Pick the best currently-runnable provider for house routing.

        Runtime-aware: tries configured primary, falls back to first
        available provider in the chain if primary is unavailable.
        """
        from app.engine.llm_pool import LLMPool

        primary = str(settings.llm_provider or "google").strip().lower()
        provider = LLMPool._providers.get(primary)
        if provider and provider.is_available():
            return primary
        for name in LLMPool._get_provider_chain():
            p = LLMPool._providers.get(name)
            if p and p.is_available():
                logger.info("[SUPERVISOR] Primary %s unavailable, using %s", primary, name)
                return name
        return primary

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

        _apply_routing_hint(state, query)

        if settings.enable_conservative_fast_routing and not state.get("_routing_hint"):
            fast_result = self._conservative_fast_route(query, context, domain_config)
            if fast_result is not None:
                agent, intent, confidence, reasoning = fast_result
                method = "conservative_fast_path"
                state["routing_metadata"] = {
                    "intent": intent,
                    "confidence": confidence,
                    "reasoning": _finalize_routing_reasoning(
                        raw_reasoning=reasoning,
                        method=method,
                        chosen_agent=agent,
                        intent=intent,
                        query=query,
                    ),
                    "llm_reasoning": "",
                    "method": method,
                    "final_agent": agent,
                }
                return agent

        # Per-request provider-aware LLM resolution
        llm = self._get_llm_for_state(state)

        if not llm:
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
            return await self._route_structured(query, context, domain_name, rag_desc, tutor_desc, domain_config, state, llm=llm)

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
                                 state: AgentState, *, llm=None) -> str:
        """Route using structured output with CoT and confidence gate (Sprint 71)."""
        from app.engine.structured_schemas import RoutingDecision
        from app.services.structured_invoke_service import StructuredInvokeService

        _llm = llm or self._llm

        routing_hint = state.get("_routing_hint") if isinstance(state.get("_routing_hint"), dict) else {}
        fast_chatter_hint = None
        if routing_hint.get("kind") == "fast_chatter":
            fast_chatter_hint = (
                str(routing_hint.get("intent") or ""),
                str(routing_hint.get("shape") or ""),
            )
        use_compact_prompt = _should_use_compact_routing_prompt(query, fast_chatter_hint)

        # Sprint 77+78: Give supervisor recent context, but keep it compact on
        # short turns so routing can still be LLM-first without carrying the
        # full house stack on every "wow/hehe/mo phong duoc chu?" beat.
        lc_messages = (context or {}).get("langchain_messages", [])
        conv_summary = (context or {}).get("conversation_summary", "")
        if lc_messages:
            turn_window = 2 if use_compact_prompt else 6
            turn_limit = 88 if use_compact_prompt else 200
            recent_turns = _build_recent_turns_for_routing(
                lc_messages,
                turn_window=turn_window,
                turn_limit=turn_limit,
            )
            context_str = f"Recent conversation:\n{recent_turns}"
            if conv_summary:
                summary_limit = 96 if use_compact_prompt else 300
                context_str = f"Summary of earlier conversation:\n{conv_summary[:summary_limit]}\n\n{context_str}"
        else:
            context_str = str(context)[:160 if use_compact_prompt else 500]

        capability_context = state.get("capability_context", "")
        if capability_context:
            cap_limit = 120 if use_compact_prompt else len(capability_context)
            context_str = f"{context_str}\n\n{capability_context[:cap_limit]}"

        # Sprint 215: Extract user_role for colleague routing
        user_role = (context or {}).get("user_role") or (context or {}).get("role") or "student"

        routing_hints: list[str] = []
        if fast_chatter_hint is not None:
            routing_hints.append(
                f"short_{fast_chatter_hint[1]} -> intent={fast_chatter_hint[0]}"
            )
        if routing_hint.get("kind") == "capability_probe":
            routing_hints.append("short_capability_probe")
        if _needs_code_studio(query):
            routing_hints.append("code_studio_signal")
        house_provider = state.get("_house_routing_provider")
        if house_provider:
            routing_hints.append(f"house_provider={house_provider}")
        routing_hints_text = ", ".join(routing_hints) or "none"

        if use_compact_prompt:
            messages = [
                SystemMessage(content=build_supervisor_micro_card_prompt()),
                HumanMessage(content=COMPACT_ROUTING_PROMPT_TEMPLATE.format(
                    query=query,
                    context=context_str,
                    routing_hints=routing_hints_text,
                )),
            ]
        else:
            messages = [
                SystemMessage(content=build_supervisor_card_prompt()),
                SystemMessage(content="You are a query router. Analyze the query step by step, classify intent, choose agent, and provide confidence."),
                SystemMessage(content=(
                    "Visual policy: explanatory charts, comparisons, process diagrams, architecture diagrams, and concept visuals "
                    "should stay on DIRECT or TUTOR so those agents can call article-figure/chart tools. "
                    "Reserve CODE_STUDIO_AGENT for code execution, app/widget generation, simulations, artifacts, files, or browser sandbox work."
                )),
                HumanMessage(content=ROUTING_PROMPT_TEMPLATE.format(
                    domain_name=domain_name,
                    rag_description=rag_desc,
                    tutor_description=tutor_desc,
                    query=query,
                    context=context_str,
                    user_role=user_role,
                )),
            ]

        result = await StructuredInvokeService.ainvoke(
            llm=_llm,
            schema=RoutingDecision,
            payload=messages,
            tier="light",
            provider=house_provider,
        )

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
        visual_decision = resolve_visual_intent(query)

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

        if (
            (
                (
                    visual_decision.presentation_intent in {"article_figure", "chart_runtime"}
                    and not _needs_code_studio(query)
                )
                or _looks_like_visual_data_request(query)
            )
            and chosen_agent != AgentType.DIRECT.value
        ):
            logger.info(
                "[SUPERVISOR] Visual lane override: %s -> direct (%s)",
                chosen_agent,
                visual_decision.presentation_intent or "visual_data_request",
            )
            chosen_agent = AgentType.DIRECT.value
            method = "structured+visual_lane_override"

        # Chart visuals must go through DIRECT (it emits visual events via SSE properly)
        # Also override when resolver detects any visual intent (force_tool=True)
        if (
            chosen_agent == AgentType.TUTOR.value
            and (
                visual_decision.presentation_intent == "chart_runtime"
                or visual_decision.force_tool
            )
        ):
            logger.info("[SUPERVISOR] Visual override: tutor -> direct (force_tool=%s, intent=%s)",
                        visual_decision.force_tool, visual_decision.presentation_intent)
            chosen_agent = AgentType.DIRECT.value
            method = "structured+visual_override"

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
            "reasoning": _finalize_routing_reasoning(
                raw_reasoning=result.reasoning,
                method=method,
                chosen_agent=chosen_agent,
                intent=result.intent,
                query=query,
            ),
            "llm_reasoning": result.reasoning,
            "method": method,
            "final_agent": chosen_agent,
            "house_provider": house_provider,
            "compact_prompt": use_compact_prompt,
        }

        return chosen_agent

    def _conservative_fast_route(self, query: str, context: dict, domain_config: dict) -> Optional[tuple[str, str, float, str]]:
        """Route only the most obvious turns without invoking the supervisor LLM."""
        normalized = _normalize_router_text(query)

        fast_chatter = classify_fast_chatter_turn(query)
        if fast_chatter is not None:
            intent, chatter_kind = fast_chatter
            reasoning = (
                "obvious social turn"
                if chatter_kind == "social"
                else f"obvious {chatter_kind.replace('_', ' ')} turn"
            )
            return (AgentType.DIRECT.value, intent, 1.0, reasoning)

        if _looks_clear_social(normalized):
            return (AgentType.DIRECT.value, "social", 1.0, "obvious social turn")

        return None

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
        if is_obvious_social_turn(query):
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
            return "Xin lỗi, mình chưa xử lý được yêu cầu này nha~ (˶˃ ᵕ ˂˶)"

        # Synthesize multiple outputs
        llm = self._get_llm_for_state(state)
        if not llm:
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
            _host_capabilities_prompt = state.get("host_capabilities_prompt", "")
            _host_capabilities_suffix = (
                f"\n\nHost Capabilities:\n{_host_capabilities_prompt}"
                if _host_capabilities_prompt else ""
            )
            _operator_prompt = state.get("operator_context_prompt", "")
            _operator_suffix = f"\n\nOperator Context:\n{_operator_prompt}" if _operator_prompt else ""
            _living_prompt = state.get("living_context_prompt", "")
            _living_suffix = f"\n\nLiving Context:\n{_living_prompt}" if _living_prompt else ""
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
                ) + _host_suffix + _host_capabilities_suffix + _operator_suffix + _living_suffix + _widget_suffix)
            ]

            try:
                response = await llm.ainvoke(messages)
            except Exception as _synth_exc:
                from app.engine.llm_pool import LLMPool, is_rate_limit_error
                if not is_rate_limit_error(_synth_exc):
                    raise
                _fb = LLMPool.get_fallback("moderate")
                if _fb is None:
                    raise
                logger.warning("[SUPERVISOR] Rate-limited, using fallback for synthesis")
                response = await _fb.ainvoke(messages)

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
        event_queue = _get_supervisor_stream_queue(state)

        # Skill Activation: match query against domain skills (progressive disclosure)
        domain_id = state.get("domain_id", "")
        query = state.get("query", "")
        if query:
            _apply_routing_hint(state, query)
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

        # Supervisor does NOT push thinking bus events (matches production GitHub code).
        # All visible thinking comes from agent nodes via astream() + narrator.render().

        try:
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
                        logger.info(
                            "[SUPERVISOR] Complex query detected -> parallel_dispatch %s",
                            planned_targets,
                        )
                        next_agent = "parallel_dispatch"
                        state["_parallel_targets"] = planned_targets
            except Exception as e:
                logger.debug("Parallel dispatch check failed: %s", e)

            state["next_agent"] = next_agent
            state["current_agent"] = "supervisor"

            metadata = state.get("routing_metadata", {}) or {}
            logger.info(
                "[SUPERVISOR] Routing to: %s (method=%s, intent=%s, conf=%.2f)",
                next_agent,
                metadata.get("method", "unknown"),
                metadata.get("intent", "unknown"),
                metadata.get("confidence", 0.0),
            )

            return state
        except Exception:
            raise

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
