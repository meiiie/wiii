from __future__ import annotations

from types import SimpleNamespace

from app.services.embedding_space_runtime_service import (
    build_embedding_migration_previews,
    build_embedding_space_status_snapshot,
)


def test_build_embedding_space_status_snapshot_exposes_policy_and_active(monkeypatch):
    contract = SimpleNamespace(
        provider="ollama",
        model="embeddinggemma",
        dimensions=768,
        fingerprint="ollama:embeddinggemma:768",
        label="embeddinggemma [ollama, 768d]",
    )
    audit = SimpleNamespace(
        audit_available=True,
        total_embedded_rows=5,
        tables=(
            SimpleNamespace(
                table_name="semantic_memories",
                embedded_row_count=3,
                tracked_row_count=3,
                untracked_row_count=0,
                fingerprints={"ollama:embeddinggemma:768": 3},
            ),
            SimpleNamespace(
                table_name="knowledge_embeddings",
                embedded_row_count=2,
                tracked_row_count=2,
                untracked_row_count=0,
                fingerprints={"ollama:embeddinggemma:768": 2},
            ),
        ),
        warnings=("all good",),
        error=None,
    )
    monkeypatch.setattr(
        "app.services.embedding_space_runtime_service.get_runtime_embedding_space_contract",
        lambda: contract,
    )
    monkeypatch.setattr(
        "app.services.embedding_space_runtime_service.get_active_embedding_space_contract",
        lambda: contract,
    )
    monkeypatch.setattr(
        "app.services.embedding_space_runtime_service.inspect_embedding_space_usage",
        lambda **_kwargs: audit,
    )

    snapshot = build_embedding_space_status_snapshot()

    assert snapshot.audit_available is True
    assert snapshot.active_matches_policy is True
    assert snapshot.total_embedded_rows == 5
    assert snapshot.total_tracked_rows == 5
    assert snapshot.total_untracked_rows == 0
    assert snapshot.policy_contract is not None
    assert snapshot.policy_contract.fingerprint == "ollama:embeddinggemma:768"
    assert snapshot.tables[0].table_name == "semantic_memories"


def test_build_embedding_migration_previews_marks_same_space_and_reembed(monkeypatch):
    def _plan(*, target_model, target_dimensions=None, tables=None):
        if target_model == "embeddinggemma":
            return SimpleNamespace(
                same_space=True,
                transition_allowed=True,
                maintenance_required=False,
                target_backend_constructible=True,
                total_embedded_rows=7,
                tables=(),
                warnings=(),
                recommended_steps=("noop",),
                detail=None,
            )
        return SimpleNamespace(
            same_space=False,
            transition_allowed=False,
            maintenance_required=True,
            target_backend_constructible=False,
            total_embedded_rows=7,
            tables=(SimpleNamespace(table_name="semantic_memories", candidate_rows=7),),
            warnings=("needs migration",),
            recommended_steps=("maintenance",),
            detail="blocked",
        )

    monkeypatch.setattr(
        "app.services.embedding_space_runtime_service.plan_embedding_space_migration",
        _plan,
    )

    previews = build_embedding_migration_previews(
        candidate_models=["embeddinggemma", "text-embedding-3-small"],
    )

    assert previews[0].target_model == "embeddinggemma"
    assert previews[0].same_space is True
    assert previews[0].requires_reembed is False
    assert previews[0].target_backend_constructible is True
    assert previews[1].target_model == "text-embedding-3-small"
    assert previews[1].allowed is False
    assert previews[1].requires_reembed is True
    assert previews[1].maintenance_required is True
    assert previews[1].embedded_row_count == 7
