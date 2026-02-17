"""
Tests for thread_utils — Organization-aware thread ID support.

Sprint 24: Multi-Organization Architecture.

Verifies:
- build_thread_id with org_id
- build_thread_id without org_id (backward compat)
- build_thread_id with org_id="default" (legacy format)
- parse_thread_id with org prefix
- parse_thread_id without org prefix (legacy)
- parse_thread_id_full
- extract_org_id
- belongs_to_user still works with both formats
- Round-trip: build → parse → build
"""

import pytest

from app.core.thread_utils import (
    build_thread_id,
    parse_thread_id,
    parse_thread_id_full,
    extract_user_id,
    extract_session_id,
    extract_org_id,
    is_valid_thread_id,
    belongs_to_user,
)


# =============================================================================
# build_thread_id
# =============================================================================


class TestBuildThreadId:
    def test_no_org(self):
        tid = build_thread_id("student-1", "session-abc")
        assert tid == "user_student-1__session_session-abc"

    def test_org_none(self):
        tid = build_thread_id("student-1", "session-abc", org_id=None)
        assert tid == "user_student-1__session_session-abc"

    def test_org_default_produces_legacy(self):
        """org_id='default' should produce legacy format (no prefix)."""
        tid = build_thread_id("student-1", "session-abc", org_id="default")
        assert tid == "user_student-1__session_session-abc"

    def test_org_custom(self):
        tid = build_thread_id("student-1", "session-abc", org_id="lms-hang-hai")
        assert tid == "org_lms-hang-hai__user_student-1__session_session-abc"

    def test_empty_user_raises(self):
        with pytest.raises(ValueError, match="user_id"):
            build_thread_id("", "session-abc", org_id="org-1")

    def test_empty_session_raises(self):
        with pytest.raises(ValueError, match="session_id"):
            build_thread_id("user-1", "", org_id="org-1")

    def test_whitespace_trimmed(self):
        tid = build_thread_id("  user-1  ", "  sess-1  ", org_id="org-1")
        assert "  " not in tid


# =============================================================================
# parse_thread_id (backward compat + org)
# =============================================================================


class TestParseThreadId:
    def test_parse_legacy(self):
        uid, sid = parse_thread_id("user_student-1__session_session-abc")
        assert uid == "student-1"
        assert sid == "session-abc"

    def test_parse_org_prefixed(self):
        """parse_thread_id strips org prefix and returns (user_id, session_id)."""
        uid, sid = parse_thread_id(
            "org_lms-hang-hai__user_student-1__session_session-abc"
        )
        assert uid == "student-1"
        assert sid == "session-abc"

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError):
            parse_thread_id("")

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError):
            parse_thread_id("garbage")


# =============================================================================
# parse_thread_id_full
# =============================================================================


class TestParseThreadIdFull:
    def test_full_with_org(self):
        org, uid, sid = parse_thread_id_full(
            "org_lms-hang-hai__user_student-1__session_session-abc"
        )
        assert org == "lms-hang-hai"
        assert uid == "student-1"
        assert sid == "session-abc"

    def test_full_legacy(self):
        org, uid, sid = parse_thread_id_full(
            "user_student-1__session_session-abc"
        )
        assert org is None
        assert uid == "student-1"
        assert sid == "session-abc"

    def test_full_empty_raises(self):
        with pytest.raises(ValueError):
            parse_thread_id_full("")


# =============================================================================
# extract_org_id
# =============================================================================


class TestExtractOrgId:
    def test_extract_from_org_prefixed(self):
        tid = "org_my-org__user_u1__session_s1"
        assert extract_org_id(tid) == "my-org"

    def test_extract_from_legacy(self):
        tid = "user_u1__session_s1"
        assert extract_org_id(tid) is None


# =============================================================================
# belongs_to_user (both formats)
# =============================================================================


class TestBelongsToUser:
    def test_legacy_format(self):
        tid = "user_student-1__session_s1"
        assert belongs_to_user(tid, "student-1") is True
        assert belongs_to_user(tid, "student-2") is False

    def test_org_format(self):
        tid = "org_org-1__user_student-1__session_s1"
        assert belongs_to_user(tid, "student-1") is True
        assert belongs_to_user(tid, "student-2") is False


# =============================================================================
# is_valid_thread_id
# =============================================================================


class TestIsValidThreadId:
    def test_legacy_valid(self):
        assert is_valid_thread_id("user_u1__session_s1") is True

    def test_org_valid(self):
        assert is_valid_thread_id("org_o1__user_u1__session_s1") is True

    def test_garbage_invalid(self):
        assert is_valid_thread_id("not-a-thread-id") is False


# =============================================================================
# Round-trip
# =============================================================================


class TestRoundTrip:
    def test_roundtrip_no_org(self):
        tid = build_thread_id("u1", "s1")
        uid, sid = parse_thread_id(tid)
        rebuilt = build_thread_id(uid, sid)
        assert rebuilt == tid

    def test_roundtrip_with_org(self):
        tid = build_thread_id("u1", "s1", org_id="org-1")
        org, uid, sid = parse_thread_id_full(tid)
        rebuilt = build_thread_id(uid, sid, org_id=org)
        assert rebuilt == tid

    def test_roundtrip_default_org(self):
        tid = build_thread_id("u1", "s1", org_id="default")
        org, uid, sid = parse_thread_id_full(tid)
        assert org is None  # "default" doesn't produce prefix
        rebuilt = build_thread_id(uid, sid, org_id=org)
        assert rebuilt == tid
