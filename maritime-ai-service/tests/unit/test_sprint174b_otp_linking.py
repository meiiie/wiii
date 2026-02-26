"""
Sprint 174b: OTP Identity Linking Tests
Updated for Sprint 176: DB-backed OTP (replaces in-memory _otp_store).

Tests:
  1. OTP generation (6-digit, unique, DB writes)
  2. OTP verification (success, wrong channel, expired, wrong code, one-time use)
  3. OTP revocation (same user+channel invalidates old code)
  4. Webhook interception (6-digit triggers OTP check, non-6-digit passes through)
  5. Config (otp_link_expiry_seconds)
  6. Integration (full flow with mocked DB)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — mock asyncpg pool (matches pattern from test_sprint177)
# ---------------------------------------------------------------------------

def _make_mock_pool(row_data=None):
    """Create a mock asyncpg pool for DB-backed OTP tests."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=0)  # Sprint 192: rate limit count defaults to 0
    if row_data:
        mock_conn.fetchrow = AsyncMock(return_value=row_data)
    else:
        mock_conn.fetchrow = AsyncMock(return_value=None)

    # pool.acquire() returns an async context manager (not a coroutine)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_ctx

    return mock_pool, mock_conn


_POOL_PATCH = "app.core.database.get_asyncpg_pool"
_EXPIRY_PATCH = "app.auth.otp_linking._get_expiry_seconds"
_LINK_PATCH = "app.auth.user_service.link_identity"


# ---------------------------------------------------------------------------
# 1. OTP Generation (DB-backed)
# ---------------------------------------------------------------------------

class TestOTPGeneration:
    """Test generate_link_code() — Sprint 176 DB-backed."""

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_generates_6_digit_code(self, _mock_expiry):
        pool, conn = _make_mock_pool()
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import generate_link_code
            code = await generate_link_code("user-1", "messenger")
        assert len(code) == 6
        assert code.isdigit()
        assert 100000 <= int(code) <= 999999

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_different_codes_for_different_users(self, _mock_expiry):
        pool, conn = _make_mock_pool()
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import generate_link_code
            codes = set()
            for i in range(20):
                code = await generate_link_code(f"user-{i}", "messenger")
                codes.add(code)
        assert len(codes) >= 18

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_db_insert_called(self, _mock_expiry):
        """Code is stored in DB via INSERT."""
        pool, conn = _make_mock_pool()
        # Sprint 194c: Force cleanup to run (random < 0.1) for deterministic test
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch("app.auth.otp_linking.random") as mock_random:
            mock_random.random.return_value = 0.05  # triggers cleanup
            from app.auth.otp_linking import generate_link_code
            code = await generate_link_code("user-1", "messenger")

        # With cleanup: cleanup → revoke old → insert new = 3 execute calls
        assert conn.execute.call_count == 3
        insert_call = conn.execute.call_args_list[2]
        assert "INSERT INTO otp_link_codes" in insert_call[0][0]
        assert insert_call[0][1] == code
        assert insert_call[0][2] == "user-1"
        assert insert_call[0][3] == "messenger"

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_cleanup_expired_on_generate(self, _mock_expiry):
        """Generating a code triggers DELETE of expired codes (Sprint 194c: probabilistic, forced here)."""
        pool, conn = _make_mock_pool()
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch("app.auth.otp_linking.random") as mock_random:
            mock_random.random.return_value = 0.05  # triggers cleanup
            from app.auth.otp_linking import generate_link_code
            await generate_link_code("user-1", "zalo")

        cleanup_call = conn.execute.call_args_list[0]
        assert "DELETE FROM otp_link_codes WHERE expires_at < NOW()" in cleanup_call[0][0]


# ---------------------------------------------------------------------------
# 2. OTP Verification (DB-backed)
# ---------------------------------------------------------------------------

class TestOTPVerification:
    """Test verify_and_link() — Sprint 176 DB-backed."""

    @pytest.mark.asyncio
    async def test_success(self):
        row_data = {
            "user_id": "user-1",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
        }
        pool, conn = _make_mock_pool(row_data)

        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch(_LINK_PATCH, new_callable=AsyncMock) as mock_link, \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_memory = False
            mock_settings.otp_max_verify_attempts = 5
            from app.auth.otp_linking import verify_and_link
            success, msg = await verify_and_link("123456", "messenger", "fb_sender_123")

        assert success is True
        assert msg == "user-1"
        mock_link.assert_called_once_with(
            user_id="user-1",
            provider="messenger",
            provider_sub="fb_sender_123",
        )

    @pytest.mark.asyncio
    async def test_wrong_code(self):
        pool, conn = _make_mock_pool()  # fetchrow returns None
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import verify_and_link
            success, msg = await verify_and_link("000000", "messenger", "fb_sender_123")
        assert success is False
        assert msg == ""

    @pytest.mark.asyncio
    async def test_wrong_channel(self):
        row_data = {
            "user_id": "user-1",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
        }
        pool, conn = _make_mock_pool(row_data)
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import verify_and_link
            success, msg = await verify_and_link("123456", "zalo", "zalo_sender_123")
        assert success is False
        assert msg == ""

    @pytest.mark.asyncio
    async def test_expired_code(self):
        row_data = {
            "user_id": "user-1",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
        }
        pool, conn = _make_mock_pool(row_data)
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import verify_and_link
            success, msg = await verify_and_link("123456", "messenger", "fb_sender_123")
        assert success is False
        assert msg == "expired"
        # Should have marked as used
        update_call = conn.execute.call_args
        assert "UPDATE otp_link_codes SET used_at" in update_call[0][0]

    @pytest.mark.asyncio
    async def test_one_time_use(self):
        """Already used code (used_at is set) → rejected."""
        row_data = {
            "user_id": "user-1",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": datetime.now(timezone.utc),
            "failed_attempts": 0,
        }
        pool, conn = _make_mock_pool(row_data)
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool):
            from app.auth.otp_linking import verify_and_link
            success, msg = await verify_and_link("123456", "messenger", "fb_sender_1")
        assert success is False
        assert msg == ""


# ---------------------------------------------------------------------------
# 3. OTP Revocation (DB DELETE)
# ---------------------------------------------------------------------------

class TestOTPRevocation:
    """Test that generating a new code DELETEs old codes for same user+channel."""

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_same_user_channel_revokes_old(self, _mock_expiry):
        pool, conn = _make_mock_pool()
        # Sprint 194c: Skip probabilistic cleanup for deterministic call indices
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch("app.auth.otp_linking.random") as mock_random:
            mock_random.random.return_value = 0.5  # skip cleanup
            from app.auth.otp_linking import generate_link_code
            await generate_link_code("user-1", "messenger")

        # Without cleanup: revoke (idx 0) → insert (idx 1) = 2 execute calls
        revoke_call = conn.execute.call_args_list[0]
        assert "DELETE FROM otp_link_codes WHERE user_id" in revoke_call[0][0]
        assert revoke_call[0][1] == "user-1"
        assert revoke_call[0][2] == "messenger"

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_different_channel_keeps_both(self, _mock_expiry):
        pool, conn = _make_mock_pool()
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch("app.auth.otp_linking.random") as mock_random:
            mock_random.random.return_value = 0.5  # skip cleanup
            from app.auth.otp_linking import generate_link_code
            await generate_link_code("user-1", "messenger")
            await generate_link_code("user-1", "zalo")

        # Without cleanup: each generate = revoke + insert = 2 execute calls
        # Call 1: revoke(0), insert(1). Call 2: revoke(2), insert(3)
        revoke_messenger = conn.execute.call_args_list[0]
        revoke_zalo = conn.execute.call_args_list[2]
        assert revoke_messenger[0][2] == "messenger"
        assert revoke_zalo[0][2] == "zalo"

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_different_user_keeps_both(self, _mock_expiry):
        pool, conn = _make_mock_pool()
        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch("app.auth.otp_linking.random") as mock_random:
            mock_random.random.return_value = 0.5  # skip cleanup
            from app.auth.otp_linking import generate_link_code
            await generate_link_code("user-1", "messenger")
            await generate_link_code("user-2", "messenger")

        # Without cleanup: each generate = revoke + insert = 2 execute calls
        revoke_u1 = conn.execute.call_args_list[0]
        revoke_u2 = conn.execute.call_args_list[2]
        assert revoke_u1[0][1] == "user-1"
        assert revoke_u2[0][1] == "user-2"


# ---------------------------------------------------------------------------
# 4. Webhook Interception — Messenger
# ---------------------------------------------------------------------------

class TestMessengerOTPInterception:
    """Test _check_otp_linking in messenger_webhook.py."""

    @pytest.mark.asyncio
    async def test_non_digit_passes_through(self):
        from app.api.v1.messenger_webhook import _check_otp_linking
        result = await _check_otp_linking("hello world", "messenger", "sender1")
        assert result is None

    @pytest.mark.asyncio
    async def test_short_digit_passes_through(self):
        from app.api.v1.messenger_webhook import _check_otp_linking
        result = await _check_otp_linking("12345", "messenger", "sender1")
        assert result is None

    @pytest.mark.asyncio
    async def test_long_digit_passes_through(self):
        from app.api.v1.messenger_webhook import _check_otp_linking
        result = await _check_otp_linking("1234567", "messenger", "sender1")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_otp_returns_success_message(self):
        with patch("app.auth.otp_linking.verify_and_link", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (True, "user-1")
            from app.api.v1.messenger_webhook import _check_otp_linking
            result = await _check_otp_linking("654321", "messenger", "fb_sender_123")
        assert result is not None
        assert "Lien ket thanh cong" in result

    @pytest.mark.asyncio
    async def test_unmatched_6digit_returns_none(self):
        with patch("app.auth.otp_linking.verify_and_link", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (False, "")
            from app.api.v1.messenger_webhook import _check_otp_linking
            result = await _check_otp_linking("999999", "messenger", "sender1")
        assert result is None


# ---------------------------------------------------------------------------
# 5. Webhook Interception — Zalo
# ---------------------------------------------------------------------------

class TestZaloOTPInterception:
    """Test _check_otp_linking in zalo_webhook.py."""

    @pytest.mark.asyncio
    async def test_non_digit_passes_through(self):
        from app.api.v1.zalo_webhook import _check_otp_linking
        result = await _check_otp_linking("xin chao", "zalo", "sender1")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_otp_returns_success(self):
        with patch("app.auth.otp_linking.verify_and_link", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (True, "user-1")
            from app.api.v1.zalo_webhook import _check_otp_linking
            result = await _check_otp_linking("654321", "zalo", "zalo_sender_123")
        assert result is not None
        assert "Lien ket thanh cong" in result

    @pytest.mark.asyncio
    async def test_messenger_code_rejected_on_zalo(self):
        with patch("app.auth.otp_linking.verify_and_link", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (False, "")
            from app.api.v1.zalo_webhook import _check_otp_linking
            result = await _check_otp_linking("654321", "zalo", "zalo_sender_123")
        assert result is None


# ---------------------------------------------------------------------------
# 6. Config
# ---------------------------------------------------------------------------

class TestOTPConfig:
    """Test OTP configuration field."""

    def test_default_expiry(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.otp_link_expiry_seconds == 300

    def test_custom_expiry(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", otp_link_expiry_seconds=600)
        assert s.otp_link_expiry_seconds == 600

    def test_expiry_min_bound(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(google_api_key="test", otp_link_expiry_seconds=10)

    def test_expiry_max_bound(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(google_api_key="test", otp_link_expiry_seconds=1000)


# ---------------------------------------------------------------------------
# 7. Integration: Full Flow (mocked DB)
# ---------------------------------------------------------------------------

class TestOTPFullFlow:
    """Integration test: generate → verify → link (all DB-mocked)."""

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_full_flow_messenger(self, _mock_expiry):
        pool, conn = _make_mock_pool()

        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch(_LINK_PATCH, new_callable=AsyncMock) as mock_link, \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_memory = False
            mock_settings.otp_generate_window_minutes = 15
            mock_settings.otp_max_generate_per_window = 5
            mock_settings.otp_max_verify_attempts = 5

            from app.auth.otp_linking import generate_link_code, verify_and_link

            # Step 1: Generate
            code = await generate_link_code("canonical-user-uuid", "messenger")
            assert len(code) == 6

            # Step 2: Simulate DB returning the generated code
            conn.fetchrow.return_value = {
                "user_id": "canonical-user-uuid",
                "channel_type": "messenger",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
                "used_at": None,
                "failed_attempts": 0,
            }

            # Step 3: Verify
            success, user_id = await verify_and_link(code, "messenger", "fb_12345")

        assert success is True
        assert user_id == "canonical-user-uuid"
        mock_link.assert_called_once_with(
            user_id="canonical-user-uuid",
            provider="messenger",
            provider_sub="fb_12345",
        )

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_full_flow_zalo(self, _mock_expiry):
        pool, conn = _make_mock_pool()

        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch(_LINK_PATCH, new_callable=AsyncMock) as mock_link, \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_memory = False
            mock_settings.otp_generate_window_minutes = 15
            mock_settings.otp_max_generate_per_window = 5
            mock_settings.otp_max_verify_attempts = 5

            from app.auth.otp_linking import generate_link_code, verify_and_link

            code = await generate_link_code("canonical-user-uuid", "zalo")

            conn.fetchrow.return_value = {
                "user_id": "canonical-user-uuid",
                "channel_type": "zalo",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
                "used_at": None,
                "failed_attempts": 0,
            }

            success, user_id = await verify_and_link(code, "zalo", "zalo_67890")

        assert success is True
        assert user_id == "canonical-user-uuid"
        mock_link.assert_called_once_with(
            user_id="canonical-user-uuid",
            provider="zalo",
            provider_sub="zalo_67890",
        )

    @patch(_EXPIRY_PATCH, return_value=300)
    @pytest.mark.asyncio
    async def test_cross_channel_blocked(self, _mock_expiry):
        """Code for messenger cannot be used on zalo."""
        pool, conn = _make_mock_pool()

        with patch(_POOL_PATCH, create=True, new_callable=AsyncMock, return_value=pool), \
             patch(_LINK_PATCH, new_callable=AsyncMock) as mock_link:
            from app.auth.otp_linking import generate_link_code, verify_and_link

            await generate_link_code("user-1", "messenger")

            # DB returns code for messenger
            conn.fetchrow.return_value = {
                "user_id": "user-1",
                "channel_type": "messenger",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
                "used_at": None,
                "failed_attempts": 0,
            }

            # Try to verify on zalo → channel mismatch
            success, _ = await verify_and_link("123456", "zalo", "zalo_sender")

        assert success is False
        mock_link.assert_not_called()
