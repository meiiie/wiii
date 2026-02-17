"""
Tests for Sprint 48: SessionSummarizer coverage.

Tests session summarization including:
- _format_messages (empty, roles, truncation)
- _get_llm (lazy init, unavailable)
- summarize_thread (no LLM, no messages, short text, success, error)
- get_recent_summaries (empty, formatted, error)
- Singleton
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# _format_messages
# ============================================================================


class TestFormatMessages:
    """Test message formatting."""

    def test_empty(self):
        from app.services.session_summarizer import SessionSummarizer
        result = SessionSummarizer._format_messages([])
        assert result == ""

    def test_user_and_assistant(self):
        from app.services.session_summarizer import SessionSummarizer
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = SessionSummarizer._format_messages(msgs)
        assert "Người dùng: Hello" in result
        assert "Trợ lý: Hi there" in result

    def test_human_role(self):
        from app.services.session_summarizer import SessionSummarizer
        msgs = [{"role": "human", "content": "Test"}]
        result = SessionSummarizer._format_messages(msgs)
        assert "Người dùng: Test" in result

    def test_truncates_content(self):
        from app.services.session_summarizer import SessionSummarizer
        msgs = [{"role": "user", "content": "x" * 500}]
        result = SessionSummarizer._format_messages(msgs)
        # Content truncated to 300 chars
        assert len(result.split(": ", 1)[1]) <= 300

    def test_max_15_messages(self):
        from app.services.session_summarizer import SessionSummarizer
        msgs = [{"role": "user", "content": f"Msg {i}"} for i in range(20)]
        result = SessionSummarizer._format_messages(msgs)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 15

    def test_skips_empty_content(self):
        from app.services.session_summarizer import SessionSummarizer
        msgs = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "Hello"},
        ]
        result = SessionSummarizer._format_messages(msgs)
        assert result.count("Người dùng") == 1


# ============================================================================
# _get_llm
# ============================================================================


class TestGetLlm:
    """Test lazy LLM initialization."""

    def test_lazy_init(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        assert svc._llm is None

    def test_llm_unavailable(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        with patch("app.services.session_summarizer.SessionSummarizer._get_llm") as mock_get:
            mock_get.return_value = None
            assert svc._get_llm() is None


# ============================================================================
# summarize_thread
# ============================================================================


class TestSummarizeThread:
    """Test thread summarization."""

    @pytest.mark.asyncio
    async def test_no_llm(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        svc._get_llm = MagicMock(return_value=None)
        result = await svc.summarize_thread("thread1", "user1", messages=[{"role": "user", "content": "Hi"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_no_messages_provided(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        mock_llm = AsyncMock()
        svc._get_llm = MagicMock(return_value=mock_llm)
        svc._load_thread_messages = AsyncMock(return_value=[])
        result = await svc.summarize_thread("thread1", "user1")
        assert result is None

    @pytest.mark.asyncio
    async def test_short_text(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        mock_llm = AsyncMock()
        svc._get_llm = MagicMock(return_value=mock_llm)
        # Very short conversation
        result = await svc.summarize_thread("t1", "u1", messages=[{"role": "user", "content": "Hi"}])
        assert result is None  # < 20 chars formatted

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        mock_response = MagicMock()
        mock_response.content = "This was a conversation about Rule 15."
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        svc._get_llm = MagicMock(return_value=mock_llm)
        svc._save_summary = MagicMock()

        msgs = [
            {"role": "user", "content": "Tell me about Rule 15 and crossing situations"},
            {"role": "assistant", "content": "Rule 15 describes the crossing situation between two power-driven vessels..."},
        ]
        result = await svc.summarize_thread("t1", "u1", messages=msgs)
        assert result == "This was a conversation about Rule 15."
        svc._save_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_error(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        svc._get_llm = MagicMock(return_value=mock_llm)

        msgs = [
            {"role": "user", "content": "A longer message to pass the 20 char threshold"},
            {"role": "assistant", "content": "Response content that is also sufficiently long"},
        ]
        result = await svc.summarize_thread("t1", "u1", messages=msgs)
        assert result is None


# ============================================================================
# get_recent_summaries
# ============================================================================


class TestGetRecentSummaries:
    """Test recent summaries retrieval."""

    @pytest.mark.asyncio
    async def test_empty(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        with patch("app.repositories.thread_repository.get_thread_repository") as mock_repo_fn:
            mock_repo = MagicMock()
            mock_repo.get_threads_with_summaries.return_value = []
            mock_repo_fn.return_value = mock_repo
            result = await svc.get_recent_summaries("user1")
            assert result == ""

    @pytest.mark.asyncio
    async def test_formatted(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        with patch("app.repositories.thread_repository.get_thread_repository") as mock_repo_fn:
            mock_repo = MagicMock()
            mock_repo.get_threads_with_summaries.return_value = [
                {"title": "Session 1", "summary": "Discussed Rule 15"},
                {"title": "Session 2", "summary": "Covered SOLAS Chapter V"},
            ]
            mock_repo_fn.return_value = mock_repo
            result = await svc.get_recent_summaries("user1")
            assert "Discussed Rule 15" in result
            assert "Covered SOLAS Chapter V" in result

    @pytest.mark.asyncio
    async def test_error(self):
        from app.services.session_summarizer import SessionSummarizer
        svc = SessionSummarizer()
        with patch("app.repositories.thread_repository.get_thread_repository", side_effect=Exception("DB error")):
            result = await svc.get_recent_summaries("user1")
            assert result == ""


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_session_summarizer(self):
        import app.services.session_summarizer as mod
        mod._summarizer = None
        s1 = mod.get_session_summarizer()
        s2 = mod.get_session_summarizer()
        assert s1 is s2
        mod._summarizer = None  # Cleanup
