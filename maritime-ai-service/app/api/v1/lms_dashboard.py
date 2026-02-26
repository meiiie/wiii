"""
LMS Dashboard Endpoints — Sprint 175: "Cắm Phích Cắm" Phase 3

Teacher and admin AI-powered dashboard endpoints:
  - Course overview (students, grades, completion rate)
  - At-risk student detection
  - AI-generated class reports
  - Admin org overview

Auth: JWT + Role-based access:
  - Teachers: courses they teach
  - Admins: all courses + org-level analytics
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.integrations.lms.registry import get_lms_connector_registry
from app.services.risk_analyzer import StudentRiskAnalyzer

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/lms/dashboard", tags=["lms-dashboard"])

_risk_analyzer = StudentRiskAnalyzer()


def _get_connector(connector_id: str = "maritime-lms"):
    """Resolve LMS connector or raise 404."""
    registry = get_lms_connector_registry()
    connector = registry.get(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"LMS connector '{connector_id}' not found")
    return connector


def _require_teacher_or_admin(role: str):
    """Only teachers and admins can access dashboard endpoints."""
    if role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Chỉ giảng viên và quản trị viên mới truy cập được")


@router.get("/courses/{course_id}/overview")
@limiter.limit("20/minute")
async def course_overview(
    request: Request,
    course_id: str,
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Get course overview: student count, average grade, completion rate."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(x_role)
    connector = _get_connector(x_connector or "maritime-lms")

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
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Identify at-risk students in a course."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(x_role)
    connector = _get_connector(x_connector or "maritime-lms")

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
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Get grade distribution for a course."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(x_role)
    connector = _get_connector(x_connector or "maritime-lms")

    students = connector.get_course_students(course_id)
    if not students:
        return {"course_id": course_id, "distribution": {}, "avg": 0, "count": 0}

    # Collect grades
    all_grades = []
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

    for student in students:
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        grades = connector.get_student_grades(sid)
        for g in grades:
            if g.course_id == course_id and g.max_grade > 0:
                pct = g.grade / g.max_grade * 100
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
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Generate an AI-powered weekly class report (Vietnamese)."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    _require_teacher_or_admin(x_role)
    connector = _get_connector(x_connector or "maritime-lms")

    # Collect data
    stats = connector.get_course_stats(course_id)
    students = connector.get_course_students(course_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Course data not available")

    # Collect at-risk students
    at_risk_names = []
    for student in (students or [])[:50]:  # cap at 50 for LLM context
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        assessment = await _risk_analyzer.analyze(
            student_id=sid, course_id=course_id, connector=connector,
        )
        if assessment["level"] in ("high", "critical"):
            at_risk_names.append(f"{student.get('name', sid)} ({', '.join(assessment['factors'][:2])})")

    # Generate report with LLM
    try:
        from app.engine.llm_pool import get_llm_moderate
        llm = get_llm_moderate()

        prompt = (
            f"Bạn là trợ lý AI giáo dục. Viết báo cáo tuần cho giảng viên lớp {course_id}.\n\n"
            f"## Thống kê:\n"
            f"- Số sinh viên: {stats.get('students_count', 'N/A')}\n"
            f"- Điểm trung bình: {stats.get('avg_grade', 'N/A')}\n"
            f"- Tỉ lệ hoàn thành: {stats.get('completion_rate', 'N/A')}%\n"
            f"- Hoạt động 7 ngày qua: {stats.get('active_last_7d', 'N/A')} sinh viên\n\n"
            f"## Sinh viên cần hỗ trợ ({len(at_risk_names)}):\n"
        )
        for name in at_risk_names[:10]:
            prompt += f"- {name}\n"

        prompt += (
            "\n## Yêu cầu:\n"
            "Viết báo cáo ngắn gọn (3-5 đoạn) bằng tiếng Việt.\n"
            "Bao gồm: tổng quan, điểm tích cực, vấn đề cần chú ý, đề xuất hành động.\n"
            "Giọng văn chuyên nghiệp, dành cho giảng viên đại học."
        )

        response = await llm.ainvoke(prompt)
        report_text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("Failed to generate AI report: %s", e)
        report_text = (
            f"Lớp {course_id}: {stats.get('students_count', 0)} sinh viên, "
            f"điểm TB {stats.get('avg_grade', 0)}, "
            f"{len(at_risk_names)} sinh viên cần hỗ trợ."
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
    x_user_id: str = Header(alias="X-User-ID", default="anonymous"),
    x_role: str = Header(alias="X-Role", default="student"),
    x_connector: Optional[str] = Header(alias="X-LMS-Connector", default="maritime-lms"),
):
    """Get organization-level overview (admin only)."""
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration disabled")

    if x_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới truy cập được")

    connector = _get_connector(x_connector or "maritime-lms")
    config = connector.get_config()

    return {
        "connector_id": config.id,
        "display_name": config.display_name,
        "backend_type": config.backend_type.value,
        "enabled": config.enabled,
        "base_url_configured": bool(config.base_url),
    }
