"""
Sprint 219: "Học Tự Nhiên" — Adaptive Preference Learning Tests

Tests for:
- Feature flag gating (enable_adaptive_preferences)
- Enhanced extraction prompt contains behavioral inference rules when enabled
- Behavioral inference rules are absent when disabled
- Config default value
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.semantic_memory import FactType, UserFact


# ---------------------------------------------------------------------------
# Config flag tests
# ---------------------------------------------------------------------------

class TestAdaptivePreferencesConfigFlag:
    """Test enable_adaptive_preferences flag exists and defaults to False."""

    def test_flag_exists_in_settings(self):
        from app.core.config import Settings
        assert "enable_adaptive_preferences" in Settings.model_fields

    def test_flag_default_is_false(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_adaptive_preferences"].default
        assert default is False

    def test_flag_is_bool_type(self):
        from app.core.config import Settings
        field = Settings.model_fields["enable_adaptive_preferences"]
        assert field.annotation is bool


# ---------------------------------------------------------------------------
# FactExtractor — _build_adaptive_preference_block tests
# ---------------------------------------------------------------------------

class TestAdaptivePreferenceBlock:
    """Test _build_adaptive_preference_block() method."""

    def _make_extractor(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        embeddings = MagicMock()
        repository = MagicMock()
        return FactExtractor(embeddings=embeddings, repository=repository)

    def test_block_empty_when_flag_disabled(self):
        """When enable_adaptive_preferences=False, block should be empty string."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = False
            result = extractor._build_adaptive_preference_block()
            assert result == ""

    def test_block_contains_rules_when_flag_enabled(self):
        """When enable_adaptive_preferences=True, block should contain behavioral rules."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert len(result) > 0
            assert "SUY LUẬN HÀNH VI" in result

    def test_block_contains_learning_style_rule(self):
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "learning_style" in result

    def test_block_contains_weakness_rule(self):
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "weakness" in result

    def test_block_contains_strength_rule(self):
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "strength" in result

    def test_block_contains_preference_rule(self):
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "preference" in result

    def test_block_contains_example_inference(self):
        """Should contain example-based inference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "ví dụ" in result

    def test_block_contains_step_by_step_inference(self):
        """Should contain step-by-step inference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "từng bước" in result

    def test_block_contains_why_deep_inference(self):
        """Should contain deep 'why' questioning inference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "tại sao" in result

    def test_block_contains_concise_preference(self):
        """Should contain concise response preference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "ngắn gọn" in result

    def test_block_contains_detailed_preference(self):
        """Should contain detailed explanation preference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "chi tiết" in result

    def test_block_contains_confidence_guidance(self):
        """Should guide LLM to use lower confidence for behavioral inference."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "0.5-0.7" in result

    def test_block_contains_comparison_inference(self):
        """Should contain comparison/contrast inference rule."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_adaptive_preferences = True
            result = extractor._build_adaptive_preference_block()
            assert "so sánh" in result


# ---------------------------------------------------------------------------
# Enhanced prompt integration tests
# ---------------------------------------------------------------------------

class TestEnhancedPromptIntegration:
    """Test that _build_enhanced_prompt includes adaptive block when enabled."""

    def _make_extractor(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        embeddings = MagicMock()
        repository = MagicMock()
        return FactExtractor(embeddings=embeddings, repository=repository)

    def test_enhanced_prompt_includes_adaptive_block_when_enabled(self):
        """The enhanced prompt should contain behavioral rules when flag is on."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_enhanced_extraction = True
            mock_settings.enable_adaptive_preferences = True
            prompt = extractor._build_enhanced_prompt("Cho mình ví dụ về COLREGs")
            assert "SUY LUẬN HÀNH VI" in prompt

    def test_enhanced_prompt_excludes_adaptive_block_when_disabled(self):
        """The enhanced prompt should NOT contain behavioral rules when flag is off."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_enhanced_extraction = True
            mock_settings.enable_adaptive_preferences = False
            prompt = extractor._build_enhanced_prompt("Cho mình ví dụ về COLREGs")
            assert "SUY LUẬN HÀNH VI" not in prompt

    def test_enhanced_prompt_still_contains_base_rules(self):
        """Adaptive block should not break base extraction rules."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_enhanced_extraction = True
            mock_settings.enable_adaptive_preferences = True
            prompt = extractor._build_enhanced_prompt("Tên mình là Hùng")
            # Base rules should still be present
            assert "Personal Information Organizer" in prompt
            assert "fact_type" in prompt
            assert "6 NHÓM" in prompt

    def test_enhanced_prompt_with_existing_facts_and_adaptive(self):
        """Adaptive block works alongside existing facts context."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_enhanced_extraction = True
            mock_settings.enable_adaptive_preferences = True
            existing = {"name": "Hùng", "role": "sinh viên"}
            prompt = extractor._build_enhanced_prompt("Giải thích từng bước", existing)
            assert "SUY LUẬN HÀNH VI" in prompt
            assert "Hùng" in prompt  # existing facts still included

    def test_legacy_prompt_unaffected_by_adaptive_flag(self):
        """Legacy prompt path should not include adaptive rules regardless of flag."""
        extractor = self._make_extractor()
        with patch("app.engine.semantic_memory.extraction.settings") as mock_settings:
            mock_settings.enable_enhanced_extraction = False
            mock_settings.enable_adaptive_preferences = True
            prompt = extractor._build_fact_extraction_prompt("test message")
            # Legacy prompt does not call _build_adaptive_preference_block
            assert "SUY LUẬN HÀNH VI" not in prompt


# ---------------------------------------------------------------------------
# Fact type validation tests for adaptive fact types
# ---------------------------------------------------------------------------

class TestAdaptiveFactTypeValidation:
    """Verify that adaptive-inferred fact types are valid and storable."""

    def _make_extractor(self):
        from app.engine.semantic_memory.extraction import FactExtractor
        embeddings = MagicMock()
        repository = MagicMock()
        return FactExtractor(embeddings=embeddings, repository=repository)

    def test_learning_style_is_valid_fact_type(self):
        extractor = self._make_extractor()
        result = extractor._validate_fact_type("learning_style")
        assert result == "learning_style"

    def test_preference_is_valid_fact_type(self):
        extractor = self._make_extractor()
        result = extractor._validate_fact_type("preference")
        assert result == "preference"

    def test_weakness_is_valid_fact_type(self):
        extractor = self._make_extractor()
        result = extractor._validate_fact_type("weakness")
        assert result == "weakness"

    def test_strength_is_valid_fact_type(self):
        extractor = self._make_extractor()
        result = extractor._validate_fact_type("strength")
        assert result == "strength"

    def test_learning_style_enum_exists(self):
        """FactType enum should have learning_style value."""
        assert FactType("learning_style") == FactType.LEARNING_STYLE

    def test_preference_enum_exists(self):
        assert FactType("preference") == FactType.PREFERENCE

    def test_weakness_enum_exists(self):
        assert FactType("weakness") == FactType.WEAKNESS

    def test_strength_enum_exists(self):
        assert FactType("strength") == FactType.STRENGTH
