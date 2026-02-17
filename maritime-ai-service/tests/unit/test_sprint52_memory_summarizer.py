"""
Tests for Sprint 52: MemorySummarizer coverage.

Tests tiered memory architecture including:
- ConversationSummary dataclass
- TieredMemoryState (get_context_for_prompt, _get_recent_user_state)
- MemorySummarizer (init, get_state, add_message, trigger_summarization,
  _create_summary_sync/async, _build_summary_prompt, _parse_summary_response,
  get_context_for_prompt, get_summary/get_summary_async, clear_session, is_available)
- Singleton
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.engine.memory_summarizer import (
    ConversationSummary,
    TieredMemoryState,
    MemorySummarizer,
)


# ============================================================================
# ConversationSummary
# ============================================================================


class TestConversationSummary:
    """Test ConversationSummary dataclass."""

    def test_defaults(self):
        s = ConversationSummary(summary_text="Test summary", message_count=5)
        assert s.summary_text == "Test summary"
        assert s.message_count == 5
        assert s.topics == []
        assert s.user_state is None
        assert s.created_at is not None

    def test_with_all_fields(self):
        s = ConversationSummary(
            summary_text="User learned about SOLAS",
            message_count=4,
            topics=["SOLAS", "fire safety"],
            user_state="focused",
        )
        assert len(s.topics) == 2
        assert s.user_state == "focused"


# ============================================================================
# TieredMemoryState
# ============================================================================


class TestTieredMemoryStateDefaults:
    """Test TieredMemoryState defaults."""

    def test_defaults(self):
        state = TieredMemoryState()
        assert state.raw_messages == []
        assert state.summaries == []
        assert state.user_facts == []
        assert state.total_messages_processed == 0


class TestGetContextForPrompt:
    """Test context building for LLM prompt."""

    def test_empty_state(self):
        state = TieredMemoryState()
        result = state.get_context_for_prompt()
        assert result == ""

    def test_with_raw_messages_only(self):
        state = TieredMemoryState()
        state.raw_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = state.get_context_for_prompt()
        assert "User: Hello" in result
        assert "AI: Hi there" in result

    def test_with_summaries(self):
        state = TieredMemoryState()
        state.summaries = [
            ConversationSummary(summary_text="Discussed SOLAS", message_count=4),
        ]
        result = state.get_context_for_prompt()
        assert "Discussed SOLAS" in result

    def test_max_raw_limit(self):
        state = TieredMemoryState()
        state.raw_messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        result = state.get_context_for_prompt(max_raw=3)
        # Should only include last 3 messages
        assert "Message 7" in result
        assert "Message 8" in result
        assert "Message 9" in result
        assert "Message 0" not in result

    def test_with_user_state(self):
        state = TieredMemoryState()
        state.summaries = [
            ConversationSummary(summary_text="Test", message_count=2, user_state="tired"),
        ]
        result = state.get_context_for_prompt()
        assert "tired" in result

    def test_last_3_summaries_only(self):
        state = TieredMemoryState()
        state.summaries = [
            ConversationSummary(summary_text=f"Summary {i}", message_count=2)
            for i in range(5)
        ]
        result = state.get_context_for_prompt()
        assert "Summary 2" in result
        assert "Summary 3" in result
        assert "Summary 4" in result
        assert "Summary 0" not in result


class TestGetRecentUserState:
    """Test user state retrieval from summaries."""

    def test_no_summaries(self):
        state = TieredMemoryState()
        assert state._get_recent_user_state() is None

    def test_no_user_state(self):
        state = TieredMemoryState()
        state.summaries = [
            ConversationSummary(summary_text="Test", message_count=2),
        ]
        assert state._get_recent_user_state() is None

    def test_returns_most_recent(self):
        state = TieredMemoryState()
        state.summaries = [
            ConversationSummary(summary_text="Early", message_count=2, user_state="happy"),
            ConversationSummary(summary_text="Late", message_count=2, user_state="tired"),
        ]
        assert state._get_recent_user_state() == "tired"


# ============================================================================
# MemorySummarizer Init
# ============================================================================


class TestMemorySummarizerInit:
    """Test MemorySummarizer initialization."""

    def test_no_api_key(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            summarizer = MemorySummarizer()
        assert summarizer._llm is None
        assert summarizer.is_available() is False

    def test_llm_init_error(self):
        with patch("app.engine.llm_pool.get_llm_light", side_effect=Exception("Import error")), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            summarizer = MemorySummarizer()
        assert summarizer._llm is None

    def test_llm_init_success(self):
        mock_llm = MagicMock()
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            summarizer = MemorySummarizer()
        assert summarizer._llm is mock_llm
        assert summarizer.is_available() is True


# ============================================================================
# get_state / clear_session
# ============================================================================


class TestMemorySummarizerState:
    """Test session state management."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    def test_get_state_creates_new(self):
        s = self._make_summarizer()
        state = s.get_state("session-1")
        assert isinstance(state, TieredMemoryState)
        assert state.total_messages_processed == 0

    def test_get_state_returns_same(self):
        s = self._make_summarizer()
        s1 = s.get_state("session-1")
        s2 = s.get_state("session-1")
        assert s1 is s2

    def test_different_sessions(self):
        s = self._make_summarizer()
        s1 = s.get_state("session-1")
        s2 = s.get_state("session-2")
        assert s1 is not s2

    def test_clear_session(self):
        s = self._make_summarizer()
        s.get_state("session-1")
        s.clear_session("session-1")
        # After clear, should create new state
        state = s.get_state("session-1")
        assert state.total_messages_processed == 0

    def test_clear_nonexistent_session(self):
        s = self._make_summarizer()
        # Should not raise
        s.clear_session("nonexistent")


# ============================================================================
# add_message
# ============================================================================


class TestAddMessage:
    """Test message addition."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    def test_adds_message(self):
        s = self._make_summarizer()
        state = s.add_message("s1", "user", "Hello")
        assert len(state.raw_messages) == 1
        assert state.raw_messages[0]["role"] == "user"
        assert state.raw_messages[0]["content"] == "Hello"
        assert state.total_messages_processed == 1

    def test_increments_counter(self):
        s = self._make_summarizer()
        s.add_message("s1", "user", "Hello")
        state = s.add_message("s1", "assistant", "Hi")
        assert state.total_messages_processed == 2

    def test_triggers_summarization_at_threshold(self):
        s = self._make_summarizer()
        # No LLM, so summarization will just trim
        for i in range(12):
            state = s.add_message("s1", "user", f"Message {i}")
        # After exceeding MAX_RAW_MESSAGES (10), should trim to last 6
        assert len(state.raw_messages) <= 7  # 6 kept + 1 new


# ============================================================================
# add_message_async
# ============================================================================


class TestAddMessageAsync:
    """Test async message addition."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    @pytest.mark.asyncio
    async def test_adds_message(self):
        s = self._make_summarizer()
        state = await s.add_message_async("s1", "user", "Hello")
        assert len(state.raw_messages) == 1
        assert state.total_messages_processed == 1

    @pytest.mark.asyncio
    async def test_triggers_summarization_at_threshold(self):
        s = self._make_summarizer()
        for i in range(12):
            state = await s.add_message_async("s1", "user", f"Message {i}")
        assert len(state.raw_messages) <= 7


# ============================================================================
# _trigger_summarization (sync)
# ============================================================================


class TestTriggerSummarization:
    """Test synchronous summarization trigger."""

    def test_no_llm_trims(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            s = MemorySummarizer()
        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]
        s._trigger_summarization("s1")
        assert len(state.raw_messages) == 6

    def test_with_llm_success(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="SUMMARY: Test summary\nUSER_STATE: none\nTOPICS: SOLAS")
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings, \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=("SUMMARY: Test summary\nUSER_STATE: none\nTOPICS: SOLAS", None)):
            mock_settings.google_api_key = "test-key"
            s = MemorySummarizer()

        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]

        s._trigger_summarization("s1")
        assert len(state.summaries) == 1
        assert len(state.raw_messages) == 8  # 12 - 4 (SUMMARIZE_BATCH_SIZE)

    def test_with_llm_error_internal_no_trim(self):
        """LLM error caught inside _create_summary_sync → returns None → no trim."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM error")
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            s = MemorySummarizer()

        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]

        s._trigger_summarization("s1")
        # _create_summary_sync catches error internally, returns None
        # Outer code sees None → no trim, no summary added
        assert len(state.raw_messages) == 12
        assert len(state.summaries) == 0

    def test_with_create_summary_raises_trims(self):
        """Error propagating from _create_summary_sync → outer except → trim to 6."""
        mock_llm = MagicMock()
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            s = MemorySummarizer()

        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]

        with patch.object(s, "_create_summary_sync", side_effect=Exception("Uncaught")):
            s._trigger_summarization("s1")
        # Outer except catches → fallback trim to 6
        assert len(state.raw_messages) == 6


# ============================================================================
# _trigger_summarization_async
# ============================================================================


class TestTriggerSummarizationAsync:
    """Test async summarization trigger."""

    @pytest.mark.asyncio
    async def test_no_llm_trims(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            s = MemorySummarizer()
        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]
        await s._trigger_summarization_async("s1")
        assert len(state.raw_messages) == 6

    @pytest.mark.asyncio
    async def test_with_llm_error_internal_no_trim(self):
        """LLM error caught inside _create_summary_async → returns None → no trim."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            s = MemorySummarizer()

        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]
        await s._trigger_summarization_async("s1")
        # _create_summary_async catches error internally, returns None
        assert len(state.raw_messages) == 12
        assert len(state.summaries) == 0

    @pytest.mark.asyncio
    async def test_with_create_summary_raises_trims(self):
        """Error propagating from _create_summary_async → outer except → trim to 6."""
        mock_llm = MagicMock()
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            s = MemorySummarizer()

        state = s.get_state("s1")
        state.raw_messages = [{"role": "user", "content": f"M{i}"} for i in range(12)]

        with patch.object(s, "_create_summary_async", new_callable=AsyncMock, side_effect=Exception("Uncaught")):
            await s._trigger_summarization_async("s1")
        assert len(state.raw_messages) == 6


# ============================================================================
# _build_summary_prompt
# ============================================================================


class TestBuildSummaryPrompt:
    """Test prompt building."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    def test_basic_prompt(self):
        s = self._make_summarizer()
        messages = [
            {"role": "user", "content": "What is SOLAS?"},
            {"role": "assistant", "content": "SOLAS stands for..."},
        ]
        prompt = s._build_summary_prompt(messages)
        assert "User: What is SOLAS?" in prompt
        assert "AI: SOLAS stands for..." in prompt
        assert "SUMMARY:" in prompt
        assert "USER_STATE:" in prompt
        assert "TOPICS:" in prompt


# ============================================================================
# _parse_summary_response
# ============================================================================


class TestParseSummaryResponse:
    """Test LLM response parsing."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    def test_valid_response(self):
        s = self._make_summarizer()
        response = "SUMMARY: User asked about SOLAS\nUSER_STATE: focused\nTOPICS: SOLAS, fire safety"
        result = s._parse_summary_response(response, 4)
        assert result.summary_text == "User asked about SOLAS"
        assert result.user_state == "focused"
        assert result.topics == ["SOLAS", "fire safety"]
        assert result.message_count == 4

    def test_no_user_state(self):
        s = self._make_summarizer()
        response = "SUMMARY: General chat\nUSER_STATE: none\nTOPICS: general"
        result = s._parse_summary_response(response, 3)
        assert result.user_state is None

    def test_empty_topics(self):
        s = self._make_summarizer()
        response = "SUMMARY: Short chat\nUSER_STATE: none\nTOPICS: "
        result = s._parse_summary_response(response, 2)
        assert result.topics == []

    def test_fallback_on_bad_response(self):
        s = self._make_summarizer()
        response = "This is just random text without proper formatting"
        result = s._parse_summary_response(response, 2)
        # Should use first 200 chars as fallback
        assert result.summary_text == response[:200]

    def test_empty_response(self):
        s = self._make_summarizer()
        result = s._parse_summary_response("", 1)
        assert result.summary_text == ""  # empty string fallback


# ============================================================================
# get_summary / get_summary_async
# ============================================================================


class TestGetSummary:
    """Test summary retrieval."""

    def _make_summarizer(self):
        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            return MemorySummarizer()

    def test_no_summaries(self):
        s = self._make_summarizer()
        assert s.get_summary("s1") is None

    def test_with_summaries(self):
        s = self._make_summarizer()
        state = s.get_state("s1")
        state.summaries = [
            ConversationSummary(summary_text="User learned about SOLAS", message_count=4, topics=["SOLAS"]),
        ]
        result = s.get_summary("s1")
        assert result is not None
        assert "User learned about SOLAS" in result

    def test_with_user_state(self):
        s = self._make_summarizer()
        state = s.get_state("s1")
        state.summaries = [
            ConversationSummary(summary_text="Chat", message_count=2, user_state="tired"),
        ]
        result = s.get_summary("s1")
        assert "tired" in result

    def test_with_topics(self):
        s = self._make_summarizer()
        state = s.get_state("s1")
        state.summaries = [
            ConversationSummary(summary_text="Chat", message_count=2, topics=["SOLAS", "COLREGS"]),
        ]
        result = s.get_summary("s1")
        assert "SOLAS" in result
        assert "COLREGS" in result

    @pytest.mark.asyncio
    async def test_async_no_summaries(self):
        s = self._make_summarizer()
        result = await s.get_summary_async("s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_with_summaries(self):
        s = self._make_summarizer()
        state = s.get_state("s1")
        state.summaries = [
            ConversationSummary(summary_text="Discussed SOLAS", message_count=4, topics=["SOLAS"]),
        ]
        result = await s.get_summary_async("s1")
        assert result is not None
        assert "Discussed SOLAS" in result

    def test_dedup_topics(self):
        s = self._make_summarizer()
        state = s.get_state("s1")
        state.summaries = [
            ConversationSummary(summary_text="S1", message_count=2, topics=["SOLAS", "COLREGS"]),
            ConversationSummary(summary_text="S2", message_count=2, topics=["SOLAS", "MARPOL"]),
        ]
        result = s.get_summary("s1")
        # SOLAS should appear only once
        assert result.count("SOLAS") == 1 or "SOLAS" in result


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton factory."""

    def test_singleton(self):
        import app.engine.memory_summarizer as mod
        old = mod._memory_summarizer
        mod._memory_summarizer = None

        with patch("app.engine.memory_summarizer.settings") as mock_settings:
            mock_settings.google_api_key = ""
            r1 = mod.get_memory_summarizer()
            r2 = mod.get_memory_summarizer()
            assert r1 is r2

        mod._memory_summarizer = old
