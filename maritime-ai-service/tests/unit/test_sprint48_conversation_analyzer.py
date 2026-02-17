"""
Tests for Sprint 48: ConversationAnalyzer coverage.

Tests conversation analysis including:
- QuestionType enum
- ConversationContext dataclass
- ConversationAnalyzer.analyze (empty, standalone, follow-up, ambiguous)
- _detect_question_type (patterns, short messages)
- _extract_current_topic (domain matching)
- _extract_keywords
- _infer_context (follow-up inference)
- _calculate_confidence
- _detect_incomplete_explanation
- build_context_prompt
- Singleton
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# QuestionType & ConversationContext
# ============================================================================


class TestQuestionTypeEnum:
    """Test QuestionType values."""

    def test_values(self):
        from app.engine.conversation_analyzer import QuestionType
        assert QuestionType.STANDALONE == "standalone"
        assert QuestionType.FOLLOW_UP == "follow_up"
        assert QuestionType.AMBIGUOUS == "ambiguous"
        assert QuestionType.CLARIFICATION == "clarification"


class TestConversationContext:
    """Test ConversationContext dataclass."""

    def test_defaults(self):
        from app.engine.conversation_analyzer import ConversationContext, QuestionType
        ctx = ConversationContext()
        assert ctx.current_topic is None
        assert ctx.question_type == QuestionType.STANDALONE
        assert ctx.confidence == 0.0
        assert ctx.recent_keywords == []
        assert ctx.proactive_hints == []
        assert ctx.should_offer_continuation is False


# ============================================================================
# _detect_question_type
# ============================================================================


class TestDetectQuestionType:
    """Test question type detection."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_standalone_rule_number(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Quy tắc 15 nói gì?")
        assert qt == QuestionType.STANDALONE

    def test_standalone_colregs(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Giải thích COLREGs")
        assert qt == QuestionType.STANDALONE

    def test_standalone_la_gi(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("SOLAS là gì?")
        assert qt == QuestionType.STANDALONE

    def test_follow_up_con(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Còn đèn xanh thì sao? Nó có ý nghĩa gì trong tình huống này?")
        assert qt == QuestionType.FOLLOW_UP

    def test_ambiguous_short_follow_up(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Còn đèn xanh?")
        assert qt == QuestionType.AMBIGUOUS

    def test_ambiguous_very_short(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Sao?")
        assert qt == QuestionType.AMBIGUOUS

    def test_ambiguous_short_generic(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("OK")
        assert qt == QuestionType.AMBIGUOUS

    def test_follow_up_vay(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        qt = analyzer._detect_question_type("Vậy quy tắc này áp dụng trong trường hợp nào thì phù hợp nhất?")
        assert qt == QuestionType.FOLLOW_UP


# ============================================================================
# _extract_current_topic
# ============================================================================


class TestExtractCurrentTopic:
    """Test topic extraction from conversation."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_navigation_lights(self, analyzer):
        msgs = [
            {"role": "user", "content": "Đèn đỏ trên tàu có ý nghĩa gì?"},
            {"role": "assistant", "content": "Đèn đỏ ở mạn trái tàu biểu thị..."},
        ]
        topic = analyzer._extract_current_topic(msgs)
        assert topic == "navigation_lights"

    def test_colregs(self, analyzer):
        msgs = [
            {"role": "user", "content": "Quy tắc tránh va chạm trên biển"},
            {"role": "assistant", "content": "Theo COLREGs, quy tắc nhường đường..."},
        ]
        topic = analyzer._extract_current_topic(msgs)
        assert topic == "colregs_rules"

    def test_no_topic(self, analyzer):
        msgs = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Chào bạn!"},
        ]
        topic = analyzer._extract_current_topic(msgs)
        assert topic is None


# ============================================================================
# _extract_keywords
# ============================================================================


class TestExtractKeywords:
    """Test keyword extraction."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_extracts_domain_keywords(self, analyzer):
        msgs = [
            {"role": "user", "content": "Tôi muốn hỏi về đèn tín hiệu trên tàu"},
        ]
        keywords = analyzer._extract_keywords(msgs)
        assert "đèn" in keywords
        assert "tín hiệu" in keywords

    def test_max_10_keywords(self, analyzer):
        msgs = [
            {"role": "user", "content": "Đèn đỏ đèn xanh đèn trắng tín hiệu mạn quy tắc rule colregs tránh va nhường đường an toàn solas cứu sinh"},
        ]
        keywords = analyzer._extract_keywords(msgs)
        assert len(keywords) <= 10

    def test_empty_messages(self, analyzer):
        keywords = analyzer._extract_keywords([])
        assert keywords == []


# ============================================================================
# _calculate_confidence
# ============================================================================


class TestCalculateConfidence:
    """Test confidence calculation."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_no_context(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext
        ctx = ConversationContext()
        assert analyzer._calculate_confidence(ctx) == 0.0

    def test_with_topic(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext
        ctx = ConversationContext(current_topic="colregs_rules")
        assert analyzer._calculate_confidence(ctx) == 0.4

    def test_with_topic_and_inferred(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext
        ctx = ConversationContext(current_topic="colregs_rules", inferred_context="Some context")
        assert analyzer._calculate_confidence(ctx) == 0.7

    def test_max_1(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext
        ctx = ConversationContext(
            current_topic="colregs",
            inferred_context="Some context",
            recent_keywords=["a", "b", "c"]
        )
        conf = analyzer._calculate_confidence(ctx)
        assert conf <= 1.0

    def test_few_keywords(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext
        ctx = ConversationContext(recent_keywords=["keyword1"])
        assert analyzer._calculate_confidence(ctx) == 0.1


# ============================================================================
# _detect_incomplete_explanation
# ============================================================================


class TestDetectIncompleteExplanation:
    """Test incomplete explanation detection."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_too_few_messages(self, analyzer):
        msgs = [{"role": "user", "content": "Hello"}]
        should_offer, topic = analyzer._detect_incomplete_explanation(msgs)
        assert should_offer is False
        assert topic is None

    def test_detects_rule_explanation(self, analyzer):
        msgs = [
            {"role": "user", "content": "Quy tắc 15 là gì?"},
            {"role": "assistant", "content": "Quy tắc 15 về tình huống cắt hướng..."},
            {"role": "user", "content": "Bao nhiêu?"},
        ]
        should_offer, topic = analyzer._detect_incomplete_explanation(msgs)
        assert should_offer is True
        assert topic == "15"

    def test_no_explanation_pattern(self, analyzer):
        msgs = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Chào bạn! Tôi có thể giúp gì?"},
            {"role": "user", "content": "Cảm ơn"},
        ]
        should_offer, topic = analyzer._detect_incomplete_explanation(msgs)
        assert should_offer is False


# ============================================================================
# analyze (full pipeline)
# ============================================================================


class TestAnalyze:
    """Test full analyze pipeline."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_empty_messages(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        ctx = analyzer.analyze([])
        assert ctx.question_type == QuestionType.STANDALONE
        assert ctx.current_topic is None

    def test_standalone_question(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        msgs = [{"role": "user", "content": "Rule 15 là gì?"}]
        ctx = analyzer.analyze(msgs)
        assert ctx.question_type == QuestionType.STANDALONE

    def test_follow_up_with_context(self, analyzer):
        from app.engine.conversation_analyzer import QuestionType
        msgs = [
            {"role": "user", "content": "Đèn đỏ trên tàu biểu thị điều gì?"},
            {"role": "assistant", "content": "Đèn đỏ ở mạn trái tàu biểu thị..."},
            {"role": "user", "content": "Còn đèn xanh thì sao? Nó áp dụng ở trường hợp nào?"},
        ]
        ctx = analyzer.analyze(msgs)
        assert ctx.question_type == QuestionType.FOLLOW_UP
        assert ctx.current_topic == "navigation_lights"

    def test_no_user_message(self, analyzer):
        msgs = [{"role": "assistant", "content": "Chào bạn!"}]
        ctx = analyzer.analyze(msgs)
        assert ctx.current_topic is None


# ============================================================================
# build_context_prompt
# ============================================================================


class TestBuildContextPrompt:
    """Test context prompt building."""

    @pytest.fixture
    def analyzer(self):
        from app.engine.conversation_analyzer import ConversationAnalyzer
        return ConversationAnalyzer()

    def test_standalone_returns_empty(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext, QuestionType
        ctx = ConversationContext(question_type=QuestionType.STANDALONE)
        assert analyzer.build_context_prompt(ctx) == ""

    def test_ambiguous_has_warning(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext, QuestionType
        ctx = ConversationContext(question_type=QuestionType.AMBIGUOUS)
        prompt = analyzer.build_context_prompt(ctx)
        assert "CONTEXT ANALYSIS" in prompt

    def test_follow_up_has_topic(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext, QuestionType
        ctx = ConversationContext(
            question_type=QuestionType.FOLLOW_UP,
            current_topic="colregs_rules",
            recent_keywords=["quy tắc", "tránh va"]
        )
        prompt = analyzer.build_context_prompt(ctx)
        assert "colregs_rules" in prompt

    def test_includes_inferred_context(self, analyzer):
        from app.engine.conversation_analyzer import ConversationContext, QuestionType
        ctx = ConversationContext(
            question_type=QuestionType.AMBIGUOUS,
            inferred_context="Related to previous topic"
        )
        prompt = analyzer.build_context_prompt(ctx)
        assert "Related to previous topic" in prompt


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_conversation_analyzer(self):
        import app.engine.conversation_analyzer as mod
        mod._conversation_analyzer = None
        a1 = mod.get_conversation_analyzer()
        a2 = mod.get_conversation_analyzer()
        assert a1 is a2
        mod._conversation_analyzer = None  # Cleanup
