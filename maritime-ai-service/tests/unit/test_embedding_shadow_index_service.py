from __future__ import annotations

from types import SimpleNamespace


class _FakeSession:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, query, *_args, **_kwargs):
        self.calls.append(str(getattr(query, "text", query)))
        return None

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ensure_shadow_vector_indexes_builds_partial_hnsw(monkeypatch):
    from app.services import embedding_shadow_index_service as mod

    fake_session = _FakeSession()
    contract = SimpleNamespace(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        fingerprint="openai:text-embedding-3-small:1536",
    )
    upserts: list[dict] = []

    monkeypatch.setattr(mod, "get_shared_session_factory", lambda: (lambda: fake_session))
    monkeypatch.setattr(mod, "upsert_embedding_space_registry_entry", lambda **kwargs: upserts.append(kwargs))

    created = mod.ensure_shadow_vector_indexes(
        target_contract=contract,
        tables=("semantic_memories",),
    )

    assert len(created) == 1
    assert "CREATE INDEX IF NOT EXISTS" in fake_session.calls[0]
    assert "semantic_memory_vectors" in fake_session.calls[0]
    assert "vector(1536)" in fake_session.calls[0]
    assert upserts[0]["index_ready"] is True
