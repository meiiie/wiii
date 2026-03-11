"""Canonical runtime model metadata shared across active backend paths."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

_catalog_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatModelMetadata:
    provider: str
    model_name: str
    display_name: str
    status: str
    released_on: str | None = None


@dataclass(frozen=True)
class EmbeddingModelMetadata:
    model_name: str
    display_name: str
    dimensions: int
    status: str
    released_on: str | None = None
    production_default: bool = False


GOOGLE_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
GOOGLE_LEGACY_MODELS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
)

GOOGLE_CHAT_MODELS: dict[str, ChatModelMetadata] = {
    GOOGLE_DEFAULT_MODEL: ChatModelMetadata(
        provider="google",
        model_name=GOOGLE_DEFAULT_MODEL,
        display_name="Gemini 3.1 Flash-Lite Preview",
        status="current",
        released_on="2026-03-03",
    ),
    "gemini-2.5-flash": ChatModelMetadata(
        provider="google",
        model_name="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        status="legacy",
    ),
    "gemini-2.5-pro": ChatModelMetadata(
        provider="google",
        model_name="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        status="legacy",
    ),
    "gemini-2.0-flash": ChatModelMetadata(
        provider="google",
        model_name="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        status="legacy",
    ),
    "gemini-2.0-flash-exp": ChatModelMetadata(
        provider="google",
        model_name="gemini-2.0-flash-exp",
        display_name="Gemini 2.0 Flash Experimental",
        status="legacy",
    ),
}

DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_BENCHMARK_CANDIDATE = "gemini-embedding-2-preview"

EMBEDDING_MODELS: dict[str, EmbeddingModelMetadata] = {
    DEFAULT_EMBEDDING_MODEL: EmbeddingModelMetadata(
        model_name=DEFAULT_EMBEDDING_MODEL,
        display_name="Gemini Embedding 001",
        dimensions=768,
        status="stable",
        production_default=True,
    ),
    EMBEDDING_BENCHMARK_CANDIDATE: EmbeddingModelMetadata(
        model_name=EMBEDDING_BENCHMARK_CANDIDATE,
        display_name="Gemini Embedding 2 Preview",
        dimensions=3072,
        status="preview",
        released_on="2026-03-10",
    ),
}


def get_chat_model_metadata(model_name: str | None) -> ChatModelMetadata | None:
    if not model_name:
        return None
    return GOOGLE_CHAT_MODELS.get(model_name)


def get_embedding_model_metadata(model_name: str | None) -> EmbeddingModelMetadata | None:
    if not model_name:
        return None
    return EMBEDDING_MODELS.get(model_name)


def get_embedding_dimensions(model_name: str | None) -> int:
    metadata = get_embedding_model_metadata(model_name)
    if metadata is None:
        return EMBEDDING_MODELS[DEFAULT_EMBEDDING_MODEL].dimensions
    return metadata.dimensions


def is_legacy_google_model(model_name: str | None) -> bool:
    metadata = get_chat_model_metadata(model_name)
    return metadata is not None and metadata.status == "legacy"


def get_current_google_chat_models() -> tuple[str, ...]:
    return tuple(
        model.model_name
        for model in GOOGLE_CHAT_MODELS.values()
        if model.status == "current"
    )


# ---------------------------------------------------------------------------
# Multi-provider static catalogs
# ---------------------------------------------------------------------------

OPENROUTER_CHAT_MODELS: dict[str, ChatModelMetadata] = {
    "openai/gpt-oss-20b:free": ChatModelMetadata(
        provider="openrouter",
        model_name="openai/gpt-oss-20b:free",
        display_name="GPT-OSS 20B (Free)",
        status="preset",
    ),
    "openai/gpt-oss-120b:free": ChatModelMetadata(
        provider="openrouter",
        model_name="openai/gpt-oss-120b:free",
        display_name="GPT-OSS 120B (Free)",
        status="preset",
    ),
}

OLLAMA_KNOWN_MODELS: dict[str, ChatModelMetadata] = {
    "qwen3:4b-instruct-2507-q4_K_M": ChatModelMetadata(
        provider="ollama",
        model_name="qwen3:4b-instruct-2507-q4_K_M",
        display_name="Qwen3 4B Instruct (Q4_K_M)",
        status="preset",
    ),
    "qwen3:8b": ChatModelMetadata(
        provider="ollama",
        model_name="qwen3:8b",
        display_name="Qwen3 8B",
        status="preset",
    ),
}


# ---------------------------------------------------------------------------
# Multi-provider helper functions
# ---------------------------------------------------------------------------

def get_all_static_chat_models() -> dict[str, dict[str, ChatModelMetadata]]:
    """Return all static chat models grouped by provider."""
    return {
        "google": dict(GOOGLE_CHAT_MODELS),
        "openrouter": dict(OPENROUTER_CHAT_MODELS),
        "ollama": dict(OLLAMA_KNOWN_MODELS),
    }


def is_known_model(provider: str, model_name: str) -> bool:
    """Check if a model exists in any static catalog."""
    all_models = get_all_static_chat_models()
    provider_models = all_models.get(provider, {})
    return model_name in provider_models


# ---------------------------------------------------------------------------
# ModelCatalogService — aggregates static + runtime-discovered models
# ---------------------------------------------------------------------------

class ModelCatalogService:
    """Aggregates static catalogs with runtime-discovered models."""

    _ollama_cache: list[ChatModelMetadata] = []
    _ollama_cache_ts: float = 0.0
    _ollama_cache_ttl: float = 60.0

    @classmethod
    async def discover_ollama_models(cls, base_url: str) -> list[ChatModelMetadata]:
        """Query Ollama /api/tags and return discovered models."""
        import httpx

        now = time.time()
        if cls._ollama_cache and (now - cls._ollama_cache_ts) < cls._ollama_cache_ttl:
            return list(cls._ollama_cache)

        url = base_url.rstrip("/")
        if url.endswith("/api"):
            url = url[:-4]

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/api/tags")
                resp.raise_for_status()
                data = resp.json()

            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if not name:
                    continue
                models.append(ChatModelMetadata(
                    provider="ollama",
                    model_name=name,
                    display_name=name,
                    status="available",
                ))

            cls._ollama_cache = models
            cls._ollama_cache_ts = now
            return list(models)
        except Exception as exc:
            _catalog_logger.debug("Ollama discovery failed: %s", exc)
            return list(cls._ollama_cache)  # return stale cache on error

    @classmethod
    async def get_full_catalog(
        cls,
        ollama_base_url: str | None = None,
    ) -> dict:
        """Return complete model catalog grouped by provider."""
        from datetime import datetime, timezone

        catalog = get_all_static_chat_models()
        ollama_discovered = False

        if ollama_base_url:
            discovered = await cls.discover_ollama_models(ollama_base_url)
            ollama_discovered = len(discovered) > 0
            # Merge discovered into ollama catalog
            merged = dict(catalog.get("ollama", {}))
            for m in discovered:
                if m.model_name not in merged:
                    merged[m.model_name] = m
                # If already in static catalog, keep static metadata but mark available
            catalog["ollama"] = merged

        return {
            "providers": catalog,
            "embedding_models": dict(EMBEDDING_MODELS),
            "ollama_discovered": ollama_discovered,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def reset_cache(cls) -> None:
        """Clear discovery caches (for testing)."""
        cls._ollama_cache = []
        cls._ollama_cache_ts = 0.0
