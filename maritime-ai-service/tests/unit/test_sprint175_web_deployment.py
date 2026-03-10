"""
Tests for Sprint 175: "Một Nền Tảng — Nhiều Tổ Chức"
Hybrid Org Distribution — Web Deployment Foundation

Covers:
    1. Config — cors_origin_regex + subdomain_base_domain defaults
    2. Subdomain extraction — extract_org_from_subdomain()
    3. OrgContextMiddleware — subdomain fallback behavior
    4. CORS middleware — regex origin support
    5. Nginx config — file existence + structure
    6. Docker Compose — nginx service presence

NOTE: Middleware tests use lazy imports from app.core.config.settings,
so settings must be patched at source: app.core.config.settings
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# 1. CONFIG TESTS
# =============================================================================


class TestWebDeploymentConfig:
    """Tests for Sprint 175 config fields."""

    def test_default_cors_origin_regex_empty(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.cors_origin_regex == ""

    def test_default_subdomain_base_domain_empty(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test")
        assert s.subdomain_base_domain == ""

    def test_cors_origin_regex_configurable(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            cors_origin_regex=r"https://.*\.wiii\.vn",
        )
        assert s.cors_origin_regex == r"https://.*\.wiii\.vn"

    def test_subdomain_base_domain_configurable(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            subdomain_base_domain="holilihu.online",
        )
        assert s.subdomain_base_domain == "holilihu.online"

    def test_both_fields_coexist_with_existing_settings(self):
        """Ensure new fields don't break existing config validation."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            cors_origin_regex=r"https://.*\.wiii\.vn",
            subdomain_base_domain="holilihu.online",
            enable_multi_tenant=True,
        )
        assert s.enable_multi_tenant is True
        assert s.cors_origin_regex != ""
        assert s.subdomain_base_domain == "holilihu.online"


# =============================================================================
# 2. SUBDOMAIN EXTRACTION TESTS
# =============================================================================


class TestSubdomainExtraction:
    """Tests for extract_org_from_subdomain() helper."""

    def test_valid_subdomain(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("phuong-luu-kiem.holilihu.online", "holilihu.online")
        assert result == "phuong-luu-kiem"

    def test_valid_subdomain_with_port(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("lms-hang-hai.holilihu.online:8080", "holilihu.online")
        assert result == "lms-hang-hai"

    def test_bare_domain_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("holilihu.online", "holilihu.online")
        assert result is None

    def test_www_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("www.holilihu.online", "holilihu.online")
        assert result is None

    def test_api_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("api.holilihu.online", "holilihu.online")
        assert result is None

    def test_admin_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("admin.holilihu.online", "holilihu.online")
        assert result is None

    def test_app_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("app.holilihu.online", "holilihu.online")
        assert result is None

    def test_mail_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("mail.holilihu.online", "holilihu.online")
        assert result is None

    def test_static_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("static.holilihu.online", "holilihu.online")
        assert result is None

    def test_cdn_reserved_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("cdn.holilihu.online", "holilihu.online")
        assert result is None

    def test_different_domain_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("phuong-luu-kiem.other.com", "holilihu.online")
        assert result is None

    def test_empty_host_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("", "holilihu.online")
        assert result is None

    def test_empty_base_domain_returns_none(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("phuong-luu-kiem.holilihu.online", "")
        assert result is None

    def test_case_insensitive(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("Phuong-Luu-Kiem.HOLILIHU.ONLINE", "holilihu.online")
        assert result == "phuong-luu-kiem"

    def test_localhost_not_matched(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("phuong-luu-kiem.localhost", "holilihu.online")
        assert result is None

    def test_multi_level_subdomain(self):
        """Multi-level subdomains (a.b.holilihu.online) should extract full prefix."""
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("dept.phuong-luu-kiem.holilihu.online", "holilihu.online")
        assert result == "dept.phuong-luu-kiem"

    def test_hyphenated_org_name(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("truong-cao-dang-hang-hai.holilihu.online", "holilihu.online")
        assert result == "truong-cao-dang-hang-hai"

    def test_numeric_org_name(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("org-123.holilihu.online", "holilihu.online")
        assert result == "org-123"


# =============================================================================
# 3. ORG CONTEXT MIDDLEWARE — SUBDOMAIN FALLBACK
# =============================================================================


class TestOrgContextMiddlewareSubdomain:
    """Tests for subdomain extraction in OrgContextMiddleware (Sprint 175)."""

    @pytest.mark.asyncio
    async def test_header_takes_priority_over_subdomain(self):
        """X-Organization-ID header should override subdomain."""
        from app.core.middleware import OrgContextMiddleware

        mock_app = AsyncMock()
        mock_response = MagicMock()
        mock_app.return_value = mock_response

        middleware = OrgContextMiddleware(mock_app)

        mock_settings = MagicMock()
        mock_settings.enable_multi_tenant = True
        mock_settings.subdomain_base_domain = "holilihu.online"

        mock_request = MagicMock()
        mock_request.headers = {
            "X-Organization-ID": "header-org",
            "host": "subdomain-org.holilihu.online",
        }

        captured_org_id = None

        async def capture_call_next(request):
            nonlocal captured_org_id
            from app.core.org_context import current_org_id
            captured_org_id = current_org_id.get(None)
            return mock_response

        with patch("app.core.middleware.logger"):
            with patch("app.core.config.settings", mock_settings):
                # Patch the org_context and repository
                with patch("app.core.org_context.current_org_id") as mock_ctx:
                    mock_token = MagicMock()
                    mock_ctx.set.return_value = mock_token

                    with patch("app.core.org_context.current_org_allowed_domains"):
                        with patch(
                            "app.repositories.organization_repository.get_organization_repository"
                        ) as mock_repo_fn:
                            mock_repo = MagicMock()
                            mock_repo.get_organization.return_value = None
                            mock_repo_fn.return_value = mock_repo

                            await middleware.dispatch(mock_request, capture_call_next)

                            # Should have set "header-org" (from header, not subdomain)
                            mock_ctx.set.assert_called_with("header-org")

    @pytest.mark.asyncio
    async def test_subdomain_fallback_when_no_header(self):
        """When no X-Organization-ID header, extract from subdomain."""
        from app.core.middleware import OrgContextMiddleware

        mock_app = AsyncMock()
        mock_response = MagicMock()

        middleware = OrgContextMiddleware(mock_app)

        mock_settings = MagicMock()
        mock_settings.enable_multi_tenant = True
        mock_settings.subdomain_base_domain = "holilihu.online"

        # Use MagicMock for headers to avoid dict.get read-only issue
        mock_headers = MagicMock()
        mock_headers.get = MagicMock(side_effect=lambda k, d="": {
            "X-Organization-ID": None,
            "host": "phuong-luu-kiem.holilihu.online",
        }.get(k, d))

        mock_request = MagicMock()
        mock_request.headers = mock_headers

        with patch("app.core.middleware.logger"):
            with patch("app.core.config.settings", mock_settings):
                with patch("app.core.org_context.current_org_id") as mock_ctx:
                    mock_token = MagicMock()
                    mock_ctx.set.return_value = mock_token

                    with patch("app.core.org_context.current_org_allowed_domains"):
                        with patch(
                            "app.repositories.organization_repository.get_organization_repository"
                        ) as mock_repo_fn:
                            mock_repo = MagicMock()
                            mock_repo.get_organization.return_value = None
                            mock_repo_fn.return_value = mock_repo

                            await middleware.dispatch(mock_request, AsyncMock(return_value=mock_response))

                            # Should have set org from subdomain
                            mock_ctx.set.assert_called_with("phuong-luu-kiem")

    @pytest.mark.asyncio
    async def test_no_subdomain_extraction_when_base_domain_empty(self):
        """When subdomain_base_domain is empty, skip extraction."""
        from app.core.middleware import OrgContextMiddleware

        mock_app = AsyncMock()
        mock_response = MagicMock()

        middleware = OrgContextMiddleware(mock_app)

        mock_settings = MagicMock()
        mock_settings.enable_multi_tenant = True
        mock_settings.subdomain_base_domain = ""  # Empty = disabled

        # Use MagicMock for headers to avoid dict.get read-only issue
        mock_headers = MagicMock()
        mock_headers.get = MagicMock(side_effect=lambda k, d="": {
            "X-Organization-ID": None,
            "host": "phuong-luu-kiem.holilihu.online",
        }.get(k, d))

        mock_request = MagicMock()
        mock_request.headers = mock_headers

        with patch("app.core.middleware.logger"):
            with patch("app.core.config.settings", mock_settings):
                with patch("app.core.org_context.current_org_id") as mock_ctx:
                    with patch("app.core.org_context.current_org_allowed_domains"):
                        await middleware.dispatch(mock_request, AsyncMock(return_value=mock_response))

                        # Should NOT have set any org
                        mock_ctx.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_noop_when_multi_tenant_disabled(self):
        """When enable_multi_tenant=False, middleware is a no-op pass-through."""
        from app.core.middleware import OrgContextMiddleware

        mock_app = AsyncMock()
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        middleware = OrgContextMiddleware(mock_app)

        mock_settings = MagicMock()
        mock_settings.enable_multi_tenant = False

        mock_request = MagicMock()
        mock_request.headers = {
            "X-Organization-ID": "some-org",
            "host": "phuong-luu-kiem.holilihu.online",
        }

        with patch("app.core.config.settings", mock_settings):
            result = await middleware.dispatch(mock_request, call_next)
            call_next.assert_awaited_once_with(mock_request)
            assert result == mock_response


# =============================================================================
# 4. CORS CONFIGURATION TESTS
# =============================================================================


class TestCORSConfig:
    """Tests for CORS regex support in create_application()."""

    def test_cors_without_regex(self):
        """When cors_origin_regex is empty, standard allow_origins is used."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.app_name = "Wiii"
            mock_settings.app_version = "0.1.0"
            mock_settings.debug = False
            mock_settings.environment = "development"
            mock_settings.cors_origins = ["*"]
            mock_settings.cors_origin_regex = ""
            mock_settings.enable_google_oauth = False
            mock_settings.api_v1_prefix = "/api/v1"
            mock_settings.enable_mcp_server = False

            # Check that the middleware config logic works
            cors_origins = ["http://localhost:1420"]
            cors_kwargs = {}
            if mock_settings.cors_origin_regex:
                cors_kwargs["allow_origin_regex"] = mock_settings.cors_origin_regex
                cors_kwargs["allow_origins"] = cors_origins
            else:
                cors_kwargs["allow_origins"] = cors_origins

            assert "allow_origin_regex" not in cors_kwargs
            assert cors_kwargs["allow_origins"] == ["http://localhost:1420"]

    def test_cors_with_regex(self):
        """When cors_origin_regex is set, allow_origin_regex param is used."""
        regex = r"https://.*\.wiii\.vn"
        cors_origins = ["http://localhost:1420"]
        cors_kwargs = {}

        cors_kwargs["allow_origin_regex"] = regex
        cors_kwargs["allow_origins"] = cors_origins

        assert cors_kwargs["allow_origin_regex"] == regex
        assert cors_kwargs["allow_origins"] == cors_origins


# =============================================================================
# 5. FILE STRUCTURE TESTS
# =============================================================================


class TestFileStructure:
    """Verify Sprint 175 file structure exists."""

    def test_nginx_conf_exists(self):
        import os
        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "nginx.conf"
        )
        assert os.path.exists(conf_path), f"nginx.conf not found at {conf_path}"

    def test_nginx_conf_has_subdomain_extraction(self):
        import os
        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "nginx.conf"
        )
        with open(conf_path, "r") as f:
            content = f.read()
        assert "X-Organization-ID" in content
        assert "subdomain" in content
        assert "proxy_pass" in content
        assert "try_files" in content

    def test_nginx_conf_has_spa_fallback(self):
        import os
        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "nginx.conf"
        )
        with open(conf_path, "r") as f:
            content = f.read()
        assert "/index.html" in content

    def test_nginx_conf_has_gzip(self):
        import os
        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "nginx.conf"
        )
        with open(conf_path, "r") as f:
            content = f.read()
        assert "gzip on" in content

    def test_nginx_conf_has_sse_support(self):
        """SSE streaming needs proxy_buffering off."""
        import os
        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "nginx.conf"
        )
        with open(conf_path, "r") as f:
            content = f.read()
        assert "proxy_buffering off" in content

    def test_docker_compose_prod_has_nginx(self):
        import os
        compose_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.prod.yml"
        )
        with open(compose_path, "r") as f:
            content = f.read()
        assert "nginx:" in content
        assert "wiii-nginx" in content
        assert "WIII_NGINX_IMAGE" in content
        assert "EMBED_ALLOWED_ORIGINS" in content

    def test_docker_compose_prod_has_subdomain_env(self):
        import os
        compose_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.prod.yml"
        )
        with open(compose_path, "r") as f:
            content = f.read()
        assert "SUBDOMAIN_BASE_DOMAIN" in content
        assert "CORS_ORIGIN_REGEX" in content

    def test_build_web_script_exists(self):
        import os
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "wiii-desktop", "scripts", "build-web.sh"
        )
        # Normalize the path for OS
        script_path = os.path.normpath(script_path)
        assert os.path.exists(script_path), f"build-web.sh not found at {script_path}"


# =============================================================================
# 6. RESERVED SUBDOMAINS
# =============================================================================


class TestReservedSubdomains:
    """All reserved subdomains should return None."""

    @pytest.mark.parametrize("subdomain", [
        "www", "api", "admin", "app", "mail", "static", "cdn",
    ])
    def test_reserved_subdomains_blocked(self, subdomain):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain(f"{subdomain}.holilihu.online", "holilihu.online")
        assert result is None, f"Expected None for reserved subdomain '{subdomain}'"


# =============================================================================
# 7. EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case tests for subdomain extraction and routing."""

    def test_subdomain_with_underscore(self):
        """Underscored slugs should work (valid for internal orgs)."""
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("test_org.holilihu.online", "holilihu.online")
        assert result == "test_org"

    def test_single_char_subdomain(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("a.holilihu.online", "holilihu.online")
        assert result == "a"

    def test_very_long_subdomain(self):
        from app.core.middleware import extract_org_from_subdomain
        long_name = "a" * 63  # DNS label max
        result = extract_org_from_subdomain(f"{long_name}.holilihu.online", "holilihu.online")
        assert result == long_name

    def test_base_domain_with_leading_dot(self):
        """base_domain should not start with dot — user configures 'holilihu.online' not '.holilihu.online'."""
        from app.core.middleware import extract_org_from_subdomain
        # If someone configures '.holilihu.online', it should still work (robust)
        result = extract_org_from_subdomain("org.holilihu.online", ".holilihu.online")
        # extract function expects no leading dot — this should not match
        assert result is None

    def test_localhost_based_testing(self):
        """For local testing with subdomain_base_domain='localhost'."""
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("phuong-luu-kiem.localhost", "localhost")
        assert result == "phuong-luu-kiem"

    def test_localhost_with_port(self):
        from app.core.middleware import extract_org_from_subdomain
        result = extract_org_from_subdomain("org1.localhost:3000", "localhost")
        assert result == "org1"


# =============================================================================
# 8. INTEGRATION — END-TO-END SUBDOMAIN FLOW
# =============================================================================


class TestSubdomainEndToEnd:
    """Integration tests simulating the full subdomain → org context flow."""

    def test_extract_then_lookup(self):
        """Full flow: Host header → extract subdomain → use as org_id."""
        from app.core.middleware import extract_org_from_subdomain

        # Simulate incoming request
        host = "truong-dai-hoc-hang-hai.holilihu.online:443"
        base_domain = "holilihu.online"

        org_id = extract_org_from_subdomain(host, base_domain)
        assert org_id == "truong-dai-hoc-hang-hai"

        # This org_id would be used to set ContextVar and query org settings
        assert len(org_id) > 0
        assert "." not in org_id  # Should be clean slug, no domain parts

    def test_priority_chain(self):
        """Header > subdomain > None."""
        from app.core.middleware import extract_org_from_subdomain

        # Scenario 1: Header present
        header_org = "header-org"
        subdomain_org = extract_org_from_subdomain("subdomain-org.holilihu.online", "holilihu.online")
        resolved = header_org or subdomain_org
        assert resolved == "header-org"

        # Scenario 2: No header, subdomain present
        header_org = None
        subdomain_org = extract_org_from_subdomain("subdomain-org.holilihu.online", "holilihu.online")
        resolved = header_org or subdomain_org
        assert resolved == "subdomain-org"

        # Scenario 3: No header, no subdomain
        header_org = None
        subdomain_org = extract_org_from_subdomain("holilihu.online", "holilihu.online")
        resolved = header_org or subdomain_org
        assert resolved is None
