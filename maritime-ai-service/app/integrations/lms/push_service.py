"""
LMS Push Service — Sprint 175: "Cắm Phích Cắm" Phase 4

Sends data FROM Wiii TO LMS (bidirectional):
  - Student insights (recommendations, learning summaries)
  - Class alerts (at-risk students, low engagement)

Uses HMAC-signed requests for service-to-service auth.
Feature-gated: only active when enable_lms_integration=True.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
from app.integrations.lms.base import LMSConnectorConfig

logger = logging.getLogger(__name__)

_circuit_breaker = PerPlatformCircuitBreaker(threshold=5, recovery_seconds=120.0)


class LMSPushService:
    """Push insights and alerts from Wiii to LMS.

    Uses the same connector config as the pull adapter.
    Signs requests with HMAC-SHA256 using the webhook_secret.
    """

    def __init__(self, config: LMSConnectorConfig):
        self._config = config
        self._api_prefix = config.extra.get("api_prefix", "api/v3/integration")

    def _sign_payload(self, payload_bytes: bytes) -> str:
        """Create HMAC-SHA256 signature for outgoing request."""
        if not self._config.webhook_secret:
            return ""
        sig = hmac.new(
            self._config.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={sig}"

    def _headers(self, signature: str = "") -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._config.service_token:
            h["Authorization"] = f"Bearer {self._config.service_token}"
        if signature:
            h["X-Wiii-Signature"] = signature
        return h

    def _post(self, path: str, data: dict) -> Optional[dict]:
        """POST to LMS with circuit breaker + HMAC signing."""
        if not self._config.base_url:
            logger.warning("LMS push: no base_url configured")
            return None

        breaker_key = f"lms_push_{self._config.id}"
        if _circuit_breaker.is_open(breaker_key):
            logger.warning("LMS push circuit breaker open for '%s'", self._config.id)
            return None

        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        signature = self._sign_payload(payload_bytes)

        try:
            resp = httpx.post(
                url,
                content=payload_bytes,
                headers=self._headers(signature),
                timeout=self._config.api_timeout,
            )
            resp.raise_for_status()
            _circuit_breaker.record_success(breaker_key)
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("LMS push timeout [%s]: %s", self._config.id, path)
            _circuit_breaker.record_failure(breaker_key)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "LMS push HTTP %s [%s]: %s",
                e.response.status_code, self._config.id, path,
            )
            _circuit_breaker.record_failure(breaker_key)
            return None
        except Exception as e:
            logger.error("LMS push error [%s]: %s", self._config.id, e)
            _circuit_breaker.record_failure(breaker_key)
            return None

    async def _post_async(self, path: str, data: dict) -> Optional[dict]:
        """Async POST variant for long-running workflows."""
        if not self._config.base_url:
            logger.warning("LMS push: no base_url configured")
            return None

        breaker_key = f"lms_push_{self._config.id}"
        if _circuit_breaker.is_open(breaker_key):
            logger.warning("LMS push circuit breaker open for '%s'", self._config.id)
            return None

        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        signature = self._sign_payload(payload_bytes)

        try:
            async with httpx.AsyncClient(timeout=self._config.api_timeout) as client:
                resp = await client.post(
                    url,
                    content=payload_bytes,
                    headers=self._headers(signature),
                )
            resp.raise_for_status()
            _circuit_breaker.record_success(breaker_key)
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("LMS push timeout [%s]: %s", self._config.id, path)
            _circuit_breaker.record_failure(breaker_key)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "LMS push HTTP %s [%s]: %s",
                e.response.status_code, self._config.id, path,
            )
            _circuit_breaker.record_failure(breaker_key)
            return None
        except Exception as e:
            logger.error("LMS push error [%s]: %s", self._config.id, e)
            _circuit_breaker.record_failure(breaker_key)
            return None

    def push_student_insight(
        self,
        student_id: str,
        insight_type: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Push an AI insight about a student to LMS.

        Args:
            student_id: LMS student ID
            insight_type: "recommendation" | "alert" | "summary"
            content: Vietnamese text content
            metadata: Optional extra data
        """
        data = {
            "student_id": student_id,
            "insight_type": insight_type,
            "content": content,
            "source": "wiii_ai",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        result = self._post(f"{self._api_prefix}/insights", data)
        if result is not None:
            logger.info("Pushed insight for student %s: %s", student_id, insight_type)
            return True
        return False

    def push_class_alert(
        self,
        course_id: str,
        alert_type: str,
        content: str,
        student_ids: Optional[list] = None,
    ) -> bool:
        """Push a class-level alert to LMS for teachers.

        Args:
            course_id: LMS course ID
            alert_type: "at_risk_student" | "low_engagement" | "content_gap"
            content: Vietnamese text
            student_ids: Optional list of relevant student IDs
        """
        data = {
            "course_id": course_id,
            "alert_type": alert_type,
            "content": content,
            "student_ids": student_ids or [],
            "source": "wiii_ai",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = self._post(f"{self._api_prefix}/alerts", data)
        if result is not None:
            logger.info("Pushed alert for course %s: %s", course_id, alert_type)
            return True
        return False


    # ── Course Generation (Design spec v2.0, 2026-03-22) ──

    def push_course_shell(
        self,
        teacher_id: str,
        category_id: str,
        title: str,
        description: str = "",
        delivery_mode: str = "SELF_PACED",
        price_type: str = "FREE",
    ) -> Optional[dict]:
        """Create an empty course shell in LMS. Returns { courseId } on success.

        Called once when teacher approves outline — before chapter expansion.
        """
        data = {
            "teacherId": teacher_id,
            "categoryId": category_id,
            "title": title,
            "description": description,
            "deliveryMode": delivery_mode,
            "priceType": price_type,
        }
        result = self._post(f"{self._api_prefix}/courses/generate", data)
        if result is not None:
            course_id = result.get("data", {}).get("courseId") if isinstance(result.get("data"), dict) else None
            logger.info("Created course shell: courseId=%s", course_id)
            return result.get("data", result)
        return None

    async def push_course_shell_async(
        self,
        teacher_id: str,
        category_id: str,
        title: str,
        description: str = "",
        delivery_mode: str = "SELF_PACED",
        price_type: str = "FREE",
    ) -> Optional[dict]:
        data = {
            "teacherId": teacher_id,
            "categoryId": category_id,
            "title": title,
            "description": description,
            "deliveryMode": delivery_mode,
            "priceType": price_type,
        }
        result = await self._post_async(f"{self._api_prefix}/courses/generate", data)
        if result is not None:
            course_id = result.get("data", {}).get("courseId") if isinstance(result.get("data"), dict) else None
            logger.info("Created course shell: courseId=%s", course_id)
            return result.get("data", result)
        return None

    def push_chapter_content(
        self,
        course_id: str,
        chapter: dict,
    ) -> Optional[dict]:
        """Push one chapter with lessons + sections to LMS.

        Per-chapter transaction on LMS side — if this fails,
        other chapters are unaffected.

        Args:
            course_id: UUID of the course (from push_course_shell).
            chapter: Full chapter content dict with nested lessons and sections.
        """
        result = self._post(
            f"{self._api_prefix}/courses/generate/{course_id}/chapters",
            chapter,
        )
        if result is not None:
            logger.info(
                "Pushed chapter '%s' to course %s",
                chapter.get("title", "untitled"),
                course_id,
            )
            return result.get("data", result)
        return None

    async def push_chapter_content_async(
        self,
        course_id: str,
        chapter: dict,
    ) -> Optional[dict]:
        result = await self._post_async(
            f"{self._api_prefix}/courses/generate/{course_id}/chapters",
            chapter,
        )
        if result is not None:
            logger.info(
                "Pushed chapter '%s' to course %s",
                chapter.get("title", "untitled"),
                course_id,
            )
            return result.get("data", result)
        return None


def get_push_service(connector_id: str = "maritime-lms") -> Optional[LMSPushService]:
    """Get a push service instance for the given connector."""
    from app.integrations.lms.registry import get_lms_connector_registry

    connector = get_lms_connector_registry().get(connector_id)
    if connector is None:
        return None
    return LMSPushService(connector.get_config())
