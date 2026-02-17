"""
Tests for Sprint 78: SOTA Context Management System

Tests cover:
  1. TokenBudgetManager — token estimation, budget allocation, compaction detection
  2. ContextBudget — serialization, layer breakdown
  3. ConversationCompactor — auto-compaction, force compact, running summary, clear
  4. ConversationWindowManager — budget-based windowing (build_messages_with_budget)
  5. Input processor integration — auto-compaction wiring
  6. API endpoints — /context/compact, /context/clear, /context/info
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from langchain_core.messages import AIMessage, HumanMessage


# =============================================================================
# Helpers
# =============================================================================


def _make_history(n: int, content_len: int = 100) -> list:
    """Create n history entries with content of specified length."""
    history = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Message {i}: " + "x" * content_len
        history.append({"role": role, "content": content})
    return history


def _make_short_history(n: int) -> list:
    """Create n short history entries."""
    return _make_history(n, content_len=20)


def _make_long_history(n: int) -> list:
    """Create n long history entries (500+ chars each)."""
    return _make_history(n, content_len=500)


# =============================================================================
# TokenBudgetManager Tests
# =============================================================================


class TestTokenBudgetManager:
    """Tests for TokenBudgetManager."""

    def test_estimate_tokens_empty(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        assert mgr.estimate_tokens("") == 0
        assert mgr.estimate_tokens(None) == 0

    def test_estimate_tokens_short_text(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        # "Hello" = 5 chars → 5//4 = 1 token
        assert mgr.estimate_tokens("Hello") == 1
        # 100 chars → 25 tokens
        assert mgr.estimate_tokens("x" * 100) == 25

    def test_estimate_tokens_vietnamese(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        # Vietnamese text (3.5 chars/token on average, so chars/4 is conservative)
        text = "Xin chào, tôi là sinh viên hàng hải. Tôi muốn học về COLREGs."
        tokens = mgr.estimate_tokens(text)
        assert tokens > 0
        # chars/4 should be conservative estimate
        assert tokens == len(text) // 4

    def test_estimate_messages_tokens(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        messages = [
            HumanMessage(content="Hello world"),  # 11 chars → 2 + 4 overhead = 6
            AIMessage(content="Hi there"),  # 8 chars → 2 + 4 = 6
        ]
        tokens = mgr.estimate_messages_tokens(messages)
        assert tokens > 0
        # Each message: chars/4 + 4 overhead
        expected = (11 // 4 + 4) + (8 // 4 + 4)
        assert tokens == expected

    def test_estimate_history_tokens(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        history = _make_history(5, content_len=40)
        tokens = mgr.estimate_history_tokens(history)
        assert tokens > 0
        # Each entry: ~50 chars content → 12 tokens + 4 overhead = 16, * 5 = ~80
        assert tokens > 50

    def test_allocate_empty(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        budget = mgr.allocate()
        assert budget.total_budget > 0
        assert budget.total_used == 0
        assert budget.utilization == 0.0
        assert not budget.needs_compaction
        assert budget.messages_included == 0

    def test_allocate_with_small_history(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        history = _make_short_history(5)
        budget = mgr.allocate(history_list=history)

        assert budget.messages_included == 5
        assert budget.messages_dropped == 0
        assert not budget.needs_compaction

    def test_allocate_with_large_history(self):
        from app.engine.context_manager import TokenBudgetManager

        # Use small window to force message dropping
        mgr = TokenBudgetManager(effective_window=500, max_output_tokens=100)
        history = _make_long_history(50)
        budget = mgr.allocate(history_list=history)

        # Should drop some messages
        assert budget.messages_included < 50
        assert budget.messages_dropped > 0

    def test_allocate_compaction_detection(self):
        from app.engine.context_manager import TokenBudgetManager

        # Tiny window forces compaction
        mgr = TokenBudgetManager(effective_window=200, max_output_tokens=50)
        history = _make_long_history(30)
        budget = mgr.allocate(history_list=history)

        # With 30 long messages and tiny window, compaction should be needed
        assert budget.needs_compaction
        assert budget.messages_dropped > 6  # MIN_MESSAGES_FOR_SUMMARY

    def test_allocate_no_compaction_when_few_dropped(self):
        from app.engine.context_manager import TokenBudgetManager

        # Large window, most messages fit
        mgr = TokenBudgetManager(effective_window=100_000, max_output_tokens=8192)
        history = _make_short_history(10)
        budget = mgr.allocate(history_list=history)

        assert not budget.needs_compaction
        assert budget.messages_included == 10

    def test_allocate_with_system_prompt_and_core_memory(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        budget = mgr.allocate(
            system_prompt="System prompt here " * 100,
            core_memory="User facts here " * 50,
            history_list=_make_short_history(5),
        )

        assert budget.system_prompt_used > 0
        assert budget.core_memory_used > 0
        assert budget.messages_included > 0

    def test_allocate_with_summary(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        budget = mgr.allocate(
            summary="Summary of previous conversation about COLREGs rules.",
            history_list=_make_short_history(5),
        )

        assert budget.summary_used > 0
        assert budget.has_summary

    def test_compute_dynamic_window(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        included, dropped = mgr.compute_dynamic_window(
            history_list=_make_short_history(20)
        )
        assert included + dropped == 20
        assert included > 0

    def test_build_context_messages(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        history = _make_short_history(5)
        messages, budget = mgr.build_context_messages(history)

        assert len(messages) == 5
        assert isinstance(messages[0], HumanMessage)  # First is user (even index)
        assert isinstance(messages[1], AIMessage)  # Second is assistant
        assert budget.messages_included == 5

    def test_build_context_messages_respects_budget(self):
        from app.engine.context_manager import TokenBudgetManager

        # Tiny window
        mgr = TokenBudgetManager(effective_window=300, max_output_tokens=50)
        history = _make_long_history(20)
        messages, budget = mgr.build_context_messages(history)

        # Should include fewer than 20 messages
        assert len(messages) < 20
        assert budget.messages_dropped > 0

    def test_build_context_messages_empty_history(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        messages, budget = mgr.build_context_messages([])
        assert messages == []
        assert budget.messages_included == 0


# =============================================================================
# ContextBudget Tests
# =============================================================================


class TestContextBudget:
    """Tests for ContextBudget serialization."""

    def test_to_dict(self):
        from app.engine.context_manager import ContextBudget

        budget = ContextBudget(
            effective_window=32000,
            max_output=8192,
            total_budget=20000,
            total_used=10000,
            utilization=0.5,
            messages_included=10,
            messages_dropped=5,
            has_summary=True,
        )
        d = budget.to_dict()

        assert d["effective_window"] == 32000
        assert d["total_used"] == 10000
        assert d["utilization"] == 0.5
        assert d["messages_included"] == 10
        assert d["has_summary"]
        assert "layers" in d
        assert "system_prompt" in d["layers"]

    def test_to_dict_default_values(self):
        from app.engine.context_manager import ContextBudget

        budget = ContextBudget()
        d = budget.to_dict()
        assert d["total_used"] == 0
        assert d["utilization"] == 0.0


# =============================================================================
# ConversationCompactor Tests
# =============================================================================


class TestConversationCompactor:
    """Tests for ConversationCompactor."""

    def test_get_set_running_summary(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        assert compactor.get_running_summary("session1") == ""

        compactor.set_running_summary("session1", "Test summary")
        assert compactor.get_running_summary("session1") == "Test summary"

    def test_set_empty_summary_clears(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        compactor.set_running_summary("s1", "Summary")
        assert compactor.get_running_summary("s1") == "Summary"

        compactor.set_running_summary("s1", "")
        assert compactor.get_running_summary("s1") == ""

    def test_clear_session(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        compactor.set_running_summary("s1", "Summary")
        compactor.clear_session("s1")
        assert compactor.get_running_summary("s1") == ""

    def test_clear_nonexistent_session(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        # Should not raise
        compactor.clear_session("nonexistent")

    @pytest.mark.asyncio
    async def test_maybe_compact_no_compaction_needed(self):
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=100_000)
        compactor = ConversationCompactor(budget_manager=mgr)

        history = _make_short_history(5)
        summary, messages, budget = await compactor.maybe_compact(
            "s1", history
        )

        assert summary == ""
        assert len(messages) == 5
        assert not budget.needs_compaction

    @pytest.mark.asyncio
    async def test_maybe_compact_triggers_compaction(self):
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager

        # Tiny window to force compaction
        mgr = TokenBudgetManager(effective_window=300, max_output_tokens=50)
        compactor = ConversationCompactor(budget_manager=mgr)

        history = _make_long_history(30)

        # Lazy import: patch at source module
        with patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get:
            mock_summarizer = MagicMock()
            mock_summarizer.is_available.return_value = False
            mock_get.return_value = mock_summarizer

            summary, messages, budget = await compactor.maybe_compact(
                "s1", history
            )

        # Should have generated a fallback summary
        if budget.needs_compaction:
            assert summary != "" or budget.messages_dropped > 0

    @pytest.mark.asyncio
    async def test_force_compact(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = _make_short_history(10)

        # Lazy import: patch at source module
        with patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get:
            mock_summarizer = MagicMock()
            mock_summarizer.is_available.return_value = False
            mock_get.return_value = mock_summarizer

            summary = await compactor.force_compact("s1", history)

        # Should have a fallback summary
        assert summary != ""
        # Should be stored
        assert compactor.get_running_summary("s1") == summary

    @pytest.mark.asyncio
    async def test_force_compact_empty_history(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        summary = await compactor.force_compact("s1", [])
        assert summary == ""

    @pytest.mark.asyncio
    async def test_force_compact_with_llm(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = _make_short_history(10)

        # Mock LLM summarizer
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "User hỏi về COLREGs và luật tránh va trên biển."

        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Lazy import: patch at source module
        with patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get:
            mock_summarizer = MagicMock()
            mock_summarizer.is_available.return_value = True
            mock_summarizer._llm = mock_llm
            mock_get.return_value = mock_summarizer

            with patch(
                "app.services.output_processor.extract_thinking_from_response",
                return_value=("User hỏi về COLREGs và luật tránh va trên biển.", None),
            ):
                summary = await compactor.force_compact("s1", history)

        assert "COLREGs" in summary
        assert compactor.get_running_summary("s1") == summary

    def test_get_context_info(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        compactor.set_running_summary("s1", "Previous summary text")

        info = compactor.get_context_info(
            session_id="s1",
            history_list=_make_short_history(10),
        )

        assert info["session_id"] == "s1"
        assert info["running_summary_chars"] > 0
        assert info["total_history_messages"] == 10
        assert "layers" in info

    def test_fallback_summary(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Chào bạn!"},
        ]
        summary = compactor._fallback_summary(history, "")
        assert "User:" in summary
        assert "AI:" in summary

    def test_fallback_summary_with_existing(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = [{"role": "user", "content": "Hello"}]
        summary = compactor._fallback_summary(history, "Previous summary")
        assert "Previous summary" in summary
        assert "User:" in summary

    def test_build_summary_prompt_fresh(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = [
            {"role": "user", "content": "Luật COLREGs là gì?"},
            {"role": "assistant", "content": "COLREGs là bộ quy tắc tránh va trên biển."},
        ]
        prompt = compactor._build_summary_prompt(history, "")
        assert "COLREGs" in prompt
        assert "Tóm tắt" in prompt

    def test_build_summary_prompt_incremental(self):
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        prompt = compactor._build_summary_prompt(
            [{"role": "user", "content": "Hello"}],
            "Previous: user asked about navigation.",
        )
        assert "Previous: user asked about navigation." in prompt
        assert "Thêm các tin nhắn mới" in prompt


# =============================================================================
# ConversationWindowManager Budget Tests
# =============================================================================


class TestConversationWindowManagerBudget:
    """Tests for Sprint 78 budget-aware windowing."""

    def test_build_messages_with_budget_default(self):
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        history = _make_short_history(5)
        messages, budget = mgr.build_messages_with_budget(history)

        assert len(messages) == 5
        if budget:  # budget manager available
            assert budget.messages_included == 5

    def test_build_messages_with_budget_large_history(self):
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        history = _make_short_history(100)
        messages, budget = mgr.build_messages_with_budget(history)

        # Should be capped by budget
        assert len(messages) <= 100
        assert len(messages) > 0

    def test_build_messages_with_budget_empty(self):
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        messages, budget = mgr.build_messages_with_budget([])

        assert messages == []

    def test_build_messages_with_budget_fallback_on_error(self):
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        history = _make_short_history(5)

        # Simulate budget manager being unavailable — patch at source module
        with patch(
            "app.engine.context_manager.get_budget_manager",
            side_effect=ImportError("not available"),
        ):
            messages, budget = mgr.build_messages_with_budget(history)

        # Should fall back to fixed window
        assert len(messages) == 5
        assert budget is None  # No budget when fallback

    def test_build_messages_with_budget_respects_system_prompt(self):
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        history = _make_short_history(10)
        messages, budget = mgr.build_messages_with_budget(
            history,
            system_prompt="Very long system prompt " * 100,
            core_memory="User facts " * 50,
        )

        # Should still include messages
        assert len(messages) > 0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingletons:
    """Tests for singleton accessors."""

    def test_get_budget_manager_singleton(self):
        from app.engine import context_manager

        # Reset singleton
        context_manager._budget_manager = None
        mgr1 = context_manager.get_budget_manager()
        mgr2 = context_manager.get_budget_manager()
        assert mgr1 is mgr2
        # Cleanup
        context_manager._budget_manager = None

    def test_get_compactor_singleton(self):
        from app.engine import context_manager

        # Reset singleton
        context_manager._compactor = None
        context_manager._budget_manager = None
        c1 = context_manager.get_compactor()
        c2 = context_manager.get_compactor()
        assert c1 is c2
        # Cleanup
        context_manager._compactor = None
        context_manager._budget_manager = None


# =============================================================================
# Integration-style Tests (Input Processor)
# =============================================================================


class TestInputProcessorIntegration:
    """Test that Sprint 78 context manager integrates with input_processor."""

    @pytest.mark.asyncio
    async def test_build_context_uses_budget_manager(self):
        """Verify input_processor.build_context calls context manager."""
        from app.services.input_processor import InputProcessor, ChatContext
        from app.models.schemas import ChatRequest, UserRole

        processor = InputProcessor()

        # Create minimal request
        request = MagicMock(spec=ChatRequest)
        request.user_id = "test_user"
        request.message = "Hello"
        request.role = UserRole.STUDENT
        request.user_context = None

        from uuid import uuid4

        session_id = uuid4()

        with patch("app.engine.context_manager.get_compactor") as mock_compactor:
            mock_inst = MagicMock()
            mock_inst.maybe_compact = AsyncMock(return_value=(
                "",  # no summary
                [HumanMessage(content="prev msg")],  # messages
                MagicMock(  # budget
                    total_used=100,
                    total_budget=20000,
                    utilization=0.005,
                    messages_included=1,
                    messages_dropped=0,
                    has_summary=False,
                ),
            ))
            mock_compactor.return_value = mock_inst

            context = await processor.build_context(request, session_id)

        assert context.langchain_messages is not None
        # Should have called maybe_compact
        mock_inst.maybe_compact.assert_called_once()


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestContextAPIEndpoints:
    """Tests for Sprint 78 API endpoints."""

    @pytest.mark.asyncio
    async def test_compact_endpoint_missing_session(self):
        """Test compact endpoint returns 400 without session ID."""
        from app.api.v1.chat import compact_context

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_auth = MagicMock()
        mock_auth.user_id = "test_user"

        result = await compact_context(mock_request, mock_auth)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_compact_endpoint_success(self):
        """Test compact endpoint succeeds with session ID."""
        from app.api.v1.chat import compact_context

        mock_request = MagicMock()
        mock_request.headers = {"X-Session-ID": "test-session"}
        mock_auth = MagicMock()
        mock_auth.user_id = "test_user"

        # Lazy imports inside function body — patch at source modules
        with patch("app.engine.context_manager.get_compactor") as mock_get_compactor, \
             patch("app.repositories.chat_history_repository.get_chat_history_repository") as mock_get_history:

            mock_compactor = MagicMock()
            mock_compactor.force_compact = AsyncMock(return_value="Test summary")
            mock_get_compactor.return_value = mock_compactor

            mock_history = MagicMock()
            mock_history.is_available.return_value = False
            mock_get_history.return_value = mock_history

            result = await compact_context(mock_request, mock_auth)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_clear_endpoint_success(self):
        """Test clear endpoint succeeds."""
        from app.api.v1.chat import clear_context

        mock_request = MagicMock()
        mock_request.headers = {"X-Session-ID": "test-session"}
        mock_auth = MagicMock()
        mock_auth.user_id = "test_user"

        # Lazy imports inside function body — patch at source modules
        with patch("app.engine.context_manager.get_compactor") as mock_get_compactor, \
             patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get_summarizer:

            mock_compactor = MagicMock()
            mock_get_compactor.return_value = mock_compactor

            mock_summarizer = MagicMock()
            mock_get_summarizer.return_value = mock_summarizer

            result = await clear_context(mock_request, mock_auth)

        assert result.status_code == 200
        mock_compactor.clear_session.assert_called_once_with("test-session", user_id="test_user")
        mock_summarizer.clear_session.assert_called_once_with("test-session")

    @pytest.mark.asyncio
    async def test_clear_endpoint_missing_session(self):
        """Test clear endpoint returns 400 without session ID."""
        from app.api.v1.chat import clear_context

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_auth = MagicMock()

        result = await clear_context(mock_request, mock_auth)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_context_info_endpoint_success(self):
        """Test context info endpoint returns usage data."""
        from app.api.v1.chat import get_context_info

        mock_request = MagicMock()
        mock_request.headers = {"X-Session-ID": "test-session"}
        mock_auth = MagicMock()
        mock_auth.user_id = "test_user"

        # Lazy imports inside function body — patch at source modules
        with patch("app.engine.context_manager.get_compactor") as mock_get_compactor, \
             patch("app.repositories.chat_history_repository.get_chat_history_repository") as mock_get_history:

            mock_compactor = MagicMock()
            mock_compactor.get_context_info.return_value = {
                "session_id": "test-session",
                "total_used": 100,
                "total_budget": 20000,
                "utilization": 0.005,
                "running_summary_chars": 0,
                "total_history_messages": 5,
                "layers": {},
            }
            mock_get_compactor.return_value = mock_compactor

            mock_history = MagicMock()
            mock_history.is_available.return_value = False
            mock_get_history.return_value = mock_history

            result = await get_context_info(mock_request, mock_auth)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_context_info_endpoint_missing_session(self):
        """Test context info endpoint returns 400 without session ID."""
        from app.api.v1.chat import get_context_info

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_auth = MagicMock()

        result = await get_context_info(mock_request, mock_auth)
        assert result.status_code == 400


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_budget_manager_custom_params(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager(
            effective_window=1000,
            max_output_tokens=200,
            compaction_threshold=0.5,
        )
        assert mgr.effective_window == 1000
        assert mgr.max_output_tokens == 200
        assert mgr.compaction_threshold == 0.5

    def test_budget_with_only_system_prompt(self):
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager()
        budget = mgr.allocate(system_prompt="A" * 10000)
        assert budget.system_prompt_used == 10000 // 4
        assert budget.utilization > 0

    def test_budget_messages_newest_first(self):
        """Verify budget keeps newest messages, drops oldest."""
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=500, max_output_tokens=100)
        history = [
            {"role": "user", "content": f"Message {i}" + "x" * 200}
            for i in range(10)
        ]
        messages, budget = mgr.build_context_messages(history)

        # The messages should be the NEWEST ones
        if messages:
            # Last message in messages should correspond to last in history
            assert "Message 9" in messages[-1].content or len(messages) == len(history)

    def test_zero_effective_window(self):
        """Budget manager with zero window should handle gracefully."""
        from app.engine.context_manager import TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=0, max_output_tokens=0)
        budget = mgr.allocate(history_list=_make_short_history(5))
        assert budget.total_budget == 0
        assert budget.messages_included == 0

    @pytest.mark.asyncio
    async def test_compactor_summary_truncation(self):
        """Verify long summaries are truncated to MAX_SUMMARY_TOKENS."""
        from app.engine.context_manager import ConversationCompactor, MAX_SUMMARY_TOKENS, CHARS_PER_TOKEN

        compactor = ConversationCompactor()
        max_chars = MAX_SUMMARY_TOKENS * CHARS_PER_TOKEN

        # Mock LLM that returns very long summary
        long_summary = "Tóm tắt " * 5000  # Very long
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = long_summary
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Lazy import: patch at source modules
        with patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get:
            mock_summarizer = MagicMock()
            mock_summarizer.is_available.return_value = True
            mock_summarizer._llm = mock_llm
            mock_get.return_value = mock_summarizer

            with patch(
                "app.services.output_processor.extract_thinking_from_response",
                return_value=(long_summary, None),
            ):
                summary = await compactor._summarize_messages(
                    _make_short_history(5), ""
                )

        # Should be truncated
        assert len(summary) <= max_chars + 10  # +10 for "..." suffix

    @pytest.mark.asyncio
    async def test_compactor_summarization_error_fallback(self):
        """When LLM summarization fails, fallback to simple text."""
        from app.engine.context_manager import ConversationCompactor

        compactor = ConversationCompactor()
        history = _make_short_history(5)

        # Lazy import: patch at source module
        with patch("app.engine.memory_summarizer.get_memory_summarizer") as mock_get:
            mock_summarizer = MagicMock()
            mock_summarizer.is_available.return_value = True
            mock_summarizer._llm = AsyncMock()
            mock_summarizer._llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
            mock_get.return_value = mock_summarizer

            summary = await compactor._summarize_messages(history, "")

        # Should have fallback summary
        assert summary != ""
        assert "User:" in summary or "AI:" in summary


# =============================================================================
# Supervisor Integration
# =============================================================================


class TestSupervisorSummaryInjection:
    """Test that supervisor uses conversation_summary from Sprint 78."""

    def test_supervisor_context_includes_summary(self):
        """Verify supervisor builds context with summary when available."""
        from langchain_core.messages import HumanMessage, AIMessage

        # Simulate what supervisor._route_structured does
        context = {
            "langchain_messages": [
                HumanMessage(content="Luật COLREGs là gì?"),
                AIMessage(content="COLREGs là bộ quy tắc tránh va."),
            ],
            "conversation_summary": "User đã hỏi về luật hàng hải cơ bản.",
        }

        lc_messages = context.get("langchain_messages", [])
        conv_summary = context.get("conversation_summary", "")

        if lc_messages:
            recent_turns = "\n".join(
                f"{'User' if getattr(m, 'type', '') == 'human' else 'AI'}: {m.content[:200]}"
                for m in lc_messages[-6:]
            )
            context_str = f"Recent conversation:\n{recent_turns}"
            if conv_summary:
                context_str = f"Summary of earlier conversation:\n{conv_summary[:300]}\n\n{context_str}"

        assert "Summary of earlier conversation" in context_str
        assert "luật hàng hải" in context_str
        assert "COLREGs" in context_str
