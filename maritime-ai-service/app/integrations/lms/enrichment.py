"""
LMS Enrichment Service — Sprint 155: "Cầu Nối"

Transforms LMS data (webhook events, API responses) into UserFacts
via FactExtractor.store_user_fact_upsert(). All facts get metadata
source='lms_enrichment' for provenance tracking.

Sprint 155b: Added source_lms_id parameter for multi-LMS provenance.
Sprint 155c: Fixed FactExtractor init (requires embeddings + repository).
"""

import logging
import threading
from typing import List, Optional

from app.integrations.lms.models import (
    AssignmentSubmittedPayload,
    AttendanceMarkedPayload,
    CourseEnrolledPayload,
    GradeSavedPayload,
    LMSGrade,
    LMSStudentProfile,
    QuizCompletedPayload,
)

logger = logging.getLogger(__name__)

_extractor_singleton = None
_extractor_lock = threading.Lock()


class LMSEnrichmentService:
    """Transform LMS data into UserFacts via FactExtractor.

    All enrichment methods accept an optional source_lms_id for provenance
    tracking. The AI agents never see this — they only see the UserFact content.
    """

    def _get_extractor(self):
        """Lazy-load FactExtractor singleton (thread-safe).

        FactExtractor requires embeddings + repository args.
        Pattern: same as SemanticMemoryEngine in core.py.
        """
        global _extractor_singleton
        if _extractor_singleton is None:
            with _extractor_lock:
                if _extractor_singleton is None:
                    from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
                    from app.engine.semantic_memory.extraction import FactExtractor
                    from app.repositories.semantic_memory_repository import SemanticMemoryRepository

                    embeddings = GeminiOptimizedEmbeddings()
                    repository = SemanticMemoryRepository()
                    _extractor_singleton = FactExtractor(embeddings, repository)
                    logger.info("LMS FactExtractor initialized")
        return _extractor_singleton

    async def _save_fact(
        self,
        user_id: str,
        fact_type: str,
        content: str,
        confidence: float = 0.9,
        source_message: Optional[str] = None,
        source_lms_id: Optional[str] = None,
    ) -> bool:
        """Delegate to FactExtractor.store_user_fact_upsert()."""
        try:
            extractor = self._get_extractor()
            lms_tag = f"[LMS:{source_lms_id}]" if source_lms_id else "[LMS]"
            return await extractor.store_user_fact_upsert(
                user_id=user_id,
                fact_content=content,
                fact_type=fact_type,
                confidence=confidence,
                source_message=source_message or f"{lms_tag} {content}",
            )
        except Exception as e:
            logger.error("Failed to save LMS fact (%s): %s", fact_type, e)
            return False

    # =========================================================================
    # Webhook event enrichments
    # =========================================================================

    async def enrich_from_grade(
        self, payload: GradeSavedPayload, source_lms_id: Optional[str] = None
    ) -> int:
        """Enrich from grade_saved event.

        Creates:
        - LEVEL fact (always) — latest grade
        - WEAKNESS fact if grade < 60%
        - STRENGTH fact if grade > 80%
        """
        count = 0
        user_id = payload.student_id
        course = payload.course_name or payload.course_id

        # Guard against division by zero
        if payload.max_grade <= 0:
            logger.warning("grade_saved with max_grade=0 for user %s", user_id)
            return 0

        pct = payload.grade / payload.max_grade * 100

        # Always create LEVEL fact
        level_content = f"level: Điểm gần nhất {course}: {payload.grade}/{payload.max_grade} ({pct:.0f}%)"
        if await self._save_fact(user_id, "level", level_content, confidence=0.90, source_lms_id=source_lms_id):
            count += 1

        # Weakness if < 60%
        if pct < 60:
            weak_content = f"weakness: Cần cải thiện môn {course} ({payload.grade}/{payload.max_grade})"
            if await self._save_fact(user_id, "weakness", weak_content, confidence=0.85, source_lms_id=source_lms_id):
                count += 1

        # Strength if > 80%
        if pct > 80:
            strong_content = f"strength: Giỏi môn {course} ({payload.grade}/{payload.max_grade})"
            if await self._save_fact(user_id, "strength", strong_content, confidence=0.85, source_lms_id=source_lms_id):
                count += 1

        return count

    async def enrich_from_enrollment(
        self, payload: CourseEnrolledPayload, source_lms_id: Optional[str] = None
    ) -> int:
        """Enrich from course_enrolled event. Creates ORGANIZATION + GOAL."""
        count = 0
        user_id = payload.student_id

        org_content = f"organization: Đang theo học môn {payload.course_name}"
        if await self._save_fact(user_id, "organization", org_content, confidence=0.95, source_lms_id=source_lms_id):
            count += 1

        semester_info = f" ({payload.semester})" if payload.semester else ""
        goal_content = f"goal: Hoàn thành môn {payload.course_name}{semester_info}"
        if await self._save_fact(user_id, "goal", goal_content, confidence=0.90, source_lms_id=source_lms_id):
            count += 1

        return count

    async def enrich_from_quiz(
        self, payload: QuizCompletedPayload, source_lms_id: Optional[str] = None
    ) -> int:
        """Enrich from quiz_completed event.

        Creates:
        - RECENT_TOPIC (always)
        - WEAKNESS if < 60%
        - STRENGTH if > 80%
        """
        count = 0
        user_id = payload.student_id
        quiz = payload.quiz_name or payload.quiz_id

        # Guard against division by zero
        if payload.max_score <= 0:
            logger.warning("quiz_completed with max_score=0 for user %s", user_id)
            return 0

        pct = payload.score / payload.max_score * 100

        # Always RECENT_TOPIC
        topic_content = f"recent_topic: Vừa làm bài kiểm tra '{quiz}'"
        if await self._save_fact(user_id, "recent_topic", topic_content, confidence=0.90, source_lms_id=source_lms_id):
            count += 1

        if pct < 60:
            weak_content = f"weakness: Khó khăn với bài kiểm tra '{quiz}' ({pct:.0f}%)"
            if await self._save_fact(user_id, "weakness", weak_content, confidence=0.85, source_lms_id=source_lms_id):
                count += 1

        if pct > 80:
            strong_content = f"strength: Nắm vững bài kiểm tra '{quiz}' ({pct:.0f}%)"
            if await self._save_fact(user_id, "strength", strong_content, confidence=0.85, source_lms_id=source_lms_id):
                count += 1

        return count

    async def enrich_from_assignment(
        self, payload: AssignmentSubmittedPayload, source_lms_id: Optional[str] = None
    ) -> int:
        """Enrich from assignment_submitted event. Creates RECENT_TOPIC."""
        user_id = payload.student_id
        assignment = payload.assignment_name or payload.assignment_id

        topic_content = f"recent_topic: Vừa nộp bài '{assignment}'"
        if await self._save_fact(user_id, "recent_topic", topic_content, confidence=0.90, source_lms_id=source_lms_id):
            return 1
        return 0

    async def enrich_from_attendance(
        self, payload: AttendanceMarkedPayload, source_lms_id: Optional[str] = None
    ) -> int:
        """Attendance is too noisy in v1 — skip."""
        return 0

    # =========================================================================
    # API pull enrichments (for future Sprint 157 on-demand use)
    # =========================================================================

    async def enrich_from_student_profile(
        self, user_id: str, profile: LMSStudentProfile, source_lms_id: Optional[str] = None
    ) -> int:
        """Enrich from LMS student profile. Creates NAME + ROLE + ORGANIZATION."""
        count = 0

        if profile.name:
            if await self._save_fact(user_id, "name", f"name: {profile.name}", confidence=0.95, source_lms_id=source_lms_id):
                count += 1

        if profile.program:
            if await self._save_fact(user_id, "role", f"role: Sinh viên ngành {profile.program}", confidence=0.95, source_lms_id=source_lms_id):
                count += 1

        if profile.class_name:
            if await self._save_fact(user_id, "organization", f"organization: Lớp {profile.class_name}", confidence=0.95, source_lms_id=source_lms_id):
                count += 1

        return count

    async def enrich_from_grades(
        self, user_id: str, grades: List[LMSGrade], source_lms_id: Optional[str] = None
    ) -> int:
        """Bulk enrichment from grade list. Delegates to enrich_from_grade."""
        count = 0
        for g in grades:
            payload = GradeSavedPayload(
                student_id=user_id,
                course_id=g.course_id,
                course_name=g.course_name,
                grade=g.grade,
                max_grade=g.max_grade,
            )
            count += await self.enrich_from_grade(payload, source_lms_id=source_lms_id)
        return count
