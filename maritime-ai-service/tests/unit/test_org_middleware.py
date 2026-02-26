"""
Tests for OrgContextMiddleware — Multi-Tenant org propagation.

Sprint 24: Multi-Organization Architecture.

Verifies:
- Middleware extracts X-Organization-ID header
- Middleware skipped when enable_multi_tenant=False
- ContextVar set and reset correctly
- No leakage between requests

NOTE: OrgContextMiddleware uses lazy imports (from ... import settings inside
dispatch). Patch at SOURCE module (app.core.config.settings).
"""

import pytest
from unittest.mock import MagicMock, patch

from starlette.requests import Request
from starlette.responses import Response

from app.core.middleware import OrgContextMiddleware


def _make_request(headers=None):
    """Create a minimal mock request."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


class TestOrgContextMiddlewareDisabled:
    """When enable_multi_tenant=False, middleware is a no-op."""

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_passthrough_when_disabled(self, mock_settings):
        mock_settings.enable_multi_tenant = False

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})
        expected_response = Response(status_code=200)

        async def call_next(req):
            return expected_response

        response = await middleware.dispatch(request, call_next)
        assert response is expected_response

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_no_contextvar_set_when_disabled(self, mock_settings):
        mock_settings.enable_multi_tenant = False

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})

        org_inside = None

        async def call_next(req):
            nonlocal org_inside
            org_inside = get_current_org_id()
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)
        assert org_inside is None  # Not set because disabled


class TestOrgContextMiddlewareEnabled:
    """When enable_multi_tenant=True, middleware propagates org context."""

    @pytest.mark.asyncio
    @patch("app.repositories.organization_repository.get_organization_repository")
    @patch("app.core.config.settings")
    async def test_sets_org_id(self, mock_settings, mock_repo_fn):
        mock_settings.enable_multi_tenant = True

        mock_repo = MagicMock()
        mock_org = MagicMock()
        mock_org.allowed_domains = ["maritime"]
        mock_repo.get_organization.return_value = mock_org
        mock_repo_fn.return_value = mock_repo

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "lms-hang-hai"})

        captured_org_id = None

        async def call_next(req):
            nonlocal captured_org_id
            captured_org_id = get_current_org_id()
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)

        assert captured_org_id == "lms-hang-hai"

    @pytest.mark.asyncio
    @patch("app.repositories.organization_repository.get_organization_repository")
    @patch("app.core.config.settings")
    async def test_resets_after_request(self, mock_settings, mock_repo_fn):
        mock_settings.enable_multi_tenant = True

        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = None
        mock_repo_fn.return_value = mock_repo

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})

        async def call_next(req):
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)

        # After request completes, context should be reset
        assert get_current_org_id() is None

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_no_header_no_context(self, mock_settings):
        mock_settings.enable_multi_tenant = True

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request()  # No X-Organization-ID

        captured_org_id = "sentinel"

        async def call_next(req):
            nonlocal captured_org_id
            captured_org_id = get_current_org_id()
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)
        assert captured_org_id is None

    @pytest.mark.asyncio
    @patch("app.repositories.organization_repository.get_organization_repository")
    @patch("app.core.config.settings")
    async def test_sets_allowed_domains(self, mock_settings, mock_repo_fn):
        mock_settings.enable_multi_tenant = True

        mock_repo = MagicMock()
        mock_org = MagicMock()
        mock_org.allowed_domains = ["maritime", "traffic_law"]
        mock_repo.get_organization.return_value = mock_org
        mock_repo_fn.return_value = mock_repo

        from app.core.org_context import get_current_org_allowed_domains

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})

        captured_domains = None

        async def call_next(req):
            nonlocal captured_domains
            captured_domains = get_current_org_allowed_domains()
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)

        assert captured_domains == ["maritime", "traffic_law"]

    @pytest.mark.asyncio
    @patch("app.repositories.organization_repository.get_organization_repository")
    @patch("app.core.config.settings")
    async def test_repo_failure_clears_org_context(self, mock_settings, mock_repo_fn):
        """Sprint 194c: If repo fails, middleware clears org context (fail-closed)."""
        mock_settings.enable_multi_tenant = True
        mock_repo_fn.side_effect = Exception("DB down")

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})

        captured_org_id = None

        async def call_next(req):
            nonlocal captured_org_id
            captured_org_id = get_current_org_id()
            return Response(status_code=200)

        await middleware.dispatch(request, call_next)

        # Sprint 194c: fail-closed — org context cleared on DB error
        assert captured_org_id is None

    @pytest.mark.asyncio
    @patch("app.repositories.organization_repository.get_organization_repository")
    @patch("app.core.config.settings")
    async def test_resets_on_exception(self, mock_settings, mock_repo_fn):
        """ContextVar reset even if call_next raises."""
        mock_settings.enable_multi_tenant = True

        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = None
        mock_repo_fn.return_value = mock_repo

        from app.core.org_context import get_current_org_id

        middleware = OrgContextMiddleware(app=MagicMock())
        request = _make_request({"X-Organization-ID": "org-1"})

        async def call_next(req):
            raise RuntimeError("Handler failed")

        with pytest.raises(RuntimeError):
            await middleware.dispatch(request, call_next)

        assert get_current_org_id() is None
