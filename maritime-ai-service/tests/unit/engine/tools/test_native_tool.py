"""Phase 2 native Tool — Runtime Migration #207.

Locks in the contract for ``Tool``, ``StructuredTool``, and the ``@tool``
decorator. Anything that consumes these downstream relies on this exact
shape (``.invoke``, ``.ainvoke``, ``.name``, ``.description``,
``.to_openai_schema``, ``.to_anthropic_schema``).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.engine.tools.native_tool import StructuredTool, Tool, tool


# ── @tool decorator forms ──

def test_tool_decorator_no_args_uses_fn_name():
    @tool
    def search(query: str) -> str:
        """Search the knowledge base."""
        return f"r:{query}"

    assert isinstance(search, Tool)
    assert search.name == "search"
    assert "Search the knowledge base" in search.description


def test_tool_decorator_with_explicit_name():
    @tool("custom_name")
    def f(q: str) -> str:
        return q

    assert f.name == "custom_name"


def test_tool_decorator_with_description_only():
    @tool(description="Compute things")
    def calc(x: str) -> str:
        return x

    assert calc.name == "calc"
    assert calc.description == "Compute things"


def test_tool_decorator_with_zero_params():
    @tool(description="Get current time")
    def now() -> str:
        return "now"

    assert now.name == "now"
    assert now.invoke() == "now"


def test_tool_decorator_marks_async_function():
    @tool
    async def fetch(url: str) -> str:
        return url

    assert fetch.is_async is True


# ── invoke ──

def test_invoke_with_string_maps_to_single_param():
    @tool
    def echo(query: str) -> str:
        return f"echo:{query}"

    assert echo.invoke("hi") == "echo:hi"


def test_invoke_with_dict():
    @tool
    def add(a: int, b: int) -> int:
        return a + b

    assert add.invoke({"a": 2, "b": 3}) == 5


def test_invoke_string_with_multiple_params_raises():
    @tool
    def add(a: int, b: int) -> int:
        return a + b

    with pytest.raises(TypeError, match="cannot map a bare string"):
        add.invoke("oops")


def test_invoke_async_function_via_invoke_raises():
    @tool
    async def fetch(url: str) -> str:
        return url

    with pytest.raises(RuntimeError, match="async"):
        fetch.invoke("http://x")


async def test_ainvoke_with_async_function():
    @tool
    async def fetch(url: str) -> str:
        return f"fetched:{url}"

    assert await fetch.ainvoke("http://x") == "fetched:http://x"


async def test_ainvoke_with_sync_function_works():
    @tool
    def echo(q: str) -> str:
        return q

    assert await echo.ainvoke("hi") == "hi"


# ── schema generation ──

def test_to_openai_schema_shape():
    @tool(description="Search the KB")
    def search(query: str) -> str:
        return ""

    schema = search.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "search"
    assert schema["function"]["description"] == "Search the KB"
    params = schema["function"]["parameters"]
    assert "query" in params["properties"]
    assert params["properties"]["query"]["type"] == "string"


def test_to_anthropic_schema_shape():
    @tool(description="Search the KB")
    def search(query: str) -> str:
        return ""

    schema = search.to_anthropic_schema()
    assert schema["name"] == "search"
    assert schema["description"] == "Search the KB"
    assert "query" in schema["input_schema"]["properties"]


def test_args_property_returns_pydantic_properties():
    @tool
    def f(query: str, limit: int = 10) -> str:
        return ""

    args = f.args
    assert "query" in args
    assert "limit" in args


def test_args_schema_alias_returns_input_model():
    """args_schema mirrors langchain_core StructuredTool — same Pydantic model."""

    @tool
    def f(query: str) -> str:
        return ""

    assert f.args_schema is f.input_model


def test_func_property_for_sync_tool():
    """func mirrors LangChain compat: sync fn ref, None for async tools."""

    @tool
    def f(q: str) -> str:
        return q

    assert f.func is f.fn
    assert f.coroutine is None


def test_coroutine_property_for_async_tool():
    """coroutine mirrors LangChain compat: coroutine ref, None for sync tools."""

    @tool
    async def f(q: str) -> str:
        return q

    assert f.coroutine is f.fn
    assert f.func is None


# ── StructuredTool.from_function ──

def test_structured_tool_alias_is_tool():
    assert StructuredTool is Tool


def test_from_function_inferred_schema():
    def f(text: str) -> str:
        return text

    t = StructuredTool.from_function(
        func=f, name="myfn", description="My fn"
    )
    assert isinstance(t, Tool)
    assert t.name == "myfn"
    assert t.description == "My fn"
    assert t.invoke("ok") == "ok"


def test_from_function_with_explicit_args_schema():
    class MyArgs(BaseModel):
        text: str
        limit: int = 5

    def f(text: str, limit: int = 5) -> str:
        return f"{text}:{limit}"

    t = StructuredTool.from_function(
        func=f, name="x", description="x", args_schema=MyArgs
    )
    schema = t.to_openai_schema()
    assert schema["function"]["parameters"]["properties"]["limit"]["default"] == 5


# ── pydantic validation ──

def test_invoke_validates_input_via_pydantic():
    @tool
    def add(a: int, b: int) -> int:
        return a + b

    with pytest.raises(Exception):  # pydantic ValidationError
        add.invoke({"a": "not_an_int", "b": 3})


def test_invoke_coerces_string_to_int():
    @tool
    def double(n: int) -> int:
        return n * 2

    # Pydantic coerces "5" → 5
    assert double.invoke({"n": "5"}) == 10


# ── **kwargs / variadic functions ──

def test_tool_with_var_keyword_accepts_arbitrary_extras():
    """Tools wrapping ``def f(**kwargs)`` must accept any input dict."""

    @tool
    def passthrough(**kwargs):
        return kwargs

    assert passthrough.invoke({}) == {}
    assert passthrough.invoke({"foo": 1, "bar": "x"}) == {"foo": 1, "bar": "x"}


def test_tool_with_var_keyword_marks_flag():
    @tool
    def passthrough(**kwargs):
        return kwargs

    assert passthrough.accepts_var_keyword is True


def test_tool_with_explicit_param_plus_var_keyword():
    """Mixed signature: explicit param + **kwargs."""

    @tool
    def f(action: str, **extras) -> dict:
        return {"action": action, "extras": extras}

    out = f.invoke({"action": "go", "speed": 5, "label": "x"})
    assert out["action"] == "go"
    assert out["extras"] == {"speed": 5, "label": "x"}
