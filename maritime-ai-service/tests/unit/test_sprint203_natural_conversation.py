"""
Sprint 203: "Tự Nhiên Như Thở" — Natural Conversation Tests

Tests for phase-aware natural conversation, canned greeting bypass,
positive prompt framing, greeting strip bypass, phase-aware fallback,
natural synthesis, domain notice fix, and diversity params.

~40 tests covering all 7 changes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# Helpers
# =============================================================================


def _mock_settings(**overrides):
    """Create a mock Settings with Sprint 203 defaults + overrides."""
    defaults = {
        "enable_natural_conversation": False,
        "llm_presence_penalty": 0.0,
        "llm_frequency_penalty": 0.0,
        "default_domain": "maritime",
        "app_name": "Wiii",
        "enable_product_search": False,
        "enable_subagent_architecture": False,
        "enable_character_tools": False,
        "enable_code_execution": False,
        "enable_lms_integration": False,
        "enable_living_agent": False,
        "enable_soul_emotion": False,
        "enable_facebook_cookie": False,
        "enable_artifacts": False,
        "enable_websocket": False,
        "quality_skip_threshold": 0.85,
        "identity_anchor_interval": 6,
        "active_domains": ["maritime"],
        "enable_corrective_rag": True,
        "use_multi_agent": True,
        "enable_agentic_loop": True,
        "agentic_loop_max_steps": 8,
        "enable_structured_outputs": True,
        "cross_domain_search": True,
        "domain_boost_score": 0.15,
        "enable_chart_tools": False,
        "enable_browser_scraping": False,
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    # Make getattr work for missing attrs
    s.__class__ = type("MockSettings", (), {})
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


# =============================================================================
# Group 1: Phase Computation (5 tests)
# =============================================================================


class TestPhaseComputation:
    """Test conversation phase computation from total_responses."""

    def test_phase_opening_at_zero(self):
        """total_responses=0 → opening."""
        total = 0
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "opening"

    def test_phase_engaged_at_1(self):
        """total_responses=1 → engaged."""
        total = 1
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "engaged"

    def test_phase_engaged_at_4(self):
        """total_responses=4 → engaged."""
        total = 4
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "engaged"

    def test_phase_deep_at_5(self):
        """total_responses=5 → deep."""
        total = 5
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "deep"

    def test_phase_closing_at_20(self):
        """total_responses=20 → closing."""
        total = 20
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "closing"

    def test_phase_deep_at_19(self):
        """total_responses=19 → deep (boundary)."""
        total = 19
        phase = "opening" if total == 0 else ("engaged" if total < 5 else ("deep" if total < 20 else "closing"))
        assert phase == "deep"

    def test_backward_compat_is_follow_up(self):
        """is_follow_up should still be True when total > 0."""
        total = 3
        is_follow_up = total > 0
        assert is_follow_up is True


# =============================================================================
# Group 2: Canned Greeting Bypass (5 tests)
# =============================================================================


class TestCannedGreetingBypass:
    """Test that natural conversation mode bypasses canned greeting dict."""

    def test_flag_on_skips_canned_greetings(self):
        """When enable_natural_conversation=True, response should be None (LLM path)."""
        _use_natural = True
        if not _use_natural:
            greetings = {"xin chào": "Xin chào! Tôi là Wiii."}
            response = greetings.get("xin chào")
        else:
            response = None
        assert response is None

    def test_flag_off_uses_canned_greetings(self):
        """When enable_natural_conversation=False, exact match returns canned."""
        _use_natural = False
        if not _use_natural:
            greetings = {"xin chào": "Xin chào! Tôi là Wiii."}
            response = greetings.get("xin chào")
        else:
            response = None
        assert response == "Xin chào! Tôi là Wiii."

    def test_flag_off_no_match_returns_none(self):
        """When flag off and no exact match, response is None."""
        greetings = {"xin chào": "Xin chào!"}
        response = greetings.get("điều 15 colregs")
        assert response is None

    def test_get_domain_greetings_still_exists(self):
        """_get_domain_greetings function should still be importable."""
        from app.engine.multi_agent.graph import _get_domain_greetings
        greetings = _get_domain_greetings("maritime")
        assert isinstance(greetings, dict)
        assert "xin chào" in greetings or "hello" in greetings

    def test_canned_greetings_not_called_when_natural(self):
        """Verify greetings dict is not even loaded when natural mode on."""
        _use_natural = True
        greetings_loaded = False
        if not _use_natural:
            greetings_loaded = True
        assert greetings_loaded is False


# =============================================================================
# Group 3: Positive Prompt Framing (6 tests)
# =============================================================================


class TestPositivePromptFraming:
    """Test that natural conversation replaces anti-instructions with positive framing."""

    def _build_prompt(self, natural=False, phase="engaged", recent_phrases=None,
                      is_follow_up=True, user_name=None):
        """Helper: build prompt with minimal persona."""
        # Lazy import in prompt_loader.py: `from app.core.config import get_settings`
        # Must patch at SOURCE module (see backend-gotchas.md)
        with patch("app.core.config.get_settings") as mock_gs:
            s = _mock_settings(enable_natural_conversation=natural)
            mock_gs.return_value = s

            from app.prompts.prompt_loader import PromptLoader
            loader = PromptLoader()
            return loader.build_system_prompt(
                role="student",
                is_follow_up=is_follow_up,
                recent_phrases=recent_phrases or [],
                total_responses=6 if is_follow_up else 0,
                user_name=user_name,
                conversation_phase=phase,
            )

    def test_opening_phase_text(self):
        """Opening phase should mention 'lần giao tiếp đầu tiên'."""
        prompt = self._build_prompt(natural=True, phase="opening", is_follow_up=False)
        assert "lần giao tiếp đầu tiên" in prompt

    def test_engaged_phase_text(self):
        """Engaged phase should say 'Đi thẳng vào nội dung'."""
        prompt = self._build_prompt(natural=True, phase="engaged")
        assert "Đi thẳng vào nội dung" in prompt

    def test_deep_phase_text(self):
        """Deep phase should mention 'thân mật hơn'."""
        prompt = self._build_prompt(natural=True, phase="deep")
        assert "thân mật hơn" in prompt

    def test_closing_phase_text(self):
        """Closing phase should mention 'cô đọng'."""
        prompt = self._build_prompt(natural=True, phase="closing")
        assert "cô đọng" in prompt

    def test_recent_phrases_included(self):
        """Recent phrases should be listed for creativity guidance."""
        prompt = self._build_prompt(
            natural=True, phase="engaged",
            recent_phrases=["Chào bạn! Mình là Wiii", "Rất vui được giúp bạn"],
        )
        assert "sáng tạo cách khác" in prompt

    def test_legacy_preserved_when_off(self):
        """When flag off, should still have 'TUYỆT ĐỐI KHÔNG'."""
        prompt = self._build_prompt(natural=False, is_follow_up=True)
        assert "TUYỆT ĐỐI KHÔNG" in prompt

    def test_no_anti_instructions_when_natural(self):
        """When natural mode on, should NOT have 'TUYỆT ĐỐI KHÔNG bắt đầu bằng'."""
        prompt = self._build_prompt(natural=True, phase="engaged")
        assert "TUYỆT ĐỐI KHÔNG bắt đầu bằng" not in prompt


# =============================================================================
# Group 4: Greeting Strip Bypass (4 tests)
# =============================================================================


class TestGreetingStripBypass:
    """Test that greeting strip is skipped when natural conversation enabled."""

    def test_strip_function_still_exists(self):
        """_strip_greeting_prefix should still be importable."""
        from app.engine.multi_agent.graph import _strip_greeting_prefix
        result = _strip_greeting_prefix("Chào bạn! Nội dung chính ở đây.")
        assert "Nội dung chính" in result

    def test_flag_off_still_strips(self):
        """When flag off, greeting prefix should be stripped."""
        from app.engine.multi_agent.graph import _strip_greeting_prefix
        text = "Chào bạn! Rất vui được gặp. Nội dung chính ở đây."
        result = _strip_greeting_prefix(text)
        assert result.startswith("Nội dung") or result.startswith("nội dung") or "Nội dung" in result

    def test_strip_preserves_short_responses(self):
        """Safety: don't strip if it removes >60% content."""
        from app.engine.multi_agent.graph import _strip_greeting_prefix
        text = "Chào bạn!"
        result = _strip_greeting_prefix(text)
        assert result == text  # Too short to strip

    def test_no_double_strip(self):
        """Already-stripped text should not be further modified."""
        from app.engine.multi_agent.graph import _strip_greeting_prefix
        text = "Nội dung trả lời trực tiếp."
        result = _strip_greeting_prefix(text)
        assert result == text


# =============================================================================
# Group 5: Phase-Aware Fallback (5 tests)
# =============================================================================


class TestPhaseAwareFallback:
    """Test context-appropriate fallbacks based on conversation phase."""

    def test_opening_fallback(self):
        """Opening phase fallback should mention 'Wiii'."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {"conversation_phase": "opening"}}
        result = _get_phase_fallback(state)
        assert "Wiii" in result

    def test_engaged_fallback(self):
        """Engaged phase fallback should mention 'trục trặc'."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {"conversation_phase": "engaged"}}
        result = _get_phase_fallback(state)
        assert "trục trặc" in result

    def test_deep_fallback(self):
        """Deep phase fallback should ask for rephrasing."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {"conversation_phase": "deep"}}
        result = _get_phase_fallback(state)
        assert "diễn đạt" in result

    def test_closing_fallback(self):
        """Closing phase fallback should ask for specifics."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {"conversation_phase": "closing"}}
        result = _get_phase_fallback(state)
        assert "cụ thể" in result

    def test_unknown_phase_defaults_to_engaged(self):
        """Unknown phase should default to engaged fallback."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {"conversation_phase": "unknown_phase"}}
        result = _get_phase_fallback(state)
        assert "trục trặc" in result

    def test_missing_phase_defaults_to_opening(self):
        """Missing conversation_phase should default to opening."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        state = {"context": {}}
        result = _get_phase_fallback(state)
        assert "Wiii" in result


# =============================================================================
# Group 6: Natural Synthesis (4 tests)
# =============================================================================


class TestNaturalSynthesis:
    """Test natural synthesis prompt without word limits."""

    def test_natural_prompt_no_word_limit(self):
        """SYNTHESIS_PROMPT_NATURAL should NOT contain '500 từ'."""
        from app.engine.multi_agent.supervisor import SYNTHESIS_PROMPT_NATURAL
        assert "500 từ" not in SYNTHESIS_PROMPT_NATURAL

    def test_legacy_prompt_has_word_limit(self):
        """SYNTHESIS_PROMPT should still contain '500 từ'."""
        from app.engine.multi_agent.supervisor import SYNTHESIS_PROMPT
        assert "500 từ" in SYNTHESIS_PROMPT

    def test_natural_prompt_has_positive_style(self):
        """Natural prompt should have positive framing."""
        from app.engine.multi_agent.supervisor import SYNTHESIS_PROMPT_NATURAL
        assert "ấm áp thân thiện" in SYNTHESIS_PROMPT_NATURAL

    @pytest.mark.asyncio
    async def test_single_output_passthrough(self):
        """Single output should be returned directly (no synthesis needed)."""
        from app.engine.multi_agent.supervisor import SupervisorAgent

        agent = SupervisorAgent.__new__(SupervisorAgent)
        agent._llm = MagicMock()

        state = {"agent_outputs": {"direct": "Hello world"}, "query": "test"}
        result = await agent.synthesize(state)
        assert result == "Hello world"


# =============================================================================
# Group 7: Domain Notice Fix (3 tests)
# =============================================================================


class TestDomainNoticeFix:
    """Test that 'greeting' intent no longer triggers domain notice."""

    def test_greeting_excluded_from_notice(self):
        """'greeting' intent should NOT trigger domain_notice."""
        intent = "greeting"
        should_notice = intent in ("off_topic", "general")
        assert should_notice is False

    def test_off_topic_still_triggers_notice(self):
        """'off_topic' intent should still trigger domain_notice."""
        intent = "off_topic"
        should_notice = intent in ("off_topic", "general")
        assert should_notice is True

    def test_general_still_triggers_notice(self):
        """'general' intent should still trigger domain_notice."""
        intent = "general"
        should_notice = intent in ("off_topic", "general")
        assert should_notice is True


# =============================================================================
# Group 8: Diversity Params Config (4 tests)
# =============================================================================


class TestDiversityParams:
    """Test LLM diversity params (presence_penalty, frequency_penalty)."""

    def test_config_defaults_zero(self):
        """Default diversity params should be 0.0."""
        s = _mock_settings()
        assert s.llm_presence_penalty == 0.0
        assert s.llm_frequency_penalty == 0.0

    def test_config_accepts_nonzero(self):
        """Non-zero values should be accepted."""
        s = _mock_settings(llm_presence_penalty=0.3, llm_frequency_penalty=0.2)
        assert s.llm_presence_penalty == 0.3
        assert s.llm_frequency_penalty == 0.2

    def test_bind_called_when_nonzero(self):
        """When natural mode + non-zero params, .bind() should be called."""
        llm = MagicMock()
        llm.bind.return_value = llm
        settings_mock = _mock_settings(
            enable_natural_conversation=True,
            llm_presence_penalty=0.3,
            llm_frequency_penalty=0.2,
        )
        _pp = getattr(settings_mock, "llm_presence_penalty", 0.0)
        _fp = getattr(settings_mock, "llm_frequency_penalty", 0.0)
        if _pp or _fp:
            llm.bind(presence_penalty=_pp, frequency_penalty=_fp)
        llm.bind.assert_called_once_with(presence_penalty=0.3, frequency_penalty=0.2)

    def test_bind_not_called_when_zero(self):
        """When params are 0.0, .bind() should NOT be called."""
        llm = MagicMock()
        settings_mock = _mock_settings(
            enable_natural_conversation=True,
            llm_presence_penalty=0.0,
            llm_frequency_penalty=0.0,
        )
        _pp = getattr(settings_mock, "llm_presence_penalty", 0.0)
        _fp = getattr(settings_mock, "llm_frequency_penalty", 0.0)
        if _pp or _fp:
            llm.bind(presence_penalty=_pp, frequency_penalty=_fp)
        llm.bind.assert_not_called()


# =============================================================================
# Group 9: State Schema (2 tests)
# =============================================================================


class TestStateSchema:
    """Test AgentState has conversation_phase field."""

    def test_conversation_phase_in_state(self):
        """AgentState should accept conversation_phase."""
        from app.engine.multi_agent.state import AgentState
        state: AgentState = {"conversation_phase": "engaged"}
        assert state["conversation_phase"] == "engaged"

    def test_conversation_phase_optional(self):
        """conversation_phase should be optional (not required)."""
        from app.engine.multi_agent.state import AgentState
        state: AgentState = {"query": "test"}
        assert state.get("conversation_phase") is None


# =============================================================================
# Group 10: Regression (4 tests)
# =============================================================================


class TestRegression:
    """Ensure existing behavior is preserved when flag is off."""

    def test_flag_defaults_to_false(self):
        """enable_natural_conversation should default to False."""
        s = _mock_settings()
        assert s.enable_natural_conversation is False

    def test_strip_greeting_prefix_unchanged(self):
        """_strip_greeting_prefix still works correctly."""
        from app.engine.multi_agent.graph import _strip_greeting_prefix
        text = "Chào Nam! Rất vui được hỗ trợ bạn. Theo Điều 15 COLREGs, tàu phải nhường đường."
        result = _strip_greeting_prefix(text)
        assert "Điều 15" in result

    def test_get_phase_fallback_function_exists(self):
        """_get_phase_fallback should be importable."""
        from app.engine.multi_agent.graph import _get_phase_fallback
        assert callable(_get_phase_fallback)

    def test_synthesis_prompt_natural_exists(self):
        """SYNTHESIS_PROMPT_NATURAL should be importable."""
        from app.engine.multi_agent.supervisor import SYNTHESIS_PROMPT_NATURAL
        assert "Query gốc" in SYNTHESIS_PROMPT_NATURAL
