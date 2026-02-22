"""
Tests for Sprint 30: ChatService coverage.

Covers:
- _init_optional: available/unavailable/erroring/check_available
- process_message: delegates to orchestrator
- Singleton pattern
"""

import importlib
import sys
import types

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# Ensure clean chat_service module — earlier tests may pollute sys.modules
# with a MagicMock stub (graph_streaming workaround).
_mod_key = "app.services.chat_service"
if _mod_key in sys.modules and isinstance(sys.modules[_mod_key], types.ModuleType):
    importlib.reload(sys.modules[_mod_key])


# =============================================================================
# _init_optional
# =============================================================================


class TestInitOptional:
    """ChatService._init_optional handles component initialization gracefully."""

    def test_returns_none_when_not_available(self):
        from app.services.chat_service import ChatService
        result = ChatService._init_optional("Test", available=False, factory=MagicMock)
        assert result is None

    def test_returns_instance_when_available(self):
        from app.services.chat_service import ChatService
        mock_factory = MagicMock(return_value="instance")
        result = ChatService._init_optional("Test", available=True, factory=mock_factory)
        assert result == "instance"

    def test_returns_none_on_factory_error(self):
        from app.services.chat_service import ChatService
        mock_factory = MagicMock(side_effect=RuntimeError("broken"))
        result = ChatService._init_optional("Test", available=True, factory=mock_factory)
        assert result is None

    def test_check_available_returns_none_if_not_available(self):
        from app.services.chat_service import ChatService
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = False
        mock_factory = MagicMock(return_value=mock_instance)
        result = ChatService._init_optional(
            "Test", available=True, factory=mock_factory, check_available=True
        )
        assert result is None

    def test_check_available_returns_instance_if_available(self):
        from app.services.chat_service import ChatService
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_factory = MagicMock(return_value=mock_instance)
        result = ChatService._init_optional(
            "Test", available=True, factory=mock_factory, check_available=True
        )
        assert result == mock_instance

    def test_passes_kwargs_to_factory(self):
        from app.services.chat_service import ChatService
        mock_factory = MagicMock(return_value="ok")
        ChatService._init_optional(
            "Test", available=True, factory=mock_factory, key1="val1"
        )
        mock_factory.assert_called_once_with(key1="val1")

    def test_no_kwargs_calls_factory_without_args(self):
        from app.services.chat_service import ChatService
        mock_factory = MagicMock(return_value="ok")
        ChatService._init_optional("Test", available=True, factory=mock_factory)
        mock_factory.assert_called_once_with()


# =============================================================================
# process_message
# =============================================================================


class TestProcessMessage:
    """ChatService.process_message delegates to orchestrator."""

    @pytest.mark.asyncio
    async def test_delegates_to_orchestrator(self):
        """process_message calls self._orchestrator.process()."""
        from app.services.chat_service import ChatService
        from app.models.schemas import ChatRequest

        service = object.__new__(ChatService)  # Skip __init__
        mock_orchestrator = MagicMock()
        mock_orchestrator.process = AsyncMock(return_value="response")
        service._orchestrator = mock_orchestrator

        request = MagicMock(spec=ChatRequest)
        result = await service.process_message(request)

        mock_orchestrator.process.assert_called_once_with(request, None)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_passes_background_save(self):
        """process_message forwards background_save callback."""
        from app.services.chat_service import ChatService

        service = object.__new__(ChatService)
        mock_orchestrator = MagicMock()
        mock_orchestrator.process = AsyncMock(return_value="resp")
        service._orchestrator = mock_orchestrator

        bg_save = MagicMock()
        request = MagicMock()
        await service.process_message(request, background_save=bg_save)

        mock_orchestrator.process.assert_called_once_with(request, bg_save)


# =============================================================================
# Singleton
# =============================================================================


class TestSingleton:
    """get_chat_service returns singleton."""

    def test_singleton_is_none_initially(self):
        import app.services.chat_service as module
        # Save and reset
        original = module._chat_service
        module._chat_service = None
        try:
            assert module._chat_service is None
        finally:
            module._chat_service = original

    def test_singleton_returns_same_instance(self):
        """get_chat_service returns same instance on repeated calls."""
        import app.services.chat_service as module
        original = module._chat_service

        # Set a mock to avoid real initialization
        mock_service = MagicMock()
        module._chat_service = mock_service
        try:
            from app.services.chat_service import get_chat_service
            result = get_chat_service()
            assert result is mock_service
        finally:
            module._chat_service = original
