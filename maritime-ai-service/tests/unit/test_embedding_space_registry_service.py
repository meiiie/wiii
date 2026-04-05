from __future__ import annotations

from types import SimpleNamespace


class _FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def execute(self, query, params=None):
        self.calls.append((str(getattr(query, "text", query)), params))
        return SimpleNamespace(fetchall=lambda: [], scalar=lambda: None)

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_registry_falls_back_to_runtime_contract_when_table_unavailable(monkeypatch):
    from app.services import embedding_space_registry_service as mod

    contract = SimpleNamespace(
        provider="ollama",
        model="embeddinggemma",
        dimensions=768,
        fingerprint="ollama:embeddinggemma:768",
        label="embeddinggemma [ollama, 768d]",
    )

    mod.invalidate_embedding_space_registry_cache()
    monkeypatch.setattr(
        mod,
        "get_shared_session_factory",
        lambda: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(mod, "get_active_embedding_space_contract", lambda: contract)
    monkeypatch.setattr(mod, "get_runtime_embedding_space_contract", lambda: contract)

    entries = mod.get_embedding_space_registry_entries("semantic_memories", force_refresh=True)

    assert len(entries) == 1
    assert entries[0].storage_kind == "inline"
    assert entries[0].reads_enabled is True
    assert entries[0].space_fingerprint == "ollama:embeddinggemma:768"


def test_prepare_shadow_embedding_space_upserts_shadow_entry(monkeypatch):
    from app.services import embedding_space_registry_service as mod

    contract = SimpleNamespace(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        fingerprint="openai:text-embedding-3-small:1536",
        label="text-embedding-3-small [openai, 1536d]",
    )
    fake_session = _FakeSession()

    mod.invalidate_embedding_space_registry_cache()
    monkeypatch.setattr(mod, "seed_inline_embedding_space_registry", lambda *args, **kwargs: ())
    monkeypatch.setattr(mod, "get_shared_session_factory", lambda: (lambda: fake_session))

    entries = mod.prepare_shadow_embedding_space(
        entity_types=("semantic_memories",),
        target_contract=contract,
    )

    assert len(entries) == 1
    assert entries[0].storage_kind == "shadow"
    assert entries[0].writes_enabled is True
    assert entries[0].reads_enabled is False
    assert any("INSERT INTO embedding_space_registry" in call[0] for call in fake_session.calls)
