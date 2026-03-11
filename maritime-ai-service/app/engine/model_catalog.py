"""Canonical runtime model metadata shared across active backend paths."""

from __future__ import annotations

from dataclasses import dataclass


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
