"""Lazy runtime bindings for product search runtime helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def build_wiii_runtime_prompt(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.character.character_card",
        "build_wiii_runtime_prompt",
    )
    return fn(*args, **kwargs)


def filter_tools_for_role(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.tools.runtime_context",
        "filter_tools_for_role",
    )
    return fn(*args, **kwargs)


async def invoke_tool_with_runtime(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.tools.invocation",
        "invoke_tool_with_runtime",
    )
    return await fn(*args, **kwargs)


def get_settings() -> Any:
    return _load_attr("app.core.config", "get_settings")()


def get_agent_llm(node_name: str, *, provider_override: str | None = None) -> Any:
    registry = _load_attr(
        "app.engine.multi_agent.agent_config",
        "AgentConfigRegistry",
    )
    return registry.get_llm(node_name, provider_override=provider_override)


def load_product_search_tools() -> list[Any]:
    tools = []
    get_product_search_tools = _load_attr(
        "app.engine.tools.product_search_tools",
        "get_product_search_tools",
    )
    tool_generate_product_report = _load_attr(
        "app.engine.tools.excel_report_tool",
        "tool_generate_product_report",
    )
    tools.extend(get_product_search_tools())
    tools.append(tool_generate_product_report)

    try:
        tool_fetch_product_detail = _load_attr(
            "app.engine.tools.product_page_scraper",
            "tool_fetch_product_detail",
        )
        tools.append(tool_fetch_product_detail)
    except Exception:
        pass

    tool_names = {tool.name for tool in tools}
    current_settings = get_settings()

    if current_settings.enable_dealer_search and "tool_dealer_search" not in tool_names:
        get_dealer_search_tool = _load_attr(
            "app.engine.tools.dealer_search_tool",
            "get_dealer_search_tool",
        )
        tools.append(get_dealer_search_tool())

    if (
        current_settings.enable_contact_extraction
        and "tool_extract_contacts" not in tool_names
    ):
        get_contact_extraction_tool = _load_attr(
            "app.engine.tools.contact_extraction_tool",
            "get_contact_extraction_tool",
        )
        tools.append(get_contact_extraction_tool())

    if (
        current_settings.enable_international_search
        and "tool_international_search" not in tool_names
    ):
        get_international_search_tool = _load_attr(
            "app.engine.tools.international_search_tool",
            "get_international_search_tool",
        )
        tools.append(get_international_search_tool())

    if (
        current_settings.enable_visual_product_search
        and "tool_identify_product_from_image" not in tool_names
    ):
        get_visual_product_search_tool = _load_attr(
            "app.engine.tools.visual_product_search",
            "get_visual_product_search_tool",
        )
        tools.append(get_visual_product_search_tool())

    return tools


async def plan_search_queries(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.tools.query_planner",
        "plan_search_queries",
    )
    return await fn(*args, **kwargs)


def format_plan_for_prompt(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.tools.query_planner",
        "format_plan_for_prompt",
    )
    return fn(*args, **kwargs)


def select_runtime_tools(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.skills.skill_recommender",
        "select_runtime_tools",
    )
    return fn(*args, **kwargs)


def get_effective_provider_impl(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.multi_agent.graph_surface_runtime",
        "get_effective_provider_impl",
    )
    return fn(*args, **kwargs)


def get_search_platform_registry() -> Any:
    fn = _load_attr(
        "app.engine.search_platforms",
        "get_search_platform_registry",
    )
    return fn()


async def curate_with_llm(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.multi_agent.subagents.search.curation",
        "curate_with_llm",
    )
    return await fn(*args, **kwargs)


__all__ = [
    "build_wiii_runtime_prompt",
    "curate_with_llm",
    "filter_tools_for_role",
    "format_plan_for_prompt",
    "get_agent_llm",
    "get_effective_provider_impl",
    "get_search_platform_registry",
    "get_settings",
    "invoke_tool_with_runtime",
    "load_product_search_tools",
    "plan_search_queries",
    "select_runtime_tools",
]
