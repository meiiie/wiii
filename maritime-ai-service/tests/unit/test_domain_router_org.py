"""
Tests for DomainRouter with allowed_domains filtering.

Sprint 24: Multi-Organization Architecture.

Verifies:
- allowed_domains filtering on all resolution paths
- Explicit domain outside allowed_domains → rejected → fallback
- No allowed_domains (None) → no filtering
- Empty allowed_domains → only default
"""

import pytest
from unittest.mock import MagicMock, patch

from app.domains.router import DomainRouter


@pytest.fixture
def router():
    return DomainRouter()


@pytest.fixture
def mock_registry():
    """Mock registry with 'maritime' and 'traffic_law' registered."""
    registry = MagicMock()
    registry.is_registered.side_effect = lambda d: d in ("maritime", "traffic_law")
    registry.get_default_id.return_value = "maritime"
    registry.get_all_keywords.return_value = {
        "maritime": ["colregs", "solas", "tàu"],
        "traffic_law": ["giao thông", "biển báo"],
    }
    return registry


# =============================================================================
# No filtering (allowed_domains=None)
# =============================================================================


class TestNoFiltering:
    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_explicit_domain_allowed(self, mock_get_reg, router, mock_registry):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve("test", explicit_domain_id="traffic_law")
        assert result == "traffic_law"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_keyword_match_allowed(self, mock_get_reg, router, mock_registry):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve("biển báo giao thông")
        assert result == "traffic_law"


# =============================================================================
# With allowed_domains filtering
# =============================================================================


class TestWithFiltering:
    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_explicit_outside_allowed_falls_through(
        self, mock_get_reg, router, mock_registry
    ):
        """If explicit domain is not in allowed_domains, it's rejected."""
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "test",
            explicit_domain_id="traffic_law",
            allowed_domains=["maritime"],
        )
        # traffic_law is rejected → falls to keyword → default → maritime
        assert result == "maritime"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_explicit_inside_allowed(
        self, mock_get_reg, router, mock_registry
    ):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "test",
            explicit_domain_id="maritime",
            allowed_domains=["maritime"],
        )
        assert result == "maritime"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_keyword_match_filtered(
        self, mock_get_reg, router, mock_registry
    ):
        """Keyword matches for domains outside allowed_domains are skipped."""
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "biển báo giao thông",  # matches traffic_law
            allowed_domains=["maritime"],  # but traffic_law not allowed
        )
        # keyword match is traffic_law but not allowed → default maritime
        assert result == "maritime"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_default_outside_allowed(
        self, mock_get_reg, router, mock_registry
    ):
        """If default domain is not in allowed_domains, use first allowed."""
        mock_get_reg.return_value = mock_registry
        # Default is maritime but allowed only traffic_law
        result = await router.resolve(
            "some query no keywords",
            allowed_domains=["traffic_law"],
        )
        # maritime is default but not allowed → org fallback → traffic_law
        assert result == "traffic_law"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_both_allowed(
        self, mock_get_reg, router, mock_registry
    ):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "test colregs",
            allowed_domains=["maritime", "traffic_law"],
        )
        assert result == "maritime"  # keyword match

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_session_domain_allowed(
        self, mock_get_reg, router, mock_registry
    ):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "test",
            session_domain="traffic_law",
            allowed_domains=["maritime", "traffic_law"],
        )
        assert result == "traffic_law"

    @pytest.mark.asyncio
    @patch("app.domains.router.get_domain_registry")
    async def test_session_domain_not_allowed(
        self, mock_get_reg, router, mock_registry
    ):
        mock_get_reg.return_value = mock_registry
        result = await router.resolve(
            "test",
            session_domain="traffic_law",
            allowed_domains=["maritime"],
        )
        # session domain not allowed → falls through to default
        assert result == "maritime"


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    @patch("app.domains.router.get_domain_registry")
    async def test_empty_allowed_domains(
        self, mock_get_reg, mock_settings, router, mock_registry
    ):
        """Empty list means nothing is allowed → falls to absolute fallback."""
        mock_get_reg.return_value = mock_registry
        mock_settings.default_domain = "maritime"
        result = await router.resolve("test", allowed_domains=[])
        assert result == "maritime"  # absolute fallback
