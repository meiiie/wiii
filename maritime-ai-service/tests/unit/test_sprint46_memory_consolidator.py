"""
Tests for Sprint 46: MemoryConsolidator coverage.

Tests memory consolidation including:
- ConsolidationResult dataclass
- should_consolidate threshold check
- consolidate (no LLM, success, error)
- _build_consolidation_prompt
- _parse_consolidation_response (valid JSON, invalid JSON, non-list, empty)
- _is_similar_insight (Jaccard similarity)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.semantic_memory import Insight, InsightCategory


# ============================================================================
# ConsolidationResult
# ============================================================================


class TestConsolidationResult:
    """Test ConsolidationResult dataclass."""

    def test_success_result(self):
        from app.engine.memory_consolidator import ConsolidationResult
        result = ConsolidationResult(
            success=True,
            original_count=40,
            final_count=30,
            consolidated_insights=[]
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        from app.engine.memory_consolidator import ConsolidationResult
        result = ConsolidationResult(
            success=False,
            original_count=40,
            final_count=40,
            consolidated_insights=[],
            error="LLM not available"
        )
        assert result.success is False
        assert result.error == "LLM not available"


# ============================================================================
# MemoryConsolidator init
# ============================================================================


class TestConsolidatorInit:
    """Test MemoryConsolidator initialization."""

    def test_init_no_api_key(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            assert mc._llm is None

    def test_init_with_api_key(self):
        mock_llm = MagicMock()
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
                from app.engine.memory_consolidator import MemoryConsolidator
                mc = MemoryConsolidator()
                assert mc._llm is mock_llm

    def test_thresholds(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            assert mc.CONSOLIDATION_THRESHOLD == 40
            assert mc.TARGET_COUNT == 30


# ============================================================================
# should_consolidate
# ============================================================================


class TestShouldConsolidate:
    """Test should_consolidate threshold check."""

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            assert await mc.should_consolidate(30) is False

    @pytest.mark.asyncio
    async def test_at_threshold(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            assert await mc.should_consolidate(40) is True

    @pytest.mark.asyncio
    async def test_above_threshold(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            assert await mc.should_consolidate(50) is True


# ============================================================================
# consolidate - no LLM
# ============================================================================


class TestConsolidateNoLLM:
    """Test consolidate when LLM not available."""

    @pytest.mark.asyncio
    async def test_no_llm_returns_failure(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            insights = [_make_insight(f"Insight {i}") for i in range(5)]
            result = await mc.consolidate(insights)
            assert result.success is False
            assert result.error == "LLM not available"
            assert result.final_count == 5


# ============================================================================
# consolidate - with LLM
# ============================================================================


class TestConsolidateWithLLM:
    """Test consolidate with mock LLM."""

    @pytest.mark.asyncio
    async def test_successful_consolidation(self):
        consolidated_json = json.dumps([
            {"category": "learning_style", "content": "Merged insight about learning", "sub_topic": "visual", "confidence": 0.9},
            {"category": "knowledge_gap", "content": "Needs help with Rule 15", "confidence": 0.85}
        ])
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content=consolidated_json)

        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
                with patch("app.services.output_processor.extract_thinking_from_response",
                            return_value=(consolidated_json, None)):
                    from app.engine.memory_consolidator import MemoryConsolidator
                    mc = MemoryConsolidator()
                    insights = [_make_insight(f"Insight {i}") for i in range(45)]
                    result = await mc.consolidate(insights)
                    assert result.success is True
                    assert result.final_count <= 30

    @pytest.mark.asyncio
    async def test_consolidation_error_returns_original(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM timeout")

        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
                from app.engine.memory_consolidator import MemoryConsolidator
                mc = MemoryConsolidator()
                insights = [_make_insight(f"Insight {i}") for i in range(5)]
                result = await mc.consolidate(insights)
                assert result.success is False
                assert result.final_count == 5


# ============================================================================
# _build_consolidation_prompt
# ============================================================================


class TestBuildConsolidationPrompt:
    """Test _build_consolidation_prompt."""

    def test_prompt_contains_insights(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            mc = MemoryConsolidator()
            insights = [
                _make_insight("Student prefers visual learning", sub_topic="visual"),
                _make_insight("Weak at navigation rules", category=InsightCategory.KNOWLEDGE_GAP)
            ]
            prompt = mc._build_consolidation_prompt(insights)
            assert "visual learning" in prompt
            assert "navigation rules" in prompt
            assert str(mc.TARGET_COUNT) in prompt


# ============================================================================
# _parse_consolidation_response
# ============================================================================


class TestParseConsolidationResponse:
    """Test _parse_consolidation_response."""

    def _make_consolidator(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            return MemoryConsolidator()

    def test_valid_json(self):
        mc = self._make_consolidator()
        response = json.dumps([
            {"category": "learning_style", "content": "Learns visually", "confidence": 0.9}
        ])
        original = [_make_insight("Original")]
        result = mc._parse_consolidation_response(response, original)
        assert len(result) >= 1
        assert result[0].content == "Learns visually"

    def test_json_with_code_block(self):
        mc = self._make_consolidator()
        response = '```json\n[{"category": "preference", "content": "Prefers examples"}]\n```'
        original = [_make_insight("Original")]
        result = mc._parse_consolidation_response(response, original)
        assert len(result) >= 1

    def test_invalid_json_fallback(self):
        mc = self._make_consolidator()
        response = "This is not JSON"
        original = [_make_insight(f"Insight {i}") for i in range(35)]
        result = mc._parse_consolidation_response(response, original)
        assert len(result) <= 30  # Falls back to original[:TARGET_COUNT]

    def test_non_list_fallback(self):
        mc = self._make_consolidator()
        response = json.dumps({"category": "learning_style", "content": "test"})
        original = [_make_insight(f"Insight {i}") for i in range(35)]
        result = mc._parse_consolidation_response(response, original)
        assert len(result) <= 30

    def test_invalid_category_skipped(self):
        mc = self._make_consolidator()
        response = json.dumps([
            {"category": "invalid_cat", "content": "Bad category"},
            {"category": "learning_style", "content": "Good one"}
        ])
        original = [_make_insight("Original")]
        result = mc._parse_consolidation_response(response, original)
        # Only the valid category should be included
        valid = [r for r in result if r.content == "Good one"]
        assert len(valid) == 1

    def test_empty_content_skipped(self):
        mc = self._make_consolidator()
        response = json.dumps([
            {"category": "learning_style", "content": ""},
            {"category": "learning_style", "content": "Valid"}
        ])
        original = [_make_insight("Original")]
        result = mc._parse_consolidation_response(response, original)
        valid = [r for r in result if r.content == "Valid"]
        assert len(valid) == 1


# ============================================================================
# _is_similar_insight
# ============================================================================


class TestIsSimilarInsight:
    """Test _is_similar_insight Jaccard check."""

    def _make_consolidator(self):
        with patch("app.engine.memory_consolidator.settings") as mock_settings:
            mock_settings.google_api_key = None
            from app.engine.memory_consolidator import MemoryConsolidator
            return MemoryConsolidator()

    def test_same_content_same_category(self):
        mc = self._make_consolidator()
        i1 = _make_insight("Student learns through visual examples")
        i2 = _make_insight("Student learns through visual examples")
        assert mc._is_similar_insight(i1, i2) is True

    def test_different_categories(self):
        mc = self._make_consolidator()
        i1 = _make_insight("Visual learning", category=InsightCategory.LEARNING_STYLE)
        i2 = _make_insight("Visual learning", category=InsightCategory.KNOWLEDGE_GAP)
        assert mc._is_similar_insight(i1, i2) is False

    def test_similar_content(self):
        mc = self._make_consolidator()
        # Need > 0.5 Jaccard: shared words must be > half of union
        i1 = _make_insight("Student prefers visual learning with examples and practice")
        i2 = _make_insight("Student prefers visual learning with examples and drills")
        # words1={student,prefers,visual,learning,with,examples,and,practice}=8
        # words2={student,prefers,visual,learning,with,examples,and,drills}=8
        # intersection={student,prefers,visual,learning,with,examples,and}=7
        # union=9, Jaccard=7/9≈0.78 > 0.5
        assert mc._is_similar_insight(i1, i2) is True

    def test_different_content(self):
        mc = self._make_consolidator()
        i1 = _make_insight("Excellent at maritime navigation")
        i2 = _make_insight("Struggles with traffic law terminology")
        assert mc._is_similar_insight(i1, i2) is False

    def test_empty_content(self):
        mc = self._make_consolidator()
        i1 = _make_insight("")
        i2 = _make_insight("Some content")
        assert mc._is_similar_insight(i1, i2) is False


# ============================================================================
# Helper
# ============================================================================


def _make_insight(
    content: str,
    category: InsightCategory = InsightCategory.LEARNING_STYLE,
    sub_topic: str = None,
    user_id: str = "user1"
) -> Insight:
    """Create a test Insight."""
    return Insight(
        user_id=user_id,
        content=content,
        category=category,
        sub_topic=sub_topic,
        confidence=0.8,
        created_at=datetime.now(),
        last_accessed=datetime.now()
    )
