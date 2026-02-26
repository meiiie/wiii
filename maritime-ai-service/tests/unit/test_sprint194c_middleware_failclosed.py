# -*- coding: utf-8 -*-
"""Sprint 194c - B6 HIGH: OrgContextMiddleware fail-closed on DB error."""
import pytest
from unittest.mock import MagicMock, patch

_SP = "app.core.config.settings"
_RP = "app.repositories.organization_repository.get_organization_repository"

def _app(captured_org, captured_domains=None):
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from app.core.middleware import OrgContextMiddleware
    async def endpoint(request: Request) -> Response:
        from app.core.org_context import current_org_id, current_org_allowed_domains
        captured_org.append(current_org_id.get())
        if captured_domains is not None:
            captured_domains.append(current_org_allowed_domains.get())
        return Response("ok")
    app = Starlette()
    app.add_route("/test", endpoint)
    app.add_middleware(OrgContextMiddleware)
    return app

class TestFailClosed:
    def test_db_error_clears_org(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        repo = MagicMock(); repo.get_organization.side_effect = RuntimeError("refused")
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured), raise_server_exceptions=False).get("/test", headers={"X-Organization-ID": "org-boom"})
        assert captured[0] is None

    def test_timeout_clears_org(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        repo = MagicMock(); repo.get_organization.side_effect = TimeoutError("slow")
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured), raise_server_exceptions=False).get("/test", headers={"X-Organization-ID": "org-slow"})
        assert captured[0] is None

    def test_import_error_clears_org(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        with patch(_SP, ms):
            with patch(_RP, side_effect=ImportError("missing")):
                TestClient(_app(captured), raise_server_exceptions=False).get("/test", headers={"X-Organization-ID": "org-imp"})
        assert captured[0] is None

    def test_db_error_domains_none(self):
        from starlette.testclient import TestClient
        co = []; cd = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        repo = MagicMock(); repo.get_organization.side_effect = Exception("err")
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(co, cd), raise_server_exceptions=False).get("/test", headers={"X-Organization-ID": "org-x"})
        assert co[0] is None and cd[0] is None

class TestSuccess:
    def test_sets_org_id(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        org = MagicMock(); org.allowed_domains = ["maritime"]
        repo = MagicMock(); repo.get_organization.return_value = org
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured)).get("/test", headers={"X-Organization-ID": "org-good"})
        assert captured[0] == "org-good"

    def test_sets_allowed_domains(self):
        from starlette.testclient import TestClient
        co = []; cd = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        org = MagicMock(); org.allowed_domains = ["maritime", "traffic_law"]
        repo = MagicMock(); repo.get_organization.return_value = org
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(co, cd)).get("/test", headers={"X-Organization-ID": "org-multi"})
        assert cd[0] == ["maritime", "traffic_law"]

    def test_org_not_found(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        repo = MagicMock(); repo.get_organization.return_value = None
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured)).get("/test", headers={"X-Organization-ID": "org-unknown"})
        assert captured[0] == "org-unknown"

class TestNoHeader:
    def test_no_org_header(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        with patch(_SP, ms):
            TestClient(_app(captured)).get("/test")
        assert captured[0] is None

class TestDisabled:
    def test_disabled_no_db(self):
        from starlette.testclient import TestClient
        captured = []; calls = []
        ms = MagicMock(); ms.enable_multi_tenant = False
        with patch(_SP, ms):
            with patch(_RP) as mr:
                mr.side_effect = lambda: calls.append(1) or MagicMock()
                TestClient(_app(captured)).get("/test", headers={"X-Organization-ID": "org-x"})
        assert len(calls) == 0

class TestCleanup:
    def test_org_reset_after_request(self):
        from starlette.testclient import TestClient
        from app.core.org_context import current_org_id
        assert current_org_id.get() is None
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = ""
        org = MagicMock(); org.allowed_domains = ["maritime"]
        repo = MagicMock(); repo.get_organization.return_value = org
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured)).get("/test", headers={"X-Organization-ID": "org-cleanup"})
        assert captured[0] == "org-cleanup"
        assert current_org_id.get() is None

class TestSubdomain:
    def test_subdomain_extraction(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = "holilihu.online"
        org = MagicMock(); org.allowed_domains = ["maritime"]
        repo = MagicMock(); repo.get_organization.return_value = org
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured)).get("/test", headers={"Host": "my-org.holilihu.online"})
        assert captured[0] == "my-org"

    def test_header_priority(self):
        from starlette.testclient import TestClient
        captured = []
        ms = MagicMock(); ms.enable_multi_tenant = True; ms.subdomain_base_domain = "holilihu.online"
        org = MagicMock(); org.allowed_domains = ["maritime"]
        repo = MagicMock(); repo.get_organization.return_value = org
        with patch(_SP, ms):
            with patch(_RP, return_value=repo):
                TestClient(_app(captured)).get("/test", headers={"X-Organization-ID": "header-org", "Host": "sub.holilihu.online"})
        assert captured[0] == "header-org"
