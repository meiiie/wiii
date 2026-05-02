"""
Tests for Sprint 174: "Một Wiii — Nhiều Nền Tảng"
Cross-Platform Identity + Dual Personality

Covers:
    1. Config — 5 new fields with defaults
    2. IdentityResolver — resolve_user_id() with feature flag on/off
    3. PersonalityMode — resolve_personality_mode() priority chain
    4. PersonalityMode — get_soul_mode_instructions()
    5. PromptLoader — personality_mode param + soul injection
    6. Messenger Webhook — identity + personality integration
    7. Zalo Webhook — incoming message handling + MAC verification
    8. Graph threading — personality_mode flows through context
    9. Router registration — Zalo webhook config-gated

NOTE: identity_resolver.py and personality_mode.py use LAZY IMPORTS
(inside function bodies), so settings must be patched at source:
  app.core.config.settings (NOT app.auth.identity_resolver.settings)
"""

import asyncio
import json
import hashlib
import hmac as hmac_mod
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.multi_agent.runtime_contracts import WiiiTurnRequest, WiiiTurnResult


# =============================================================================
# 1. CONFIG TESTS
# =============================================================================


class TestCrossPlatformConfig:
    """Tests for Sprint 174 config fields."""

    def test_default_cross_platform_identity_disabled(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.enable_cross_platform_identity is False

    def test_default_zalo_webhook_disabled(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.enable_zalo_webhook is False

    def test_default_zalo_webhook_token_none(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.zalo_webhook_token is None

    def test_default_personality_mode_professional(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.default_personality_mode == "professional"

    def test_default_channel_personality_map(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        mapping = json.loads(s.channel_personality_map)
        assert mapping["web"] == "professional"
        assert mapping["desktop"] == "professional"
        assert mapping["messenger"] == "soul"
        assert mapping["zalo"] == "soul"
        assert mapping["telegram"] == "professional"

    def test_channel_personality_map_override(self):
        from app.core.config import Settings
        custom = '{"web":"soul","messenger":"professional"}'
        s = Settings(google_api_key="test", channel_personality_map=custom)
        mapping = json.loads(s.channel_personality_map)
        assert mapping["web"] == "soul"
        assert mapping["messenger"] == "professional"


# =============================================================================
# 2. IDENTITY RESOLVER TESTS
# Lazy imports: patch at app.core.config.settings and
#   app.auth.user_service.find_or_create_by_provider
# =============================================================================


class TestIdentityResolver:
    """Tests for resolve_user_id()."""

    @pytest.mark.asyncio
    async def test_disabled_returns_legacy_id(self):
        """When cross-platform identity is disabled, return legacy format."""
        from app.auth.identity_resolver import resolve_user_id

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = False
            result = await resolve_user_id("messenger", "12345")
            assert result == "messenger_12345"

    @pytest.mark.asyncio
    async def test_disabled_zalo_returns_legacy_id(self):
        from app.auth.identity_resolver import resolve_user_id

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = False
            result = await resolve_user_id("zalo", "zalo_user_001")
            assert result == "zalo_zalo_user_001"

    @pytest.mark.asyncio
    async def test_enabled_calls_find_or_create(self):
        """When enabled, calls find_or_create_by_provider and returns canonical ID."""
        from app.auth.identity_resolver import resolve_user_id

        mock_user = {"id": "uuid-canonical-123", "name": "Test"}

        with patch("app.core.config.settings") as mock_settings, \
             patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, return_value=mock_user) as mock_focp:
            mock_settings.enable_cross_platform_identity = True
            result = await resolve_user_id("messenger", "fb_sender_42", display_name="Tester")
            assert result == "uuid-canonical-123"
            mock_focp.assert_called_once_with(
                provider="messenger",
                provider_sub="fb_sender_42",
                email=None,
                name="Tester",
                auto_create=True,
                email_verified=False,
            )

    @pytest.mark.asyncio
    async def test_enabled_returns_legacy_on_none(self):
        """When find_or_create returns None, fall back to legacy."""
        from app.auth.identity_resolver import resolve_user_id

        with patch("app.core.config.settings") as mock_settings, \
             patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, return_value=None):
            mock_settings.enable_cross_platform_identity = True
            result = await resolve_user_id("telegram", "tg_999")
            assert result == "telegram_tg_999"

    @pytest.mark.asyncio
    async def test_enabled_returns_legacy_on_error(self):
        """When find_or_create raises exception, fall back gracefully."""
        from app.auth.identity_resolver import resolve_user_id

        with patch("app.core.config.settings") as mock_settings, \
             patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, side_effect=Exception("DB down")):
            mock_settings.enable_cross_platform_identity = True
            result = await resolve_user_id("messenger", "fb_123")
            assert result == "messenger_fb_123"

    @pytest.mark.asyncio
    async def test_email_verified_false_by_default(self):
        """Messaging platforms should never auto-link by email."""
        from app.auth.identity_resolver import resolve_user_id

        mock_user = {"id": "uuid-1"}

        with patch("app.core.config.settings") as mock_settings, \
             patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, return_value=mock_user) as mock_focp:
            mock_settings.enable_cross_platform_identity = True
            await resolve_user_id("zalo", "zalo_001")
            call_kwargs = mock_focp.call_args[1]
            assert call_kwargs["email_verified"] is False
            assert call_kwargs["email"] is None


# =============================================================================
# 3. PERSONALITY MODE TESTS
# Lazy imports: patch at app.core.config.settings
# =============================================================================


class TestPersonalityMode:
    """Tests for resolve_personality_mode() priority chain."""

    def test_disabled_returns_professional(self):
        """When feature is disabled, always returns professional."""
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = False
            result = resolve_personality_mode("messenger")
            assert result == "professional"

    def test_explicit_mode_highest_priority(self):
        """Explicit mode overrides everything."""
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"messenger":"soul"}'
            mock_settings.default_personality_mode = "professional"
            result = resolve_personality_mode("messenger", explicit_mode="professional")
            assert result == "professional"

    def test_explicit_soul_mode(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"web":"professional"}'
            mock_settings.default_personality_mode = "professional"
            result = resolve_personality_mode("web", explicit_mode="soul")
            assert result == "soul"

    def test_invalid_explicit_mode_falls_through(self):
        """Invalid explicit mode is ignored."""
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"messenger":"soul"}'
            mock_settings.default_personality_mode = "professional"
            result = resolve_personality_mode("messenger", explicit_mode="invalid")
            assert result == "soul"  # Falls through to channel mapping

    def test_channel_mapping_messenger_soul(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"messenger":"soul","web":"professional"}'
            mock_settings.default_personality_mode = "professional"
            result = resolve_personality_mode("messenger")
            assert result == "soul"

    def test_channel_mapping_web_professional(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"messenger":"soul","web":"professional"}'
            mock_settings.default_personality_mode = "soul"
            result = resolve_personality_mode("web")
            assert result == "professional"

    def test_unknown_channel_uses_default(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = '{"messenger":"soul"}'
            mock_settings.default_personality_mode = "soul"
            result = resolve_personality_mode("unknown_channel")
            assert result == "soul"

    def test_invalid_json_uses_default(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = "not-json"
            mock_settings.default_personality_mode = "professional"
            result = resolve_personality_mode("messenger")
            assert result == "professional"

    def test_default_fallback_professional(self):
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = "{}"
            mock_settings.default_personality_mode = "invalid_mode"
            result = resolve_personality_mode("web")
            assert result == "professional"  # Ultimate fallback


class TestSoulModeInstructions:
    """Tests for get_soul_mode_instructions()."""

    def test_contains_key_instructions(self):
        from app.engine.personality_mode import get_soul_mode_instructions

        instructions = get_soul_mode_instructions()
        assert "BẠN THÂN" in instructions
        assert "ĐỒNG CẢM" in instructions
        assert "NGẮN GỌN" in instructions
        assert "cảm xúc" in instructions

    def test_returns_non_empty_string(self):
        from app.engine.personality_mode import get_soul_mode_instructions

        instructions = get_soul_mode_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 50


# =============================================================================
# 4. PROMPT LOADER INTEGRATION TESTS
# =============================================================================


class TestPromptLoaderPersonalityMode:
    """Tests for personality_mode param in build_system_prompt()."""

    def test_professional_mode_no_soul_injection(self):
        """Professional mode should NOT inject soul mode instructions."""
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="student",
            personality_mode="professional",
        )
        assert "CHẾ ĐỘ LINH HỒN" not in prompt
        assert "Soul Mode" not in prompt

    def test_none_mode_no_soul_injection(self):
        """None personality_mode should NOT inject soul mode instructions."""
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt(
            role="student",
            personality_mode=None,
        )
        assert "CHẾ ĐỘ LINH HỒN" not in prompt

    def test_soul_mode_injects_instructions(self):
        """Soul mode should inject casual companion instructions."""
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        # get_soul_mode_instructions is called directly, not via lazy import
        # So we just test that the prompt contains the expected content
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_living_agent = False
            # Patch compile_soul_prompt to avoid YAML loading issues
            with patch("app.engine.living_agent.soul_loader.compile_soul_prompt", return_value=""):
                prompt = loader.build_system_prompt(
                    role="student",
                    personality_mode="soul",
                )
                assert "CHẾ ĐỘ LINH HỒN" in prompt
                assert "BẠN THÂN" in prompt

    def test_soul_mode_loads_soul_yaml_when_living_agent_off(self):
        """Soul mode should load wiii_soul.yaml even if enable_living_agent=False."""
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        mock_soul = "--- LINH HỒN CỦA WIII ---\nTên: Wiii"

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_living_agent = False
            with patch("app.engine.living_agent.soul_loader.compile_soul_prompt", return_value=mock_soul):
                prompt = loader.build_system_prompt(
                    role="student",
                    personality_mode="soul",
                )
                assert "LINH HỒN CỦA WIII" in prompt

    def test_backward_compat_no_personality_mode(self):
        """Without personality_mode, output should be identical to before."""
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt_default = loader.build_system_prompt(role="student")
        prompt_none = loader.build_system_prompt(role="student", personality_mode=None)
        assert prompt_default == prompt_none


# =============================================================================
# 5. MESSENGER WEBHOOK TESTS
# Lazy imports in _process_and_reply: patch at SOURCE modules
# =============================================================================


class TestMessengerWebhookCrossPlatform:
    """Tests for updated _process_and_reply with identity + personality."""

    @pytest.mark.asyncio
    async def test_process_calls_resolve_user_id(self):
        from app.api.v1.messenger_webhook import _process_and_reply

        mock_result = {"response": "Chào bạn!"}

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="canonical-uuid") as mock_resolve, \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value=mock_result):
            answer = await _process_and_reply("fb_sender_42", "Hello")
            mock_resolve.assert_called_once_with("messenger", "fb_sender_42")
            assert answer == "Chào bạn!"

    @pytest.mark.asyncio
    async def test_process_passes_personality_mode_in_context(self):
        from app.api.v1.messenger_webhook import _process_and_reply

        mock_result = {"response": "OK"}

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="user-1"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value=mock_result) as mock_process:
            await _process_and_reply("sender_1", "Test")
            call_kwargs = mock_process.call_args[1]
            assert call_kwargs["context"]["personality_mode"] == "soul"
            assert call_kwargs["context"]["channel_type"] == "messenger"
            assert call_kwargs["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_process_uses_canonical_user_id(self):
        from app.api.v1.messenger_webhook import _process_and_reply

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="canonical-uuid-999"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="professional"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value={"response": "OK"}) as mock_process:
            await _process_and_reply("sender_x", "Hi")
            assert mock_process.call_args[1]["user_id"] == "canonical-uuid-999"

    @pytest.mark.asyncio
    async def test_process_uses_native_wiii_turn_request(self):
        from app.api.v1.messenger_webhook import _process_and_reply

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="canonical-uuid-999"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="professional"), \
             patch(
                 "app.engine.multi_agent.runtime.run_wiii_turn",
                 new_callable=AsyncMock,
                 return_value=WiiiTurnResult.from_payload({"response": "OK"}),
             ) as mock_run_turn:
            answer = await _process_and_reply("sender_x", "Hi")

        turn_request = mock_run_turn.await_args.args[0]
        assert isinstance(turn_request, WiiiTurnRequest)
        assert turn_request.query == "Hi"
        assert turn_request.run_context.user_id == "canonical-uuid-999"
        assert turn_request.run_context.session_id == "messenger_sender_x"
        assert turn_request.run_context.context["personality_mode"] == "professional"
        assert turn_request.run_context.context["channel_type"] == "messenger"
        assert answer == "OK"


# =============================================================================
# 6. ZALO WEBHOOK TESTS
# zalo_webhook.py imports settings at module level — patchable at module
# =============================================================================


class TestZaloWebhookMAC:
    """Tests for Zalo MAC verification."""

    def test_verify_mac_no_secret_permissive(self):
        from app.api.v1.zalo_webhook import _verify_zalo_mac

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = None
            assert _verify_zalo_mac(b"body", None) is True

    def test_verify_mac_missing_header_rejects(self):
        from app.api.v1.zalo_webhook import _verify_zalo_mac

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = "my-secret"
            assert _verify_zalo_mac(b"body", None) is False

    def test_verify_mac_valid_signature(self):
        from app.api.v1.zalo_webhook import _verify_zalo_mac

        secret = "test-secret"
        body = b'{"event_name":"user_send_text"}'
        expected_mac = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = secret
            assert _verify_zalo_mac(body, expected_mac) is True

    def test_verify_mac_invalid_signature(self):
        from app.api.v1.zalo_webhook import _verify_zalo_mac

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = "my-secret"
            assert _verify_zalo_mac(b"body", "wrong-mac") is False


class TestZaloWebhookProcessing:
    """Tests for Zalo _process_and_reply — lazy imports, patch at source."""

    @pytest.mark.asyncio
    async def test_process_calls_resolve_user_id(self):
        from app.api.v1.zalo_webhook import _process_and_reply

        mock_result = {"response": "Chào!"}

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="uuid-zalo-1") as mock_resolve, \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value=mock_result):
            answer = await _process_and_reply("zalo_user_1", "Chào Wiii!")
            mock_resolve.assert_called_once_with("zalo", "zalo_user_1")
            assert answer == "Chào!"

    @pytest.mark.asyncio
    async def test_process_passes_soul_mode(self):
        from app.api.v1.zalo_webhook import _process_and_reply

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="user-z"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value={"response": "OK"}) as mock_process:
            await _process_and_reply("z_001", "Test")
            ctx = mock_process.call_args[1]["context"]
            assert ctx["personality_mode"] == "soul"
            assert ctx["channel_type"] == "zalo"

    @pytest.mark.asyncio
    async def test_process_session_id_format(self):
        from app.api.v1.zalo_webhook import _process_and_reply

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="user-z"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch("app.engine.multi_agent.graph.process_with_multi_agent", new_callable=AsyncMock, return_value={"response": "OK"}) as mock_process:
            await _process_and_reply("zalo_777", "Hi")
            assert mock_process.call_args[1]["session_id"] == "zalo_zalo_777"

    @pytest.mark.asyncio
    async def test_process_uses_native_wiii_turn_request(self):
        from app.api.v1.zalo_webhook import _process_and_reply

        with patch("app.auth.identity_resolver.resolve_user_id", new_callable=AsyncMock, return_value="user-z"), \
             patch("app.engine.personality_mode.resolve_personality_mode", return_value="soul"), \
             patch(
                 "app.engine.multi_agent.runtime.run_wiii_turn",
                 new_callable=AsyncMock,
                 return_value=WiiiTurnResult.from_payload({"response": "OK"}),
             ) as mock_run_turn:
            answer = await _process_and_reply("zalo_777", "Hi")

        turn_request = mock_run_turn.await_args.args[0]
        assert isinstance(turn_request, WiiiTurnRequest)
        assert turn_request.query == "Hi"
        assert turn_request.run_context.user_id == "user-z"
        assert turn_request.run_context.session_id == "zalo_zalo_777"
        assert turn_request.run_context.context["personality_mode"] == "soul"
        assert turn_request.run_context.context["channel_type"] == "zalo"
        assert answer == "OK"


class TestZaloSendReply:
    """Tests for _send_zalo_reply — Sprint 188: delegates to channel_sender."""

    @pytest.mark.asyncio
    async def test_send_reply_no_token_skips(self):
        """When no access token configured, should log error and not crash."""
        from app.api.v1.zalo_webhook import _send_zalo_reply

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.zalo_oa_access_token = None
            # Should not raise
            await _send_zalo_reply("recipient_1", "Hello")

    @pytest.mark.asyncio
    async def test_send_reply_calls_api(self):
        """When access token is set, should call Zalo API via channel_sender."""
        from app.api.v1.zalo_webhook import _send_zalo_reply

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": 0, "message": "Success"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.config.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client):
            mock_settings.zalo_oa_access_token = "test-token"
            await _send_zalo_reply("recipient_1", "Chào bạn!")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "openapi.zalo.me" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_reply_truncates_long_text(self):
        from app.api.v1.zalo_webhook import _send_zalo_reply

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": 0}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        long_text = "A" * 3000

        with patch("app.core.config.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client):
            mock_settings.zalo_oa_access_token = "tok"
            await _send_zalo_reply("r1", long_text)

            payload = mock_client.post.call_args[1]["json"]
            assert len(payload["message"]["text"]) <= 2000


class TestZaloWebhookEndpoint:
    """Tests for the /zalo/webhook FastAPI endpoint."""

    @pytest.mark.asyncio
    async def test_non_text_event_ignored(self):
        """Non user_send_text events should be ignored."""
        from app.api.v1.zalo_webhook import zalo_incoming

        mock_request = AsyncMock()
        mock_request.body.return_value = json.dumps({
            "event_name": "user_submit_info",
            "sender": {"id": "z1"},
        }).encode()
        mock_request.headers = {}

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = None
            result = await zalo_incoming(mock_request)
            assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_missing_sender_ignored(self):
        from app.api.v1.zalo_webhook import zalo_incoming

        mock_request = AsyncMock()
        mock_request.body.return_value = json.dumps({
            "event_name": "user_send_text",
            "sender": {},
            "message": {"text": "Hi"},
        }).encode()
        mock_request.headers = {}

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings:
            mock_settings.zalo_oa_secret_key = None
            result = await zalo_incoming(mock_request)
            assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_valid_message_processed(self):
        """Sprint 188: Webhook now uses async background processing."""
        from app.api.v1.zalo_webhook import zalo_incoming, _seen_message_ids

        mock_request = AsyncMock()
        mock_request.body.return_value = json.dumps({
            "event_name": "user_send_text",
            "sender": {"id": "zalo_user_123"},
            "message": {"text": "Chào Wiii!", "msg_id": "test_msg_001"},
        }).encode()
        mock_request.headers = {}

        _seen_message_ids.clear()

        with patch("app.api.v1.zalo_webhook.settings") as mock_settings, \
             patch("app.api.v1.zalo_webhook._process_and_reply_background", new_callable=AsyncMock) as mock_bg:
            mock_settings.zalo_oa_secret_key = None
            result = await zalo_incoming(mock_request)
            assert result["status"] == "ok"
            # Sprint 188: background task was scheduled via create_task
            # Give event loop a tick to fire the task
            await asyncio.sleep(0.01)
            mock_bg.assert_called_once_with("zalo_user_123", "Chào Wiii!")


# =============================================================================
# 7. GRAPH THREADING TESTS
# _build_direct_system_messages uses lazy import for get_prompt_loader
# → patch at app.prompts.prompt_loader.get_prompt_loader
# =============================================================================


class TestGraphPersonalityModeThreading:
    """Tests that personality_mode flows through graph context."""

    def test_build_direct_system_messages_passes_personality_mode(self):
        """_build_direct_system_messages should pass personality_mode to build_system_prompt."""
        from app.engine.multi_agent.graph import _build_direct_system_messages

        mock_state = {
            "context": {
                "user_name": "Test",
                "personality_mode": "soul",
            },
            "user_id": "user-1",
        }

        with patch("app.prompts.prompt_loader.get_prompt_loader") as mock_get_loader, \
             patch("app.engine.multi_agent.graph._build_direct_tools_context", return_value=""):
            mock_loader = MagicMock()
            mock_loader.build_system_prompt.return_value = "System prompt"
            mock_get_loader.return_value = mock_loader

            _build_direct_system_messages(mock_state, "Hello", "Maritime")

            call_kwargs = mock_loader.build_system_prompt.call_args[1]
            assert call_kwargs["personality_mode"] == "soul"

    def test_build_direct_system_messages_no_personality_mode(self):
        """When personality_mode not in context, should pass None."""
        from app.engine.multi_agent.graph import _build_direct_system_messages

        mock_state = {
            "context": {"user_name": "Test"},
            "user_id": "user-1",
        }

        with patch("app.prompts.prompt_loader.get_prompt_loader") as mock_get_loader, \
             patch("app.engine.multi_agent.graph._build_direct_tools_context", return_value=""):
            mock_loader = MagicMock()
            mock_loader.build_system_prompt.return_value = "System prompt"
            mock_get_loader.return_value = mock_loader

            _build_direct_system_messages(mock_state, "Hello", "Maritime")

            call_kwargs = mock_loader.build_system_prompt.call_args[1]
            assert call_kwargs["personality_mode"] is None

    def test_build_direct_system_messages_appends_code_studio_delivery_contract(self):
        """code_studio_agent should receive a delivery-first contract after the base prompt."""
        from app.engine.multi_agent.graph import _build_direct_system_messages

        mock_state = {
            "context": {"user_name": "Test"},
            "user_id": "user-1",
        }

        with patch("app.prompts.prompt_loader.get_prompt_loader") as mock_get_loader, \
             patch("app.engine.multi_agent.graph._build_direct_tools_context", return_value=""):
            mock_loader = MagicMock()
            mock_loader.build_system_prompt.return_value = "System prompt"
            mock_get_loader.return_value = mock_loader

            messages = _build_direct_system_messages(
                mock_state,
                "Ve mot bieu do bang Python",
                "Maritime",
                role_name="code_studio_agent",
            )

            system_message = messages[0]
            # Phase 1 migration: native dict payload (role/content)
            assert "CODE STUDIO DELIVERY CONTRACT" in system_message["content"]
            assert "khong mo dau bang loi chao" in system_message["content"].lower()


# =============================================================================
# 8. ROUTER REGISTRATION TESTS
# =============================================================================


class TestZaloRouterRegistration:
    """Tests for Zalo webhook router gating in __init__.py."""

    def test_zalo_router_exists(self):
        """Zalo webhook router module should be importable."""
        from app.api.v1.zalo_webhook import router
        assert router is not None
        assert router.prefix == "/zalo"

    def test_messenger_router_exists(self):
        """Messenger webhook router should still be importable."""
        from app.api.v1.messenger_webhook import router
        assert router is not None
        assert router.prefix == "/messenger"


# =============================================================================
# 9. INTEGRATION SCENARIO TESTS
# =============================================================================


class TestCrossPlatformScenarios:
    """End-to-end scenarios for cross-platform identity."""

    @pytest.mark.asyncio
    async def test_same_user_shared_memory_across_platforms(self):
        """Same physical user on Messenger and Zalo should resolve to same canonical ID."""
        from app.auth.identity_resolver import resolve_user_id

        mock_user = {"id": "canonical-uuid-shared"}

        with patch("app.core.config.settings") as mock_settings, \
             patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, return_value=mock_user):
            mock_settings.enable_cross_platform_identity = True

            messenger_uid = await resolve_user_id("messenger", "fb_12345")
            zalo_uid = await resolve_user_id("zalo", "zalo_67890")

            # Both resolve to same canonical user
            assert messenger_uid == "canonical-uuid-shared"
            assert zalo_uid == "canonical-uuid-shared"

    def test_messenger_soul_web_professional(self):
        """Messenger should default to soul, Web should default to professional."""
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = True
            mock_settings.channel_personality_map = (
                '{"web":"professional","desktop":"professional",'
                '"messenger":"soul","zalo":"soul","telegram":"professional"}'
            )
            mock_settings.default_personality_mode = "professional"

            assert resolve_personality_mode("messenger") == "soul"
            assert resolve_personality_mode("zalo") == "soul"
            assert resolve_personality_mode("web") == "professional"
            assert resolve_personality_mode("desktop") == "professional"
            assert resolve_personality_mode("telegram") == "professional"

    def test_feature_flag_off_zero_impact(self):
        """When enable_cross_platform_identity=False, everything returns defaults."""
        from app.engine.personality_mode import resolve_personality_mode

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = False

            # Always professional regardless of channel
            assert resolve_personality_mode("messenger") == "professional"
            assert resolve_personality_mode("zalo") == "professional"
            assert resolve_personality_mode("web") == "professional"

    @pytest.mark.asyncio
    async def test_feature_flag_off_legacy_user_ids(self):
        """When disabled, user IDs remain in legacy format."""
        from app.auth.identity_resolver import resolve_user_id

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_identity = False

            assert await resolve_user_id("messenger", "fb_123") == "messenger_fb_123"
            assert await resolve_user_id("zalo", "z_456") == "zalo_z_456"
            assert await resolve_user_id("telegram", "tg_789") == "telegram_tg_789"
