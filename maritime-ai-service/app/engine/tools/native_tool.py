"""Wiii native Tool — replaces langchain_core.tools.

Phase 2 of the runtime migration epic (issue #207). Drop-in replacement
for ``langchain_core.tools.{tool, StructuredTool, BaseTool}``: same call
shape (``.name``, ``.description``, ``.invoke()``, ``.ainvoke()``) so the
existing ``ToolRegistry`` (in ``registry.py``) and call sites continue to
work without behavioural change.

Output: provider-agnostic JSON Schema via ``Tool.to_openai_schema()`` and
``Tool.to_anthropic_schema()``. The OpenAI shape is also accepted by
Gemini/Zhipu via their OpenAI-compat endpoints.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, ConfigDict, create_model


def _build_input_model(
    fn: Callable, model_name: Optional[str] = None
) -> tuple[type[BaseModel], bool]:
    """Derive a Pydantic model from a callable signature.

    Returns (model, accepts_var_keyword). When the function declares
    ``**kwargs``, the model is configured with ``extra="allow"`` so the
    schema is still valid JSON Schema while runtime invoke can pass any
    extras through.
    """
    sig = inspect.signature(fn)
    fields: dict[str, tuple[Any, Any]] = {}
    accepts_var_keyword = False
    for pname, param in sig.parameters.items():
        if pname in {"self", "cls"}:
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_var_keyword = True
            continue
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        annotation = (
            param.annotation if param.annotation is not inspect.Parameter.empty else str
        )
        default = param.default if param.default is not inspect.Parameter.empty else ...
        fields[pname] = (annotation, default)

    name = model_name or f"{fn.__name__.title().replace('_', '')}Input"
    config = ConfigDict(extra="allow") if accepts_var_keyword else None

    if not fields:
        # Zero declared parameters — empty model. ``extra="allow"`` lets
        # ``**kwargs`` style functions accept any input.
        if config is not None:
            return create_model(name, __config__=config), accepts_var_keyword
        return create_model(name), accepts_var_keyword

    if config is not None:
        return create_model(name, __config__=config, **fields), accepts_var_keyword
    return create_model(name, **fields), accepts_var_keyword


@dataclass
class Tool:
    """A single tool — function + metadata + JSON Schema."""

    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable
    is_async: bool = False
    requires_confirmation: bool = False
    mutates_state: bool = False
    accepts_var_keyword: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def args(self) -> dict[str, Any]:
        """Return JSON schema of arguments — mirrors ``langchain_core.tools.BaseTool.args``."""
        schema = self.input_model.model_json_schema()
        return schema.get("properties", {})

    @property
    def args_schema(self) -> type[BaseModel]:
        """Pydantic input model — mirrors ``langchain_core.tools.StructuredTool.args_schema``."""
        return self.input_model

    def to_openai_schema(self) -> dict[str, Any]:
        """OpenAI Chat Completions tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Anthropic Messages tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

    def _normalize_input(self, input: Union[str, dict, None]) -> dict:
        """Accept dict, string, or None — match LangChain's permissive ``invoke``."""
        if input is None:
            return {}
        if isinstance(input, dict):
            return input
        # String input → assign to first parameter if exactly one exists.
        params = list(self.input_model.model_fields.keys())
        if len(params) == 1:
            return {params[0]: input}
        if not params:
            return {}
        # Multiple params + string → ambiguous; let pydantic raise.
        raise TypeError(
            f"Tool {self.name!r} expects {params!r}; cannot map a bare string."
        )

    def _resolve_call_args(self, input: Union[str, dict, None], kwargs: dict) -> dict:
        args = self._normalize_input(input) if input is not None else kwargs
        validated = self.input_model.model_validate(args)
        # When the underlying function declares ``**kwargs``, pass the raw
        # validated dict (model_dump strips extras under ``extra="allow"`` only
        # for declared fields, so we merge to preserve passthrough).
        if self.accepts_var_keyword:
            merged = dict(args)
            merged.update(validated.model_dump())
            return merged
        return validated.model_dump()

    def invoke(self, input: Union[str, dict, None] = None, **kwargs: Any) -> Any:
        """Synchronous invocation."""
        call_args = self._resolve_call_args(input, kwargs)
        result = self.fn(**call_args)
        if inspect.iscoroutine(result):
            raise RuntimeError(
                f"Tool {self.name!r} is async; use ``await tool.ainvoke(...)``"
            )
        return result

    async def ainvoke(self, input: Union[str, dict, None] = None, **kwargs: Any) -> Any:
        """Asynchronous invocation."""
        call_args = self._resolve_call_args(input, kwargs)
        result = self.fn(**call_args)
        if inspect.iscoroutine(result):
            result = await result
        return result

    @classmethod
    def from_function(
        cls,
        func: Callable,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        args_schema: Optional[type[BaseModel]] = None,
    ) -> "Tool":
        """Build a Tool from a function — mirrors ``StructuredTool.from_function``."""
        if args_schema is not None:
            input_model = args_schema
            accepts_var_keyword = False
        else:
            input_model, accepts_var_keyword = _build_input_model(func)
        is_async = inspect.iscoroutinefunction(func)
        return cls(
            name=name or func.__name__,
            description=description or (func.__doc__ or "").strip().split("\n")[0],
            input_model=input_model,
            fn=func,
            is_async=is_async,
            accepts_var_keyword=accepts_var_keyword,
        )


# Alias for migration: ``StructuredTool`` was the explicit-schema variant in
# LangChain. Native ``Tool`` already supports ``args_schema=`` via
# ``from_function`` so the two collapse into one class.
StructuredTool = Tool


def tool(
    name_or_fn: Union[str, Callable, None] = None,
    *,
    description: Optional[str] = None,
    args_schema: Optional[type[BaseModel]] = None,
    requires_confirmation: bool = False,
    mutates_state: bool = False,
) -> Union[Tool, Callable[..., Tool]]:
    """Decorator: wrap a function as a ``Tool``.

    Usage::

        @tool
        def f(x: str) -> str: ...

        @tool("custom_name")
        def f(x: str) -> str: ...

        @tool(description="Search the KB")
        def f(query: str) -> str: ...
    """

    def make_tool(fn: Callable, _name: Optional[str] = None) -> Tool:
        if args_schema is not None:
            input_model = args_schema
            accepts_var_keyword = False
        else:
            input_model, accepts_var_keyword = _build_input_model(fn)
        is_async = inspect.iscoroutinefunction(fn)
        return Tool(
            name=_name or fn.__name__,
            description=description or (fn.__doc__ or "").strip().split("\n")[0],
            input_model=input_model,
            fn=fn,
            is_async=is_async,
            requires_confirmation=requires_confirmation,
            mutates_state=mutates_state,
            accepts_var_keyword=accepts_var_keyword,
        )

    if callable(name_or_fn) and not isinstance(name_or_fn, str):
        # @tool (no parens)
        return make_tool(name_or_fn)
    if isinstance(name_or_fn, str):
        # @tool("name")
        def named_wrapper(fn: Callable) -> Tool:
            return make_tool(fn, _name=name_or_fn)
        return named_wrapper

    # @tool() or @tool(description=...) etc.
    def wrapper(fn: Callable) -> Tool:
        return make_tool(fn)
    return wrapper


__all__ = ["Tool", "StructuredTool", "tool"]
