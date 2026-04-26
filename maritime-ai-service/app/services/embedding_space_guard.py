"""Embedding space contracts and runtime guardrails for shared vector indexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Mapping

from sqlalchemy import text

from app.core.database import get_shared_session_factory
from app.core.config import settings
from app.engine.model_catalog import get_embedding_dimensions, get_embedding_provider

logger = logging.getLogger(__name__)

EMBEDDING_SPACE_METADATA_KEY = "_embedding_space"
_LEGACY_FINGERPRINT_KEY = "embedding_space_fingerprint"
_TRACKED_FINGERPRINT_SQL = (
    "COALESCE("
    "metadata -> '_embedding_space' ->> 'fingerprint', "
    "metadata ->> 'embedding_space_fingerprint'"
    ")"
)


@dataclass(frozen=True)
class EmbeddingSpaceContract:
    provider: str
    model: str
    dimensions: int
    fingerprint: str
    label: str

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingSpaceTableAudit:
    table_name: str
    embedded_row_count: int
    tracked_row_count: int
    untracked_row_count: int
    fingerprints: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingSpaceAudit:
    audit_available: bool
    current_contract: EmbeddingSpaceContract | None
    tables: tuple[EmbeddingSpaceTableAudit, ...]
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def total_embedded_rows(self) -> int:
        return sum(item.embedded_row_count for item in self.tables)


@dataclass(frozen=True)
class EmbeddingSpaceTransitionValidation:
    allowed: bool
    current_contract: EmbeddingSpaceContract | None
    target_contract: EmbeddingSpaceContract | None
    same_space: bool = False
    requires_reembed: bool = False
    blocking_tables: tuple[str, ...] = ()
    mixed_tables: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    detail: str | None = None
    audit: EmbeddingSpaceAudit | None = None


def _normalize_dimensions(model_name: str | None, dimensions: int | None) -> int:
    if isinstance(dimensions, int) and dimensions > 0:
        return dimensions
    return get_embedding_dimensions(model_name)


def build_embedding_space_contract(
    model_name: str | None,
    dimensions: int | None = None,
) -> EmbeddingSpaceContract | None:
    if not isinstance(model_name, str):
        return None
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return None
    resolved_dimensions = _normalize_dimensions(normalized_model, dimensions)
    provider = get_embedding_provider(normalized_model)
    fingerprint = f"{provider}:{normalized_model}:{resolved_dimensions}".lower()
    label = f"{normalized_model} [{provider}, {resolved_dimensions}d]"
    return EmbeddingSpaceContract(
        provider=provider,
        model=normalized_model,
        dimensions=resolved_dimensions,
        fingerprint=fingerprint,
        label=label,
    )


def get_runtime_embedding_space_contract() -> EmbeddingSpaceContract | None:
    return build_embedding_space_contract(
        getattr(settings, "embedding_model", None),
        getattr(settings, "embedding_dimensions", None),
    )


def get_active_embedding_space_contract() -> EmbeddingSpaceContract | None:
    try:
        from app.engine.embedding_runtime import get_embedding_backend

        backend = get_embedding_backend()
        if backend and backend.is_available() and backend.model_name:
            return build_embedding_space_contract(
                backend.model_name,
                getattr(backend, "dimensions", None),
            )
    except Exception as exc:
        logger.debug("Active embedding space contract unavailable: %s", exc)
    return get_runtime_embedding_space_contract()


def preserve_embedding_space_metadata(
    metadata: Mapping[str, Any] | None,
    existing_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    current_payload = dict(existing_metadata or {})
    current_space = current_payload.get(EMBEDDING_SPACE_METADATA_KEY)
    if current_space is not None:
        payload[EMBEDDING_SPACE_METADATA_KEY] = current_space
    current_fingerprint = current_payload.get(_LEGACY_FINGERPRINT_KEY)
    if current_fingerprint:
        payload[_LEGACY_FINGERPRINT_KEY] = current_fingerprint
    return payload


def stamp_embedding_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    model_name: str | None = None,
    dimensions: int | None = None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    if model_name is None and dimensions is None:
        contract = get_active_embedding_space_contract()
    else:
        contract = build_embedding_space_contract(
            model_name or getattr(settings, "embedding_model", None),
            dimensions if dimensions is not None else getattr(settings, "embedding_dimensions", None),
        )
    if contract is None:
        return payload
    payload[EMBEDDING_SPACE_METADATA_KEY] = contract.to_metadata()
    payload[_LEGACY_FINGERPRINT_KEY] = contract.fingerprint
    return payload


def _fetch_table_audit(session, table_name: str) -> EmbeddingSpaceTableAudit:
    embedded_row_count = int(
        session.execute(
            text(f"SELECT COUNT(*) FROM {table_name} WHERE embedding IS NOT NULL")
        ).scalar()
        or 0
    )
    tracked_row_count = int(
        session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE embedding IS NOT NULL
                  AND {_TRACKED_FINGERPRINT_SQL} IS NOT NULL
                """
            )
        ).scalar()
        or 0
    )
    fingerprint_rows = session.execute(
        text(
            f"""
            SELECT {_TRACKED_FINGERPRINT_SQL} AS fingerprint, COUNT(*) AS count
            FROM {table_name}
            WHERE embedding IS NOT NULL
              AND {_TRACKED_FINGERPRINT_SQL} IS NOT NULL
            GROUP BY 1
            ORDER BY COUNT(*) DESC, 1
            """
        )
    ).fetchall()
    fingerprints = {
        str(row[0]): int(row[1])
        for row in fingerprint_rows
        if row[0]
    }
    return EmbeddingSpaceTableAudit(
        table_name=table_name,
        embedded_row_count=embedded_row_count,
        tracked_row_count=tracked_row_count,
        untracked_row_count=max(0, embedded_row_count - tracked_row_count),
        fingerprints=fingerprints,
    )


def inspect_embedding_space_usage(
    *,
    current_model: str | None = None,
    current_dimensions: int | None = None,
) -> EmbeddingSpaceAudit:
    current_contract = build_embedding_space_contract(
        current_model or getattr(settings, "embedding_model", None),
        current_dimensions
        if current_dimensions is not None
        else getattr(settings, "embedding_dimensions", None),
    )
    try:
        session_factory = get_shared_session_factory()
        with session_factory() as session:
            tables = (
                _fetch_table_audit(session, "semantic_memories"),
                _fetch_table_audit(session, "knowledge_embeddings"),
            )
    except Exception as exc:
        logger.warning("Embedding space audit unavailable: %s", exc)
        return EmbeddingSpaceAudit(
            audit_available=False,
            current_contract=current_contract,
            tables=(),
            warnings=("Khong the kiem tra vector-space hien tai tu database.",),
            error=str(exc),
        )

    warnings: list[str] = []
    for table in tables:
        if table.embedded_row_count <= 0:
            continue
        if len(table.fingerprints) > 1:
            warnings.append(
                f"{table.table_name} dang chua nhieu vector-space: "
                + ", ".join(f"{fp} ({count})" for fp, count in table.fingerprints.items())
            )
        if table.untracked_row_count > 0:
            warnings.append(
                f"{table.table_name} con {table.untracked_row_count} row embedding cu "
                "chua co fingerprint metadata."
            )
        if (
            current_contract is not None
            and table.fingerprints
            and current_contract.fingerprint not in table.fingerprints
        ):
            warnings.append(
                f"{table.table_name} khong khop runtime embedding hien tai "
                f"({current_contract.fingerprint})."
            )

    return EmbeddingSpaceAudit(
        audit_available=True,
        current_contract=current_contract,
        tables=tables,
        warnings=tuple(warnings),
    )


def build_runtime_embedding_space_warnings(
    *,
    current_model: str | None = None,
    current_dimensions: int | None = None,
) -> list[str]:
    audit = inspect_embedding_space_usage(
        current_model=current_model,
        current_dimensions=current_dimensions,
    )
    return list(audit.warnings)


def validate_embedding_space_transition_with_audit(
    *,
    current_contract: EmbeddingSpaceContract | None,
    target_contract: EmbeddingSpaceContract | None,
    audit: EmbeddingSpaceAudit | None,
) -> EmbeddingSpaceTransitionValidation:
    if current_contract is None or target_contract is None:
        return EmbeddingSpaceTransitionValidation(
            allowed=True,
            current_contract=current_contract,
            target_contract=target_contract,
            audit=audit,
        )

    resolved_audit = audit or inspect_embedding_space_usage(
        current_model=current_contract.model,
        current_dimensions=current_contract.dimensions,
    )
    if current_contract.fingerprint == target_contract.fingerprint:
        return EmbeddingSpaceTransitionValidation(
            allowed=True,
            current_contract=current_contract,
            target_contract=target_contract,
            same_space=True,
            warnings=resolved_audit.warnings,
            audit=resolved_audit,
        )

    if not resolved_audit.audit_available:
        return EmbeddingSpaceTransitionValidation(
            allowed=True,
            current_contract=current_contract,
            target_contract=target_contract,
            requires_reembed=False,
            warnings=resolved_audit.warnings,
            detail=None,
            audit=resolved_audit,
        )

    blocking_tables: list[str] = []
    mixed_tables: list[str] = []
    for table in resolved_audit.tables:
        if table.embedded_row_count <= 0:
            continue
        if len(table.fingerprints) > 1:
            mixed_tables.append(table.table_name)
        blocking_tables.append(
            f"{table.table_name}={table.embedded_row_count}"
            + (
                f" (tracked={table.tracked_row_count}, untracked={table.untracked_row_count})"
                if table.tracked_row_count or table.untracked_row_count
                else ""
            )
        )

    if not blocking_tables:
        return EmbeddingSpaceTransitionValidation(
            allowed=True,
            current_contract=current_contract,
            target_contract=target_contract,
            requires_reembed=False,
            warnings=resolved_audit.warnings,
            audit=resolved_audit,
        )

    detail = (
        "Khong the doi embedding model in-place tu "
        f"{current_contract.label} sang {target_contract.label} khi index hien tai van co vector song: "
        + ", ".join(blocking_tables)
        + ". Hay re-embed/purge truoc, hoac giu nguyen cung vector-space."
    )
    if mixed_tables:
        detail += " Index hien tai da co dau hieu bi tron nhieu vector-space: " + ", ".join(mixed_tables) + "."

    return EmbeddingSpaceTransitionValidation(
        allowed=False,
        current_contract=current_contract,
        target_contract=target_contract,
        requires_reembed=True,
        blocking_tables=tuple(blocking_tables),
        mixed_tables=tuple(mixed_tables),
        warnings=resolved_audit.warnings,
        detail=detail,
        audit=resolved_audit,
    )


def validate_embedding_space_transition(
    *,
    current_model: str | None,
    current_dimensions: int | None,
    target_model: str | None,
    target_dimensions: int | None,
) -> EmbeddingSpaceTransitionValidation:
    current_contract = build_embedding_space_contract(current_model, current_dimensions)
    target_contract = build_embedding_space_contract(target_model, target_dimensions)
    audit = (
        inspect_embedding_space_usage(
            current_model=current_contract.model,
            current_dimensions=current_contract.dimensions,
        )
        if current_contract is not None
        else None
    )
    return validate_embedding_space_transition_with_audit(
        current_contract=current_contract,
        target_contract=target_contract,
        audit=audit,
    )
