# -*- coding: utf-8 -*-
"""Sprint 194c - B1 CRITICAL: admin-context uses require_auth."""
import pytest
from unittest.mock import MagicMock, patch

_SP = "app.core.config.settings"
_RP = "app.repositories.organization_repository.get_organization_repository"

def _auth(uid="user-1", am="jwt", role="student"):
    from app.core.security import AuthenticatedUser
    return AuthenticatedUser(user_id=uid, auth_method=am, role=role)

class TestAdminContextDependency:
    def test_accepts_auth(self):
        import inspect
        from app.auth.user_router import get_my_admin_context
        sig = inspect.signature(get_my_admin_context)
        assert "auth" in sig.parameters
        from app.core.security import AuthenticatedUser
        assert sig.parameters["auth"].annotation is AuthenticatedUser

    def test_no_request_param(self):
        import inspect
        from app.auth.user_router import get_my_admin_context
        from starlette.requests import Request
        for _, p in inspect.signature(get_my_admin_context).parameters.items():
            assert p.annotation is not Request

    def test_has_depends(self):
        import inspect
        from app.auth.user_router import get_my_admin_context
        assert hasattr(inspect.signature(get_my_admin_context).parameters["auth"].default, "dependency")

class TestAdminContextAuth:
    @pytest.mark.asyncio
    async def test_student(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="student"))
        assert r["is_system_admin"] is False and r["is_org_admin"] is False

    @pytest.mark.asyncio
    async def test_admin(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="admin"))
        assert r["is_system_admin"] is True and r["is_org_admin"] is True

    @pytest.mark.asyncio
    async def test_teacher(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="teacher"))
        assert r["is_system_admin"] is False

    @pytest.mark.asyncio
    async def test_api_key_downgraded(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(am="api_key", role="student"))
        assert r["is_system_admin"] is False

    @pytest.mark.asyncio
    async def test_uid_for_org_lookup(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        repo = MagicMock(); repo.get_user_admin_orgs.return_value = []
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                from app.auth.user_router import get_my_admin_context
                await get_my_admin_context(auth=_auth(uid="uid-42", role="teacher"))
        repo.get_user_admin_orgs.assert_called_once_with("uid-42")

class TestAdminContextOrgFailure:
    @pytest.mark.asyncio
    async def test_db_error_warning(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        repo = MagicMock(); repo.get_user_admin_orgs.side_effect = RuntimeError("DB down")
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                from app.auth.user_router import get_my_admin_context
                r = await get_my_admin_context(auth=_auth(role="student"))
        assert r["_warning"] == "org admin lookup failed"
        assert r["admin_org_ids"] == [] and r["is_org_admin"] is False

    @pytest.mark.asyncio
    async def test_db_error_preserves_sysadmin(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        repo = MagicMock(); repo.get_user_admin_orgs.side_effect = Exception("timeout")
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                from app.auth.user_router import get_my_admin_context
                r = await get_my_admin_context(auth=_auth(role="admin"))
        assert r["is_system_admin"] is True and r["_warning"] == "org admin lookup failed"

    @pytest.mark.asyncio
    async def test_repo_import_failure(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        with patch(_SP, ms):
            with patch(_RP, side_effect=ImportError("missing")):
                from app.auth.user_router import get_my_admin_context
                r = await get_my_admin_context(auth=_auth(role="teacher"))
        assert "_warning" in r and r["admin_org_ids"] == []

class TestAdminContextFlags:
    @pytest.mark.asyncio
    async def test_both_true(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        repo = MagicMock(); repo.get_user_admin_orgs.return_value = []
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                from app.auth.user_router import get_my_admin_context
                r = await get_my_admin_context(auth=_auth(role="student"))
        assert r["enable_org_admin"] is True

    @pytest.mark.asyncio
    async def test_org_true_mt_false(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="student"))
        assert r["enable_org_admin"] is False

    @pytest.mark.asyncio
    async def test_both_false(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="student"))
        assert r["enable_org_admin"] is False and r["admin_org_ids"] == []

    @pytest.mark.asyncio
    async def test_multiple_orgs(self):
        ms = MagicMock(); ms.enable_org_admin = True; ms.enable_multi_tenant = True
        repo = MagicMock(); repo.get_user_admin_orgs.return_value = ["org-a", "org-b"]
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                from app.auth.user_router import get_my_admin_context
                r = await get_my_admin_context(auth=_auth(role="teacher"))
        assert r["is_org_admin"] is True and r["admin_org_ids"] == ["org-a", "org-b"]

class TestAdminContextShape:
    @pytest.mark.asyncio
    async def test_required_keys(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth())
        assert {"is_system_admin", "is_org_admin", "admin_org_ids", "enable_org_admin"}.issubset(r.keys())

    @pytest.mark.asyncio
    async def test_booleans(self):
        ms = MagicMock(); ms.enable_org_admin = False; ms.enable_multi_tenant = False
        with patch(_SP, ms):
            from app.auth.user_router import get_my_admin_context
            r = await get_my_admin_context(auth=_auth(role="student"))
        assert isinstance(r["is_system_admin"], bool) and isinstance(r["is_org_admin"], bool)
