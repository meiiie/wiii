"""Helpers for dual-write/read of shadow embedding tables."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Sequence

from app.engine.embedding_runtime import build_embedding_backend_for_provider_model
from app.services.embedding_space_guard import (
    EmbeddingSpaceContract,
    stamp_embedding_metadata,
)
from app.services.embedding_space_registry_service import EmbeddingSpaceRegistryEntry

logger = logging.getLogger(__name__)


def format_pg_array_literal(values: Sequence[float]) -> str:
    return "{" + ",".join(str(value) for value in values) + "}"


def embedding_matches_contract(
    embedding: Sequence[float] | None,
    contract: EmbeddingSpaceContract | EmbeddingSpaceRegistryEntry,
) -> bool:
    return bool(embedding) and len(embedding or []) == int(contract.dimensions)


def build_shadow_embedding_sync(
    *,
    text_to_embed: str,
    space: EmbeddingSpaceRegistryEntry,
    source_embedding: Sequence[float] | None = None,
    source_contract: EmbeddingSpaceContract | None = None,
) -> list[float]:
    if (
        source_embedding
        and source_contract is not None
        and source_contract.fingerprint == space.space_fingerprint
        and len(source_embedding) == space.dimensions
    ):
        return list(source_embedding)

    backend = build_embedding_backend_for_provider_model(
        provider=space.provider,
        model_name=space.model,
        dimensions=space.dimensions,
    )
    if backend is None:
        raise RuntimeError(
            f"Khong tao duoc embedding backend cho shadow space {space.space_fingerprint}."
        )
    results = backend.embed_documents([text_to_embed])
    if not results or not results[0]:
        raise RuntimeError(
            f"Shadow embedding backend {space.space_fingerprint} khong tra ve vector hop le."
        )
    return list(results[0])


async def build_shadow_embedding_async(
    *,
    text_to_embed: str,
    space: EmbeddingSpaceRegistryEntry,
    source_embedding: Sequence[float] | None = None,
    source_contract: EmbeddingSpaceContract | None = None,
) -> list[float]:
    if (
        source_embedding
        and source_contract is not None
        and source_contract.fingerprint == space.space_fingerprint
        and len(source_embedding) == space.dimensions
    ):
        return list(source_embedding)

    backend = build_embedding_backend_for_provider_model(
        provider=space.provider,
        model_name=space.model,
        dimensions=space.dimensions,
    )
    if backend is None:
        raise RuntimeError(
            f"Khong tao duoc embedding backend cho shadow space {space.space_fingerprint}."
        )
    results = await backend.aembed_documents([text_to_embed])
    if not results or not results[0]:
        raise RuntimeError(
            f"Shadow embedding backend {space.space_fingerprint} khong tra ve vector hop le."
        )
    return list(results[0])


def build_shadow_metadata(
    metadata: dict[str, Any] | None,
    *,
    contract: EmbeddingSpaceContract | EmbeddingSpaceRegistryEntry,
) -> str:
    payload = stamp_embedding_metadata(
        metadata or {},
        model_name=contract.model,
        dimensions=contract.dimensions,
    )
    return json.dumps(payload, ensure_ascii=False)


def filter_shadow_spaces(
    spaces: Iterable[EmbeddingSpaceRegistryEntry],
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    return tuple(space for space in spaces if space.storage_kind == "shadow")
