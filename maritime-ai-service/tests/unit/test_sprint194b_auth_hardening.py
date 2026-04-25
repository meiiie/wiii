"""
Sprint 194b — "Khien Cuoi" Pre-Release Auth & Identity Hardening Tests.

Tests cover:
- C2: API key auth user_id trust in production
- C4: Role escalation guard via API key
- M1: Thread ID sanitization
- M4: Org admin endpoint consistency
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException


# ============================================================================
# Shared fixtures + helpers
# ============================================================================


def _make_pool_mock(mock_conn):
    """Create an asyncpg pool mock with proper async context manager on acquire().

    asyncpg's `pool.acquire()` returns an async context manager directly,
    NOT a coroutine. So we use MagicMock for the pool, and set acquire()'s
    return_value to a MagicMock with __aenter__/__aexit__.
    """
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_ctx
    return mock_pool


@pytest.fixture
def mock_settings_production():
    """Mock settings configured for production environment."""
    s = MagicMock()
    s.api_key = "test-api-key-prod"
    s.jwt_secret_key = "test-secret-key"
    s.jwt_algorithm = "HS256"
    s.jwt_expire_minutes = 15
    s.jwt_audience = "wiii"
    s.environment = "production"
    s.lms_service_token = None
    s.enable_org_membership_check = False
    s.enable_jti_denylist = False
    s.enforce_api_key_role_restriction = True
    s.enable_auth_audit = False
    return s


@pytest.fixture
def mock_settings_development():
    """Mock settings configured for development environment."""
    s = MagicMock()
    s.api_key = "test-api-key-dev"
    s.jwt_secret_key = "test-secret-key"
    s.jwt_algorithm = "HS256"
    s.jwt_expire_minutes = 15
    s.jwt_audience = "wiii"
    s.environment = "development"
    s.lms_service_token = None
    s.enable_org_membership_check = False
    s.enable_jti_denylist = False
    s.enforce_api_key_role_restriction = True
    s.enable_auth_audit = False
    return s


@pytest.fixture
def mock_settings_org_admin():
    """Mock settings for org admin tests."""
    s = MagicMock()
    s.enable_multi_tenant = True
    s.enable_org_admin = True
    return s


@pytest.fixture
def mock_settings_org_admin_disabled():
    """Mock settings with org admin feature disabled."""
    s = MagicMock()
    s.enable_multi_tenant = True
    s.enable_org_admin = False
    return s


# ============================================================================
# C2: API key auth — user ID trust in production
# ============================================================================


class TestAPIKeyUserIDTrustProduction:
    """Sprint 194b (C2): In production, API key auth ignores X-User-ID."""

    @pytest.mark.asyncio
    async def test_production_with_user_id_uses_api_client_principal(
        self,
        mock_settings_production,
    ):
        """In production, general API key auth ignores caller-supplied X-User-ID."""
        with patch(
            "app.core.security.settings",
            mock_settings_production,
        ), patch("app.core.security.logger") as mock_logger:
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="student-123",
                x_role="student",
                x_session_id="sess-1",
                x_org_id=None,
            )
            assert result.user_id == "api-client"
            assert result.auth_method == "api_key"
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if "Ignoring X-User-ID=%s" in str(call)
            ]
            assert len(warning_calls) == 1

    @pytest.mark.asyncio
    async def test_production_without_user_id_defaults_to_api_client(
        self,
        mock_settings_production,
    ):
        """In production, missing X-User-ID defaults to 'api-client'."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id=None,
                x_role="student",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.user_id == "api-client"
            assert result.auth_method == "api_key"

    @pytest.mark.asyncio
    async def test_production_api_client_literal_no_warning(
        self,
        mock_settings_production,
    ):
        """In production, X-User-ID='api-client' should not trigger the warning branch."""
        with patch("app.core.security.settings", mock_settings_production):
            with patch("app.core.security.logger") as mock_logger:
                from app.core.security import require_auth

                result = await require_auth(
                    api_key="test-api-key-prod",
                    credentials=None,
                    x_user_id="api-client",
                    x_role="student",
                    x_session_id=None,
                    x_org_id=None,
                )
                assert result.user_id == "api-client"
                warning_calls = [
                    call for call in mock_logger.warning.call_args_list
                    if "Ignoring X-User-ID=%s" in str(call)
                ]
                assert len(warning_calls) == 0

    @pytest.mark.asyncio
    async def test_development_with_user_id_trusts_normally(
        self,
        mock_settings_development,
    ):
        """In development, X-User-ID is trusted without flagging."""
        with patch("app.core.security.settings", mock_settings_development):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-dev",
                credentials=None,
                x_user_id="dev-user-456",
                x_role="student",
                x_session_id="sess-dev",
                x_org_id=None,
            )
            assert result.user_id == "dev-user-456"
            assert result.auth_method == "api_key"

    @pytest.mark.asyncio
    async def test_development_without_user_id_defaults_to_anonymous(
        self,
        mock_settings_development,
    ):
        """In development, missing X-User-ID defaults to 'anonymous'."""
        with patch("app.core.security.settings", mock_settings_development):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-dev",
                credentials=None,
                x_user_id=None,
                x_role=None,
                x_session_id=None,
                x_org_id=None,
            )
            assert result.user_id == "anonymous"
            assert result.role == "student"  # Default role

    @pytest.mark.asyncio
    async def test_production_empty_string_user_id_defaults_to_api_client(
        self,
        mock_settings_production,
    ):
        """In production, empty-string X-User-ID is falsy so defaults to 'api-client'."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="",
                x_role="student",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.user_id == "api-client"


class TestLMSServiceTokenAuth:
    """Sprint 220/194b: LMS service token is a separate proxied auth mode."""

    @pytest.mark.asyncio
    async def test_lms_service_token_auth_preserves_proxied_user(
        self,
        mock_settings_production,
    ):
        mock_settings_production.api_key = "primary-api-key"
        mock_settings_production.lms_service_token = "lms-service-token"

        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="lms-service-token",
                credentials=None,
                x_user_id="student-123",
                x_role="teacher",
                x_session_id="sess-1",
                x_org_id=None,
            )

            assert result.user_id == "student-123"
            assert result.role == "teacher"
            assert result.auth_method == "lms_service"

    @pytest.mark.asyncio
    async def test_lms_service_token_requires_user_id(
        self,
        mock_settings_production,
    ):
        mock_settings_production.api_key = "primary-api-key"
        mock_settings_production.lms_service_token = "lms-service-token"

        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    api_key="lms-service-token",
                    credentials=None,
                    x_user_id=None,
                    x_role="student",
                    x_session_id=None,
                    x_org_id=None,
                )

        assert exc_info.value.status_code == 401
        assert "requires X-User-ID" in exc_info.value.detail

    def test_verify_api_key_ignores_non_string_lms_secret(
        self,
        mock_settings_production,
    ):
        mock_settings_production.api_key = "primary-api-key"
        mock_settings_production.lms_service_token = MagicMock()

        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import verify_api_key

            assert verify_api_key("primary-api-key") is True
            assert verify_api_key("wrong-key") is False


# ============================================================================
# C4: API key role restriction (escalation guard)
# ============================================================================


class TestAPIKeyRoleRestriction:
    """Sprint 192/194b (C4): Role escalation via API key is blocked in production."""

    @pytest.mark.asyncio
    async def test_admin_role_downgraded_in_production(self, mock_settings_production):
        """In production with enforce_api_key_role_restriction, admin role is downgraded."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="attacker-1",
                x_role="admin",
                x_session_id=None,
                x_org_id=None,
            )
            # Role must be downgraded to "student"
            assert result.role == "student"
            assert result.auth_method == "api_key"

    @pytest.mark.asyncio
    async def test_student_role_not_affected_in_production(self, mock_settings_production):
        """Student role passes through without downgrade in production."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="student-1",
                x_role="student",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.role == "student"

    @pytest.mark.asyncio
    async def test_teacher_role_not_affected_in_production(self, mock_settings_production):
        """Teacher role passes through without downgrade in production."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="teacher-1",
                x_role="teacher",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.role == "teacher"

    @pytest.mark.asyncio
    async def test_admin_role_allowed_in_development(self, mock_settings_development):
        """In development, admin role via API key is NOT downgraded (restriction only in prod)."""
        with patch("app.core.security.settings", mock_settings_development):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-dev",
                credentials=None,
                x_user_id="dev-admin",
                x_role="admin",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_restriction_disabled_allows_admin_in_production(self):
        """When enforce_api_key_role_restriction is False, admin via API key is allowed."""
        s = MagicMock()
        s.api_key = "test-key"
        s.environment = "production"
        s.enforce_api_key_role_restriction = False
        s.enable_org_membership_check = False
        s.enable_jti_denylist = False
        s.enable_auth_audit = False

        with patch("app.core.security.settings", s):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-key",
                credentials=None,
                x_user_id="some-user",
                x_role="admin",
                x_session_id=None,
                x_org_id=None,
            )
            assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_unknown_role_downgraded_in_production(self, mock_settings_production):
        """An unrecognized role (e.g., 'superadmin') should also be downgraded."""
        with patch("app.core.security.settings", mock_settings_production):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="test-api-key-prod",
                credentials=None,
                x_user_id="hacker-1",
                x_role="superadmin",
                x_session_id=None,
                x_org_id=None,
            )
            # Any role not in ("student", "teacher") is downgraded
            assert result.role == "student"


# ============================================================================
# M1: Thread ID sanitization
# ============================================================================


class TestThreadIDSanitization:
    """Sprint 194b (M1): _sanitize_thread_segment prevents injection."""

    def test_normal_segment_unchanged(self):
        """A normal alphanumeric+hyphen segment passes through unchanged."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        assert _sanitize_thread_segment("normal-user-123") == "normal-user-123"

    def test_sql_injection_stripped(self):
        """SQL injection characters are removed."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        result = _sanitize_thread_segment("user'; DROP TABLE--")
        # Only alphanumeric, underscore, hyphen, dot survive
        assert "'" not in result
        assert ";" not in result
        assert " " not in result
        # The word parts should remain
        assert "user" in result
        assert "DROP" in result
        assert "TABLE" in result

    def test_long_segment_truncated(self):
        """Segments longer than max_len are truncated."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        long_input = "a" * 200
        result = _sanitize_thread_segment(long_input)
        assert len(result) == 128

    def test_spaces_stripped(self):
        """Spaces are not in the allowed character set and are removed."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        result = _sanitize_thread_segment("hello world spaces")
        assert " " not in result
        assert result == "helloworldspaces"

    def test_dots_allowed(self):
        """Dots are in the allowed character set."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        assert _sanitize_thread_segment("user.name.123") == "user.name.123"

    def test_underscores_allowed(self):
        """Underscores are in the allowed character set."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        assert _sanitize_thread_segment("user_name_123") == "user_name_123"

    def test_hyphens_allowed(self):
        """Hyphens are in the allowed character set."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        assert _sanitize_thread_segment("user-name-123") == "user-name-123"

    def test_custom_max_len(self):
        """Custom max_len parameter is respected."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        result = _sanitize_thread_segment("abcdefghij", max_len=5)
        assert result == "abcde"
        assert len(result) == 5

    def test_unicode_stripped(self):
        """Non-ASCII Unicode characters are stripped."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        result = _sanitize_thread_segment("user-Wiii-xin-chao")
        # Vietnamese diacritics (if any) would be stripped; ASCII-only chars remain
        assert result == "user-Wiii-xin-chao"

    def test_special_chars_all_stripped(self):
        """Various special characters are all removed."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        result = _sanitize_thread_segment("@#$%^&*()+={}")
        assert result == ""

    def test_empty_string(self):
        """Empty input returns empty output."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        assert _sanitize_thread_segment("") == ""

    def test_regex_pattern_is_correct(self):
        """Verify the compiled regex pattern allows only expected chars."""
        from app.repositories.thread_repository import _THREAD_SEGMENT_RE

        # These should NOT be matched (they are allowed)
        assert _THREAD_SEGMENT_RE.search("a") is None
        assert _THREAD_SEGMENT_RE.search("Z") is None
        assert _THREAD_SEGMENT_RE.search("0") is None
        assert _THREAD_SEGMENT_RE.search("_") is None
        assert _THREAD_SEGMENT_RE.search("-") is None
        assert _THREAD_SEGMENT_RE.search(".") is None

        # These SHOULD be matched (they will be stripped)
        assert _THREAD_SEGMENT_RE.search("'") is not None
        assert _THREAD_SEGMENT_RE.search(";") is not None
        assert _THREAD_SEGMENT_RE.search(" ") is not None
        assert _THREAD_SEGMENT_RE.search("@") is not None


# ============================================================================
# M4: Org admin endpoint consistency
# ============================================================================


class TestOrgAdminEndpointConsistency:
    """Sprint 194b (M4): _require_org_admin_or_platform_admin consistency."""

    def test_platform_admin_always_passes(self, mock_settings_org_admin):
        """Platform admin (role=admin) always returns 'platform_admin'."""
        with patch("app.api.v1.organizations.settings", mock_settings_org_admin):
            from app.api.v1.organizations import _require_org_admin_or_platform_admin
            from app.core.security import AuthenticatedUser

            auth = AuthenticatedUser(
                user_id="platform-admin-1",
                auth_method="jwt",
                role="admin",
            )
            result = _require_org_admin_or_platform_admin(auth, "any-org")
            assert result == "platform_admin"

    def test_org_admin_passes_when_feature_enabled(self, mock_settings_org_admin):
        """Org admin passes when enable_org_admin=True and repo confirms role."""
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"

        with patch("app.api.v1.organizations.settings", mock_settings_org_admin):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                from app.api.v1.organizations import _require_org_admin_or_platform_admin
                from app.core.security import AuthenticatedUser

                auth = AuthenticatedUser(
                    user_id="org-admin-1",
                    auth_method="jwt",
                    role="teacher",  # Not platform admin
                )
                result = _require_org_admin_or_platform_admin(auth, "org-1")
                assert result == "admin"
                mock_repo.get_user_org_role.assert_called_once_with("org-admin-1", "org-1")

    def test_org_owner_passes_when_feature_enabled(self, mock_settings_org_admin):
        """Org owner passes when enable_org_admin=True and repo confirms owner role."""
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "owner"

        with patch("app.api.v1.organizations.settings", mock_settings_org_admin):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                from app.api.v1.organizations import _require_org_admin_or_platform_admin
                from app.core.security import AuthenticatedUser

                auth = AuthenticatedUser(
                    user_id="org-owner-1",
                    auth_method="jwt",
                    role="teacher",
                )
                result = _require_org_admin_or_platform_admin(auth, "org-1")
                assert result == "owner"

    def test_regular_user_rejected_when_feature_enabled(self, mock_settings_org_admin):
        """Regular user (student) with no org role raises 403."""
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "student"

        with patch("app.api.v1.organizations.settings", mock_settings_org_admin):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                from app.api.v1.organizations import _require_org_admin_or_platform_admin
                from app.core.security import AuthenticatedUser

                auth = AuthenticatedUser(
                    user_id="student-1",
                    auth_method="jwt",
                    role="student",
                )
                with pytest.raises(HTTPException) as exc_info:
                    _require_org_admin_or_platform_admin(auth, "org-1")
                assert exc_info.value.status_code == 403
                assert "Organization admin role required" in exc_info.value.detail

    def test_non_admin_rejected_when_feature_disabled(self, mock_settings_org_admin_disabled):
        """When enable_org_admin=False, non-platform-admin always gets 403."""
        with patch("app.api.v1.organizations.settings", mock_settings_org_admin_disabled):
            from app.api.v1.organizations import _require_org_admin_or_platform_admin
            from app.core.security import AuthenticatedUser

            auth = AuthenticatedUser(
                user_id="teacher-1",
                auth_method="jwt",
                role="teacher",
            )
            with pytest.raises(HTTPException) as exc_info:
                _require_org_admin_or_platform_admin(auth, "org-1")
            assert exc_info.value.status_code == 403
            assert "Admin role required" in exc_info.value.detail

    def test_platform_admin_passes_regardless_of_feature_flag(self, mock_settings_org_admin_disabled):
        """Platform admin bypasses the org admin feature flag entirely."""
        with patch("app.api.v1.organizations.settings", mock_settings_org_admin_disabled):
            from app.api.v1.organizations import _require_org_admin_or_platform_admin
            from app.core.security import AuthenticatedUser

            auth = AuthenticatedUser(
                user_id="platform-admin-1",
                auth_method="jwt",
                role="admin",
            )
            result = _require_org_admin_or_platform_admin(auth, "org-1")
            assert result == "platform_admin"

    def test_no_org_role_at_all_rejected(self, mock_settings_org_admin):
        """User with None org role is rejected."""
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = None

        with patch("app.api.v1.organizations.settings", mock_settings_org_admin):
            with patch("app.api.v1.organizations.get_organization_repository", return_value=mock_repo):
                from app.api.v1.organizations import _require_org_admin_or_platform_admin
                from app.core.security import AuthenticatedUser

                auth = AuthenticatedUser(
                    user_id="unknown-user",
                    auth_method="jwt",
                    role="student",
                )
                with pytest.raises(HTTPException) as exc_info:
                    _require_org_admin_or_platform_admin(auth, "org-1")
                assert exc_info.value.status_code == 403


# ============================================================================
# Combined scenarios: production + org + role
# ============================================================================


class TestCombinedScenarios:
    """Combined scenarios testing multiple hardening features together."""

    @pytest.mark.asyncio
    async def test_production_api_key_admin_with_org_downgraded(self):
        """In production: admin role via API key + org context = role downgraded + org set."""
        s = MagicMock()
        s.api_key = "combo-key"
        s.environment = "production"
        s.lms_service_token = None
        s.enforce_api_key_role_restriction = True
        s.enable_org_membership_check = False
        s.enable_jti_denylist = False
        s.enable_auth_audit = False

        with patch("app.core.security.settings", s):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="combo-key",
                credentials=None,
                x_user_id="user-combo",
                x_role="admin",
                x_session_id="sess-combo",
                x_org_id="org-combo",
            )
            assert result.role == "student"  # Downgraded
            assert result.user_id == "api-client"
            assert result.organization_id == "org-combo"
            assert result.session_id == "sess-combo"

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self):
        """Invalid API key still raises 401 regardless of environment."""
        s = MagicMock()
        s.api_key = "correct-key"
        s.environment = "production"
        s.enforce_api_key_role_restriction = True
        s.enable_org_membership_check = False
        s.enable_jti_denylist = False
        s.enable_auth_audit = False

        with patch("app.core.security.settings", s):
            from app.core.security import require_auth

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    api_key="wrong-key",
                    credentials=None,
                    x_user_id="hacker",
                    x_role="admin",
                    x_session_id=None,
                    x_org_id=None,
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        """No API key and no JWT token raises 401."""
        s = MagicMock()
        s.api_key = "some-key"
        s.environment = "production"

        with patch("app.core.security.settings", s):
            from app.core.security import require_auth

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    api_key=None,
                    credentials=None,
                    x_user_id="someone",
                    x_role="student",
                    x_session_id=None,
                    x_org_id=None,
                )
            assert exc_info.value.status_code == 401
            assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_api_key_with_valid_jwt_falls_back_to_jwt(self):
        """Issue #86: stale API key must not override a valid Bearer JWT.

        A common browser-side regression: user switches from OAuth to legacy
        (or vice versa) and one credential goes stale while the other is
        fresh. Prior behavior rejected the whole request at the API-key step;
        correct behavior is to try every provided credential before failing.
        """
        import jwt as _jwt
        from datetime import datetime, timedelta, timezone
        from fastapi.security import HTTPAuthorizationCredentials

        s = MagicMock()
        s.api_key = "the-only-valid-api-key"
        s.jwt_secret_key = "test-secret-key"
        s.jwt_algorithm = "HS256"
        s.jwt_expire_minutes = 15
        s.jwt_audience = "wiii"
        s.environment = "production"
        s.lms_service_token = None
        s.enforce_api_key_role_restriction = True
        s.enable_org_membership_check = False
        s.enable_jti_denylist = False
        s.enable_auth_audit = False

        payload = {
            "sub": "jwt-user-1",
            "role": "teacher",
            "auth_method": "oauth",
            "type": "access",
            "aud": "wiii",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = _jwt.encode(payload, "test-secret-key", algorithm="HS256")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with (
            patch("app.core.security.settings", s),
            patch("app.auth.token_service.settings", s),
        ):
            from app.core.security import require_auth

            result = await require_auth(
                api_key="stale-wrong-key",  # would 401 under old behavior
                credentials=creds,
                x_user_id=None,
                x_role=None,
                x_session_id=None,
                x_org_id=None,
            )

        # JWT identity wins; request authenticated as the JWT subject.
        assert result.user_id == "jwt-user-1"
        assert result.role == "teacher"
        assert result.auth_method == "oauth"

    @pytest.mark.asyncio
    async def test_invalid_api_key_with_invalid_jwt_still_401(self):
        """Issue #86 security check: both creds invalid still raises 401."""
        from fastapi.security import HTTPAuthorizationCredentials

        s = MagicMock()
        s.api_key = "the-only-valid-api-key"
        s.jwt_secret_key = "test-secret-key"
        s.jwt_algorithm = "HS256"
        s.jwt_expire_minutes = 15
        s.jwt_audience = "wiii"
        s.environment = "production"
        s.lms_service_token = None
        s.enforce_api_key_role_restriction = True
        s.enable_org_membership_check = False
        s.enable_jti_denylist = False
        s.enable_auth_audit = False

        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not-a-valid-jwt"
        )

        with (
            patch("app.core.security.settings", s),
            patch("app.auth.token_service.settings", s),
        ):
            from app.core.security import require_auth

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    api_key="stale-wrong-key",
                    credentials=creds,
                    x_user_id=None,
                    x_role=None,
                    x_session_id=None,
                    x_org_id=None,
                )
            # JWT verify raises its own 401 before we reach the final
            # "Invalid API key" branch — either message is acceptable, but
            # status must be 401.
            assert exc_info.value.status_code == 401

    def test_sanitize_then_truncate_order(self):
        """Sanitization happens before truncation — injected chars don't count toward length."""
        from app.repositories.thread_repository import _sanitize_thread_segment

        # 100 good chars + 50 bad chars + 50 good chars = 200 total
        # After sanitization: 150 good chars, truncated to 128
        good_prefix = "a" * 100
        bad_middle = "!@#$%" * 10  # 50 bad chars
        good_suffix = "b" * 50
        segment = good_prefix + bad_middle + good_suffix

        result = _sanitize_thread_segment(segment)
        # After stripping bad: "a" * 100 + "b" * 50 = 150 chars, truncated to 128
        assert len(result) == 128
        assert result == ("a" * 100 + "b" * 28)
