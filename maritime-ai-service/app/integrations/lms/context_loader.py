"""
LMS Context Loader — Sprint 220: "Cắm Phích" Production Connection

On-demand fetch of student's LMS data for system prompt injection.
Cached per user (5-minute TTL) to avoid hammering LMS API.

Usage:
    loader = get_lms_context_loader()
    ctx = loader.load_student_context(user_id, connector_id="maritime-lms")
    if ctx:
        prompt_block = loader.format_for_prompt(ctx)

Feature-gated: enable_lms_integration=True required.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache TTL: 5 minutes
_CACHE_TTL_SECONDS = 300


@dataclass
class LMSStudentContext:
    """Aggregated LMS context for a single student."""

    student_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    program: Optional[str] = None
    class_name: Optional[str] = None

    # Enrollments: list of {"course_id", "course_name", "semester"?}
    enrollments: List[dict] = field(default_factory=list)

    # Grades: list of LMSGrade-like dicts
    grades: List[dict] = field(default_factory=list)

    # Upcoming assignments: list of LMSUpcomingAssignment-like dicts
    upcoming_assignments: List[dict] = field(default_factory=list)

    # Quiz history: list of raw quiz dicts
    quiz_history: List[dict] = field(default_factory=list)

    # Timestamp of when this context was loaded
    loaded_at: float = field(default_factory=time.time)


# Simple in-memory cache: {user_id -> (LMSStudentContext, timestamp)}
_context_cache: Dict[str, tuple] = {}


class LMSContextLoader:
    """Loads student's LMS context for AI system prompt injection.

    Fetches enrollments, grades, upcoming assignments from LMS.
    Caches for 5 minutes per user to avoid hammering LMS API.
    """

    def load_student_context(
        self,
        user_id: str,
        connector_id: Optional[str] = None,
    ) -> Optional[LMSStudentContext]:
        """Fetch student's LMS data, with caching.

        Args:
            user_id: External LMS user ID (resolved via identity lookup)
            connector_id: LMS connector identifier (None = skip, no hardcoded assumption)

        Returns:
            LMSStudentContext if data available, None otherwise
        """
        # Sprint 220c: No connector = no LMS data (removed hardcoded default)
        if not connector_id:
            logger.debug("[LMS] No connector_id provided, skipping context load")
            return None

        # Sprint 220c: Compound cache key for multi-connector support
        cache_key = f"{user_id}:{connector_id}"

        # Check cache first
        cached = _context_cache.get(cache_key)
        if cached:
            ctx, ts = cached
            if time.time() - ts < _CACHE_TTL_SECONDS:
                logger.debug("[LMS] Context cache hit for user %s", user_id)
                return ctx

        # Fetch from LMS
        try:
            from app.integrations.lms.registry import get_lms_connector_registry

            connector = get_lms_connector_registry().get(connector_id)
            if connector is None:
                logger.debug("[LMS] Connector '%s' not found", connector_id)
                return None

            context = LMSStudentContext(student_id=user_id)

            # Profile
            profile = connector.get_student_profile(user_id)
            if profile:
                context.name = profile.full_name or profile.name  # Sprint 220c: prefer full_name
                context.email = profile.email
                context.program = profile.program
                context.class_name = profile.class_name

            # Enrollments
            enrollments = connector.get_student_enrollments(user_id)
            if enrollments:
                context.enrollments = enrollments[:20]  # cap

            # Grades
            grades = connector.get_student_grades(user_id)
            if grades:
                context.grades = [
                    {
                        "course_id": g.course_id,
                        "course_name": g.course_name,
                        "grade": g.grade,
                        "max_grade": g.max_grade,
                        "percentage": g.percentage,
                        "date": g.date,
                    }
                    for g in grades[:30]  # cap
                ]

            # Upcoming assignments
            assignments = connector.get_upcoming_assignments(user_id)
            if assignments:
                context.upcoming_assignments = [
                    {
                        "assignment_id": a.assignment_id,
                        "assignment_name": a.assignment_name,
                        "course_id": a.course_id,
                        "course_name": a.course_name,
                        "due_date": a.due_date.strftime("%d/%m/%Y %H:%M")
                        if a.due_date
                        else None,
                    }
                    for a in assignments[:10]  # cap
                ]

            # Quiz history
            quiz_history = connector.get_student_quiz_history(user_id)
            if quiz_history:
                context.quiz_history = quiz_history[:20]  # cap

            # Check if we got any data at all
            has_data = (
                context.name
                or context.enrollments
                or context.grades
                or context.upcoming_assignments
            )
            if not has_data:
                logger.debug("[LMS] No data found for user %s", user_id)
                return None

            # Cache
            context.loaded_at = time.time()
            _context_cache[cache_key] = (context, time.time())
            logger.info(
                "[LMS] Context loaded for user %s: %d enrollments, %d grades, %d assignments",
                user_id,
                len(context.enrollments),
                len(context.grades),
                len(context.upcoming_assignments),
            )
            return context

        except Exception as e:
            logger.warning("[LMS] Failed to load context for user %s: %s", user_id, e)
            return None

    def format_for_prompt(self, context: LMSStudentContext) -> str:
        """Format LMS data as Vietnamese text block for system prompt injection.

        Returns a concise block suitable for injection into the AI system prompt.
        """
        lines = ["--- THÔNG TIN HỌC TẬP (từ LMS) ---"]

        # Student info
        if context.name:
            info_parts = [f"Sinh viên: {context.name}"]
            if context.program:
                info_parts.append(f"Ngành: {context.program}")
            if context.class_name:
                info_parts.append(f"Lớp: {context.class_name}")
            lines.append(" | ".join(info_parts))

        # Enrollments with grade summary
        if context.grades:
            lines.append("\nMôn học và điểm:")
            # Group grades by course
            course_grades: Dict[str, list] = {}
            for g in context.grades:
                cid = g["course_id"]
                if cid not in course_grades:
                    course_grades[cid] = {
                        "name": g.get("course_name") or cid,
                        "grades": [],
                    }
                course_grades[cid]["grades"].append(g)

            for cid, info in list(course_grades.items())[:8]:
                grades_list = info["grades"]
                avg_pct = (
                    sum(g["percentage"] for g in grades_list) / len(grades_list)
                    if grades_list
                    else 0
                )
                emoji = "🟢" if avg_pct >= 80 else "🟡" if avg_pct >= 60 else "🔴"
                lines.append(f"  {emoji} {info['name']}: TB {avg_pct:.0f}%")
        elif context.enrollments:
            lines.append("\nMôn học đang theo:")
            for e in context.enrollments[:8]:
                name = e.get("course_name") or e.get("course_id", "N/A")
                lines.append(f"  - {name}")

        # Upcoming assignments
        if context.upcoming_assignments:
            lines.append("\nBài tập sắp tới:")
            for a in context.upcoming_assignments[:5]:
                due = a.get("due_date", "N/A")
                lines.append(f"  📌 {a['assignment_name']} ({a.get('course_name', '')}) — Hạn: {due}")

        # Recent quiz results
        if context.quiz_history:
            lines.append("\nKiểm tra gần đây:")
            for q in context.quiz_history[:5]:
                name = q.get("quiz_name") or q.get("quiz_id", "N/A")
                score = q.get("score")
                max_s = q.get("max_score") or 0
                status = q.get("status", "")
                if score is not None and max_s > 0:
                    pct = score / max_s * 100
                    emoji = "✅" if pct >= 80 else "⚠️" if pct >= 60 else "❌"
                    lines.append(f"  {emoji} {name}: {score}/{max_s} ({pct:.0f}%)")
                elif status == "IN_PROGRESS":
                    lines.append(f"  ⏳ {name}: Đang làm")

        lines.append(
            "\n⚠️ Dữ liệu trên lấy từ LMS — dùng để cá nhân hóa câu trả lời. "
            "Khi sinh viên hỏi về điểm/bài tập, hãy tham chiếu dữ liệu này."
        )

        return "\n".join(lines)

    def invalidate_cache(self, user_id: str, connector_id: Optional[str] = None) -> None:
        """Remove cached context for a user (called after webhook events).

        Sprint 220c: Supports compound keys. If connector_id is None,
        removes all entries matching user_id prefix.
        """
        if connector_id:
            _context_cache.pop(f"{user_id}:{connector_id}", None)
        else:
            # Remove all entries for this user (any connector)
            keys_to_remove = [k for k in _context_cache if k.startswith(f"{user_id}:")]
            for k in keys_to_remove:
                _context_cache.pop(k, None)
            # Also try legacy key (plain user_id)
            _context_cache.pop(user_id, None)

    def clear_cache(self) -> None:
        """Clear all cached contexts."""
        _context_cache.clear()


# Singleton
_loader_instance: Optional[LMSContextLoader] = None


def get_lms_context_loader() -> LMSContextLoader:
    """Get the singleton LMSContextLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = LMSContextLoader()
    return _loader_instance
