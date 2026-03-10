"""
LMS Webhook Handler — Sprint 155: "Cầu Nối"

Dispatches incoming LMS webhook events to the appropriate enrichment handler.

Sprint 155b: Routes by event.source via registry for multi-LMS support.
"""

import logging

from app.integrations.lms.enrichment import LMSEnrichmentService
from app.integrations.lms.models import (
    AssignmentSubmittedPayload,
    AttendanceMarkedPayload,
    CourseEnrolledPayload,
    GradeSavedPayload,
    LMSWebhookEvent,
    LMSWebhookEventType,
    LMSWebhookResponse,
    QuizCompletedPayload,
)

logger = logging.getLogger(__name__)


class LMSWebhookHandler:
    """Dispatch webhook events to enrichment handlers.

    Enrichment is LMS-agnostic — the same enrichment logic runs regardless
    of which LMS sent the event. The source_lms_id is passed for provenance.
    """

    def __init__(self):
        self._enrichment = LMSEnrichmentService()

    async def handle_event(self, event: LMSWebhookEvent) -> LMSWebhookResponse:
        """Route event to appropriate handler and return response."""
        handler_map = {
            LMSWebhookEventType.GRADE_SAVED: self._handle_grade_saved,
            LMSWebhookEventType.COURSE_ENROLLED: self._handle_course_enrolled,
            LMSWebhookEventType.QUIZ_COMPLETED: self._handle_quiz_completed,
            LMSWebhookEventType.ASSIGNMENT_SUBMITTED: self._handle_assignment_submitted,
            LMSWebhookEventType.ATTENDANCE_MARKED: self._handle_attendance_marked,
        }

        handler = handler_map.get(event.event_type)
        if handler is None:
            logger.info("Ignoring unknown LMS event type: %s", event.event_type)
            return LMSWebhookResponse(
                status="ignored",
                event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                message="Unknown event type",
            )

        try:
            facts_created = await handler(event.payload, event.source)

            # Sprint 220: Invalidate LMS context cache so next chat sees fresh data
            student_id = event.payload.get("student_id")
            if student_id:
                try:
                    from app.integrations.lms.context_loader import get_lms_context_loader
                    get_lms_context_loader().invalidate_cache(student_id)
                except Exception:
                    pass  # Cache invalidation is best-effort

            return LMSWebhookResponse(
                status="accepted",
                event_type=event.event_type.value,
                facts_created=facts_created,
                message=f"source={event.source}",
            )
        except Exception as e:
            logger.error("Error handling LMS event %s from %s: %s", event.event_type, event.source, e)
            return LMSWebhookResponse(
                status="error",
                event_type=event.event_type.value,
                message="Internal processing error",
            )

    async def _handle_grade_saved(self, payload: dict, source: str) -> int:
        p = GradeSavedPayload(**payload)
        return await self._enrichment.enrich_from_grade(p, source_lms_id=source)

    async def _handle_course_enrolled(self, payload: dict, source: str) -> int:
        p = CourseEnrolledPayload(**payload)
        return await self._enrichment.enrich_from_enrollment(p, source_lms_id=source)

    async def _handle_quiz_completed(self, payload: dict, source: str) -> int:
        p = QuizCompletedPayload(**payload)
        return await self._enrichment.enrich_from_quiz(p, source_lms_id=source)

    async def _handle_assignment_submitted(self, payload: dict, source: str) -> int:
        p = AssignmentSubmittedPayload(**payload)
        return await self._enrichment.enrich_from_assignment(p, source_lms_id=source)

    async def _handle_attendance_marked(self, payload: dict, source: str) -> int:
        p = AttendanceMarkedPayload(**payload)
        return await self._enrichment.enrich_from_attendance(p, source_lms_id=source)
