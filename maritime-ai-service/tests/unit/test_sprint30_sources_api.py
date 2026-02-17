"""
Tests for Sprint 30: Sources API endpoint coverage.

Covers:
- list_sources: limit clamping, auth requirement
- Source schema validation
- Auth requirement on both endpoints (Sprint 28 structural + functional)

Note: _get_asyncpg_url tests moved to test_sprint32_config_asyncpg_url.py
(Sprint 32: centralized as settings.asyncpg_url property)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.api.v1.sources import SourceDetailResponse


def _make_request():
    """Create a real starlette Request for rate-limited endpoints."""
    from starlette.requests import Request
    scope = {
        "type": "http", "method": "GET", "path": "/api/v1/sources",
        "headers": [], "query_string": b"", "root_path": "",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


# =============================================================================
# SourceDetailResponse schema
# =============================================================================


class TestSourceDetailResponse:
    """Test the Pydantic response model."""

    def test_required_fields(self):
        resp = SourceDetailResponse(
            node_id="chunk_001",
            content="Some content",
        )
        assert resp.node_id == "chunk_001"
        assert resp.content == "Some content"
        assert resp.content_type == "text"

    def test_optional_fields_default_none(self):
        resp = SourceDetailResponse(node_id="x", content="c")
        assert resp.document_id is None
        assert resp.page_number is None
        assert resp.image_url is None
        assert resp.bounding_boxes is None
        assert resp.chunk_index is None
        assert resp.confidence_score is None
        assert resp.metadata is None

    def test_all_fields(self):
        resp = SourceDetailResponse(
            node_id="n1",
            content="text",
            document_id="doc-1",
            page_number=5,
            image_url="http://img.png",
            bounding_boxes=[{"x0": 10, "y0": 20}],
            content_type="heading",
            chunk_index=2,
            confidence_score=0.95,
            metadata={"key": "val"},
        )
        assert resp.page_number == 5
        assert resp.confidence_score == 0.95
        assert len(resp.bounding_boxes) == 1


# =============================================================================
# list_sources — limit clamping
# =============================================================================


class TestListSourcesLimitClamping:
    """The limit parameter should be clamped to 1-100."""

    @staticmethod
    def _make_pool_mock():
        """Create a mock asyncpg pool with proper async context manager."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"total": 0}
        mock_conn.fetch.return_value = []

        # pool.acquire() returns an async context manager (not a coroutine)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm
        return mock_pool

    @pytest.mark.asyncio
    async def test_limit_clamped_to_max_100(self):
        """Requesting limit=999 should be clamped to 100."""
        from app.api.v1.sources import list_sources

        mock_pool = self._make_pool_mock()
        mock_auth = MagicMock()
        mock_auth.user_id = "user-1"

        with patch("app.api.v1.sources.get_pool", AsyncMock(return_value=mock_pool)):
            result = await list_sources(
                request=_make_request(), auth=mock_auth, limit=999, offset=0
            )

        assert result["pagination"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_limit_clamped_to_min_1(self):
        from app.api.v1.sources import list_sources

        mock_pool = self._make_pool_mock()
        mock_auth = MagicMock()

        with patch("app.api.v1.sources.get_pool", AsyncMock(return_value=mock_pool)):
            result = await list_sources(request=_make_request(), auth=mock_auth, limit=-5, offset=0)

        assert result["pagination"]["limit"] == 1


# =============================================================================
# Auth requirements (structural)
# =============================================================================


class TestSourcesAuth:
    """Both endpoints require auth (Sprint 28)."""

    def test_get_source_details_has_auth_param(self):
        import inspect
        from app.api.v1.sources import get_source_details
        sig = inspect.signature(get_source_details)
        assert "auth" in sig.parameters

    def test_list_sources_has_auth_param(self):
        import inspect
        from app.api.v1.sources import list_sources
        sig = inspect.signature(list_sources)
        assert "auth" in sig.parameters

    def test_error_messages_sanitized(self):
        """Error responses should not contain str(e)."""
        from pathlib import Path
        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "sources.py"
        source = source_path.read_text(encoding="utf-8")
        for line in source.split("\n"):
            if "HTTPException" in line and "detail=" in line:
                assert "{e}" not in line, f"Error leak: {line.strip()}"
                assert "{str(e)}" not in line, f"Error leak: {line.strip()}"
