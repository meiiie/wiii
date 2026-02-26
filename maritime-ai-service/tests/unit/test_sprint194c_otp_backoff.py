# -*- coding: utf-8 -*-
"""Sprint 194c - B3 HIGH: OTP exponential backoff + B8: probabilistic cleanup."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

_PP = "app.core.database.get_asyncpg_pool"
_SP = "app.core.config.settings"

def _pool_conn():
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return AsyncMock(return_value=pool), conn

def _row(uid="user-1", ch="zalo", fa=0, used=None, upd=None, exp=None):
    if exp is None:
        exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    if upd is None and fa > 0:
        upd = datetime.now(timezone.utc) - timedelta(seconds=120)
    return {"user_id": uid, "channel_type": ch, "expires_at": exp,
            "used_at": used, "failed_attempts": fa, "updated_at": upd}

def _ms(**kw):
    s = MagicMock()
    s.otp_link_expiry_seconds = 300
    s.otp_max_verify_attempts = 5
    s.otp_max_generate_per_window = 10
    s.otp_generate_window_minutes = 60
    s.enable_cross_platform_memory = False
    for k, v in kw.items(): setattr(s, k, v)
    return s

class TestExponentialCooldown:
    @pytest.mark.asyncio
    async def test_zero_attempts_no_cooldown(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=0))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    from app.auth.otp_linking import verify_and_link
                    ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is True and msg == "user-1"

    @pytest.mark.asyncio
    async def test_1_attempt_within_cooldown(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=1, upd=datetime.now(timezone.utc) - timedelta(milliseconds=100)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == "rate_limited"

    @pytest.mark.asyncio
    async def test_1_attempt_cooldown_elapsed(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=1, upd=datetime.now(timezone.utc) - timedelta(seconds=2)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    from app.auth.otp_linking import verify_and_link
                    _, msg = await verify_and_link("123456", "zalo", "s1")
        assert msg != "rate_limited"

    @pytest.mark.asyncio
    async def test_3_attempts_within_4s(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=3, upd=datetime.now(timezone.utc) - timedelta(seconds=1)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == "rate_limited"

    @pytest.mark.asyncio
    async def test_3_attempts_4s_elapsed(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=3, upd=datetime.now(timezone.utc) - timedelta(seconds=5)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    from app.auth.otp_linking import verify_and_link
                    _, msg = await verify_and_link("123456", "zalo", "s1")
        assert msg != "rate_limited"

    @pytest.mark.asyncio
    async def test_6_attempts_32s_not_elapsed(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=6, upd=datetime.now(timezone.utc) - timedelta(seconds=10)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(otp_max_verify_attempts=10)):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == "rate_limited"

class TestCooldownCap:
    @pytest.mark.asyncio
    async def test_cap_at_60s(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=10, upd=datetime.now(timezone.utc) - timedelta(seconds=30)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(otp_max_verify_attempts=20)):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == "rate_limited"

    @pytest.mark.asyncio
    async def test_cap_elapsed(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=10, upd=datetime.now(timezone.utc) - timedelta(seconds=61)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(otp_max_verify_attempts=20)):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    from app.auth.otp_linking import verify_and_link
                    _, msg = await verify_and_link("123456", "zalo", "s1")
        assert msg != "rate_limited"

class TestLockoutPriority:
    @pytest.mark.asyncio
    async def test_lockout_before_cooldown(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=5, upd=datetime.now(timezone.utc) - timedelta(milliseconds=50)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(otp_max_verify_attempts=5)):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == "locked"

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_code_not_found(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=None)
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("000000", "zalo", "sx")
        assert ok is False and msg == ""

    @pytest.mark.asyncio
    async def test_wrong_channel(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(ch="messenger"))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "s1")
        assert ok is False and msg == ""

    @pytest.mark.asyncio
    async def test_expired_code(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=0, exp=datetime.now(timezone.utc) - timedelta(minutes=10)))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                from app.auth.otp_linking import verify_and_link
                ok, msg = await verify_and_link("123456", "zalo", "sx")
        assert ok is False and msg == "expired"

    @pytest.mark.asyncio
    async def test_updated_at_none_skips_cooldown(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=2, upd=None))
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    from app.auth.otp_linking import verify_and_link
                    _, msg = await verify_and_link("123456", "zalo", "s1")
        assert msg != "rate_limited"

class TestProbabilisticCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_below_threshold(self):
        pf, c = _pool_conn()
        c.fetchval = AsyncMock(return_value=0)
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.otp_linking.random.random", return_value=0.05):
                    from app.auth.otp_linking import generate_link_code
                    await generate_link_code("u1", "zalo")
        cleanup = [x for x in c.execute.call_args_list if "expires_at < NOW()" in str(x)]
        assert len(cleanup) >= 1

    @pytest.mark.asyncio
    async def test_cleanup_above_threshold(self):
        pf, c = _pool_conn()
        c.fetchval = AsyncMock(return_value=0)
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.otp_linking.random.random", return_value=0.50):
                    from app.auth.otp_linking import generate_link_code
                    await generate_link_code("u1", "messenger")
        cleanup = [x for x in c.execute.call_args_list if "expires_at < NOW()" in str(x)]
        assert len(cleanup) == 0

    @pytest.mark.asyncio
    async def test_cleanup_at_boundary(self):
        pf, c = _pool_conn()
        c.fetchval = AsyncMock(return_value=0)
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms()):
                with patch("app.auth.otp_linking.random.random", return_value=0.1):
                    from app.auth.otp_linking import generate_link_code
                    await generate_link_code("u1", "telegram")
        cleanup = [x for x in c.execute.call_args_list if "expires_at < NOW()" in str(x)]
        assert len(cleanup) == 0

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        pf, c = _pool_conn()
        c.fetchval = AsyncMock(return_value=10)
        c.execute = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(otp_max_generate_per_window=10)):
                with patch("app.auth.otp_linking.random.random", return_value=0.99):
                    from app.auth.otp_linking import generate_link_code
                    with pytest.raises(ValueError, match="Rate limit exceeded"):
                        await generate_link_code("rl-user", "zalo")

class TestCrossPlatformMerge:
    @pytest.mark.asyncio
    async def test_merge_on_success(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=0))
        c.execute = AsyncMock()
        merger = AsyncMock(); merger.merge_memories = AsyncMock()
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(enable_cross_platform_memory=True)):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    with patch("app.engine.semantic_memory.cross_platform.get_cross_platform_memory", return_value=merger):
                        from app.auth.otp_linking import verify_and_link
                        ok, _ = await verify_and_link("123456", "zalo", "z-999")
        assert ok is True
        merger.merge_memories.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_failure_nonblocking(self):
        pf, c = _pool_conn()
        c.fetchrow = AsyncMock(return_value=_row(fa=0))
        c.execute = AsyncMock()
        merger = AsyncMock(); merger.merge_memories = AsyncMock(side_effect=Exception("merge failed"))
        with patch(_PP, create=True, new=pf):
            with patch(_SP, _ms(enable_cross_platform_memory=True)):
                with patch("app.auth.user_service.link_identity", AsyncMock()):
                    with patch("app.engine.semantic_memory.cross_platform.get_cross_platform_memory", return_value=merger):
                        from app.auth.otp_linking import verify_and_link
                        ok, msg = await verify_and_link("123456", "zalo", "z-err")
        assert ok is True and msg == "user-1"
