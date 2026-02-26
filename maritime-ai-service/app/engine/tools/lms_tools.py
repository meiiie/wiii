"""
LMS Agent Tools — Sprint 175: "Cắm Phích Cắm" Phase 2

LangChain tools that AI agents use to query LMS data on behalf of users.
Bound to Direct Response and Tutor agents when enable_lms_integration=True.

Role-based:
  - Students: own data only (grades, assignments, enrollments)
  - Teachers: class overview, at-risk detection
  - Admins: any student/course data

All tools return Vietnamese text formatted for AI consumption.
"""

import logging

from langchain_core.tools import tool

from app.engine.tools.registry import (
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

# Tool category for LMS tools — reuse UTILITY since ToolCategory is an enum
# and we don't want to modify it just for this.
_LMS_CATEGORY = ToolCategory.UTILITY


def _get_connector(connector_id: str = "maritime-lms"):
    """Get LMS connector from registry."""
    from app.integrations.lms.registry import get_lms_connector_registry
    return get_lms_connector_registry().get(connector_id)


# =============================================================================
# Student tools (all roles)
# =============================================================================


@tool
def tool_check_student_grades(student_id: str) -> str:
    """Kiểm tra điểm số của sinh viên từ LMS.
    Dùng khi sinh viên hỏi về điểm, kết quả học tập, hoặc bạn cần biết
    trình độ của sinh viên để điều chỉnh nội dung giảng dạy.

    Args:
        student_id: Mã sinh viên (VD: "student-123")
    """
    connector = _get_connector()
    if connector is None:
        return "Không thể kết nối với LMS. Hệ thống chưa được cấu hình."

    grades = connector.get_student_grades(student_id)
    if not grades:
        return f"Chưa có dữ liệu điểm cho sinh viên {student_id}."

    lines = [f"📊 Điểm của sinh viên {student_id}:"]
    for g in grades:
        course = g.course_name or g.course_id
        pct = g.percentage
        emoji = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "🔴"
        lines.append(f"  {emoji} {course}: {g.grade}/{g.max_grade} ({pct:.0f}%)")

    avg = sum(g.percentage for g in grades) / len(grades) if grades else 0
    lines.append(f"\n📈 Điểm trung bình: {avg:.1f}%")
    return "\n".join(lines)


@tool
def tool_list_upcoming_assignments(student_id: str) -> str:
    """Xem bài tập sắp đến hạn của sinh viên.
    Dùng khi sinh viên hỏi về deadline, bài tập cần nộp, hoặc kế hoạch học tập.

    Args:
        student_id: Mã sinh viên (VD: "student-123")
    """
    connector = _get_connector()
    if connector is None:
        return "Không thể kết nối với LMS."

    assignments = connector.get_upcoming_assignments(student_id)
    if not assignments:
        return f"Không có bài tập sắp đến hạn cho sinh viên {student_id}."

    lines = [f"📝 Bài tập sắp đến hạn của sinh viên {student_id}:"]
    for a in assignments:
        course = a.course_name or a.course_id
        due = a.due_date.strftime("%d/%m/%Y %H:%M") if a.due_date else "N/A"
        lines.append(f"  📌 {a.assignment_name} ({course}) — Hạn: {due}")

    return "\n".join(lines)


@tool
def tool_check_course_progress(student_id: str, course_id: str) -> str:
    """Kiểm tra tiến độ học tập của sinh viên trong một môn học cụ thể.
    Bao gồm điểm số, bài tập, và bài kiểm tra trong môn đó.

    Args:
        student_id: Mã sinh viên
        course_id: Mã môn học (VD: "NHH101")
    """
    connector = _get_connector()
    if connector is None:
        return "Không thể kết nối với LMS."

    # Get grades for this course
    grades = connector.get_student_grades(student_id)
    course_grades = [g for g in grades if g.course_id == course_id]

    # Get assignments
    assignments = connector.get_upcoming_assignments(student_id)
    course_assignments = [a for a in assignments if a.course_id == course_id]

    # Get quiz history
    quiz_history = connector.get_student_quiz_history(student_id)
    course_quizzes = [
        q for q in quiz_history
        if isinstance(q, dict) and q.get("course_id") == course_id
    ]

    lines = [f"📖 Tiến độ môn {course_id} — Sinh viên {student_id}:"]

    if course_grades:
        lines.append("\n  📊 Điểm:")
        for g in course_grades:
            lines.append(f"    - {g.course_name or g.course_id}: {g.grade}/{g.max_grade} ({g.percentage:.0f}%)")
    else:
        lines.append("\n  📊 Chưa có điểm")

    if course_assignments:
        lines.append(f"\n  📝 Bài tập sắp tới: {len(course_assignments)} bài")
        for a in course_assignments[:5]:
            due = a.due_date.strftime("%d/%m") if a.due_date else "N/A"
            lines.append(f"    - {a.assignment_name} (hạn {due})")

    if course_quizzes:
        lines.append(f"\n  🧪 Bài kiểm tra đã làm: {len(course_quizzes)}")
        for q in course_quizzes[:5]:
            name = q.get("quiz_name", q.get("quiz_id", "N/A"))
            score = q.get("score", 0)
            max_s = q.get("max_score", 0)
            pct = (score / max_s * 100) if max_s > 0 else 0
            lines.append(f"    - {name}: {score}/{max_s} ({pct:.0f}%)")

    return "\n".join(lines)


# =============================================================================
# Teacher tools (teacher + admin only)
# =============================================================================


@tool
def tool_get_class_overview(course_id: str) -> str:
    """Tổng quan lớp học: số sinh viên, điểm trung bình, tỉ lệ hoàn thành.
    Chỉ dành cho giảng viên và quản trị viên.

    Args:
        course_id: Mã lớp học/môn học (VD: "NHH101")
    """
    connector = _get_connector()
    if connector is None:
        return "Không thể kết nối với LMS."

    stats = connector.get_course_stats(course_id)
    if stats is None:
        return f"Không có dữ liệu thống kê cho lớp {course_id}."

    lines = [
        f"📋 Tổng quan lớp {course_id}:",
        f"  👥 Số sinh viên: {stats.get('students_count', 'N/A')}",
        f"  📊 Điểm trung bình: {stats.get('avg_grade', 'N/A')}",
        f"  ✅ Tỉ lệ hoàn thành: {stats.get('completion_rate', 'N/A')}%",
        f"  🕐 Hoạt động 7 ngày qua: {stats.get('active_last_7d', 'N/A')} sinh viên",
        f"  ⚠️ Sinh viên nguy cơ: {stats.get('at_risk_count', 'N/A')}",
    ]
    return "\n".join(lines)


@tool
def tool_find_at_risk_students(course_id: str) -> str:
    """Tìm sinh viên có nguy cơ trong lớp dựa trên phân tích dữ liệu.
    Phân tích: điểm thấp, xu hướng giảm, bài tập trễ, kiểm tra yếu.
    Chỉ dành cho giảng viên và quản trị viên.

    Args:
        course_id: Mã lớp học (VD: "NHH101")
    """
    import asyncio
    from app.services.risk_analyzer import StudentRiskAnalyzer

    connector = _get_connector()
    if connector is None:
        return "Không thể kết nối với LMS."

    students = connector.get_course_students(course_id)
    if not students:
        return f"Không có danh sách sinh viên cho lớp {course_id}."

    analyzer = StudentRiskAnalyzer()
    at_risk = []

    for student in students[:50]:  # cap for performance
        sid = student.get("id") or student.get("student_id", "")
        if not sid:
            continue
        try:
            # Run async in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    assessment = pool.submit(
                        asyncio.run,
                        analyzer.analyze(student_id=sid, course_id=course_id, connector=connector)
                    ).result()
            else:
                assessment = asyncio.run(
                    analyzer.analyze(student_id=sid, course_id=course_id, connector=connector)
                )
        except Exception:
            assessment = {"score": 0, "level": "unknown", "factors": []}

        if assessment["level"] in ("high", "critical"):
            at_risk.append({
                "name": student.get("name", sid),
                "score": assessment["score"],
                "level": assessment["level"],
                "factors": assessment["factors"],
            })

    if not at_risk:
        return f"✅ Không có sinh viên nguy cơ cao trong lớp {course_id}."

    at_risk.sort(key=lambda x: x["score"], reverse=True)
    lines = [f"⚠️ Sinh viên nguy cơ trong lớp {course_id} ({len(at_risk)} người):"]
    for s in at_risk:
        emoji = "🔴" if s["level"] == "critical" else "🟠"
        reasons = ", ".join(s["factors"][:3])
        lines.append(f"  {emoji} {s['name']} (điểm rủi ro: {s['score']:.0%}) — {reasons}")

    return "\n".join(lines)


# =============================================================================
# Tool collection functions
# =============================================================================


def get_lms_student_tools() -> list:
    """Get LMS tools available to all roles (student/teacher/admin)."""
    return [
        tool_check_student_grades,
        tool_list_upcoming_assignments,
        tool_check_course_progress,
    ]


def get_lms_teacher_tools() -> list:
    """Get LMS tools for teachers and admins only."""
    return [
        tool_get_class_overview,
        tool_find_at_risk_students,
    ]


def get_all_lms_tools(role: str = "student") -> list:
    """Get LMS tools filtered by role."""
    tools = get_lms_student_tools()
    if role in ("teacher", "admin"):
        tools.extend(get_lms_teacher_tools())
    return tools


def register_lms_tools():
    """Register LMS tools in the global tool registry."""
    registry = get_tool_registry()

    for t in get_lms_student_tools():
        registry.register(
            tool=t,
            category=_LMS_CATEGORY,
            access=ToolAccess.READ,
            description=t.description,
            roles=["student", "teacher", "admin"],
        )

    for t in get_lms_teacher_tools():
        registry.register(
            tool=t,
            category=_LMS_CATEGORY,
            access=ToolAccess.READ,
            description=t.description,
            roles=["teacher", "admin"],
        )

    logger.info("Registered %d LMS tools", len(get_lms_student_tools()) + len(get_lms_teacher_tools()))
