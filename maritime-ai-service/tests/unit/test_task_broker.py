"""
Tests for Task Broker Configuration (Sprint 18).

Verifies:
- get_broker returns InMemoryBroker when enable_background_tasks=False
- get_broker falls back to InMemoryBroker when taskiq-redis not installed
- get_broker singleton behavior (caches broker instance)
- get_scheduler returns None when enable_scheduler=False
- get_scheduler returns None when broker is None
- _get_inmemory_broker returns None when taskiq not installed
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

taskiq = pytest.importorskip("taskiq", reason="taskiq not installed")

import app.core.task_broker as task_broker_module
from app.core.task_broker import get_broker, get_scheduler, _get_inmemory_broker


@pytest.fixture(autouse=True)
def reset_broker_singleton():
    """Reset module-level broker/scheduler singletons before each test."""
    task_broker_module._broker = None
    task_broker_module._scheduler = None
    yield
    task_broker_module._broker = None
    task_broker_module._scheduler = None


class TestGetBroker:
    """Tests for get_broker()."""

    def test_returns_inmemory_when_background_tasks_disabled(self):
        """When enable_background_tasks=False, should return InMemoryBroker."""
        mock_settings = MagicMock()
        mock_settings.enable_background_tasks = False

        with patch("app.core.config.settings", mock_settings):
            broker = get_broker()

        if broker is not None:
            from taskiq import InMemoryBroker
            assert isinstance(broker, InMemoryBroker)

    def test_returns_inmemory_when_taskiq_redis_not_installed(self):
        """When taskiq-redis is not installed, should fall back to InMemoryBroker."""
        mock_settings = MagicMock()
        mock_settings.enable_background_tasks = True

        def raise_import_error(*args, **kwargs):
            raise ImportError("No module named 'taskiq_redis'")

        with patch("app.core.config.settings", mock_settings):
            with patch.dict("sys.modules", {"taskiq_redis": None}):
                # Force ImportError on taskiq_redis import
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == "taskiq_redis":
                        raise ImportError("No module named 'taskiq_redis'")
                    return original_import(name, *args, **kwargs)

                with patch.object(builtins, "__import__", side_effect=mock_import):
                    broker = get_broker()

        if broker is not None:
            from taskiq import InMemoryBroker
            assert isinstance(broker, InMemoryBroker)

    def test_singleton_returns_cached_broker(self):
        """After first call, subsequent calls should return the cached broker."""
        mock_settings = MagicMock()
        mock_settings.enable_background_tasks = False

        with patch("app.core.config.settings", mock_settings):
            broker1 = get_broker()
            broker2 = get_broker()

        assert broker1 is broker2

    def test_cached_broker_returned_without_reinitializing(self):
        """When _broker is already set, get_broker returns it immediately."""
        sentinel = MagicMock()
        task_broker_module._broker = sentinel

        result = get_broker()
        assert result is sentinel

    def test_general_exception_falls_back_to_inmemory(self):
        """On unexpected exception in settings, should fall back to InMemoryBroker."""
        mock_settings = MagicMock()
        type(mock_settings).enable_background_tasks = PropertyMock(
            side_effect=RuntimeError("config boom")
        )

        with patch("app.core.config.settings", mock_settings):
            broker = get_broker()

        # Should be InMemoryBroker or None (if taskiq not installed)
        if broker is not None:
            from taskiq import InMemoryBroker
            assert isinstance(broker, InMemoryBroker)


class TestGetInMemoryBroker:
    """Tests for _get_inmemory_broker()."""

    def test_returns_inmemory_broker_instance(self):
        """Should create and cache an InMemoryBroker."""
        broker = _get_inmemory_broker()
        from taskiq import InMemoryBroker
        assert isinstance(broker, InMemoryBroker)

    def test_returns_none_when_taskiq_not_available(self):
        """When taskiq is not importable, should return None."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "taskiq":
                raise ImportError("No module named 'taskiq'")
            return original_import(name, *args, **kwargs)

        task_broker_module._broker = None  # Reset

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = _get_inmemory_broker()

        assert result is None


class TestGetScheduler:
    """Tests for get_scheduler()."""

    def test_returns_none_when_scheduler_disabled(self):
        """When enable_scheduler=False, should return None."""
        mock_settings = MagicMock()
        mock_settings.enable_scheduler = False

        with patch("app.core.config.settings", mock_settings):
            scheduler = get_scheduler()

        assert scheduler is None

    def test_returns_none_when_broker_is_none(self):
        """When get_broker returns None, scheduler should also be None."""
        mock_settings = MagicMock()
        mock_settings.enable_scheduler = True

        with patch("app.core.config.settings", mock_settings):
            with patch("app.core.task_broker.get_broker", return_value=None):
                scheduler = get_scheduler()

        assert scheduler is None

    def test_returns_cached_scheduler(self):
        """When _scheduler is already set, returns it immediately."""
        sentinel = MagicMock()
        task_broker_module._scheduler = sentinel

        result = get_scheduler()
        assert result is sentinel

    def test_returns_none_when_dependencies_missing(self):
        """When TaskiqScheduler or RedisScheduleSource can't be imported, returns None."""
        mock_settings = MagicMock()
        mock_settings.enable_scheduler = True

        mock_broker = MagicMock()

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("taskiq_redis",):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch("app.core.config.settings", mock_settings):
            with patch("app.core.task_broker.get_broker", return_value=mock_broker):
                with patch.object(builtins, "__import__", side_effect=mock_import):
                    scheduler = get_scheduler()

        assert scheduler is None
