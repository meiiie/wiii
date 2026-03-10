"""
Sprint 220c: "Nhúng Wiii Pro" — LMS Identity Resolution Tests

Tests for:
  1. find_external_identity: reverse-lookup (Wiii UUID → external identity)
  2. resolve_lms_identity: helper combining org settings + identity lookup
  3. context_loader: connector_id=None returns None (no hardcoded default)
  4. context_loader: compound cache key for multi-connector
  5. OrgAIConfig external_connector_id field
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# 1. find_external_identity Tests
# =============================================================================


def _make_mock_pool(mock_conn):
    """Create a properly async mock pool for asyncpg."""
    mock_pool = MagicMock()

    # asyncpg pool.acquire() returns an async context manager
    class _AcquireCM:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *args):
            pass

    mock_pool.acquire.return_value = _AcquireCM()
    return mock_pool


class TestFindExternalIdentity:
    """Test reverse-lookup: Wiii UUID → external identity."""

    @pytest.mark.asyncio
    async def test_match_found(self):
        """Returns identity dict when user has a linked LMS identity."""
        mock_row = {
            "provider_sub": "lms-student-42",
            "provider_issuer": "maritime-lms",
            "email": "student@lms.edu",
            "display_name": "Nguyen Van A",
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _make_mock_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        with patch("app.auth.user_service._get_pool", side_effect=fake_get_pool):
            from app.auth.user_service import find_external_identity

            result = await find_external_identity("wiii-uuid-123", "lms")

        assert result is not None
        assert result["provider_sub"] == "lms-student-42"
        assert result["provider_issuer"] == "maritime-lms"

    @pytest.mark.asyncio
    async def test_no_match(self):
        """Returns None when user has no linked LMS identity."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _make_mock_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        with patch("app.auth.user_service._get_pool", side_effect=fake_get_pool):
            from app.auth.user_service import find_external_identity

            result = await find_external_identity("wiii-uuid-999", "lms")

        assert result is None

    @pytest.mark.asyncio
    async def test_with_issuer_filter(self):
        """Filters by provider_issuer when specified."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "provider_sub": "lms-student-42",
            "provider_issuer": "maritime-lms",
            "email": None,
            "display_name": None,
        })
        mock_pool = _make_mock_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        with patch("app.auth.user_service._get_pool", side_effect=fake_get_pool):
            from app.auth.user_service import find_external_identity

            result = await find_external_identity(
                "wiii-uuid-123", "lms", provider_issuer="maritime-lms",
            )

        assert result is not None
        # Verify the 3-param query was used (provider_issuer provided)
        call_args = mock_conn.fetchrow.call_args
        assert "provider_issuer = $3" in call_args[0][0]


# =============================================================================
# 2. resolve_lms_identity Tests
# =============================================================================


class TestResolveLmsIdentity:
    """Test the shared identity resolver helper."""

    @pytest.mark.asyncio
    async def test_with_org_connector(self):
        """Uses org-specific connector_id as issuer filter."""
        mock_org_settings = MagicMock()
        mock_org_settings.ai_config.external_connector_id = "maritime-lms"

        mock_identity = {
            "provider_sub": "lms-student-42",
            "provider_issuer": "maritime-lms",
        }

        # Patch at SOURCE modules (lazy imports inside function body)
        with (
            patch(
                "app.core.org_settings.get_effective_settings",
                return_value=mock_org_settings,
            ),
            patch(
                "app.auth.user_service.find_external_identity",
                new_callable=AsyncMock,
                return_value=mock_identity,
            ) as mock_find,
        ):
            from app.auth.external_identity import resolve_lms_identity

            lms_id, conn_id = await resolve_lms_identity("wiii-uuid-123", "lms-hang-hai")

        assert lms_id == "lms-student-42"
        assert conn_id == "maritime-lms"
        # Verify issuer filter was passed
        mock_find.assert_called_once_with(
            user_id="wiii-uuid-123",
            provider="lms",
            provider_issuer="maritime-lms",
        )

    @pytest.mark.asyncio
    async def test_without_org(self):
        """Works without org context (no issuer filter)."""
        mock_identity = {
            "provider_sub": "lms-student-42",
            "provider_issuer": "some-lms",
        }

        with patch(
            "app.auth.user_service.find_external_identity",
            new_callable=AsyncMock,
            return_value=mock_identity,
        ) as mock_find:
            from app.auth.external_identity import resolve_lms_identity

            lms_id, conn_id = await resolve_lms_identity("wiii-uuid-123")

        assert lms_id == "lms-student-42"
        assert conn_id == "some-lms"
        # No issuer filter when no org
        mock_find.assert_called_once_with(
            user_id="wiii-uuid-123",
            provider="lms",
            provider_issuer=None,
        )

    @pytest.mark.asyncio
    async def test_no_linked_identity(self):
        """Returns (None, None) when user has no LMS identity."""
        with patch(
            "app.auth.user_service.find_external_identity",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.auth.external_identity import resolve_lms_identity

            lms_id, conn_id = await resolve_lms_identity("wiii-uuid-999")

        assert lms_id is None
        assert conn_id is None


# =============================================================================
# 3. context_loader Tests (Sprint 220c changes)
# =============================================================================


class TestContextLoaderConnectorId:
    """Test context_loader with resolved identity (not hardcoded)."""

    def test_no_connector_returns_none(self):
        """connector_id=None returns None (no hardcoded default)."""
        from app.integrations.lms.context_loader import LMSContextLoader

        loader = LMSContextLoader()
        loader.clear_cache()
        result = loader.load_student_context("student-1", connector_id=None)
        assert result is None

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_compound_cache_key(self, mock_registry):
        """Different connectors produce separate cache entries."""
        from app.integrations.lms.context_loader import (
            LMSContextLoader,
            _context_cache,
        )

        # Connector returns some data
        connector = MagicMock()
        connector.get_student_profile.return_value = MagicMock(
            name="Test", email="t@t.com", program=None, class_name=None,
        )
        connector.get_student_enrollments.return_value = [{"course_id": "C1", "course_name": "Course 1"}]
        connector.get_student_grades.return_value = []
        connector.get_upcoming_assignments.return_value = []
        connector.get_student_quiz_history.return_value = []
        mock_registry.return_value.get.return_value = connector

        loader = LMSContextLoader()
        loader.clear_cache()

        # Load with two different connectors
        loader.load_student_context("student-1", connector_id="lms-a")
        loader.load_student_context("student-1", connector_id="lms-b")

        # Both should be cached separately
        assert "student-1:lms-a" in _context_cache
        assert "student-1:lms-b" in _context_cache

    @patch("app.integrations.lms.registry.get_lms_connector_registry")
    def test_invalidate_by_user_clears_all_connectors(self, mock_registry):
        """invalidate_cache(user_id) without connector clears all entries."""
        from app.integrations.lms.context_loader import (
            LMSContextLoader,
            _context_cache,
        )

        connector = MagicMock()
        connector.get_student_profile.return_value = MagicMock(
            name="Test", email="t@t.com", program=None, class_name=None,
        )
        connector.get_student_enrollments.return_value = [{"course_id": "C1", "course_name": "Course 1"}]
        connector.get_student_grades.return_value = []
        connector.get_upcoming_assignments.return_value = []
        connector.get_student_quiz_history.return_value = []
        mock_registry.return_value.get.return_value = connector

        loader = LMSContextLoader()
        loader.clear_cache()

        loader.load_student_context("student-1", connector_id="lms-a")
        loader.load_student_context("student-1", connector_id="lms-b")
        assert len([k for k in _context_cache if k.startswith("student-1:")]) == 2

        # Invalidate all for this user
        loader.invalidate_cache("student-1")
        assert len([k for k in _context_cache if k.startswith("student-1:")]) == 0


# =============================================================================
# 4. OrgAIConfig external_connector_id
# =============================================================================


class TestOrgAIConfigConnector:
    """Test external_connector_id field on OrgAIConfig."""

    def test_default_none(self):
        """external_connector_id defaults to None."""
        from app.models.organization import OrgAIConfig

        config = OrgAIConfig()
        assert config.external_connector_id is None

    def test_set_connector(self):
        """Can set external_connector_id."""
        from app.models.organization import OrgAIConfig

        config = OrgAIConfig(external_connector_id="maritime-lms")
        assert config.external_connector_id == "maritime-lms"

    def test_serialization(self):
        """external_connector_id survives dict round-trip (JSONB storage)."""
        from app.models.organization import OrgAIConfig

        config = OrgAIConfig(external_connector_id="my-lms")
        data = config.model_dump()
        restored = OrgAIConfig(**data)
        assert restored.external_connector_id == "my-lms"
