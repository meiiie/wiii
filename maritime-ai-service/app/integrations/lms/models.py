"""
LMS Integration Models — Sprint 155: "Cầu Nối"

Pydantic schemas for LMS webhook events (inbound) and API response models.

Sprint 155c: Fixed datetime.utcnow → datetime.now(UTC), added ge= validators.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Webhook Event Models (LMS → Wiii)
# =============================================================================

class LMSWebhookEventType(str, Enum):
    """Supported LMS webhook event types."""
    GRADE_SAVED = "grade_saved"
    COURSE_ENROLLED = "course_enrolled"
    ASSIGNMENT_SUBMITTED = "assignment_submitted"
    QUIZ_COMPLETED = "quiz_completed"
    ATTENDANCE_MARKED = "attendance_marked"


class GradeSavedPayload(BaseModel):
    """Payload for grade_saved events."""
    student_id: str
    course_id: str
    course_name: Optional[str] = None
    grade: float = Field(ge=0)
    max_grade: float = Field(ge=0)
    assignment_name: Optional[str] = None


class CourseEnrolledPayload(BaseModel):
    """Payload for course_enrolled events."""
    student_id: str
    course_id: str
    course_name: str
    semester: Optional[str] = None


class QuizCompletedPayload(BaseModel):
    """Payload for quiz_completed events."""
    student_id: str
    quiz_id: str
    quiz_name: Optional[str] = None
    course_id: str
    course_name: Optional[str] = None
    score: float = Field(ge=0)
    max_score: float = Field(ge=0)
    duration_minutes: Optional[int] = None


class AssignmentSubmittedPayload(BaseModel):
    """Payload for assignment_submitted events."""
    student_id: str
    assignment_id: str
    assignment_name: Optional[str] = None
    course_id: str
    course_name: Optional[str] = None
    submitted_at: datetime


class AttendanceMarkedPayload(BaseModel):
    """Payload for attendance_marked events."""
    student_id: str
    course_id: str
    course_name: Optional[str] = None
    date: str
    status: str  # "present" | "absent" | "late"


class LMSWebhookEvent(BaseModel):
    """Top-level webhook envelope from LMS."""
    event_type: LMSWebhookEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any]
    source: str = "spring_boot_lms"


class LMSWebhookResponse(BaseModel):
    """Response returned to LMS after processing a webhook."""
    status: str = "accepted"
    event_type: str
    facts_created: int = 0
    message: str = ""


# =============================================================================
# LMS API Response Models (for on-demand pull, future Sprint 157)
# =============================================================================

class LMSStudentProfile(BaseModel):
    """Student profile from LMS API."""
    id: str
    name: str
    email: Optional[str] = None
    class_name: Optional[str] = None  # e.g. "ĐKTB K62A"
    program: Optional[str] = None     # e.g. "Điều khiển tàu biển"
    enrolled_courses: List[str] = Field(default_factory=list)


class LMSGrade(BaseModel):
    """Single grade record from LMS API."""
    course_id: str
    course_name: Optional[str] = None
    grade: float
    max_grade: float
    date: Optional[str] = None

    @property
    def percentage(self) -> float:
        """Grade as percentage (0-100)."""
        return (self.grade / self.max_grade * 100) if self.max_grade > 0 else 0.0


class LMSUpcomingAssignment(BaseModel):
    """Upcoming assignment from LMS API."""
    assignment_id: str
    assignment_name: str
    course_id: str
    course_name: Optional[str] = None
    due_date: datetime
