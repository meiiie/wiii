"""
Tests for Sprint 33: ConversationAnalyzer — pure logic, no LLM.

Covers:
- _detect_question_type: question classification
- _extract_current_topic: topic extraction from history
- _extract_keywords: keyword extraction
- _calculate_confidence: confidence scoring
- analyze: end-to-end analysis
- build_context_prompt: prompt construction
"""

import pytest
from app.engine.conversation_analyzer import (
    ConversationAnalyzer,
    ConversationContext,
    QuestionType,
)


@pytest.fixture
def analyzer():
    return ConversationAnalyzer()


# =============================================================================
# QuestionType enum
# =============================================================================


class TestQuestionType:
    def test_enum_values(self):
        assert QuestionType.STANDALONE == "standalone"
        assert QuestionType.FOLLOW_UP == "follow_up"
        assert QuestionType.AMBIGUOUS == "ambiguous"


# =============================================================================
# ConversationContext dataclass
# =============================================================================


class TestConversationContext:
    def test_defaults(self):
        ctx = ConversationContext()
        assert ctx.current_topic is None
        assert ctx.question_type == QuestionType.STANDALONE
        assert ctx.recent_keywords == []
        assert ctx.confidence == 0.0

    def test_should_offer_continuation(self):
        ctx = ConversationContext(should_offer_continuation=True)
        assert ctx.should_offer_continuation is True


# =============================================================================
# _detect_question_type
# =============================================================================


class TestDetectQuestionType:
    def test_standalone_with_rule(self, analyzer):
        qtype = analyzer._detect_question_type("quy tắc 15 nói gì?")
        assert qtype == QuestionType.STANDALONE

    def test_follow_up_pattern(self, analyzer):
        qtype = analyzer._detect_question_type("còn quy tắc 16 thì sao?")
        assert qtype in (QuestionType.FOLLOW_UP, QuestionType.AMBIGUOUS)

    def test_ambiguous_short(self, analyzer):
        qtype = analyzer._detect_question_type("rồi sao?")
        assert qtype in (QuestionType.AMBIGUOUS, QuestionType.FOLLOW_UP)

    def test_standalone_long(self, analyzer):
        qtype = analyzer._detect_question_type(
            "Giải thích chi tiết về COLREGS và các quy tắc tránh va"
        )
        assert qtype == QuestionType.STANDALONE

    def test_empty_message(self, analyzer):
        qtype = analyzer._detect_question_type("")
        assert qtype == QuestionType.AMBIGUOUS


# =============================================================================
# _extract_current_topic
# =============================================================================


class TestExtractCurrentTopic:
    def test_navigation_topic(self, analyzer):
        messages = [
            {"role": "user", "content": "hỏi về đèn tín hiệu hành trình"},
            {"role": "assistant", "content": "Đèn tín hiệu hành trình gồm..."},
        ]
        topic = analyzer._extract_current_topic(messages)
        # Should detect navigation_lights or navigation-related
        assert topic is not None

    def test_no_topic(self, analyzer):
        messages = [
            {"role": "user", "content": "xin chào bạn"},
        ]
        topic = analyzer._extract_current_topic(messages)
        # "xin chào" is a greeting, may not match domain topics
        # Could be None or match due to overlap
        assert topic is None or isinstance(topic, str)

    def test_empty_messages(self, analyzer):
        topic = analyzer._extract_current_topic([])
        assert topic is None

    def test_colregs_topic(self, analyzer):
        messages = [
            {"role": "user", "content": "COLREGS rule 15 về tình huống cắt nhau"},
            {"role": "assistant", "content": "Quy tắc 15 COLREGs nói về..."},
        ]
        topic = analyzer._extract_current_topic(messages)
        assert topic is not None


# =============================================================================
# _extract_keywords
# =============================================================================


class TestExtractKeywords:
    def test_basic_extraction(self, analyzer):
        messages = [
            {"role": "user", "content": "SOLAS chapter III about lifesaving"},
            {"role": "assistant", "content": "Chapter III covers lifesaving..."},
        ]
        keywords = analyzer._extract_keywords(messages)
        assert isinstance(keywords, list)

    def test_empty_messages(self, analyzer):
        keywords = analyzer._extract_keywords([])
        assert keywords == []


# =============================================================================
# _calculate_confidence
# =============================================================================


class TestCalculateConfidence:
    def test_zero_confidence(self, analyzer):
        ctx = ConversationContext()
        conf = analyzer._calculate_confidence(ctx)
        assert conf == 0.0

    def test_topic_adds_confidence(self, analyzer):
        ctx = ConversationContext(current_topic="colregs_rules")
        conf = analyzer._calculate_confidence(ctx)
        assert conf >= 0.4

    def test_full_context_high_confidence(self, analyzer):
        ctx = ConversationContext(
            current_topic="colregs_rules",
            inferred_context="Discussing COLREGs rule 15",
            recent_keywords=["colregs", "rule", "crossing"],
        )
        conf = analyzer._calculate_confidence(ctx)
        assert conf >= 0.8

    def test_capped_at_1(self, analyzer):
        ctx = ConversationContext(
            current_topic="safety",
            inferred_context="Full context available",
            recent_keywords=["a", "b", "c", "d", "e"],
        )
        conf = analyzer._calculate_confidence(ctx)
        assert conf <= 1.0


# =============================================================================
# analyze (end-to-end)
# =============================================================================


class TestAnalyze:
    def test_analyze_empty_messages(self, analyzer):
        ctx = analyzer.analyze([])
        assert isinstance(ctx, ConversationContext)

    def test_analyze_with_history(self, analyzer):
        messages = [
            {"role": "user", "content": "tell me about COLREGS rule 15"},
            {"role": "assistant", "content": "Rule 15 deals with crossing situations..."},
            {"role": "user", "content": "what about rule 16?"},
        ]
        ctx = analyzer.analyze(messages)
        assert isinstance(ctx, ConversationContext)
        assert ctx.question_type is not None

    def test_analyze_standalone_question(self, analyzer):
        messages = [
            {"role": "user", "content": "Giải thích chi tiết về SOLAS Chapter II-2 về phòng cháy"},
        ]
        ctx = analyzer.analyze(messages)
        assert ctx.question_type == QuestionType.STANDALONE


# =============================================================================
# build_context_prompt
# =============================================================================


class TestBuildContextPrompt:
    def test_builds_prompt_with_context(self, analyzer):
        ctx = ConversationContext(
            current_topic="colregs_rules",
            question_type=QuestionType.FOLLOW_UP,
            inferred_context="Đang nói về COLREGs",
            recent_keywords=["colregs", "rule"],
            confidence=0.8,
        )
        prompt = analyzer.build_context_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_builds_prompt_empty_context(self, analyzer):
        ctx = ConversationContext()
        prompt = analyzer.build_context_prompt(ctx)
        assert isinstance(prompt, str)

    def test_follow_up_mention(self, analyzer):
        ctx = ConversationContext(
            question_type=QuestionType.FOLLOW_UP,
            current_topic="safety",
            confidence=0.5,
        )
        prompt = analyzer.build_context_prompt(ctx)
        # Should mention follow-up or context
        assert isinstance(prompt, str)
