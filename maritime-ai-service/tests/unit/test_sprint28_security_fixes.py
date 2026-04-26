"""
Tests for Sprint 28: Security hardening fixes.

Covers:
- insights.py: auth parameter required (no bypass)
- sources.py: auth parameter added to both endpoints
- security.py: JWT role from token, not X-Role header
- middleware.py: OrgContext logs errors instead of silent pass
- Error message sanitization (no str(e) in responses)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone


# =============================================================================
# Insights API — Auth Required
# =============================================================================

class TestInsightsAuthRequired:
    """Sprint 28: insights endpoint must require authentication."""

    def test_auth_parameter_has_no_default(self):
        """RequireAuth should NOT have = None default."""
        import inspect
        from app.api.v1.insights import get_user_insights

        sig = inspect.signature(get_user_insights)
        auth_param = sig.parameters.get("auth")
        assert auth_param is not None
        # Should not have a default of None
        assert auth_param.default is inspect.Parameter.empty or auth_param.default is not None

    def test_ownership_check_always_runs(self):
        """The ownership check should not be gated by 'if auth'."""
        import ast
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "insights.py"
        source = source_path.read_text(encoding="utf-8")

        # Should NOT contain the old pattern "if auth and auth.user_id"
        assert "if auth and auth.user_id" not in source
        # Should contain defensive "if not auth" check
        assert "if not auth" in source


# =============================================================================
# Sources API — Auth Added
# =============================================================================

class TestSourcesAuthAdded:
    """Sprint 28: sources endpoints must require authentication."""

    def test_get_source_details_requires_auth(self):
        """get_source_details should have auth parameter."""
        import inspect
        from app.api.v1.sources import get_source_details

        sig = inspect.signature(get_source_details)
        assert "auth" in sig.parameters

    def test_list_sources_requires_auth(self):
        """list_sources should have auth parameter."""
        import inspect
        from app.api.v1.sources import list_sources

        sig = inspect.signature(list_sources)
        assert "auth" in sig.parameters

    def test_sources_imports_require_auth(self):
        """sources.py should import RequireAuth."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "sources.py"
        source = source_path.read_text(encoding="utf-8")
        assert "from app.api.deps import RequireAuth" in source

    def test_error_messages_sanitized(self):
        """Error responses should NOT include str(e)."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "sources.py"
        source = source_path.read_text(encoding="utf-8")

        # Should not contain f-string with {e} or {str(e)} in detail=
        lines = source.split("\n")
        for line in lines:
            if "detail=" in line and ("{e}" in line or "{str(e)}" in line):
                pytest.fail(f"Error message leak found: {line.strip()}")


# =============================================================================
# JWT Role Override — Security Fix
# =============================================================================

class TestJWTRoleOverrideFix:
    """Sprint 28: JWT auth should use token role, not X-Role header."""

    def test_token_payload_has_role_field(self):
        """TokenPayload should have optional role field."""
        from app.core.security import TokenPayload

        # Create payload with role
        payload = TokenPayload(
            sub="user-1",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
            role="admin",
        )
        assert payload.role == "admin"

    def test_token_payload_role_defaults_to_none(self):
        """TokenPayload.role should default to None."""
        from app.core.security import TokenPayload

        payload = TokenPayload(
            sub="user-1",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )
        assert payload.role is None

    @pytest.mark.asyncio
    async def test_jwt_auth_ignores_x_role_header(self):
        """JWT authentication should NOT use X-Role header."""
        from app.core.security import require_auth, TokenPayload
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="fake-token",
        )

        token_payload = TokenPayload(
            sub="user-1",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
            role="student",
        )

        with patch("app.core.security.verify_jwt_token", return_value=token_payload):
            result = await require_auth(
                api_key=None,
                credentials=mock_credentials,
                x_user_id="user-1",
                x_role="admin",  # Attacker tries to override role
                x_session_id=None,
                x_org_id=None,
            )

        # Should use token role (student), NOT X-Role header (admin)
        assert result.role == "student"
        assert result.auth_method == "jwt"

    @pytest.mark.asyncio
    async def test_api_key_auth_still_uses_x_role(self):
        """API key auth should still use X-Role header (trusted backend)."""
        from app.core.security import require_auth

        with patch("app.core.security.verify_api_key", return_value=True):
            result = await require_auth(
                api_key="valid-key",
                credentials=None,
                x_user_id="user-1",
                x_role="teacher",
                x_session_id=None,
                x_org_id=None,
            )

        # API key auth uses X-Role (trusted LMS backend)
        assert result.role == "teacher"
        assert result.auth_method == "api_key"


# =============================================================================
# OrgContext Middleware — Logging Fix
# =============================================================================

class TestOrgContextMiddlewareLogging:
    """Sprint 28: Middleware should log errors, not silently pass."""

    def test_middleware_does_not_silently_pass(self):
        """middleware.py should NOT have bare 'except Exception: pass'."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "core" / "middleware.py"
        source = source_path.read_text(encoding="utf-8")

        # Should NOT contain "except Exception:\n                pass"
        assert "except Exception:\n                pass" not in source

    def test_middleware_has_logger(self):
        """middleware.py should have a logger for warning messages."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "core" / "middleware.py"
        source = source_path.read_text(encoding="utf-8")

        assert "logger = logging.getLogger" in source
        assert "logger.warning" in source


# =============================================================================
# Error Message Sanitization
# =============================================================================

class TestErrorMessageSanitization:
    """Sprint 28: API error responses must not leak internal details."""

    def test_admin_no_error_leak(self):
        """admin.py should not expose str(e) in HTTP responses."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "admin.py"
        source = source_path.read_text(encoding="utf-8")

        lines = source.split("\n")
        for line in lines:
            if "HTTPException" in line and "detail=" in line:
                if "{e}" in line or "{str(e)}" in line:
                    pytest.fail(f"Error message leak in admin.py: {line.strip()}")

    def test_chat_no_error_leak_in_history(self):
        """chat.py should not expose str(e) in chat history error responses."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "chat.py"
        source = source_path.read_text(encoding="utf-8")

        # Check for the specific patterns we fixed
        assert "Failed to retrieve chat history: {str(e)}" not in source
        assert "Failed to delete chat history: {str(e)}" not in source


# =============================================================================
# Emoji in Logger — Windows Crash Fix
# =============================================================================

class TestEmojiInLoggerFixed:
    """Sprint 28: No emoji in logger calls (Windows cp1252 crash)."""

    def test_main_no_emoji_in_logger(self):
        """main.py should not have emoji in logger calls."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "main.py"
        source = source_path.read_text(encoding="utf-8")

        # Should not contain waving hand emoji in logger
        assert "\U0001f44b" not in source.split("logger.info")[1] if "logger.info" in source else True
        # Simpler check: no waving hand emoji anywhere near logger
        for line in source.split("\n"):
            if "logger." in line and "\U0001f44b" in line:
                pytest.fail(f"Emoji in logger call: {line.strip()}")

    def test_llm_pool_no_emoji_in_logger(self):
        """llm_pool.py should not have emoji in logger calls."""
        from pathlib import Path

        source_path = Path(__file__).parent.parent.parent / "app" / "engine" / "llm_pool.py"
        source = source_path.read_text(encoding="utf-8")

        for line in source.split("\n"):
            if "logger." in line and "\u2705" in line:
                pytest.fail(f"Emoji in logger call: {line.strip()}")
