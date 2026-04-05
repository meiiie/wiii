"""Lazy runtime bindings for admin router helpers.

This module keeps ``admin.py`` as a thin HTTP surface while preserving
patchable names there for tests and runtime wiring.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def __getattr__(name: str) -> Any:
    binding_map = {
        "DEFAULT_EMBEDDING_MODEL": (
            "app.engine.model_catalog",
            "DEFAULT_EMBEDDING_MODEL",
        ),
        "GOOGLE_DEFAULT_MODEL": (
            "app.engine.model_catalog",
            "GOOGLE_DEFAULT_MODEL",
        ),
        "OPENAI_DEFAULT_MODEL": (
            "app.engine.model_catalog",
            "OPENAI_DEFAULT_MODEL",
        ),
        "OPENAI_DEFAULT_MODEL_ADVANCED": (
            "app.engine.model_catalog",
            "OPENAI_DEFAULT_MODEL_ADVANCED",
        ),
        "get_chat_model_metadata": (
            "app.engine.model_catalog",
            "get_chat_model_metadata",
        ),
        "get_embedding_dimensions": (
            "app.engine.model_catalog",
            "get_embedding_dimensions",
        ),
        "get_default_embedding_model_for_provider": (
            "app.engine.model_catalog",
            "get_default_embedding_model_for_provider",
        ),
        "get_embedding_model_metadata": (
            "app.engine.model_catalog",
            "get_embedding_model_metadata",
        ),
        "resolve_openai_catalog_provider": (
            "app.engine.model_catalog",
            "resolve_openai_catalog_provider",
        ),
        "create_provider": (
            "app.engine.llm_provider_registry",
            "create_provider",
        ),
        "get_supported_provider_names": (
            "app.engine.llm_provider_registry",
            "get_supported_provider_names",
        ),
        "is_supported_provider": (
            "app.engine.llm_provider_registry",
            "is_supported_provider",
        ),
        "get_runtime_provider_preset": (
            "app.engine.llm_runtime_profiles",
            "get_runtime_provider_preset",
        ),
        "is_known_default_provider_chain": (
            "app.engine.llm_runtime_profiles",
            "is_known_default_provider_chain",
        ),
        "should_apply_openrouter_defaults": (
            "app.engine.llm_runtime_profiles",
            "should_apply_openrouter_defaults",
        ),
        "dumps_agent_runtime_profiles": (
            "app.engine.multi_agent.agent_runtime_profiles",
            "dumps_agent_runtime_profiles",
        ),
        "sanitize_agent_runtime_profiles": (
            "app.engine.multi_agent.agent_runtime_profiles",
            "sanitize_agent_runtime_profiles",
        ),
        "build_timeout_profiles_snapshot": (
            "app.engine.llm_timeout_policy",
            "build_timeout_profiles_snapshot",
        ),
        "dumps_timeout_provider_overrides": (
            "app.engine.llm_timeout_policy",
            "dumps_timeout_provider_overrides",
        ),
        "loads_timeout_provider_overrides": (
            "app.engine.llm_timeout_policy",
            "loads_timeout_provider_overrides",
        ),
        "get_ingestion_service": (
            "app.services.multimodal_ingestion_service",
            "get_ingestion_service",
        ),
        "get_user_graph_repository": (
            "app.repositories.user_graph_repository",
            "get_user_graph_repository",
        ),
        "get_domain_registry": (
            "app.domains.registry",
            "get_domain_registry",
        ),
        "get_persisted_llm_runtime_policy": (
            "app.services.llm_runtime_policy_service",
            "get_persisted_llm_runtime_policy",
        ),
        "get_shared_session_factory": (
            "app.core.database",
            "get_shared_session_factory",
        ),
    }
    target = binding_map.get(name)
    if target is None:
        raise AttributeError(name)
    return _load_attr(*target)


__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "GOOGLE_DEFAULT_MODEL",
    "OPENAI_DEFAULT_MODEL",
    "OPENAI_DEFAULT_MODEL_ADVANCED",
    "build_timeout_profiles_snapshot",
    "create_provider",
    "dumps_agent_runtime_profiles",
    "dumps_timeout_provider_overrides",
    "get_chat_model_metadata",
    "get_domain_registry",
    "get_default_embedding_model_for_provider",
    "get_embedding_dimensions",
    "get_embedding_model_metadata",
    "get_ingestion_service",
    "get_persisted_llm_runtime_policy",
    "get_runtime_provider_preset",
    "get_shared_session_factory",
    "get_supported_provider_names",
    "get_user_graph_repository",
    "is_known_default_provider_chain",
    "is_supported_provider",
    "loads_timeout_provider_overrides",
    "OPENAI_DEFAULT_MODEL",
    "OPENAI_DEFAULT_MODEL_ADVANCED",
    "resolve_openai_catalog_provider",
    "sanitize_agent_runtime_profiles",
    "should_apply_openrouter_defaults",
]
