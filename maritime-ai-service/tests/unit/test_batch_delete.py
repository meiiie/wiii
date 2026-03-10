"""Tests for the chat_history bulk delete path."""

import inspect


def test_delete_user_history_uses_single_chat_history_delete():
    """delete_user_history should issue one direct DELETE on chat_history."""
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    assert "DELETE FROM chat_history" in source
    assert ".in_(" not in source
    assert "chat_sessions" not in source
    assert "chat_messages" not in source


def test_delete_user_history_is_org_scoped():
    """delete_user_history should respect current org scope."""
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    assert "org_filter" in source
    assert "org_params" in source
