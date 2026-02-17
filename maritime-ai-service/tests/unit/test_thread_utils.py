"""
Tests for app.core.thread_utils — composite thread ID construction and parsing.

Sprint 16: Virtual Agent-per-User Architecture
"""

import pytest

from app.core.thread_utils import (
    belongs_to_user,
    build_thread_id,
    extract_session_id,
    extract_user_id,
    is_valid_thread_id,
    parse_thread_id,
)


# --- build_thread_id ---


def test_build_thread_id_valid():
    result = build_thread_id("student-123", "abc-456")
    assert result == "user_student-123__session_abc-456"


def test_build_thread_id_strips_whitespace():
    result = build_thread_id("  alice  ", "  sess-1  ")
    assert result == "user_alice__session_sess-1"


def test_build_thread_id_empty_user_id_raises():
    with pytest.raises(ValueError, match="user_id must not be empty"):
        build_thread_id("", "session-1")


def test_build_thread_id_whitespace_only_user_id_raises():
    with pytest.raises(ValueError, match="user_id must not be empty"):
        build_thread_id("   ", "session-1")


def test_build_thread_id_empty_session_id_raises():
    with pytest.raises(ValueError, match="session_id must not be empty"):
        build_thread_id("user-1", "")


def test_build_thread_id_whitespace_only_session_id_raises():
    with pytest.raises(ValueError, match="session_id must not be empty"):
        build_thread_id("user-1", "   ")


# --- parse_thread_id ---


def test_parse_thread_id_valid():
    user_id, session_id = parse_thread_id("user_student-123__session_abc-456")
    assert user_id == "student-123"
    assert session_id == "abc-456"


def test_parse_thread_id_empty_string_raises():
    with pytest.raises(ValueError, match="thread_id must not be empty"):
        parse_thread_id("")


def test_parse_thread_id_missing_separator_raises():
    with pytest.raises(ValueError, match="missing.*separator"):
        parse_thread_id("user_student-123_session_abc")


def test_parse_thread_id_missing_user_prefix_raises():
    with pytest.raises(ValueError, match="must start with"):
        parse_thread_id("student-123__session_abc-456")


def test_parse_thread_id_roundtrip():
    """build then parse should return the original values."""
    original_user = "bob"
    original_session = "xyz-789"
    thread_id = build_thread_id(original_user, original_session)
    user_id, session_id = parse_thread_id(thread_id)
    assert user_id == original_user
    assert session_id == original_session


# --- extract_user_id / extract_session_id ---


def test_extract_user_id():
    assert extract_user_id("user_alice__session_s1") == "alice"


def test_extract_session_id():
    assert extract_session_id("user_alice__session_s1") == "s1"


# --- is_valid_thread_id ---


def test_is_valid_thread_id_true():
    assert is_valid_thread_id("user_x__session_y") is True


def test_is_valid_thread_id_false_missing_prefix():
    assert is_valid_thread_id("x__session_y") is False


def test_is_valid_thread_id_false_missing_separator():
    assert is_valid_thread_id("user_x_y") is False


def test_is_valid_thread_id_false_empty():
    assert is_valid_thread_id("") is False


def test_is_valid_thread_id_false_none():
    assert is_valid_thread_id(None) is False


# --- belongs_to_user ---


def test_belongs_to_user_matching():
    tid = build_thread_id("student-123", "sess-1")
    assert belongs_to_user(tid, "student-123") is True


def test_belongs_to_user_non_matching():
    tid = build_thread_id("student-123", "sess-1")
    assert belongs_to_user(tid, "other-user") is False


def test_belongs_to_user_invalid_thread_id():
    assert belongs_to_user("garbage", "student-123") is False


def test_belongs_to_user_none_thread_id():
    assert belongs_to_user(None, "student-123") is False
