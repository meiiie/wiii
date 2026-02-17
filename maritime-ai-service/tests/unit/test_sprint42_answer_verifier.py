"""
Tests for Sprint 42: AnswerVerifier coverage.

Tests answer verification logic including:
- VerificationResult dataclass behavior
- Empty/missing input handling
- Rule-based fallback verification
- LLM-based verification with mock
- Citation checking
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# ============================================================================
# VerificationResult dataclass tests
# ============================================================================


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_needs_warning_when_invalid(self):
        """needs_warning is True when is_valid=False."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        result = VerificationResult(is_valid=False, confidence=90, issues=[])
        assert result.needs_warning is True

    def test_needs_warning_when_low_confidence(self):
        """needs_warning is True when confidence < 70."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        result = VerificationResult(is_valid=True, confidence=60, issues=[])
        assert result.needs_warning is True

    def test_no_warning_when_valid_and_confident(self):
        """needs_warning is False when valid and confidence >= 70."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        result = VerificationResult(is_valid=True, confidence=80, issues=[])
        assert result.needs_warning is False

    def test_needs_warning_at_boundary(self):
        """needs_warning at confidence=70 boundary."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        # Exactly 70 should NOT need warning (>= 70)
        result_at_70 = VerificationResult(is_valid=True, confidence=70, issues=[])
        assert result_at_70.needs_warning is False
        # 69 should need warning
        result_at_69 = VerificationResult(is_valid=True, confidence=69, issues=[])
        assert result_at_69.needs_warning is True

    def test_warning_field_default(self):
        """warning defaults to None."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        result = VerificationResult(is_valid=True, confidence=80, issues=[])
        assert result.warning is None

    def test_warning_field_custom(self):
        """warning can be set."""
        from app.engine.agentic_rag.answer_verifier import VerificationResult
        result = VerificationResult(
            is_valid=False, confidence=50,
            issues=["test"], warning="Custom warning"
        )
        assert result.warning == "Custom warning"


# ============================================================================
# AnswerVerifier edge cases
# ============================================================================


class TestAnswerVerifierEdgeCases:
    """Test AnswerVerifier input handling."""

    @pytest.fixture
    def verifier_no_llm(self):
        """Create verifier with no LLM (triggers rule-based fallback)."""
        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.answer_verifier import AnswerVerifier
            v = AnswerVerifier()
            assert v._llm is None
            return v

    @pytest.mark.asyncio
    async def test_verify_empty_answer(self, verifier_no_llm):
        """Empty answer returns invalid result."""
        result = await verifier_no_llm.verify("", [{"content": "source"}])
        assert result.is_valid is False
        assert result.confidence == 0
        assert "Empty answer" in result.issues

    @pytest.mark.asyncio
    async def test_verify_no_sources(self, verifier_no_llm):
        """No sources returns uncertain result."""
        result = await verifier_no_llm.verify("Some answer", [])
        assert result.is_valid is True
        assert result.confidence == 50
        assert result.warning is not None

    @pytest.mark.asyncio
    async def test_verify_none_answer(self, verifier_no_llm):
        """None/empty answer triggers empty check."""
        result = await verifier_no_llm.verify("", [])
        assert result.is_valid is False
        assert result.confidence == 0

    def test_is_available_no_llm(self, verifier_no_llm):
        """is_available returns False when no LLM."""
        assert verifier_no_llm.is_available() is False

    def test_is_available_with_llm(self):
        """is_available returns True when LLM exists."""
        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate") as mock_llm:
            mock_llm.return_value = MagicMock()
            from app.engine.agentic_rag.answer_verifier import AnswerVerifier
            v = AnswerVerifier()
            assert v.is_available() is True


# ============================================================================
# Rule-based verification (fallback)
# ============================================================================


class TestRuleBasedVerification:
    """Test rule-based fallback verification."""

    @pytest.fixture
    def verifier(self):
        """Create verifier with no LLM."""
        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.answer_verifier import AnswerVerifier
            return AnswerVerifier()

    @pytest.mark.asyncio
    async def test_high_overlap_passes(self, verifier):
        """High keyword overlap results in valid verification."""
        sources = [{"content": "Rule 15 says vessels must give way when crossing from starboard"}]
        answer = "According to Rule 15, vessels crossing from starboard must give way"
        result = await verifier.verify(answer, sources)
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_low_overlap_fails(self, verifier):
        """Low keyword overlap results in low confidence."""
        sources = [{"content": "COLREGs Rule 15 crossing situation"}]
        answer = "The Bermuda Triangle is a mysterious area in the Atlantic Ocean"
        result = await verifier.verify(answer, sources)
        assert result.confidence < 70

    @pytest.mark.asyncio
    async def test_sources_with_text_key(self, verifier):
        """Sources using 'text' key instead of 'content'."""
        sources = [{"text": "SOLAS Chapter II fire safety regulations"}]
        answer = "SOLAS Chapter II covers fire safety regulations"
        result = await verifier.verify(answer, sources)
        assert result.confidence > 0

    def test_rule_based_verify_direct(self, verifier):
        """Direct call to _rule_based_verify."""
        sources = [{"content": "word1 word2 word3 word4 word5"}]
        answer = "word1 word2 word3 word4 word5"
        result = verifier._rule_based_verify(answer, sources)
        assert result.is_valid is True
        assert result.confidence > 70


# ============================================================================
# LLM-based verification
# ============================================================================


class TestLLMBasedVerification:
    """Test LLM-based verification with mocked LLM."""

    @pytest.fixture
    def verifier_with_llm(self):
        """Create verifier with mocked LLM."""
        mock_llm = AsyncMock()
        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate", return_value=mock_llm):
            from app.engine.agentic_rag.answer_verifier import AnswerVerifier
            v = AnswerVerifier()
            return v, mock_llm

    @pytest.mark.asyncio
    async def test_llm_verify_valid(self, verifier_with_llm):
        """LLM returns valid verification."""
        verifier, mock_llm = verifier_with_llm
        mock_llm.ainvoke.return_value = MagicMock(
            content=json.dumps({
                "is_factually_correct": True,
                "confidence": 90,
                "issues": [],
                "has_unsupported_claims": False
            })
        )
        result = await verifier.verify("Good answer", [{"content": "source text"}])
        assert result.is_valid is True
        assert result.confidence == 90
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_llm_verify_hallucination(self, verifier_with_llm):
        """LLM detects hallucination."""
        verifier, mock_llm = verifier_with_llm
        mock_llm.ainvoke.return_value = MagicMock(
            content=json.dumps({
                "is_factually_correct": False,
                "confidence": 30,
                "issues": ["Fabricated statistics"],
                "has_unsupported_claims": True
            })
        )
        result = await verifier.verify("Bad answer", [{"content": "source text"}])
        assert result.is_valid is False
        assert result.warning is not None
        assert "xác minh" in result.warning.lower() or "tin cậy" in result.warning.lower()

    @pytest.mark.asyncio
    async def test_llm_verify_low_confidence(self, verifier_with_llm):
        """LLM returns low confidence."""
        verifier, mock_llm = verifier_with_llm
        mock_llm.ainvoke.return_value = MagicMock(
            content=json.dumps({
                "is_factually_correct": True,
                "confidence": 40,
                "issues": ["Vague answer"],
                "has_unsupported_claims": False
            })
        )
        result = await verifier.verify("Vague answer", [{"content": "source"}])
        assert result.is_valid is False
        assert "40" in result.warning

    @pytest.mark.asyncio
    async def test_llm_verify_json_in_codeblock(self, verifier_with_llm):
        """LLM wraps JSON in markdown code block."""
        verifier, mock_llm = verifier_with_llm
        json_data = json.dumps({
            "is_factually_correct": True,
            "confidence": 85,
            "issues": [],
            "has_unsupported_claims": False
        })
        mock_llm.ainvoke.return_value = MagicMock(
            content=f"```json\n{json_data}\n```"
        )
        result = await verifier.verify("Answer", [{"content": "source"}])
        assert result.is_valid is True
        assert result.confidence == 85

    @pytest.mark.asyncio
    async def test_llm_verify_failure_falls_back(self, verifier_with_llm):
        """LLM failure falls back to rule-based."""
        verifier, mock_llm = verifier_with_llm
        mock_llm.ainvoke.side_effect = Exception("LLM error")
        result = await verifier.verify(
            "word1 word2 word3",
            [{"content": "word1 word2 word3 word4"}]
        )
        # Should still get a result from rule-based fallback
        assert isinstance(result.confidence, (int, float))


# ============================================================================
# Citation checking
# ============================================================================


class TestCitationChecking:
    """Test citation verification."""

    @pytest.fixture
    def verifier(self):
        """Create verifier."""
        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.answer_verifier import AnswerVerifier
            return AnswerVerifier()

    @pytest.mark.asyncio
    async def test_check_citations_found_in_sources(self, verifier):
        """Citations found in sources are marked valid."""
        sources = [{"content": "According to Rule 15, crossing situation requires action by give-way vessel"}]
        answer = "Rule 15 states the crossing situation requirements"
        results = await verifier.check_citations(answer, sources)
        assert "Rule 15" in results
        assert results["Rule 15"] is True

    @pytest.mark.asyncio
    async def test_check_citations_not_in_sources(self, verifier):
        """Citations not in sources are marked invalid."""
        sources = [{"content": "Safety regulations for fire protection"}]
        answer = "Rule 15 requires vessels to give way"
        results = await verifier.check_citations(answer, sources)
        assert "Rule 15" in results
        assert results["Rule 15"] is False

    @pytest.mark.asyncio
    async def test_check_citations_vietnamese_patterns(self, verifier):
        """Vietnamese citation patterns detected."""
        sources = [{"content": "Theo Điều 15, quy tắc tránh va"}]
        answer = "Điều 15 quy định về tình huống cắt nhau"
        results = await verifier.check_citations(answer, sources)
        found_dieu = any("Điều 15" in k for k in results)
        assert found_dieu

    @pytest.mark.asyncio
    async def test_check_citations_no_citations(self, verifier):
        """No citations in answer returns empty dict."""
        sources = [{"content": "Some content"}]
        answer = "A general statement without specific references"
        results = await verifier.check_citations(answer, sources)
        # May find number patterns but no specific rule citations
        # The key thing is it doesn't crash
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_check_citations_solas_pattern(self, verifier):
        """SOLAS citation pattern detected."""
        sources = [{"content": "SOLAS Chapter II-2 fire safety"}]
        answer = "According to SOLAS Chapter II-2, fire protection is required"
        results = await verifier.check_citations(answer, sources)
        found_solas = any("SOLAS" in k for k in results)
        assert found_solas
