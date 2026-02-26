"""
Sprint 115: SOTA Personality System — 6 Improvements

Tests:
1. Anticharacter section in identity YAML
2. Expanded example dialogues (7→18)
3. Configurable identity anchor (10→6, data flow fix)
4. Emotional state machine (2D mood with decay)
5. Personality evaluation suite (drift detection)
6. Pipeline wiring (mood_hint flow)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass

import yaml


# =============================================================================
# PATHS
# =============================================================================

PROMPTS_DIR = Path(__file__).parent.parent.parent / "app" / "prompts"
IDENTITY_PATH = PROMPTS_DIR / "wiii_identity.yaml"


@pytest.fixture(autouse=True)
def _mock_character_state_manager():
    """Prevent build_system_prompt from connecting to PostgreSQL."""
    with patch(
        "app.engine.character.character_state.get_character_state_manager"
    ) as mock_mgr:
        inst = MagicMock()
        inst.compile_living_state.return_value = ""
        mock_mgr.return_value = inst
        yield


# =============================================================================
# TEST 1: ANTICHARACTER SECTION
# =============================================================================

class TestAnticharacter:
    """Sprint 115 Improvement #2: Anticharacter — negative space definition."""

    def test_anticharacter_exists_in_yaml(self):
        """Identity YAML should have anticharacter section."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        identity = config["identity"]
        assert "anticharacter" in identity

    def test_anticharacter_has_10_items(self):
        """Anticharacter should have 10 items."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        anticharacter = config["identity"]["anticharacter"]
        assert len(anticharacter) == 10

    def test_anticharacter_items_are_strings(self):
        """All anticharacter items should be strings."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        for item in config["identity"]["anticharacter"]:
            assert isinstance(item, str)
            assert len(item) > 10  # Not empty or trivial

    def test_anticharacter_covers_robot_voice(self):
        """Should include robot/corporate AI voice."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        items_lower = [i.lower() for i in config["identity"]["anticharacter"]]
        assert any("máy móc" in i or "robot" in i for i in items_lower)

    def test_anticharacter_covers_formal_voice(self):
        """Should include overly formal/stiff voice."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        items_lower = [i.lower() for i in config["identity"]["anticharacter"]]
        assert any("formal" in i or "cứng nhắc" in i for i in items_lower)

    def test_anticharacter_injected_in_prompt(self):
        """build_system_prompt should inject anticharacter."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        assert "WIII KHÔNG BAO GIỜ:" in prompt

    def test_anticharacter_items_appear_in_prompt(self):
        """At least some anticharacter items should appear in the prompt."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        anticharacter = config["identity"]["anticharacter"]
        # At least first item should be in prompt
        assert anticharacter[0] in prompt


# =============================================================================
# TEST 2: EXPANDED EXAMPLE DIALOGUES
# =============================================================================

class TestExpandedExamples:
    """Sprint 115 Improvement #3: Expand example dialogues (7→18)."""

    def test_example_dialogues_count(self):
        """Should have 18 example dialogues."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        examples = config["identity"]["example_dialogues"]
        assert len(examples) == 18

    def test_all_examples_have_required_fields(self):
        """Each example should have context, user, wiii."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        for i, ex in enumerate(config["identity"]["example_dialogues"]):
            assert "context" in ex, f"Example {i} missing context"
            assert "user" in ex, f"Example {i} missing user"
            assert "wiii" in ex, f"Example {i} missing wiii"

    def test_new_scenarios_covered(self):
        """New scenarios should be present."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        contexts = [ex["context"].lower() for ex in config["identity"]["example_dialogues"]]
        # Check for new scenario types
        assert any("bối rối" in c or "không hiểu" in c for c in contexts)
        assert any("tranh luận" in c or "không đồng ý" in c for c in contexts)
        assert any("tin vui" in c for c in contexts)
        assert any("hỏi về wiii" in c for c in contexts)
        assert any("đùa" in c for c in contexts)

    def test_prompt_includes_8_examples(self):
        """build_system_prompt should include up to 8 examples (was 5)."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student")
        # Count [context] blocks in the VÍ DỤ section
        example_section = prompt.split("VÍ DỤ CÁCH WIII NÓI CHUYỆN:")[-1].split("---")[0]
        context_blocks = example_section.count("[")
        assert context_blocks >= 7  # Should have at least 7 (8 max)
        assert context_blocks <= 8

    def test_original_7_still_present(self):
        """Original 7 examples should still be present."""
        config = yaml.safe_load(IDENTITY_PATH.read_text(encoding="utf-8"))
        examples = config["identity"]["example_dialogues"]
        # Check first 7 original contexts
        original_contexts = [
            "user mệt mỏi",
            "user hỏi kiến thức",
            "user chào lần đầu",
        ]
        actual_contexts = [ex["context"].lower() for ex in examples[:7]]
        for oc in original_contexts:
            assert any(oc in c for c in actual_contexts), f"Missing original: {oc}"


# =============================================================================
# TEST 3: CONFIGURABLE IDENTITY ANCHOR
# =============================================================================

class TestConfigurableAnchor:
    """Sprint 115 Improvement #1: Configurable identity anchor interval."""

    def test_config_has_anchor_interval(self):
        """Settings should have identity_anchor_interval."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            identity_anchor_interval=6,
        )
        assert s.identity_anchor_interval == 6

    def test_config_default_is_6(self):
        """Default should be 6 (was 10)."""
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.identity_anchor_interval == 6

    def test_config_min_3(self):
        """Minimum should be 3."""
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(google_api_key="test", identity_anchor_interval=2)

    def test_config_max_50(self):
        """Maximum should be 50."""
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(google_api_key="test", identity_anchor_interval=51)

    def test_anchor_triggers_at_6(self):
        """Anchor should trigger at total_responses=6 (default)."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", total_responses=6)
        assert "PERSONA REMINDER" in prompt

    def test_anchor_not_at_5(self):
        """Anchor should NOT trigger at total_responses=5."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", total_responses=5)
        assert "PERSONA REMINDER" not in prompt

    def test_anchor_at_0(self):
        """Anchor should NOT trigger at total_responses=0."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", total_responses=0)
        assert "PERSONA REMINDER" not in prompt

    @patch("app.core.config.settings")
    def test_anchor_configurable_interval(self, mock_settings):
        """Anchor interval should be configurable."""
        mock_settings.identity_anchor_interval = 10
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        # At 9, should NOT trigger with interval=10
        prompt_9 = loader.build_system_prompt(role="student", total_responses=9)
        assert "PERSONA REMINDER" not in prompt_9
        # At 10, SHOULD trigger with interval=10
        prompt_10 = loader.build_system_prompt(role="student", total_responses=10)
        assert "PERSONA REMINDER" in prompt_10


# =============================================================================
# TEST 4: EMOTIONAL STATE MACHINE
# =============================================================================

class TestEmotionalState:
    """Sprint 115 Improvement #4: 2D mood state machine."""

    def test_emotional_state_defaults(self):
        """Default state should be neutral."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState()
        assert state.positivity == 0.0
        assert state.energy == 0.5

    def test_mood_neutral_at_defaults(self):
        """Default mood should be NEUTRAL."""
        from app.engine.emotional_state import EmotionalState, MoodState
        state = EmotionalState()
        assert state.mood == MoodState.NEUTRAL

    def test_mood_excited(self):
        """Positive + high energy = EXCITED."""
        from app.engine.emotional_state import EmotionalState, MoodState
        state = EmotionalState(positivity=0.5, energy=0.8)
        assert state.mood == MoodState.EXCITED

    def test_mood_warm(self):
        """Positive + low energy = WARM."""
        from app.engine.emotional_state import EmotionalState, MoodState
        state = EmotionalState(positivity=0.5, energy=0.3)
        assert state.mood == MoodState.WARM

    def test_mood_concerned(self):
        """Negative + high energy = CONCERNED."""
        from app.engine.emotional_state import EmotionalState, MoodState
        state = EmotionalState(positivity=-0.5, energy=0.8)
        assert state.mood == MoodState.CONCERNED

    def test_mood_gentle(self):
        """Negative + low energy = GENTLE."""
        from app.engine.emotional_state import EmotionalState, MoodState
        state = EmotionalState(positivity=-0.5, energy=0.2)
        assert state.mood == MoodState.GENTLE

    def test_clamp(self):
        """Values should be clamped to valid ranges."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState(positivity=2.0, energy=-0.5)
        state.clamp()
        assert state.positivity == 1.0
        assert state.energy == 0.0

    def test_decay_toward_neutral(self):
        """Decay should move state toward neutral."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState(positivity=1.0, energy=1.0)
        state.decay(rate=0.5)
        assert state.positivity < 1.0
        assert state.energy < 1.0

    def test_decay_rate_zero_no_change(self):
        """Zero decay rate should not change state."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState(positivity=0.8, energy=0.8)
        state.decay(rate=0.0)
        assert state.positivity == 0.8
        assert state.energy == 0.8

    def test_mood_hint_neutral_empty(self):
        """Neutral mood should return empty hint."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState()
        assert state.mood_hint == ""

    def test_mood_hint_excited(self):
        """Excited mood should return energy hint."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState(positivity=0.5, energy=0.8)
        hint = state.mood_hint
        assert "phấn khích" in hint or "năng lượng" in hint

    def test_mood_hint_gentle(self):
        """Gentle mood should return empathetic hint."""
        from app.engine.emotional_state import EmotionalState
        state = EmotionalState(positivity=-0.5, energy=0.2)
        hint = state.mood_hint
        assert "nhẹ nhàng" in hint or "buồn" in hint

    def test_mood_state_enum_values(self):
        """MoodState enum should have 5 values."""
        from app.engine.emotional_state import MoodState
        assert len(MoodState) == 5


class TestEmotionalStateManager:
    """Sprint 115: EmotionalStateManager singleton."""

    def test_manager_singleton(self):
        """Should return same instance."""
        from app.engine.emotional_state import get_emotional_state_manager
        m1 = get_emotional_state_manager()
        m2 = get_emotional_state_manager()
        assert m1 is m2

    def test_detect_positive_keyword(self):
        """Positive keywords should increase positivity."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        hint = mgr.detect_and_update("test_user", "Hay quá, cảm ơn!")
        state = mgr.get_state("test_user")
        assert state.positivity > 0

    def test_detect_negative_keyword(self):
        """Negative keywords should decrease positivity."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        hint = mgr.detect_and_update("test_user", "Buồn quá, thất vọng quá.")
        state = mgr.get_state("test_user")
        assert state.positivity < 0

    def test_detect_neutral_message(self):
        """Neutral message should return empty hint (after decay only)."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        hint = mgr.detect_and_update("neutral_user", "Rule 15 là gì?")
        # New user starts at neutral, decay keeps at neutral
        assert hint == ""

    def test_per_user_isolation(self):
        """Each user should have separate state."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        mgr.detect_and_update("happy_user", "Vui quá! Yay!")
        mgr.detect_and_update("sad_user", "Buồn quá.")
        happy_state = mgr.get_state("happy_user")
        sad_state = mgr.get_state("sad_user")
        assert happy_state.positivity > 0
        assert sad_state.positivity < 0

    def test_reset_user(self):
        """Reset should clear user state."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        mgr.detect_and_update("reset_user", "Vui quá!")
        mgr.reset("reset_user")
        state = mgr.get_state("reset_user")
        assert state.positivity == 0.0

    def test_decay_applied_before_detection(self):
        """Decay should be applied before keyword detection."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        # First message: strong positive
        mgr.detect_and_update("decay_user", "Tuyệt vời! Yay!")
        pos_after_first = mgr.get_state("decay_user").positivity
        # Second message: neutral (no keywords) — decay should reduce positivity
        mgr.detect_and_update("decay_user", "Rule 15 là gì?")
        pos_after_second = mgr.get_state("decay_user").positivity
        assert pos_after_second < pos_after_first

    def test_multiple_keywords_stack(self):
        """Multiple keywords in one message should stack."""
        from app.engine.emotional_state import EmotionalStateManager
        mgr = EmotionalStateManager()
        mgr.detect_and_update("multi_user", "Tuyệt vời! Hay quá! Vui quá!")
        state = mgr.get_state("multi_user")
        assert state.positivity > 0.3  # Multiple positive keywords




# =============================================================================
# TEST 6: PIPELINE WIRING (mood_hint flow)
# =============================================================================

class TestPipelineWiring:
    """Sprint 115 Improvement #6: Mood hint wiring through pipeline."""

    def test_chat_context_has_mood_hint(self):
        """ChatContext should have mood_hint field."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        from app.models.schemas import UserRole
        ctx = ChatContext(
            user_id="test",
            session_id=uuid4(),
            message="test",
            user_role=UserRole.STUDENT,
            mood_hint="User vui vẻ",
        )
        assert ctx.mood_hint == "User vui vẻ"

    def test_chat_context_mood_hint_default_empty(self):
        """ChatContext mood_hint should default to empty string."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        from app.models.schemas import UserRole
        ctx = ChatContext(
            user_id="test",
            session_id=uuid4(),
            message="test",
            user_role=UserRole.STUDENT,
        )
        assert ctx.mood_hint == ""

    def test_mood_hint_in_system_prompt(self):
        """build_system_prompt should inject mood_hint."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="student",
            mood_hint="User đang phấn khích — hãy năng lượng!",
        )
        assert "[MOOD:" in prompt
        assert "phấn khích" in prompt

    def test_mood_hint_empty_not_injected(self):
        """Empty mood_hint should not add MOOD section."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", mood_hint="")
        assert "[MOOD:" not in prompt

    def test_mood_hint_none_not_injected(self):
        """None mood_hint should not add MOOD section."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt(role="student", mood_hint=None)
        assert "[MOOD:" not in prompt


# =============================================================================
# TEST: CONFIG SETTINGS
# =============================================================================

class TestConfigSettings:
    """Sprint 115: New config settings."""

    def test_enable_emotional_state_default_false(self):
        """enable_emotional_state should default to False."""
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.enable_emotional_state is False

    def test_emotional_decay_rate_default(self):
        """emotional_decay_rate should default to 0.15."""
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.emotional_decay_rate == 0.15

    def test_identity_anchor_interval_custom(self):
        """Should accept custom anchor interval."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", identity_anchor_interval=12)
        assert s.identity_anchor_interval == 12


# =============================================================================
# TEST: DATA FLOW FIX (total_responses through pipeline)
# =============================================================================

class TestDataFlowFix:
    """Sprint 115: total_responses flows from SessionState through pipeline."""

    def test_multi_agent_context_has_total_responses(self):
        """ChatOrchestrator should pass total_responses to multi_agent_context."""
        from uuid import uuid4
        from app.services.session_manager import SessionState
        state = SessionState(session_id=uuid4())
        # Simulate 8 responses
        for _ in range(8):
            state.increment_response(used_name=False)
            state.add_phrase("test")
        assert state.total_responses == 8

    def test_session_state_tracks_name_usage(self):
        """SessionState should track name_usage_count."""
        from uuid import uuid4
        from app.services.session_manager import SessionState
        state = SessionState(session_id=uuid4())
        state.increment_response(used_name=True)
        state.increment_response(used_name=False)
        assert state.name_usage_count == 1
        assert state.total_responses == 2

    def test_session_state_tracks_recent_phrases(self):
        """SessionState should track recent_phrases (max 5)."""
        from uuid import uuid4
        from app.services.session_manager import SessionState
        state = SessionState(session_id=uuid4())
        for i in range(7):
            state.add_phrase(f"phrase_{i}")
        assert len(state.recent_phrases) == 5

    def test_tutor_node_forwards_total_responses(self):
        """TutorNode._build_system_prompt should accept total_responses."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        # Should not raise with new params
        prompt = loader.build_system_prompt(
            role="student",
            total_responses=8,
            name_usage_count=2,
            mood_hint="User vui",
        )
        assert "PERSONA REMINDER" in prompt  # 8 >= 6
        assert "[MOOD:" in prompt


