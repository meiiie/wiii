"""Lazy runtime bindings for vision processor helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def __getattr__(name: str) -> Any:
    binding_map = {
        "ChunkResult": ("app.services.chunking_service", "ChunkResult"),
        "PageResult": (
            "app.services.multimodal_ingestion_contracts",
            "PageResult",
        ),
    }
    target = binding_map.get(name)
    if target is None:
        raise AttributeError(name)
    return _load_attr(*target)


def get_effective_org_id() -> Any:
    return _load_attr("app.core.org_filter", "get_effective_org_id")()


async def _analyze_image_with_vision(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.agentic_rag.visual_rag",
        "_analyze_image_with_vision",
    )
    return await fn(*args, **kwargs)


async def _fetch_image_as_base64(*args, **kwargs) -> Any:
    fn = _load_attr(
        "app.engine.agentic_rag.visual_rag",
        "_fetch_image_as_base64",
    )
    return await fn(*args, **kwargs)


__all__ = [
    "ChunkResult",
    "PageResult",
    "_analyze_image_with_vision",
    "_fetch_image_as_base64",
    "get_effective_org_id",
]
