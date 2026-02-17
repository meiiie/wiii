"""
Tests for Sprint 38: ReflectionParser — Self-RAG reflection token parsing.

Covers:
- ReflectionResult dataclass
- ReflectionConfidence enum
- _parse_bool helper
- _check_supported pattern matching
- _check_useful pattern matching
- _extract_confidence scoring
- _check_needs_correction decision logic
- parse() integration with mocked extract_thinking_from_response
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.agentic_rag.reflection_parser import (
    ReflectionConfidence,
    ReflectionResult,
    ReflectionParser,
    REFLECTION_PATTERNS,
    CORRECTION_INDICATORS,
    POSITIVE_INDICATORS,
)


@pytest.fixture
def parser():
    """Create a ReflectionParser with reflection disabled (avoid settings dep)."""
    with patch("app.engine.agentic_rag.reflection_parser.settings") as mock_settings:
        mock_settings.rag_enable_reflection = False
        mock_settings.rag_quality_mode = "balanced"
        p = ReflectionParser()
    # Patch settings for methods that read it at call time
    with patch("app.engine.agentic_rag.reflection_parser.settings") as mock_settings:
        mock_settings.rag_quality_mode = "balanced"
        yield p


# ============================================================================
# ReflectionResult dataclass
# ============================================================================


class TestReflectionResult:
    def test_creation(self):
        r = ReflectionResult(
            is_supported=True,
            is_useful=True,
            needs_correction=False,
            confidence=ReflectionConfidence.HIGH,
            thinking_content="thinking",
            answer_content="answer",
        )
        assert r.is_supported is True
        assert r.correction_reason is None
        assert r.raw_response is None

    def test_with_correction_reason(self):
        r = ReflectionResult(
            is_supported=False,
            is_useful=True,
            needs_correction=True,
            confidence=ReflectionConfidence.LOW,
            thinking_content="",
            answer_content="test",
            correction_reason="Low confidence",
        )
        assert r.correction_reason == "Low confidence"


# ============================================================================
# ReflectionConfidence enum
# ============================================================================


class TestReflectionConfidence:
    def test_values(self):
        assert ReflectionConfidence.HIGH.value == "high"
        assert ReflectionConfidence.MEDIUM.value == "medium"
        assert ReflectionConfidence.LOW.value == "low"
        assert ReflectionConfidence.UNKNOWN.value == "unknown"


# ============================================================================
# Regex patterns
# ============================================================================


class TestReflectionPatterns:
    def test_supported_pattern_bracket(self):
        match = REFLECTION_PATTERNS["supported"].search("[IS_SUPPORTED: yes]")
        assert match is not None

    def test_supported_pattern_underscore(self):
        match = REFLECTION_PATTERNS["supported"].search("[ISSUPPORTED: true]")
        assert match is not None

    def test_supported_pattern_key_value(self):
        match = REFLECTION_PATTERNS["supported"].search("is_supported: yes")
        assert match is not None

    def test_useful_pattern_bracket(self):
        match = REFLECTION_PATTERNS["useful"].search("[IS_USEFUL: yes]")
        assert match is not None

    def test_needs_correction_pattern(self):
        match = REFLECTION_PATTERNS["needs_correction"].search("[NEEDS_CORRECTION: yes]")
        assert match is not None

    def test_json_confidence_pattern(self):
        match = REFLECTION_PATTERNS["json_confidence"].search('"confidence": 0.85')
        assert match is not None
        assert match.group(1) == "0.85"

    def test_json_confidence_vietnamese(self):
        match = REFLECTION_PATTERNS["json_confidence"].search('"chính xác": 9')
        assert match is not None
        assert match.group(1) == "9"


# ============================================================================
# _parse_bool
# ============================================================================


class TestParseBool:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = False
            return ReflectionParser()

    @pytest.mark.parametrize("value,expected", [
        ("yes", True),
        ("true", True),
        ("1", True),
        ("có", True),
        ("đúng", True),
        ("chính xác", True),
        ("no", False),
        ("false", False),
        ("0", False),
        ("không", False),
        ("  Yes  ", True),
        ("FALSE", False),
    ])
    def test_parse_bool_values(self, parser_inst, value, expected):
        assert parser_inst._parse_bool(value) == expected


# ============================================================================
# _check_supported
# ============================================================================


class TestCheckSupported:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = False
            return ReflectionParser()

    def test_explicit_token_yes(self, parser_inst):
        assert parser_inst._check_supported("[IS_SUPPORTED: yes]", None) is True

    def test_explicit_token_no(self, parser_inst):
        assert parser_inst._check_supported("[IS_SUPPORTED: no]", None) is False

    def test_citation_indicator_vietnamese(self, parser_inst):
        assert parser_inst._check_supported("Theo điều 15 COLREGs", None) is True

    def test_citation_indicator_english(self, parser_inst):
        assert parser_inst._check_supported("According to the regulation", None) is True

    def test_negative_indicator(self, parser_inst):
        assert parser_inst._check_supported("không có thông tin về vấn đề này", None) is False

    def test_default_supported(self, parser_inst):
        assert parser_inst._check_supported("Some normal answer text", None) is True

    def test_thinking_content_checked(self, parser_inst):
        assert parser_inst._check_supported("answer", "dựa trên tài liệu") is True


# ============================================================================
# _check_useful
# ============================================================================


class TestCheckUseful:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = False
            return ReflectionParser()

    def test_explicit_token_yes(self, parser_inst):
        assert parser_inst._check_useful("[IS_USEFUL: yes]", None) is True

    def test_explicit_token_no(self, parser_inst):
        assert parser_inst._check_useful("[IS_USEFUL: no]", None) is False

    def test_unhelpful_indicator_vietnamese(self, parser_inst):
        assert parser_inst._check_useful("Tôi không thể trả lời", None) is False

    def test_unhelpful_indicator_english(self, parser_inst):
        assert parser_inst._check_useful("I cannot provide that information", None) is False

    def test_short_text_not_useful(self, parser_inst):
        assert parser_inst._check_useful("short", None) is False

    def test_long_text_useful(self, parser_inst):
        text = "This is a detailed answer that provides comprehensive information about the topic at hand."
        assert parser_inst._check_useful(text, None) is True


# ============================================================================
# _extract_confidence
# ============================================================================


class TestExtractConfidence:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = False
            return ReflectionParser()

    def test_high_score_decimal(self, parser_inst):
        conf = parser_inst._extract_confidence('"confidence": 0.9', None)
        assert conf == ReflectionConfidence.HIGH

    def test_high_score_integer(self, parser_inst):
        conf = parser_inst._extract_confidence('"confidence": 9', None)
        assert conf == ReflectionConfidence.HIGH

    def test_medium_score(self, parser_inst):
        conf = parser_inst._extract_confidence('"confidence": 0.6', None)
        assert conf == ReflectionConfidence.MEDIUM

    def test_low_score(self, parser_inst):
        conf = parser_inst._extract_confidence('"confidence": 0.3', None)
        assert conf == ReflectionConfidence.LOW

    def test_positive_indicators_high(self, parser_inst):
        text = "Chắc chắn rằng câu trả lời chính xác và rõ ràng dựa trên điều luật."
        conf = parser_inst._extract_confidence(text, None)
        assert conf == ReflectionConfidence.HIGH

    def test_negative_indicators_low(self, parser_inst):
        text = "Không chắc chắn, cần xác minh, thiếu thông tin."
        conf = parser_inst._extract_confidence(text, None)
        assert conf == ReflectionConfidence.LOW

    def test_mixed_indicators_medium(self, parser_inst):
        text = "Đúng nhưng cần kiểm tra thêm."
        conf = parser_inst._extract_confidence(text, None)
        assert conf == ReflectionConfidence.MEDIUM


# ============================================================================
# _check_needs_correction
# ============================================================================


class TestCheckNeedsCorrection:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = False
            s.rag_quality_mode = "balanced"
            return ReflectionParser()

    def test_explicit_token(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "[NEEDS_CORRECTION: yes]", None, True, True, ReflectionConfidence.HIGH
            )
        assert needs is True
        assert "Explicit correction token" in reason

    def test_low_confidence(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "text", None, True, True, ReflectionConfidence.LOW
            )
        assert needs is True
        assert "Low confidence" in reason

    def test_not_supported(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "text", None, False, True, ReflectionConfidence.MEDIUM
            )
        assert needs is True

    def test_not_useful(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "text", None, True, False, ReflectionConfidence.MEDIUM
            )
        assert needs is True

    def test_high_confidence_no_correction(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "good text", None, True, True, ReflectionConfidence.HIGH
            )
        assert needs is False
        assert reason is None

    def test_quality_mode_medium_triggers(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "quality"
            needs, reason = parser_inst._check_needs_correction(
                "text", None, True, True, ReflectionConfidence.MEDIUM
            )
        assert needs is True
        assert "Quality mode" in reason

    def test_thinking_correction_indicator(self, parser_inst):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            needs, reason = parser_inst._check_needs_correction(
                "answer", "cần xác minh thêm", True, True, ReflectionConfidence.MEDIUM
            )
        assert needs is True
        assert "Correction indicator in thinking" in reason


# ============================================================================
# parse() integration
# ============================================================================


class TestParseIntegration:
    @pytest.fixture
    def parser_inst(self):
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_enable_reflection = True
            s.rag_quality_mode = "balanced"
            return ReflectionParser()

    @patch("app.services.output_processor.extract_thinking_from_response")
    def test_parse_supported_useful_high(self, mock_extract, parser_inst):
        mock_extract.return_value = (
            "Theo điều 15 COLREGs, tàu thuyền phải nhường đường khi gặp nhau cắt hướng.",
            "Thinking: câu trả lời chính xác và rõ ràng dựa trên điều luật"
        )
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            result = parser_inst.parse("raw response")

        assert result.is_supported is True
        assert result.is_useful is True
        assert result.needs_correction is False

    @patch("app.services.output_processor.extract_thinking_from_response")
    def test_parse_unsupported(self, mock_extract, parser_inst):
        mock_extract.return_value = (
            "Không có thông tin về vấn đề này trong tài liệu.",
            None
        )
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            result = parser_inst.parse("raw response")

        assert result.is_supported is False
        assert result.needs_correction is True

    @patch("app.services.output_processor.extract_thinking_from_response")
    def test_parse_with_explicit_tokens(self, mock_extract, parser_inst):
        mock_extract.return_value = (
            "[IS_SUPPORTED: yes] [IS_USEFUL: yes] Answer content here which is sufficiently long.",
            "[NEEDS_CORRECTION: no]"
        )
        with patch("app.engine.agentic_rag.reflection_parser.settings") as s:
            s.rag_quality_mode = "balanced"
            result = parser_inst.parse("raw")

        assert result.is_supported is True
        assert result.is_useful is True
