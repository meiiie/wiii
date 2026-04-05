from __future__ import annotations

import pytest

from app.services.embedding_space_guard import (
    EMBEDDING_SPACE_METADATA_KEY,
    build_embedding_space_contract,
    preserve_embedding_space_metadata,
    inspect_embedding_space_usage,
    stamp_embedding_metadata,
    validate_embedding_space_transition,
)


class _FakeResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def fetchall(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, plan):
        self._plan = list(plan)

    def execute(self, *_args, **_kwargs):
        if not self._plan:
            raise AssertionError("Unexpected execute() call")
        item = self._plan.pop(0)
        return _FakeResult(scalar=item.get("scalar"), rows=item.get("rows"))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _session_factory(plan):
    def _factory():
        return _FakeSession(plan)

    return _factory


def test_build_embedding_space_contract_uses_model_and_dimensions():
    contract = build_embedding_space_contract("embeddinggemma", 768)
    assert contract is not None
    assert contract.provider == "ollama"
    assert contract.fingerprint == "ollama:embeddinggemma:768"


def test_stamp_embedding_metadata_adds_contract_marker():
    payload = stamp_embedding_metadata({"domain_id": "maritime"}, model_name="embeddinggemma", dimensions=768)
    assert payload["domain_id"] == "maritime"
    assert payload["embedding_space_fingerprint"] == "ollama:embeddinggemma:768"
    assert payload[EMBEDDING_SPACE_METADATA_KEY]["model"] == "embeddinggemma"


def test_preserve_embedding_space_metadata_keeps_existing_contract():
    payload = preserve_embedding_space_metadata(
        {"domain_id": "maritime"},
        {
            EMBEDDING_SPACE_METADATA_KEY: {"fingerprint": "ollama:embeddinggemma:768"},
            "embedding_space_fingerprint": "ollama:embeddinggemma:768",
        },
    )

    assert payload["domain_id"] == "maritime"
    assert payload["embedding_space_fingerprint"] == "ollama:embeddinggemma:768"
    assert payload[EMBEDDING_SPACE_METADATA_KEY]["fingerprint"] == "ollama:embeddinggemma:768"


def test_inspect_embedding_space_usage_reports_untracked_rows(monkeypatch):
    plan = [
        {"scalar": 3},
        {"scalar": 1},
        {"rows": [("ollama:embeddinggemma:768", 1)]},
        {"scalar": 2},
        {"scalar": 2},
        {"rows": [("ollama:embeddinggemma:768", 2)]},
    ]
    monkeypatch.setattr(
        "app.services.embedding_space_guard.get_shared_session_factory",
        lambda: _session_factory(plan),
    )

    audit = inspect_embedding_space_usage(current_model="embeddinggemma", current_dimensions=768)
    assert audit.audit_available is True
    assert audit.tables[0].table_name == "semantic_memories"
    assert audit.tables[0].untracked_row_count == 2
    assert any("semantic_memories" in warning for warning in audit.warnings)


def test_validate_embedding_space_transition_blocks_when_live_vectors_exist(monkeypatch):
    plan = [
        {"scalar": 2},
        {"scalar": 2},
        {"rows": [("ollama:embeddinggemma:768", 2)]},
        {"scalar": 1},
        {"scalar": 1},
        {"rows": [("ollama:embeddinggemma:768", 1)]},
    ]
    monkeypatch.setattr(
        "app.services.embedding_space_guard.get_shared_session_factory",
        lambda: _session_factory(plan),
    )

    result = validate_embedding_space_transition(
        current_model="embeddinggemma",
        current_dimensions=768,
        target_model="text-embedding-3-small",
        target_dimensions=768,
    )
    assert result.allowed is False
    assert result.same_space is False
    assert result.requires_reembed is True
    assert result.blocking_tables
    assert result.detail is not None
    assert "Khong the doi embedding model in-place" in result.detail


def test_validate_embedding_space_transition_allows_when_space_unchanged(monkeypatch):
    plan = [
        {"scalar": 2},
        {"scalar": 2},
        {"rows": [("ollama:embeddinggemma:768", 2)]},
        {"scalar": 0},
        {"scalar": 0},
        {"rows": []},
    ]
    monkeypatch.setattr(
        "app.services.embedding_space_guard.get_shared_session_factory",
        lambda: _session_factory(plan),
    )

    result = validate_embedding_space_transition(
        current_model="embeddinggemma",
        current_dimensions=768,
        target_model="embeddinggemma",
        target_dimensions=768,
    )
    assert result.allowed is True
    assert result.same_space is True
    assert result.requires_reembed is False


def test_validate_embedding_space_transition_fails_open_when_audit_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.embedding_space_guard.get_shared_session_factory",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    result = validate_embedding_space_transition(
        current_model="embeddinggemma",
        current_dimensions=768,
        target_model="text-embedding-3-small",
        target_dimensions=768,
    )
    assert result.allowed is True
    assert result.audit is not None
    assert result.audit.audit_available is False
