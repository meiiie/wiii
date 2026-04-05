"""
LMS Dashboard Endpoints - Sprint 175: "Cam Phich Cam" Phase 3

Teacher and admin AI-powered dashboard endpoints:
  - Course overview (students, grades, completion rate)
  - At-risk student detection
  - AI-generated class reports
  - Admin org overview

Identity V2:
  - Canonical Wiii identity comes from auth/JWT
  - LMS teacher/admin capabilities are host-local overlays
  - Platform admin remains a Wiii-global concern
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import RequireAuth
from app.core.config import settings
from app.core.security import AuthenticatedUser, is_platform_admin, normalize_host_role
from app.integrations.lms.registry import get_lms_connector_registry
from app.services.risk_analyzer import StudentRiskAnalyzer

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/lms/dashboard", tags=["lms-dashboard"])

_risk_analyzer = StudentRiskAnalyzer()
_DEFAULT_LMS_CONNECTOR = "maritime-lms"


def _get_connector(connector_id: str = _DEFAULT_LMS_CONNECTOR):
    """Resolve LMS connector or raise 404."""
    registry = get_lms_connector_registry()
    connector = registry.get(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"LMS connector '{connector_id}' not found")
    return connector


def _resolve_effective_host_role(auth: AuthenticatedUser) -> str:
    """Resolve LMS-local role without conflating it with Wiii-global authority."""
    if is_platform_admin(auth):
        return "platform_admin"
    return normalize_host_role(auth.host_role) or normalize_host_role(auth.role) or "student"


def _resolve_connector_id(auth: AuthenticatedUser, requested_connector: Optional[str]) -> str:
    normalized_requested = requested_connector.strip() if isinstance(requested_connector, str) else ""
    if normalized_requested:
        return normalized_requested
    normalized_auth_connector = (auth.connector_id or "").strip()
    if normalized_auth_connector:
        return normalized_auth_connector
    return _DEFAULT_LMS_CONNECTOR


def _require_teacher_or_admin(auth: AuthenticatedUser | str) -> None:
    """Only LMS teachers/admins or Wiii platform admins can access dashboards."""
    if isinstance(auth, str):
        effective_role = normalize_host_role(auth) or "student"
    else:
        effective_role = _resolve_effective_host_role(auth)
    if effective_role not in {"platform_admin", "teacher", "admin", "org_admin"}:
        raise HTTPException(status_code=403, detail="Chi giang vien va quan tri vien moi truy cap duoc")


def _require_org_overview_access(auth: AuthenticatedUser) -> None:
    """Org overview is for LMS admins/org-admins or Wiii platform admins."""
    effective_role = _resolve_effective_host_role(auth)
    if effective_role in {"platform_admin", "admin", "org_admin"}:
        return
    if auth.organization_role in {"admin", "owner"}:
        return
    raise HTTPException(status_code=403, detail="Chi quan tri vien moi truy cap duoc")


@router.get("/courses/{course_id}/overview")
@limiter.limit("20/minute")
async def course_overview(
    request: Request,
    course_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Get course overview: student count, average grade, completion rate."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(auth)
    connector = _get_connector(_resolve_connector_id(auth, x_connector))

    stats = connector.get_course_stats(course_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Course stats not available")

    return {
        "course_id": course_id,
        "students_count": stats.get("students_count", 0),
        "avg_grade": stats.get("avg_grade", 0),
        "completion_rate": stats.get("completion_rate", 0),
        "active_last_7d": stats.get("active_last_7d", 0),
        "at_risk_count": stats.get("at_risk_count", 0),
    }


@router.get("/courses/{course_id}/at-risk")
@limiter.limit("10/minute")
async def at_risk_students(
    request: Request,
    course_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Identify at-risk students in a course."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(auth)
    connector = _get_connector(_resolve_connector_id(auth, x_connector))

    students = connector.get_course_students(course_id)
    if not students:
        return {"course_id": course_id, "at_risk": [], "count": 0}

    at_risk = []
    for student in students:
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        assessment = await _risk_analyzer.analyze(
            student_id=sid,
            course_id=course_id,
            connector=connector,
        )
        if assessment["level"] in ("high", "critical"):
            at_risk.append({
                "student_id": sid,
                "name": student.get("name", ""),
                "risk_score": assessment["score"],
                "risk_level": assessment["level"],
                "reasons": assessment["factors"],
            })

    at_risk.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"course_id": course_id, "at_risk": at_risk, "count": len(at_risk)}


@router.get("/courses/{course_id}/grade-distribution")
@limiter.limit("20/minute")
async def grade_distribution(
    request: Request,
    course_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Get grade distribution for a course."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(auth)
    connector = _get_connector(_resolve_connector_id(auth, x_connector))

    students = connector.get_course_students(course_id)
    if not students:
        return {"course_id": course_id, "distribution": {}, "avg": 0, "count": 0}

    all_grades = []
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

    for student in students:
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        grades = connector.get_student_grades(sid)
        for grade in grades:
            if grade.course_id == course_id and grade.max_grade > 0:
                pct = grade.grade / grade.max_grade * 100
                all_grades.append(pct)
                if pct >= 85:
                    distribution["A"] += 1
                elif pct >= 70:
                    distribution["B"] += 1
                elif pct >= 55:
                    distribution["C"] += 1
                elif pct >= 40:
                    distribution["D"] += 1
                else:
                    distribution["F"] += 1

    avg = sum(all_grades) / len(all_grades) if all_grades else 0
    return {
        "course_id": course_id,
        "distribution": distribution,
        "avg": round(avg, 1),
        "count": len(all_grades),
    }


@router.post("/courses/{course_id}/ai-report")
@limiter.limit("5/minute")
async def generate_ai_report(
    request: Request,
    course_id: str,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Generate an AI-powered weekly class report (Vietnamese)."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(auth)
    connector = _get_connector(_resolve_connector_id(auth, x_connector))

    stats = connector.get_course_stats(course_id)
    students = connector.get_course_students(course_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Course data not available")

    at_risk_names = []
    for student in (students or [])[:50]:
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        assessment = await _risk_analyzer.analyze(
            student_id=sid,
            course_id=course_id,
            connector=connector,
        )
        if assessment["level"] in ("high", "critical"):
            at_risk_names.append(f"{student.get('name', sid)} ({', '.join(assessment['factors'][:2])})")

    try:
        from app.engine.llm_pool import get_llm_moderate

        llm = get_llm_moderate()
        prompt = (
            f"Ban la tro ly AI giao duc. Viet bao cao tuan cho giang vien lop {course_id}.\n\n"
            f"## Thong ke:\n"
            f"- So sinh vien: {stats.get('students_count', 'N/A')}\n"
            f"- Diem trung binh: {stats.get('avg_grade', 'N/A')}\n"
            f"- Ti le hoan thanh: {stats.get('completion_rate', 'N/A')}%\n"
            f"- Hoat dong 7 ngay qua: {stats.get('active_last_7d', 'N/A')} sinh vien\n\n"
            f"## Sinh vien can ho tro ({len(at_risk_names)}):\n"
        )
        for name in at_risk_names[:10]:
            prompt += f"- {name}\n"

        prompt += (
            "\n## Yeu cau:\n"
            "Viet bao cao ngan gon (3-5 doan) bang tieng Viet.\n"
            "Bao gom: tong quan, diem tich cuc, van de can chu y, de xuat hanh dong.\n"
            "Giong van chuyen nghiep, danh cho giang vien dai hoc."
        )

        response = await llm.ainvoke(prompt)
        report_text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("Failed to generate AI report: %s", exc)
        report_text = (
            f"Lop {course_id}: {stats.get('students_count', 0)} sinh vien, "
            f"diem TB {stats.get('avg_grade', 0)}, "
            f"{len(at_risk_names)} sinh vien can ho tro."
        )

    return {
        "course_id": course_id,
        "report": report_text,
        "stats": stats,
        "at_risk_count": len(at_risk_names),
    }


@router.get("/org/overview")
@limiter.limit("10/minute")
async def org_overview(
    request: Request,
    auth: RequireAuth,
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default=None),
):
    """Get organization-level overview."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_org_overview_access(auth)
    connector = _get_connector(_resolve_connector_id(auth, x_connector))
    config = connector.get_config()

    return {
        "connector_id": config.id,
        "display_name": config.display_name,
        "backend_type": config.backend_type.value,
        "enabled": config.enabled,
        "base_url_configured": bool(config.base_url),
    }
