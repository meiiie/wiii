"""Guards for canonical WiiiRunner runtime import surfaces."""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.streaming_runtime import process_with_multi_agent_streaming
from app.engine.multi_agent.stream_utils import create_status_event


@pytest.mark.asyncio
async def test_runtime_surface_delegates_to_sync_impl():
    from app.engine.multi_agent import runtime

    process = AsyncMock(return_value={"response": "ok"})

    with patch.object(runtime, "process_with_multi_agent_impl", new=process):
        result = await runtime.process_with_multi_agent(
            query="hello",
            user_id="user-1",
            session_id="session-1",
        )

    assert result == {"response": "ok"}
    process.assert_awaited_once()
    assert process.call_args.kwargs["query"] == "hello"
    assert process.call_args.kwargs["build_domain_config"] is runtime._build_domain_config
    assert process.call_args.kwargs["cleanup_tracer"] is runtime._cleanup_tracer


@pytest.mark.asyncio
async def test_runtime_surface_preserves_legacy_graph_patch_path():
    from app.engine.multi_agent.runtime import process_with_multi_agent

    process = AsyncMock(return_value={"response": "legacy-ok"})

    with patch("app.engine.multi_agent.graph.process_with_multi_agent", new=process):
        result = await process_with_multi_agent(
            query="hello",
            user_id="user-1",
            session_id="session-1",
        )

    assert result == {"response": "legacy-ok"}
    process.assert_awaited_once()


def test_runtime_surface_has_no_hard_graph_import():
    from app.engine.multi_agent import runtime

    source = Path(runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "app.engine.multi_agent.graph" not in imported_modules


@pytest.mark.asyncio
async def test_streaming_runtime_surface_delegates_to_streaming_entrypoint():
    expected_event = await create_status_event("ok")

    async def stream(*_args, **_kwargs):
        yield expected_event

    with patch(
        "app.engine.multi_agent.graph_streaming.process_with_multi_agent_streaming",
        new=stream,
    ):
        events = [
            event
            async for event in process_with_multi_agent_streaming(
                query="hello",
                user_id="user-1",
                session_id="session-1",
            )
        ]

    assert events == [expected_event]
