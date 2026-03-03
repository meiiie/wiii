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


# ===================================================================
# Router tests (Sprint 224 Task 3)
# ===================================================================


class TestMagicLinkRequest:
    """POST /auth/magic/request -- send magic link email."""

    @pytest.mark.asyncio
    async def test_create_magic_link_sends_email(self):
        """Core logic creates token and sends email."""
        from app.auth.magic_link_router import _create_magic_link

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)  # rate limit check
        mock_conn.execute = AsyncMock()

        with patch("app.auth.magic_link_router.send_magic_link_email", new_callable=AsyncMock, return_value=True) as mock_send, \
             patch("app.auth.magic_link_router.settings") as mock_settings:
            mock_settings.magic_link_expires_seconds = 600
            mock_settings.magic_link_base_url = "http://localhost:8000"
            mock_settings.magic_link_max_per_hour = 5
            mock_settings.api_v1_prefix = "/api/v1"

            result = await _create_magic_link("test@example.com", mock_conn)
            assert "session_id" in result
            assert len(result["session_id"]) > 20
            assert result["expires_in"] == 600
            assert "message" in result
            mock_send.assert_called_once()
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_magic_link_rate_limited(self):
        """Rate limit rejects when too many requests."""
        from app.auth.magic_link_router import _create_magic_link

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=10)  # over limit

        with patch("app.auth.magic_link_router.settings") as mock_settings, \
             pytest.raises(Exception) as exc_info:
            mock_settings.magic_link_max_per_hour = 5
            await _create_magic_link("test@example.com", mock_conn)
        assert "429" in str(exc_info.value.status_code) or "Too many" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_magic_link_email_failure(self):
        """Email send failure raises 500."""
        from app.auth.magic_link_router import _create_magic_link

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.execute = AsyncMock()

        with patch("app.auth.magic_link_router.send_magic_link_email", new_callable=AsyncMock, return_value=False), \
             patch("app.auth.magic_link_router.settings") as mock_settings, \
             pytest.raises(Exception) as exc_info:
            mock_settings.magic_link_expires_seconds = 600
            mock_settings.magic_link_base_url = "http://localhost:8000"
            mock_settings.magic_link_max_per_hour = 5
            mock_settings.api_v1_prefix = "/api/v1"
            await _create_magic_link("test@example.com", mock_conn)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_create_magic_link_stores_token_hash_not_raw(self):
        """DB receives hashed token, not the raw token."""
        from app.auth.magic_link_router import _create_magic_link

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.execute = AsyncMock()

        with patch("app.auth.magic_link_router.send_magic_link_email", new_callable=AsyncMock, return_value=True), \
             patch("app.auth.magic_link_router.settings") as mock_settings:
            mock_settings.magic_link_expires_seconds = 600
            mock_settings.magic_link_base_url = "http://localhost:8000"
            mock_settings.magic_link_max_per_hour = 5
            mock_settings.api_v1_prefix = "/api/v1"

            await _create_magic_link("test@example.com", mock_conn)

            # Verify the INSERT call
            call_args = mock_conn.execute.call_args
            insert_sql = call_args[0][0]
            assert "INSERT INTO magic_link_tokens" in insert_sql
            # token_hash is the first positional param ($1)
            stored_hash = call_args[0][1]
            assert len(stored_hash) == 64  # SHA256 hex digest

    @pytest.mark.asyncio
    async def test_create_magic_link_at_rate_limit_boundary(self):
        """Exactly at max_per_hour should still be rejected."""
        from app.auth.magic_link_router import _create_magic_link

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=5)  # exactly at limit

        with patch("app.auth.magic_link_router.settings") as mock_settings, \
             pytest.raises(Exception) as exc_info:
            mock_settings.magic_link_max_per_hour = 5
            await _create_magic_link("test@example.com", mock_conn)
        assert exc_info.value.status_code == 429


class TestMagicLinkVerify:
    """GET /auth/magic/verify/{token} -- verify token + create JWT."""

    def test_hash_token_consistent(self):
        from app.auth.magic_link_service import hash_token
        assert hash_token("abc") == hash_token("abc")
        assert hash_token("abc") != hash_token("def")

    def test_hash_token_is_sha256(self):
        from app.auth.magic_link_service import hash_token
        expected = hashlib.sha256(b"test_token").hexdigest()
        assert hash_token("test_token") == expected


class TestMagicLinkHTMLPages:
    """HTML response pages."""

    def test_success_page_ws_pushed(self):
        from app.auth.magic_link_router import _success_page
        response = _success_page(True)
        assert response.status_code == 200
        assert "thành công" in response.body.decode().lower()

    def test_success_page_ws_not_pushed(self):
        from app.auth.magic_link_router import _success_page
        response = _success_page(False)
        assert response.status_code == 200
        body = response.body.decode().lower()
        assert "xác minh" in body or "thử lại" in body

    def test_error_page(self):
        from app.auth.magic_link_router import _error_page
        response = _error_page("Token hết hạn")
        assert response.status_code == 400
        assert "Token hết hạn" in response.body.decode()

    def test_error_page_contains_wiii_branding(self):
        from app.auth.magic_link_router import _error_page
        response = _error_page("Test error")
        body = response.body.decode()
        assert "The Wiii Lab" in body

    def test_success_page_contains_wiii_branding(self):
        from app.auth.magic_link_router import _success_page
        response = _success_page(True)
        body = response.body.decode()
        assert "The Wiii Lab" in body


# ===================================================================
# Router structure tests (Sprint 224 Task 3 — endpoint registration)
# ===================================================================


class TestMagicLinkRouter:
    """Router endpoint registration and model tests."""

    def test_magic_link_request_model_validates_email(self):
        """MagicLinkRequest requires email with min_length=5."""
        import pydantic
        from app.auth.magic_link_router import MagicLinkRequest

        req = MagicLinkRequest(email="a@b.co")
        assert req.email == "a@b.co"

        with pytest.raises(pydantic.ValidationError):
            MagicLinkRequest(email="ab")  # too short

    def test_magic_link_response_model(self):
        from app.auth.magic_link_router import MagicLinkResponse
        resp = MagicLinkResponse(message="sent", session_id="abc123", expires_in=600)
        assert resp.session_id == "abc123"
        assert resp.expires_in == 600

    def test_router_prefix(self):
        from app.auth.magic_link_router import router
        assert router.prefix == "/auth/magic-link"

    def test_router_has_request_endpoint(self):
        from app.auth.magic_link_router import router
        paths = [r.path for r in router.routes]
        assert any("request" in p for p in paths)

    def test_router_has_verify_endpoint(self):
        from app.auth.magic_link_router import router
        paths = [r.path for r in router.routes]
        assert any("verify" in p and "token" in p for p in paths)

    def test_router_has_websocket_endpoint(self):
        from app.auth.magic_link_router import router
        paths = [r.path for r in router.routes]
        assert any("/ws/" in p for p in paths)
