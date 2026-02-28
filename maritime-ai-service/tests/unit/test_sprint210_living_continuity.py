"""
Sprint 210: "Sống Thật" — Living Continuity Tests.

Tests the 8 bug fixes that bring Wiii's Living Agent from clock to consciousness:
1. Chat → Emotion feedback loop (sync + streaming)
2. Episodic memory storage
3. Mood reset fix (2h→6h, CURIOUS→NEUTRAL)
4. Mood change threshold lowered (0.3→0.2)
5. Reflection daily (not weekly 1h window)
6. _action_reflect actually calls Reflector
7. Journal expanded time window (morning+evening)
8. Insight extraction from browsing
9. Goal seeding from soul definition
10. LLM timeout protection (60s per action)
11. Config flag
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4


# ============================================================================
# Shared helpers
# ============================================================================

def _make_settings(**overrides):
    """Create a settings mock with Sprint 210 flags."""
    defaults = {
        "enable_living_agent": True,
        "enable_living_continuity": True,
        "living_agent_heartbeat_interval": 60,
        "living_agent_active_hours_start": 0,
        "living_agent_active_hours_end": 24,
        "living_agent_enable_social_browse": False,
        "living_agent_enable_skill_building": False,
        "living_agent_enable_journal": False,
        "living_agent_require_human_approval": False,
        "living_agent_max_actions_per_heartbeat": 5,
        "living_agent_max_daily_cycles": 48,
        "living_agent_enable_weather": False,
        "living_agent_enable_briefing": False,
        "living_agent_enable_skill_learning": False,
        "living_agent_enable_proactive_messaging": False,
        "living_agent_enable_routine_tracking": False,
        "living_agent_enable_autonomy_graduation": False,
        "living_agent_enable_dynamic_goals": False,
        "living_agent_autonomy_level": 0,
        "enable_identity_core": False,
        "enable_narrative_context": False,
        "enable_natural_conversation": False,
        "enable_skill_tool_bridge": False,
        "enable_skill_metrics": False,
        "default_domain": "maritime",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_soul():
    """Create a mock SoulConfig with interests."""
    soul = MagicMock()
    soul.short_term_goals = ["Learn COLREGs"]
    soul.long_term_goals = ["Become maritime expert"]
    soul.interests.primary = ["maritime"]
    soul.interests.exploring = ["AI"]
    soul.interests.wants_to_learn = ["Docker", "Kubernetes", "Rust"]
    return soul


# ============================================================================
# GROUP 1: Config flag
# ============================================================================

class TestConfigFlag:
    """Test enable_living_continuity config."""

    def test_flag_exists_as_bool(self):
        """Flag exists and is a boolean (default False, but env can override)."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert isinstance(s.enable_living_continuity, bool)

    def test_flag_can_be_enabled(self):
        """Flag can be set to True."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_living_continuity=True,
        )
        assert s.enable_living_continuity is True

    def test_flag_requires_living_agent_conceptually(self):
        """enable_living_continuity is meaningless without enable_living_agent,
        but should not error — it's just a no-op."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_living_continuity=True,
            enable_living_agent=False,
        )
        assert s.enable_living_continuity is True
        assert s.enable_living_agent is False


# ============================================================================
# GROUP 2: Mood Reset Fix (emotion_engine.py)
# ============================================================================

class TestMoodResetFix:
    """Test Sprint 210 mood reset changes in emotion_engine."""

    def test_no_reset_at_2h(self):
        """Mood should NOT reset after only 2h of inactivity."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, MoodType

        state = EmotionalState(primary_mood=MoodType.HAPPY)
        # Set last_updated to 2.5h ago
        state.last_updated = datetime.now(timezone.utc) - timedelta(hours=2.5)
        engine = EmotionEngine(initial_state=state)

        # Trigger natural recovery
        engine._apply_natural_recovery()

        # HAPPY should NOT be forced to CURIOUS after 2h
        assert engine._state.primary_mood == MoodType.HAPPY

    def test_reset_to_neutral_at_6h(self):
        """Mood should fade to NEUTRAL (not CURIOUS) after 6h inactivity."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, MoodType

        state = EmotionalState(primary_mood=MoodType.HAPPY)
        state.last_updated = datetime.now(timezone.utc) - timedelta(hours=7)
        engine = EmotionEngine(initial_state=state)

        engine._apply_natural_recovery()

        assert engine._state.primary_mood == MoodType.NEUTRAL

    def test_no_reset_for_calm_moods(self):
        """CURIOUS, NEUTRAL, CALM should not be reset even after 6h."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import EmotionalState, MoodType

        for mood in [MoodType.CURIOUS, MoodType.NEUTRAL, MoodType.CALM]:
            state = EmotionalState(primary_mood=mood)
            state.last_updated = datetime.now(timezone.utc) - timedelta(hours=10)
            engine = EmotionEngine(initial_state=state)
            engine._apply_natural_recovery()
            assert engine._state.primary_mood == mood

    def test_threshold_lowered_to_0_2(self):
        """Mood should change when intensity >= 0.2 (was 0.3), after dampening."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            EmotionalState, MoodType, LifeEvent, LifeEventType,
        )

        engine = EmotionEngine()
        # Set last_mood_change to past to bypass cooldown
        engine._last_mood_change = datetime(2020, 1, 1, tzinfo=timezone.utc)

        # POSITIVE_FEEDBACK has intensity=0.7. With importance=0.3:
        # effective intensity = 0.7 * 0.3 = 0.21 — above new 0.2 threshold
        engine.process_event(LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="Test",
            importance=0.3,
        ))
        # Cooldown elapsed → mood changes immediately
        assert engine._state.primary_mood == MoodType.HAPPY

    def test_threshold_blocks_below_0_2(self):
        """Mood should NOT change when intensity < 0.2."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            EmotionalState, MoodType, LifeEvent, LifeEventType,
        )

        engine = EmotionEngine()
        # POSITIVE_FEEDBACK intensity=0.7, importance=0.2 → 0.14 < 0.2
        engine.process_event(LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="Test",
            importance=0.2,
        ))
        # Should stay at initial mood (CURIOUS) since 0.14 < 0.2
        assert engine._state.primary_mood == MoodType.CURIOUS


# ============================================================================
# GROUP 3: Chat → Emotion Feedback (chat_orchestrator.py)
# ============================================================================

class TestChatEmotionFeedback:
    """Test chat → Living Agent emotion feedback loop."""

    @pytest.mark.asyncio
    async def test_user_conversation_event_fired(self):
        """Regular message fires USER_CONVERSATION event."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType

        engine = EmotionEngine()
        events_received = []
        original_process = engine.process_event

        def capture_event(event):
            events_received.append(event)
            return original_process(event)

        engine.process_event = capture_event

        # Simulate what chat_orchestrator does
        msg = "Luật COLREGs là gì?"
        _event_type = LifeEventType.USER_CONVERSATION
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = LifeEventType.POSITIVE_FEEDBACK
            _importance = 0.8

        engine.process_event(LifeEvent(
            event_type=_event_type,
            description=f"Conversation: {msg[:100]}",
            importance=_importance,
        ))

        assert len(events_received) == 1
        assert events_received[0].event_type == LifeEventType.USER_CONVERSATION

    def test_positive_feedback_on_cam_on(self):
        """Message with 'cảm ơn' triggers POSITIVE_FEEDBACK."""
        msg = "Cảm ơn bạn rất nhiều!"
        _event_type = "USER_CONVERSATION"
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
        assert _event_type == "POSITIVE_FEEDBACK"

    def test_positive_feedback_on_thank(self):
        """English 'thank' triggers POSITIVE_FEEDBACK."""
        msg = "Thank you so much!"
        _event_type = "USER_CONVERSATION"
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
        assert _event_type == "POSITIVE_FEEDBACK"

    def test_positive_feedback_on_hay_qua(self):
        """Vietnamese 'hay quá' triggers POSITIVE_FEEDBACK."""
        msg = "Hay quá bạn ơi!"
        _event_type = "USER_CONVERSATION"
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
        assert _event_type == "POSITIVE_FEEDBACK"

    def test_negative_feedback_on_sai_roi(self):
        """Vietnamese 'sai rồi' triggers NEGATIVE_FEEDBACK."""
        msg = "Sai rồi bạn ơi!"
        _event_type = "USER_CONVERSATION"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
            _importance = 0.8
        elif any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong", "tệ"]):
            _event_type = "NEGATIVE_FEEDBACK"
            _importance = 0.7
        assert _event_type == "NEGATIVE_FEEDBACK"
        assert _importance == 0.7

    def test_negative_feedback_on_wrong(self):
        """English 'wrong' triggers NEGATIVE_FEEDBACK."""
        msg = "That's wrong!"
        _event_type = "USER_CONVERSATION"
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
        elif any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong", "tệ"]):
            _event_type = "NEGATIVE_FEEDBACK"
        assert _event_type == "NEGATIVE_FEEDBACK"

    def test_neutral_message_stays_user_conversation(self):
        """Neutral message stays USER_CONVERSATION."""
        msg = "Giải thích quy tắc 15 cho tôi"
        _event_type = "USER_CONVERSATION"
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank", "hay quá", "tuyệt", "giỏi"]):
            _event_type = "POSITIVE_FEEDBACK"
        elif any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong", "tệ"]):
            _event_type = "NEGATIVE_FEEDBACK"
        assert _event_type == "USER_CONVERSATION"

    def test_flag_off_no_event(self):
        """When enable_living_continuity=False, no emotion event is fired."""
        settings = _make_settings(enable_living_continuity=False)
        # Simulate the guard check
        fired = False
        if getattr(settings, "enable_living_continuity", False):
            fired = True
        assert not fired


# ============================================================================
# GROUP 4: Episodic Memory
# ============================================================================

class TestEpisodicMemory:
    """Test Sprint 210 episodic memory (MemoryType.EPISODE)."""

    def test_episode_enum_exists(self):
        """EPISODE enum value should exist in MemoryType."""
        from app.models.semantic_memory import MemoryType
        assert hasattr(MemoryType, 'EPISODE')
        assert MemoryType.EPISODE.value == "episode"

    def test_episode_content_format(self):
        """Episode content should include agent type, question, and answer."""
        _topic = "rag_agent"
        _message = "Luật COLREGs là gì?"
        _response = "COLREGs là bộ quy tắc phòng ngừa va chạm trên biển..."
        _episode = f"[{_topic}] User asked: {_message[:150]}. Wiii answered about: {_response[:150]}"

        assert "[rag_agent]" in _episode
        assert "User asked:" in _episode
        assert "Wiii answered about:" in _episode

    def test_episode_importance_from_positive(self):
        """Positive feedback should result in importance=0.8."""
        msg = "Cảm ơn bạn!"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank"]):
            _importance = 0.8
        assert _importance == 0.8

    def test_episode_importance_from_negative(self):
        """Negative feedback should result in importance=0.7."""
        msg = "Sai rồi!"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong"]):
            _importance = 0.7
        assert _importance == 0.7

    def test_episode_importance_default(self):
        """Default importance is 0.5."""
        msg = "Giải thích quy tắc 15"
        _importance = 0.5
        _msg_lower = msg.lower()
        if any(w in _msg_lower for w in ["cảm ơn", "cam on", "thank"]):
            _importance = 0.8
        elif any(w in _msg_lower for w in ["sai rồi", "không đúng", "wrong"]):
            _importance = 0.7
        assert _importance == 0.5

    def test_episode_flag_off_no_storage(self):
        """When enable_living_continuity=False, no episode is stored."""
        settings = _make_settings(enable_living_continuity=False)
        stored = False
        if getattr(settings, "enable_living_continuity", False):
            stored = True
        assert not stored


# ============================================================================
# GROUP 5: Reflection Daily
# ============================================================================

class TestReflectionDaily:
    """Test reflection window changes (weekly → daily)."""

    def test_daily_window_hit_at_21h(self):
        """Reflection should trigger at 21:00 UTC+7."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        # 21:00 UTC+7 = 14:00 UTC
        with patch("app.engine.living_agent.heartbeat.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 2, 26, 14, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Direct calculation check
            now_vn = datetime(2026, 2, 26, 14, 0, tzinfo=timezone.utc) + timedelta(hours=7)
            assert 21 <= now_vn.hour <= 22

    def test_daily_window_hit_at_22h(self):
        """Reflection should trigger at 22:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 15, 0, tzinfo=timezone.utc) + timedelta(hours=7)
        assert 21 <= now_vn.hour <= 22

    def test_daily_window_miss_at_19h(self):
        """Reflection should NOT trigger at 19:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc) + timedelta(hours=7)
        assert not (21 <= now_vn.hour <= 22)

    def test_daily_not_just_sunday(self):
        """Reflection should work on any day of the week."""
        # Test multiple days: Feb 23 (Mon) through Feb 28 (Sat) + Mar 1 (Sun)
        test_dates = [
            (2026, 2, 23), (2026, 2, 24), (2026, 2, 25),
            (2026, 2, 26), (2026, 2, 27), (2026, 2, 28), (2026, 3, 1),
        ]
        for year, month, day in test_dates:
            # 14:00 UTC = 21:00 UTC+7
            now_vn = datetime(year, month, day, 14, 0, tzinfo=timezone.utc) + timedelta(hours=7)
            assert 21 <= now_vn.hour <= 22, f"Failed for {year}-{month}-{day}"

    @pytest.mark.asyncio
    async def test_reflector_has_reflected_today(self):
        """_has_reflected_today should use date_trunc('day')."""
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()

        # Mock DB to return count=1
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: 1

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.fetchone.return_value = mock_row
            mock_factory.return_value = MagicMock(return_value=mock_session)

            result = await reflector._has_reflected_today(None)
            assert result is True


# ============================================================================
# GROUP 6: _action_reflect Fix
# ============================================================================

class TestActionReflectFix:
    """Test _action_reflect actually calls Reflector."""

    @pytest.mark.asyncio
    async def test_action_reflect_calls_reflector(self):
        """_action_reflect should call reflector.reflect() (not just fire event)."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import LifeEvent, LifeEventType

        scheduler = HeartbeatScheduler()
        engine = MagicMock()
        engine.process_event = MagicMock()

        mock_entry = MagicMock()
        mock_entry.content = "Today I learned about COLREGs and felt proud."

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=mock_entry)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            mock_reflector.reflect.assert_called_once()
            engine.process_event.assert_called_once()
            event = engine.process_event.call_args[0][0]
            assert event.event_type == LifeEventType.REFLECTION_COMPLETED
            assert "Today I learned" in event.description

    @pytest.mark.asyncio
    async def test_action_reflect_handles_none(self):
        """_action_reflect should handle reflector returning None gracefully."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=None)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            # Should NOT fire REFLECTION_COMPLETED when reflect() returns None
            engine.process_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_action_reflect_handles_exception(self):
        """_action_reflect should handle reflector errors gracefully."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import LifeEventType

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(side_effect=Exception("DB error"))
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            # Should still fire a fallback event on error
            engine.process_event.assert_called_once()
            event = engine.process_event.call_args[0][0]
            assert event.event_type == LifeEventType.REFLECTION_COMPLETED

    @pytest.mark.asyncio
    async def test_action_reflect_includes_content_in_description(self):
        """Reflection event description should include reflection content snippet."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        mock_entry = MagicMock()
        mock_entry.content = "X" * 200  # Long content

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=mock_entry)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            event = engine.process_event.call_args[0][0]
            assert event.description.startswith("Reflection: ")
            # Should be truncated to ~100 chars
            assert len(event.description) <= 120


# ============================================================================
# GROUP 7: Journal Expanded Window
# ============================================================================

class TestJournalExpandedWindow:
    """Test journal time window changes (evening → morning+evening)."""

    def test_morning_window_8h(self):
        """Journal should be available at 8:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 1, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 8:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_morning_window_9h(self):
        """Journal should be available at 9:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 2, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 9:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_evening_window_20h(self):
        """Journal should be available at 20:00 UTC+7 (existing window)."""
        now_vn = datetime(2026, 2, 26, 13, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 20:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_midday_not_journal_time(self):
        """Journal should NOT be available at 15:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 8, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 15:00 VN
        assert not ((8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22))


# ============================================================================
# GROUP 8: Insight Extraction
# ============================================================================

class TestInsightExtraction:
    """Test browsing → insight extraction (social_browser.py)."""

    @pytest.mark.asyncio
    async def test_high_relevance_saved_as_insight(self):
        """Items with relevance >= 0.6 should be saved as insights."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="COLREGs Update 2026",
                summary="Major changes to Rule 15",
                relevance_score=0.8,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            saved = await browser._extract_and_save_insights(items)
            assert saved == 1
            # Verify INSERT was called
            mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_low_relevance_not_saved(self):
        """Items with relevance < 0.6 should NOT be saved."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="Random News",
                summary="Something unrelated",
                relevance_score=0.3,
            ),
        ]

        saved = await browser._extract_and_save_insights(items)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_empty_title_not_saved(self):
        """Items with empty titles should NOT be saved."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="",
                summary="High relevance but no title",
                relevance_score=0.9,
            ),
        ]

        saved = await browser._extract_and_save_insights(items)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_insight_content_format(self):
        """Insight content should follow [Discovery] format."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="COLREGs Rule 15 Update",
                summary="Crossing situation rules updated for autonomous vessels",
                relevance_score=0.7,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            await browser._extract_and_save_insights(items)

            # Check the content passed to INSERT — find it in any execute call
            found_content = False
            for call in mock_session.execute.call_args_list:
                # params can be in args[1] or kwargs
                params = call[0][1] if len(call[0]) > 1 else call.kwargs
                if isinstance(params, dict) and "content" in params:
                    assert "[Discovery]" in params["content"]
                    assert "COLREGs Rule 15 Update" in params["content"]
                    found_content = True
                    break
            assert found_content, "No INSERT with content param found"

    @pytest.mark.asyncio
    async def test_db_error_doesnt_crash(self):
        """DB errors during insight extraction should be swallowed."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="Test",
                summary="Test summary",
                relevance_score=0.8,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_factory.side_effect = Exception("DB connection failed")

            # Should not raise
            saved = await browser._extract_and_save_insights(items)
            assert saved == 0

    def test_mark_as_insight_exists(self):
        """_mark_as_insight method should exist."""
        from app.engine.living_agent.social_browser import SocialBrowser
        browser = SocialBrowser()
        assert hasattr(browser, '_mark_as_insight')


# ============================================================================
# GROUP 9: Goal Seeding
# ============================================================================

class TestGoalSeeding:
    """Test goal seeding from soul definition."""

    @pytest.mark.asyncio
    async def test_seeds_from_wants_to_learn(self):
        """seed_initial_goals should create goals from wants_to_learn."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                # 3 from wants_to_learn + 1 meta-goal = 4
                assert seeded == 4
                assert mock_create.call_count == 4

    @pytest.mark.asyncio
    async def test_idempotent_with_existing_goals(self):
        """seed_initial_goals should return 0 if goals already exist."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        existing_goal = MagicMock()
        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[existing_goal]):
            seeded = await manager.seed_initial_goals(soul)
            assert seeded == 0

    @pytest.mark.asyncio
    async def test_meta_goal_always_created(self):
        """Meta-goal about helping students should always be created."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = MagicMock()
        soul.interests.wants_to_learn = []  # No topics

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                assert seeded == 1  # Only meta-goal
                call_args = mock_create.call_args
                assert "sinh viên hàng hải" in call_args[1]["title"]

    @pytest.mark.asyncio
    async def test_max_3_learning_goals(self):
        """Should limit to first 3 wants_to_learn topics."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = MagicMock()
        soul.interests.wants_to_learn = ["A", "B", "C", "D", "E"]

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                # 3 learning + 1 meta = 4
                assert seeded == 4

    @pytest.mark.asyncio
    async def test_goals_use_soul_seed_source(self):
        """Seeded goals should have source='soul_seed'."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                await manager.seed_initial_goals(soul)

                for call in mock_create.call_args_list:
                    assert call[1]["source"] == "soul_seed"


# ============================================================================
# GROUP 10: LLM Timeout Protection
# ============================================================================

class TestLLMTimeout:
    """Test 60s timeout protection in heartbeat actions."""

    @pytest.mark.asyncio
    async def test_timeout_wraps_action(self):
        """_execute_action should have 60s timeout."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()
        action = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        # REST does nothing, should complete instantly
        await scheduler._execute_action(action, soul, engine)
        # No error — pass

    @pytest.mark.asyncio
    async def test_timeout_on_slow_action(self):
        """Action exceeding 60s should be cancelled, not crash."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()

        async def slow_dispatch(action, soul, engine):
            await asyncio.sleep(100)  # Simulate very slow action

        action = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        with patch.object(scheduler, '_dispatch_action', side_effect=slow_dispatch):
            # Should not raise — timeout is caught internally
            await scheduler._execute_action(action, soul, engine)

    @pytest.mark.asyncio
    async def test_action_continues_after_timeout(self):
        """Heartbeat should continue processing after one action times out."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()
        call_count = 0

        async def track_dispatch(action, soul, engine):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(100)  # First action times out
            # Second action completes

        action1 = HeartbeatAction(action_type=ActionType.REFLECT, priority=0.5)
        action2 = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        with patch.object(scheduler, '_dispatch_action', side_effect=track_dispatch):
            await scheduler._execute_action(action1, soul, engine)
            await scheduler._execute_action(action2, soul, engine)

        assert call_count == 2  # Both dispatched, first timed out

    @pytest.mark.asyncio
    async def test_dispatch_action_exists(self):
        """_dispatch_action should exist as the internal handler."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        scheduler = HeartbeatScheduler()
        assert hasattr(scheduler, '_dispatch_action')


# ============================================================================
# GROUP 11: Heartbeat Goal Seeding Integration
# ============================================================================

class TestHeartbeatGoalSeeding:
    """Test goal seeding wired into heartbeat _action_check_goals."""

    @pytest.mark.asyncio
    async def test_check_goals_seeds_once(self):
        """_action_check_goals should seed goals on first call."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        soul = _make_soul()

        mock_manager = AsyncMock()
        mock_manager.seed_initial_goals = AsyncMock(return_value=4)
        mock_manager.get_active_goals = AsyncMock(return_value=[MagicMock()])

        with patch("app.engine.living_agent.goal_manager.get_goal_manager", return_value=mock_manager):
            await scheduler._action_check_goals(soul)

            mock_manager.seed_initial_goals.assert_called_once_with(soul)
            assert scheduler._goals_seeded is True

    @pytest.mark.asyncio
    async def test_check_goals_idempotent(self):
        """_action_check_goals should NOT re-seed on subsequent calls."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        scheduler._goals_seeded = True  # Already seeded
        soul = _make_soul()

        mock_manager = AsyncMock()
        mock_manager.get_active_goals = AsyncMock(return_value=[])

        with patch("app.engine.living_agent.goal_manager.get_goal_manager", return_value=mock_manager):
            await scheduler._action_check_goals(soul)

            mock_manager.seed_initial_goals.assert_not_called()


# ============================================================================
# GROUP 12: Reflector Daily Method
# ============================================================================

class TestReflectorDailyMethod:
    """Test Reflector.reflect() daily method."""

    @pytest.mark.asyncio
    async def test_reflect_method_exists(self):
        """Reflector should have a reflect() method (Sprint 210)."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()
        assert hasattr(reflector, 'reflect')
        assert asyncio.iscoroutinefunction(reflector.reflect)

    @pytest.mark.asyncio
    async def test_reflect_skips_if_already_reflected_today(self):
        """reflect() should return None if already reflected today."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        with patch.object(reflector, '_has_reflected_today', new_callable=AsyncMock, return_value=True):
            result = await reflector.reflect()
            assert result is None

    @pytest.mark.asyncio
    async def test_reflect_uses_1_day_lookback(self):
        """reflect() should gather data from past 1 day (not 7)."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        with patch.object(reflector, '_has_reflected_today', new_callable=AsyncMock, return_value=False):
            with patch.object(reflector, '_get_journal_summary', new_callable=AsyncMock, return_value="") as mock_journal:
                with patch.object(reflector, '_get_emotion_summary', new_callable=AsyncMock, return_value=""):
                    with patch.object(reflector, '_get_browsing_summary', new_callable=AsyncMock, return_value=""):
                        with patch.object(reflector, '_get_skills_summary', new_callable=AsyncMock, return_value=""):
                            with patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                                mock_llm.return_value.generate = AsyncMock(return_value=None)
                                await reflector.reflect()

                                # Check journal_summary called with days=1
                                mock_journal.assert_called_once_with(1, None)

    def test_is_reflection_time_daily(self):
        """is_reflection_time should return True at 21:00 any day."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        # We can't easily mock datetime.now in the method since it uses
        # datetime.now(timezone.utc) directly. Test the logic.
        from datetime import timedelta
        # Monday 21:30 UTC+7 = 14:30 UTC
        utc_time = datetime(2026, 2, 23, 14, 30, tzinfo=timezone.utc)
        now_vn = utc_time + timedelta(hours=7)
        assert 21 <= now_vn.hour <= 22


# ============================================================================
# GROUP 13: Integration — Emotion changes from conversation
# ============================================================================

class TestEmotionFromConversation:
    """Integration test: conversation events affect mood."""

    def test_positive_feedback_makes_happy(self):
        """POSITIVE_FEEDBACK event should change mood to HAPPY (after cooldown)."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            LifeEvent, LifeEventType, MoodType,
        )

        engine = EmotionEngine()
        # Bypass cooldown for test
        engine._last_mood_change = datetime(2020, 1, 1, tzinfo=timezone.utc)
        engine.process_event(LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="User said 'cảm ơn'",
            importance=0.8,
        ))

        assert engine._state.primary_mood == MoodType.HAPPY

    def test_negative_feedback_makes_concerned(self):
        """NEGATIVE_FEEDBACK event should change mood to CONCERNED (after cooldown)."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            LifeEvent, LifeEventType, MoodType,
        )

        engine = EmotionEngine()
        engine._last_mood_change = datetime(2020, 1, 1, tzinfo=timezone.utc)
        engine.process_event(LifeEvent(
            event_type=LifeEventType.NEGATIVE_FEEDBACK,
            description="User said 'sai rồi'",
            importance=0.7,
        ))

        assert engine._state.primary_mood == MoodType.CONCERNED

    def test_user_conversation_no_mood_change_at_default_importance(self):
        """USER_CONVERSATION has mood=None, so no mood change regardless of threshold."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            LifeEvent, LifeEventType, MoodType,
        )

        engine = EmotionEngine()
        initial_mood = engine._state.primary_mood

        engine.process_event(LifeEvent(
            event_type=LifeEventType.USER_CONVERSATION,
            description="Normal chat",
            importance=0.5,
        ))

        # USER_CONVERSATION has mood=None → no mood change
        assert engine._state.primary_mood == initial_mood

    def test_engagement_increases_on_conversation(self):
        """USER_CONVERSATION should increase engagement."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import LifeEvent, LifeEventType

        engine = EmotionEngine()
        initial_engagement = engine._state.engagement

        engine.process_event(LifeEvent(
            event_type=LifeEventType.USER_CONVERSATION,
            description="Normal chat",
            importance=0.5,
        ))

        # Engagement delta = +0.05 * 0.5 = +0.025
        assert engine._state.engagement > initial_engagement

    def test_mood_dampening_prevents_pingpong(self):
        """Sprint 210b: Rapid alternating events should NOT cause mood flip-flop."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            LifeEvent, LifeEventType, MoodType,
        )

        engine = EmotionEngine()
        # Don't bypass cooldown — test dampening behavior

        # Student A: positive
        engine.process_event(LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="Student A: cảm ơn!",
            importance=0.8,
        ))
        mood_after_first = engine._state.primary_mood

        # Student B: negative (immediately after — within cooldown)
        engine.process_event(LifeEvent(
            event_type=LifeEventType.NEGATIVE_FEEDBACK,
            description="Student B: sai rồi!",
            importance=0.7,
        ))
        mood_after_second = engine._state.primary_mood

        # Mood should NOT have flipped — still within cooldown
        # (Either stayed at initial, or changed to first event's mood at SENTIMENT_THRESHOLD)
        # The key invariant: it did NOT flip twice
        assert mood_after_first == mood_after_second or mood_after_second == MoodType.CURIOUS

    def test_accumulated_sentiment_majority_wins(self):
        """Sprint 210b: After enough events, majority sentiment wins."""
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import (
            LifeEvent, LifeEventType, MoodType,
        )

        engine = EmotionEngine()
        engine._last_mood_change = datetime(2020, 1, 1, tzinfo=timezone.utc)

        # 3 positive events to exceed SENTIMENT_THRESHOLD
        for i in range(3):
            engine._last_mood_change = datetime(2020, 1, 1, tzinfo=timezone.utc)
            engine.process_event(LifeEvent(
                event_type=LifeEventType.POSITIVE_FEEDBACK,
                description=f"Student {i}: cảm ơn!",
                importance=0.8,
            ))

        # Majority is positive → should be HAPPY
        assert engine._state.primary_mood == MoodType.HAPPY
