from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


def _make_settings():
    settings = MagicMock()
    settings.api_key = "primary-api-key"
    settings.lms_service_token = "lms-service-token"
    settings.jwt_secret_key = "test-secret-key"
    settings.jwt_algorithm = "HS256"
    settings.jwt_expire_minutes = 15
    settings.jwt_audience = "wiii"
    settings.environment = "production"
    settings.enable_org_membership_check = False
    settings.enable_jti_denylist = False
    settings.enforce_api_key_role_restriction = True
    settings.enable_auth_audit = False
    return settings


def _make_lms_token(**overrides) -> str:
    payload = {
        "sub": "wiii-user-1",
        "role": "teacher",
        "platform_role": "user",
        "host_role": "org_admin",
        "role_source": "lms_host",
        "active_organization_id": "org-lms",
        "connector_id": "maritime-lms",
        "identity_version": "2",
        "auth_method": "lms",
        "type": "access",
        "aud": "wiii",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    payload.update(overrides)
    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


def test_host_roles_do_not_become_platform_admin():
    from app.core.security import (
        derive_platform_role_from_legacy_role,
        map_host_role_to_legacy_role,
        normalize_host_role,
    )

    assert normalize_host_role(None) is None
    assert normalize_host_role("") is None
    assert normalize_host_role("ORG_ADMIN") == "org_admin"
    assert map_host_role_to_legacy_role("admin") == "teacher"
    assert map_host_role_to_legacy_role("org_admin") == "teacher"
    assert derive_platform_role_from_legacy_role("admin", auth_method="lms") == "user"
    assert derive_platform_role_from_legacy_role("admin", auth_method="google") == "platform_admin"


@pytest.mark.asyncio
async def test_lms_service_uses_jwt_identity_v2_claims():
    settings = _make_settings()
    token = _make_lms_token()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with (
        patch("app.core.security.settings", settings),
        patch("app.auth.token_service.settings", settings),
    ):
        from app.core.security import require_auth

        user = await require_auth(
            api_key="lms-service-token",
            credentials=creds,
            x_user_id="wiii-user-1",
            x_role="admin",
            x_session_id="sess-1",
            x_org_id=None,
            x_host_role="org_admin",
        )

    assert user.user_id == "wiii-user-1"
    assert user.role == "teacher"
    assert user.platform_role == "user"
    assert user.host_role == "org_admin"
    assert user.role_source == "lms_host"
    assert user.organization_id == "org-lms"


@pytest.mark.asyncio
async def test_lms_service_rejects_header_jwt_identity_mismatch():
    settings = _make_settings()
    token = _make_lms_token(sub="canonical-user")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with (
        patch("app.core.security.settings", settings),
        patch("app.auth.token_service.settings", settings),
    ):
        from app.core.security import require_auth

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(
                api_key="lms-service-token",
                credentials=creds,
                x_user_id="different-user",
                x_role="teacher",
                x_session_id=None,
                x_org_id=None,
                x_host_role="teacher",
            )

    assert exc_info.value.status_code == 401
    assert "mismatch" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_admin_accepts_explicit_platform_admin_even_with_teacher_legacy_role():
    from app.api.deps import _require_admin
    from app.core.security import AuthenticatedUser

    auth = AuthenticatedUser(
        user_id="platform-admin-1",
        auth_method="jwt",
        role="teacher",
        platform_role="platform_admin",
        role_source="platform",
    )

    result = await _require_admin(auth)
    assert result.platform_role == "platform_admin"
