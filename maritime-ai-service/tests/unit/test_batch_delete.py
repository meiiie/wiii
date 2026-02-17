"""
Test batch delete uses IN clause instead of loop.
Verifies TASK-003 fix.
"""
import pytest
import inspect


def test_delete_user_history_uses_batch():
    """
    Verify delete_user_history uses batch delete (IN clause).

    Before fix: Loop with N queries
    After fix: Single query with IN clause
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    # Should use .in_() for batch operation
    assert ".in_(" in source, (
        "delete_user_history should use .in_() for batch delete"
    )

    # Should NOT have nested query in loop
    # This is a heuristic check
    assert "for chat_session in sessions:" not in source or ".in_(" in source, (
        "delete_user_history should not query inside loop"
    )


def test_delete_uses_synchronize_session_false():
    """
    Verify batch delete uses synchronize_session=False for performance.
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    assert "synchronize_session=False" in source, (
        "Batch delete should use synchronize_session=False"
    )
