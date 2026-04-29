"""LMS Host Adapter - Vietnamese prompt formatting with role/stage awareness."""

from app.engine.context.adapters.base import HostAdapter
from app.engine.context.host_context import HostContext

_PAGE_LABELS: dict[str, str] = {
    "dashboard": "Trang chủ",
    "lesson": "Bài giảng",
    "course_overview": "Tổng quan khóa học",
    "course_list": "Danh sách khóa học",
    "course_detail": "Chi tiết khóa học",
    "course_editor": "Trình soạn khóa học",
    "quiz": "Bài kiểm tra",
    "exam": "Bài thi",
    "assignment": "Bài tập",
    "assignment_list": "Danh sách bài tập",
    "resource": "Tài liệu",
    "forum": "Diễn đàn",
    "grades": "Bảng điểm",
    "analytics": "Phân tích",
    "teacher_page": "Không gian giảng viên",
    "admin_page": "Không gian quản trị",
    "settings": "Cài đặt",
}

_PAGE_SKILL_MAP: dict[str, list[str]] = {
    "lesson": ["lms-lesson"],
    "quiz": ["lms-quiz"],
    "exam": ["lms-quiz"],
    "assignment": ["lms-assignment"],
    "course_editor": [
        "lms-teacher-course-editor",
        "lms-teacher-doc-to-course",
        "lms-teacher-lesson-experience",
        "lms-teacher-quiz-orchestrator",
    ],
    "analytics": ["lms-org-admin-governance", "lms-system-admin-ops"],
    "admin_page": ["lms-org-admin-governance", "lms-system-admin-ops"],
    "teacher_page": ["lms-teacher-course-editor"],
}


class LMSHostAdapter(HostAdapter):
    """Adapter for LMS hosts with Vietnamese, role-aware prompt shaping."""

    host_type = "lms"

    def format_context_for_prompt(self, ctx: HostContext) -> str:
        page = ctx.page
        page_type = page.get("type", "unknown")
        page_title = page.get("title", "")
        metadata = page.get("metadata", {})
        page_label = _PAGE_LABELS.get(page_type, page_type)

        parts: list[str] = [f'<host_context type="lms" page_type="{page_type}">']
        parts.append(f"  <page>{page_label} - {page_title}</page>")
        if ctx.connector_id:
            parts.append(f"  <connector>{ctx.connector_id}</connector>")
        if ctx.host_workspace_id:
            parts.append(f"  <workspace>{ctx.host_workspace_id}</workspace>")
        if ctx.host_organization_id:
            parts.append(f"  <host_organization>{ctx.host_organization_id}</host_organization>")

        if ctx.user_role:
            parts.append(f"  <user_role>{ctx.user_role}</user_role>")
        if ctx.workflow_stage:
            parts.append(f"  <workflow_stage>{ctx.workflow_stage}</workflow_stage>")

        course_name = metadata.get("course_name")
        if course_name:
            parts.append(f"  <course>{course_name}</course>")
        chapter = metadata.get("chapter_name")
        if chapter:
            parts.append(f"  <chapter>{chapter}</chapter>")
        requested_action = metadata.get("action")
        if requested_action:
            parts.append(f"  <requested_action>{requested_action}</requested_action>")

        if ctx.content and ctx.content.get("snippet"):
            parts.append(f'  <content>{ctx.content["snippet"]}</content>')

        quiz_q = metadata.get("quiz_question")
        if quiz_q:
            parts.append(f"  <quiz_question>{quiz_q}</quiz_question>")
            quiz_opts = metadata.get("quiz_options", [])
            if quiz_opts:
                opts_str = " | ".join(
                    f"{chr(65 + i)}) {opt}" for i, opt in enumerate(quiz_opts)
                )
                parts.append(f"  <quiz_options>{opts_str}</quiz_options>")

        if ctx.user_state:
            state_parts = self._format_user_state(ctx.user_state)
            if state_parts:
                parts.append(f"  <user_state>{'; '.join(state_parts)}</user_state>")

        if ctx.selection:
            selected_type = str(ctx.selection.get("type", "")).strip()
            selected_label = str(ctx.selection.get("label", "")).strip()
            if selected_type or selected_label:
                parts.append(f"  <selection>{selected_type} - {selected_label}</selection>")

        if ctx.editable_scope:
            scope_type = str(ctx.editable_scope.get("type", "")).strip()
            allowed = ctx.editable_scope.get("allowed_operations", [])
            if scope_type or allowed:
                allowed_str = ", ".join(str(item) for item in allowed) if isinstance(allowed, list) else ""
                parts.append(f"  <editable_scope>{scope_type}; ops={allowed_str}</editable_scope>")

        if ctx.entity_refs:
            labels = []
            for ref in ctx.entity_refs[:6]:
                if not isinstance(ref, dict):
                    continue
                ref_type = str(ref.get("type", "")).strip()
                ref_title = str(ref.get("title", "")).strip()
                if ref_type or ref_title:
                    labels.append(f"{ref_type}:{ref_title}")
            if labels:
                parts.append(f"  <entity_refs>{' | '.join(labels)}</entity_refs>")

        available_targets = metadata.get("available_targets")
        if isinstance(available_targets, list):
            target_labels: list[str] = []
            for target in available_targets[:24]:
                if not isinstance(target, dict):
                    continue
                target_id = str(target.get("id", "")).strip()
                if not target_id:
                    continue
                label = str(target.get("label", "")).strip()
                selector = str(target.get("selector", "")).strip()
                text = target_id
                if label:
                    text = f'{text}="{label[:80]}"'
                if selector and selector != target_id:
                    text = f"{text} selector={selector}"
                if target.get("click_safe") is True:
                    click_kind = str(target.get("click_kind", "")).strip()
                    text = f"{text} click_safe=true"
                    if click_kind:
                        text = f"{text} click_kind={click_kind}"
                target_labels.append(text)
            if target_labels:
                parts.append(f"  <available_targets>{' | '.join(target_labels)}</available_targets>")

        if ctx.available_actions:
            labels = [
                (
                    f"{a.get('label', a.get('name', a.get('action', '')))}"
                    f"{' [confirm]' if a.get('requires_confirmation') else ''}"
                    f"{' [write]' if a.get('mutates_state') else ''}"
                )
                for a in ctx.available_actions
            ]
            labels = [label for label in labels if label]
            if labels:
                parts.append(f"  <available_actions>{', '.join(labels)}</available_actions>")

        if page_type in ("quiz", "exam"):
            parts.append(
                "  <instruction>"
                "KHÔNG cho đáp án trực tiếp. Hướng dẫn Socratic. "
                "Khong chon phuong an dung ho, khong hoan thanh bai lam ho."
                "</instruction>"
            )
        elif page_type == "assignment":
            parts.append(
                "  <instruction>"
                "Khong viet ho bai nop hoan chinh hoac dap an cuoi cung. "
                "Huong dan cach tiep can, dan y, rubric, va goi y tung buoc de nguoi hoc tu hoan thanh."
                "</instruction>"
            )
        elif page_type == "lesson":
            parts.append(
                "  <instruction>"
                "Hỗ trợ người học hiểu bài giảng, gợi mở Socratic và bám sát nội dung đang xem."
                "</instruction>"
            )
        elif page_type == "course_editor":
            if requested_action == "generate_lesson":
                parts.append(
                    "  <instruction>"
                    "Người dùng đang chủ động mở Wiii để tạo bài giảng hoặc cấu trúc khóa học từ ngữ cảnh Course Editor hiện tại."
                    "</instruction>"
                )
            else:
                parts.append(
                    "  <instruction>"
                    "Đây là bối cảnh authoring. Ưu tiên host actions, preview trước commit, và chỉnh lesson bằng cấu trúc trước khi nghĩ tới code tự do."
                    "</instruction>"
                )
        elif page_type in {"analytics", "admin_page"}:
            parts.append(
                "  <instruction>"
                "Giữ câu trả lời ngắn, rõ, audit-friendly, và nêu rõ phạm vi ảnh hưởng trước khi đề xuất hành động."
                "</instruction>"
            )
        else:
            parts.append(
                "  <instruction>"
                "Liên hệ nội dung trang khi trả lời."
                "</instruction>"
            )

        try:
            from app.core.config import get_settings

            if getattr(get_settings(), "enable_rich_page_context", False):
                from app.engine.context.host_context import format_structured_data_for_prompt

                structured_text = format_structured_data_for_prompt(ctx)
                if structured_text:
                    parts.append(f"  <data>\n{structured_text}\n  </data>")
        except Exception:
            pass

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
                correct = "Đúng" if user_state.get("is_correct") else "Sai"
                state_parts.append(f'Đáp án trước: "{last_answer}" -> {correct}')

        progress = user_state.get("progress_percent")
        if progress is not None:
            state_parts.append(f"Tiến độ: {progress:.0f}%")

        return state_parts
