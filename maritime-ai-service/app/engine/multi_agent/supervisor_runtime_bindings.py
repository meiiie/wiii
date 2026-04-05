"""Lazy runtime bindings for supervisor orchestration helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def __getattr__(name: str) -> Any:
    binding_map = {
        "RoutingDecision": (
            "app.engine.structured_schemas",
            "RoutingDecision",
        ),
        "StructuredInvokeService": (
            "app.services.structured_invoke_service",
            "StructuredInvokeService",
        ),
        "LLMPool": ("app.engine.llm_pool", "LLMPool"),
        "is_rate_limit_error": (
            "app.engine.llm_pool",
            "is_rate_limit_error",
        ),
        "extract_thinking_from_response": (
            "app.services.output_processor",
            "extract_thinking_from_response",
        ),
        "build_supervisor_card_prompt": (
            "app.engine.character.character_card",
            "build_supervisor_card_prompt",
        ),
        "build_supervisor_micro_card_prompt": (
            "app.engine.character.character_card",
            "build_supervisor_micro_card_prompt",
        ),
        "build_synthesis_card_prompt": (
            "app.engine.character.character_card",
            "build_synthesis_card_prompt",
        ),
        "resolve_visual_intent": (
            "app.engine.multi_agent.visual_intent_resolver",
            "resolve_visual_intent",
        ),
    }
    target = binding_map.get(name)
    if target is None:
        raise AttributeError(name)
    return _load_attr(*target)


def get_synth_settings() -> Any:
    return _load_attr("app.core.config", "get_settings")()


def get_domain_registry() -> Any:
    return _load_attr("app.domains.registry", "get_domain_registry")()


def get_skill_handbook() -> Any:
    return _load_attr("app.engine.skills.skill_handbook", "get_skill_handbook")()


def plan_parallel_targets(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.multi_agent.orchestration_planner",
        "plan_parallel_targets",
    )
    return fn(*args, **kwargs)


__all__ = [
    "LLMPool",
    "RoutingDecision",
    "StructuredInvokeService",
    "build_supervisor_card_prompt",
    "build_supervisor_micro_card_prompt",
    "build_synthesis_card_prompt",
    "extract_thinking_from_response",
    "get_domain_registry",
    "get_skill_handbook",
    "get_synth_settings",
    "is_rate_limit_error",
    "plan_parallel_targets",
    "resolve_visual_intent",
]
