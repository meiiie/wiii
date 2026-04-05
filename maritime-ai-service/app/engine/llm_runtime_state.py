"""Shared runtime-state access for LLM orchestration observers.

This lets services inspect current pool/runtime state without importing the
heavy ``LLMPool`` module directly.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

_get_stats: Callable[[], dict[str, Any]] | None = None
_get_provider_info: Callable[[str], Any] | None = None
_get_request_selectable_providers: Callable[[], list[str]] | None = None


def _ensure_runtime_access_registered() -> None:
    global _get_stats, _get_provider_info, _get_request_selectable_providers
    if (
        _get_stats is not None
        and _get_provider_info is not None
        and _get_request_selectable_providers is not None
    ):
        return
    try:
        importlib.import_module("app.engine.llm_pool")
    except Exception:
        return


def register_llm_runtime_access(
    *,
    get_stats: Callable[[], dict[str, Any]],
    get_provider_info: Callable[[str], Any],
    get_request_selectable_providers: Callable[[], list[str]],
) -> None:
    global _get_stats, _get_provider_info, _get_request_selectable_providers
    _get_stats = get_stats
    _get_provider_info = get_provider_info
    _get_request_selectable_providers = get_request_selectable_providers


def get_llm_runtime_stats() -> dict[str, Any]:
    _ensure_runtime_access_registered()
    if _get_stats is None:
        return {}
    return _get_stats()


def get_llm_runtime_provider_info(name: str):
    _ensure_runtime_access_registered()
    if _get_provider_info is None:
        return None
    return _get_provider_info(name)


def get_llm_runtime_request_selectable_providers() -> list[str]:
    _ensure_runtime_access_registered()
    if _get_request_selectable_providers is None:
        return []
    return _get_request_selectable_providers()
