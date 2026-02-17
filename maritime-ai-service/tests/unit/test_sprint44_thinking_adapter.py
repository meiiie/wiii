"""
Tests for Sprint 44: ThinkingAdapter coverage.

Tests Cache-Augmented Generation adapter including:
- AdaptedResponse dataclass
- LLM-based adaptation with mock
- Response parsing (thinking/answer extraction)
- History and profile building
- Fallback on error
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# AdaptedResponse dataclass
# ============================================================================


class TestAdaptedResponse:
    """Test AdaptedResponse dataclass."""

    def test_default_values(self):
        from app.engine.agentic_rag.thinking_adapter import AdaptedResponse
        resp = AdaptedResponse(answer="test", thinking="thought")
        assert resp.original_cached is True
        assert resp.adaptation_time_ms == 0.0
        assert resp.adaptation_method == "light_llm"

    def test_custom_values(self):
        from app.engine.agentic_rag.thinking_adapter import AdaptedResponse
        resp = AdaptedResponse(
            answer="adapted",
            thinking="fresh thinking",
            original_cached=False,
            adaptation_time_ms=150.5,
            adaptation_method="custom"
        )
        assert resp.original_cached is False
        assert resp.adaptation_time_ms == 150.5
        assert resp.adaptation_method == "custom"


# ============================================================================
# ThinkingAdapter initialization
# ============================================================================


class TestThinkingAdapterInit:
    """Test ThinkingAdapter initialization."""

    def test_lazy_llm_init(self):
        """LLM is lazily initialized."""
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light") as mock_get:
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                adapter = ThinkingAdapter()
                assert adapter._llm is None
                assert adapter._initialized is False
                mock_get.assert_not_called()

    def test_ensure_llm_initializes(self):
        """_ensure_llm initializes LLM on first call."""
        mock_llm = MagicMock()
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light", return_value=mock_llm):
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                adapter = ThinkingAdapter()
                adapter._ensure_llm()
                assert adapter._llm is mock_llm
                assert adapter._initialized is True

    def test_ensure_llm_only_once(self):
        """_ensure_llm only initializes once."""
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light") as mock_get:
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                adapter = ThinkingAdapter()
                adapter._ensure_llm()
                adapter._ensure_llm()
                mock_get.assert_called_once()


# ============================================================================
# Response parsing
# ============================================================================


class TestParseResponse:
    """Test _parse_response thinking/answer extraction."""

    @pytest.fixture
    def adapter(self):
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light"):
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                return ThinkingAdapter()

    def test_thinking_and_answer_tags(self, adapter):
        """Extract thinking and answer from tags."""
        content = "<thinking>My reasoning</thinking>\n<answer>Final answer</answer>"
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(content, None)):
            thinking, answer = adapter._parse_response(content)
            assert thinking == "My reasoning"
            assert answer == "Final answer"

    def test_only_thinking_tags(self, adapter):
        """Content with only thinking tags, answer is remainder."""
        content = "<thinking>Reasoning</thinking>\nSome leftover text"
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(content, None)):
            thinking, answer = adapter._parse_response(content)
            assert thinking == "Reasoning"

    def test_no_tags(self, adapter):
        """No tags, full content is answer."""
        content = "Just a plain response without any tags"
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(content, None)):
            thinking, answer = adapter._parse_response(content)
            assert thinking == ""
            assert answer == content

    def test_native_thinking(self, adapter):
        """Gemini native thinking extracted."""
        content = "Answer text only"
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Answer text only", "Gemini native thought")):
            thinking, answer = adapter._parse_response(content)
            assert thinking == "Gemini native thought"
            assert answer == "Answer text only"


# ============================================================================
# History and profile building
# ============================================================================


class TestHistoryProfileBuilding:
    """Test _build_history_summary and _build_user_profile."""

    @pytest.fixture
    def adapter(self):
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light"):
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                return ThinkingAdapter()

    def test_history_no_context(self, adapter):
        result = adapter._build_history_summary(None)
        assert result != ""

    def test_history_empty_history(self, adapter):
        result = adapter._build_history_summary({"chat_history": []})
        assert result != ""

    def test_history_with_messages(self, adapter):
        context = {
            "chat_history": [
                {"role": "user", "content": "What is Rule 15?"},
                {"role": "assistant", "content": "Rule 15 is about crossing situations"},
            ]
        }
        result = adapter._build_history_summary(context)
        assert "Rule 15" in result

    def test_history_truncates_to_last_4(self, adapter):
        context = {
            "chat_history": [
                {"role": "user", "content": f"Message {i}"} for i in range(10)
            ]
        }
        result = adapter._build_history_summary(context)
        # Should only have last 4 messages
        assert "Message 9" in result
        assert "Message 6" in result

    def test_profile_no_context(self, adapter):
        result = adapter._build_user_profile(None)
        assert result != ""

    def test_profile_with_name_and_role(self, adapter):
        context = {"user_name": "Minh", "user_role": "student"}
        result = adapter._build_user_profile(context)
        assert "Minh" in result
        assert "student" in result

    def test_profile_with_semantic_context(self, adapter):
        context = {
            "user_role": "student",
            "semantic_context": "User is interested in SOLAS fire safety"
        }
        result = adapter._build_user_profile(context)
        assert "SOLAS" in result

    def test_profile_empty_context(self, adapter):
        # {} is falsy in Python, so returns early with "Không rõ"
        result = adapter._build_user_profile({})
        # Empty dict is falsy → returns fallback
        assert result != ""

    def test_profile_role_only(self, adapter):
        """Context with only user_role."""
        result = adapter._build_user_profile({"user_role": "student"})
        assert "student" in result


# ============================================================================
# adapt method
# ============================================================================


class TestAdaptMethod:
    """Test adapt method with mocked LLM."""

    @pytest.fixture
    def adapter_with_llm(self):
        mock_llm = AsyncMock()
        mock_budget = MagicMock()
        mock_budget_result = MagicMock()
        mock_budget_result.tier.value = "light"
        mock_budget_result.thinking_tokens = 256
        mock_budget_result.response_tokens = 512
        mock_budget.get_budget.return_value = mock_budget_result

        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light", return_value=mock_llm):
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget", return_value=mock_budget):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                adapter = ThinkingAdapter()
                # Force the mock LLM to be set (since _ensure_llm would call real get_llm_light)
                adapter._llm = mock_llm
                adapter._initialized = True
                return adapter, mock_llm

    @pytest.mark.asyncio
    async def test_adapt_success(self, adapter_with_llm):
        """Successful adaptation returns adapted response."""
        adapter, mock_llm = adapter_with_llm
        mock_llm.ainvoke.return_value = MagicMock(
            content="<thinking>Fresh thought</thinking>\n<answer>Adapted answer</answer>"
        )

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("<thinking>Fresh thought</thinking>\n<answer>Adapted answer</answer>", None)):
            result = await adapter.adapt(
                query="What is Rule 15?",
                cached_response={"answer": "Old answer", "sources": [], "thinking": "Old thinking"},
                similarity=0.99
            )
            assert result.answer == "Adapted answer"
            assert result.thinking == "Fresh thought"
            assert result.original_cached is False
            assert result.adaptation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_adapt_failure_fallback(self, adapter_with_llm):
        """LLM failure falls back to cached response."""
        adapter, mock_llm = adapter_with_llm
        mock_llm.ainvoke.side_effect = Exception("LLM error")

        result = await adapter.adapt(
            query="Test",
            cached_response={"answer": "Cached answer", "thinking": "Cached thought"},
            similarity=0.95
        )
        assert result.answer == "Cached answer"
        assert result.original_cached is True
        assert result.adaptation_method == "fallback"

    @pytest.mark.asyncio
    async def test_adapt_empty_answer_uses_cached(self, adapter_with_llm):
        """Empty adapted answer falls back to cached."""
        adapter, mock_llm = adapter_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="")

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("", None)):
            result = await adapter.adapt(
                query="Test",
                cached_response={"answer": "Good cached", "thinking": ""},
                similarity=0.99
            )
            # Empty adapted answer falls back to cached
            assert result.answer == "Good cached"


# ============================================================================
# Adaptation prompt building
# ============================================================================


class TestAdaptationPrompt:
    """Test _build_adaptation_prompt."""

    @pytest.fixture
    def adapter(self):
        with patch("app.engine.agentic_rag.thinking_adapter.get_llm_light"):
            with patch("app.engine.agentic_rag.adaptive_token_budget.get_adaptive_token_budget"):
                from app.engine.agentic_rag.thinking_adapter import ThinkingAdapter
                return ThinkingAdapter()

    def test_high_similarity_prompt(self, adapter):
        """High similarity (>=0.99) uses confirmation instruction."""
        prompt = adapter._build_adaptation_prompt(
            query="test", cached_answer="answer",
            cached_thinking="thought", history_summary="none",
            user_profile="student", similarity=0.99
        )
        assert "Wiii" in prompt
        assert "99" in prompt  # similarity percentage

    def test_lower_similarity_prompt(self, adapter):
        """Lower similarity uses different adaptation instruction."""
        prompt = adapter._build_adaptation_prompt(
            query="test", cached_answer="answer",
            cached_thinking="thought", history_summary="none",
            user_profile="student", similarity=0.95
        )
        assert "Wiii" in prompt
        # Should have different instruction than high similarity
        assert "95" in prompt
