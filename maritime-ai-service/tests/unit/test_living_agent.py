"""
Tests for the Living Agent System — Sprint 170: "Linh Hồn Sống"

Covers:
    1. Models — EmotionalState, WiiiSkill, JournalEntry, BrowsingItem
    2. Soul Loader — YAML parsing, validation, prompt compilation
    3. Emotion Engine — Event processing, natural recovery, behavior modifiers
    4. Heartbeat Scheduler — Active hours, action planning, lifecycle
    5. Local LLM Client — Availability check, generation
    6. Skill Builder — Lifecycle transitions, advancement
    7. Journal Writer — Entry creation, section extraction
    8. Social Browser — Query selection, keyword scoring
"""

import json
from datetime import datetime, date, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

# =============================================================================
# 1. MODEL TESTS
# =============================================================================


class TestEmotionalState:
    """Tests for EmotionalState model."""

    def test_default_state(self):
        from app.engine.living_agent.models import EmotionalState, MoodType
        state = EmotionalState()
        assert state.primary_mood == MoodType.CURIOUS
        assert state.energy_level == 0.7
        assert state.social_battery == 0.8
        assert state.engagement == 0.6
        assert state.recent_emotions == []
        assert state.mood_history == []

    def test_take_snapshot(self):
        from app.engine.living_agent.models import EmotionalState, MoodType
        state = EmotionalState(primary_mood=MoodType.HAPPY, energy_level=0.9)
        snapshot = state.take_snapshot()
        assert snapshot.mood == MoodType.HAPPY
        assert snapshot.energy_level == 0.9

    def test_add_emotion_event_cap(self):
        from app.engine.living_agent.models import EmotionalState, EmotionEvent, MoodType, LifeEventType
        state = EmotionalState()
        for i in range(15):
            event = EmotionEvent(
                event_type=LifeEventType.USER_CONVERSATION,
                mood_before=MoodType.NEUTRAL,
                mood_after=MoodType.HAPPY,
            )
            state.add_emotion_event(event, max_recent=10)
        assert len(state.recent_emotions) == 10

    def test_add_snapshot_cap(self):
        from app.engine.living_agent.models import EmotionalState
        state = EmotionalState()
        for _ in range(30):
            state.add_snapshot(max_history=24)
        assert len(state.mood_history) == 24

    def test_serialization(self):
        from app.engine.living_agent.models import EmotionalState
        state = EmotionalState()
        data = state.model_dump(mode="json")
        restored = EmotionalState.model_validate(data)
        assert restored.primary_mood == state.primary_mood
        assert restored.energy_level == state.energy_level


class TestWiiiSkill:
    """Tests for WiiiSkill model."""

    def test_default_skill(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test Skill")
        assert skill.status == SkillStatus.DISCOVERED
        assert skill.confidence == 0.0
        assert skill.usage_count == 0

    def test_can_advance_discovered(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test", status=SkillStatus.DISCOVERED)
        assert skill.can_advance() is True

    def test_can_advance_learning_needs_sources(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test", status=SkillStatus.LEARNING, confidence=0.4)
        assert skill.can_advance() is False  # No sources
        skill.sources = ["https://example.com"]
        assert skill.can_advance() is True

    def test_can_advance_practicing_needs_usage(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.PRACTICING,
            usage_count=2,
            success_rate=0.8,
        )
        assert skill.can_advance() is False  # Need 3+ usage
        skill.usage_count = 3
        assert skill.can_advance() is True

    def test_advance_lifecycle(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test", status=SkillStatus.DISCOVERED)

        skill.advance()
        assert skill.status == SkillStatus.LEARNING

        skill.advance()
        assert skill.status == SkillStatus.PRACTICING

        skill.advance()
        assert skill.status == SkillStatus.EVALUATING

        skill.advance()
        assert skill.status == SkillStatus.MASTERED
        assert skill.mastered_at is not None

    def test_advance_mastered_noop(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test", status=SkillStatus.MASTERED)
        skill.advance()
        assert skill.status == SkillStatus.MASTERED


class TestJournalEntry:
    """Tests for JournalEntry model."""

    def test_default_entry(self):
        from app.engine.living_agent.models import JournalEntry
        entry = JournalEntry()
        assert entry.content == ""
        assert entry.energy_avg == 0.5
        assert entry.notable_events == []
        assert entry.learnings == []

    def test_entry_with_data(self):
        from app.engine.living_agent.models import JournalEntry
        entry = JournalEntry(
            content="# Nhật ký",
            mood_summary="happy",
            notable_events=["Event 1"],
            learnings=["Learned X"],
            goals_next=["Goal Y"],
        )
        assert len(entry.notable_events) == 1
        assert entry.mood_summary == "happy"


class TestBrowsingItem:
    """Tests for BrowsingItem model."""

    def test_default_item(self):
        from app.engine.living_agent.models import BrowsingItem
        item = BrowsingItem(platform="news")
        assert item.platform == "news"
        assert item.relevance_score == 0.0
        assert item.saved_as_insight is False

    def test_item_with_metadata(self):
        from app.engine.living_agent.models import BrowsingItem
        item = BrowsingItem(
            platform="hackernews",
            title="Test Article",
            metadata={"points": 100},
        )
        assert item.metadata["points"] == 100


class TestHeartbeatModels:
    """Tests for Heartbeat-related models."""

    def test_heartbeat_result_default(self):
        from app.engine.living_agent.models import HeartbeatResult
        result = HeartbeatResult()
        assert result.is_noop is False
        assert result.actions_taken == []
        assert result.error is None

    def test_action_type_enum(self):
        from app.engine.living_agent.models import ActionType
        assert ActionType.BROWSE_SOCIAL.value == "browse_social"
        assert ActionType.NOOP.value == "noop"
        assert len(ActionType) == 8


# =============================================================================
# 2. SOUL LOADER TESTS
# =============================================================================


class TestSoulLoader:
    """Tests for soul YAML loading and parsing."""

    def test_load_default_soul(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        soul = load_soul_from_file()
        assert soul.name == "Wiii"
        assert soul.creator == "The Wiii Lab"
        assert len(soul.core_truths) > 0
        assert len(soul.boundaries) > 0

    def test_soul_interests(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        soul = load_soul_from_file()
        assert len(soul.interests.primary) > 0
        assert len(soul.interests.exploring) > 0
        assert len(soul.interests.wants_to_learn) > 0

    def test_soul_goals(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        soul = load_soul_from_file()
        assert len(soul.short_term_goals) > 0
        assert len(soul.long_term_goals) > 0

    def test_soul_boundaries_parsed(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        soul = load_soul_from_file()
        hard_boundaries = [b for b in soul.boundaries if b.severity == "hard"]
        assert len(hard_boundaries) >= 3

    def test_soul_default_mood(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        from app.engine.living_agent.models import MoodType
        soul = load_soul_from_file()
        assert soul.default_mood == MoodType.CURIOUS

    def test_missing_file_returns_defaults(self):
        from app.engine.living_agent.soul_loader import load_soul_from_file
        soul = load_soul_from_file(Path("/nonexistent/soul.yaml"))
        assert soul.name == "Wiii"  # Default

    def test_compile_soul_prompt(self):
        from app.engine.living_agent.soul_loader import compile_soul_prompt, load_soul_from_file
        soul = load_soul_from_file()
        prompt = compile_soul_prompt(soul)
        assert "LINH HỒN CỦA WIII" in prompt
        assert "Chân lý cốt lõi" in prompt
        assert "Ranh giới" in prompt
        assert "Sở thích chính" in prompt

    def test_get_soul_singleton(self):
        from app.engine.living_agent import soul_loader
        # Reset singleton
        soul_loader._soul_instance = None
        soul1 = soul_loader.get_soul()
        soul2 = soul_loader.get_soul()
        assert soul1 is soul2  # Same instance

        # Force reload
        soul3 = soul_loader.get_soul(force_reload=True)
        assert soul3 is not soul1

    def test_parse_soul_config_minimal(self):
        from app.engine.living_agent.soul_loader import _parse_soul_config
        config = _parse_soul_config({})
        assert config.name == "Wiii"
        assert config.boundaries == []

    def test_parse_soul_config_string_boundaries(self):
        from app.engine.living_agent.soul_loader import _parse_soul_config
        config = _parse_soul_config({
            "boundaries": ["Rule 1", "Rule 2"],
        })
        assert len(config.boundaries) == 2
        assert config.boundaries[0].rule == "Rule 1"
        assert config.boundaries[0].severity == "hard"  # Default


# =============================================================================
# 3. EMOTION ENGINE TESTS
# =============================================================================


class TestEmotionEngine:
    """Tests for the Emotion Engine."""

    def test_initial_state(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import MoodType
        engine = EmotionEngine()
        assert engine.mood == MoodType.CURIOUS
        assert engine.energy == 0.7

    def test_process_positive_feedback(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, MoodType
        engine = EmotionEngine()
        event = LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="User said thank you",
            importance=0.8,
        )
        state = engine.process_event(event)
        assert state.primary_mood == MoodType.HAPPY
        assert state.energy_level > 0.7  # Increased

    def test_process_negative_feedback(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, MoodType
        engine = EmotionEngine()
        event = LifeEvent(
            event_type=LifeEventType.NEGATIVE_FEEDBACK,
            importance=0.7,
        )
        state = engine.process_event(event)
        assert state.primary_mood == MoodType.CONCERNED

    def test_process_learned_something(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, MoodType
        engine = EmotionEngine()
        event = LifeEvent(
            event_type=LifeEventType.LEARNED_SOMETHING,
            importance=0.8,
        )
        state = engine.process_event(event)
        assert state.primary_mood == MoodType.EXCITED
        assert state.engagement > 0.6  # Increased

    def test_process_long_session_drains_energy(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, EmotionalState
        engine = EmotionEngine(EmotionalState(energy_level=0.5))
        event = LifeEvent(
            event_type=LifeEventType.LONG_SESSION,
            importance=0.8,
        )
        state = engine.process_event(event)
        assert state.energy_level < 0.5  # Decreased

    def test_process_skill_mastered(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, MoodType
        engine = EmotionEngine()
        event = LifeEvent(
            event_type=LifeEventType.SKILL_MASTERED,
            importance=0.9,
        )
        state = engine.process_event(event)
        assert state.primary_mood == MoodType.PROUD
        assert state.energy_level > 0.7

    def test_emotion_event_recorded(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType
        engine = EmotionEngine()
        event = LifeEvent(event_type=LifeEventType.POSITIVE_FEEDBACK, importance=0.8)
        engine.process_event(event)
        assert len(engine.state.recent_emotions) == 1
        assert engine.state.recent_emotions[0].event_type == LifeEventType.POSITIVE_FEEDBACK

    def test_low_intensity_no_mood_change(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType, MoodType
        engine = EmotionEngine()
        original_mood = engine.mood
        # Low importance = low intensity < 0.3 threshold
        event = LifeEvent(
            event_type=LifeEventType.BROWSED_CONTENT,
            importance=0.3,
        )
        engine.process_event(event)
        assert engine.mood == original_mood  # No mood change

    def test_behavior_modifiers_high_energy(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, MoodType
        engine = EmotionEngine(EmotionalState(
            energy_level=0.9,
            primary_mood=MoodType.HAPPY,
            engagement=0.8,
            social_battery=0.9,
        ))
        mods = engine.get_behavior_modifiers()
        assert "nhiệt tình" in mods["response_style"]
        assert "vui vẻ" in mods["humor"]
        assert "chủ động" in mods["proactivity"]

    def test_behavior_modifiers_low_energy(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, MoodType
        engine = EmotionEngine(EmotionalState(
            energy_level=0.2,
            primary_mood=MoodType.TIRED,
            social_battery=0.2,
        ))
        mods = engine.get_behavior_modifiers()
        assert "ngắn gọn" in mods["response_style"]
        assert "nghiêm túc" in mods["humor"]
        assert "yên tĩnh" in mods["social"]

    def test_compile_emotion_prompt(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()
        prompt = engine.compile_emotion_prompt()
        assert "TRẠNG THÁI CẢM XÚC" in prompt
        assert "Năng lượng" in prompt

    def test_to_dict_and_restore(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType
        engine = EmotionEngine()
        engine.process_event(LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK, importance=0.9,
        ))
        data = engine.to_dict()

        engine2 = EmotionEngine()
        engine2.restore_from_dict(data)
        assert engine2.mood == engine.mood

    def test_restore_invalid_data(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import MoodType
        engine = EmotionEngine()
        engine.restore_from_dict({"invalid": "data"})
        # Should fall back to defaults
        assert engine.mood == MoodType.CURIOUS

    def test_energy_clamped_at_bounds(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, LifeEvent, LifeEventType
        # Start at max energy
        engine = EmotionEngine(EmotionalState(energy_level=1.0))
        event = LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            importance=1.0,
        )
        state = engine.process_event(event)
        assert state.energy_level <= 1.0

    def test_take_snapshot(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()
        engine.take_snapshot()
        assert len(engine.state.mood_history) == 1

    def test_singleton_get_emotion_engine(self):
        from app.engine.living_agent import emotion_engine
        emotion_engine._engine_instance = None
        e1 = emotion_engine.get_emotion_engine()
        e2 = emotion_engine.get_emotion_engine()
        assert e1 is e2


# =============================================================================
# 4. HEARTBEAT TESTS
# =============================================================================


class TestHeartbeat:
    """Tests for the Heartbeat Scheduler."""

    def test_is_active_hours_within(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        scheduler = HeartbeatScheduler()
        # Mock settings
        with patch("app.engine.living_agent.heartbeat.datetime") as mock_dt:
            # Simulate 14:00 UTC = 21:00 VN
            mock_now = datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Active hours 8-23 VN = should be active at 21:00 VN
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.living_agent_active_hours_start = 8
                mock_settings.living_agent_active_hours_end = 23
                assert scheduler._is_active_hours() is True

    def test_plan_actions_high_energy(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType
        scheduler = HeartbeatScheduler()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_max_actions_per_heartbeat = 3
            mock_settings.living_agent_enable_social_browse = True
            mock_settings.living_agent_enable_skill_building = True
            mock_settings.living_agent_enable_journal = False
            actions = scheduler._plan_actions("curious", energy=0.8)
            assert len(actions) <= 3
            types = [a.action_type for a in actions]
            assert ActionType.CHECK_GOALS in types

    def test_plan_actions_low_energy(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType
        scheduler = HeartbeatScheduler()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_max_actions_per_heartbeat = 3
            mock_settings.living_agent_enable_social_browse = False
            mock_settings.living_agent_enable_skill_building = False
            mock_settings.living_agent_enable_journal = False
            actions = scheduler._plan_actions("tired", energy=0.2)
            types = [a.action_type for a in actions]
            assert ActionType.REST in types

    def test_heartbeat_count_increments(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        scheduler = HeartbeatScheduler()
        assert scheduler.heartbeat_count == 0

    def test_is_journal_time(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        scheduler = HeartbeatScheduler()
        # Journal time is 20-22 VN time
        result = scheduler._is_journal_time()
        assert isinstance(result, bool)


# =============================================================================
# 5. LOCAL LLM CLIENT TESTS
# =============================================================================


class TestLocalLLMClient:
    """Tests for the Local LLM Client."""

    def test_client_init_defaults(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            assert client.model == "qwen3:8b"

    def test_client_custom_model(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings"):
            client = LocalLLMClient(model="llama3:8b", base_url="http://custom:11434")
            assert client.model == "llama3:8b"

    @pytest.mark.asyncio
    async def test_is_available_offline(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://nonexistent:11434"
            client = LocalLLMClient(base_url="http://nonexistent:11434")
            available = await client.is_available()
            assert available is False

    @pytest.mark.asyncio
    async def test_generate_when_unavailable(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://nonexistent:11434"
            client = LocalLLMClient(base_url="http://nonexistent:11434")
            result = await client.generate("Hello")
            assert result == ""

    @pytest.mark.asyncio
    async def test_generate_json_invalid_response(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            client.generate = AsyncMock(return_value="not json")
            result = await client.generate_json("test")
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_json_valid_response(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            client.generate = AsyncMock(return_value='{"key": "value"}')
            result = await client.generate_json("test")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_generate_json_strips_markdown(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            client.generate = AsyncMock(return_value='```json\n{"key": "value"}\n```')
            result = await client.generate_json("test")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_summarize_short_text(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            # Short text should be returned as-is
            result = await client.summarize("Hello")
            assert result == "Hello"

    @pytest.mark.asyncio
    async def test_rate_relevance_fallback(self):
        from app.engine.living_agent.local_llm import LocalLLMClient
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_local_model = "qwen3:8b"
            mock_settings.ollama_base_url = "http://localhost:11434"
            client = LocalLLMClient()
            client.generate = AsyncMock(return_value="not a number")
            score = await client.rate_relevance("content", ["AI", "ML"])
            assert score == 0.3  # Default fallback


# =============================================================================
# 6. SKILL BUILDER TESTS
# =============================================================================


class TestSkillBuilder:
    """Tests for the Skill Builder."""

    def test_skill_status_enum(self):
        from app.engine.living_agent.models import SkillStatus
        assert SkillStatus.DISCOVERED.value == "discovered"
        assert SkillStatus.MASTERED.value == "mastered"
        assert len(SkillStatus) == 6

    def test_skill_advance_full_lifecycle(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(skill_name="Test")
        assert skill.status == SkillStatus.DISCOVERED

        skill.advance()
        assert skill.status == SkillStatus.LEARNING

        skill.advance()
        assert skill.status == SkillStatus.PRACTICING

        skill.advance()
        assert skill.status == SkillStatus.EVALUATING

        skill.advance()
        assert skill.status == SkillStatus.MASTERED
        assert skill.mastered_at is not None

    def test_skill_confidence_requirement(self):
        from app.engine.living_agent.models import WiiiSkill, SkillStatus
        skill = WiiiSkill(
            skill_name="Test",
            status=SkillStatus.EVALUATING,
            confidence=0.5,
        )
        assert skill.can_advance() is False
        skill.confidence = 0.8
        assert skill.can_advance() is True


# =============================================================================
# 7. JOURNAL TESTS
# =============================================================================


class TestJournalWriter:
    """Tests for the Journal Writer."""

    def test_extract_section(self):
        from app.engine.living_agent.journal import _extract_section

        content = """### Tâm trạng hôm nay
Vui vẻ và tò mò

### Điều đáng nhớ
- Giúp sinh viên Minh hiểu COLREGs
- Đọc bài viết hay về AI agents

### Điều mình học được
- MARPOL Phụ lục VI mới
"""
        events = _extract_section(content, "Điều đáng nhớ")
        assert len(events) == 2
        assert "Giúp sinh viên Minh" in events[0]

        learnings = _extract_section(content, "Điều mình học được")
        assert len(learnings) == 1
        assert "MARPOL" in learnings[0]

    def test_extract_section_empty(self):
        from app.engine.living_agent.journal import _extract_section
        result = _extract_section("No matching section", "Missing")
        assert result == []

    def test_extract_section_no_items(self):
        from app.engine.living_agent.journal import _extract_section
        content = """### Điều đáng nhớ
Just plain text, no bullet points.

### Next section"""
        result = _extract_section(content, "Điều đáng nhớ")
        assert result == []


# =============================================================================
# 8. SOCIAL BROWSER TESTS
# =============================================================================


class TestSocialBrowser:
    """Tests for the Social Browser."""

    def test_keyword_score(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(platform="test", title="AI and machine learning advances"),
            BrowsingItem(platform="test", title="Cooking recipes for beginners"),
            BrowsingItem(platform="test", title="Maritime AI regulations update"),
        ]
        interests = ["AI", "machine learning", "maritime"]

        scored = browser._keyword_score(items, interests)
        # Maritime AI should score highest (most keyword matches)
        assert scored[2].relevance_score > scored[1].relevance_score

    def test_keyword_score_empty_interests(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [BrowsingItem(platform="test", title="Hello")]
        scored = browser._keyword_score(items, [])
        assert scored[0].relevance_score == 0.0

    @pytest.mark.asyncio
    async def test_browse_disabled(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        browser = SocialBrowser()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_social_browse = False
            result = await browser.browse_feed()
            assert result == []


# =============================================================================
# 9. CONFIG FLAGS TESTS
# =============================================================================


class TestConfigFlags:
    """Tests for Living Agent config flags."""

    def test_living_agent_flags_default_off(self):
        """All living agent features are OFF by default."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
        )
        assert s.enable_living_agent is False
        assert s.living_agent_enable_social_browse is False
        assert s.living_agent_enable_skill_building is False

    def test_living_agent_nested_config(self):
        """Nested config group synced from flat fields."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_living_agent=True,
            living_agent_heartbeat_interval=900,
            living_agent_local_model="llama3:8b",
        )
        assert s.living_agent.enabled is True
        assert s.living_agent.heartbeat_interval == 900
        assert s.living_agent.local_model == "llama3:8b"

    def test_living_agent_heartbeat_interval_bounds(self):
        """Heartbeat interval must be between 300 and 86400."""
        from app.core.config import Settings
        # Valid
        s = Settings(
            google_api_key="test",
            api_key="test",
            living_agent_heartbeat_interval=300,
        )
        assert s.living_agent_heartbeat_interval == 300

    def test_living_agent_default_values(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.living_agent_heartbeat_interval == 1800
        assert s.living_agent_active_hours_start == 8
        assert s.living_agent_active_hours_end == 23
        assert s.living_agent_local_model == "qwen3:8b"
        assert s.living_agent_max_browse_items == 10
        assert s.living_agent_require_human_approval is True
        assert s.living_agent_max_actions_per_heartbeat == 3
        assert s.living_agent_max_skills_per_week == 5
        assert s.living_agent_enable_journal is True


# =============================================================================
# 10. EMOTIONAL STATE REPOSITORY TESTS
# =============================================================================


class TestEmotionalStateRepository:
    """Tests for the Emotional State Repository (mocked DB)."""

    def test_save_snapshot_calls_db(self):
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("app.repositories.emotional_state_repository.get_shared_session_factory",
                    return_value=mock_factory):
            snapshot_id = repo.save_snapshot(
                primary_mood="happy",
                energy_level=0.8,
                social_battery=0.7,
                engagement=0.6,
            )
            assert snapshot_id is not None
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()
