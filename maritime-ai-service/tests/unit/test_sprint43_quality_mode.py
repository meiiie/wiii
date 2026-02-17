"""
Tests for Sprint 43: Quality Mode Presets coverage.

Tests RAG quality mode configuration and preset selection.
"""

import pytest
from unittest.mock import patch


# ============================================================================
# QualityModePreset
# ============================================================================


class TestQualityModePreset:
    """Test preset data structure."""

    def test_speed_preset(self):
        from app.engine.agentic_rag.quality_mode import QUALITY_PRESETS
        speed = QUALITY_PRESETS["speed"]
        assert speed.name == "speed"
        assert speed.max_iterations == 1
        assert speed.enable_reflection is False
        assert speed.enable_verification is False
        assert speed.early_exit is True
        assert speed.thinking_level == "low"

    def test_balanced_preset(self):
        from app.engine.agentic_rag.quality_mode import QUALITY_PRESETS
        balanced = QUALITY_PRESETS["balanced"]
        assert balanced.name == "balanced"
        assert balanced.max_iterations == 2
        assert balanced.enable_reflection is True
        assert balanced.enable_verification is True
        assert balanced.confidence_high == 0.85

    def test_quality_preset(self):
        from app.engine.agentic_rag.quality_mode import QUALITY_PRESETS
        quality = QUALITY_PRESETS["quality"]
        assert quality.name == "quality"
        assert quality.max_iterations == 3
        assert quality.enable_reflection is True
        assert quality.early_exit is False
        assert quality.thinking_level == "high"
        assert quality.confidence_high == 0.92

    def test_all_presets_have_descriptions(self):
        from app.engine.agentic_rag.quality_mode import QUALITY_PRESETS
        for name, preset in QUALITY_PRESETS.items():
            assert preset.description, f"Preset '{name}' has no description"

    def test_confidence_ordering(self):
        """Speed < balanced < quality for confidence thresholds."""
        from app.engine.agentic_rag.quality_mode import QUALITY_PRESETS
        assert QUALITY_PRESETS["speed"].confidence_high < QUALITY_PRESETS["balanced"].confidence_high
        assert QUALITY_PRESETS["balanced"].confidence_high < QUALITY_PRESETS["quality"].confidence_high


# ============================================================================
# get_quality_preset
# ============================================================================


class TestGetQualityPreset:
    """Test preset selection."""

    def test_get_speed(self):
        from app.engine.agentic_rag.quality_mode import get_quality_preset
        preset = get_quality_preset("speed")
        assert preset.name == "speed"

    def test_get_balanced(self):
        from app.engine.agentic_rag.quality_mode import get_quality_preset
        preset = get_quality_preset("balanced")
        assert preset.name == "balanced"

    def test_get_quality(self):
        from app.engine.agentic_rag.quality_mode import get_quality_preset
        preset = get_quality_preset("quality")
        assert preset.name == "quality"

    def test_unknown_mode_falls_back(self):
        """Unknown mode falls back to balanced."""
        from app.engine.agentic_rag.quality_mode import get_quality_preset
        preset = get_quality_preset("nonexistent")
        assert preset.name == "balanced"

    def test_none_uses_settings(self):
        """None uses settings.rag_quality_mode."""
        with patch("app.engine.agentic_rag.quality_mode.settings") as mock_settings:
            mock_settings.rag_quality_mode = "quality"
            from app.engine.agentic_rag.quality_mode import get_quality_preset
            preset = get_quality_preset(None)
            assert preset.name == "quality"
