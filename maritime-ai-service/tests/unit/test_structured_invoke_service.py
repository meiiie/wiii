from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel


class _Schema(BaseModel):
    status: str


@pytest.mark.asyncio
async def test_structured_invoke_uses_pinned_failover_for_explicit_provider():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    expected = SimpleNamespace(content='{"status":"ok"}')

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=expected),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
            provider="zhipu",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    assert mock_invoke.await_args.kwargs["failover_mode"] == "pinned"
    assert mock_invoke.await_args.kwargs["timeout_profile"] == "structured"
    assert callable(mock_invoke.await_args.kwargs["on_primary"])
    llm.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_structured_invoke_falls_back_to_json_parse_for_openai_compatible():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm._wiii_provider_name = "openai"
    llm.with_structured_output.side_effect = RuntimeError("native structured unsupported")

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=SimpleNamespace(content='{"status":"ok"}')),
    ):
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_structured_invoke_falls_back_to_json_when_native_path_breaks_after_auto_failover():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm._wiii_provider_name = "openai"
    structured_llm = MagicMock()
    llm.with_structured_output.return_value = structured_llm

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(
            side_effect=[
                RuntimeError("native structured failed after provider failover"),
                SimpleNamespace(content='```json\n{"status":"ok"}\n```'),
            ]
        ),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    assert mock_invoke.await_count == 2
    assert mock_invoke.await_args_list[0].args[0] is structured_llm
    assert callable(mock_invoke.await_args_list[0].kwargs["on_primary"])
    assert mock_invoke.await_args_list[1].args[0] is llm
    assert mock_invoke.await_args_list[1].kwargs["on_primary"] is not None
    raw_on_fallback = mock_invoke.await_args_list[1].kwargs["on_fallback"]
    fallback_llm = MagicMock()
    fallback_llm.streaming = True
    fallback_clone = MagicMock()
    fallback_clone.streaming = False
    fallback_llm.model_copy.return_value = fallback_clone
    assert raw_on_fallback(fallback_llm) is fallback_clone


@pytest.mark.asyncio
async def test_structured_invoke_honors_explicit_background_timeout_profile():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    structured_llm = MagicMock()
    llm.with_structured_output.return_value = structured_llm
    expected = _Schema(status="ok")

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=expected),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
            timeout_profile="background",
        )

    assert result == expected
    assert mock_invoke.await_args.kwargs["timeout_profile"] == "background"


@pytest.mark.asyncio
async def test_structured_invoke_uses_llm_runtime_provider_as_auto_primary_preference():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm._wiii_provider_name = "zhipu"
    expected = SimpleNamespace(content='{"status":"ok"}')

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=expected),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    assert mock_invoke.await_args.kwargs["provider"] == "zhipu"


@pytest.mark.asyncio
async def test_structured_invoke_skips_native_schema_path_for_auto_google_runtime():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm._wiii_provider_name = "google"

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=SimpleNamespace(content='{"status":"ok"}')),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    llm.with_structured_output.assert_not_called()
    assert mock_invoke.await_args.kwargs["provider"] == "google"


@pytest.mark.asyncio
async def test_structured_invoke_skips_native_schema_path_for_auto_nvidia_runtime():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm._wiii_provider_name = "nvidia"

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=SimpleNamespace(content='{"status":"ok"}')),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    llm.with_structured_output.assert_not_called()
    assert mock_invoke.await_args.kwargs["provider"] == "nvidia"


@pytest.mark.asyncio
async def test_structured_invoke_disables_streaming_for_native_structured_path():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    llm.streaming = True
    cloned_llm = MagicMock()
    cloned_llm.streaming = False
    structured_llm = MagicMock()
    llm.model_copy.return_value = cloned_llm
    cloned_llm.with_structured_output.return_value = structured_llm
    expected = _Schema(status="ok")

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=expected),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
            provider="google",
        )

    assert result == expected
    llm.model_copy.assert_called_once_with(update={"streaming": False})
    cloned_llm.with_structured_output.assert_called_once_with(_Schema)
    assert mock_invoke.await_args.args[0] is structured_llm


@pytest.mark.asyncio
async def test_structured_invoke_passes_on_failover_callback_through():
    from app.services.structured_invoke_service import StructuredInvokeService

    llm = MagicMock()
    expected = SimpleNamespace(content='{"status":"ok"}')
    on_failover = AsyncMock()

    with patch(
        "app.services.structured_invoke_service.ainvoke_with_failover",
        new=AsyncMock(return_value=expected),
    ) as mock_invoke:
        result = await StructuredInvokeService.ainvoke(
            llm=llm,
            schema=_Schema,
            payload="hello",
            provider="zhipu",
            on_failover=on_failover,
        )

    assert isinstance(result, _Schema)
    assert result.status == "ok"
    assert mock_invoke.await_args.kwargs["on_failover"] is on_failover
