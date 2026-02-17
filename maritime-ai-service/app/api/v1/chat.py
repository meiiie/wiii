"""
Chat API Endpoint for LMS Integration
Requirements: 1.1, 1.2, 1.4
Spec: CHỈ THỊ KỸ THUẬT SỐ 03, SỐ 04

POST /api/v1/chat - Main chat endpoint for LMS integration
"""
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import RequireAuth
from app.core.config import settings
from app.core.constants import CONFIDENCE_BASE, CONFIDENCE_MAX, CONFIDENCE_PER_SOURCE
from app.core.exceptions import WiiiException
from app.core.rate_limit import limiter
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatResponseData,
    ChatResponseMetadata,
    SourceInfo,
    ErrorResponse,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    GetHistoryResponse,
    HistoryMessage,
    HistoryPagination,
    ToolUsageInfo,  # CHỈ THỊ SỐ 27: API Transparency
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"description": "Validation error - thiếu trường bắt buộc"},
        401: {"description": "Authentication required - thiếu X-API-Key"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
    summary="Chat Completion (LMS Integration)",
    description="""
    **Endpoint chính cho LMS Hàng Hải gọi vào.**
    
    Nhận câu hỏi từ LMS, xử lý qua RAG/Memory, trả về câu trả lời JSON.
    
    **Role-Based Prompting:**
    - `student`: AI đóng vai Gia sư (Tutor) - giọng văn khuyến khích, giải thích cặn kẽ
    - `teacher`/`admin`: AI đóng vai Trợ lý (Assistant) - chuyên nghiệp, ngắn gọn
    
    **Requirements: 1.1, 1.2, 1.4**
    **Spec: CHỈ THỊ KỸ THUẬT SỐ 03**
    """,
)
@limiter.limit("30/minute")
async def chat_completion(
    request: Request,
    chat_request: ChatRequest,
    auth: RequireAuth,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """
    Process a chat completion request from LMS.
    
    Args:
        request: FastAPI request object (for rate limiting)
        chat_request: The chat request payload with user_id, message, role
        auth: Authenticated via X-API-Key header
    
    Returns:
        ChatResponse with status, data (answer, sources, suggested_questions), metadata
    """
    start_time = time.time()
    
    logger.info(
        "Chat request from user %s (role: %s, auth: %s): %s...",
        chat_request.user_id, chat_request.role.value, auth.auth_method,
        chat_request.message[:50]
    )
    
    try:
        # Process through integrated ChatService with role-based prompting
        # Use BackgroundTasks to save chat history without blocking response
        # Spec: CHỈ THỊ KỸ THUẬT SỐ 04
        from app.services.chat_service import get_chat_service
        
        chat_service = get_chat_service()
        internal_response = await chat_service.process_message(
            chat_request,
            background_save=background_tasks.add_task
        )
        
        processing_time = time.time() - start_time
        
        # Convert sources to LMS format (CHỈ THỊ 26: include image_url)
        sources = []
        if internal_response.sources:
            for src in internal_response.sources:
                sources.append(SourceInfo(
                    title=src.title,
                    content=src.content_snippet or "",
                    image_url=getattr(src, 'image_url', None),
                    # Feature: source-highlight-citation v0.9.8
                    page_number=getattr(src, 'page_number', None),
                    document_id=getattr(src, 'document_id', None),
                    bounding_boxes=getattr(src, 'bounding_boxes', None)
                ))
        
        # Generate suggested questions based on context
        suggested_questions = _generate_suggested_questions(
            chat_request.message, 
            internal_response.message
        )
        
        # CHỈ THỊ SỐ 27: Extract tools_used from internal response metadata
        tools_used = []
        if internal_response.metadata and internal_response.metadata.get("tools_used"):
            for tool in internal_response.metadata["tools_used"]:
                tools_used.append(ToolUsageInfo(
                    name=tool.get("name", "unknown"),
                    description=_get_tool_description(tool)
                ))
        
        # LMS Integration: Extract analytics metadata
        topics_accessed = None
        document_ids_used = None
        confidence_score = None
        query_type = None
        
        if sources:
            # Extract topics from source titles
            topics_accessed = [src.title for src in sources if src.title]
            # Extract document IDs
            document_ids_used = list(set(
                src.document_id for src in sources if src.document_id
            ))
            # Confidence based on sources found (simple heuristic)
            confidence_score = min(CONFIDENCE_BASE + len(sources) * CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX)
        
        # Classify query type (simple rule-based)
        query_type = _classify_query_type(chat_request.message)
        
        # Build LMS-compatible response
        # Extract session_id from internal response metadata
        session_id = None
        if internal_response.metadata:
            session_id = internal_response.metadata.get("session_id")
        
        # CHỈ THỊ SỐ 28: Extract reasoning_trace from internal response (SOTA)
        reasoning_trace = None
        if internal_response.metadata and internal_response.metadata.get("reasoning_trace"):
            reasoning_trace = internal_response.metadata["reasoning_trace"]
            logger.info("[REASONING_TRACE] Included %d steps in response", reasoning_trace.total_steps)
        
        # CHỈ THỊ SỐ 28: Extract thinking_content for LMS frontend display (Claude/OpenAI style)
        thinking_content = None
        thinking = None  # CHỈ THỊ SỐ 29: Natural Vietnamese thinking
        if internal_response.metadata:
            # Legacy: thinking_content (structured summary)
            if internal_response.metadata.get("thinking_content"):
                thinking_content = internal_response.metadata["thinking_content"]
            # CHỈ THỊ SỐ 29: thinking (natural Vietnamese)
            if internal_response.metadata.get("thinking"):
                thinking = internal_response.metadata["thinking"]
                logger.info("[THINKING] Included %d chars natural thinking", len(thinking))
        
        # Sprint 80b: Extract domain notice from internal response
        domain_notice = None
        if internal_response.metadata:
            domain_notice = internal_response.metadata.get("domain_notice")

        response = ChatResponse(
            status="success",
            data=ChatResponseData(
                answer=internal_response.message,
                sources=sources,
                suggested_questions=suggested_questions,
                domain_notice=domain_notice,
            ),
            metadata=ChatResponseMetadata(
                processing_time=round(processing_time, 3),
                model=settings.rag_model_version,
                agent_type=internal_response.agent_type,
                session_id=session_id,  # FIX: Add session_id for thread continuity
                tools_used=tools_used,  # CHỈ THỊ SỐ 27: API Transparency
                # CHỈ THỊ SỐ 28: SOTA Reasoning Trace + Thinking Content
                reasoning_trace=reasoning_trace,
                thinking_content=thinking_content,  # Structured summary (legacy)
                thinking=thinking,  # CHỈ THỊ SỐ 29: Natural Vietnamese thinking
                # Sprint 103: Routing metadata for debugging
                routing_metadata=internal_response.metadata.get("routing_metadata") if internal_response.metadata else None,
                # LMS Integration: Analytics fields
                topics_accessed=topics_accessed,
                confidence_score=round(confidence_score, 2) if confidence_score else None,
                document_ids_used=document_ids_used,
                query_type=query_type
            )
        )
        
        logger.info(
            "Chat response generated in %.3fs (agent: %s)",
            processing_time, internal_response.agent_type.value
        )
        
        return response
        
    except WiiiException as e:
        logger.error("Chat service error [%s]: %s", e.error_code, e.message)
        return JSONResponse(
            status_code=e.http_status,
            content={
                "status": "error",
                "error_code": e.error_code,
                "message": e.message,
                "request_id": request.headers.get("X-Request-ID"),
            }
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing chat request: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request.headers.get("X-Request-ID"),
            }
        )


def _get_tool_description(tool: dict) -> str:
    """
    Generate human-readable description for a tool usage.
    
    CHỈ THỊ SỐ 27: API Transparency
    **Feature: api-transparency-thinking**
    **Validates: Requirements 1.3**
    """
    name = tool.get("name", "unknown")
    args = tool.get("args", {})
    result = tool.get("result", "")
    
    if name in ("tool_knowledge_search", "tool_maritime_search"):
        query = args.get("query", "")
        return f"Tra cứu: {query}" if query else "Tra cứu kiến thức"
    elif name == "tool_save_user_info":
        key = args.get("key", "")
        value = args.get("value", "")
        return f"Lưu thông tin: {key}={value}" if key else "Lưu thông tin người dùng"
    elif name == "tool_get_user_info":
        key = args.get("key", "all")
        return f"Lấy thông tin: {key}"
    else:
        return result[:100] if result else f"Gọi tool: {name}"


def _classify_query_type(message: str) -> str:
    """
    Classify query type for LMS analytics.
    
    LMS Integration: Track learning patterns via query classification.
    
    Returns:
        - factual: Questions about specific facts, definitions, articles
        - conceptual: Questions about understanding concepts
        - procedural: Questions about processes, how-to, steps
    """
    message_lower = message.lower()
    
    # Procedural keywords
    procedural_keywords = [
        "làm thế nào", "như thế nào", "cách", "thủ tục", "quy trình",
        "bước", "how to", "steps", "process", "procedure"
    ]
    
    # Factual keywords
    factual_keywords = [
        "điều", "khoản", "quy định", "là gì", "what is", "định nghĩa",
        "nghĩa là", "rule", "article", "regulation"
    ]
    
    # Check procedural first (more specific)
    for kw in procedural_keywords:
        if kw in message_lower:
            return "procedural"
    
    # Check factual
    for kw in factual_keywords:
        if kw in message_lower:
            return "factual"
    
    # Default to conceptual (understanding-based questions)
    return "conceptual"


def _generate_suggested_questions(user_message: str, ai_response: str) -> list[str]:
    """
    Generate 3 suggested follow-up questions based on context.

    Logic:
    1. Detect topic from AI response content
    2. Return context-appropriate suggestions
    3. If no specific topic detected, return generic helpful suggestions
    """
    user_lower = user_message.lower()
    response_lower = ai_response.lower()

    # Generic follow-up suggestions based on conversation context
    if any(kw in response_lower for kw in ['quy tắc', 'rule', 'điều', 'quy định']):
        return [
            "Khi nào áp dụng quy tắc này?",
            "Có ngoại lệ nào không?",
            "Bạn có thể giải thích chi tiết hơn không?"
        ]
    elif any(kw in response_lower for kw in ['an toàn', 'safety', 'thiết bị']):
        return [
            "Yêu cầu cụ thể là gì?",
            "Quy trình kiểm tra như thế nào?",
            "Có tiêu chuẩn nào liên quan không?"
        ]
    elif any(kw in user_lower for kw in ['học', 'tìm hiểu', 'giải thích', 'dạy']):
        return [
            "Bạn muốn tìm hiểu thêm về chủ đề nào?",
            "Bạn cần giải thích chi tiết hơn không?",
            "Bạn muốn làm bài tập thực hành không?"
        ]
    else:
        # Generic helpful suggestions
        return [
            "Bạn muốn tìm hiểu thêm về chủ đề nào?",
            "Bạn có câu hỏi nào khác không?",
            "Tôi có thể giúp gì thêm cho bạn?"
        ]


@router.get(
    "/history/{user_id}",
    response_model=GetHistoryResponse,
    responses={
        200: {"description": "Chat history retrieved successfully"},
        401: {"description": "Authentication required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get user chat history (Phase 2)",
    description="""
    **Lấy lịch sử chat của một user với phân trang.**
    
    Hỗ trợ đồng bộ hóa đa thiết bị trong Phase 2.
    
    **Query Parameters:**
    - `limit`: Số tin nhắn trả về (default: 20, max: 100)
    - `offset`: Vị trí bắt đầu (default: 0)
    
    **Spec: CHỈ THỊ KỸ THUẬT SỐ 11**
    """
)
async def get_chat_history(
    user_id: str,
    auth: RequireAuth,
    limit: int = 20,
    offset: int = 0,
) -> GetHistoryResponse:
    """
    Get paginated chat history for a user.
    
    Args:
        user_id: ID of user whose history to retrieve
        auth: Authenticated via X-API-Key header
        limit: Number of messages to return (default 20, max 100)
        offset: Offset for pagination (default 0)
    
    Returns:
        GetHistoryResponse with messages and pagination info
    """
    try:
        # Validate limit
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 20
        if offset < 0:
            offset = 0
        
        # Get history from repository
        from app.repositories.chat_history_repository import get_chat_history_repository
        
        chat_history_repo = get_chat_history_repository()
        messages, total = chat_history_repo.get_user_history(user_id, limit, offset)
        
        # Convert to response format
        history_messages = [
            HistoryMessage(
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at
            )
            for msg in messages
        ]
        
        logger.info("Retrieved %d messages for user %s (total: %d)", len(history_messages), user_id, total)
        
        return GetHistoryResponse(
            data=history_messages,
            pagination=HistoryPagination(
                total=total,
                limit=limit,
                offset=offset
            )
        )
        
    except Exception as e:
        logger.exception(f"Error retrieving chat history: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "Failed to retrieve chat history"
            }
        )


@router.delete(
    "/history/{user_id}",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Chat history deleted successfully"},
        403: {"description": "Permission denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Delete user chat history",
    description="""
    **Xóa toàn bộ lịch sử chat của một user.**
    
    **Access Control:**
    - `admin`: Có thể xóa lịch sử của bất kỳ user nào
    - `student`/`teacher`: Chỉ có thể xóa lịch sử của chính mình
    """
)
async def delete_chat_history(
    user_id: str,
    request: DeleteHistoryRequest,
    auth: RequireAuth,
) -> DeleteHistoryResponse:
    """
    Delete chat history for a user.
    
    Args:
        user_id: ID of user whose history to delete
        request: Contains role and requesting_user_id
        auth: Authenticated via X-API-Key header
    
    Returns:
        DeleteHistoryResponse with status and count of deleted messages
    """
    try:
        # Check permissions using authenticated role (not request body)
        if auth.role == "admin":
            # Admin can delete any user's history
            pass
        elif auth.role in ["student", "teacher"]:
            # Users can only delete their own history
            if auth.user_id != user_id:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "permission_denied",
                        "message": "Permission denied. Users can only delete their own chat history."
                    }
                )
        else:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "invalid_role",
                    "message": "Permission denied. Invalid role."
                }
            )
        
        # Delete from chat history repository
        from app.repositories.chat_history_repository import get_chat_history_repository
        
        chat_history_repo = get_chat_history_repository()
        deleted_count = chat_history_repo.delete_user_history(user_id)
        
        logger.info(
            "Deleted %d chat messages for user %s by %s (%s)",
            deleted_count, user_id, request.requesting_user_id, request.role
        )
        
        return DeleteHistoryResponse(
            status="deleted",
            user_id=user_id,
            messages_deleted=deleted_count,
            deleted_by=request.requesting_user_id
        )
        
    except Exception as e:
        logger.exception(f"Error deleting chat history: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "Failed to delete chat history"
            }
        )


# =============================================================================
# Sprint 78: Context Management API — User controls for conversation context
# SOTA Reference: Claude /compact, /clear, /context commands
# =============================================================================


@router.post(
    "/context/compact",
    summary="Compact conversation context",
    description="""
    **Tóm tắt lịch sử hội thoại để giải phóng context window.**

    Tương đương `/compact` trong Claude Code.
    Giữ lại 4 tin nhắn gần nhất, tóm tắt phần còn lại thành running summary.
    """,
    responses={
        200: {"description": "Context compacted successfully"},
        401: {"description": "Authentication required"},
    },
)
@limiter.limit("10/minute")
async def compact_context(
    request: Request,
    auth: RequireAuth,
) -> JSONResponse:
    """Compact conversation context — summarize older turns."""
    user_id = auth.user_id
    session_id = request.headers.get("X-Session-ID", "")

    if not session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session", "message": "X-Session-ID header required"},
        )

    try:
        from app.engine.context_manager import get_compactor
        from app.repositories.chat_history_repository import get_chat_history_repository

        compactor = get_compactor()
        chat_history = get_chat_history_repository()

        # Load history (pass user_id for new schema fallback)
        history_list = []
        if chat_history.is_available():
            recent = chat_history.get_recent_messages(session_id, user_id=user_id)
            history_list = [{"role": m.role, "content": m.content} for m in recent]

        # Force compact
        summary = await compactor.force_compact(session_id, history_list, user_id=user_id)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "compacted",
                "session_id": session_id,
                "summary_length": len(summary),
                "messages_summarized": max(0, len(history_list) - 4),
                "message": "Hội thoại đã được tóm tắt thành công.",
            },
        )

    except Exception as e:
        logger.exception("Error compacting context: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "compact_failed", "message": "Failed to compact context"},
        )


@router.post(
    "/context/clear",
    summary="Clear conversation context",
    description="""
    **Xóa toàn bộ context hội thoại và bắt đầu cuộc trò chuyện mới.**

    Tương đương `/clear` trong Claude Code.
    Xóa running summary, memory state, nhưng KHÔNG xóa user facts (Core Memory).
    """,
    responses={
        200: {"description": "Context cleared successfully"},
        401: {"description": "Authentication required"},
    },
)
@limiter.limit("10/minute")
async def clear_context(
    request: Request,
    auth: RequireAuth,
) -> JSONResponse:
    """Clear conversation context — start fresh (preserves user facts)."""
    user_id = auth.user_id  # Sprint 79: needed for DB cleanup
    session_id = request.headers.get("X-Session-ID", "")

    if not session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session", "message": "X-Session-ID header required"},
        )

    try:
        from app.engine.context_manager import get_compactor
        from app.engine.memory_summarizer import get_memory_summarizer

        compactor = get_compactor()
        summarizer = get_memory_summarizer()

        # Clear running summary
        compactor.clear_session(session_id, user_id=user_id)

        # Clear memory summarizer state
        summarizer.clear_session(session_id)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "cleared",
                "session_id": session_id,
                "message": "Context đã được xóa. Bắt đầu cuộc trò chuyện mới.",
            },
        )

    except Exception as e:
        logger.exception("Error clearing context: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "clear_failed", "message": "Failed to clear context"},
        )


@router.get(
    "/context/info",
    summary="Get context usage info",
    description="""
    **Xem thông tin sử dụng context window.**

    Tương đương `/context list` trong Claude Code / OpenClawd `/status`.
    Hiển thị: token budget, utilization, số tin nhắn, running summary.
    """,
    responses={
        200: {"description": "Context info retrieved"},
        401: {"description": "Authentication required"},
    },
)
@limiter.limit("30/minute")
async def get_context_info(
    request: Request,
    auth: RequireAuth,
) -> JSONResponse:
    """Get context usage info for introspection."""
    user_id = auth.user_id
    session_id = request.headers.get("X-Session-ID", "")

    if not session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session", "message": "X-Session-ID header required"},
        )

    try:
        from app.engine.context_manager import get_compactor
        from app.repositories.chat_history_repository import get_chat_history_repository

        compactor = get_compactor()
        chat_history = get_chat_history_repository()

        # Load history (pass user_id for new schema fallback)
        history_list = []
        if chat_history.is_available():
            recent = chat_history.get_recent_messages(session_id, user_id=user_id)
            history_list = [{"role": m.role, "content": m.content} for m in recent]

        info = compactor.get_context_info(
            session_id=session_id,
            history_list=history_list,
            user_id=user_id,
        )

        return JSONResponse(status_code=status.HTTP_200_OK, content=info)

    except Exception as e:
        logger.exception("Error getting context info: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "info_failed", "message": "Failed to get context info"},
        )
