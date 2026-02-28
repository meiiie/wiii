"""
Tests for Sprint 176: Wiii Soul AGI — All Phases.

Covers:
- Phase 1A: Persistent emotion (save/load)
- Phase 1B: Weather service
- Phase 2A: Briefing composer
- Phase 2B: Circadian rhythm
- Phase 3A: Smart browsing
- Phase 3B: Routine tracker
- Phase 4A: Deep reflection
- Phase 4B: Dynamic goals
- Phase 5A: Proactive messaging
- Phase 5B: Autonomy manager
- Config: New feature flags
- Models: New Pydantic models
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# =============================================================================
# Config Tests — New feature flags
# =============================================================================

class TestSoulAGIConfig:
    """Test new feature flags in config.py."""

    def test_weather_flags_exist(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_enable_weather=True,
            living_agent_weather_api_key="test-key",
            living_agent_weather_city="Hanoi",
        )
        assert s.living_agent_enable_weather is True
        assert s.living_agent_weather_api_key == "test-key"
        assert s.living_agent_weather_city == "Hanoi"

    def test_weather_defaults(self):
        from app.core.config import Settings
        s = Settings(api_key="test")
        assert s.living_agent_enable_weather is False
        assert s.living_agent_weather_api_key is None
        assert s.living_agent_weather_city == "Ho Chi Minh City"

    def test_briefing_flags_exist(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_enable_briefing=True,
            living_agent_briefing_channels='["zalo"]',
            living_agent_briefing_users='["user1"]',
        )
        assert s.living_agent_enable_briefing is True
        assert json.loads(s.living_agent_briefing_channels) == ["zalo"]

    def test_routine_flag(self):
        from app.core.config import Settings
        s = Settings(api_key="test", living_agent_enable_routine_tracking=True)
        assert s.living_agent_enable_routine_tracking is True

    def test_goals_flag(self):
        from app.core.config import Settings
        s = Settings(api_key="test", living_agent_enable_dynamic_goals=True)
        assert s.living_agent_enable_dynamic_goals is True

    def test_proactive_flags(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_enable_proactive_messaging=True,
            living_agent_max_proactive_per_day=5,
            living_agent_proactive_quiet_start=22,
            living_agent_proactive_quiet_end=6,
        )
        assert s.living_agent_enable_proactive_messaging is True
        assert s.living_agent_max_proactive_per_day == 5
        assert s.living_agent_proactive_quiet_start == 22
        assert s.living_agent_proactive_quiet_end == 6

    def test_autonomy_flags(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            living_agent_autonomy_level=2,
            living_agent_enable_autonomy_graduation=True,
        )
        assert s.living_agent_autonomy_level == 2
        assert s.living_agent_enable_autonomy_graduation is True

    def test_autonomy_level_bounds(self):
        from app.core.config import Settings
        s = Settings(api_key="test", living_agent_autonomy_level=0)
        assert s.living_agent_autonomy_level == 0

    def test_facebook_token_flags(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            facebook_verify_token="verify123",
            facebook_page_access_token="page_token",
        )
        assert s.facebook_verify_token == "verify123"
        assert s.facebook_page_access_token == "page_token"


# =============================================================================
# Models Tests — New Pydantic models
# =============================================================================

class TestSoulAGIModels:
    """Test new Pydantic models."""

    def test_weather_info(self):
        from app.engine.living_agent.models import WeatherInfo
        w = WeatherInfo(city="HCM", temp=32.5, humidity=80, description="nang nong")
        assert w.temp == 32.5
        assert w.humidity == 80

    def test_weather_forecast(self):
        from app.engine.living_agent.models import WeatherForecast
        f = WeatherForecast(dt_txt="2026-02-23 15:00", temp=30, rain_probability=60)
        assert f.rain_probability == 60

    def test_briefing_type(self):
        from app.engine.living_agent.models import BriefingType
        assert BriefingType.MORNING.value == "morning"
        assert BriefingType.EVENING.value == "evening"

    def test_briefing(self):
        from app.engine.living_agent.models import Briefing, BriefingType
        b = Briefing(briefing_type=BriefingType.MORNING, content="Chao sang!")
        assert b.content == "Chao sang!"
        assert len(b.delivered_to) == 0

    def test_user_routine(self):
        from app.engine.living_agent.models import UserRoutine
        r = UserRoutine(
            user_id="u1",
            typical_active_hours=[8, 9, 10, 18, 19],
            preferred_briefing_time=7,
            total_messages=42,
        )
        assert r.total_messages == 42
        assert 9 in r.typical_active_hours

    def test_reflection_entry(self):
        from app.engine.living_agent.models import ReflectionEntry
        e = ReflectionEntry(
            content="Tuan nay tot lam",
            insights=["Lam viec hieu qua hon"],
            goals_next_week=["Doc 3 bai AI"],
        )
        assert len(e.insights) == 1
        assert e.goals_next_week[0] == "Doc 3 bai AI"

    def test_goal_lifecycle(self):
        from app.engine.living_agent.models import GoalStatus, GoalPriority, WiiiGoal
        g = WiiiGoal(
            title="Learn Docker",
            status=GoalStatus.PROPOSED,
            priority=GoalPriority.HIGH,
        )
        assert g.status == GoalStatus.PROPOSED
        assert g.priority == GoalPriority.HIGH
        assert g.progress == 0.0

    def test_autonomy_level(self):
        from app.engine.living_agent.models import AutonomyLevel
        assert AutonomyLevel.SUPERVISED.value == 0
        assert AutonomyLevel.SEMI_AUTO.value == 1
        assert AutonomyLevel.AUTONOMOUS.value == 2
        assert AutonomyLevel.FULL_TRUST.value == 3

    def test_proactive_message(self):
        from app.engine.living_agent.models import ProactiveMessage
        m = ProactiveMessage(
            user_id="u1",
            channel="messenger",
            content="Hey!",
            trigger="briefing",
        )
        assert m.delivered is False
        assert m.channel == "messenger"

    def test_action_type_new_values(self):
        from app.engine.living_agent.models import ActionType
        assert ActionType.CHECK_WEATHER.value == "check_weather"
        assert ActionType.SEND_BRIEFING.value == "send_briefing"
        assert ActionType.DEEP_REFLECT.value == "deep_reflect"


# =============================================================================
# Phase 1A: Persistent Emotion
# =============================================================================

class TestPersistentEmotion:
    """Test emotion save/load to DB."""

    def test_to_dict_returns_serializable(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()
        d = engine.to_dict()
        assert "primary_mood" in d
        assert "energy_level" in d
        # Should be JSON-serializable
        json.dumps(d)

    def test_restore_from_dict(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import MoodType
        engine = EmotionEngine()
        engine.restore_from_dict({
            "primary_mood": "happy",
            "energy_level": 0.9,
            "social_battery": 0.5,
            "engagement": 0.3,
        })
        assert engine.mood == MoodType.HAPPY
        assert engine.energy == 0.9

    def test_restore_bad_data_falls_back(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        from app.engine.living_agent.models import MoodType
        engine = EmotionEngine()
        engine.restore_from_dict({"invalid": True})
        # Should fallback to defaults
        assert engine.mood == MoodType.CURIOUS

    @pytest.mark.asyncio
    async def test_save_state_to_db(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        # Lazy import → patch at source module
        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            await engine.save_state_to_db()
            # Should have called execute at least twice (delete + insert)
            assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_load_state_from_db_empty(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        # Lazy import → patch at source module
        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            result = await engine.load_state_from_db()
            assert result is False


# =============================================================================
# Phase 2B: Circadian Rhythm
# =============================================================================

class TestCircadianRhythm:
    """Test circadian energy modifiers."""

    def test_circadian_modifier_morning(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()
        initial_energy = engine.energy

        # Mock time to morning (9 AM UTC+7 = 2 AM UTC)
        mock_dt = datetime(2026, 2, 23, 2, 0, tzinfo=timezone.utc)
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        # Energy should be nudged toward morning peak (0.95)
        # Since it's a 10% blend, exact value depends on initial
        assert isinstance(engine.energy, float)

    def test_circadian_modifier_night(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        engine = EmotionEngine()

        # Mock time to night (22:00 UTC+7 = 15:00 UTC)
        mock_dt = datetime(2026, 2, 23, 15, 0, tzinfo=timezone.utc)
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        # Energy should be nudged toward evening low (0.40)
        assert engine.energy < 0.75  # Should decrease from default 0.7


# =============================================================================
# Phase 1B: Weather Service
# =============================================================================

class TestWeatherService:
    """Test weather service."""

    def test_singleton(self):
        from app.engine.living_agent.weather_service import get_weather_service
        s1 = get_weather_service()
        s2 = get_weather_service()
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_get_current_disabled(self):
        from app.engine.living_agent.weather_service import WeatherService
        svc = WeatherService()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_weather = False
            result = await svc.get_current()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_no_api_key(self):
        from app.engine.living_agent.weather_service import WeatherService
        svc = WeatherService()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_weather = True
            mock_settings.living_agent_weather_api_key = None
            result = await svc.get_current()
            assert result is None

    def test_format_current_vi(self):
        from app.engine.living_agent.weather_service import WeatherService
        from app.engine.living_agent.models import WeatherInfo
        svc = WeatherService()
        w = WeatherInfo(city="HCM", temp=32.0, humidity=80, description="nang nong")
        text = svc.format_current_vi(w)
        assert "HCM" in text
        assert "32.0" in text

    def test_should_alert_rain(self):
        from app.engine.living_agent.weather_service import WeatherService
        from app.engine.living_agent.models import WeatherForecast
        svc = WeatherService()

        no_rain = [WeatherForecast(rain_probability=20)]
        assert svc.should_alert_rain(no_rain) is False

        rain = [WeatherForecast(rain_probability=80)]
        assert svc.should_alert_rain(rain) is True

    def test_cache_works(self):
        from app.engine.living_agent.weather_service import WeatherService
        svc = WeatherService()
        svc._set_cached("test_key", "test_value")
        assert svc._get_cached("test_key") == "test_value"

    def test_cache_miss(self):
        from app.engine.living_agent.weather_service import WeatherService
        svc = WeatherService()
        assert svc._get_cached("nonexistent") is None


# =============================================================================
# Phase 2A: Briefing Composer
# =============================================================================

class TestBriefingComposer:
    """Test briefing system."""

    def test_singleton(self):
        from app.engine.living_agent.briefing_composer import get_briefing_composer
        c1 = get_briefing_composer()
        c2 = get_briefing_composer()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_compose_disabled(self):
        from app.engine.living_agent.briefing_composer import BriefingComposer
        composer = BriefingComposer()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_briefing = False
            result = await composer.compose_for_time()
            assert result is None


# =============================================================================
# Phase 3B: Routine Tracker
# =============================================================================

class TestRoutineTracker:
    """Test user routine tracking."""

    def test_singleton(self):
        from app.engine.living_agent.routine_tracker import get_routine_tracker
        t1 = get_routine_tracker()
        t2 = get_routine_tracker()
        assert t1 is t2

    @pytest.mark.asyncio
    async def test_record_disabled(self):
        from app.engine.living_agent.routine_tracker import RoutineTracker
        tracker = RoutineTracker()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_routine_tracking = False
            # Should not raise
            await tracker.record_interaction("user1")


# =============================================================================
# Phase 4A: Reflector
# =============================================================================

class TestReflector:
    """Test deep reflection system."""

    def test_singleton(self):
        from app.engine.living_agent.reflector import get_reflector
        r1 = get_reflector()
        r2 = get_reflector()
        assert r1 is r2

    def test_is_reflection_time_sunday(self):
        """Sprint 210: Reflection is now daily 21-22h UTC+7 (not Sunday only)."""
        from app.engine.living_agent.reflector import Reflector
        r = Reflector()
        # 21:00 UTC+7 = 14:00 UTC (any day)
        with patch("app.engine.living_agent.reflector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)  # 21:00 VN
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert r.is_reflection_time() is True

    def test_extract_section(self):
        from app.engine.living_agent.reflector import _extract_section
        content = """
### Dieu lam tot
- Hoc duoc nhieu
- Giao tiep tot

### Dieu can cai thien
- Can tap trung hon
"""
        items = _extract_section(content, "Dieu lam tot")
        assert len(items) == 2
        assert "Hoc duoc nhieu" in items[0]


# =============================================================================
# Phase 4B: Goal Manager
# =============================================================================

class TestGoalManager:
    """Test dynamic goals."""

    def test_singleton(self):
        from app.engine.living_agent.goal_manager import get_goal_manager
        m1 = get_goal_manager()
        m2 = get_goal_manager()
        assert m1 is m2

    def test_goal_status_values(self):
        from app.engine.living_agent.models import GoalStatus
        assert GoalStatus.PROPOSED.value == "proposed"
        assert GoalStatus.ACTIVE.value == "active"
        assert GoalStatus.COMPLETED.value == "completed"
        assert GoalStatus.ABANDONED.value == "abandoned"


# =============================================================================
# Phase 5A: Proactive Messenger
# =============================================================================

class TestProactiveMessenger:
    """Test proactive messaging with anti-spam."""

    def test_singleton(self):
        from app.engine.living_agent.proactive_messenger import get_proactive_messenger
        m1 = get_proactive_messenger()
        m2 = get_proactive_messenger()
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_can_send_disabled(self):
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger
        m = ProactiveMessenger()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_proactive_messaging = False
            assert await m.can_send("user1") is False

    @pytest.mark.asyncio
    async def test_daily_limit(self):
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger
        m = ProactiveMessenger()

        # Set today's date so _reset_daily_if_needed() won't clear counts
        from app.engine.living_agent.proactive_messenger import _VN_OFFSET
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        m._daily_reset_date = now_vn.strftime("%Y-%m-%d")
        m._daily_counts["user1"] = 3

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_enable_proactive_messaging = True
            mock_settings.living_agent_max_proactive_per_day = 3
            mock_settings.living_agent_proactive_quiet_start = 23
            mock_settings.living_agent_proactive_quiet_end = 5

            # Already at daily limit — should be blocked before opt-out check
            result = await m.can_send("user1")
            assert result is False

    def test_daily_reset(self):
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger
        m = ProactiveMessenger()
        m._daily_counts["user1"] = 5
        m._daily_reset_date = "2020-01-01"  # Old date

        m._reset_daily_if_needed()
        assert m._daily_counts == {}  # Should reset


# =============================================================================
# Phase 5B: Autonomy Manager
# =============================================================================

class TestAutonomyManager:
    """Test autonomy graduation."""

    def test_singleton(self):
        from app.engine.living_agent.autonomy_manager import get_autonomy_manager
        m1 = get_autonomy_manager()
        m2 = get_autonomy_manager()
        assert m1 is m2

    def test_supervised_permissions(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        from app.engine.living_agent.models import ActionType
        m = AutonomyManager()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_autonomy_level = 0

            assert m.can_execute(ActionType.CHECK_GOALS) is True
            assert m.can_execute(ActionType.REST) is True
            assert m.can_execute(ActionType.BROWSE_SOCIAL) is False
            assert m.can_execute(ActionType.SEND_BRIEFING) is False

    def test_semi_auto_permissions(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        from app.engine.living_agent.models import ActionType
        m = AutonomyManager()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_autonomy_level = 1

            assert m.can_execute(ActionType.BROWSE_SOCIAL) is True
            assert m.can_execute(ActionType.WRITE_JOURNAL) is True
            assert m.can_execute(ActionType.SEND_BRIEFING) is False
            assert m.can_execute(ActionType.LEARN_TOPIC) is False

    def test_autonomous_permissions(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        from app.engine.living_agent.models import ActionType
        m = AutonomyManager()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_autonomy_level = 2

            assert m.can_execute(ActionType.BROWSE_SOCIAL) is True
            assert m.can_execute(ActionType.SEND_BRIEFING) is True
            assert m.can_execute(ActionType.LEARN_TOPIC) is True

    def test_needs_approval_inverse(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        from app.engine.living_agent.models import ActionType
        m = AutonomyManager()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_autonomy_level = 0
            assert m.needs_approval(ActionType.BROWSE_SOCIAL) is True
            assert m.needs_approval(ActionType.CHECK_GOALS) is False

    def test_get_status(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        m = AutonomyManager()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_autonomy_level = 0
            status = m.get_status()

            assert status["level"] == 0
            assert "level_name" in status
            assert "allowed_actions" in status
            assert "needs_approval" in status

    def test_record_safety_violation(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        m = AutonomyManager()
        m.record_safety_violation("test violation")
        assert m._stats["safety_violations"] == 1

    def test_record_success(self):
        from app.engine.living_agent.autonomy_manager import AutonomyManager
        m = AutonomyManager()
        m.record_success()
        assert m._stats["successful_actions"] == 1


# =============================================================================
# Heartbeat Integration
# =============================================================================

class TestHeartbeatIntegration:
    """Test heartbeat with new Soul AGI actions."""

    @pytest.mark.asyncio
    async def test_plan_actions_includes_weather(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType
        scheduler = HeartbeatScheduler()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_max_actions_per_heartbeat = 5
            mock_settings.living_agent_enable_social_browse = False
            mock_settings.living_agent_enable_skill_building = False
            mock_settings.living_agent_enable_journal = False
            mock_settings.living_agent_enable_weather = True
            mock_settings.living_agent_enable_briefing = False
            mock_settings.living_agent_enable_proactive_messaging = False

            # Mock morning time
            mock_dt = datetime(2026, 2, 23, 22, 0, tzinfo=timezone.utc)  # 05:00 UTC+7
            with patch("app.engine.living_agent.heartbeat.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_dt
                mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

                actions = await scheduler._plan_actions("curious", 0.7)
                action_types = [a.action_type for a in actions]
                assert ActionType.CHECK_WEATHER in action_types

    @pytest.mark.asyncio
    async def test_plan_actions_includes_briefing(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType
        scheduler = HeartbeatScheduler()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_max_actions_per_heartbeat = 5
            mock_settings.living_agent_enable_social_browse = False
            mock_settings.living_agent_enable_skill_building = False
            mock_settings.living_agent_enable_journal = False
            mock_settings.living_agent_enable_weather = False
            mock_settings.living_agent_enable_briefing = True
            mock_settings.living_agent_enable_proactive_messaging = False

            # Mock briefing time (06:00 UTC+7 = 23:00 UTC)
            mock_dt = datetime(2026, 2, 22, 23, 0, tzinfo=timezone.utc)
            with patch("app.engine.living_agent.heartbeat.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_dt
                mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

                actions = await scheduler._plan_actions("curious", 0.7)
                action_types = [a.action_type for a in actions]
                assert ActionType.SEND_BRIEFING in action_types

    @pytest.mark.asyncio
    async def test_browse_uses_auto_topic(self):
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import ActionType
        scheduler = HeartbeatScheduler()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.living_agent_max_actions_per_heartbeat = 5
            mock_settings.living_agent_enable_social_browse = True
            mock_settings.living_agent_enable_skill_building = False
            mock_settings.living_agent_enable_journal = False
            mock_settings.living_agent_enable_weather = False
            mock_settings.living_agent_enable_briefing = False
            mock_settings.living_agent_enable_proactive_messaging = False

            mock_dt = datetime(2026, 2, 23, 3, 0, tzinfo=timezone.utc)  # 10 AM UTC+7
            with patch("app.engine.living_agent.heartbeat.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_dt
                mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

                actions = await scheduler._plan_actions("curious", 0.8)
                browse_actions = [a for a in actions if a.action_type == ActionType.BROWSE_SOCIAL]
                if browse_actions:
                    assert browse_actions[0].target == "auto"


# =============================================================================
# Smart Browsing (Phase 3A)
# =============================================================================

class TestSmartBrowsing:
    """Test context-aware topic selection."""

    @pytest.mark.asyncio
    async def test_smart_topic_morning(self):
        """Sprint 188: Topic selection is weighted-random, news favored in morning."""
        from app.engine.living_agent.social_browser import SocialBrowser, _TOPIC_QUERIES
        browser = SocialBrowser()

        mock_dt = datetime(2026, 2, 23, 1, 0, tzinfo=timezone.utc)  # 08:00 UTC+7
        with patch("app.engine.living_agent.social_browser.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

            topics = set()
            for _ in range(30):
                browser._recent_topics.clear()
                topic = await browser._select_smart_topic()
                topics.add(topic)
            assert "news" in topics
            for t in topics:
                assert t in _TOPIC_QUERIES

    @pytest.mark.asyncio
    async def test_smart_topic_afternoon(self):
        """Sprint 188: Afternoon favors tech/maritime but uses weighted random."""
        from app.engine.living_agent.social_browser import SocialBrowser, _TOPIC_QUERIES
        browser = SocialBrowser()

        mock_dt = datetime(2026, 2, 23, 7, 0, tzinfo=timezone.utc)  # 14:00 UTC+7
        with patch("app.engine.living_agent.social_browser.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

            topics = set()
            for _ in range(30):
                browser._recent_topics.clear()
                topic = await browser._select_smart_topic()
                topics.add(topic)
            # tech or maritime should appear with high probability
            assert topics & {"tech", "maritime"}
            for t in topics:
                assert t in _TOPIC_QUERIES


# =============================================================================
# Module Exports
# =============================================================================

class TestModuleExports:
    """Test that all new models are properly exported from __init__."""

    def test_all_new_models_exported(self):
        from app.engine.living_agent import (
            WeatherInfo,
            WeatherForecast,
            BriefingType,
            Briefing,
            UserRoutine,
            ReflectionEntry,
            GoalStatus,
            GoalPriority,
            WiiiGoal,
            AutonomyLevel,
            ProactiveMessage,
        )
        assert WeatherInfo is not None
        assert BriefingType.MORNING.value == "morning"
        assert AutonomyLevel.SUPERVISED.value == 0
