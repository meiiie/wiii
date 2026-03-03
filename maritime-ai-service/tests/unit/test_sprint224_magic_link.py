"""Sprint 224: Magic Link Email Auth — Unit Tests."""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConfigDefaults:
    """Config flag defaults."""

    def test_enable_magic_link_auth_default_false(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_magic_link_auth"].default
        assert default is False

    def test_magic_link_expires_default_600(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_expires_seconds"].default
        assert default == 600

    def test_magic_link_max_per_hour_default_5(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_max_per_hour"].default
        assert default == 5

    def test_magic_link_ws_timeout_default_900(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_ws_timeout_seconds"].default
        assert default == 900

    def test_magic_link_resend_cooldown_default_45(self):
        from app.core.config import Settings
        default = Settings.model_fields["magic_link_resend_cooldown_seconds"].default
        assert default == 45


class TestEmailService:
    """Email sending via Resend."""

    def test_build_magic_link_html_contains_url(self):
        from app.auth.email_service import build_magic_link_html
        html = build_magic_link_html("https://wiii.app/verify/abc123")
        assert "https://wiii.app/verify/abc123" in html
        assert "Đăng nhập Wiii" in html

    def test_build_magic_link_html_contains_expiry_notice(self):
        from app.auth.email_service import build_magic_link_html
        html = build_magic_link_html("https://example.com/verify/x")
        assert "10 phút" in html

    @pytest.mark.asyncio
    async def test_send_magic_link_email_calls_resend(self):
        from app.auth.email_service import send_magic_link_email

        mock_settings = MagicMock()
        mock_settings.resend_api_key = "re_test_key"
        mock_settings.magic_link_from_email = "Wiii <noreply@wiii.app>"

        with patch("app.auth.email_service.resend") as mock_resend, \
             patch("app.auth.email_service.settings", mock_settings):
            mock_resend.Emails.send.return_value = {"id": "email_123"}
            result = await send_magic_link_email("test@example.com", "https://wiii.app/verify/abc")
            assert result is True
            mock_resend.Emails.send.assert_called_once()
            call_args = mock_resend.Emails.send.call_args[0][0]
            assert call_args["to"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_send_magic_link_email_handles_error(self):
        from app.auth.email_service import send_magic_link_email

        mock_settings = MagicMock()
        mock_settings.resend_api_key = "re_test_key"
        mock_settings.magic_link_from_email = "Wiii <noreply@wiii.app>"

        with patch("app.auth.email_service.resend") as mock_resend, \
             patch("app.auth.email_service.settings", mock_settings):
            mock_resend.Emails.send.side_effect = Exception("API error")
            result = await send_magic_link_email("test@example.com", "https://wiii.app/verify/abc")
            assert result is False


class TestMagicLinkTokenGeneration:
    """Token generation and hashing."""

    def test_generate_token_returns_tuple(self):
        from app.auth.magic_link_service import generate_magic_token
        raw_token, token_hash = generate_magic_token()
        assert len(raw_token) > 32
        assert len(token_hash) == 64  # SHA256 hex

    def test_token_hash_is_sha256(self):
        from app.auth.magic_link_service import generate_magic_token, hash_token
        raw_token, token_hash = generate_magic_token()
        assert hash_token(raw_token) == token_hash

    def test_different_tokens_each_call(self):
        from app.auth.magic_link_service import generate_magic_token
        t1, _ = generate_magic_token()
        t2, _ = generate_magic_token()
        assert t1 != t2


class TestMagicLinkVerification:
    """Token verification logic (no DB)."""

    def test_token_not_expired(self):
        from app.auth.magic_link_service import is_token_expired
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert is_token_expired(future) is False

    def test_token_expired(self):
        from app.auth.magic_link_service import is_token_expired
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert is_token_expired(past) is True

    def test_token_already_used(self):
        from app.auth.magic_link_service import is_token_used
        assert is_token_used(datetime.now(timezone.utc)) is True

    def test_token_not_used(self):
        from app.auth.magic_link_service import is_token_used
        assert is_token_used(None) is False


class TestEmailValidation:
    """Email format validation."""

    def test_valid_email(self):
        from app.auth.magic_link_service import validate_email
        assert validate_email("student@maritime.edu") is True

    def test_invalid_email_no_at(self):
        from app.auth.magic_link_service import validate_email
        assert validate_email("invalid-email") is False

    def test_invalid_email_empty(self):
        from app.auth.magic_link_service import validate_email
        assert validate_email("") is False

    def test_invalid_email_spaces(self):
        from app.auth.magic_link_service import validate_email
        assert validate_email("  ") is False


class TestSessionManager:
    """WebSocket session management."""

    def test_singleton_returns_same_instance(self):
        from app.auth.magic_link_service import get_session_manager
        m1 = get_session_manager()
        m2 = get_session_manager()
        assert m1 is m2

    def test_remove_nonexistent_session(self):
        from app.auth.magic_link_service import MagicLinkSessionManager
        mgr = MagicLinkSessionManager()
        mgr.remove("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_push_to_missing_session_returns_false(self):
        from app.auth.magic_link_service import MagicLinkSessionManager
        mgr = MagicLinkSessionManager()
        result = await mgr.push_tokens("nonexistent", {"token": "abc"})
        assert result is False

    def test_active_count_starts_at_zero(self):
        from app.auth.magic_link_service import MagicLinkSessionManager
        mgr = MagicLinkSessionManager()
        assert mgr.active_count == 0
