from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4


def _make_repo():
    from app.repositories.semantic_memory_repository import SemanticMemoryRepository

    repo = SemanticMemoryRepository.__new__(SemanticMemoryRepository)
    repo._engine = MagicMock()
    repo._session_factory = MagicMock()
    repo._initialized = True
    return repo


def test_save_memory_dual_writes_shadow_vectors(monkeypatch):
    from app.models.semantic_memory import MemoryType, SemanticMemoryCreate
    from app.repositories import semantic_memory_repository_runtime as mod

    repo = _make_repo()
    mock_session = MagicMock()
    mock_insert_result = MagicMock()
    row_id = uuid4()
    mock_row = SimpleNamespace(
        id=row_id,
        user_id="user-1",
        content="Mình tên là Nam",
        memory_type="message",
        importance=0.7,
        metadata={},
        session_id="session-1",
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    mock_insert_result.fetchone.return_value = mock_row
    mock_session.execute.side_effect = [mock_insert_result, MagicMock()]
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    repo._session_factory.return_value = mock_session

    inline_space = SimpleNamespace(
        storage_kind="inline",
        provider="ollama",
        model="embeddinggemma",
        dimensions=768,
        space_fingerprint="ollama:embeddinggemma:768",
    )
    shadow_space = SimpleNamespace(
        storage_kind="shadow",
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        space_fingerprint="openai:text-embedding-3-small:1536",
    )
    source_contract = SimpleNamespace(
        provider="ollama",
        model="embeddinggemma",
        dimensions=768,
        fingerprint="ollama:embeddinggemma:768",
    )

    def _fake_build_shadow_embedding_sync(*, text_to_embed, space, source_embedding, source_contract):
        if space.storage_kind == "inline":
            return list(source_embedding)
        return [0.2] * space.dimensions

    monkeypatch.setattr(mod, "get_embedding_write_spaces", lambda *_args, **_kwargs: (inline_space, shadow_space))
    monkeypatch.setattr(mod, "get_active_embedding_space_contract", lambda: source_contract)
    monkeypatch.setattr(mod, "build_shadow_embedding_sync", _fake_build_shadow_embedding_sync)

    memory = SemanticMemoryCreate(
        user_id="user-1",
        content="Mình tên là Nam",
        embedding=[0.1] * 768,
        memory_type=MemoryType.MESSAGE,
        importance=0.7,
        metadata={"source": "unit-test"},
        session_id="session-1",
    )

    result = repo.save_memory(memory)

    assert result is not None
    assert mock_session.execute.call_count == 2
    shadow_query = mock_session.execute.call_args_list[1][0][0].text
    shadow_params = mock_session.execute.call_args_list[1][0][1]
    assert "INSERT INTO semantic_memory_vectors" in shadow_query
    assert shadow_params["space_fingerprint"] == "openai:text-embedding-3-small:1536"
    assert shadow_params["memory_id"] == str(row_id)
