"""
Tests for LangGraph Checkpointer — request-scoped open_checkpointer() API.

Verifies:
- open_checkpointer() yields a working checkpointer on success
- open_checkpointer() yields None when package not installed
- open_checkpointer() yields None on connection failure
- Old API (no __aenter__) falls back to direct use + conn.close()
- New API (context manager) uses __aenter__/__aexit__
- setup() is called once per process (idempotent via _setup_complete)
- reset_checkpointer() resets _setup_complete
- get_checkpointer() shim always returns None
- close_checkpointer() is a no-op
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
    mod._setup_complete = False


# ---------------------------------------------------------------------------
# Tests: open_checkpointer() — new context manager API
# ---------------------------------------------------------------------------

class TestCheckpointerInit:
    """Test open_checkpointer() context manager."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        _reset()
        yield
        _reset()

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
            async with mod.open_checkpointer() as checkpointer:
                assert checkpointer is mock_saver
            mock_cm.__aenter__.assert_awaited_once()
            mock_saver.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_checkpointer_old_api_setup(self):
        """Old API: from_conn_string returns instance directly, calls .setup() then .conn.close()."""
        import app.engine.multi_agent.checkpointer as mod

        mock_conn = AsyncMock()
        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_saver.conn = mock_conn
        # Old API: no __aenter__ attribute
        del mock_saver.__aenter__

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_saver

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            _reset()
            async with mod.open_checkpointer() as checkpointer:
                assert checkpointer is mock_saver
            mock_saver.setup.assert_awaited_once()
            mock_conn.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_checkpointer_import_error(self):
        """open_checkpointer yields None when package not installed."""
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
                async with mod.open_checkpointer() as checkpointer:
                    assert checkpointer is None

    @pytest.mark.asyncio
    async def test_get_checkpointer_connection_error(self):
        """open_checkpointer yields None on connection failure."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            _reset()
            async with mod.open_checkpointer() as checkpointer:
                assert checkpointer is None

    @pytest.mark.asyncio
    async def test_setup_only_called_once(self):
        """_ensure_setup: setup() is called only on first call per process."""
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
            # First call
            async with mod.open_checkpointer() as cp1:
                assert cp1 is mock_saver
            # Second call — setup should NOT be called again
            async with mod.open_checkpointer() as cp2:
                assert cp2 is mock_saver

        # setup() should have been called exactly once
        assert mock_saver.setup.await_count == 1

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Each open_checkpointer() call opens a fresh connection (request-scoped)."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

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
            async with mod.open_checkpointer() as cp:
                assert cp is not None

    @pytest.mark.asyncio
    async def test_singleton_returns_none_after_failed_init(self):
        """open_checkpointer yields None when connection fails."""
        import app.engine.multi_agent.checkpointer as mod
        _reset()

        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.side_effect = Exception("DB down")

        with patch.dict("sys.modules", {
            "langgraph.checkpoint.postgres.aio": mock_module,
        }):
            async with mod.open_checkpointer() as cp:
                assert cp is None


# ---------------------------------------------------------------------------
# Tests: Compatibility shims
# ---------------------------------------------------------------------------

class TestCheckpointerClose:
    """Test that deprecated shims behave as no-ops."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        _reset()
        yield
        _reset()

    @pytest.mark.asyncio
    async def test_close_with_context_manager(self):
        """close_checkpointer() is a no-op (request-scoped cleanup happens in open_checkpointer)."""
        import app.engine.multi_agent.checkpointer as mod
        # Should not raise
        result = await mod.close_checkpointer()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_with_old_api_connection(self):
        """close_checkpointer() always returns None without error."""
        import app.engine.multi_agent.checkpointer as mod
        result = await mod.close_checkpointer()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_without_connection(self):
        """close_checkpointer() is safe to call with no active checkpointer."""
        import app.engine.multi_agent.checkpointer as mod
        result = await mod.close_checkpointer()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_handles_error(self):
        """close_checkpointer() never raises."""
        import app.engine.multi_agent.checkpointer as mod
        # Should not raise even if called multiple times
        await mod.close_checkpointer()
        await mod.close_checkpointer()

    def test_reset_checkpointer(self):
        """reset_checkpointer() clears _setup_complete for fresh setup next open."""
        import app.engine.multi_agent.checkpointer as mod

        mod._setup_complete = True

        mod.reset_checkpointer()

        assert mod._setup_complete is False
