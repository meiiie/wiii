"""
Tests for Sprint 51: InsightRepositoryMixin coverage.

Tests insight repository operations including:
- get_user_insights (success, empty, error)
- delete_user_insights (success, empty, error)
- get_insights_by_category (success, empty, error)
"""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.models.semantic_memory import MemoryType
from app.repositories.insight_repository import InsightRepositoryMixin


# ============================================================================
# Helpers
# ============================================================================


class MockRepo(InsightRepositoryMixin):
    """Concrete class combining mixin with required methods."""

    TABLE_NAME = "semantic_memories"

    def __init__(self):
        self._initialized = True
        self._session_factory = None

    def _ensure_initialized(self):
        pass


def _make_repo():
    """Create mock repo with mocked session."""
    repo = MockRepo()
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: mock_session
    mock_session.__exit__ = MagicMock(return_value=False)
    repo._session_factory = lambda: mock_session
    return repo, mock_session


def _make_insight_row(content="User prefers visual learning", importance=0.8):
    """Create a mock row mimicking a DB row."""
    row = MagicMock()
    row.id = uuid4()
    row.content = content
    row.memory_type = "insight" if hasattr(MemoryType, "INSIGHT") else "user_fact"
    row.importance = importance
    row.metadata = {"insight_category": "learning_style"}
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    row.last_accessed = None
    row.similarity = 1.0
    return row


# ============================================================================
# get_user_insights
# ============================================================================


class TestGetUserInsights:
    """Test insight retrieval."""

    def test_success(self):
        repo, session = _make_repo()
        rows = [_make_insight_row("Insight 1"), _make_insight_row("Insight 2")]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        session.execute.return_value = mock_result

        results = repo.get_user_insights("user1")
        assert len(results) == 2
        assert results[0].content == "Insight 1"

    def test_empty(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        results = repo.get_user_insights("user1")
        assert results == []

    def test_error(self):
        repo, session = _make_repo()
        session.execute.side_effect = Exception("DB error")

        results = repo.get_user_insights("user1")
        assert results == []

    def test_custom_limit(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        repo.get_user_insights("user1", limit=5)
        # Verify limit is passed
        call_args = session.execute.call_args
        assert call_args[0][1]["limit"] == 5


# ============================================================================
# delete_user_insights
# ============================================================================


class TestDeleteUserInsights:
    """Test insight deletion."""

    def test_success(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [MagicMock(), MagicMock(), MagicMock()]
        session.execute.return_value = mock_result

        count = repo.delete_user_insights("user1")
        assert count == 3
        session.commit.assert_called_once()

    def test_empty(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        count = repo.delete_user_insights("user1")
        assert count == 0

    def test_error(self):
        repo, session = _make_repo()
        session.execute.side_effect = Exception("DB error")

        count = repo.delete_user_insights("user1")
        assert count == 0


# ============================================================================
# get_insights_by_category
# ============================================================================


class TestGetInsightsByCategory:
    """Test category-filtered insight retrieval."""

    def test_success(self):
        repo, session = _make_repo()
        row = _make_insight_row("Weak at navigation")
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row]
        session.execute.return_value = mock_result

        results = repo.get_insights_by_category("user1", "knowledge_gap")
        assert len(results) == 1

    def test_empty(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        results = repo.get_insights_by_category("user1", "learning_style")
        assert results == []

    def test_error(self):
        repo, session = _make_repo()
        session.execute.side_effect = Exception("DB error")

        results = repo.get_insights_by_category("user1", "any")
        assert results == []

    def test_custom_limit(self):
        repo, session = _make_repo()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        repo.get_insights_by_category("user1", "style", limit=3)
        call_args = session.execute.call_args
        assert call_args[0][1]["limit"] == 3
