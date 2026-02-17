"""
Tests for Sprint 53: InsightExtractor coverage.

Tests behavioral insight extraction:
- InsightExtractor init (no-api-key, error, success)
- extract_insights (no-llm, success, error, empty)
- _build_insight_prompt (basic, with-history)
- _parse_extraction_response (valid, markdown, not-list, invalid-category,
  short-content, empty-fields, json-error, general-error)
"""

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock

from app.models.semantic_memory import InsightCategory


# ============================================================================
# Init
# ============================================================================


class TestInsightExtractorInit:
    """Test InsightExtractor initialization."""

    def test_no_api_key(self):
        with patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = ""
            from app.engine.insight_extractor import InsightExtractor
            extractor = InsightExtractor()
        assert extractor._llm is None

    def test_llm_init_error(self):
        with patch("app.engine.llm_pool.get_llm_light", side_effect=Exception("LLM error")), \
             patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            from app.engine.insight_extractor import InsightExtractor
            extractor = InsightExtractor()
        assert extractor._llm is None

    def test_llm_init_success(self):
        mock_llm = MagicMock()
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            from app.engine.insight_extractor import InsightExtractor
            extractor = InsightExtractor()
        assert extractor._llm is mock_llm

    def test_categories(self):
        from app.engine.insight_extractor import InsightExtractor
        assert "learning_style" in InsightExtractor.INSIGHT_CATEGORIES
        assert "knowledge_gap" in InsightExtractor.INSIGHT_CATEGORIES
        assert "goal_evolution" in InsightExtractor.INSIGHT_CATEGORIES
        assert "habit" in InsightExtractor.INSIGHT_CATEGORIES
        assert "preference" in InsightExtractor.INSIGHT_CATEGORIES
        assert len(InsightExtractor.INSIGHT_CATEGORIES) == 5


# ============================================================================
# extract_insights
# ============================================================================


class TestExtractInsights:
    """Test insight extraction pipeline."""

    def _make_extractor(self, llm=None):
        with patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = ""
            from app.engine.insight_extractor import InsightExtractor
            extractor = InsightExtractor()
        extractor._llm = llm
        return extractor

    @pytest.mark.asyncio
    async def test_no_llm(self):
        extractor = self._make_extractor(llm=None)
        result = await extractor.extract_insights("user1", "Hello")
        assert result == []

    @pytest.mark.asyncio
    async def test_success(self):
        mock_llm = MagicMock()
        response_json = json.dumps([{
            "category": "learning_style",
            "content": "User thich hoc qua vi du thuc te hon la doc ly thuyet",
            "sub_topic": "practical_learning",
            "confidence": 0.85
        }], ensure_ascii=False)
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=response_json))

        extractor = self._make_extractor(llm=mock_llm)

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(response_json, None)):
            result = await extractor.extract_insights("user1", "Toi thich hoc bang vi du")

        assert len(result) == 1
        assert result[0].category == InsightCategory.LEARNING_STYLE
        assert result[0].user_id == "user1"
        assert result[0].confidence == 0.85

    @pytest.mark.asyncio
    async def test_llm_error(self):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))

        extractor = self._make_extractor(llm=mock_llm)
        result = await extractor.extract_insights("user1", "Test message")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_response(self):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))

        extractor = self._make_extractor(llm=mock_llm)
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("[]", None)):
            result = await extractor.extract_insights("user1", "Xin chao")
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_insights(self):
        mock_llm = MagicMock()
        response_json = json.dumps([
            {
                "category": "learning_style",
                "content": "User thich hoc qua vi du thuc te hon la doc ly thuyet kho khan",
                "confidence": 0.8
            },
            {
                "category": "knowledge_gap",
                "content": "User con nham lan giua Rule 13 va Rule 15 trong COLREGs navigation",
                "confidence": 0.9
            }
        ], ensure_ascii=False)
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=response_json))

        extractor = self._make_extractor(llm=mock_llm)
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(response_json, None)):
            result = await extractor.extract_insights("user1", "Rule 13 va Rule 15 giong nhau?")

        assert len(result) == 2
        assert result[0].category == InsightCategory.LEARNING_STYLE
        assert result[1].category == InsightCategory.KNOWLEDGE_GAP


# ============================================================================
# _build_insight_prompt
# ============================================================================


class TestBuildInsightPrompt:
    """Test prompt building."""

    def _make_extractor(self):
        with patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = ""
            from app.engine.insight_extractor import InsightExtractor
            return InsightExtractor()

    def test_basic(self):
        extractor = self._make_extractor()
        prompt = extractor._build_insight_prompt("What is SOLAS?", [])
        assert "What is SOLAS?" in prompt
        assert "learning_style" in prompt
        assert "knowledge_gap" in prompt

    def test_with_history(self):
        extractor = self._make_extractor()
        history = ["I want to learn COLREGs", "What are navigation lights?", "Tell me about Rule 13"]
        prompt = extractor._build_insight_prompt("Rule 13 details?", history)
        assert "Conversation context" in prompt
        assert "I want to learn COLREGs" in prompt

    def test_history_limited_to_3(self):
        extractor = self._make_extractor()
        history = [f"Message {i}" for i in range(10)]
        prompt = extractor._build_insight_prompt("Current message", history)
        # Should only include last 3
        assert "Message 7" in prompt
        assert "Message 8" in prompt
        assert "Message 9" in prompt
        assert "Message 0" not in prompt


# ============================================================================
# _parse_extraction_response
# ============================================================================


class TestParseExtractionResponse:
    """Test LLM response parsing."""

    def _make_extractor(self):
        with patch("app.engine.insight_extractor.settings") as mock_settings:
            mock_settings.google_api_key = ""
            from app.engine.insight_extractor import InsightExtractor
            return InsightExtractor()

    def test_valid_json(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "learning_style",
            "content": "User thich hoc qua vi du thuc te hon la doc ly thuyet",
            "sub_topic": "practical_learning",
            "confidence": 0.85
        }])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert len(result) == 1
        assert result[0].category == InsightCategory.LEARNING_STYLE
        assert result[0].sub_topic == "practical_learning"

    def test_markdown_json(self):
        extractor = self._make_extractor()
        response = '```json\n[{"category": "habit", "content": "User thuong hoc vao buoi toi va thich on bai nhieu lan", "confidence": 0.7}]\n```'
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert len(result) == 1
        assert result[0].category == InsightCategory.HABIT

    def test_not_list(self):
        extractor = self._make_extractor()
        response = json.dumps({"category": "habit", "content": "single object"})
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert result == []

    def test_invalid_category(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "invalid_category_xyz",
            "content": "Some long enough content for the test to pass validation check",
            "confidence": 0.8
        }])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert result == []

    def test_short_content(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "learning_style",
            "content": "Too short",  # Less than 20 chars
            "confidence": 0.8
        }])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert result == []

    def test_empty_fields(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "",
            "content": "",
            "confidence": 0.8
        }])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert result == []

    def test_json_error(self):
        extractor = self._make_extractor()
        result = extractor._parse_extraction_response("user1", "not valid json", "test msg")
        assert result == []

    def test_non_dict_item(self):
        extractor = self._make_extractor()
        response = json.dumps(["string item", 42])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert result == []

    def test_default_confidence(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "preference",
            "content": "User quan tam dac biet den cac tinh huong emergency va rescue operations"
        }])
        result = extractor._parse_extraction_response("user1", response, "test msg")
        assert len(result) == 1
        assert result[0].confidence == 0.8  # Default

    def test_source_messages(self):
        extractor = self._make_extractor()
        response = json.dumps([{
            "category": "goal_evolution",
            "content": "User da chuyen tu hoc co ban sang chuan bi thi bang thuyen truong hang 3",
            "confidence": 0.9
        }])
        result = extractor._parse_extraction_response("user1", response, "I want to prepare for captain exam")
        assert len(result) == 1
        assert "I want to prepare for captain exam" in result[0].source_messages
