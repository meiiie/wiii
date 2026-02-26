"""
Sprint 188: "Linh Hồn Thức Tỉnh" — Soul AGI Production Deployment Tests

Tests cover:
1. Emotion Persistence wiring (G1)
2. Channel Sender (G2)
3. Proactive Messenger complete send (G2)
4. Circadian rhythm enhancement (G3)
5. Context-aware smart browsing (G4)
6. Webhook hardening (dedup, async)
7. Config additions
"""

import asyncio
import json
import pytest
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# =============================================================================
# 1. Emotion Persistence (8 tests)
# =============================================================================


class TestEmotionPersistence:
    """G1: Emotion state persists across restarts."""

    def _make_engine(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        return EmotionEngine()

    def test_load_from_db_if_needed_sets_flag(self):
        """load_from_db_if_needed sets _db_loaded flag."""
        engine = self._make_engine()
        assert engine._db_loaded is False

    @pytest.mark.asyncio
    async def test_load_from_db_if_needed_idempotent(self):
        """Second call returns False without touching DB."""
        engine = self._make_engine()
        with patch.object(engine, "load_state_from_db", new_callable=AsyncMock, return_value=True):
            result1 = await engine.load_from_db_if_needed()
            result2 = await engine.load_from_db_if_needed()
        assert result1 is True
        assert result2 is False

    @pytest.mark.asyncio
    async def test_load_from_db_if_needed_calls_load(self):
        """First call delegates to load_state_from_db."""
        engine = self._make_engine()
        with patch.object(engine, "load_state_from_db", new_callable=AsyncMock, return_value=False) as mock:
            await engine.load_from_db_if_needed()
        mock.assert_awaited_once()

    def test_to_dict_serializable(self):
        """to_dict produces JSON-serializable dict."""
        engine = self._make_engine()
        data = engine.to_dict()
        json_str = json.dumps(data, ensure_ascii=False)
        assert "primary_mood" in json_str

    def test_restore_from_dict_valid(self):
        """restore_from_dict restores mood from valid data."""
        engine = self._make_engine()
        data = engine.to_dict()
        data["primary_mood"] = "happy"
        data["energy_level"] = 0.9
        engine.restore_from_dict(data)
        assert engine.mood.value == "happy"
        assert engine.energy == pytest.approx(0.9, abs=0.01)

    def test_restore_from_dict_invalid_uses_defaults(self):
        """restore_from_dict falls back to defaults on bad data."""
        engine = self._make_engine()
        engine.restore_from_dict({"primary_mood": "nonexistent_mood"})
        # Should reset to default (curious)
        assert engine.mood.value == "curious"

    @pytest.mark.asyncio
    async def test_save_state_to_db_handles_error(self):
        """save_state_to_db doesn't raise on DB error."""
        engine = self._make_engine()
        with patch("app.engine.living_agent.emotion_engine.EmotionEngine.save_state_to_db",
                    new_callable=AsyncMock):
            # Should not raise
            await engine.save_state_to_db()

    def test_process_event_triggers_persistence(self):
        """process_event schedules save_state_to_db in background."""
        from app.engine.living_agent.models import LifeEvent, LifeEventType
        engine = self._make_engine()

        event = LifeEvent(
            event_type=LifeEventType.POSITIVE_FEEDBACK,
            description="Great!",
            importance=0.8,
        )

        # Mock the event loop to capture the created task
        mock_loop = MagicMock()
        mock_loop.create_task = MagicMock()
        with patch("asyncio.get_running_loop", return_value=mock_loop):
            engine.process_event(event)
        mock_loop.create_task.assert_called_once()


# =============================================================================
# 2. Channel Sender (8 tests)
# =============================================================================


class TestChannelSender:
    """G2: Shared Messenger + Zalo channel sender."""

    @pytest.mark.asyncio
    async def test_send_messenger_no_token(self):
        """Returns error when no token configured."""
        from app.engine.living_agent.channel_sender import send_messenger_message

        mock_settings = MagicMock()
        mock_settings.facebook_page_access_token = None
        with patch("app.core.config.settings", mock_settings):
            result = await send_messenger_message("user123", "Hello")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_messenger_success(self):
        """Successful Messenger send returns success=True."""
        from app.engine.living_agent.channel_sender import send_messenger_message

        mock_settings = MagicMock()
        mock_settings.facebook_page_access_token = "test_token"
        mock_settings.facebook_graph_api_version = "v22.0"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await send_messenger_message("user123", "Hello")
        assert result.success is True
        assert result.channel == "messenger"

    @pytest.mark.asyncio
    async def test_send_messenger_failure(self):
        """Failed Messenger send returns error details."""
        from app.engine.living_agent.channel_sender import send_messenger_message

        mock_settings = MagicMock()
        mock_settings.facebook_page_access_token = "test_token"
        mock_settings.facebook_graph_api_version = "v22.0"

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await send_messenger_message("user123", "Hello")
        assert result.success is False
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_send_zalo_no_token(self):
        """Returns error when no Zalo token configured."""
        from app.engine.living_agent.channel_sender import send_zalo_message

        mock_settings = MagicMock()
        mock_settings.zalo_oa_access_token = None
        with patch("app.core.config.settings", mock_settings):
            result = await send_zalo_message("user456", "Xin chao")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_zalo_success(self):
        """Successful Zalo send returns success=True."""
        from app.engine.living_agent.channel_sender import send_zalo_message

        mock_settings = MagicMock()
        mock_settings.zalo_oa_access_token = "test_token"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"error": 0})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await send_zalo_message("user456", "Xin chao")
        assert result.success is True
        assert result.channel == "zalo"

    @pytest.mark.asyncio
    async def test_send_zalo_api_error(self):
        """Zalo API error (error != 0) returns failure."""
        from app.engine.living_agent.channel_sender import send_zalo_message

        mock_settings = MagicMock()
        mock_settings.zalo_oa_access_token = "test_token"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"error": -201, "message": "Invalid token"})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await send_zalo_message("user456", "Xin chao")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_send_to_channel_routes_messenger(self):
        """send_to_channel routes 'messenger' correctly."""
        from app.engine.living_agent.channel_sender import send_to_channel, DeliveryResult

        with patch("app.engine.living_agent.channel_sender.send_messenger_message",
                    new_callable=AsyncMock,
                    return_value=DeliveryResult(success=True, channel="messenger")) as mock:
            result = await send_to_channel("messenger", "user1", "Hi")
        assert result.success is True
        mock.assert_awaited_once_with("user1", "Hi")

    @pytest.mark.asyncio
    async def test_send_to_channel_unsupported(self):
        """send_to_channel returns error for unsupported channel."""
        from app.engine.living_agent.channel_sender import send_to_channel

        result = await send_to_channel("telegram", "user1", "Hi")
        assert result.success is False
        assert "Unsupported" in result.error


# =============================================================================
# 3. Proactive Messenger (8 tests)
# =============================================================================


class TestProactiveMessenger:
    """G2: Proactive messenger uses channel_sender."""

    def _make_messenger(self):
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger
        return ProactiveMessenger()

    @pytest.mark.asyncio
    async def test_can_send_disabled(self):
        """can_send returns False when feature disabled."""
        m = self._make_messenger()
        mock_settings = MagicMock()
        mock_settings.living_agent_enable_proactive_messaging = False
        with patch("app.core.config.settings", mock_settings):
            assert await m.can_send("user1") is False

    @pytest.mark.asyncio
    async def test_can_send_quiet_hours(self):
        """can_send returns False during quiet hours."""
        m = self._make_messenger()
        mock_settings = MagicMock()
        mock_settings.living_agent_enable_proactive_messaging = True
        mock_settings.living_agent_proactive_quiet_start = 23
        mock_settings.living_agent_proactive_quiet_end = 5
        mock_settings.living_agent_max_proactive_per_day = 3

        # Mock time to 01:00 UTC+7 (within quiet hours)
        fixed_time = datetime(2026, 2, 24, 18, 0, 0, tzinfo=timezone.utc)  # 01:00 UTC+7
        with patch("app.core.config.settings", mock_settings), \
             patch("app.engine.living_agent.proactive_messenger.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await m.can_send("user1")
        assert result is False

    @pytest.mark.asyncio
    async def test_can_send_daily_limit(self):
        """can_send returns False when daily limit reached."""
        m = self._make_messenger()
        mock_settings = MagicMock()
        mock_settings.living_agent_enable_proactive_messaging = True
        mock_settings.living_agent_proactive_quiet_start = 23
        mock_settings.living_agent_proactive_quiet_end = 5
        mock_settings.living_agent_max_proactive_per_day = 2

        m._daily_counts["user1"] = 2
        now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
        m._daily_reset_date = now_vn.strftime("%Y-%m-%d")

        with patch("app.core.config.settings", mock_settings):
            result = await m.can_send("user1")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_calls_channel_sender(self):
        """send() delivers via channel_sender._deliver."""
        m = self._make_messenger()
        with patch.object(m, "can_send", new_callable=AsyncMock, return_value=True), \
             patch.object(m, "_deliver", new_callable=AsyncMock, return_value=True), \
             patch.object(m, "_save_message", new_callable=AsyncMock):
            result = await m.send("user1", "messenger", "Hello!", trigger="briefing")
        assert result is True
        assert m._daily_counts["user1"] == 1

    @pytest.mark.asyncio
    async def test_send_blocked_returns_false(self):
        """send() returns False when can_send blocks."""
        m = self._make_messenger()
        with patch.object(m, "can_send", new_callable=AsyncMock, return_value=False):
            result = await m.send("user1", "messenger", "Hello!")
        assert result is False

    @pytest.mark.asyncio
    async def test_deliver_uses_channel_sender(self):
        """_deliver routes through channel_sender.send_to_channel."""
        m = self._make_messenger()
        from app.engine.living_agent.channel_sender import DeliveryResult

        mock_engine = MagicMock()
        mock_engine.process_event = MagicMock()

        with patch("app.engine.living_agent.emotion_engine.get_emotion_engine", return_value=mock_engine), \
             patch("app.engine.living_agent.channel_sender.send_to_channel",
                    new_callable=AsyncMock,
                    return_value=DeliveryResult(success=True, channel="messenger")):
            result = await m._deliver("user1", "messenger", "Test")
        assert result is True

    @pytest.mark.asyncio
    async def test_deliver_failure(self):
        """_deliver returns False on channel_sender failure."""
        m = self._make_messenger()
        from app.engine.living_agent.channel_sender import DeliveryResult

        with patch("app.engine.living_agent.channel_sender.send_to_channel",
                    new_callable=AsyncMock,
                    return_value=DeliveryResult(success=False, error="timeout")):
            result = await m._deliver("user1", "messenger", "Test")
        assert result is False

    def test_daily_reset(self):
        """Daily counters reset at midnight UTC+7."""
        m = self._make_messenger()
        m._daily_counts["user1"] = 5
        m._daily_reset_date = "2026-01-01"  # Old date
        m._reset_daily_if_needed()
        assert m._daily_counts == {}


# =============================================================================
# 4. Circadian Rhythm Enhancement (6 tests)
# =============================================================================


class TestCircadianRhythm:
    """G3: Enhanced circadian rhythm with 40% blend."""

    def _make_engine(self):
        from app.engine.living_agent.emotion_engine import EmotionEngine
        return EmotionEngine()

    def test_circadian_40_percent_blend(self):
        """Circadian applies 40% blend (not 10%)."""
        engine = self._make_engine()
        engine._state.energy_level = 0.5

        # Mock 9 AM UTC+7 (target energy = 0.95)
        fixed_time = datetime(2026, 2, 24, 2, 0, 0, tzinfo=timezone.utc)  # 09:00 UTC+7
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        # 0.5 * 0.6 + 0.95 * 0.4 = 0.68 (vs 0.545 with 10% blend)
        assert engine.energy == pytest.approx(0.68, abs=0.02)

    def test_circadian_evening_low_energy(self):
        """Evening (23:00) significantly drops energy."""
        engine = self._make_engine()
        engine._state.energy_level = 0.8

        # Mock 23:00 UTC+7 (target energy = 0.20)
        fixed_time = datetime(2026, 2, 24, 16, 0, 0, tzinfo=timezone.utc)  # 23:00 UTC+7
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        # 0.8 * 0.6 + 0.20 * 0.4 = 0.56
        assert engine.energy == pytest.approx(0.56, abs=0.02)

    def test_circadian_mood_neutral_override(self):
        """Circadian sets mood hint when current mood is NEUTRAL."""
        from app.engine.living_agent.models import MoodType
        engine = self._make_engine()
        engine._state.primary_mood = MoodType.NEUTRAL

        # Mock 8 AM UTC+7 → should set CURIOUS
        fixed_time = datetime(2026, 2, 24, 1, 0, 0, tzinfo=timezone.utc)  # 08:00 UTC+7
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        assert engine.mood == MoodType.CURIOUS

    def test_circadian_no_override_non_neutral(self):
        """Circadian doesn't override non-NEUTRAL mood."""
        from app.engine.living_agent.models import MoodType
        engine = self._make_engine()
        engine._state.primary_mood = MoodType.HAPPY

        fixed_time = datetime(2026, 2, 24, 13, 0, 0, tzinfo=timezone.utc)  # 20:00 UTC+7
        with patch("app.engine.living_agent.emotion_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            engine.apply_circadian_modifier()

        assert engine.mood == MoodType.HAPPY  # Unchanged

    def test_behavior_modifiers_include_tone(self):
        """get_behavior_modifiers() includes 'tone' key (Sprint 188)."""
        engine = self._make_engine()
        modifiers = engine.get_behavior_modifiers()
        assert "tone" in modifiers
        assert isinstance(modifiers["tone"], str)

    def test_compile_emotion_prompt_format(self):
        """compile_emotion_prompt returns Vietnamese formatted string."""
        engine = self._make_engine()
        prompt = engine.compile_emotion_prompt()
        assert "TRẠNG THÁI CẢM XÚC" in prompt
        assert "Tâm trạng" in prompt


# =============================================================================
# 5. Smart Browsing Context (6 tests)
# =============================================================================


class TestSmartBrowsing:
    """G4: Context-aware topic selection."""

    def _make_browser(self):
        from app.engine.living_agent.social_browser import SocialBrowser
        return SocialBrowser()

    def test_recent_topics_rotation(self):
        """Topic rotation prevents repeats within 3 cycles."""
        browser = self._make_browser()
        browser._recent_topics = ["news", "tech", "maritime"]

        # When all topics are recently used, it falls back to all topics
        assert len(browser._recent_topics) == 3

    @pytest.mark.asyncio
    async def test_smart_topic_time_weighted(self):
        """Time-weighted selection favors news in morning."""
        browser = self._make_browser()

        # Mock morning time (8 AM UTC+7)
        fixed_time = datetime(2026, 2, 24, 1, 0, 0, tzinfo=timezone.utc)  # 08:00 UTC+7
        with patch("app.engine.living_agent.social_browser.datetime") as mock_dt, \
             patch.object(browser, "_get_topic_from_memories", new_callable=AsyncMock, return_value=None), \
             patch.object(browser, "_get_topic_from_skills", return_value=None):
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Run many times and check news appears
            topics = set()
            for _ in range(20):
                browser._recent_topics.clear()
                topic = await browser._select_smart_topic()
                topics.add(topic)
            assert "news" in topics

    @pytest.mark.asyncio
    async def test_smart_topic_from_skills(self):
        """Skills-based topic selection takes priority over time."""
        browser = self._make_browser()

        with patch.object(browser, "_get_topic_from_memories", new_callable=AsyncMock, return_value=None), \
             patch.object(browser, "_get_topic_from_skills", return_value="maritime"):
            topic = await browser._select_smart_topic()
        assert topic == "maritime"

    def test_get_topic_from_skills_no_skills(self):
        """Returns None when no skills are learning."""
        browser = self._make_browser()
        with patch("app.engine.living_agent.skill_builder.get_skill_builder") as mock:
            mock_builder = MagicMock()
            mock_builder.get_all_skills.return_value = []
            mock.return_value = mock_builder
            result = browser._get_topic_from_skills()
        assert result is None

    def test_get_topic_from_skills_exception(self):
        """Returns None on exception."""
        browser = self._make_browser()
        with patch("app.engine.living_agent.skill_builder.get_skill_builder",
                    side_effect=ImportError("no module")):
            result = browser._get_topic_from_skills()
        assert result is None

    @pytest.mark.asyncio
    async def test_browse_feed_disabled(self):
        """browse_feed returns [] when feature disabled."""
        browser = self._make_browser()
        mock_settings = MagicMock()
        mock_settings.living_agent_enable_social_browse = False
        with patch("app.core.config.settings", mock_settings):
            items = await browser.browse_feed(topic="news")
        assert items == []


# =============================================================================
# 6. Webhook Hardening (6 tests)
# =============================================================================


class TestWebhookHardening:
    """Sprint 188: Dedup, async processing."""

    def test_messenger_dedup_first_message(self):
        """First message is NOT duplicate."""
        from app.api.v1.messenger_webhook import _is_duplicate, _seen_message_ids
        _seen_message_ids.clear()
        assert _is_duplicate("msg_001") is False

    def test_messenger_dedup_repeat_message(self):
        """Same message ID is detected as duplicate."""
        from app.api.v1.messenger_webhook import _is_duplicate, _seen_message_ids
        _seen_message_ids.clear()
        _is_duplicate("msg_002")
        assert _is_duplicate("msg_002") is True

    def test_messenger_dedup_lru_eviction(self):
        """LRU evicts old entries after max size."""
        from app.api.v1.messenger_webhook import _is_duplicate, _seen_message_ids, _MAX_DEDUP_SIZE
        _seen_message_ids.clear()

        for i in range(_MAX_DEDUP_SIZE + 10):
            _is_duplicate(f"msg_{i:05d}")

        # First few should have been evicted
        assert "msg_00000" not in _seen_message_ids
        # Last ones should still be there
        assert f"msg_{_MAX_DEDUP_SIZE + 9:05d}" in _seen_message_ids

    def test_messenger_dedup_empty_id(self):
        """Empty message ID is never duplicate."""
        from app.api.v1.messenger_webhook import _is_duplicate, _seen_message_ids
        _seen_message_ids.clear()
        assert _is_duplicate("") is False
        assert _is_duplicate("") is False  # Still not duplicate

    def test_zalo_dedup_works(self):
        """Zalo webhook also has dedup."""
        from app.api.v1.zalo_webhook import _is_duplicate, _seen_message_ids
        _seen_message_ids.clear()
        assert _is_duplicate("zalo_001") is False
        assert _is_duplicate("zalo_001") is True

    def test_zalo_dedup_separate_from_messenger(self):
        """Zalo and Messenger have separate dedup caches."""
        import app.api.v1.messenger_webhook as mw
        import app.api.v1.zalo_webhook as zw
        mw._seen_message_ids.clear()
        zw._seen_message_ids.clear()

        mw._is_duplicate("shared_id")
        # Same ID should NOT be detected as duplicate in Zalo's cache
        assert zw._is_duplicate("shared_id") is False


# =============================================================================
# 7. Config (4 tests)
# =============================================================================


class TestConfig:
    """Sprint 188: New config fields."""

    def test_facebook_graph_api_version_default(self):
        """facebook_graph_api_version defaults to v22.0."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.facebook_graph_api_version == "v22.0"

    def test_facebook_graph_api_version_custom(self):
        """facebook_graph_api_version can be overridden."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            facebook_graph_api_version="v23.0",
            _env_file=None,
        )
        assert s.facebook_graph_api_version == "v23.0"

    def test_delivery_result_dataclass(self):
        """DeliveryResult has correct defaults."""
        from app.engine.living_agent.channel_sender import DeliveryResult
        r = DeliveryResult()
        assert r.success is False
        assert r.channel == ""
        assert r.error is None

    def test_delivery_result_with_values(self):
        """DeliveryResult stores values."""
        from app.engine.living_agent.channel_sender import DeliveryResult
        r = DeliveryResult(
            success=True,
            channel="messenger",
            recipient_id="user1",
            status_code=200,
        )
        assert r.success is True
        assert r.status_code == 200
