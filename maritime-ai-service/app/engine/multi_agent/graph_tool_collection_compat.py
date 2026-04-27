"""Compatibility helpers for graph-local tool collection wrappers.

These helpers keep the legacy ``app.engine.multi_agent.graph`` patch surface
small while preserving graph-local ``settings`` monkeypatch behavior.
"""

from typing import Any


def _call_with_tool_collection_settings(
    tool_collection_module: Any,
    settings_obj: Any,
    function_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    original_settings = tool_collection_module.settings
    tool_collection_module.settings = settings_obj
    try:
        return getattr(tool_collection_module, function_name)(*args, **kwargs)
    finally:
        tool_collection_module.settings = original_settings


def collect_direct_tools_with_settings(
    query: str,
    user_role: str = "student",
    *,
    state: Any = None,
    settings_obj: Any,
    tool_collection_module: Any,
) -> Any:
    return _call_with_tool_collection_settings(
        tool_collection_module,
        settings_obj,
        "_collect_direct_tools",
        query,
        user_role=user_role,
        state=state,
    )


def collect_code_studio_tools_with_settings(
    query: str,
    user_role: str = "student",
    *,
    settings_obj: Any,
    tool_collection_module: Any,
) -> Any:
    return _call_with_tool_collection_settings(
        tool_collection_module,
        settings_obj,
        "_collect_code_studio_tools",
        query,
        user_role=user_role,
    )


def direct_required_tool_names_with_settings(
    query: str,
    user_role: str = "student",
    *,
    settings_obj: Any,
    tool_collection_module: Any,
) -> list[str]:
    return _call_with_tool_collection_settings(
        tool_collection_module,
        settings_obj,
        "_direct_required_tool_names",
        query,
        user_role=user_role,
    )


def code_studio_required_tool_names_with_settings(
    query: str,
    user_role: str = "student",
    *,
    settings_obj: Any,
    tool_collection_module: Any,
) -> list[str]:
    return _call_with_tool_collection_settings(
        tool_collection_module,
        settings_obj,
        "_code_studio_required_tool_names",
        query,
        user_role=user_role,
    )
