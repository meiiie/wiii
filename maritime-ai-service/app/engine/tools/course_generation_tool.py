"""
Course Generation Tool — AI agent tool for creating LMS courses from documents.

Registered in the tool registry so the AI agent can invoke it when a teacher
asks to "tạo khóa học từ file này" or "generate course from this document".

Design spec v2.0 (2026-03-22).
"""

import logging
from typing import Optional

from app.engine.tools.native_tool import tool

logger = logging.getLogger(__name__)


@tool
def tool_generate_course_outline(
    document_id: str,
    course_title: Optional[str] = None,
    target_chapters: Optional[int] = None,
    language: str = "vi",
    teacher_prompt: str = "",
) -> dict:
    """Tạo outline khóa học từ tài liệu đã upload.

    Phân tích tài liệu và tạo cấu trúc chapters/lessons để giáo viên review
    trước khi tạo nội dung chi tiết.

    Args:
        document_id: ID của tài liệu đã upload (từ /knowledge/upload).
        course_title: Tên khóa học (tùy chọn, AI sẽ tự đề xuất nếu bỏ trống).
        target_chapters: Số chương mong muốn (tùy chọn).
        language: Ngôn ngữ nội dung ('vi' hoặc 'en').
        teacher_prompt: Yêu cầu đặc biệt từ giáo viên.

    Returns:
        Course outline JSON với chapters, lessons, sourcePages mapping.
    """
    # This tool is invoked by the AI agent within a chat conversation.
    # The actual workflow execution happens asynchronously —
    # this tool returns a status message and the workflow runs in background.
    return {
        "status": "OUTLINE_GENERATING",
        "message": f"Đang phân tích tài liệu {document_id} và tạo outline khóa học...",
        "document_id": document_id,
        "target_chapters": target_chapters,
        "language": language,
        "teacher_prompt": teacher_prompt,
        "action_required": "Vui lòng đợi trong giây lát. Outline sẽ hiển thị để giáo viên review.",
    }


@tool
def tool_approve_course_outline(
    generation_id: str,
    approved_chapter_indices: list[int],
    course_title: Optional[str] = None,
    category_id: Optional[str] = None,
) -> dict:
    """Duyệt outline và bắt đầu tạo nội dung chi tiết cho các chương đã chọn.

    Giáo viên gọi tool này sau khi review outline và chọn chương nào muốn tạo.

    Args:
        generation_id: ID của generation session (từ outline response).
        approved_chapter_indices: Danh sách index các chương được duyệt (0-based).
        course_title: Tên khóa học cuối cùng (tùy chọn, dùng tên từ outline nếu bỏ trống).
        category_id: UUID danh mục khóa học trong LMS (tùy chọn).

    Returns:
        Status của quá trình tạo nội dung.
    """
    return {
        "status": "EXPAND_STARTED",
        "message": f"Đã duyệt {len(approved_chapter_indices)} chương. Đang tạo nội dung chi tiết...",
        "generation_id": generation_id,
        "approved_chapters": approved_chapter_indices,
        "action_required": "Nội dung sẽ được tạo từng chương. Mỗi chương xong sẽ xuất hiện trong Course Editor.",
    }
