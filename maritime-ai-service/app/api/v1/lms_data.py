"""
LMS Data Pull Endpoints - Sprint 175: "Cam Phich Cam"

Expose on-demand LMS data pull for internal use and teacher dashboards.
Delegates to registered LMS connector adapters (SpringBootLMSAdapter, etc.).

Identity V2:
  - Canonical Wiii identity comes from JWT/service auth
  - LMS host role is a local overlay, not a global Wiii role
  - Student self-access resolves the linked LMS identity instead of trusting
    arbitrary X-User-ID headers
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import RequireAuth
from app.auth.external_identity import resolve_lms_identity
from app.core.config import settings
from app.core.security import AuthenticatedUser, is_platform_admin, normalize_host_role
from app.integrations.lms.registry import get_lms_connector_registry

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/lms", tags=["lms-data"])

_DEFAULT_LMS_CONNECTOR = "maritime-lms"


def _get_connector(connector_id: str = _DEFAULT_LMS_CONNECTOR):
    """Resolve LMS connector or raise 404."""
    registry = get_lms_connector_registry()
    connector = registry.get(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"LMS connector '{connector_id}' not found")
    return connector


def _resolve_effective_host_role(auth: AuthenticatedUser) -> str:
    """Resolve LMS-local role without letting it redefine Wiii identity."""
    if is_platform_admin(auth):
        return "platform_admin"
    return normalize_host_role(auth.host_role) or normalize_host_role(auth.role) or "student"


def _resolve_connector_id(auth: AuthenticatedUser, requested_connector: Optional[str]) -> str:
    """Prefer explicit host connector, then auth connector, then default."""
    normalized_requested = requested_connector.strip() if isinstance(requested_connector, str) else ""
    if normalized_requested:
        return normalized_requested
    normalized_auth_connector = (auth.connector_id or "").strip()
    if normalized_auth_connector:
        return normalized_auth_connector
    return _DEFAULT_LMS_CONNECTOR


async def _resolve_requester_student_identity(
    auth: AuthenticatedUser,
    *,
    connector_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the LMS student identity associated with this canonical user."""
    effective_connector = connector_id or auth.connector_id

    # Trusted LMS backend proxy requests may still carry the host-local user id
    # directly without a nested Wiii JWT.
    if auth.auth_method == "lms_service" and auth.role_source == "lms_host":
        return auth.user_id, effective_connector

    resolved_student_id, resolved_connector = await resolve_lms_identity(
        auth.user_id,
        auth.organization_id,
    )
    return resolved_student_id, resolved_connector or effective_connector


async def _check_student_access(
    auth: AuthenticatedUser,
    target_student_id: str,
    *,
    connector_id: Optional[str] = None,
) -> None:
    """Enforce LMS access: students can only view their own linked LMS data."""
    effective_role = _resolve_effective_host_role(auth)
    if effective_role in {"platform_admin", "teacher", "admin", "org_admin"}:
        return

    requester_student_id, requester_connector = await _resolve_requester_student_identity(
        auth,
        connector_id=connector_id,
    )
    if not requester_student_id or requester_student_id != target_student_id:
        raise HTTPException(
            status_code=403,
            detail="Ban chi co the xem du lieu cua chinh minh",
        )
    if connector_id and requester_connector and requester_connector != connector_id:
        raise HTTPException(
            status_code=403,
            detail="Tai khoan cua ban khong duoc lien ket voi LMS workspace nay",
        )


@router.get("/students/{student_id}/profile")
@limiter.limit("30/minute")
async def get_student_profile(
    request: Request,
    student_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Pull student profile from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    connector_id = _resolve_connector_id(auth, x_connector)
    await _check_student_access(auth, student_id, connector_id=connector_id)
    connector = _get_connector(connector_id)

    profile = connector.get_student_profile(student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return profile.model_dump()


@router.get("/students/{student_id}/grades")
@limiter.limit("30/minute")
async def get_student_grades(
    request: Request,
    student_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Pull student grades from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    connector_id = _resolve_connector_id(auth, x_connector)
    await _check_student_access(auth, student_id, connector_id=connector_id)
    connector = _get_connector(connector_id)

    grades = connector.get_student_grades(student_id)
    return {"student_id": student_id, "grades": [g.model_dump() for g in grades], "count": len(grades)}


@router.get("/students/{student_id}/enrollments")
@limiter.limit("30/minute")
async def get_student_enrollments(
    request: Request,
    student_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Pull student enrollments from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    connector_id = _resolve_connector_id(auth, x_connector)
    await _check_student_access(auth, student_id, connector_id=connector_id)
    connector = _get_connector(connector_id)

    enrollments = connector.get_student_enrollments(student_id)
    return {"student_id": student_id, "enrollments": enrollments, "count": len(enrollments)}


@router.get("/students/{student_id}/assignments")
@limiter.limit("30/minute")
async def get_student_assignments(
    request: Request,
    student_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Pull upcoming assignments for a student from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    connector_id = _resolve_connector_id(auth, x_connector)
    await _check_student_access(auth, student_id, connector_id=connector_id)
    connector = _get_connector(connector_id)

    assignments = connector.get_upcoming_assignments(student_id)
    return {
        "student_id": student_id,
        "assignments": [a.model_dump() for a in assignments],
        "count": len(assignments),
    }


@router.get("/students/{student_id}/quiz-history")
@limiter.limit("30/minute")
async def get_student_quiz_history(
    request: Request,
    student_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Pull quiz history for a student from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    connector_id = _resolve_connector_id(auth, x_connector)
    await _check_student_access(auth, student_id, connector_id=connector_id)
    connector = _get_connector(connector_id)

    quiz_history = connector.get_student_quiz_history(student_id)
    return {"student_id": student_id, "quiz_history": quiz_history, "count": len(quiz_history)}
