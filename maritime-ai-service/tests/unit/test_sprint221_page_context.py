"""Sprint 221: Page-Aware AI Context — schema tests."""
import pytest
from app.models.schemas import PageContext, StudentPageState, UserContext


class TestPageContext:
    def test_minimal_page_context(self):
        ctx = PageContext(page_type="lesson")
        assert ctx.page_type == "lesson"
        assert ctx.page_title is None
        assert ctx.content_snippet is None

    def test_full_page_context(self):
        ctx = PageContext(
            page_type="quiz",
            page_title="Quiz Chương 3: Khí áp",
            course_id="course-123",
            course_name="Khí Tượng Hải Dương",
            lesson_id="lesson-42",
            lesson_name="Áp suất khí quyển",
            chapter_name="Chương 3: Khí áp và gió",
            content_snippet="Áp suất khí quyển tiêu chuẩn...",
            content_type="exercise",
            quiz_question="Áp suất tại mực nước biển?",
            quiz_options=["760 mmHg", "1013.25 hPa", "Cả A và B"],
            assignment_description=None,
        )
        assert ctx.page_type == "quiz"
        assert ctx.quiz_question == "Áp suất tại mực nước biển?"
        assert len(ctx.quiz_options) == 3

    def test_content_snippet_max_length(self):
        long_text = "x" * 2001
        with pytest.raises(Exception):
            PageContext(page_type="lesson", content_snippet=long_text)

    def test_content_snippet_at_limit(self):
        ctx = PageContext(page_type="lesson", content_snippet="x" * 2000)
        assert len(ctx.content_snippet) == 2000


class TestStudentPageState:
    def test_empty_state(self):
        state = StudentPageState()
        assert state.time_on_page_ms is None
        assert state.scroll_percent is None

    def test_full_state(self):
        state = StudentPageState(
            time_on_page_ms=180000, scroll_percent=45.0,
            quiz_attempts=2, last_answer="A) 760 mmHg",
            is_correct=False, progress_percent=60.0,
        )
        assert state.quiz_attempts == 2
        assert state.is_correct is False


class TestUserContextPageAware:
    def test_user_context_without_page(self):
        ctx = UserContext(display_name="Minh", role="student")
        assert ctx.page_context is None
        assert ctx.student_state is None
        assert ctx.available_actions is None

    def test_user_context_with_page(self):
        ctx = UserContext(
            display_name="Minh", role="student",
            page_context=PageContext(
                page_type="lesson", page_title="Áp suất khí quyển",
                course_name="Khí Tượng Hải Dương",
            ),
            student_state=StudentPageState(time_on_page_ms=180000, scroll_percent=45.0),
            available_actions=[{"action": "navigate", "label": "Bài tiếp theo", "target": "/lessons/43"}],
        )
        assert ctx.page_context.page_type == "lesson"
        assert ctx.student_state.time_on_page_ms == 180000
        assert len(ctx.available_actions) == 1


class TestPageContextPromptFormatting:
    """Sprint 221: format_page_context_for_prompt() tests."""

    def test_format_lesson_context(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        from app.models.schemas import PageContext
        ctx = PageContext(
            page_type="lesson",
            page_title="Áp suất khí quyển",
            course_name="Khí Tượng Hải Dương",
            chapter_name="Chương 3: Khí áp và gió",
            content_type="theory",
            content_snippet="Áp suất khí quyển tiêu chuẩn tại mực nước biển là 1013.25 hPa.",
        )
        result = format_page_context_for_prompt(ctx, student_state=None)
        assert "NGỮ CẢNH TRANG HIỆN TẠI" in result
        assert "Áp suất khí quyển" in result
        assert "Khí Tượng Hải Dương" in result
        assert "1013.25 hPa" in result

    def test_format_quiz_context_no_answer_leak(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        from app.models.schemas import PageContext, StudentPageState
        ctx = PageContext(
            page_type="quiz",
            page_title="Quiz Chương 3",
            course_name="Khí Tượng",
            quiz_question="Áp suất tiêu chuẩn tại mực nước biển?",
            quiz_options=["760 mmHg", "1013.25 hPa", "Cả A và B", "Không đáp án nào"],
        )
        state = StudentPageState(quiz_attempts=2, last_answer="A) 760 mmHg", is_correct=False)
        result = format_page_context_for_prompt(ctx, student_state=state)
        assert "KHÔNG cho đáp án trực tiếp" in result
        assert "Lần thử: 2" in result

    def test_format_dashboard_minimal(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        from app.models.schemas import PageContext
        ctx = PageContext(page_type="dashboard")
        result = format_page_context_for_prompt(ctx, student_state=None)
        assert "NGỮ CẢNH TRANG HIỆN TẠI" in result

    def test_format_none_returns_empty(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        result = format_page_context_for_prompt(None, student_state=None)
        assert result == ""

    def test_format_with_student_state_time(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        from app.models.schemas import PageContext, StudentPageState
        ctx = PageContext(page_type="lesson", page_title="Bài 1")
        state = StudentPageState(time_on_page_ms=180000, scroll_percent=45.0)
        result = format_page_context_for_prompt(ctx, student_state=state)
        assert "3 phút" in result or "180" in result
        assert "45%" in result or "45" in result

    def test_format_with_available_actions(self):
        from app.prompts.prompt_loader import format_page_context_for_prompt
        from app.models.schemas import PageContext
        ctx = PageContext(page_type="lesson", page_title="Bài 1")
        actions = [
            {"action": "navigate", "label": "Bài tiếp theo"},
            {"action": "request_hint", "label": "Xem gợi ý"},
        ]
        result = format_page_context_for_prompt(ctx, student_state=None, available_actions=actions)
        assert "Bài tiếp theo" in result
        assert "Xem gợi ý" in result
