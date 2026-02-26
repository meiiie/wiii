"""
Sprint 205: "Cầu Nối Kỹ Năng" — Skill ↔ Tool Bridge Tests

Tests that tool execution feeds back into skill lifecycle (SkillBuilder)
and execution metrics (SkillMetricsTracker), and that mastered skills
get boosted in IntelligentToolSelector.

SOTA 2026 Reference:
  - Voyager: Mastered skills become priority tools
  - OpenClaw: Tool execution → skill advancement feedback loop

38 tests across 7 groups:
1. record_tool_usage → SkillMetricsTracker (6 tests)
2. record_tool_usage → SkillBuilder bridge (6 tests)
3. Mastered skill auto-registration (4 tests)
4. get_mastery_score (5 tests)
5. get_mastered_tools (4 tests)
6. IntelligentToolSelector mastery boost (6 tests)
7. Config flag gating + regression (7 tests)
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

import app.engine.skills.skill_tool_bridge as bridge_module


# =============================================================================
# Helpers
# =============================================================================


def _mock_settings(**overrides):
    """Create a mock Settings with Sprint 205 defaults + overrides."""
    defaults = {
        "enable_skill_metrics": False,
        "enable_skill_tool_bridge": False,
        "enable_living_agent": False,
        "enable_intelligent_tool_selection": False,
        "enable_unified_skill_index": False,
        "tool_selection_strategy": "hybrid",
        "tool_selection_max_candidates": 15,
        "living_agent_max_skills_per_week": 10,
        "default_domain": "maritime",
        "app_name": "Wiii",
    }
    defaults.update(overrides)
    s = MagicMock()
    s.__class__ = type("MockSettings", (), {})
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


@pytest.fixture(autouse=True)
def reset_bridge_state():
    """Reset module-level state before each test."""
    bridge_module._registered_mastered.clear()
    yield
    bridge_module._registered_mastered.clear()


# =============================================================================
# Group 1: record_tool_usage → SkillMetricsTracker (6 tests)
# =============================================================================


class TestMetricsRecording:
    """Tool usage feeds into SkillMetricsTracker when enable_skill_metrics=True."""

    @patch("app.core.config.get_settings")
    def test_metrics_recorded_when_enabled(self, mock_gs):
        """Metrics tracker receives record_invocation when flag on."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True)
        mock_tracker = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            bridge_module.record_tool_usage("tool_web_search", success=True, latency_ms=200)

        mock_tracker.record_invocation.assert_called_once()
        call_kwargs = mock_tracker.record_invocation.call_args
        assert call_kwargs[1]["skill_id"] == "tool:tool_web_search"
        assert call_kwargs[1]["success"] is True
        assert call_kwargs[1]["latency_ms"] == 200

    @patch("app.core.config.get_settings")
    def test_metrics_skipped_when_disabled(self, mock_gs):
        """Metrics tracker NOT called when enable_skill_metrics=False."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=False)
        mock_tracker = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            bridge_module.record_tool_usage("tool_web_search", success=True)

        mock_tracker.record_invocation.assert_not_called()

    @patch("app.core.config.get_settings")
    def test_metrics_includes_query_snippet(self, mock_gs):
        """Query snippet is truncated to 100 chars."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True)
        mock_tracker = MagicMock()
        long_query = "x" * 200

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            bridge_module.record_tool_usage("tool_web_search", success=True, query_snippet=long_query)

        call_kwargs = mock_tracker.record_invocation.call_args[1]
        assert len(call_kwargs["query_snippet"]) == 100

    @patch("app.core.config.get_settings")
    def test_metrics_includes_error_message(self, mock_gs):
        """Error message is passed to tracker."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True)
        mock_tracker = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            bridge_module.record_tool_usage("tool_web_search", success=False, error_message="timeout")

        call_kwargs = mock_tracker.record_invocation.call_args[1]
        assert call_kwargs["error_message"] == "timeout"
        assert call_kwargs["success"] is False

    @patch("app.core.config.get_settings")
    def test_metrics_includes_org_id(self, mock_gs):
        """Organization ID is passed through."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True)
        mock_tracker = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            bridge_module.record_tool_usage("tool_web_search", success=True, organization_id="org-123")

        call_kwargs = mock_tracker.record_invocation.call_args[1]
        assert call_kwargs["organization_id"] == "org-123"

    @patch("app.core.config.get_settings")
    def test_metrics_failure_does_not_raise(self, mock_gs):
        """Metrics recording failure is silently caught."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True)

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", side_effect=RuntimeError("boom")):
            # Should not raise
            bridge_module.record_tool_usage("tool_web_search", success=True)


# =============================================================================
# Group 2: record_tool_usage → SkillBuilder Bridge (6 tests)
# =============================================================================


class TestSkillBuilderBridge:
    """Tool usage feeds into SkillBuilder when both flags enabled."""

    @patch("app.core.config.get_settings")
    def test_skill_usage_recorded(self, mock_gs):
        """SkillBuilder.record_usage called for mapped tools."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = MagicMock(
            status=MagicMock(value="practicing"), confidence=0.5
        )

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_builder.record_usage.assert_called_once_with("maritime_navigation", success=True)

    @patch("app.core.config.get_settings")
    def test_skill_auto_discovered(self, mock_gs):
        """Unknown skill auto-discovered via SkillBuilder.discover()."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.side_effect = [None, None]  # Not found first time, nor after

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            bridge_module.record_tool_usage("tool_search_news", success=True)

        mock_builder.discover.assert_called_once_with(
            skill_name="news_analysis", domain="news", source="tool:tool_search_news"
        )

    @patch("app.core.config.get_settings")
    def test_no_bridge_when_living_agent_disabled(self, mock_gs):
        """Bridge skipped when enable_living_agent=False."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=False
        )
        mock_builder = MagicMock()

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_builder.record_usage.assert_not_called()

    @patch("app.core.config.get_settings")
    def test_no_bridge_for_utility_tools(self, mock_gs):
        """Utility tools (None in _TOOL_SKILL_MAP) skip bridge."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_builder = MagicMock()

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            bridge_module.record_tool_usage("tool_current_datetime", success=True)

        mock_builder.record_usage.assert_not_called()

    @patch("app.core.config.get_settings")
    def test_bridge_failure_does_not_raise(self, mock_gs):
        """SkillBuilder errors are silently caught."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", side_effect=RuntimeError("db down")):
            # Should not raise
            bridge_module.record_tool_usage("tool_search_maritime", success=True)

    @patch("app.core.config.get_settings")
    def test_failed_tool_records_failure(self, mock_gs):
        """Failed tool invocations pass success=False to SkillBuilder."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = MagicMock(
            status=MagicMock(value="learning"), confidence=0.3
        )

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            bridge_module.record_tool_usage("tool_web_search", success=False)

        mock_builder.record_usage.assert_called_once_with("web_research", success=False)


# =============================================================================
# Group 3: Mastered Skill Auto-Registration (4 tests)
# =============================================================================


class TestMasteredSkillRegistration:
    """When skill reaches MASTERED, auto-register as priority tool."""

    @patch("app.core.config.get_settings")
    def test_mastered_triggers_registration(self, mock_gs):
        """Skill reaching MASTERED triggers _register_mastered_skill."""
        from app.engine.living_agent.models import SkillStatus

        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True,
            enable_skill_metrics=True,
        )
        mock_skill_pre = MagicMock(status=SkillStatus.EVALUATING, confidence=0.7)
        mock_skill_post = MagicMock(status=SkillStatus.MASTERED, confidence=0.85)
        mock_builder = MagicMock()
        mock_builder._find_by_name.side_effect = [mock_skill_pre, mock_skill_post]

        mock_tracker = MagicMock()

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        # Should have called record_invocation for metrics + mastery bonus
        assert mock_tracker.record_invocation.call_count >= 1
        assert "maritime_navigation" in bridge_module._registered_mastered

    @patch("app.core.config.get_settings")
    def test_no_duplicate_registration(self, mock_gs):
        """Mastered skill only registered once."""
        from app.engine.living_agent.models import SkillStatus

        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True,
            enable_skill_metrics=True,
        )
        bridge_module._registered_mastered.add("maritime_navigation")

        mock_skill = MagicMock(status=SkillStatus.MASTERED, confidence=0.9)
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill

        mock_tracker = MagicMock()

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        # Only the normal metrics recording, NOT a mastery bonus
        mastery_calls = [c for c in mock_tracker.record_invocation.call_args_list
                         if "[MASTERY]" in str(c)]
        assert len(mastery_calls) == 0

    def test_is_mastered_true(self):
        """_is_mastered returns True for MASTERED skills."""
        from app.engine.living_agent.models import SkillStatus
        skill = MagicMock(status=SkillStatus.MASTERED)
        assert bridge_module._is_mastered(skill) is True

    def test_is_mastered_false(self):
        """_is_mastered returns False for non-MASTERED skills."""
        from app.engine.living_agent.models import SkillStatus
        skill = MagicMock(status=SkillStatus.LEARNING)
        assert bridge_module._is_mastered(skill) is False


# =============================================================================
# Group 4: get_mastery_score (5 tests)
# =============================================================================


class TestGetMasteryScore:
    """get_mastery_score returns skill confidence for IntelligentToolSelector."""

    @patch("app.core.config.get_settings")
    def test_returns_confidence(self, mock_gs):
        """Returns skill.confidence when bridge enabled."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_skill = MagicMock(confidence=0.75)
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = mock_skill

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            score = bridge_module.get_mastery_score("tool_search_maritime")

        assert score == 0.75

    @patch("app.core.config.get_settings")
    def test_returns_zero_when_bridge_disabled(self, mock_gs):
        """Returns 0.0 when enable_skill_tool_bridge=False."""
        mock_gs.return_value = _mock_settings(enable_skill_tool_bridge=False)
        assert bridge_module.get_mastery_score("tool_search_maritime") == 0.0

    @patch("app.core.config.get_settings")
    def test_returns_zero_when_living_agent_disabled(self, mock_gs):
        """Returns 0.0 when enable_living_agent=False."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=False
        )
        assert bridge_module.get_mastery_score("tool_search_maritime") == 0.0

    @patch("app.core.config.get_settings")
    def test_returns_zero_for_unmapped_tool(self, mock_gs):
        """Returns 0.0 for tools not in _TOOL_SKILL_MAP."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        assert bridge_module.get_mastery_score("tool_unknown_thing") == 0.0

    @patch("app.core.config.get_settings")
    def test_returns_zero_for_utility_tool(self, mock_gs):
        """Returns 0.0 for utility tools (None mapping)."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        assert bridge_module.get_mastery_score("tool_current_datetime") == 0.0


# =============================================================================
# Group 5: get_mastered_tools (4 tests)
# =============================================================================


class TestGetMasteredTools:
    """get_mastered_tools returns tool names whose skills are MASTERED."""

    @patch("app.core.config.get_settings")
    def test_returns_tools_for_mastered_skills(self, mock_gs):
        """Returns tool names mapped to mastered skill domains."""
        from app.engine.living_agent.models import SkillStatus, WiiiSkill

        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_skill = MagicMock(skill_name="maritime_navigation", status=SkillStatus.MASTERED)
        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = [mock_skill]

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            tools = bridge_module.get_mastered_tools()

        # Both tool_maritime_search and tool_search_maritime map to maritime_navigation
        assert "tool_maritime_search" in tools
        assert "tool_search_maritime" in tools

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_disabled(self, mock_gs):
        """Returns [] when bridge disabled."""
        mock_gs.return_value = _mock_settings(enable_skill_tool_bridge=False)
        assert bridge_module.get_mastered_tools() == []

    @patch("app.core.config.get_settings")
    def test_returns_empty_when_no_mastered(self, mock_gs):
        """Returns [] when no skills are MASTERED."""
        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = []

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            tools = bridge_module.get_mastered_tools()

        assert tools == []

    @patch("app.core.config.get_settings")
    def test_multiple_mastered_domains(self, mock_gs):
        """Returns tools from multiple mastered domains."""
        from app.engine.living_agent.models import SkillStatus

        mock_gs.return_value = _mock_settings(
            enable_skill_tool_bridge=True, enable_living_agent=True
        )
        mock_skills = [
            MagicMock(skill_name="maritime_navigation", status=SkillStatus.MASTERED),
            MagicMock(skill_name="web_research", status=SkillStatus.MASTERED),
        ]
        mock_builder = MagicMock()
        mock_builder.get_all_skills.return_value = mock_skills

        with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
            tools = bridge_module.get_mastered_tools()

        assert "tool_web_search" in tools
        assert "tool_search_maritime" in tools


# =============================================================================
# Group 6: IntelligentToolSelector Mastery Boost (6 tests)
# =============================================================================


class TestSelectorMasteryBoost:
    """IntelligentToolSelector Step 4 includes mastery score."""

    def _make_selector(self):
        """Create IntelligentToolSelector instance."""
        from app.engine.skills.skill_recommender import IntelligentToolSelector
        return IntelligentToolSelector()

    def test_mastery_boost_applied(self):
        """Tools with mastery > 0 get score boost."""
        from app.engine.skills.skill_recommender import ToolRecommendation

        selector = self._make_selector()
        pool = [
            ToolRecommendation(tool_name="tool_search_maritime", score=0.5, reason="test"),
            ToolRecommendation(tool_name="tool_web_search", score=0.5, reason="test"),
        ]

        mock_tracker = MagicMock()
        mock_tracker.get_metrics.return_value = None  # No metrics

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch.object(selector, "_get_mastery_boost", side_effect=[0.8, 0.0]):
                result = selector._step4_metrics_rerank(pool)

        # Maritime should be boosted
        assert result[0].tool_name == "tool_search_maritime"
        assert result[0].score > result[1].score
        assert "mastery" in result[0].reason

    def test_no_mastery_boost_when_zero(self):
        """Tools with mastery=0 get no boost."""
        from app.engine.skills.skill_recommender import ToolRecommendation

        selector = self._make_selector()
        pool = [ToolRecommendation(tool_name="tool_web_search", score=0.5, reason="test")]

        mock_tracker = MagicMock()
        mock_tracker.get_metrics.return_value = None

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch.object(selector, "_get_mastery_boost", return_value=0.0):
                result = selector._step4_metrics_rerank(pool)

        assert result[0].score == 0.5  # Unchanged
        assert "mastery" not in result[0].reason

    def test_mastery_boost_combined_with_metrics(self):
        """Mastery adds on top of existing metrics score."""
        from app.engine.skills.skill_recommender import ToolRecommendation
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        selector = self._make_selector()
        pool = [ToolRecommendation(tool_name="tool_search_maritime", score=0.5, reason="test")]

        mock_metrics = MagicMock()
        mock_metrics.total_invocations = 10
        mock_metrics.success_rate = 0.9
        mock_metrics.avg_latency_ms = 200.0
        mock_metrics.avg_cost_per_invocation = 0.001
        mock_metrics.cost_estimate_usd = 0.01

        mock_tracker = MagicMock()
        mock_tracker.get_metrics.return_value = mock_metrics

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch.object(selector, "_get_mastery_boost", return_value=0.9):
                result = selector._step4_metrics_rerank(pool)

        # Should have both metrics and mastery in reason
        assert "metrics" in result[0].reason
        assert "mastery" in result[0].reason
        assert result[0].score > 0.5  # Boosted above initial

    def test_get_mastery_boost_uses_bridge(self):
        """_get_mastery_boost delegates to skill_tool_bridge.get_mastery_score."""
        from app.engine.skills.skill_recommender import IntelligentToolSelector

        with patch("app.engine.skills.skill_tool_bridge.get_mastery_score", return_value=0.75):
            score = IntelligentToolSelector._get_mastery_boost("tool_search_maritime")

        assert score == 0.75

    def test_get_mastery_boost_handles_import_error(self):
        """_get_mastery_boost returns 0.0 on import error."""
        from app.engine.skills.skill_recommender import IntelligentToolSelector

        with patch("app.engine.skills.skill_tool_bridge.get_mastery_score", side_effect=ImportError):
            score = IntelligentToolSelector._get_mastery_boost("tool_search_maritime")

        assert score == 0.0

    def test_mastery_only_pool_ranked(self):
        """Pool with only mastery (no metrics) is properly ranked."""
        from app.engine.skills.skill_recommender import ToolRecommendation

        selector = self._make_selector()
        pool = [
            ToolRecommendation(tool_name="tool_search_legal", score=0.3, reason="cat"),
            ToolRecommendation(tool_name="tool_search_maritime", score=0.3, reason="cat"),
            ToolRecommendation(tool_name="tool_web_search", score=0.3, reason="cat"),
        ]

        mock_tracker = MagicMock()
        mock_tracker.get_metrics.return_value = None

        # Maritime has high mastery, others low or zero
        mastery_map = {
            "tool_search_maritime": 0.95,
            "tool_search_legal": 0.2,
            "tool_web_search": 0.0,
        }

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch.object(selector, "_get_mastery_boost", side_effect=lambda t: mastery_map.get(t, 0.0)):
                result = selector._step4_metrics_rerank(pool)

        # Maritime should rank first
        assert result[0].tool_name == "tool_search_maritime"
        assert result[-1].tool_name == "tool_web_search"


# =============================================================================
# Group 7: Config Flag Gating + Regression (7 tests)
# =============================================================================


class TestConfigGating:
    """Verify feature flags correctly gate all Sprint 205 functionality."""

    @patch("app.core.config.get_settings")
    def test_both_loops_fire_when_all_enabled(self, mock_gs):
        """Both metrics + skill bridge fire when all flags enabled."""
        mock_gs.return_value = _mock_settings(
            enable_skill_metrics=True,
            enable_skill_tool_bridge=True,
            enable_living_agent=True,
        )
        mock_tracker = MagicMock()
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = MagicMock(
            status=MagicMock(value="practicing"), confidence=0.5
        )

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_tracker.record_invocation.assert_called_once()
        mock_builder.record_usage.assert_called_once()

    @patch("app.core.config.get_settings")
    def test_no_loops_when_all_disabled(self, mock_gs):
        """Neither loop fires when flags are off (default state)."""
        mock_gs.return_value = _mock_settings()
        mock_tracker = MagicMock()
        mock_builder = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_tracker.record_invocation.assert_not_called()
        mock_builder.record_usage.assert_not_called()

    @patch("app.core.config.get_settings")
    def test_metrics_only_mode(self, mock_gs):
        """Only metrics fire when enable_skill_metrics=True but bridge=False."""
        mock_gs.return_value = _mock_settings(enable_skill_metrics=True, enable_skill_tool_bridge=False)
        mock_tracker = MagicMock()
        mock_builder = MagicMock()

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_tracker.record_invocation.assert_called_once()
        mock_builder.record_usage.assert_not_called()

    @patch("app.core.config.get_settings")
    def test_bridge_only_mode(self, mock_gs):
        """Only bridge fires when enable_skill_tool_bridge=True but metrics=False."""
        mock_gs.return_value = _mock_settings(
            enable_skill_metrics=False, enable_skill_tool_bridge=True,
            enable_living_agent=True,
        )
        mock_tracker = MagicMock()
        mock_builder = MagicMock()
        mock_builder._find_by_name.return_value = MagicMock(
            status=MagicMock(value="practicing"), confidence=0.5
        )

        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", return_value=mock_tracker):
            with patch("app.engine.living_agent.skill_builder.get_skill_builder", return_value=mock_builder):
                bridge_module.record_tool_usage("tool_search_maritime", success=True)

        mock_tracker.record_invocation.assert_not_called()
        mock_builder.record_usage.assert_called_once()

    def test_tool_skill_map_completeness(self):
        """_TOOL_SKILL_MAP covers all expected core tools."""
        expected_tools = [
            "tool_knowledge_search", "tool_maritime_search", "tool_search_maritime",
            "tool_web_search", "tool_search_news", "tool_search_legal",
            "tool_calculator", "tool_current_datetime", "tool_think",
            "tool_report_progress", "tool_character_note",
        ]
        for tool in expected_tools:
            assert tool in bridge_module._TOOL_SKILL_MAP

    def test_infer_domain_maritime(self):
        """Maritime tools infer maritime domain."""
        assert bridge_module._infer_domain("tool_search_maritime") == "maritime"

    def test_infer_domain_fallback(self):
        """Unknown tools infer general domain."""
        assert bridge_module._infer_domain("tool_something_else") == "general"


# =============================================================================
# Group 8: Config presence (1 test)
# =============================================================================


class TestConfigPresence:
    """Verify Sprint 205 config field exists."""

    def test_enable_skill_tool_bridge_in_config(self):
        """enable_skill_tool_bridge field exists in Settings."""
        from app.core.config import Settings
        assert hasattr(Settings, "model_fields") or hasattr(Settings, "__fields__")
        # Check field exists via Pydantic
        fields = Settings.model_fields if hasattr(Settings, "model_fields") else Settings.__fields__
        assert "enable_skill_tool_bridge" in fields
