"""Helpers for reporting the effective runtime LLM provider/model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import settings


def _configured_model_for_provider(provider: str) -> str:
    """Return the configured model name for a provider."""
    normalized = (provider or "").strip().lower()
    if normalized == "google":
        return settings.google_model
    if normalized in {"openai", "openrouter"}:
        return settings.openai_model
    if normalized == "ollama":
        return settings.ollama_model
    return settings.rag_model_version


def get_active_runtime_provider(preferred_provider: str | None = None) -> str:
    """Resolve the active provider from metadata, pool state, or config."""
    provider = (preferred_provider or "").strip().lower()
    if provider:
        return provider

    try:
        from app.engine.llm_pool import LLMPool

        pool_provider = LLMPool.get_active_provider()
        if isinstance(pool_provider, str) and pool_provider.strip():
            return pool_provider.strip().lower()
    except Exception:
        pass

    configured = getattr(settings, "llm_provider", "google")
    if isinstance(configured, str) and configured.strip():
        return configured.strip().lower()
    return "google"


def resolve_runtime_llm_metadata(
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Return normalized runtime provider/model metadata."""
    raw_provider = None
    raw_model = None

    if metadata:
        raw_provider = metadata.get("provider") or metadata.get("active_provider")
        raw_model = metadata.get("model")

    provider = get_active_runtime_provider(raw_provider)
    model = raw_model or _configured_model_for_provider(provider)

    return {
        "provider": provider,
        "model": model,
    }
