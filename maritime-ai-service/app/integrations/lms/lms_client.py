"""
LMS API Client — Sprint 155: "Cầu Nối"

Sync httpx client for LMS REST APIs.
Circuit breaker protected, service-token authenticated.

Sprint 155b: Refactored to accept params (for multi-LMS adapter pattern).
Sprint 155c: HMAC deduped to base.verify_hmac_sha256, student_id sanitized.
"""

import logging
import re
from typing import List, Optional

import httpx

from app.core.config import get_settings
from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
from app.integrations.lms.base import verify_hmac_sha256
from app.integrations.lms.models import (
    LMSGrade,
    LMSStudentProfile,
    LMSUpcomingAssignment,
)

logger = logging.getLogger(__name__)

_circuit_breaker = PerPlatformCircuitBreaker(threshold=5, recovery_seconds=120.0)

# Student ID must be alphanumeric, hyphens, underscores, dots (no path traversal)
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_student_id(student_id: str) -> str:
    """Validate student_id is safe for URL path interpolation."""
    if not student_id or not _SAFE_ID_RE.match(student_id):
        raise ValueError(f"Invalid student_id format: {student_id!r}")
    return student_id


class LMSClient:
    """Sync httpx client for LMS REST API.

    Can be instantiated with explicit params (multi-LMS adapter pattern)
    or no-arg to read from settings (backward compat).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        service_token: Optional[str] = None,
        timeout: Optional[int] = None,
        connector_id: str = "default",
    ):
        if base_url is not None:
            # Explicit params (used by SpringBootLMSAdapter)
            self._base_url = base_url
            self._token = service_token
            self._timeout = timeout or 10
        else:
            # Backward compat: read from settings
            s = get_settings()
            self._base_url = s.lms_base_url
            self._token = s.lms_service_token
            self._timeout = s.lms_api_timeout
        self._connector_id = connector_id

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _get(self, path: str) -> Optional[dict]:
        """GET request with circuit breaker + timeout."""
        if not self._base_url:
            logger.debug("LMS base_url not configured")
            return None
        breaker_key = f"lms_{self._connector_id}"
        if _circuit_breaker.is_open(breaker_key):
            logger.warning("LMS API circuit breaker is open for '%s'", self._connector_id)
            return None
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=self._timeout)
            resp.raise_for_status()
            _circuit_breaker.record_success(breaker_key)
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("LMS API timeout [%s]: %s", self._connector_id, path)
            _circuit_breaker.record_failure(breaker_key)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("LMS API HTTP error %s [%s]: %s", e.response.status_code, self._connector_id, path)
            _circuit_breaker.record_failure(breaker_key)
            return None
        except Exception as e:
            logger.error("LMS API unexpected error [%s]: %s", self._connector_id, e)
            _circuit_breaker.record_failure(breaker_key)
            return None

    def get_student_profile(self, student_id: str) -> Optional[LMSStudentProfile]:
        """Fetch student profile from LMS."""
        sid = _validate_student_id(student_id)
        data = self._get(f"api/students/{sid}")
        if data is None:
            return None
        try:
            return LMSStudentProfile(**data)
        except Exception as e:
            logger.error("Failed to parse student profile: %s", e)
            return None

    def get_student_grades(self, student_id: str) -> List[LMSGrade]:
        """Fetch student grades from LMS."""
        sid = _validate_student_id(student_id)
        data = self._get(f"api/students/{sid}/grades")
        if data is None:
            return []
        try:
            if isinstance(data, list):
                return [LMSGrade(**g) for g in data]
            return []
        except Exception as e:
            logger.error("Failed to parse student grades: %s", e)
            return []

    def get_upcoming_assignments(self, student_id: str) -> List[LMSUpcomingAssignment]:
        """Fetch upcoming assignments from LMS."""
        sid = _validate_student_id(student_id)
        data = self._get(f"api/students/{sid}/assignments/upcoming")
        if data is None:
            return []
        try:
            if isinstance(data, list):
                return [LMSUpcomingAssignment(**a) for a in data]
            return []
        except Exception as e:
            logger.error("Failed to parse upcoming assignments: %s", e)
            return []

    @staticmethod
    def verify_webhook_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 webhook signature. Delegates to shared utility."""
        return verify_hmac_sha256(payload_bytes, signature, secret)
