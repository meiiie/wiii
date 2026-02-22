"""Tests for app.core.database — Singleton engine pattern."""

import pytest
from unittest.mock import patch, MagicMock

from app.core.database import (
    get_shared_engine,
    get_shared_session_factory,
    test_connection as db_test_connection,
    close_shared_engine,
    _shared_engine,
)


@pytest.fixture(autouse=True)
def reset_database_singletons():
    """Reset module-level singletons between tests."""
    import app.core.database as db_mod
    db_mod._shared_engine = None
    db_mod._shared_session_factory = None
    db_mod._engine_initialized = False
    yield
    db_mod._shared_engine = None
    db_mod._shared_session_factory = None
    db_mod._engine_initialized = False


class TestGetSharedEngine:
    """Test singleton engine creation."""

    @patch("app.core.database.event")
    @patch("app.core.database.create_engine")
    def test_creates_engine_once(self, mock_create_engine, mock_event):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        engine1 = get_shared_engine()
        engine2 = get_shared_engine()

        assert engine1 is engine2
        mock_create_engine.assert_called_once()

    @patch("app.core.database.event")
    @patch("app.core.database.create_engine")
    def test_engine_pool_settings(self, mock_create_engine, mock_event):
        mock_create_engine.return_value = MagicMock()
        get_shared_engine()

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["pool_pre_ping"] is True
        # Sprint 170b: pool_size reads from settings (default min=2, max=10)
        from app.core.config import settings
        assert call_kwargs["pool_size"] == settings.async_pool_min_size
        assert call_kwargs["max_overflow"] == settings.async_pool_max_size - settings.async_pool_min_size
        assert call_kwargs["pool_timeout"] == 30
        assert call_kwargs["pool_recycle"] == 1800
        assert call_kwargs["echo"] is False

    @patch("app.core.database.create_engine", side_effect=Exception("DB unreachable"))
    def test_raises_on_creation_failure(self, mock_create_engine):
        with pytest.raises(Exception, match="DB unreachable"):
            get_shared_engine()


class TestGetSharedSessionFactory:
    """Test session factory creation."""

    @patch("app.core.database.create_engine")
    def test_creates_session_factory(self, mock_create_engine):
        mock_create_engine.return_value = MagicMock()
        factory = get_shared_session_factory()
        assert factory is not None

    @patch("app.core.database.create_engine")
    def test_session_factory_is_singleton(self, mock_create_engine):
        mock_create_engine.return_value = MagicMock()
        f1 = get_shared_session_factory()
        f2 = get_shared_session_factory()
        assert f1 is f2


class TestCloseSharedEngine:
    """Test engine cleanup."""

    @patch("app.core.database.event")
    @patch("app.core.database.create_engine")
    def test_dispose_and_reset(self, mock_create_engine, mock_event):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        get_shared_engine()
        close_shared_engine()

        mock_engine.dispose.assert_called_once()

        import app.core.database as db_mod
        assert db_mod._shared_engine is None
        assert db_mod._shared_session_factory is None
        assert db_mod._engine_initialized is False

    def test_close_noop_when_not_initialized(self):
        # Should not raise
        close_shared_engine()


class TestTestConnection:
    """Test the test_connection helper."""

    @patch("app.core.database.get_shared_session_factory")
    def test_success(self, mock_factory):
        mock_session = MagicMock()
        mock_factory.return_value = MagicMock(return_value=mock_session)
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        result = db_test_connection()
        assert result is True

    @patch("app.core.database.get_shared_session_factory", side_effect=Exception("fail"))
    def test_failure_returns_false(self, mock_factory):
        result = db_test_connection()
        assert result is False
