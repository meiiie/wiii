"""
Thread Management Utilities for Wiii

Sprint 16: Virtual Agent-per-User Architecture
Provides composite thread ID construction and parsing for per-user conversation isolation.

Thread ID formats:
  Legacy: "user_{user_id}__session_{session_id}"
  Org:    "org_{org_id}__user_{user_id}__session_{session_id}"

Sprint 24: Added org_id parameter. The "default" org produces legacy format
for backward compatibility.
"""

from typing import Optional

# Separator between user_id and session_id parts
_THREAD_SEP = "__session_"
_USER_PREFIX = "user_"
_ORG_PREFIX = "org_"
_ORG_SEP = "__user_"


def build_thread_id(
    user_id: str, session_id: str, org_id: Optional[str] = None
) -> str:
    """
    Build a composite thread ID from user_id, session_id, and optional org_id.

    Format (no org or org="default"):
        "user_{user_id}__session_{session_id}"
    Format (with org):
        "org_{org_id}__user_{user_id}__session_{session_id}"

    Args:
        user_id: The user's identifier (e.g., "student-123")
        session_id: The session identifier (e.g., "abc-456")
        org_id: Optional organization ID (e.g., "lms-hang-hai")

    Returns:
        Composite thread ID string

    Raises:
        ValueError: If user_id or session_id is empty/None
    """
    # Sprint 121b: Defensive conversion — callers may pass UUID objects
    user_id = str(user_id).strip() if user_id else ""
    session_id = str(session_id).strip() if session_id else ""
    if not user_id:
        raise ValueError("user_id must not be empty")
    if not session_id:
        raise ValueError("session_id must not be empty")

    base = f"{_USER_PREFIX}{user_id}{_THREAD_SEP}{session_id}"

    if org_id and org_id != "default":
        return f"{_ORG_PREFIX}{org_id}{_ORG_SEP}{user_id}{_THREAD_SEP}{session_id}"

    return base


def parse_thread_id(thread_id: str) -> tuple[str, str]:
    """
    Parse a composite thread ID back into (user_id, session_id).

    Supports both legacy and org-prefixed formats.

    Args:
        thread_id: Composite thread ID string

    Returns:
        Tuple of (user_id, session_id)

    Raises:
        ValueError: If thread_id format is invalid
    """
    if not thread_id:
        raise ValueError("thread_id must not be empty")

    if _THREAD_SEP not in thread_id:
        raise ValueError(
            f"Invalid thread_id format: missing '{_THREAD_SEP}' separator"
        )

    # Strip org prefix if present: "org_X__user_Y__session_Z"
    working = thread_id
    if working.startswith(_ORG_PREFIX) and _ORG_SEP in working:
        # Remove "org_{org_id}__" prefix to get "user_{user_id}__session_{session_id}"
        _, working = working.split(_ORG_SEP, 1)
        working = f"{_USER_PREFIX}{working}"

    if not working.startswith(_USER_PREFIX):
        raise ValueError(
            f"Invalid thread_id format: must start with '{_USER_PREFIX}'"
        )

    # Remove "user_" prefix, then split on "__session_"
    without_prefix = working[len(_USER_PREFIX):]
    parts = without_prefix.split(_THREAD_SEP, 1)

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "Invalid thread_id format: could not extract user_id and session_id"
        )

    return parts[0], parts[1]


def parse_thread_id_full(thread_id: str) -> tuple[Optional[str], str, str]:
    """
    Parse a composite thread ID into (org_id, user_id, session_id).

    Sprint 24: Extended parser that also extracts organization.

    Args:
        thread_id: Composite thread ID string

    Returns:
        Tuple of (org_id or None, user_id, session_id)

    Raises:
        ValueError: If thread_id format is invalid
    """
    if not thread_id:
        raise ValueError("thread_id must not be empty")

    org_id = None

    if thread_id.startswith(_ORG_PREFIX) and _ORG_SEP in thread_id:
        org_part, rest = thread_id.split(_ORG_SEP, 1)
        org_id = org_part[len(_ORG_PREFIX):]
        # rest is now "user_id__session_session_id" — prepend user_ prefix
        user_id, session_id = _parse_user_session(f"{_USER_PREFIX}{rest}")
    else:
        user_id, session_id = parse_thread_id(thread_id)

    return org_id, user_id, session_id


def _parse_user_session(part: str) -> tuple[str, str]:
    """Parse 'user_{uid}__session_{sid}' into (uid, sid)."""
    if not part.startswith(_USER_PREFIX):
        raise ValueError("Invalid format: expected user_ prefix")
    without_prefix = part[len(_USER_PREFIX):]
    pieces = without_prefix.split(_THREAD_SEP, 1)
    if len(pieces) != 2 or not pieces[0] or not pieces[1]:
        raise ValueError("Invalid format: could not extract user_id and session_id")
    return pieces[0], pieces[1]


def extract_user_id(thread_id: str) -> str:
    """Extract user_id from a composite thread ID."""
    user_id, _ = parse_thread_id(thread_id)
    return user_id


def extract_session_id(thread_id: str) -> str:
    """Extract session_id from a composite thread ID."""
    _, session_id = parse_thread_id(thread_id)
    return session_id


def extract_org_id(thread_id: str) -> Optional[str]:
    """Extract org_id from a composite thread ID (None for legacy format)."""
    org_id, _, _ = parse_thread_id_full(thread_id)
    return org_id


def is_valid_thread_id(thread_id: str) -> bool:
    """
    Check if a string is a valid composite thread ID format.

    Returns:
        True if format is valid, False otherwise
    """
    try:
        parse_thread_id(thread_id)
        return True
    except (ValueError, TypeError):
        return False


def belongs_to_user(thread_id: str, user_id: str) -> bool:
    """
    Check if a thread_id belongs to a given user.

    Used for ownership verification in API endpoints.

    Args:
        thread_id: Composite thread ID
        user_id: User ID to check against

    Returns:
        True if the thread belongs to the user
    """
    try:
        extracted_user_id = extract_user_id(thread_id)
        return extracted_user_id == user_id
    except (ValueError, TypeError):
        return False
