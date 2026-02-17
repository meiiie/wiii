"""
Tests for Sprint 116: Pre-Compaction Memory Flush

Tests cover:
  1. _flush_memories_before_compaction — fact extraction and character block updates
  2. Integration with maybe_compact — flush called before summarization
  3. Fail-safe behavior — flush failure doesn't block compaction
  4. Edge cases — empty messages, no user_id, LLM errors

NOTE: _flush_memories_before_compaction uses lazy imports inside the function body.
      Patch at SOURCE module (e.g., app.engine.llm_pool.get_llm_light),
      NOT at consuming module (app.engine.context_manager.get_llm_light).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_history(n: int, content_len: int = 100) -> list:
    """Create n history entries with content of specified length."""
    history = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Message {i}: " + "x" * content_len
        history.append({"role": role, "content": content})
    return history


# Patch targets — lazy imports resolved at source modules
_LLM_PATCH = "app.engine.llm_pool.get_llm_light"
_CHAR_STATE_PATCH = "app.engine.character.character_state.get_character_state_manager"


# =============================================================================
# _flush_memories_before_compaction Tests
# =============================================================================


class TestPreCompactionMemoryFlush:
    """Test the pre-compaction memory flush (OpenClaw pattern)."""

    def _get_compactor(self):
        """Get a ConversationCompactor instance."""
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager
        return ConversationCompactor(budget_manager=TokenBudgetManager())

    @pytest.mark.asyncio
    async def test_flush_extracts_facts_and_writes_to_blocks(self):
        """Flush should extract facts from LLM and write to character blocks."""
        compactor = self._get_compactor()
        messages = [
            {"role": "user", "content": "Tôi là Hùng, sinh viên năm 3 hàng hải"},
            {"role": "assistant", "content": "Chào Hùng! Rất vui được gặp bạn!"},
            {"role": "user", "content": "Mình hay bị nhầm Rule 15 với Rule 14"},
        ]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "facts": [
                {"block": "user_patterns", "content": "Hùng, SV năm 3, hay nhầm Rule 15/14"},
                {"block": "learned_lessons", "content": "Cần giải thích rõ sự khác biệt Rule 14 vs 15"},
            ]
        }, ensure_ascii=False)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_manager = MagicMock()
        mock_manager.update_block.return_value = MagicMock()

        with patch(_LLM_PATCH, return_value=mock_llm), \
             patch(_CHAR_STATE_PATCH, return_value=mock_manager):
            await compactor._flush_memories_before_compaction(messages, user_id="user-123")

        assert mock_manager.update_block.call_count == 2
        call_args_0 = mock_manager.update_block.call_args_list[0]
        assert call_args_0[1]["label"] == "user_patterns"
        assert "Hùng" in call_args_0[1]["append"]
        call_args_1 = mock_manager.update_block.call_args_list[1]
        assert call_args_1[1]["label"] == "learned_lessons"

    @pytest.mark.asyncio
    async def test_flush_skips_when_no_messages(self):
        """Flush should be a no-op when messages list is empty."""
        compactor = self._get_compactor()

        with patch(_LLM_PATCH) as mock_get_llm:
            await compactor._flush_memories_before_compaction([], user_id="user-123")

        mock_get_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_skips_when_no_user_id(self):
        """Flush should be a no-op when user_id is empty."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "test"}]

        with patch(_LLM_PATCH) as mock_get_llm:
            await compactor._flush_memories_before_compaction(messages, user_id="")

        mock_get_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_handles_empty_facts(self):
        """Flush should handle LLM returning no facts gracefully."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "Xin chào"}]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"facts": []}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_manager = MagicMock()

        with patch(_LLM_PATCH, return_value=mock_llm), \
             patch(_CHAR_STATE_PATCH, return_value=mock_manager):
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

        mock_manager.update_block.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_handles_llm_error_gracefully(self):
        """Flush should catch LLM errors and not block compaction."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "test"}]

        with patch(_LLM_PATCH, side_effect=Exception("LLM down")):
            # Should NOT raise
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

    @pytest.mark.asyncio
    async def test_flush_handles_json_parse_error(self):
        """Flush should catch malformed LLM JSON output."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "test"}]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "not valid json at all"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(_LLM_PATCH, return_value=mock_llm):
            # Should NOT raise
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

    @pytest.mark.asyncio
    async def test_flush_caps_at_3_facts(self):
        """Flush should never write more than 3 facts even if LLM returns more."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "lots of info"}]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "facts": [
                {"block": "user_patterns", "content": f"Fact {i}"} for i in range(5)
            ]
        })
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_manager = MagicMock()
        mock_manager.update_block.return_value = MagicMock()

        with patch(_LLM_PATCH, return_value=mock_llm), \
             patch(_CHAR_STATE_PATCH, return_value=mock_manager):
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

        assert mock_manager.update_block.call_count == 3

    @pytest.mark.asyncio
    async def test_flush_rejects_invalid_block_labels(self):
        """Flush should skip facts with invalid block labels."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "test"}]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "facts": [
                {"block": "invalid_label", "content": "Should be skipped"},
                {"block": "self_notes", "content": "Should be kept"},
            ]
        })
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_manager = MagicMock()
        mock_manager.update_block.return_value = MagicMock()

        with patch(_LLM_PATCH, return_value=mock_llm), \
             patch(_CHAR_STATE_PATCH, return_value=mock_manager):
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

        assert mock_manager.update_block.call_count == 1
        assert mock_manager.update_block.call_args[1]["label"] == "self_notes"

    @pytest.mark.asyncio
    async def test_flush_handles_markdown_fenced_json(self):
        """Flush should strip markdown code fences from LLM output."""
        compactor = self._get_compactor()
        messages = [{"role": "user", "content": "test"}]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '```json\n{"facts": [{"block": "self_notes", "content": "Test"}]}\n```'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_manager = MagicMock()
        mock_manager.update_block.return_value = MagicMock()

        with patch(_LLM_PATCH, return_value=mock_llm), \
             patch(_CHAR_STATE_PATCH, return_value=mock_manager):
            await compactor._flush_memories_before_compaction(messages, user_id="u1")

        assert mock_manager.update_block.call_count == 1


# =============================================================================
# Integration: Flush called during maybe_compact
# =============================================================================


class TestFlushIntegrationWithCompaction:
    """Test that memory flush is called during compaction."""

    @pytest.mark.asyncio
    async def test_maybe_compact_calls_flush_before_summarize(self):
        """maybe_compact should call flush BEFORE summarization."""
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=2000)
        compactor = ConversationCompactor(budget_manager=mgr)
        history = _make_history(50, content_len=200)

        call_order = []

        async def mock_flush(messages, user_id=""):
            call_order.append("flush")

        async def mock_summarize(messages, existing=""):
            call_order.append("summarize")
            return "Summary"

        compactor._flush_memories_before_compaction = mock_flush
        compactor._summarize_messages = mock_summarize

        with patch.object(compactor, "_persist_summary_to_db"), \
             patch.object(compactor, "_persist_session_summary"), \
             patch.object(compactor, "_load_summary_from_db", return_value=""):
            await compactor.maybe_compact(
                session_id="test-session",
                history_list=history,
                system_prompt="System prompt " * 50,
                core_memory="Core memory " * 20,
                user_id="test-user",
            )

        assert call_order == ["flush", "summarize"]

    @pytest.mark.asyncio
    async def test_maybe_compact_does_not_flush_when_no_compaction(self):
        """When compaction is not needed, flush should not be called."""
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=100_000)
        compactor = ConversationCompactor(budget_manager=mgr)
        history = _make_history(5, content_len=20)
        flush_called = False

        async def mock_flush(messages, user_id=""):
            nonlocal flush_called
            flush_called = True

        compactor._flush_memories_before_compaction = mock_flush

        await compactor.maybe_compact(
            session_id="test",
            history_list=history,
            system_prompt="short prompt",
        )

        assert not flush_called

    @pytest.mark.asyncio
    async def test_flush_failure_does_not_block_compaction(self):
        """Even if flush fails, compaction should still proceed."""
        from app.engine.context_manager import ConversationCompactor, TokenBudgetManager

        mgr = TokenBudgetManager(effective_window=2000)
        compactor = ConversationCompactor(budget_manager=mgr)
        history = _make_history(50, content_len=200)

        async def failing_flush(messages, user_id=""):
            raise RuntimeError("Flush exploded!")

        async def mock_summarize(messages, existing=""):
            return "Summary after failed flush"

        compactor._flush_memories_before_compaction = failing_flush
        compactor._summarize_messages = mock_summarize

        with patch.object(compactor, "_persist_summary_to_db"), \
             patch.object(compactor, "_persist_session_summary"), \
             patch.object(compactor, "_load_summary_from_db", return_value=""):
            summary, messages, budget = await compactor.maybe_compact(
                session_id="test",
                history_list=history,
                system_prompt="System " * 100,
                user_id="test-user",
            )

        assert summary == "Summary after failed flush"
