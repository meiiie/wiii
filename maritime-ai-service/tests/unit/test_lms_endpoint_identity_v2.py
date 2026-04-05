from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_auth(**overrides):
    from app.core.security import AuthenticatedUser

    payload = {
        "user_id": "wiii-user-1",
        "auth_method": "jwt",
        "role": "student",
        "platform_role": "user",
        "organization_role": None,
        "host_role": None,
        "role_source": "jwt",
        "organization_id": "lms-hang-hai",
        "connector_id": "maritime-lms",
        "identity_version": "2",
    }
    payload.update(overrides)
    return AuthenticatedUser(**payload)


@pytest.mark.asyncio
async def test_student_profile_allows_host_teacher_overlay():
    from app.api.v1 import lms_data
    from app.integrations.lms.models import LMSStudentProfile

    profile = LMSStudentProfile(id="student-2", name="Nguyen Van B")
    connector = MagicMock()
    connector.get_student_profile.return_value = profile

    auth = _make_auth(host_role="teacher")
    request = MagicMock()

    with patch.object(lms_data.settings, "enable_lms_integration", True):
        with patch.object(lms_data, "_get_connector", return_value=connector):
                result = await lms_data.get_student_profile.__wrapped__(
                    request, "student-2", auth, "maritime-lms",
                )

    assert result["id"] == "student-2"
    connector.get_student_profile.assert_called_once_with("student-2")


@pytest.mark.asyncio
async def test_student_profile_uses_resolved_lms_identity_for_self_access():
    from app.api.v1 import lms_data
    from app.integrations.lms.models import LMSStudentProfile

    profile = LMSStudentProfile(id="student-1", name="Nguyen Van A")
    connector = MagicMock()
    connector.get_student_profile.return_value = profile

    auth = _make_auth(role="student", host_role=None)
    request = MagicMock()

    with patch.object(lms_data.settings, "enable_lms_integration", True):
        with patch.object(lms_data, "_get_connector", return_value=connector):
            with patch.object(
                lms_data,
                "resolve_lms_identity",
                new=AsyncMock(return_value=("student-1", "maritime-lms")),
            ):
                result = await lms_data.get_student_profile.__wrapped__(
                    request, "student-1", auth, "maritime-lms",
                )

    assert result["id"] == "student-1"


@pytest.mark.asyncio
async def test_org_overview_allows_wiii_org_admin_membership():
    from app.api.v1 import lms_dashboard
    from app.integrations.lms.base import LMSBackendType, LMSConnectorConfig

    connector = MagicMock()
    connector.get_config.return_value = LMSConnectorConfig(
        id="maritime-lms",
        display_name="Maritime LMS",
        backend_type=LMSBackendType.SPRING_BOOT,
        enabled=True,
        base_url="http://localhost:8088",
    )

    auth = _make_auth(organization_role="admin")
    request = MagicMock()

    with patch.object(lms_dashboard.settings, "enable_lms_integration", True):
        with patch.object(lms_dashboard, "_get_connector", return_value=connector):
                result = await lms_dashboard.org_overview.__wrapped__(
                    request, auth, "maritime-lms",
                )

    assert result["connector_id"] == "maritime-lms"
    assert result["display_name"] == "Maritime LMS"


@pytest.mark.asyncio
async def test_org_overview_allows_platform_admin_without_host_role():
    from app.api.v1 import lms_dashboard
    from app.integrations.lms.base import LMSBackendType, LMSConnectorConfig

    connector = MagicMock()
    connector.get_config.return_value = LMSConnectorConfig(
        id="maritime-lms",
        display_name="Maritime LMS",
        backend_type=LMSBackendType.SPRING_BOOT,
        enabled=True,
        base_url="http://localhost:8088",
    )

    auth = _make_auth(role="admin", platform_role="platform_admin", role_source="platform")
    request = MagicMock()

    with patch.object(lms_dashboard.settings, "enable_lms_integration", True):
        with patch.object(lms_dashboard, "_get_connector", return_value=connector):
                result = await lms_dashboard.org_overview.__wrapped__(
                    request, auth, "maritime-lms",
                )

    assert result["backend_type"] == "spring_boot"


def test_connector_resolution_prefers_auth_binding_when_header_missing():
    from app.api.v1.lms_dashboard import _resolve_connector_id

    auth = _make_auth(connector_id="connected-lms")
    assert _resolve_connector_id(auth, None) == "connected-lms"
