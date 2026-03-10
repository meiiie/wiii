"""
Tests for LangGraph Checkpointer Singleton.

Verifies:
- Singleton initialization and reuse
- Graceful degradation when PostgreSQL unavailable
- Close and reset behavior
- ImportError handling when package missing
- New context manager API (>=3.0.4) and old .setup() API
"""

import sys
import types

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Break circular import (graph → services → chat_service → graph)
_cs_key = "app.services.chat_service"
if _cs_key not in sys.modules:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset():
    """Reset checkpointer singleton state between tests."""
    from app.engine.multi_agent import checkpointer as mod
    mod._checkpointer = None
    mod._context_manager = None
    mod._initialized = False


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------

class TestCheckpointerInit:
    """Test checkpointer singleton initialization."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        _reset()
        yield
        _reset()

    @pytest.mark.asyncio
    async def test_get_checkpointer_old_api_setup(self):
        """Old API: from_conn_string returns instance, calls .setup()."""
        import app.engine.multi_agent.checkpointer as mod

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        # Old API: no __aenter__ attribute
        del mock_saver.__aenter__

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_saver

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            _reset()
            result = await mod.get_checkpointer()

            assert result is mock_saver
            mock_saver.setup.assert_awaited_once()
            assert mod._initialized is True
            assert mod._context_manager is None

    @pytest.mark.asyncio
    async def test_get_checkpointer_new_api_context_manager(self):
        """New API (>=3.0.4): from_conn_string returns async context manager."""
        import app.engine.multi_agent.checkpointer as mod

        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_cm

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            _reset()
            result = await mod.get_checkpointer()

            assert result is mock_saver
            mock_cm.__aenter__.assert_awaited_once()
            mock_saver.setup.assert_awaited_once()
            assert mod._initialized is True
            assert mod._context_manager is mock_cm

    @pytest.mark.asyncio
    async def test_get_checkpointer_import_error(self):
        """Checkpointer returns None when package not installed."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": None,
            "langgraph.checkpoint.postgres": None,
        }):
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if "langgraph.checkpoint.postgres" in name:
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                _reset()
                result = await mod.get_checkpointer()
                assert result is None
                assert mod._initialized is True

    @pytest.mark.asyncio
    async def test_get_checkpointer_connection_error(self):
        """Checkpointer returns None on connection failure."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            _reset()
            result = await mod.get_checkpointer()
            assert result is None
            assert mod._initialized is True
            assert mod._context_manager is None

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Second call returns cached instance without re-initializing."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        mock_saver = AsyncMock()
        mod._checkpointer = mock_saver
        mod._initialized = True

        result = await mod.get_checkpointer()
        assert result is mock_saver

    @pytest.mark.asyncio
    async def test_singleton_returns_none_after_failed_init(self):
        """After failed init, returns None without retrying."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        mod._checkpointer = None
        mod._initialized = True

        result = await mod.get_checkpointer()
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Close
# ---------------------------------------------------------------------------

class TestCheckpointerClose:
    """Test checkpointer close and reset."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        _reset()
        yield
        _reset()

    @pytest.mark.asyncio
    async def test_close_with_context_manager(self):
        """New API: close calls __aexit__ on context manager."""
        import app.engine.multi_agent.checkpointer as mod

        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mod._checkpointer = AsyncMock()
        mod._context_manager = mock_cm
        mod._initialized = True

        await mod.close_checkpointer()

        mock_cm.__aexit__.assert_awaited_once_with(None, None, None)
        assert mod._checkpointer is None
        assert mod._context_manager is None
        assert mod._initialized is False

    @pytest.mark.asyncio
    async def test_close_with_old_api_connection(self):
        """Old API: close calls conn.close() on active checkpointer."""
        import app.engine.multi_agent.checkpointer as mod

        mock_conn = AsyncMock()
        mock_saver = MagicMock()
        mock_saver.conn = mock_conn

        mod._checkpointer = mock_saver
        mod._context_manager = None
        mod._initialized = True

        await mod.close_checkpointer()

        mock_conn.close.assert_awaited_once()
        assert mod._checkpointer is None
        assert mod._initialized is False

    @pytest.mark.asyncio
    async def test_close_without_connection(self):
        """Close handles None checkpointer gracefully."""
        import app.engine.multi_agent.checkpointer as mod

        mod._checkpointer = None
        mod._initialized = True

        await mod.close_checkpointer()

        assert mod._checkpointer is None
        assert mod._initialized is False

    @pytest.mark.asyncio
    async def test_close_handles_error(self):
        """Close handles error during close gracefully."""
        import app.engine.multi_agent.checkpointer as mod

        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(side_effect=Exception("Already closed"))

        mod._checkpointer = AsyncMock()
        mod._context_manager = mock_cm
        mod._initialized = True

        # Should not raise
        await mod.close_checkpointer()
        assert mod._checkpointer is None

    def test_reset_checkpointer(self):
        """reset_checkpointer clears all singleton state."""
        import app.engine.multi_agent.checkpointer as mod

        mod._checkpointer = "something"
        mod._context_manager = "cm"
        mod._initialized = True

        mod.reset_checkpointer()

        assert mod._checkpointer is None
        assert mod._context_manager is None
        assert mod._initialized is False
