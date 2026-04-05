"""Prompt page-context formatting helpers."""

from __future__ import annotations


def format_page_context_for_prompt_impl(
    page_context,
    student_state=None,
    available_actions=None,
) -> str:
    """Format page context for system prompt injection (Sprint 221)."""
    if not page_context:
        return ""

    page_labels = {
        "dashboard": "Trang chủ",
        "lesson": "Bài giảng",
        "quiz": "Bài kiểm tra",
        "assignment": "Bài tập",
        "resource": "Tài liệu",
        "forum": "Diễn đàn",
        "grades": "Bảng điểm",
        "settings": "Cài đặt",
    }

    parts = ["--- NGỮ CẢNH TRANG HIỆN TẠI ---"]

    page_label = page_labels.get(page_context.page_type or "", page_context.page_type or "Trang")
    title_part = f' — "{page_context.page_title}"' if page_context.page_title else ""
    chapter_part = f" ({page_context.chapter_name})" if page_context.chapter_name else ""
    parts.append(f"📍 Trang: {page_label}{title_part}{chapter_part}")

    if page_context.course_name:
        parts.append(f"📚 Môn: {page_context.course_name}")

    if page_context.content_type:
        content_labels = {
            "theory": "Lý thuyết",
            "exercise": "Bài tập",
            "video": "Video",
            "pdf": "Tài liệu PDF",
            "discussion": "Thảo luận",
        }
        parts.append(
            f"📝 Loại: {content_labels.get(page_context.content_type, page_context.content_type)}"
        )

    if page_context.content_snippet:
        parts.append(f'\nNội dung đang xem:\n"{page_context.content_snippet}"')

    if page_context.quiz_question:
        parts.append(f'\nCâu hỏi đang làm:\n"{page_context.quiz_question}"')
        if page_context.quiz_options:
            for i, opt in enumerate(page_context.quiz_options):
                label = chr(65 + i)
                parts.append(f"  {label}) {opt}")

    if student_state:
        state_lines = []
        if student_state.time_on_page_ms is not None:
            minutes = student_state.time_on_page_ms // 60000
            if minutes > 0:
                state_lines.append(f"⏱️ Thời gian trên trang: {minutes} phút")
        if student_state.scroll_percent is not None:
            state_lines.append(f"📖 Đã đọc: {student_state.scroll_percent:.0f}%")
        if student_state.quiz_attempts is not None:
            state_lines.append(f"Lần thử: {student_state.quiz_attempts}")
            if student_state.last_answer:
                correctness = "Đúng" if student_state.is_correct else "Sai"
                state_lines.append(f'Đáp án trước: "{student_state.last_answer}" → {correctness}')
        if student_state.progress_percent is not None:
            state_lines.append(f"📊 Tiến độ: {student_state.progress_percent:.0f}%")
        if state_lines:
            parts.append("\nTrạng thái:\n- " + "\n- ".join(state_lines))

    if available_actions:
        action_labels = [a.get("label", a.get("action", "")) for a in available_actions]
        if action_labels:
            parts.append("\nHành động có sẵn: " + ", ".join(action_labels))

    if page_context.page_type == "quiz":
        parts.append(
            "\n⚠️ QUAN TRỌNG: KHÔNG cho đáp án trực tiếp."
            "\nHướng dẫn Socratic: gợi mở để sinh viên suy nghĩ."
            "\nNếu đã sai 3+ lần → có thể gợi ý rõ hơn."
        )
    else:
        parts.append(
            "\n⚠️ Sinh viên đang xem nội dung này — khi hỏi, hãy liên hệ trực tiếp."
            "\nGợi ý Socratic (hỏi gợi mở), không cho đáp án trực tiếp."
        )

    return "\n".join(parts)
