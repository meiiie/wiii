"""Sprint 223: Structured page data models + formatting."""
from app.engine.context.host_context import (
    HostContext,
    format_structured_data_for_prompt,
)


class TestStructuredPageData:
    """Test structured data extraction from HostContext."""

    def test_grades_structured_data_formatted(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [
                        {"code": "NAV-201", "name": "ECDIS và Radar/ARPA", "progress": 70, "status": "active"},
                        {"code": "SAF-201", "name": "Chữa Cháy Nâng Cao", "progress": 50, "status": "active"},
                    ],
                    "summary": {"total": 2, "completed": 0, "avg_progress": 60},
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "NAV-201" in result
        assert "ECDIS" in result
        assert "70" in result
        assert "Chữa Cháy" in result

    def test_assignment_list_structured_data_formatted(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "assignment_list", "title": "Bài tập của tôi"},
            content={
                "structured": {
                    "_type": "assignment_list",
                    "assignments": [
                        {"name": "Bai tap ECDIS-Radar", "course_name": "ECDIS", "due_date": "2026-03-28T02:00:00", "status": "NOT_STARTED"},
                    ],
                    "summary": {"total": 1, "pending": 1, "overdue": 0},
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "Bai tap ECDIS-Radar" in result
        assert "2026-03-28" in result
        assert "NOT_STARTED" in result or "Chưa bắt đầu" in result

    def test_lesson_structured_data_formatted(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "lesson", "title": "Bài học COLREGs"},
            content={
                "structured": {
                    "_type": "lesson",
                    "course_name": "COLREGs",
                    "chapter_name": "Chapter 2",
                    "lesson_title": "Rule 5 — Lookout",
                    "content_text": "Every vessel shall maintain a proper lookout...",
                    "media_types": ["video", "pdf"],
                    "progress": 45,
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "Rule 5" in result
        assert "COLREGs" in result
        assert "45" in result

    def test_quiz_structured_data_formatted(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "quiz", "title": "Kiểm tra"},
            content={
                "structured": {
                    "_type": "quiz",
                    "quiz_title": "COLREGs Quiz 1",
                    "question_number": 3,
                    "total_questions": 10,
                    "question_text": "Khi nào áp dụng Rule 5?",
                    "options": ["Trong lãnh hải", "Ngoài biển khơi", "Mọi lúc"],
                    "attempts_used": 1,
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "3/10" in result or "câu 3" in result.lower()
        assert "Rule 5" in result

    def test_course_overview_structured_data_formatted(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "course_overview", "title": "ECDIS"},
            content={
                "structured": {
                    "_type": "course_overview",
                    "course_name": "ECDIS và Radar/ARPA",
                    "course_code": "NAV-201",
                    "instructor": "TS. Lê Văn Hùng",
                    "chapters": [
                        {"name": "Giới thiệu ECDIS", "lesson_count": 5, "completed": 3},
                        {"name": "Radar/ARPA", "lesson_count": 8, "completed": 2},
                    ],
                    "total_progress": 70,
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "NAV-201" in result
        assert "TS. Lê Văn Hùng" in result

    def test_no_structured_data_returns_empty(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content=None,
        )
        result = format_structured_data_for_prompt(ctx)
        assert result == ""

    def test_unknown_type_returns_json_fallback(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "unknown_page"},
            content={
                "structured": {"_type": "custom", "data": "something"}
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "something" in result

    def test_empty_courses_list(self):
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [],
                    "summary": {"total": 0, "completed": 0, "avg_progress": 0},
                }
            },
        )
        result = format_structured_data_for_prompt(ctx)
        assert "0" in result


from app.engine.context.adapters.lms import LMSHostAdapter


class TestLMSAdapterStructuredData:
    """Test LMSHostAdapter formats structured data in XML."""

    def test_grades_structured_in_xml(self):
        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [
                        {"code": "NAV-201", "name": "ECDIS", "progress": 70, "status": "active"},
                    ],
                    "summary": {"total": 1, "completed": 0, "avg_progress": 70},
                }
            },
        )
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "<data>" in result
            assert "NAV-201" in result
            assert "ECDIS" in result
            assert "70" in result

    def test_assignment_structured_in_xml(self):
        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "assignment_list", "title": "Bài tập"},
            content={
                "structured": {
                    "_type": "assignment_list",
                    "assignments": [
                        {"name": "ECDIS-Radar", "course_name": "ECDIS", "due_date": "2026-03-28", "status": "NOT_STARTED"},
                    ],
                    "summary": {"total": 1, "pending": 1, "overdue": 0},
                }
            },
        )
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "<data>" in result
            assert "ECDIS-Radar" in result

    def test_no_structured_data_still_works(self):
        """Backward compat: no structured data -> original behavior."""
        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={"snippet": "Some content"},
        )
        result = adapter.format_context_for_prompt(ctx)
        assert "host_context" in result
        assert "Some content" in result
        assert "<data>" not in result

    def test_structured_plus_snippet_both_present(self):
        """Both structured and snippet -> structured takes priority for <data> tag."""
        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "snippet": "Old snippet",
                "structured": {
                    "_type": "grades",
                    "courses": [{"code": "X", "name": "Y", "progress": 50, "status": "active"}],
                    "summary": {"total": 1, "completed": 0, "avg_progress": 50},
                },
            },
        )
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "<data>" in result
            assert "Y" in result

    def test_feature_gate_off_skips_structured(self):
        """When enable_rich_page_context=False, structured data ignored."""
        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [{"code": "X", "name": "Y", "progress": 50, "status": "active"}],
                    "summary": {"total": 1, "completed": 0, "avg_progress": 50},
                },
            },
        )
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = False
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "<data>" not in result


class TestGraphInjectionStructured:
    """Test that _inject_host_context uses structured data."""

    def test_structured_data_appears_in_prompt(self):
        """When host_context has structured data, it appears in the injected prompt."""
        from unittest.mock import patch, MagicMock

        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [{"code": "NAV-201", "name": "ECDIS", "progress": 70, "status": "active"}],
                    "summary": {"total": 1, "completed": 0, "avg_progress": 70},
                }
            },
        )
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "NAV-201" in result
            assert "<data>" in result

    def test_structured_data_not_in_prompt_when_gate_off(self):
        """When enable_rich_page_context=False, no <data> in prompt."""
        from unittest.mock import patch, MagicMock

        adapter = LMSHostAdapter()
        ctx = HostContext(
            host_type="lms",
            page={"type": "grades", "title": "Bảng điểm"},
            content={
                "structured": {
                    "_type": "grades",
                    "courses": [{"code": "NAV-201", "name": "ECDIS", "progress": 70, "status": "active"}],
                    "summary": {"total": 1, "completed": 0, "avg_progress": 70},
                }
            },
        )
        mock_settings = MagicMock()
        mock_settings.enable_rich_page_context = False
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = adapter.format_context_for_prompt(ctx)
            assert "<data>" not in result

    def test_all_formatters_produce_output(self):
        """Each structured data type produces non-empty formatted output."""
        test_cases = [
            {"_type": "grades", "courses": [{"code": "X", "name": "Y", "progress": 1, "status": "active"}], "summary": {"total": 1, "completed": 0, "avg_progress": 1}},
            {"_type": "assignment_list", "assignments": [{"name": "A", "course_name": "B", "due_date": "2026-01-01", "status": "NOT_STARTED"}], "summary": {"total": 1, "pending": 1, "overdue": 0}},
            {"_type": "lesson", "course_name": "C", "chapter_name": "D", "lesson_title": "E", "content_text": "text", "media_types": [], "progress": 50},
            {"_type": "quiz", "quiz_title": "Q", "question_number": 1, "total_questions": 5, "question_text": "?", "options": ["a", "b"], "attempts_used": 0},
            {"_type": "course_overview", "course_name": "F", "course_code": "G", "instructor": "H", "chapters": [], "total_progress": 80},
        ]
        for data in test_cases:
            ctx = HostContext(
                host_type="lms",
                page={"type": data["_type"]},
                content={"structured": data},
            )
            result = format_structured_data_for_prompt(ctx)
            assert len(result) > 0, f"Empty output for _type={data['_type']}"
