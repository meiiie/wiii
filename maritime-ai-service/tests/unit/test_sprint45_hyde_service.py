"""
Tests for Sprint 45: HyDEService coverage.

Tests Hypothetical Document Embeddings service including:
- HyDEResult dataclass
- Language detection (Vietnamese vs English)
- should_use_hyde pattern matching
- Hypothetical document generation with mock LLM
- Query enhancement (conditional HyDE)
- Domain template injection
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# HyDEResult dataclass
# ============================================================================


class TestHyDEResult:
    """Test HyDEResult dataclass."""

    def test_success_result(self):
        from app.services.hyde_service import HyDEResult
        result = HyDEResult(
            original_query="What is Rule 15?",
            hypothetical_document="Rule 15 covers crossing situations...",
            language="en",
            success=True
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        from app.services.hyde_service import HyDEResult
        result = HyDEResult(
            original_query="query",
            hypothetical_document="query",
            language="unknown",
            success=False,
            error="LLM error"
        )
        assert result.success is False
        assert result.error == "LLM error"


# ============================================================================
# HyDEService initialization
# ============================================================================


class TestHyDEServiceInit:
    """Test HyDEService initialization."""

    def test_init_without_llm(self):
        from app.services.hyde_service import HyDEService
        svc = HyDEService()
        assert svc._llm is None
        assert svc._available is True

    def test_init_with_llm(self):
        from app.services.hyde_service import HyDEService
        mock_llm = MagicMock()
        svc = HyDEService(llm=mock_llm)
        assert svc._llm is mock_llm

    def test_set_domain_templates(self):
        from app.services.hyde_service import HyDEService
        svc = HyDEService()
        svc.set_domain_templates({"vi": "Vietnamese template {question}", "en": "English template {question}"})
        assert "vi" in svc._domain_templates
        assert "en" in svc._domain_templates


# ============================================================================
# Language detection
# ============================================================================


class TestLanguageDetection:
    """Test _detect_language."""

    @pytest.fixture
    def svc(self):
        from app.services.hyde_service import HyDEService
        return HyDEService()

    def test_english(self, svc):
        assert svc._detect_language("What is Rule 15 about?") == "en"

    def test_vietnamese(self, svc):
        assert svc._detect_language("Quy t\u1eafc 15 l\u00e0 g\u00ec?") == "vi"

    def test_vietnamese_with_diacritics(self, svc):
        assert svc._detect_language("\u0110i\u1ec1u 15 quy \u0111\u1ecbnh v\u1ec1 t\u00ecnh hu\u1ed1ng c\u1eaft nhau") == "vi"

    def test_mixed_defaults_to_vietnamese(self, svc):
        assert svc._detect_language("T\u00f4i mu\u1ed1n h\u1ecfi v\u1ec1 COLREG Rule 15") == "vi"

    def test_pure_ascii(self, svc):
        assert svc._detect_language("hello world") == "en"


# ============================================================================
# should_use_hyde
# ============================================================================


class TestShouldUseHyDE:
    """Test pattern matching for HyDE applicability."""

    @pytest.fixture
    def svc(self):
        from app.services.hyde_service import HyDEService
        return HyDEService()

    # Specific patterns (should NOT use HyDE)
    def test_specific_rule_number(self, svc):
        assert svc.should_use_hyde("Rule 15") is False

    def test_specific_vn_rule(self, svc):
        assert svc.should_use_hyde("quy t\u1eafc 15") is False

    def test_specific_dieu(self, svc):
        assert svc.should_use_hyde("\u0111i\u1ec1u 15") is False

    def test_specific_quoted_phrase(self, svc):
        assert svc.should_use_hyde('"crossing situation"') is False

    def test_specific_numeric(self, svc):
        assert svc.should_use_hyde("123") is False

    # Vague patterns (should use HyDE)
    def test_vague_what(self, svc):
        assert svc.should_use_hyde("what is maritime safety?") is True

    def test_vague_how(self, svc):
        assert svc.should_use_hyde("how do ships avoid collision?") is True

    def test_vague_why(self, svc):
        assert svc.should_use_hyde("why is COLREG important?") is True

    def test_vague_giai_thich(self, svc):
        assert svc.should_use_hyde("gi\u1ea3i th\u00edch v\u1ec1 lu\u1eadt h\u00e0ng h\u1ea3i") is True

    def test_vague_explain(self, svc):
        assert svc.should_use_hyde("explain the crossing situation") is True

    def test_vague_la_gi(self, svc):
        assert svc.should_use_hyde("l\u00e0 g\u00ec SOLAS?") is True

    # Length-based heuristic
    def test_long_query_uses_hyde(self, svc):
        """Queries with >= 5 words get HyDE by default."""
        assert svc.should_use_hyde("ships must follow certain rules at sea") is True

    def test_short_query_no_hyde(self, svc):
        """Short queries without patterns don't use HyDE."""
        assert svc.should_use_hyde("SOLAS") is False


# ============================================================================
# generate_hypothetical_document
# ============================================================================


class TestGenerateHypotheticalDocument:
    """Test LLM-based hypothetical document generation."""

    @pytest.mark.asyncio
    async def test_generation_success(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Hypothetical answer about Rule 15 crossing situation requirements")
        svc = HyDEService(llm=mock_llm)

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Hypothetical answer about Rule 15 crossing situation requirements", None)):
            result = await svc.generate_hypothetical_document("What is Rule 15?")
            assert result.success is True
            assert "Rule 15" in result.hypothetical_document
            assert result.language == "en"

    @pytest.mark.asyncio
    async def test_generation_vietnamese(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Quy t\u1eafc 15 v\u1ec1 t\u00ecnh hu\u1ed1ng c\u1eaft nhau")
        svc = HyDEService(llm=mock_llm)

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Quy t\u1eafc 15 v\u1ec1 t\u00ecnh hu\u1ed1ng c\u1eaft nhau", None)):
            result = await svc.generate_hypothetical_document("Quy t\u1eafc 15 l\u00e0 g\u00ec?")
            assert result.language == "vi"

    @pytest.mark.asyncio
    async def test_generation_failure_fallback(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM timeout")
        svc = HyDEService(llm=mock_llm)

        result = await svc.generate_hypothetical_document("Test query")
        assert result.success is False
        assert result.hypothetical_document == "Test query"  # Fallback to original
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_domain_template_used(self):
        """Domain template overrides default when available."""
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Custom domain response")
        svc = HyDEService(llm=mock_llm)
        svc.set_domain_templates({"en": "Custom template: {question}"})

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Custom domain response", None)):
            result = await svc.generate_hypothetical_document("Test query")
            assert result.success is True
            # Verify domain template was used (check the prompt arg)
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert "Custom template" in call_args[0].content


# ============================================================================
# enhance_query
# ============================================================================


class TestEnhanceQuery:
    """Test conditional query enhancement."""

    @pytest.mark.asyncio
    async def test_enhance_when_beneficial(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Enhanced hypothetical document")
        svc = HyDEService(llm=mock_llm)

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Enhanced hypothetical document", None)):
            # Vague query should trigger HyDE
            result = await svc.enhance_query("what is maritime safety?")
            assert result == "Enhanced hypothetical document"

    @pytest.mark.asyncio
    async def test_skip_when_specific(self):
        from app.services.hyde_service import HyDEService
        svc = HyDEService()
        # Specific query should not use HyDE
        result = await svc.enhance_query("Rule 15")
        assert result == "Rule 15"

    @pytest.mark.asyncio
    async def test_force_override(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Forced HyDE output")
        svc = HyDEService(llm=mock_llm)

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Forced HyDE output", None)):
            # Force=True overrides pattern matching
            result = await svc.enhance_query("Rule 15", force=True)
            assert result == "Forced HyDE output"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        from app.services.hyde_service import HyDEService
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("fail")
        svc = HyDEService(llm=mock_llm)

        result = await svc.enhance_query("what is maritime safety?")
        assert result == "what is maritime safety?"  # Fallback to original
