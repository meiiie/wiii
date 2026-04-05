"""Registry helpers for active/shadow embedding spaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import time
from typing import Any, Iterable, Literal

from sqlalchemy import text

from app.core.database import get_shared_session_factory
from app.services.embedding_space_guard import (
    EmbeddingSpaceContract,
    get_active_embedding_space_contract,
    get_runtime_embedding_space_contract,
)

logger = logging.getLogger(__name__)

EmbeddingEntityType = Literal["semantic_memories", "knowledge_embeddings"]
EmbeddingStorageKind = Literal["inline", "shadow"]
EmbeddingRegistryState = Literal["active", "shadow", "retired"]

_SUPPORTED_ENTITY_TYPES: tuple[EmbeddingEntityType, ...] = (
    "semantic_memories",
    "knowledge_embeddings",
)
_CACHE_TTL_SECONDS = 10.0


@dataclass(frozen=True)
class EmbeddingSpaceRegistryEntry:
    entity_type: EmbeddingEntityType
    space_fingerprint: str
    provider: str
    model: str
    dimensions: int
    storage_kind: EmbeddingStorageKind
    state: EmbeddingRegistryState
    reads_enabled: bool
    writes_enabled: bool
    index_ready: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _CacheEntry:
    created_at: float
    entries: dict[EmbeddingEntityType, tuple[EmbeddingSpaceRegistryEntry, ...]]


_registry_cache: _CacheEntry | None = None


def invalidate_embedding_space_registry_cache() -> None:
    global _registry_cache
    _registry_cache = None


def _normalize_entity_type(entity_type: str) -> EmbeddingEntityType:
    normalized = (entity_type or "").strip().lower()
    if normalized not in _SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"Unsupported embedding registry entity_type: {entity_type}")
    return normalized  # type: ignore[return-value]


def _contract_to_inline_entry(
    entity_type: EmbeddingEntityType,
    contract: EmbeddingSpaceContract | None,
) -> EmbeddingSpaceRegistryEntry | None:
    if contract is None:
        return None
    return EmbeddingSpaceRegistryEntry(
        entity_type=entity_type,
        space_fingerprint=contract.fingerprint,
        provider=contract.provider,
        model=contract.model,
        dimensions=contract.dimensions,
        storage_kind="inline",
        state="active",
        reads_enabled=True,
        writes_enabled=True,
        index_ready=True,
        metadata={"source": "runtime_fallback"},
    )


def _fetch_registry_entries_uncached() -> dict[EmbeddingEntityType, tuple[EmbeddingSpaceRegistryEntry, ...]]:
    results: dict[EmbeddingEntityType, list[EmbeddingSpaceRegistryEntry]] = {
        "semantic_memories": [],
        "knowledge_embeddings": [],
    }
    try:
        session_factory = get_shared_session_factory()
        with session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                        entity_type,
                        space_fingerprint,
                        provider,
                        model,
                        dimensions,
                        storage_kind,
                        state,
                        reads_enabled,
                        writes_enabled,
                        index_ready,
                        metadata
                    FROM embedding_space_registry
                    ORDER BY
                        entity_type ASC,
                        CASE state
                            WHEN 'active' THEN 0
                            WHEN 'shadow' THEN 1
                            ELSE 2
                        END ASC,
                        CASE storage_kind
                            WHEN 'inline' THEN 0
                            ELSE 1
                        END ASC,
                        model ASC
                    """
                )
            ).fetchall()
    except Exception as exc:
        logger.debug("Embedding registry table unavailable, falling back to runtime contract: %s", exc)
        rows = []

    for row in rows:
        entity_type = _normalize_entity_type(str(row.entity_type))
        results[entity_type].append(
            EmbeddingSpaceRegistryEntry(
                entity_type=entity_type,
                space_fingerprint=str(row.space_fingerprint),
                provider=str(row.provider),
                model=str(row.model),
                dimensions=int(row.dimensions),
                storage_kind=str(row.storage_kind),  # type: ignore[arg-type]
                state=str(row.state),  # type: ignore[arg-type]
                reads_enabled=bool(row.reads_enabled),
                writes_enabled=bool(row.writes_enabled),
                index_ready=bool(row.index_ready),
                metadata=dict(row.metadata or {}),
            )
        )

    runtime_contract = get_active_embedding_space_contract() or get_runtime_embedding_space_contract()
    for entity_type in _SUPPORTED_ENTITY_TYPES:
        if results[entity_type]:
            continue
        fallback_entry = _contract_to_inline_entry(entity_type, runtime_contract)
        if fallback_entry is not None:
            results[entity_type].append(fallback_entry)

    return {
        entity_type: tuple(entries)
        for entity_type, entries in results.items()
    }


def _get_registry_snapshot(*, force_refresh: bool = False) -> dict[EmbeddingEntityType, tuple[EmbeddingSpaceRegistryEntry, ...]]:
    global _registry_cache
    now = time.monotonic()
    if (
        not force_refresh
        and _registry_cache is not None
        and now - _registry_cache.created_at < _CACHE_TTL_SECONDS
    ):
        return _registry_cache.entries

    entries = _fetch_registry_entries_uncached()
    _registry_cache = _CacheEntry(created_at=now, entries=entries)
    return entries


def get_embedding_space_registry_entries(
    entity_type: EmbeddingEntityType,
    *,
    force_refresh: bool = False,
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    normalized = _normalize_entity_type(entity_type)
    return _get_registry_snapshot(force_refresh=force_refresh).get(normalized, ())


def get_active_embedding_read_space(
    entity_type: EmbeddingEntityType,
    *,
    force_refresh: bool = False,
) -> EmbeddingSpaceRegistryEntry | None:
    for entry in get_embedding_space_registry_entries(entity_type, force_refresh=force_refresh):
        if entry.state == "active" and entry.reads_enabled:
            return entry
    entries = get_embedding_space_registry_entries(entity_type, force_refresh=force_refresh)
    return entries[0] if entries else None


def get_embedding_write_spaces(
    entity_type: EmbeddingEntityType,
    *,
    force_refresh: bool = False,
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    entries = tuple(
        entry
        for entry in get_embedding_space_registry_entries(entity_type, force_refresh=force_refresh)
        if entry.writes_enabled
    )
    if entries:
        return entries
    fallback = get_active_embedding_read_space(entity_type, force_refresh=force_refresh)
    return (fallback,) if fallback is not None else ()


def upsert_embedding_space_registry_entry(
    *,
    entity_type: EmbeddingEntityType,
    contract: EmbeddingSpaceContract,
    storage_kind: EmbeddingStorageKind,
    state: EmbeddingRegistryState,
    reads_enabled: bool,
    writes_enabled: bool,
    index_ready: bool,
    metadata: dict[str, Any] | None = None,
) -> EmbeddingSpaceRegistryEntry:
    normalized = _normalize_entity_type(entity_type)
    session_factory = get_shared_session_factory()
    payload = dict(metadata or {})
    with session_factory() as session:
        session.execute(
            text(
                """
                INSERT INTO embedding_space_registry (
                    entity_type,
                    space_fingerprint,
                    provider,
                    model,
                    dimensions,
                    storage_kind,
                    state,
                    reads_enabled,
                    writes_enabled,
                    index_ready,
                    metadata,
                    updated_at
                )
                VALUES (
                    :entity_type,
                    :space_fingerprint,
                    :provider,
                    :model,
                    :dimensions,
                    :storage_kind,
                    :state,
                    :reads_enabled,
                    :writes_enabled,
                    :index_ready,
                    CAST(:metadata AS jsonb),
                    NOW()
                )
                ON CONFLICT (entity_type, space_fingerprint)
                DO UPDATE SET
                    provider = EXCLUDED.provider,
                    model = EXCLUDED.model,
                    dimensions = EXCLUDED.dimensions,
                    storage_kind = EXCLUDED.storage_kind,
                    state = EXCLUDED.state,
                    reads_enabled = EXCLUDED.reads_enabled,
                    writes_enabled = EXCLUDED.writes_enabled,
                    index_ready = EXCLUDED.index_ready,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """
            ),
            {
                "entity_type": normalized,
                "space_fingerprint": contract.fingerprint,
                "provider": contract.provider,
                "model": contract.model,
                "dimensions": contract.dimensions,
                "storage_kind": storage_kind,
                "state": state,
                "reads_enabled": reads_enabled,
                "writes_enabled": writes_enabled,
                "index_ready": index_ready,
                "metadata": json.dumps(payload, ensure_ascii=False),
            },
        )
        session.commit()

    invalidate_embedding_space_registry_cache()
    return EmbeddingSpaceRegistryEntry(
        entity_type=normalized,
        space_fingerprint=contract.fingerprint,
        provider=contract.provider,
        model=contract.model,
        dimensions=contract.dimensions,
        storage_kind=storage_kind,
        state=state,
        reads_enabled=reads_enabled,
        writes_enabled=writes_enabled,
        index_ready=index_ready,
        metadata=payload,
    )


def seed_inline_embedding_space_registry(
    *,
    entity_types: Iterable[EmbeddingEntityType] | None = None,
    contract: EmbeddingSpaceContract | None = None,
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    resolved_contract = contract or get_active_embedding_space_contract() or get_runtime_embedding_space_contract()
    if resolved_contract is None:
        return ()
    targets = tuple(_normalize_entity_type(item) for item in (entity_types or _SUPPORTED_ENTITY_TYPES))
    created: list[EmbeddingSpaceRegistryEntry] = []
    for entity_type in targets:
        existing = get_embedding_space_registry_entries(entity_type)
        if existing:
            continue
        created.append(
            upsert_embedding_space_registry_entry(
                entity_type=entity_type,
                contract=resolved_contract,
                storage_kind="inline",
                state="active",
                reads_enabled=True,
                writes_enabled=True,
                index_ready=True,
                metadata={"seeded": True, "seed_reason": "inline_default"},
            )
        )
    return tuple(created)


def prepare_shadow_embedding_space(
    *,
    entity_types: Iterable[EmbeddingEntityType] | None = None,
    target_contract: EmbeddingSpaceContract,
    index_ready: bool = False,
    metadata: dict[str, Any] | None = None,
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    seed_inline_embedding_space_registry()
    targets = tuple(_normalize_entity_type(item) for item in (entity_types or _SUPPORTED_ENTITY_TYPES))
    prepared: list[EmbeddingSpaceRegistryEntry] = []
    for entity_type in targets:
        prepared.append(
            upsert_embedding_space_registry_entry(
                entity_type=entity_type,
                contract=target_contract,
                storage_kind="shadow",
                state="shadow",
                reads_enabled=False,
                writes_enabled=True,
                index_ready=index_ready,
                metadata={"prepared": True, **dict(metadata or {})},
            )
        )
    return tuple(prepared)


def promote_shadow_embedding_space(
    *,
    entity_types: Iterable[EmbeddingEntityType] | None = None,
    target_contract: EmbeddingSpaceContract,
) -> tuple[EmbeddingSpaceRegistryEntry, ...]:
    targets = tuple(_normalize_entity_type(item) for item in (entity_types or _SUPPORTED_ENTITY_TYPES))
    session_factory = get_shared_session_factory()
    promoted: list[EmbeddingSpaceRegistryEntry] = []
    with session_factory() as session:
        for entity_type in targets:
            session.execute(
                text(
                    """
                    UPDATE embedding_space_registry
                    SET state = CASE
                            WHEN state = 'active' THEN 'retired'
                            ELSE state
                        END,
                        reads_enabled = FALSE,
                        writes_enabled = FALSE,
                        updated_at = NOW()
                    WHERE entity_type = :entity_type
                    """
                ),
                {"entity_type": entity_type},
            )
            session.execute(
                text(
                    """
                    UPDATE embedding_space_registry
                    SET state = 'active',
                        reads_enabled = TRUE,
                        writes_enabled = TRUE,
                        updated_at = NOW()
                    WHERE entity_type = :entity_type
                      AND space_fingerprint = :space_fingerprint
                    """
                ),
                {
                    "entity_type": entity_type,
                    "space_fingerprint": target_contract.fingerprint,
                },
            )
        session.commit()

    invalidate_embedding_space_registry_cache()
    for entity_type in targets:
        active = get_active_embedding_read_space(entity_type, force_refresh=True)
        if active is not None:
            promoted.append(active)
    return tuple(promoted)
