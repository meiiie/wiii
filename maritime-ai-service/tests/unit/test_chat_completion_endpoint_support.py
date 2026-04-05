from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.chat_completion_endpoint_support import process_chat_completion_request
from app.core.exceptions import ProviderUnavailableError


@pytest.mark.asyncio
async def test_process_chat_completion_request_rejects_unavailable_provider_before_chat_service_init():
    chat_request = SimpleNamespace(provider="google")

    with patch(
        "app.services.llm_selectability_service.ensure_provider_is_selectable",
        side_effect=ProviderUnavailableError(
            provider="google",
            reason_code="busy",
            message="Provider tam thoi ban hoac da cham gioi han.",
        ),
    ), patch("app.services.chat_service.get_chat_service") as mock_get_chat_service:
        with pytest.raises(ProviderUnavailableError):
            await process_chat_completion_request(
                chat_request=chat_request,
                background_save=lambda *args, **kwargs: None,
            )

    mock_get_chat_service.assert_not_called()


@pytest.mark.asyncio
async def test_process_chat_completion_request_uses_chat_service_for_auto_provider():
    chat_request = SimpleNamespace(provider="auto")
    expected = object()
    chat_service = SimpleNamespace(process_message=AsyncMock(return_value=expected))

    with patch(
        "app.services.chat_service.get_chat_service",
        return_value=chat_service,
    ) as mock_get_chat_service:
        result = await process_chat_completion_request(
            chat_request=chat_request,
            background_save=lambda *args, **kwargs: None,
        )

    assert result is expected
    mock_get_chat_service.assert_called_once()
    chat_service.process_message.assert_awaited_once()
    args = chat_service.process_message.await_args
    assert args.args == (chat_request,)
    assert callable(args.kwargs["background_save"])
