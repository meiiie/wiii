"""
Tests for Vietnamese pronoun/name disambiguation in fact extraction.

Bug: "Minh que Hai Phong" → LLM extracts name="Minh" instead of recognizing
"minh" as the Vietnamese pronoun "mình" (meaning "I/me").

Fix: _detect_pronoun_as_name() pre-filter + prompt rules + examples.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engine.semantic_memory.extraction import (
    _detect_pronoun_as_name,
    _strip_diacritics,
    _VIETNAMESE_PRONOUNS,
)


# ============================================================================
# _strip_diacritics
# ============================================================================


class TestStripDiacritics:
    """Test Vietnamese diacritics stripping."""

    def test_strips_common_vietnamese(self):
        assert _strip_diacritics("Hải Phòng") == "Hai Phong"

    def test_strips_d_stroke(self):
        assert _strip_diacritics("đại học") == "dai hoc"
        assert _strip_diacritics("Đại học") == "Dai hoc"

    def test_strips_complex_diacritics(self):
        assert _strip_diacritics("Luật Hàng hải Quốc tế") == "Luat Hang hai Quoc te"

    def test_preserves_ascii(self):
        assert _strip_diacritics("hello world") == "hello world"

    def test_empty_string(self):
        assert _strip_diacritics("") == ""

    def test_bong_da(self):
        """Regression: 'bóng đá' must become 'bong da' not 'bong đa'."""
        assert _strip_diacritics("bóng đá") == "bong da"


# ============================================================================
# _VIETNAMESE_PRONOUNS constant
# ============================================================================


class TestVietnamesePronouns:
    """Test the pronoun mapping constant."""

    def test_contains_common_pronouns(self):
        assert "minh" in _VIETNAMESE_PRONOUNS
        assert "toi" in _VIETNAMESE_PRONOUNS
        assert "em" in _VIETNAMESE_PRONOUNS
        assert "anh" in _VIETNAMESE_PRONOUNS

    def test_maps_to_diacriticized_form(self):
        assert _VIETNAMESE_PRONOUNS["minh"] == "mình"
        assert _VIETNAMESE_PRONOUNS["toi"] == "tôi"
        assert _VIETNAMESE_PRONOUNS["chi"] == "chị"

    def test_does_not_contain_real_names(self):
        """Common Vietnamese names should NOT be in pronoun list."""
        assert "hung" not in _VIETNAMESE_PRONOUNS
        assert "linh" not in _VIETNAMESE_PRONOUNS
        assert "nam" not in _VIETNAMESE_PRONOUNS


# ============================================================================
# _detect_pronoun_as_name — the core fix
# ============================================================================


class TestDetectPronounAsName:
    """Test pronoun detection before fact extraction."""

    # --- Should detect pronoun ---

    def test_minh_que_hai_phong(self):
        """The original bug: 'Minh que Hai Phong'."""
        result = _detect_pronoun_as_name("Minh que Hai Phong")
        assert result == "minh"

    def test_minh_la_sinh_vien(self):
        result = _detect_pronoun_as_name("Minh la sinh vien nam 3")
        assert result == "minh"

    def test_minh_cung_thich(self):
        result = _detect_pronoun_as_name("Minh cung thich choi bong da")
        assert result == "minh"

    def test_minh_dang_o_ky_tuc_xa(self):
        result = _detect_pronoun_as_name("Minh dang o ky tuc xa")
        assert result == "minh"

    def test_minh_hoc_truong_hang_hai(self):
        result = _detect_pronoun_as_name("Minh hoc truong Hang hai")
        assert result == "minh"

    def test_toi_la_sinh_vien(self):
        result = _detect_pronoun_as_name("Toi la sinh vien")
        assert result == "toi"

    def test_em_la_student(self):
        result = _detect_pronoun_as_name("Em la sinh vien nam 3")
        assert result == "em"

    def test_with_diacritics(self):
        """Should also work with diacritics present."""
        result = _detect_pronoun_as_name("Mình quê Hải Phòng")
        assert result == "minh"

    def test_minh_thich(self):
        result = _detect_pronoun_as_name("Minh thich mon Luat Hang hai")
        assert result == "minh"

    def test_minh_co_hobby(self):
        result = _detect_pronoun_as_name("Minh co so thich choi bong da")
        assert result == "minh"

    def test_minh_muon(self):
        result = _detect_pronoun_as_name("Minh muon lam Captain")
        assert result == "minh"

    # --- Should NOT detect pronoun (real names / non-pronoun patterns) ---

    def test_minh_la_hung_is_name_intro(self):
        """'Minh la Hung' — 'minh' is pronoun, detected. The real name is 'Hung'."""
        result = _detect_pronoun_as_name("Minh la Hung")
        assert result == "minh"

    def test_xin_chao_not_pronoun(self):
        """'Xin chao' starts with 'xin', not a pronoun."""
        result = _detect_pronoun_as_name("Xin chao, minh la Hung")
        assert result is None

    def test_rule_5_not_pronoun(self):
        """Maritime question — no pronoun at start."""
        result = _detect_pronoun_as_name("Rule 5 ve viec canh gioi")
        assert result is None

    def test_solas_not_pronoun(self):
        result = _detect_pronoun_as_name("SOLAS la gi?")
        assert result is None

    def test_empty_message(self):
        result = _detect_pronoun_as_name("")
        assert result is None

    def test_single_word_pronoun_no_context(self):
        """Single word 'Minh' without context verb → no detection."""
        result = _detect_pronoun_as_name("Minh")
        assert result is None

    def test_pronoun_needs_context_word(self):
        """'Minh ABC' where ABC is not a context word → no detection."""
        result = _detect_pronoun_as_name("Minh Khai")
        assert result is None

    def test_ban_co_nho(self):
        """'Ban co nho' — 'ban' is pronoun + 'co' is context."""
        result = _detect_pronoun_as_name("Ban co nho minh khong?")
        assert result == "ban"


# ============================================================================
# Enhanced prompt includes pronoun rules and warnings
# ============================================================================


def _make_extractor(llm=None):
    """Create FactExtractor with mocked dependencies."""
    from app.engine.semantic_memory.extraction import FactExtractor

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])
    mock_repo = MagicMock()
    return FactExtractor(
        embeddings=mock_embeddings,
        repository=mock_repo,
        llm=llm,
    )


class TestEnhancedPromptPronounRules:
    """Test that enhanced prompt includes Vietnamese pronoun awareness."""

    def test_prompt_contains_pronoun_rule(self):
        """Enhanced prompt must contain pronoun disambiguation rule."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Hello")
        assert "ĐẠI TỪ NHÂN XƯNG" in prompt

    def test_prompt_lists_common_pronouns(self):
        """Enhanced prompt must list minh/toi/em as pronouns."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Hello")
        assert "minh" in prompt.lower()
        assert "toi" in prompt.lower() or "tôi" in prompt.lower()

    def test_prompt_has_pronoun_example(self):
        """Enhanced prompt must have the 'Minh que Hai Phong' counter-example."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Hello")
        assert "Minh que Hai Phong" in prompt

    def test_pronoun_warning_injected_for_minh(self):
        """When message starts with pronoun, warning block is injected."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Minh que Hai Phong, hien dang o ky tuc xa")
        assert "CẢNH BÁO" in prompt
        assert "mình" in prompt
        assert "KHÔNG PHẢI tên người" in prompt

    def test_no_warning_for_normal_message(self):
        """When message doesn't start with pronoun, no warning injected."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("SOLAS la gi?")
        assert "CẢNH BÁO" not in prompt

    def test_no_warning_for_real_name_intro(self):
        """'Xin chao, minh la Hung' — starts with 'Xin', no warning."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Xin chao, minh la Hung")
        assert "CẢNH BÁO" not in prompt

    def test_prompt_requires_explicit_name_pattern(self):
        """Prompt instructs to only extract name with 'tên là X' / 'mình là X' patterns."""
        fe = _make_extractor()
        prompt = fe._build_enhanced_prompt("Hello")
        assert "tên là X" in prompt or "mình là X" in prompt


class TestLegacyPromptPronounRules:
    """Test that legacy prompt also has pronoun awareness."""

    def test_legacy_prompt_contains_pronoun_warning_for_minh(self):
        fe = _make_extractor()
        prompt = fe._build_legacy_prompt("Minh que Hai Phong")
        assert "WARNING" in prompt
        assert "pronoun" in prompt.lower()

    def test_legacy_prompt_no_warning_for_normal(self):
        fe = _make_extractor()
        prompt = fe._build_legacy_prompt("SOLAS la gi?")
        assert "WARNING" not in prompt

    def test_legacy_prompt_has_pronoun_examples(self):
        fe = _make_extractor()
        prompt = fe._build_legacy_prompt("Hello")
        assert "Vietnamese pronouns" in prompt or "mình" in prompt


# ============================================================================
# Integration: prompt + LLM should not extract pronoun as name
# ============================================================================


class TestPronounNotExtractedAsName:
    """Integration test: full extraction pipeline should not confuse pronouns."""

    @pytest.mark.asyncio
    async def test_minh_not_extracted_as_name(self):
        """When LLM returns pronoun as name, the prompt should have prevented it.

        This test verifies the prompt content that gets sent to LLM
        includes the pronoun warning for the bug-triggering message.
        """
        fe = _make_extractor(llm=AsyncMock())

        captured_prompt = None

        async def capture_prompt(prompt_text):
            nonlocal captured_prompt
            captured_prompt = prompt_text
            mock_response = MagicMock()
            mock_response.content = "[]"  # LLM correctly returns no name
            return mock_response

        fe._llm.ainvoke = capture_prompt

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("[]", None)):
            await fe.extract_user_facts("u1", "Minh que Hai Phong, hien dang o ky tuc xa")

        assert captured_prompt is not None
        # The prompt should warn about "minh" being a pronoun
        assert "CẢNH BÁO" in captured_prompt or "WARNING" in captured_prompt
        assert "mình" in captured_prompt
