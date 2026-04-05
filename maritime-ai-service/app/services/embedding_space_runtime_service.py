"""Admin-facing runtime summaries for embedding-space health and migration safety."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from app.engine.model_catalog import EMBEDDING_MODELS, get_embedding_model_metadata
from app.services.embedding_space_guard import (
    EmbeddingSpaceAudit,
    EmbeddingSpaceContract,
    EmbeddingSpaceTableAudit,
    get_active_embedding_space_contract,
    get_runtime_embedding_space_contract,
    inspect_embedding_space_usage,
)
from app.services.embedding_space_migration_service import plan_embedding_space_migration


@dataclass(frozen=True)
class EmbeddingSpaceContractStatus:
    provider: str
    model: str
    dimensions: int
    fingerprint: str
    label: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingSpaceTableStatus:
    table_name: str
    embedded_row_count: int
    tracked_row_count: int
    untracked_row_count: int
    fingerprints: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingSpaceStatusSnapshot:
    audit_available: bool
    policy_contract: EmbeddingSpaceContractStatus | None
    active_contract: EmbeddingSpaceContractStatus | None
    active_matches_policy: bool | None
    total_embedded_rows: int
    total_tracked_rows: int
    total_untracked_rows: int
    tables: tuple[EmbeddingSpaceTableStatus, ...]
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["policy_contract"] = self.policy_contract.to_dict() if self.policy_contract else None
        payload["active_contract"] = self.active_contract.to_dict() if self.active_contract else None
        payload["tables"] = [item.to_dict() for item in self.tables]
        return payload


@dataclass(frozen=True)
class EmbeddingMigrationPreview:
    target_model: str
    target_provider: str
    target_dimensions: int
    target_label: str
    target_status: str
    same_space: bool
    allowed: bool
    requires_reembed: bool
    target_backend_constructible: bool
    maintenance_required: bool
    embedded_row_count: int
    blocking_tables: tuple[str, ...] = ()
    mixed_tables: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_steps: tuple[str, ...] = ()
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _serialize_contract(contract: EmbeddingSpaceContract | None) -> EmbeddingSpaceContractStatus | None:
    if contract is None:
        return None
    return EmbeddingSpaceContractStatus(
        provider=contract.provider,
        model=contract.model,
        dimensions=contract.dimensions,
        fingerprint=contract.fingerprint,
        label=contract.label,
    )


def _serialize_table(table: EmbeddingSpaceTableAudit) -> EmbeddingSpaceTableStatus:
    return EmbeddingSpaceTableStatus(
        table_name=table.table_name,
        embedded_row_count=table.embedded_row_count,
        tracked_row_count=table.tracked_row_count,
        untracked_row_count=table.untracked_row_count,
        fingerprints=dict(table.fingerprints),
    )


def _ordered_candidate_models(candidate_models: Iterable[str] | None = None) -> list[str]:
    names = list(candidate_models) if candidate_models is not None else list(EMBEDDING_MODELS.keys())
    deduped = {name.strip(): None for name in names if isinstance(name, str) and name.strip()}
    metadata_items = []
    status_order = {"stable": 0, "current": 1, "available": 2, "preview": 3}
    for model_name in deduped.keys():
        metadata = get_embedding_model_metadata(model_name)
        if metadata is None:
            continue
        metadata_items.append(
            (
                status_order.get(metadata.status, 9),
                0 if metadata.production_default else 1,
                metadata.provider,
                metadata.model_name,
            )
        )
    metadata_items.sort()
    return [item[3] for item in metadata_items]


def build_embedding_space_status_snapshot() -> EmbeddingSpaceStatusSnapshot:
    policy_contract = get_runtime_embedding_space_contract()
    active_contract = get_active_embedding_space_contract()
    audit_contract = active_contract or policy_contract
    audit = inspect_embedding_space_usage(
        current_model=audit_contract.model if audit_contract else None,
        current_dimensions=audit_contract.dimensions if audit_contract else None,
    )
    active_matches_policy = None
    if policy_contract is not None and active_contract is not None:
        active_matches_policy = active_contract.fingerprint == policy_contract.fingerprint
    elif policy_contract is None and active_contract is None:
        active_matches_policy = True

    tables = tuple(_serialize_table(table) for table in audit.tables)
    return EmbeddingSpaceStatusSnapshot(
        audit_available=audit.audit_available,
        policy_contract=_serialize_contract(policy_contract),
        active_contract=_serialize_contract(active_contract),
        active_matches_policy=active_matches_policy,
        total_embedded_rows=audit.total_embedded_rows,
        total_tracked_rows=sum(item.tracked_row_count for item in audit.tables),
        total_untracked_rows=sum(item.untracked_row_count for item in audit.tables),
        tables=tables,
        warnings=audit.warnings,
        error=audit.error,
    )


def build_embedding_migration_previews(
    *,
    candidate_models: Iterable[str] | None = None,
) -> list[EmbeddingMigrationPreview]:
    previews: list[EmbeddingMigrationPreview] = []
    for model_name in _ordered_candidate_models(candidate_models):
        metadata = get_embedding_model_metadata(model_name)
        if metadata is None:
            continue
        plan = plan_embedding_space_migration(
            target_model=metadata.model_name,
            target_dimensions=metadata.dimensions,
        )

        previews.append(
            EmbeddingMigrationPreview(
                target_model=metadata.model_name,
                target_provider=metadata.provider,
                target_dimensions=metadata.dimensions,
                target_label=metadata.display_name,
                target_status=metadata.status,
                same_space=plan.same_space,
                allowed=plan.transition_allowed,
                requires_reembed=plan.maintenance_required or (not plan.same_space and not plan.transition_allowed),
                target_backend_constructible=plan.target_backend_constructible,
                maintenance_required=plan.maintenance_required,
                embedded_row_count=plan.total_embedded_rows,
                blocking_tables=tuple(
                    f"{item.table_name}={item.candidate_rows}"
                    for item in plan.tables
                    if item.candidate_rows > 0
                ),
                mixed_tables=(),
                warnings=plan.warnings,
                recommended_steps=plan.recommended_steps,
                detail=plan.detail,
            )
        )

    previews.sort(
        key=lambda item: (
            0 if item.same_space else 1,
            0 if item.allowed else 1,
            item.target_provider,
            item.target_model,
        )
    )
    return previews
