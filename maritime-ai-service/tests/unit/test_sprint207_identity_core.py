"""
Sprint 207: "Bản Ngã" — Identity Core (Self-Evolving Layer) tests.

Tests the Three-Layer Identity Layer 2:
    - IdentityInsight model + InsightCategory enum
    - IdentityCore.get_identity_context() (hot path)
    - IdentityCore.generate_self_insights() (cold path)
    - Soul Core drift validation
    - Prompt integration
    - Config gating

38 tests total.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.engine.living_agent.models import (
    IdentityInsight,
    InsightCategory,
    ReflectionEntry,
    SkillStatus,
    WiiiSkill,
)


# =============================================================================
# Helper: mock settings
# =============================================================================

def _mock_settings(**overrides):
    """Create a mock settings with defaults for identity core tests."""
    defaults = {
        "enable_living_agent": True,
        "enable_identity_core": True,
        "enable_narrative_context": False,
        "enable_natural_conversation": False,
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


# =============================================================================
# 1. IdentityInsight Model Tests
# =============================================================================

class TestIdentityInsightModel:
    """Test the IdentityInsight Pydantic model."""

    def test_create_basic_insight(self):
        insight = IdentityInsight(text="Mình giỏi COLREGs")
        assert insight.text == "Mình giỏi COLREGs"
        assert insight.category == InsightCategory.GROWTH
        assert insight.confidence == 0.5
        assert insight.source == "reflection"
        assert insight.validated is False
        assert insight.id is not None

    def test_all_categories(self):
        assert InsightCategory.STRENGTH == "strength"
        assert InsightCategory.PREFERENCE == "preference"
        assert InsightCategory.GROWTH == "growth"
        assert InsightCategory.RELATIONSHIP == "relationship"

    def test_custom_fields(self):
        insight = IdentityInsight(
            text="Mình thích dạy",
            category=InsightCategory.PREFERENCE,
            confidence=0.9,
            source="skill",
            validated=True,
        )
        assert insight.category == InsightCategory.PREFERENCE
        assert insight.confidence == 0.9
        assert insight.validated is True

    def test_confidence_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        insight = IdentityInsight(text="Test", confidence=0.0)
        assert insight.confidence == 0.0
        insight2 = IdentityInsight(text="Test", confidence=1.0)
        assert insight2.confidence == 1.0

    def test_created_at_default(self):
        before = datetime.now(timezone.utc)
        insight = IdentityInsight(text="Test")
        after = datetime.now(timezone.utc)
        assert before <= insight.created_at <= after


# =============================================================================
# 2. get_identity_context() — Hot Path Tests
# =============================================================================

class TestGetIdentityContext:
    """Test the synchronous hot-path prompt injection."""

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_disabled(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_identity_core=False)
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        assert core.get_identity_context() == ""

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_living_agent_disabled(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_living_agent=False)
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        assert core.get_identity_context() == ""

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_no_insights(self, mock_gs):
        mock_gs.return_value = _mock_settings()
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        assert core.get_identity_context() == ""

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_no_validated_insights(self, mock_gs):
        mock_gs.return_value = _mock_settings()
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [
            IdentityInsight(text="Unvalidated", validated=False),
        ]
        assert core.get_identity_context() == ""

    @patch("app.core.config.get_settings")
    def test_returns_context_with_validated_insights(self, mock_gs):
        mock_gs.return_value = _mock_settings()
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [
            IdentityInsight(text="Mình giỏi COLREGs", validated=True, confidence=0.8),
            IdentityInsight(text="Mình thích dạy", validated=True, confidence=0.7),
        ]
        ctx = core.get_identity_context()
        assert "BẢN NGÃ CỦA WIII" in ctx
        assert "Mình giỏi COLREGs" in ctx
        assert "Mình thích dạy" in ctx
        assert "HẾT BẢN NGÃ" in ctx

    @patch("app.core.config.get_settings")
    def test_top5_by_confidence(self, mock_gs):
        mock_gs.return_value = _mock_settings()
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [
            IdentityInsight(text=f"Insight {i}", validated=True, confidence=i * 0.1)
            for i in range(10)
        ]
        ctx = core.get_identity_context()
        # Should include highest confidence (0.9, 0.8, 0.7, 0.6, 0.5)
        assert "Insight 9" in ctx
        assert "Insight 5" in ctx
        # Should NOT include lowest
        assert "Insight 0" not in ctx

    @patch("app.core.config.get_settings")
    def test_exception_returns_empty(self, mock_gs):
        mock_gs.side_effect = RuntimeError("boom")
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        assert core.get_identity_context() == ""


# =============================================================================
# 3. generate_self_insights() — Cold Path Tests
# =============================================================================

class TestGenerateSelfInsights:
    """Test async insight generation from reflections."""

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    async def test_disabled_returns_empty(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_identity_core=False)
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()
        assert result == []

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    @patch("app.engine.living_agent.reflector.get_reflector")
    async def test_no_reflections_returns_empty(self, mock_refl, mock_gs):
        mock_gs.return_value = _mock_settings()
        refl = MagicMock()
        refl.get_recent_reflections = AsyncMock(return_value=[])
        mock_refl.return_value = refl

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()
        assert result == []

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    @patch("app.engine.living_agent.reflector.get_reflector")
    @patch("app.engine.living_agent.skill_builder.get_skill_builder")
    @patch("app.engine.living_agent.local_llm.get_local_llm")
    @patch("app.engine.living_agent.soul_loader.get_soul")
    async def test_successful_generation(self, mock_soul, mock_llm_fn, mock_sb, mock_refl, mock_gs):
        mock_gs.return_value = _mock_settings()

        # Reflection data
        refl = MagicMock()
        refl.get_recent_reflections = AsyncMock(return_value=[
            ReflectionEntry(content="Tuan nay minh hoc nhieu ve COLREGs. User khen minh giai thich ro."),
        ])
        mock_refl.return_value = refl

        # Skills
        builder = MagicMock()
        builder.get_all_skills.return_value = [
            WiiiSkill(skill_name="COLREGs", domain="maritime", status=SkillStatus.PRACTICING, confidence=0.7),
        ]
        mock_sb.return_value = builder

        # LLM
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=(
            "- Minh gioi giai thich COLREGs\n"
            "- Minh thich day hon tra cuu\n"
        ))
        mock_llm_fn.return_value = llm

        # Soul
        soul = MagicMock()
        soul.core_truths = ["Luon hoc hoi", "Giup nguoi dung"]
        soul.boundaries = []
        mock_soul.return_value = soul

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()

        assert len(result) == 2
        assert result[0].text == "Minh gioi giai thich COLREGs"
        assert result[0].validated is True
        assert result[1].text == "Minh thich day hon tra cuu"

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    @patch("app.engine.living_agent.reflector.get_reflector")
    @patch("app.engine.living_agent.local_llm.get_local_llm")
    @patch("app.engine.living_agent.soul_loader.get_soul")
    async def test_llm_failure_returns_empty(self, mock_soul, mock_llm_fn, mock_refl, mock_gs):
        mock_gs.return_value = _mock_settings()
        refl = MagicMock()
        refl.get_recent_reflections = AsyncMock(return_value=[
            ReflectionEntry(content="Some reflection"),
        ])
        mock_refl.return_value = refl
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_llm_fn.return_value = llm

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()
        assert result == []

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    @patch("app.engine.living_agent.reflector.get_reflector")
    @patch("app.engine.living_agent.skill_builder.get_skill_builder")
    @patch("app.engine.living_agent.local_llm.get_local_llm")
    @patch("app.engine.living_agent.soul_loader.get_soul")
    async def test_deduplication(self, mock_soul, mock_llm_fn, mock_sb, mock_refl, mock_gs):
        """Duplicate insights should not be added twice."""
        mock_gs.return_value = _mock_settings()
        refl = MagicMock()
        refl.get_recent_reflections = AsyncMock(return_value=[
            ReflectionEntry(content="Reflection text"),
        ])
        mock_refl.return_value = refl
        builder = MagicMock()
        builder.get_all_skills.return_value = []
        mock_sb.return_value = builder
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="- Minh gioi COLREGs\n- Minh gioi COLREGs\n")
        mock_llm_fn.return_value = llm
        soul = MagicMock()
        soul.core_truths = []
        soul.boundaries = []
        mock_soul.return_value = soul

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()
        assert len(result) == 1


# =============================================================================
# 4. Soul Core Drift Validation Tests
# =============================================================================

class TestDriftValidation:
    """Test that insights contradicting Soul Core are rejected."""

    def test_valid_insight_passes(self):
        from app.engine.living_agent.identity_core import _validate_against_soul
        assert _validate_against_soul("Minh gioi COLREGs", ["Luon hoc hoi"]) is True

    def test_drift_signal_rejected(self):
        from app.engine.living_agent.identity_core import _validate_against_soul
        assert _validate_against_soul("Minh khong phai AI ma la con nguoi", []) is False

    def test_hate_signal_rejected(self):
        from app.engine.living_agent.identity_core import _validate_against_soul
        assert _validate_against_soul("Minh ghet user", []) is False

    def test_refusal_signal_rejected(self):
        from app.engine.living_agent.identity_core import _validate_against_soul
        assert _validate_against_soul("Minh khong muon giup ai", []) is False

    def test_normal_text_passes(self):
        from app.engine.living_agent.identity_core import _validate_against_soul
        assert _validate_against_soul("Minh dang tien bo ve web search", ["Giup nguoi dung"]) is True


# =============================================================================
# 5. Insight Categorization Tests
# =============================================================================

class TestCategorization:
    """Test keyword-based insight categorization."""

    def test_strength_category(self):
        from app.engine.living_agent.identity_core import _categorize_insight
        assert _categorize_insight("Minh gioi giai thich") == InsightCategory.STRENGTH

    def test_preference_category(self):
        from app.engine.living_agent.identity_core import _categorize_insight
        assert _categorize_insight("Minh thich day hoc") == InsightCategory.PREFERENCE

    def test_relationship_category(self):
        from app.engine.living_agent.identity_core import _categorize_insight
        assert _categorize_insight("User thuong hoi minh ve hang hai") == InsightCategory.RELATIONSHIP

    def test_growth_default(self):
        from app.engine.living_agent.identity_core import _categorize_insight
        assert _categorize_insight("Dang tien bo ve ky nang moi") == InsightCategory.GROWTH


# =============================================================================
# 6. Helper Function Tests
# =============================================================================

class TestHelpers:
    """Test parsing and similarity helpers."""

    def test_parse_insight_lines(self):
        from app.engine.living_agent.identity_core import _parse_insight_lines
        content = "Some preamble\n- Insight one here\n- Insight two here\nNot a bullet"
        lines = _parse_insight_lines(content)
        assert len(lines) == 2
        assert lines[0] == "Insight one here"

    def test_parse_rejects_too_short(self):
        from app.engine.living_agent.identity_core import _parse_insight_lines
        lines = _parse_insight_lines("- Hi\n- This is long enough to pass")
        assert len(lines) == 1

    def test_has_similar_detects_overlap(self):
        from app.engine.living_agent.identity_core import _has_similar
        existing = {"minh gioi giai thich colregs"}
        assert _has_similar("minh gioi giai thich colregs tot", existing) is True

    def test_has_similar_no_overlap(self):
        from app.engine.living_agent.identity_core import _has_similar
        existing = {"minh gioi giai thich colregs"}
        assert _has_similar("user hay hoi ve hang hai", existing) is False


# =============================================================================
# 7. Prompt Integration Tests
# =============================================================================

class TestPromptIntegration:
    """Test that identity context is injected into system prompt."""

    @patch("app.core.config.get_settings")
    def test_prompt_loader_injects_identity(self, mock_gs):
        """Verify the prompt_loader section exists and runs."""
        mock_gs.return_value = _mock_settings(enable_identity_core=True)

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [
            IdentityInsight(text="Mình giỏi COLREGs", validated=True, confidence=0.8),
        ]
        ctx = core.get_identity_context()
        assert "BẢN NGÃ CỦA WIII" in ctx
        assert "Mình giỏi COLREGs" in ctx

    @patch("app.core.config.get_settings")
    def test_prompt_loader_skips_when_disabled(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_identity_core=False)

        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [
            IdentityInsight(text="Mình giỏi COLREGs", validated=True),
        ]
        assert core.get_identity_context() == ""


# =============================================================================
# 8. Config Gating Tests
# =============================================================================

class TestConfigGating:
    """Test feature flag gating behavior."""

    @patch("app.core.config.get_settings")
    def test_flag_exists_in_config(self, mock_gs):
        """Verify enable_identity_core flag exists with default=False."""
        from app.core.config import Settings
        assert "enable_identity_core" in Settings.model_fields
        # Check code default (not .env override)
        assert Settings.model_fields["enable_identity_core"].default is False

    @patch("app.core.config.get_settings")
    def test_hot_path_gated(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_identity_core=False)
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        core._insights = [IdentityInsight(text="Should not show", validated=True)]
        assert core.get_identity_context() == ""

    @pytest.mark.asyncio
    @patch("app.core.config.get_settings")
    async def test_cold_path_gated(self, mock_gs):
        mock_gs.return_value = _mock_settings(enable_identity_core=False)
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        result = await core.generate_self_insights()
        assert result == []

    @patch("app.core.config.get_settings")
    def test_living_agent_required(self, mock_gs):
        mock_gs.return_value = _mock_settings(
            enable_living_agent=False,
            enable_identity_core=True,
        )
        from app.engine.living_agent.identity_core import IdentityCore
        core = IdentityCore()
        assert core.get_identity_context() == ""

    def test_singleton_access(self):
        """Verify get_identity_core() returns singleton."""
        from app.engine.living_agent import identity_core as mod
        # Reset singleton
        old = mod._identity_core_instance
        mod._identity_core_instance = None
        try:
            c1 = mod.get_identity_core()
            c2 = mod.get_identity_core()
            assert c1 is c2
        finally:
            mod._identity_core_instance = old

    def test_model_in_init_exports(self):
        """Verify IdentityInsight and InsightCategory are exported."""
        from app.engine.living_agent import IdentityInsight as Exported
        from app.engine.living_agent import InsightCategory as ExportedCat
        assert Exported is IdentityInsight
        assert ExportedCat is InsightCategory
