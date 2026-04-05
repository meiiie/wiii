"""Presentation helpers for the LMS chat JSON response."""

from app.core.constants import (
    CONFIDENCE_BASE,
    CONFIDENCE_MAX,
    CONFIDENCE_PER_SOURCE,
)
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatResponseData,
    ChatResponseMetadata,
    InternalChatResponse,
    SourceInfo,
    ToolUsageInfo,
)
from app.services.model_switch_prompt_service import (
    build_model_switch_prompt_for_failover,
)


def get_tool_description(tool: dict) -> str:
    """Generate a short human-readable description for a used tool."""
    name = tool.get("name", "unknown")
    args = tool.get("args", {})
    result = tool.get("result", "")

    if name in ("tool_knowledge_search", "tool_maritime_search"):
        query = args.get("query", "")
        return f"Tra cứu: {query}" if query else "Tra cứu kiến thức"
    if name == "tool_save_user_info":
        key = args.get("key", "")
        value = args.get("value", "")
        return f"Lưu thông tin: {key}={value}" if key else "Lưu thông tin người dùng"
    if name == "tool_get_user_info":
        key = args.get("key", "all")
        return f"Lấy thông tin: {key}"
    return result[:100] if result else f"Gọi tool: {name}"


def classify_query_type(message: str) -> str:
    """Classify query type for LMS analytics."""
    message_lower = message.lower()
    code_keywords = [
        "python", "code", "chart", "plot", "bieu do", "html", "landing page",
        "excel", "word", "docx", "xlsx", "javascript", "react",
    ]

    procedural_keywords = [
        "làm thế nào", "như thế nào", "cách", "thủ tục", "quy trình",
        "bước", "how to", "steps", "process", "procedure",
    ]
    factual_keywords = [
        "điều", "khoản", "quy định", "là gì", "what is", "định nghĩa",
        "nghĩa là", "rule", "article", "regulation",
    ]

    for keyword in code_keywords:
        if keyword in message_lower:
            return "code_generation"
    for keyword in procedural_keywords:
        if keyword in message_lower:
            return "procedural"
    for keyword in factual_keywords:
        if keyword in message_lower:
            return "factual"
    return "conceptual"


def generate_suggested_questions(user_message: str, ai_response: str) -> list[str]:
    """Generate follow-up suggestions from the current exchange."""
    user_lower = user_message.lower()
    response_lower = ai_response.lower()

    if any(keyword in user_lower for keyword in [
        "python", "code", "chart", "plot", "bieu do", "html", "landing page",
        "excel", "word", "docx", "xlsx", "javascript", "react",
    ]):
        return [
            "Báº¡n muá»‘n mÃ¬nh dÃ¹ng dá»¯ liá»‡u cá»¥ thá»ƒ nÃ o Ä‘á»ƒ lÃ m láº¡i phiÃªn báº£n chuáº©n hÆ¡n?",
            "Báº¡n cÃ³ muá»‘n Ä‘á»•i kiá»ƒu hiá»ƒn thá»‹ hoáº·c mÃ u sáº¯c cá»§a artifact khÃ´ng?",
            "Báº¡n muá»‘n mÃ¬nh xuáº¥t thÃªm má»™t file khÃ¡c nhÆ° HTML, Excel, hoáº·c Word khÃ´ng?",
        ]

    if any(keyword in response_lower for keyword in ["quy tắc", "rule", "điều", "quy định"]):
        return [
            "Khi nào áp dụng quy tắc này?",
            "Có ngoại lệ nào không?",
            "Bạn có thể giải thích chi tiết hơn không?",
        ]
    if any(keyword in response_lower for keyword in ["an toàn", "safety", "thiết bị"]):
        return [
            "Yêu cầu cụ thể là gì?",
            "Quy trình kiểm tra như thế nào?",
            "Có tiêu chuẩn nào liên quan không?",
        ]
    if any(keyword in user_lower for keyword in ["học", "tìm hiểu", "giải thích", "dạy"]):
        return [
            "Bạn muốn tìm hiểu thêm về chủ đề nào?",
            "Bạn cần giải thích chi tiết hơn không?",
            "Bạn muốn làm bài tập thực hành không?",
        ]
    return [
        "Bạn muốn tìm hiểu thêm về chủ đề nào?",
        "Bạn có câu hỏi nào khác không?",
        "Tôi có thể giúp gì thêm cho bạn?",
    ]


def build_chat_response(
    *,
    chat_request: ChatRequest,
    internal_response: InternalChatResponse,
    processing_time: float,
    provider_name: str | None,
    model_name: str | None,
    runtime_authoritative: bool = True,
) -> ChatResponse:
    """Build the LMS-facing JSON response from the internal response."""
    sources = []
    if internal_response.sources:
        for src in internal_response.sources:
            sources.append(
                SourceInfo(
                    title=src.title,
                    content=src.content_snippet or "",
                    image_url=getattr(src, "image_url", None),
                    page_number=getattr(src, "page_number", None),
                    document_id=getattr(src, "document_id", None),
                    bounding_boxes=getattr(src, "bounding_boxes", None),
                )
            )

    tools_used = []
    metadata = internal_response.metadata or {}
    for tool in metadata.get("tools_used", []):
        tools_used.append(
            ToolUsageInfo(
                name=tool.get("name", "unknown"),
                description=get_tool_description(tool),
            )
        )

    topics_accessed = [src.title for src in sources if src.title] or None
    document_ids_used = list({src.document_id for src in sources if src.document_id}) or None
    confidence_score = None
    if sources:
        confidence_score = min(
            CONFIDENCE_BASE + len(sources) * CONFIDENCE_PER_SOURCE,
            CONFIDENCE_MAX,
        )

    return ChatResponse(
        status="success",
        data=ChatResponseData(
            answer=internal_response.message,
            sources=sources,
            suggested_questions=generate_suggested_questions(
                chat_request.message,
                internal_response.message,
            ),
            domain_notice=metadata.get("domain_notice"),
        ),
        metadata=ChatResponseMetadata(
            processing_time=round(processing_time, 3),
            provider=provider_name,
            model=model_name or "",
            agent_type=internal_response.agent_type,
            session_id=metadata.get("session_id"),
            tools_used=tools_used,
            reasoning_trace=metadata.get("reasoning_trace"),
            thinking_content=metadata.get("thinking_content"),
            thinking=metadata.get("thinking"),
            thinking_lifecycle=metadata.get("thinking_lifecycle"),
            failover=metadata.get("failover"),
            model_switch_prompt=build_model_switch_prompt_for_failover(
                failover=metadata.get("failover"),
                requested_provider=getattr(chat_request, "provider", None),
            ),
            routing_metadata=metadata.get("routing_metadata"),
            topics_accessed=topics_accessed,
            confidence_score=round(confidence_score, 2) if confidence_score else None,
            document_ids_used=document_ids_used,
            query_type=classify_query_type(chat_request.message),
            runtime_authoritative=runtime_authoritative,
        ),
    )
