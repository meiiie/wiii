from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


class _FakeConn:
    def __init__(self):
        self.fetch_query = ""
        self.fetch_params = ()
        self.commands: list[str] = []

    async def execute(self, query, *_params):
        self.commands.append(str(query))
        return "SET"

    async def fetch(self, query, *params):
        self.fetch_query = str(query)
        self.fetch_params = params
        return []


@pytest.mark.asyncio
async def test_dense_search_uses_shadow_vector_table(monkeypatch):
    from app.repositories.dense_search_repository import DenseSearchRepository

    repo = DenseSearchRepository.__new__(DenseSearchRepository)
    repo._pool = None
    repo._available = True
    repo._column_cache = {}
    conn = _FakeConn()

    async def _get_pool():
        return _FakePool(conn)

    async def _has_column(_conn, table, column):
        if table == "knowledge_embeddings" and column == "domain_id":
            return False
        return False

    repo._get_pool = _get_pool
    repo._has_column = _has_column

    shadow_space = SimpleNamespace(
        storage_kind="shadow",
        space_fingerprint="openai:text-embedding-3-small:1536",
        dimensions=1536,
    )
    monkeypatch.setattr(
        "app.repositories.dense_search_repository.get_active_embedding_read_space",
        lambda *_args, **_kwargs: shadow_space,
    )

    results = await repo.search([0.1] * 1536, limit=3)

    assert results == []
    assert "knowledge_embedding_vectors" in conn.fetch_query
    assert conn.fetch_params[1] == "openai:text-embedding-3-small:1536"
