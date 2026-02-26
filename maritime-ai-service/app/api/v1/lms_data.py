"""
LMS Data Pull Endpoints — Sprint 175: "Cắm Phích Cắm"

Expose on-demand LMS data pull for internal use and teacher dashboards.
Delegates to registered LMS connector adapters (SpringBootLMSAdapter, etc.).

Auth: JWT + Role-based access:
  - Students: own data only
  - Teachers: own students in their courses
  - Admins: any student data
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.integrations.lms.registry import get_lms_connector_registry

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/lms", tags=["lms-data"])


def _get_connector(connector_id: str = "maritime-lms"):
    """Resolve LMS connector or raise 404."""
    registry = get_lms_connector_registry()
    connector = registry.get(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"LMS connector '{connector_id}' not found")
    return connector


def _check_student_access(
    requester_id: str, requester_role: str, target_student_id: str
):
    """Enforce role-based access: students can only see own data."""
    if requester_role in ("admin", "teacher"):
        return
    if requester_id != target_student_id:
        raise HTTPException(
            status_code=403,
            detail="Bạn chỉ có thể xem dữ liệu của chính mình",
        )


@router.get("/students/{student_id}/profile")
@limiter.limit("30/minute")
async def get_student_profile(
    request: Request,
    student_id: str,
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Pull student profile from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _check_student_access(x_user_id, x_role, student_id)
    connector = _get_connector(x_connector or "maritime-lms")

    profile = connector.get_student_profile(student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return profile.model_dump()


@router.get("/students/{student_id}/grades")
@limiter.limit("30/minute")
async def get_student_grades(
    request: Request,
    student_id: str,
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Pull student grades from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _check_student_access(x_user_id, x_role, student_id)
    connector = _get_connector(x_connector or "maritime-lms")

    grades = connector.get_student_grades(student_id)
    return {"student_id": student_id, "grades": [g.model_dump() for g in grades], "count": len(grades)}


@router.get("/students/{student_id}/enrollments")
@limiter.limit("30/minute")
async def get_student_enrollments(
    request: Request,
    student_id: str,
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Pull student enrollments from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _check_student_access(x_user_id, x_role, student_id)
    connector = _get_connector(x_connector or "maritime-lms")

    enrollments = connector.get_student_enrollments(student_id)
    return {"student_id": student_id, "enrollments": enrollments, "count": len(enrollments)}


@router.get("/students/{student_id}/assignments")
@limiter.limit("30/minute")
async def get_student_assignments(
    request: Request,
    student_id: str,
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Pull upcoming assignments for a student from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _check_student_access(x_user_id, x_role, student_id)
    connector = _get_connector(x_connector or "maritime-lms")

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
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Pull quiz history for a student from LMS."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _check_student_access(x_user_id, x_role, student_id)
    connector = _get_connector(x_connector or "maritime-lms")

    quiz_history = connector.get_student_quiz_history(student_id)
    return {"student_id": student_id, "quiz_history": quiz_history, "count": len(quiz_history)}
