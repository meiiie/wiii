"""LMS Host Adapter — Vietnamese prompt formatting, Socratic quiz guardrails.

Sprint 222: Universal Context Engine.
Converts HostContext from an LMS host into a Vietnamese XML block
with page-type-aware instructions and Socratic guardrails for quizzes.
"""
from app.engine.context.adapters.base import HostAdapter
from app.engine.context.host_context import HostContext

_PAGE_LABELS: dict[str, str] = {
    "dashboard": "Trang chủ",
    "lesson": "Bài giảng",
    "course_overview": "Tổng quan khóa học",
    "course_list": "Danh sách khóa học",
    "quiz": "Bài kiểm tra",
    "exam": "Bài thi",
    "assignment": "Bài tập",
    "resource": "Tài liệu",
    "forum": "Diễn đàn",
    "grades": "Bảng điểm",
    "settings": "Cài đặt",
}

_PAGE_SKILL_MAP: dict[str, list[str]] = {
    "lesson": ["lms-lesson"],
    "quiz": ["lms-quiz"],
    "exam": ["lms-quiz"],
    "assignment": ["lms-assignment"],
}


class LMSHostAdapter(HostAdapter):
    """Adapter for LMS hosts — Vietnamese output with Socratic pedagogy."""

    host_type = "lms"

    def format_context_for_prompt(self, ctx: HostContext) -> str:
        page = ctx.page
        page_type = page.get("type", "unknown")
        page_title = page.get("title", "")
        metadata = page.get("metadata", {})
        page_label = _PAGE_LABELS.get(page_type, page_type)

        parts: list[str] = [f'<host_context type="lms" page_type="{page_type}">']
        parts.append(f"  <page>{page_label} — {page_title}</page>")

        # Course and chapter metadata
        course_name = metadata.get("course_name")
        if course_name:
            parts.append(f"  <course>{course_name}</course>")
        chapter = metadata.get("chapter_name")
        if chapter:
            parts.append(f"  <chapter>{chapter}</chapter>")

        # Content snippet
        if ctx.content and ctx.content.get("snippet"):
            parts.append(f'  <content>{ctx.content["snippet"]}</content>')

        # Quiz question and options
        quiz_q = metadata.get("quiz_question")
        if quiz_q:
            parts.append(f"  <quiz_question>{quiz_q}</quiz_question>")
            quiz_opts = metadata.get("quiz_options", [])
            if quiz_opts:
                opts_str = " | ".join(
                    f"{chr(65 + i)}) {opt}" for i, opt in enumerate(quiz_opts)
                )
                parts.append(f"  <quiz_options>{opts_str}</quiz_options>")

        # User state
        if ctx.user_state:
            state_parts = self._format_user_state(ctx.user_state)
            if state_parts:
                parts.append(
                    f"  <user_state>{'; '.join(state_parts)}</user_state>"
                )

        # Available actions
        if ctx.available_actions:
            labels = [
                a.get("label", a.get("action", ""))
                for a in ctx.available_actions
            ]
            labels = [lb for lb in labels if lb]
            if labels:
                parts.append(
                    f"  <available_actions>{', '.join(labels)}</available_actions>"
                )

        # Page-type-specific instructions
        if page_type in ("quiz", "exam"):
            parts.append(
                "  <instruction>"
                "KHÔNG cho đáp án trực tiếp. Hướng dẫn Socratic."
                "</instruction>"
            )
        elif page_type == "lesson":
            parts.append(
                "  <instruction>"
                "Hỗ trợ sinh viên hiểu bài giảng, gợi ý Socratic."
                "</instruction>"
            )
        else:
            parts.append(
                "  <instruction>"
                "Liên hệ nội dung trang khi trả lời."
                "</instruction>"
            )

        parts.append("</host_context>")
        return "\n".join(parts)

    def get_page_skill_ids(self, ctx: HostContext) -> list[str]:
        page_type = ctx.page.get("type", "unknown")
        return _PAGE_SKILL_MAP.get(page_type, ["lms-default"])

    @staticmethod
    def _format_user_state(user_state: dict) -> list[str]:
        """Build Vietnamese user-state description fragments."""
        state_parts: list[str] = []

        time_ms = user_state.get("time_on_page_ms")
        if time_ms is not None:
            minutes = time_ms // 60000
            if minutes > 0:
                state_parts.append(f"Thời gian: {minutes} phút")

        scroll = user_state.get("scroll_percent")
        if scroll is not None:
            state_parts.append(f"Đã đọc: {scroll:.0f}%")

        attempts = user_state.get("quiz_attempts")
        if attempts is not None:
            state_parts.append(f"Lần thử: {attempts}")
            last_answer = user_state.get("last_answer")
            if last_answer:
                correct = (
                    "Đúng" if user_state.get("is_correct") else "Sai"
                )
                state_parts.append(f'Đáp án trước: "{last_answer}" → {correct}')

        progress = user_state.get("progress_percent")
        if progress is not None:
            state_parts.append(f"Tiến độ: {progress:.0f}%")

        return state_parts
