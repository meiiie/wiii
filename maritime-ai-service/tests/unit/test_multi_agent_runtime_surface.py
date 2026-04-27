"""Guards for canonical WiiiRunner runtime import surfaces."""

import ast
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.streaming_runtime import process_with_multi_agent_streaming
from app.engine.multi_agent.stream_utils import create_status_event


@pytest.mark.asyncio
async def test_runtime_surface_delegates_to_sync_impl():
    sys.modules.pop("app.engine.multi_agent.graph", None)

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
async def test_runtime_surface_skips_unpatched_legacy_graph_module():
    import app.engine.multi_agent.graph  # noqa: F401
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


@pytest.mark.asyncio
async def test_graph_surface_delegates_to_runtime_entrypoint():
    from app.engine.multi_agent import graph

    process = AsyncMock(return_value={"response": "runtime-ok"})

    with patch("app.engine.multi_agent.runtime.process_with_multi_agent", new=process):
        result = await graph.process_with_multi_agent(
            query="hello",
            user_id="user-1",
            session_id="session-1",
        )

    assert result == {"response": "runtime-ok"}
    process.assert_awaited_once()
    assert process.call_args.kwargs["query"] == "hello"


def test_graph_tool_collection_wrapper_uses_graph_settings_and_restores(monkeypatch):
    from app.engine.multi_agent import graph

    calls = []
    original_settings = object()
    patched_settings = object()
    state = {"session_id": "session-1"}

    class FakeToolCollection:
        settings = original_settings

        def _collect_direct_tools(self, query, *, user_role, state=None):
            calls.append((self.settings, query, user_role, state))
            return ["weather_tool"], ["datetime_tool"]

    fake_tools = FakeToolCollection()
    monkeypatch.setattr(graph, "_tool_collection_module", fake_tools)
    monkeypatch.setattr(graph, "settings", patched_settings)

    result = graph._collect_direct_tools(
        "weather now",
        user_role="teacher",
        state=state,
    )

    assert result == (["weather_tool"], ["datetime_tool"])
    assert calls == [(patched_settings, "weather now", "teacher", state)]
    assert fake_tools.settings is original_settings


def test_graph_tool_collection_wrapper_restores_settings_after_error(monkeypatch):
    from app.engine.multi_agent import graph

    original_settings = object()
    patched_settings = object()

    class FakeToolCollection:
        settings = original_settings

        def _direct_required_tool_names(self, query, *, user_role):
            assert self.settings is patched_settings
            raise RuntimeError("tool selection failed")

    fake_tools = FakeToolCollection()
    monkeypatch.setattr(graph, "_tool_collection_module", fake_tools)
    monkeypatch.setattr(graph, "settings", patched_settings)

    with pytest.raises(RuntimeError, match="tool selection failed"):
        graph._direct_required_tool_names("hello", user_role="student")

    assert fake_tools.settings is original_settings


def test_graph_code_studio_tool_collection_wrapper_uses_graph_settings(monkeypatch):
    from app.engine.multi_agent import graph

    calls = []
    original_settings = object()
    patched_settings = object()

    class FakeToolCollection:
        settings = original_settings

        def _collect_code_studio_tools(self, query, *, user_role):
            calls.append((self.settings, query, user_role))
            return ["code_studio"], ["render_app"]

    fake_tools = FakeToolCollection()
    monkeypatch.setattr(graph, "_tool_collection_module", fake_tools)
    monkeypatch.setattr(graph, "settings", patched_settings)

    result = graph._collect_code_studio_tools("build an app", user_role="teacher")

    assert result == (["code_studio"], ["render_app"])
    assert calls == [(patched_settings, "build an app", "teacher")]
    assert fake_tools.settings is original_settings


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

    import_from_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    dynamic_import_modules = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "app.engine.multi_agent.graph"
        and (
            (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            )
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            )
        )
    }
    forbidden_module = "app.engine.multi_agent.graph"
    assert forbidden_module not in import_from_modules
    assert forbidden_module not in imported_modules
    assert forbidden_module not in dynamic_import_modules


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
