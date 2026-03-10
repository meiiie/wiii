"""
Sprint 220: "Cắm Phích" — LMS Hàng Hải Production Connection Tests

Tests for:
  - LMSContextLoader: caching, data aggregation, prompt formatting
  - LMS prompt injection: system prompt includes LMS data
  - LMS tool registration: tools registered when gate enabled
  - LMSInsightGenerator: conversation analysis, push flow
  - Webhook cache invalidation: fresh data after events
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# 1. LMSContextLoader Tests
# =============================================================================


class TestLMSContextLoader:
    """Test on-demand LMS data fetch + caching."""

    def _make_loader(self):
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        loader.clear_cache()
        return loader

    def _mock_connector(self):
        """Create a mock connector with student data."""
        from app.integrations.lms.models import (
            LMSGrade,
            LMSStudentProfile,
            LMSUpcomingAssignment,
        )

        connector = MagicMock()
        connector.get_student_profile.return_value = LMSStudentProfile(
            id="student-1",
            name="Nguyễn Văn A",
            email="a@maritime.edu",
            program="Điều khiển tàu biển",
            class_name="ĐKTB K62A",
        )
        connector.get_student_grades.return_value = [
            LMSGrade(course_id="NHH101", course_name="Luật Hàng Hải", grade=7.5, max_grade=10),
            LMSGrade(course_id="NHH102", course_name="An Toàn Hàng Hải", grade=8.0, max_grade=10),
            LMSGrade(course_id="NHH103", course_name="MARPOL", grade=5.5, max_grade=10),
        ]
        connector.get_upcoming_assignments.return_value = [
            LMSUpcomingAssignment(
                assignment_id="a1",
                assignment_name="Bài kiểm tra COLREGs",
                course_id="NHH101",
                course_name="Luật Hàng Hải",
                due_date=datetime(2026, 3, 5, 23, 59, tzinfo=timezone.utc),
            ),
        ]
        connector.get_student_enrollments.return_value = [
            {"course_id": "NHH101", "course_name": "Luật Hàng Hải"},
            {"course_id": "NHH102", "course_name": "An Toàn Hàng Hải"},
        ]
        connector.get_student_quiz_history.return_value = [
            {"quiz_id": "q1", "quiz_name": "Quiz SOLAS", "score": 85, "max_score": 100, "course_id": "NHH102"},
            {"quiz_id": "q2", "quiz_name": "Quiz MARPOL", "score": 55, "max_score": 100, "course_id": "NHH103"},
        ]
        return connector

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_load_student_context_success(self, mock_registry):
        """Successfully loads student context from LMS."""
        connector = self._mock_connector()
        mock_registry.return_value.get.return_value = connector

        loader = self._make_loader()
        # Sprint 220c: connector_id is now required (no hardcoded default)
        ctx = loader.load_student_context("student-1", connector_id="maritime-lms")

        assert ctx is not None
        assert ctx.student_id == "student-1"
        assert ctx.name == "Nguyễn Văn A"
        assert ctx.program == "Điều khiển tàu biển"
        assert len(ctx.grades) == 3
        assert len(ctx.upcoming_assignments) == 1
        assert len(ctx.enrollments) == 2
        assert len(ctx.quiz_history) == 2

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_load_student_context_caching(self, mock_registry):
        """Context is cached for 5 minutes."""
        connector = self._mock_connector()
        mock_registry.return_value.get.return_value = connector

        loader = self._make_loader()
        ctx1 = loader.load_student_context("student-1", connector_id="maritime-lms")
        ctx2 = loader.load_student_context("student-1", connector_id="maritime-lms")

        assert ctx1 is ctx2  # Same object from cache
        # Connector methods called only once (first load)
        assert connector.get_student_profile.call_count == 1

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_cache_invalidation(self, mock_registry):
        """Cache invalidation forces re-fetch."""
        connector = self._mock_connector()
        mock_registry.return_value.get.return_value = connector

        loader = self._make_loader()
        loader.load_student_context("student-1", connector_id="maritime-lms")
        loader.invalidate_cache("student-1", connector_id="maritime-lms")
        loader.load_student_context("student-1", connector_id="maritime-lms")

        # Should be called twice (initial + after invalidation)
        assert connector.get_student_profile.call_count == 2

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_connector_not_found(self, mock_registry):
        """Returns None when connector not found."""
        mock_registry.return_value.get.return_value = None

        loader = self._make_loader()
        ctx = loader.load_student_context("student-1", connector_id="maritime-lms")
        assert ctx is None

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_no_data_returns_none(self, mock_registry):
        """Returns None when no LMS data available."""
        connector = MagicMock()
        connector.get_student_profile.return_value = None
        connector.get_student_grades.return_value = []
        connector.get_upcoming_assignments.return_value = []
        connector.get_student_enrollments.return_value = []
        connector.get_student_quiz_history.return_value = []
        mock_registry.return_value.get.return_value = connector

        loader = self._make_loader()
        ctx = loader.load_student_context("student-1", connector_id="maritime-lms")
        assert ctx is None

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_exception_returns_none(self, mock_registry):
        """Returns None on exception (never crashes)."""
        mock_registry.return_value.get.side_effect = RuntimeError("DB down")

        loader = self._make_loader()
        ctx = loader.load_student_context("student-1", connector_id="maritime-lms")
        assert ctx is None


# =============================================================================
# 2. Prompt Formatting Tests
# =============================================================================


class TestLMSPromptFormatting:
    """Test format_for_prompt() Vietnamese output."""

    def _make_context(self):
        from app.integrations.lms.context_loader import LMSStudentContext
        return LMSStudentContext(
            student_id="student-1",
            name="Nguyễn Văn A",
            program="Điều khiển tàu biển",
            class_name="ĐKTB K62A",
            grades=[
                {"course_id": "NHH101", "course_name": "Luật Hàng Hải", "grade": 7.5, "max_grade": 10, "percentage": 75.0, "date": None},
                {"course_id": "NHH103", "course_name": "MARPOL", "grade": 5.5, "max_grade": 10, "percentage": 55.0, "date": None},
            ],
            upcoming_assignments=[
                {"assignment_id": "a1", "assignment_name": "Bài kiểm tra COLREGs", "course_id": "NHH101", "course_name": "Luật Hàng Hải", "due_date": "05/03/2026 23:59"},
            ],
            quiz_history=[
                {"quiz_id": "q1", "quiz_name": "Quiz SOLAS", "score": 85, "max_score": 100},
                {"quiz_id": "q2", "quiz_name": "Quiz MARPOL", "score": 55, "max_score": 100},
            ],
        )

    def test_format_includes_student_info(self):
        """Format includes student name, program, class."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "Nguyễn Văn A" in text
        assert "Điều khiển tàu biển" in text
        assert "ĐKTB K62A" in text

    def test_format_includes_grades(self):
        """Format includes course grades with emoji indicators."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "Luật Hàng Hải" in text
        assert "MARPOL" in text
        # Grade indicators
        assert "🟡" in text  # 75% = yellow
        assert "🔴" in text  # 55% = red

    def test_format_includes_assignments(self):
        """Format includes upcoming assignments."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "Bài kiểm tra COLREGs" in text
        assert "05/03/2026" in text

    def test_format_includes_quiz_history(self):
        """Format includes quiz results with pass/fail indicators."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "Quiz SOLAS" in text
        assert "Quiz MARPOL" in text
        assert "✅" in text  # 85% = pass
        assert "⚠️" in text  # 55% = warning

    def test_format_header(self):
        """Format starts with the LMS section header."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "THÔNG TIN HỌC TẬP (từ LMS)" in text

    def test_format_includes_usage_instruction(self):
        """Format includes instruction for AI to use LMS data."""
        from app.integrations.lms.context_loader import LMSContextLoader
        loader = LMSContextLoader()
        ctx = self._make_context()
        text = loader.format_for_prompt(ctx)

        assert "cá nhân hóa" in text


# =============================================================================
# 3. LMS Prompt Injection Tests
# =============================================================================


class TestLMSPromptInjection:
    """Test that build_system_prompt injects LMS context."""

    @patch("app.integrations.lms.context_loader.get_lms_context_loader")
    def test_lms_context_injected_when_enabled(self, mock_loader_fn):
        """LMS context is injected when enable_lms_integration=True."""
        from app.integrations.lms.context_loader import LMSStudentContext

        mock_ctx = LMSStudentContext(
            student_id="s1",
            name="Test Student",
            grades=[{"course_id": "C1", "course_name": "Nav", "grade": 8, "max_grade": 10, "percentage": 80, "date": None}],
        )
        mock_loader = MagicMock()
        mock_loader.load_student_context.return_value = mock_ctx
        mock_loader.format_for_prompt.return_value = "--- THÔNG TIN HỌC TẬP (từ LMS) ---\nTest data"
        mock_loader_fn.return_value = mock_loader

        with patch("app.core.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.enable_lms_integration = True
            mock_get_settings.return_value = mock_settings

            from app.prompts.prompt_loader import PromptLoader
            loader = PromptLoader()
            prompt = loader.build_system_prompt(
                role="student",
                user_id="s1",
            )

        assert "THÔNG TIN HỌC TẬP" in prompt

    @patch("app.core.config.settings")
    def test_lms_context_not_injected_when_disabled(self, mock_settings):
        """LMS context is NOT injected when enable_lms_integration=False."""
        mock_settings.enable_lms_integration = False

        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="student",
            user_id="s1",
        )

        assert "THÔNG TIN HỌC TẬP (từ LMS)" not in prompt

    def test_lms_context_skipped_without_user_id(self):
        """LMS context injection is skipped when no user_id."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")

        assert "THÔNG TIN HỌC TẬP (từ LMS)" not in prompt


# =============================================================================
# 4. LMS Tool Registration Tests
# =============================================================================


class TestLMSToolRegistration:
    """Test that LMS tools are registered in the tool registry."""

    def test_register_lms_tools(self):
        """register_lms_tools registers all 5 tools."""
        from app.engine.tools.registry import ToolRegistry

        registry = ToolRegistry()
        with patch("app.engine.tools.lms_tools.get_tool_registry", return_value=registry):
            from app.engine.tools.lms_tools import register_lms_tools
            register_lms_tools()

        names = registry.get_all_names()
        assert "tool_check_student_grades" in names
        assert "tool_list_upcoming_assignments" in names
        assert "tool_check_course_progress" in names
        assert "tool_get_class_overview" in names
        assert "tool_find_at_risk_students" in names

    def test_lms_student_tools_count(self):
        """3 student tools available."""
        from app.engine.tools.lms_tools import get_lms_student_tools
        assert len(get_lms_student_tools()) == 3

    def test_lms_teacher_tools_count(self):
        """2 teacher tools available."""
        from app.engine.tools.lms_tools import get_lms_teacher_tools
        assert len(get_lms_teacher_tools()) == 2

    def test_get_all_lms_tools_student(self):
        """Students get 3 tools."""
        from app.engine.tools.lms_tools import get_all_lms_tools
        assert len(get_all_lms_tools(role="student")) == 3

    def test_get_all_lms_tools_teacher(self):
        """Teachers get all 5 tools."""
        from app.engine.tools.lms_tools import get_all_lms_tools
        assert len(get_all_lms_tools(role="teacher")) == 5


# =============================================================================
# 5. LMS Insight Generator Tests
# =============================================================================


class TestLMSInsightGenerator:
    """Test post-conversation insight analysis."""

    def _make_generator(self):
        from app.integrations.lms.insight_generator import LMSInsightGenerator
        return LMSInsightGenerator()

    def _make_context_with_weak_grades(self):
        from app.integrations.lms.context_loader import LMSStudentContext
        return LMSStudentContext(
            student_id="s1",
            name="Test",
            grades=[
                {"course_id": "NHH103", "course_name": "MARPOL", "grade": 5.0, "max_grade": 10, "percentage": 50.0, "date": None},
                {"course_id": "NHH101", "course_name": "Luật Hàng Hải", "grade": 8.5, "max_grade": 10, "percentage": 85.0, "date": None},
            ],
        )

    def test_knowledge_gap_detected(self):
        """Detects knowledge gap when student asks about a weak topic."""
        gen = self._make_generator()
        ctx = self._make_context_with_weak_grades()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="Em muốn hỏi về quy định MARPOL về xả thải ra biển",
            response="MARPOL Annex I quy định...",
            lms_context=ctx,
        )

        knowledge_gaps = [i for i in insights if i.insight_type == "knowledge_gap"]
        assert len(knowledge_gaps) >= 1
        assert "MARPOL" in knowledge_gaps[0].content
        assert knowledge_gaps[0].related_course_id == "NHH103"

    def test_no_gap_for_strong_topic(self):
        """No knowledge gap when student asks about a strong topic."""
        gen = self._make_generator()
        ctx = self._make_context_with_weak_grades()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="Cho em hỏi về Luật Hàng Hải quốc tế",
            response="Luật Hàng Hải quốc tế bao gồm...",
            lms_context=ctx,
        )

        knowledge_gaps = [i for i in insights if i.insight_type == "knowledge_gap"]
        assert len(knowledge_gaps) == 0  # 85% is not a weak grade

    def test_engagement_detected(self):
        """Detects engagement when student explores deeply."""
        gen = self._make_generator()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="Tại sao quy định COLREG lại khác biệt so với SOLAS trong trường hợp tàu container? Em muốn phân tích sâu hơn về ứng dụng thực tế",
            response="Đây là câu hỏi hay...",
        )

        engagement = [i for i in insights if i.insight_type == "engagement"]
        assert len(engagement) >= 1

    def test_confusion_detected(self):
        """Detects confusion signals."""
        gen = self._make_generator()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="Em không hiểu phần này, giải thích lại cho em được không?",
            response="Để mình giải thích lại...",
        )

        confusion = [i for i in insights if i.insight_type == "confusion"]
        assert len(confusion) >= 1

    def test_trivial_message_no_insights(self):
        """No insights for trivial messages (greetings, etc.)."""
        gen = self._make_generator()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="Chào Wiii!",
            response="Chào bạn!",
        )

        assert len(insights) == 0

    def test_short_message_no_insights(self):
        """No insights for very short messages."""
        gen = self._make_generator()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="ok",
            response="Rồi!",
        )

        assert len(insights) == 0

    def test_empty_message_no_insights(self):
        """No insights for empty messages."""
        gen = self._make_generator()

        insights = gen.analyze_conversation(
            user_id="s1",
            message="",
            response="",
        )

        assert len(insights) == 0


class TestInsightPushFlow:
    """Test the fire-and-forget insight push to LMS."""

    @pytest.mark.asyncio
    async def test_analyze_and_push_no_crash(self):
        """analyze_and_push_insights never crashes (fire-and-forget)."""
        from app.integrations.lms.insight_generator import analyze_and_push_insights

        # Even with no connector, should not raise
        with patch("app.integrations.lms.push_service.get_push_service", return_value=None):
            await analyze_and_push_insights(
                user_id="s1",
                message="Em muốn hỏi về MARPOL",
                response="MARPOL là...",
            )

    @pytest.mark.asyncio
    async def test_analyze_and_push_calls_push_service(self):
        """Insights are pushed via push_service when available."""
        from app.integrations.lms.context_loader import LMSStudentContext
        from app.integrations.lms.insight_generator import analyze_and_push_insights

        ctx = LMSStudentContext(
            student_id="s1",
            name="Test",
            grades=[
                {"course_id": "NHH103", "course_name": "MARPOL", "grade": 4.0, "max_grade": 10, "percentage": 40.0, "date": None},
            ],
        )

        mock_push = MagicMock()
        mock_push.push_student_insight.return_value = True

        with patch("app.integrations.lms.push_service.get_push_service", return_value=mock_push):
            await analyze_and_push_insights(
                user_id="s1",
                message="Em muốn hỏi về quy định MARPOL về xả nước dằn",
                response="MARPOL Annex I quy định...",
                lms_context=ctx,
            )

        # Should have been called at least once (knowledge_gap insight)
        assert mock_push.push_student_insight.called

    @pytest.mark.asyncio
    async def test_analyze_and_push_swallows_exceptions(self):
        """analyze_and_push_insights swallows all exceptions."""
        from app.integrations.lms.insight_generator import analyze_and_push_insights

        with patch("app.integrations.lms.push_service.get_push_service", side_effect=RuntimeError("boom")):
            # Should not raise
            await analyze_and_push_insights(
                user_id="s1",
                message="Test message about navigation rules",
                response="Navigation rules state...",
            )


# =============================================================================
# 6. Webhook Cache Invalidation Tests
# =============================================================================


class TestWebhookCacheInvalidation:
    """Test that webhook events invalidate the LMS context cache."""

    @pytest.mark.asyncio
    async def test_grade_saved_invalidates_cache(self):
        """grade_saved webhook invalidates student's context cache."""
        from app.integrations.lms.context_loader import get_lms_context_loader
        from app.integrations.lms.models import LMSWebhookEvent, LMSWebhookEventType
        from app.integrations.lms.webhook_handler import LMSWebhookHandler

        # Pre-populate cache
        loader = get_lms_context_loader()
        from app.integrations.lms.context_loader import _context_cache, LMSStudentContext
        _context_cache["student-1"] = (LMSStudentContext(student_id="student-1"), time.time())

        assert "student-1" in _context_cache

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={"student_id": "student-1", "course_id": "C1", "grade": 8.0, "max_grade": 10},
        )

        handler = LMSWebhookHandler()
        with patch.object(handler._enrichment, "enrich_from_grade", new_callable=AsyncMock, return_value=1):
            await handler.handle_event(event)

        # Cache should be invalidated
        assert "student-1" not in _context_cache

    @pytest.mark.asyncio
    async def test_quiz_completed_invalidates_cache(self):
        """quiz_completed webhook invalidates student's context cache."""
        from app.integrations.lms.context_loader import get_lms_context_loader, _context_cache, LMSStudentContext
        from app.integrations.lms.models import LMSWebhookEvent, LMSWebhookEventType
        from app.integrations.lms.webhook_handler import LMSWebhookHandler

        _context_cache["student-2"] = (LMSStudentContext(student_id="student-2"), time.time())

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.QUIZ_COMPLETED,
            payload={"student_id": "student-2", "quiz_id": "q1", "course_id": "C1", "score": 85, "max_score": 100},
        )

        handler = LMSWebhookHandler()
        with patch.object(handler._enrichment, "enrich_from_quiz", new_callable=AsyncMock, return_value=1):
            await handler.handle_event(event)

        assert "student-2" not in _context_cache


# =============================================================================
# 7. LMSStudentContext Data Tests
# =============================================================================


class TestLMSStudentContext:
    """Test LMSStudentContext dataclass."""

    def test_default_empty_lists(self):
        """Default lists are empty, not shared references."""
        from app.integrations.lms.context_loader import LMSStudentContext

        ctx1 = LMSStudentContext(student_id="s1")
        ctx2 = LMSStudentContext(student_id="s2")

        assert ctx1.grades is not ctx2.grades
        assert ctx1.enrollments == []
        assert ctx1.grades == []
        assert ctx1.upcoming_assignments == []
        assert ctx1.quiz_history == []

    def test_loaded_at_auto_set(self):
        """loaded_at is auto-set to current time."""
        from app.integrations.lms.context_loader import LMSStudentContext

        before = time.time()
        ctx = LMSStudentContext(student_id="s1")
        after = time.time()

        assert before <= ctx.loaded_at <= after


# =============================================================================
# 8. Integration: Chat Orchestrator LMS Insight Push
# =============================================================================


class TestChatOrchestratorLMSInsights:
    """Test that chat orchestrator fires insight analysis."""

    def test_insight_push_code_path_exists(self):
        """Verify the insight push import path is valid."""
        from app.integrations.lms.insight_generator import analyze_and_push_insights
        assert callable(analyze_and_push_insights)

    def test_context_loader_import_path(self):
        """Verify context loader import path is valid."""
        from app.integrations.lms.context_loader import get_lms_context_loader
        loader = get_lms_context_loader()
        assert loader is not None


# =============================================================================
# 9. _is_trivial_message Tests
# =============================================================================


class TestTrivialMessageDetection:
    """Test trivial message filtering."""

    def test_greeting_is_trivial(self):
        from app.integrations.lms.insight_generator import _is_trivial_message
        assert _is_trivial_message("chào") is True
        assert _is_trivial_message("xin chào wiii") is True
        assert _is_trivial_message("hello") is True

    def test_thanks_is_trivial(self):
        from app.integrations.lms.insight_generator import _is_trivial_message
        assert _is_trivial_message("cảm ơn") is True

    def test_question_is_not_trivial(self):
        from app.integrations.lms.insight_generator import _is_trivial_message
        assert _is_trivial_message("quy tắc colreg là gì?") is False

    def test_ok_is_trivial(self):
        from app.integrations.lms.insight_generator import _is_trivial_message
        assert _is_trivial_message("ok") is True
        assert _is_trivial_message("được") is True


# =============================================================================
# 10. LMSContextLoader.clear_cache Tests
# =============================================================================


class TestContextLoaderCacheClear:
    """Test cache management methods."""

    def test_clear_cache(self):
        """clear_cache removes all entries."""
        from app.integrations.lms.context_loader import (
            LMSContextLoader,
            LMSStudentContext,
            _context_cache,
        )

        _context_cache["user-a"] = (LMSStudentContext(student_id="a"), time.time())
        _context_cache["user-b"] = (LMSStudentContext(student_id="b"), time.time())

        loader = LMSContextLoader()
        loader.clear_cache()

        assert len(_context_cache) == 0

    def test_invalidate_single_user(self):
        """invalidate_cache removes only one user."""
        from app.integrations.lms.context_loader import (
            LMSContextLoader,
            LMSStudentContext,
            _context_cache,
        )

        _context_cache["user-a"] = (LMSStudentContext(student_id="a"), time.time())
        _context_cache["user-b"] = (LMSStudentContext(student_id="b"), time.time())

        loader = LMSContextLoader()
        loader.invalidate_cache("user-a")

        assert "user-a" not in _context_cache
        assert "user-b" in _context_cache

        # Cleanup
        loader.clear_cache()
