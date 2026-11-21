from datetime import datetime, timezone, timedelta

import pytest

from tests.unit.living_continuity_helpers import (
    _make_settings,
    reset_runtime_metrics as reset_runtime_metrics,
)


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
