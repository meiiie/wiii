"""
Spring Boot LMS Connector — First concrete implementation.

Sprint 155b: Multi-LMS Plugin Architecture
Sprint 155c: SSRF protection, student_id validation, HMAC consolidated.

Handles the custom Spring Boot LMS used by the Maritime University.
Webhook format: canonical LMSWebhookEvent (passes through).
API: REST with Bearer token auth.
"""

import logging
from typing import List, Optional

import httpx

from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
from app.integrations.lms.base import (
    LMSConnectorAdapter,
    LMSConnectorConfig,
)
from app.integrations.lms.lms_client import _validate_student_id
from app.integrations.lms.models import (
    LMSGrade,
    LMSStudentProfile,
    LMSUpcomingAssignment,
    LMSWebhookEvent,
)

logger = logging.getLogger(__name__)

_circuit_breaker = PerPlatformCircuitBreaker(threshold=5, recovery_seconds=120.0)


class SpringBootLMSAdapter(LMSConnectorAdapter):
    """Adapter for custom Spring Boot LMS (Maritime University).

    The Spring Boot LMS sends webhooks in our canonical LMSWebhookEvent format
    (since we control both codebases). The normalize_webhook method just parses
    and validates the payload directly.

    Sprint 175: Configurable API path prefix via config.extra["api_prefix"].
    Default: "api/v3/integration" for Maritime LMS.
    """

    def __init__(self, config: LMSConnectorConfig):
        self._config = config
        self._api_prefix = config.extra.get("api_prefix", "api/v3/integration")

    def get_config(self) -> LMSConnectorConfig:
        return self._config

    def normalize_webhook(
        self, raw_payload: dict, headers: dict
    ) -> Optional[LMSWebhookEvent]:
        """Spring Boot LMS sends canonical format — parse directly."""
        try:
            event = LMSWebhookEvent(**raw_payload)
            # Override source with our connector ID for provenance
            event.source = self._config.id
            return event
        except Exception as e:
            logger.warning("Failed to parse Spring Boot webhook: %s", e)
            return None

    # =========================================================================
    # REST API pull methods
    # =========================================================================

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._config.service_token:
            h["Authorization"] = f"Bearer {self._config.service_token}"
        return h

    def _get(self, path: str) -> Optional[dict]:
        """GET request with circuit breaker + timeout."""
        if not self._config.base_url:
            return None
        breaker_key = f"lms_{self._config.id}"
        if _circuit_breaker.is_open(breaker_key):
            logger.warning("LMS circuit breaker open for '%s'", self._config.id)
            return None
        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            resp = httpx.get(
                url, headers=self._headers(), timeout=self._config.api_timeout
            )
            resp.raise_for_status()
            _circuit_breaker.record_success(breaker_key)
            body = resp.json()
            # Sprint 220c: Unwrap Spring Boot response envelope
            # API returns {"success": true, "data": ...} wrapper
            if isinstance(body, dict) and "success" in body:
                if not body["success"]:
                    logger.debug(
                        "LMS API returned success=false [%s]: %s",
                        self._config.id, body.get("message", ""),
                    )
                    return None
                if "data" in body:
                    return body["data"]
            return body
        except httpx.TimeoutException:
            logger.warning("LMS API timeout [%s]: %s", self._config.id, path)
            _circuit_breaker.record_failure(breaker_key)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "LMS API HTTP %s [%s]: %s",
                e.response.status_code, self._config.id, path,
            )
            _circuit_breaker.record_failure(breaker_key)
            return None
        except Exception as e:
            logger.error("LMS API error [%s]: %s", self._config.id, e)
            _circuit_breaker.record_failure(breaker_key)
            return None

    def get_student_profile(self, student_id: str) -> Optional[LMSStudentProfile]:
        sid = _validate_student_id(student_id)
        data = self._get(f"{self._api_prefix}/students/{sid}/profile")
        if data is None:
            return None
        try:
            return LMSStudentProfile(**data)
        except Exception as e:
            logger.error("Failed to parse student profile: %s", e)
            return None

    def get_student_grades(self, student_id: str) -> List[LMSGrade]:
        sid = _validate_student_id(student_id)
        data = self._get(f"{self._api_prefix}/students/{sid}/grades")
        if data is None:
            return []
        try:
            return [LMSGrade(**g) for g in data] if isinstance(data, list) else []
        except Exception as e:
            logger.error("Failed to parse student grades: %s", e)
            return []

    def get_upcoming_assignments(
        self, student_id: str
    ) -> List[LMSUpcomingAssignment]:
        sid = _validate_student_id(student_id)
        data = self._get(f"{self._api_prefix}/students/{sid}/assignments/upcoming")
        if data is None:
            return []
        try:
            return (
                [LMSUpcomingAssignment(**a) for a in data]
                if isinstance(data, list)
                else []
            )
        except Exception as e:
            logger.error("Failed to parse upcoming assignments: %s", e)
            return []

    def get_student_enrollments(self, student_id: str) -> List[dict]:
        """Fetch student course enrollments from LMS API."""
        sid = _validate_student_id(student_id)
        data = self._get(f"{self._api_prefix}/students/{sid}/enrollments")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def get_student_quiz_history(self, student_id: str) -> List[dict]:
        """Fetch student quiz attempt history from LMS API."""
        sid = _validate_student_id(student_id)
        data = self._get(f"{self._api_prefix}/students/{sid}/quiz-history")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def get_course_students(self, course_id: str) -> List[dict]:
        """Fetch student roster for a course (teacher/admin only)."""
        cid = _validate_student_id(course_id)  # same validation pattern
        data = self._get(f"{self._api_prefix}/courses/{cid}/students")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def get_course_stats(self, course_id: str) -> Optional[dict]:
        """Fetch course statistics (teacher/admin only)."""
        cid = _validate_student_id(course_id)
        return self._get(f"{self._api_prefix}/courses/{cid}/stats")
