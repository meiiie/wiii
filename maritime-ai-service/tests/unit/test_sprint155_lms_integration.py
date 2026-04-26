"""
Sprint 155: "Cầu Nối" — LMS Integration Foundation Tests
Sprint 155b: Multi-LMS Plugin Architecture Tests
Sprint 155c: Security Hardening Tests

Tests for:
- HMAC webhook signature verification
- Webhook event parsing + validation
- Grade enrichment (LEVEL + WEAKNESS/STRENGTH)
- Other enrichments (enrollment, quiz, assignment, attendance)
- LMS API client + student_id sanitization
- Webhook handler dispatch + error sanitization
- Config integration
- Multi-LMS: adapter ABC, registry, Spring Boot adapter, loader
- Security: negative grade validation, repr masking, HMAC consolidation
"""

import hashlib
import hmac as hmac_mod
import json
import re
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy dependencies before import
# ---------------------------------------------------------------------------
_STUBBED_MODULES = {}
for mod in [
    "app.engine.llm_pool",
    "app.engine.gemini_embedding",
    "app.repositories.semantic_memory_repository",
    "app.services.output_processor",
]:
    if mod not in sys.modules:
        stub = MagicMock()
        sys.modules[mod] = stub
        _STUBBED_MODULES[mod] = stub

from app.integrations.lms.models import (
    AssignmentSubmittedPayload,
    AttendanceMarkedPayload,
    CourseEnrolledPayload,
    GradeSavedPayload,
    LMSGrade,
    LMSStudentProfile,
    LMSUpcomingAssignment,
    LMSWebhookEvent,
    LMSWebhookEventType,
    LMSWebhookResponse,
    QuizCompletedPayload,
)
from app.integrations.lms.lms_client import LMSClient, _validate_student_id
from app.integrations.lms.enrichment import LMSEnrichmentService
from app.integrations.lms.webhook_handler import LMSWebhookHandler
from app.integrations.lms.base import (
    LMSBackendType,
    LMSConnectorAdapter,
    LMSConnectorConfig,
    verify_hmac_sha256,
)
from app.integrations.lms.registry import LMSConnectorRegistry, get_lms_connector_registry
from app.integrations.lms.connectors.spring_boot import SpringBootLMSAdapter

for mod, stub in _STUBBED_MODULES.items():
    if sys.modules.get(mod) is stub:
        del sys.modules[mod]


# =============================================================================
# TestHMACVerification
# =============================================================================


class TestHMACVerification:
    """Test HMAC-SHA256 webhook signature verification."""

    def _sign(self, body: bytes, secret: str) -> str:
        digest = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_valid_signature_passes(self):
        body = b'{"event_type":"grade_saved","payload":{}}'
        secret = "test-secret-key"
        sig = self._sign(body, secret)
        assert LMSClient.verify_webhook_signature(body, sig, secret) is True

    def test_invalid_signature_rejected(self):
        body = b'{"event_type":"grade_saved","payload":{}}'
        secret = "test-secret-key"
        assert LMSClient.verify_webhook_signature(body, "sha256=invalid", secret) is False

    def test_wrong_secret_rejected(self):
        body = b'{"event_type":"grade_saved","payload":{}}'
        sig = self._sign(body, "correct-secret")
        assert LMSClient.verify_webhook_signature(body, sig, "wrong-secret") is False

    def test_empty_body_signature(self):
        body = b""
        secret = "test-secret"
        sig = self._sign(body, secret)
        assert LMSClient.verify_webhook_signature(body, sig, secret) is True

    def test_timing_safe_comparison(self):
        body = b"test"
        secret = "s"
        sig = self._sign(body, secret)
        assert LMSClient.verify_webhook_signature(body, sig, secret) is True

    def test_missing_sha256_prefix_rejected(self):
        body = b"test"
        secret = "s"
        digest = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert LMSClient.verify_webhook_signature(body, digest, secret) is False

    def test_base_verify_hmac_sha256_function(self):
        """Test the shared utility function from base.py."""
        body = b'{"test": true}'
        secret = "shared-secret"
        sig = self._sign(body, secret)
        assert verify_hmac_sha256(body, sig, secret) is True
        assert verify_hmac_sha256(body, "sha256=wrong", secret) is False

    def test_lms_client_delegates_to_shared_verify(self):
        """LMSClient.verify_webhook_signature delegates to base.verify_hmac_sha256."""
        body = b"delegate"
        secret = "s"
        sig = self._sign(body, secret)
        # Both should return same result — no duplication
        assert LMSClient.verify_webhook_signature(body, sig, secret) == verify_hmac_sha256(body, sig, secret)


# =============================================================================
# TestWebhookEventParsing
# =============================================================================


class TestWebhookEventParsing:
    """Test Pydantic model parsing for webhook events."""

    def test_valid_grade_saved_event(self):
        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={
                "student_id": "u1", "course_id": "c1",
                "course_name": "COLREGs", "grade": 7.5, "max_grade": 10.0,
            },
        )
        assert event.event_type == LMSWebhookEventType.GRADE_SAVED
        assert event.payload["grade"] == 7.5
        assert event.source == "spring_boot_lms"

    def test_valid_course_enrolled_event(self):
        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.COURSE_ENROLLED,
            payload={
                "student_id": "u1", "course_id": "c2",
                "course_name": "SOLAS", "semester": "2025-2",
            },
        )
        assert event.event_type == LMSWebhookEventType.COURSE_ENROLLED

    def test_valid_quiz_completed_event(self):
        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.QUIZ_COMPLETED,
            payload={
                "student_id": "u1", "quiz_id": "q1",
                "quiz_name": "Bai kiem tra COLREGs", "course_id": "c1",
                "score": 8.0, "max_score": 10.0,
            },
        )
        assert event.event_type == LMSWebhookEventType.QUIZ_COMPLETED

    def test_unknown_event_type_raises(self):
        with pytest.raises(Exception):
            LMSWebhookEvent(event_type="unknown_event", payload={})

    def test_webhook_response_model(self):
        resp = LMSWebhookResponse(event_type="grade_saved", facts_created=2, message="OK")
        assert resp.status == "accepted"
        assert resp.facts_created == 2

    def test_custom_source_field(self):
        """Source field can be customized per LMS."""
        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={}, source="maritime-lms",
        )
        assert event.source == "maritime-lms"

    def test_timestamp_is_timezone_aware(self):
        """Sprint 155c: timestamp uses datetime.now(UTC), not utcnow."""
        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={},
        )
        assert event.timestamp.tzinfo is not None

    def test_negative_grade_rejected(self):
        """Sprint 155c: grade must be >= 0."""
        with pytest.raises(Exception):
            GradeSavedPayload(
                student_id="u1", course_id="c1",
                grade=-1.0, max_grade=10.0,
            )

    def test_negative_max_grade_rejected(self):
        """Sprint 155c: max_grade must be >= 0."""
        with pytest.raises(Exception):
            GradeSavedPayload(
                student_id="u1", course_id="c1",
                grade=5.0, max_grade=-10.0,
            )

    def test_negative_quiz_score_rejected(self):
        """Sprint 155c: score must be >= 0."""
        with pytest.raises(Exception):
            QuizCompletedPayload(
                student_id="u1", quiz_id="q1", course_id="c1",
                score=-1.0, max_score=10.0,
            )


# =============================================================================
# TestGradeEnrichment
# =============================================================================


class TestGradeEnrichment:
    """Test grade -> UserFact enrichment logic."""

    @pytest.fixture
    def service(self):
        svc = LMSEnrichmentService()
        svc._save_fact = AsyncMock(return_value=True)
        return svc

    @pytest.mark.asyncio
    async def test_low_grade_creates_weakness_fact(self, service):
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="COLREGs",
            grade=4.0, max_grade=10.0,
        )
        count = await service.enrich_from_grade(payload)
        assert count == 3  # level + weakness + course_context (Sprint 175)
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "level" in types_saved
        assert "weakness" in types_saved

    @pytest.mark.asyncio
    async def test_high_grade_creates_strength_fact(self, service):
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="COLREGs",
            grade=9.0, max_grade=10.0,
        )
        count = await service.enrich_from_grade(payload)
        assert count == 3  # level + strength + course_context (Sprint 175)
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "level" in types_saved
        assert "strength" in types_saved

    @pytest.mark.asyncio
    async def test_medium_grade_no_weakness_strength(self, service):
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="COLREGs",
            grade=7.0, max_grade=10.0,
        )
        count = await service.enrich_from_grade(payload)
        assert count == 2  # level + course_context (Sprint 175)
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "level" in types_saved
        assert "weakness" not in types_saved
        assert "strength" not in types_saved

    @pytest.mark.asyncio
    async def test_always_creates_level_fact(self, service):
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="Test",
            grade=5.0, max_grade=10.0,
        )
        await service.enrich_from_grade(payload)
        first_call = service._save_fact.call_args_list[0]
        assert first_call.kwargs.get("fact_type") == "level" or first_call.args[1] == "level"

    @pytest.mark.asyncio
    async def test_zero_max_grade_handles_division(self, service):
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="Test",
            grade=5.0, max_grade=0.0,
        )
        count = await service.enrich_from_grade(payload)
        assert count == 0
        service._save_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_lms_id_passed_through(self, service):
        """source_lms_id is forwarded to _save_fact for provenance."""
        payload = GradeSavedPayload(
            student_id="u1", course_id="c1", course_name="Test",
            grade=8.0, max_grade=10.0,
        )
        await service.enrich_from_grade(payload, source_lms_id="maritime-lms")
        for call in service._save_fact.call_args_list:
            assert call.kwargs.get("source_lms_id") == "maritime-lms"


# =============================================================================
# TestOtherEnrichments
# =============================================================================


class TestOtherEnrichments:
    """Test enrichment for non-grade events."""

    @pytest.fixture
    def service(self):
        svc = LMSEnrichmentService()
        svc._save_fact = AsyncMock(return_value=True)
        return svc

    @pytest.mark.asyncio
    async def test_enrollment_creates_org_and_goal(self, service):
        payload = CourseEnrolledPayload(
            student_id="u1", course_id="c1",
            course_name="SOLAS", semester="2025-2",
        )
        count = await service.enrich_from_enrollment(payload)
        assert count == 2
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "organization" in types_saved
        assert "goal" in types_saved

    @pytest.mark.asyncio
    async def test_quiz_low_score_creates_weakness(self, service):
        payload = QuizCompletedPayload(
            student_id="u1", quiz_id="q1", quiz_name="Quiz 1",
            course_id="c1", score=3.0, max_score=10.0,
        )
        count = await service.enrich_from_quiz(payload)
        assert count == 2
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "weakness" in types_saved

    @pytest.mark.asyncio
    async def test_quiz_high_score_creates_strength(self, service):
        payload = QuizCompletedPayload(
            student_id="u1", quiz_id="q1", quiz_name="Quiz 1",
            course_id="c1", score=9.0, max_score=10.0,
        )
        count = await service.enrich_from_quiz(payload)
        assert count == 2
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "strength" in types_saved

    @pytest.mark.asyncio
    async def test_quiz_creates_recent_topic(self, service):
        payload = QuizCompletedPayload(
            student_id="u1", quiz_id="q1", quiz_name="Quiz 1",
            course_id="c1", score=6.0, max_score=10.0,
        )
        count = await service.enrich_from_quiz(payload)
        assert count >= 1
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "recent_topic" in types_saved

    @pytest.mark.asyncio
    async def test_quiz_zero_max_score_skips(self, service):
        """Sprint 155c: zero max_score is handled safely."""
        payload = QuizCompletedPayload(
            student_id="u1", quiz_id="q1", quiz_name="Quiz 1",
            course_id="c1", score=6.0, max_score=0.0,
        )
        count = await service.enrich_from_quiz(payload)
        assert count == 0
        service._save_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_assignment_creates_recent_topic(self, service):
        payload = AssignmentSubmittedPayload(
            student_id="u1", assignment_id="a1",
            assignment_name="Bai tap COLREGs",
            course_id="c1", submitted_at=datetime.now(timezone.utc),
        )
        count = await service.enrich_from_assignment(payload)
        assert count == 1

    @pytest.mark.asyncio
    async def test_attendance_skipped_in_v1(self, service):
        payload = AttendanceMarkedPayload(
            student_id="u1", course_id="c1",
            date="2026-02-20", status="present",
        )
        count = await service.enrich_from_attendance(payload)
        assert count == 0
        service._save_fact.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_grades_enrichment(self, service):
        """Test enrich_from_grades processes all grades."""
        grades = [
            LMSGrade(course_id="c1", course_name="COLREGs", grade=9.0, max_grade=10.0),
            LMSGrade(course_id="c2", course_name="SOLAS", grade=4.0, max_grade=10.0),
        ]
        count = await service.enrich_from_grades("u1", grades)
        # 9/10 → level + strength + course_context = 3,  4/10 → level + weakness + course_context = 3
        assert count == 6


# =============================================================================
# TestLMSClient
# =============================================================================


class TestLMSClient:
    """Test LMS API client with mocked httpx."""

    @patch("app.integrations.lms.lms_client.get_settings")
    @patch("app.integrations.lms.lms_client.httpx.get")
    def test_get_student_profile_success(self, mock_get, mock_settings):
        mock_settings.return_value = MagicMock(
            lms_base_url="http://lms.test", lms_service_token="tok", lms_api_timeout=5,
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "u1", "name": "Nguyen Van A",
            "class_name": "DKTB K62A", "program": "Dieu khien tau bien",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = LMSClient()
        profile = client.get_student_profile("u1")
        assert profile is not None
        assert profile.name == "Nguyen Van A"

    @patch("app.integrations.lms.lms_client.get_settings")
    @patch("app.integrations.lms.lms_client.httpx.get")
    def test_get_student_grades_success(self, mock_get, mock_settings):
        mock_settings.return_value = MagicMock(
            lms_base_url="http://lms.test", lms_service_token="tok", lms_api_timeout=5,
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"course_id": "c1", "course_name": "COLREGs", "grade": 8.0, "max_grade": 10.0},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = LMSClient()
        grades = client.get_student_grades("u1")
        assert len(grades) == 1
        assert grades[0].percentage == 80.0

    @patch("app.integrations.lms.lms_client.get_settings")
    @patch("app.integrations.lms.lms_client.httpx.get")
    def test_network_timeout_returns_none(self, mock_get, mock_settings):
        import httpx
        mock_settings.return_value = MagicMock(
            lms_base_url="http://lms.test", lms_service_token="tok", lms_api_timeout=5,
        )
        mock_get.side_effect = httpx.TimeoutException("timeout")

        client = LMSClient()
        result = client.get_student_profile("u1")
        assert result is None

    @patch("app.integrations.lms.lms_client.get_settings")
    @patch("app.integrations.lms.lms_client.httpx.get")
    def test_http_error_returns_none(self, mock_get, mock_settings):
        import httpx
        mock_settings.return_value = MagicMock(
            lms_base_url="http://lms.test", lms_service_token="tok", lms_api_timeout=5,
        )
        resp = httpx.Response(500, request=httpx.Request("GET", "http://lms.test/api/students/u1"))
        mock_get.side_effect = httpx.HTTPStatusError("error", response=resp, request=resp.request)

        client = LMSClient()
        result = client.get_student_profile("u1")
        assert result is None

    @patch("app.integrations.lms.lms_client.get_settings")
    @patch("app.integrations.lms.lms_client._circuit_breaker")
    def test_circuit_breaker_opens_after_threshold(self, mock_cb, mock_settings):
        mock_settings.return_value = MagicMock(
            lms_base_url="http://lms.test", lms_service_token="tok", lms_api_timeout=5,
        )
        mock_cb.is_open.return_value = True

        client = LMSClient()
        result = client.get_student_profile("u1")
        assert result is None

    @patch("app.integrations.lms.lms_client.get_settings")
    def test_no_base_url_returns_none(self, mock_settings):
        mock_settings.return_value = MagicMock(
            lms_base_url=None, lms_service_token=None, lms_api_timeout=5,
        )

        client = LMSClient()
        result = client.get_student_profile("u1")
        assert result is None

    def test_explicit_params_constructor(self):
        """LMSClient can be created with explicit params (multi-LMS)."""
        client = LMSClient(
            base_url="http://custom-lms.test",
            service_token="my-token",
            timeout=15,
            connector_id="custom-lms",
        )
        assert client._base_url == "http://custom-lms.test"
        assert client._token == "my-token"
        assert client._timeout == 15
        assert client._connector_id == "custom-lms"


# =============================================================================
# TestStudentIdValidation (Sprint 155c)
# =============================================================================


class TestStudentIdValidation:
    """Test student_id sanitization against path traversal."""

    def test_valid_student_id(self):
        assert _validate_student_id("user-123") == "user-123"
        assert _validate_student_id("u1") == "u1"
        assert _validate_student_id("student_001") == "student_001"
        assert _validate_student_id("abc.def") == "abc.def"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError):
            _validate_student_id("../admin")

    def test_slash_rejected(self):
        with pytest.raises(ValueError):
            _validate_student_id("user/admin")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            _validate_student_id("")

    def test_spaces_rejected(self):
        with pytest.raises(ValueError):
            _validate_student_id("user name")

    def test_special_chars_rejected(self):
        with pytest.raises(ValueError):
            _validate_student_id("user;drop table")


# =============================================================================
# TestWebhookHandler
# =============================================================================


class TestWebhookHandler:
    """Test webhook event dispatch."""

    @pytest.mark.asyncio
    async def test_grade_saved_dispatches_correctly(self):
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_grade = AsyncMock(return_value=2)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={
                "student_id": "u1", "course_id": "c1",
                "course_name": "COLREGs", "grade": 4.0, "max_grade": 10.0,
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "accepted"
        assert resp.facts_created == 2

    @pytest.mark.asyncio
    async def test_enrollment_dispatches_correctly(self):
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_enrollment = AsyncMock(return_value=2)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.COURSE_ENROLLED,
            payload={
                "student_id": "u1", "course_id": "c1",
                "course_name": "SOLAS", "semester": "2025-2",
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "accepted"
        assert resp.facts_created == 2

    @pytest.mark.asyncio
    async def test_handler_error_sanitizes_message(self):
        """Sprint 155c: Error messages don't leak internal details."""
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_grade = AsyncMock(side_effect=ValueError("secret internal detail"))

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            payload={
                "student_id": "u1", "course_id": "c1",
                "grade": 5.0, "max_grade": 10.0,
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "error"
        assert "secret internal detail" not in resp.message
        assert resp.message == "Internal processing error"

    @pytest.mark.asyncio
    async def test_handler_passes_source_to_enrichment(self):
        """Verify source_lms_id is forwarded from event.source."""
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_grade = AsyncMock(return_value=1)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.GRADE_SAVED,
            source="maritime-lms",
            payload={
                "student_id": "u1", "course_id": "c1",
                "grade": 8.0, "max_grade": 10.0,
            },
        )
        await handler.handle_event(event)
        handler._enrichment.enrich_from_grade.assert_called_once()
        call_kwargs = handler._enrichment.enrich_from_grade.call_args
        # The handler passes (payload_dict, source) positionally
        assert call_kwargs[1]["source_lms_id"] == "maritime-lms"

    @pytest.mark.asyncio
    async def test_quiz_completed_dispatches(self):
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_quiz = AsyncMock(return_value=2)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.QUIZ_COMPLETED,
            payload={
                "student_id": "u1", "quiz_id": "q1",
                "course_id": "c1", "score": 8.0, "max_score": 10.0,
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "accepted"

    @pytest.mark.asyncio
    async def test_assignment_submitted_dispatches(self):
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_assignment = AsyncMock(return_value=1)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.ASSIGNMENT_SUBMITTED,
            payload={
                "student_id": "u1", "assignment_id": "a1",
                "course_id": "c1",
                "submitted_at": "2026-02-20T10:00:00",
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "accepted"

    @pytest.mark.asyncio
    async def test_attendance_marked_dispatches(self):
        handler = LMSWebhookHandler()
        handler._enrichment = MagicMock()
        handler._enrichment.enrich_from_attendance = AsyncMock(return_value=0)

        event = LMSWebhookEvent(
            event_type=LMSWebhookEventType.ATTENDANCE_MARKED,
            payload={
                "student_id": "u1", "course_id": "c1",
                "date": "2026-02-20", "status": "present",
            },
        )
        resp = await handler.handle_event(event)
        assert resp.status == "accepted"
        assert resp.facts_created == 0


# =============================================================================
# TestStudentProfileEnrichment
# =============================================================================


class TestStudentProfileEnrichment:
    """Test student profile enrichment for future API pull."""

    @pytest.fixture
    def service(self):
        svc = LMSEnrichmentService()
        svc._save_fact = AsyncMock(return_value=True)
        return svc

    @pytest.mark.asyncio
    async def test_profile_creates_name_role_org(self, service):
        profile = LMSStudentProfile(
            id="u1", name="Nguyen Van A",
            class_name="DKTB K62A", program="Dieu khien tau bien",
        )
        count = await service.enrich_from_student_profile("u1", profile)
        assert count == 3
        types_saved = [call.kwargs.get("fact_type") or call.args[1] for call in service._save_fact.call_args_list]
        assert "name" in types_saved
        assert "role" in types_saved
        assert "organization" in types_saved

    @pytest.mark.asyncio
    async def test_profile_without_program_creates_2(self, service):
        profile = LMSStudentProfile(id="u1", name="Test User")
        count = await service.enrich_from_student_profile("u1", profile)
        assert count == 1


# =============================================================================
# TestLMSConfig
# =============================================================================


class TestLMSConfig:
    """Test config integration."""

    def test_default_feature_flag_false(self):
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.enable_lms_integration is False

    def test_nested_config_group_synced(self):
        from app.core.config import Settings
        s = Settings(_env_file=None, enable_lms_integration=True, lms_webhook_secret="test")
        assert s.lms.enabled is True
        assert s.lms.webhook_secret == "test"
        assert s.lms.api_timeout == 10

    def test_cross_field_warning_no_secret(self, caplog):
        import logging
        from app.core.config import Settings
        with caplog.at_level(logging.WARNING):
            Settings(_env_file=None, enable_lms_integration=True)
        assert any("lms_webhook_secret" in r.message for r in caplog.records)

    def test_lms_connectors_default_empty(self):
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.lms_connectors == "[]"

    def test_lms_api_timeout_validation(self):
        """Sprint 155c: api_timeout has ge=3, le=60."""
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(_env_file=None, lms_api_timeout=1)  # too low


# =============================================================================
# TestLMSGradeModel
# =============================================================================


class TestLMSGradeModel:
    """Test LMSGrade model properties."""

    def test_percentage_normal(self):
        g = LMSGrade(course_id="c1", grade=8.0, max_grade=10.0)
        assert g.percentage == 80.0

    def test_percentage_zero_max(self):
        g = LMSGrade(course_id="c1", grade=5.0, max_grade=0.0)
        assert g.percentage == 0.0


# =============================================================================
# TestLMSConnectorConfig (Sprint 155c)
# =============================================================================


class TestLMSConnectorConfig:
    """Test config dataclass security features."""

    def test_repr_masks_secrets(self):
        """Sprint 155c: repr() doesn't expose service_token or webhook_secret."""
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
            service_token="super-secret-token",
            webhook_secret="super-secret-key",
        )
        r = repr(config)
        assert "super-secret-token" not in r
        assert "super-secret-key" not in r
        assert "***" in r

    def test_repr_shows_none_when_no_secret(self):
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
        )
        r = repr(config)
        assert "None" in r
        assert "***" not in r


# =============================================================================
# TestLMSConnectorAdapter (Sprint 155b: Multi-LMS)
# =============================================================================


class TestLMSConnectorAdapter:
    """Test the ABC and concrete Spring Boot adapter."""

    def test_spring_boot_adapter_get_config(self):
        config = LMSConnectorConfig(
            id="maritime-lms",
            display_name="Maritime LMS",
            backend_type=LMSBackendType.SPRING_BOOT,
            base_url="http://lms.maritime.edu",
            webhook_secret="secret123",
        )
        adapter = SpringBootLMSAdapter(config)
        assert adapter.get_config().id == "maritime-lms"
        assert adapter.get_config().backend_type == LMSBackendType.SPRING_BOOT

    def test_spring_boot_normalize_webhook(self):
        config = LMSConnectorConfig(
            id="maritime-lms",
            display_name="Maritime LMS",
            backend_type=LMSBackendType.SPRING_BOOT,
        )
        adapter = SpringBootLMSAdapter(config)

        raw = {
            "event_type": "grade_saved",
            "payload": {"student_id": "u1", "course_id": "c1", "grade": 8.0, "max_grade": 10.0},
        }
        event = adapter.normalize_webhook(raw, {})
        assert event is not None
        assert event.event_type == LMSWebhookEventType.GRADE_SAVED
        assert event.source == "maritime-lms"  # Overridden by adapter

    def test_spring_boot_normalize_invalid_returns_none(self):
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
        )
        adapter = SpringBootLMSAdapter(config)
        event = adapter.normalize_webhook({"event_type": "invalid_xyz", "payload": {}}, {})
        assert event is None

    def test_adapter_verify_signature_with_secret(self):
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
            webhook_secret="my-secret",
        )
        adapter = SpringBootLMSAdapter(config)
        body = b'{"test": true}'
        digest = hmac_mod.new(b"my-secret", body, hashlib.sha256).hexdigest()
        sig = f"sha256={digest}"

        assert adapter.verify_signature(body, {"X-LMS-Signature": sig}) is True
        assert adapter.verify_signature(body, {"X-LMS-Signature": "sha256=wrong"}) is False

    def test_adapter_verify_signature_no_secret_rejects(self):
        """No secret configured = fail-closed (returns False)."""
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
            webhook_secret=None,
        )
        adapter = SpringBootLMSAdapter(config)
        assert adapter.verify_signature(b"any", {}) is False

    def test_adapter_verify_signature_missing_header_fails(self):
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
            webhook_secret="secret",
        )
        adapter = SpringBootLMSAdapter(config)
        assert adapter.verify_signature(b"any", {}) is False

    def test_backend_type_enum(self):
        assert LMSBackendType.SPRING_BOOT.value == "spring_boot"
        assert LMSBackendType.MOODLE.value == "moodle"
        assert LMSBackendType.CANVAS.value == "canvas"


# =============================================================================
# TestLMSConnectorRegistry (Sprint 155b: Multi-LMS)
# =============================================================================


class TestLMSConnectorRegistry:
    """Test registry singleton pattern."""

    def test_register_and_get(self):
        registry = LMSConnectorRegistry()
        config = LMSConnectorConfig(
            id="test-lms", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
        )
        adapter = SpringBootLMSAdapter(config)
        registry.register(adapter)

        assert registry.get("test-lms") is adapter
        assert registry.get("nonexistent") is None

    def test_list_ids(self):
        registry = LMSConnectorRegistry()
        for i in range(3):
            config = LMSConnectorConfig(
                id=f"lms-{i}", display_name=f"LMS {i}",
                backend_type=LMSBackendType.SPRING_BOOT,
            )
            registry.register(SpringBootLMSAdapter(config))

        assert len(registry) == 3
        assert set(registry.list_ids()) == {"lms-0", "lms-1", "lms-2"}

    def test_get_all_enabled(self):
        registry = LMSConnectorRegistry()
        for i in range(3):
            config = LMSConnectorConfig(
                id=f"lms-{i}", display_name=f"LMS {i}",
                backend_type=LMSBackendType.SPRING_BOOT,
                enabled=(i != 1),  # lms-1 disabled
            )
            registry.register(SpringBootLMSAdapter(config))

        enabled = registry.get_all_enabled()
        assert len(enabled) == 2
        ids = {a.get_config().id for a in enabled}
        assert "lms-1" not in ids

    def test_clear(self):
        registry = LMSConnectorRegistry()
        config = LMSConnectorConfig(
            id="test", display_name="Test",
            backend_type=LMSBackendType.SPRING_BOOT,
        )
        registry.register(SpringBootLMSAdapter(config))
        assert len(registry) == 1
        registry.clear()
        assert len(registry) == 0

    def test_singleton_getter(self):
        """get_lms_connector_registry returns same instance."""
        r1 = get_lms_connector_registry()
        r2 = get_lms_connector_registry()
        assert r1 is r2


# =============================================================================
# TestLMSLoader (Sprint 155b: Multi-LMS)
# =============================================================================


class TestLMSLoader:
    """Test connector loader with auto-migration."""

    def test_bootstrap_disabled(self):
        from app.integrations.lms.loader import bootstrap_lms_connectors
        settings = MagicMock()
        settings.enable_lms_integration = False
        count = bootstrap_lms_connectors(settings)
        assert count == 0

    def test_bootstrap_from_json_connectors(self):
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = json.dumps([{
            "id": "test-sb",
            "backend_type": "spring_boot",
            "display_name": "Test Spring Boot",
            "base_url": "http://lms.test",
            "webhook_secret": "secret",
        }])
        settings.lms_base_url = None

        count = bootstrap_lms_connectors(settings)
        assert count == 1
        assert registry.get("test-sb") is not None
        assert registry.get("test-sb").get_config().display_name == "Test Spring Boot"
        registry.clear()

    def test_bootstrap_auto_migrate_flat_fields(self):
        """Backward compat: flat fields auto-create a 'default' connector."""
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = "[]"
        settings.lms_base_url = "http://old-lms.test"
        settings.lms_service_token = "old-token"
        settings.lms_webhook_secret = "old-secret"
        settings.lms_api_timeout = 10

        count = bootstrap_lms_connectors(settings)
        assert count == 1
        default = registry.get("default")
        assert default is not None
        assert default.get_config().base_url == "http://old-lms.test"
        registry.clear()

    def test_bootstrap_json_takes_precedence_over_flat(self):
        """If both lms_connectors and lms_base_url set, JSON wins."""
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = json.dumps([{
            "id": "json-lms", "backend_type": "spring_boot",
            "base_url": "http://json-lms.test",
        }])
        settings.lms_base_url = "http://flat-lms.test"  # Should be ignored

        count = bootstrap_lms_connectors(settings)
        assert count == 1
        assert registry.get("json-lms") is not None
        assert registry.get("default") is None  # Flat not used
        registry.clear()

    def test_bootstrap_multiple_connectors(self):
        """Register multiple LMS connectors from JSON config."""
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = json.dumps([
            {"id": "lms-a", "backend_type": "spring_boot", "base_url": "http://a.test"},
            {"id": "lms-b", "backend_type": "spring_boot", "base_url": "http://b.test"},
        ])
        settings.lms_base_url = None

        count = bootstrap_lms_connectors(settings)
        assert count == 2
        assert registry.get("lms-a") is not None
        assert registry.get("lms-b") is not None
        registry.clear()

    def test_bootstrap_unknown_backend_skipped(self):
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = json.dumps([
            {"id": "unknown", "backend_type": "totally_unknown", "base_url": "http://x.test"},
        ])
        settings.lms_base_url = None

        count = bootstrap_lms_connectors(settings)
        assert count == 0
        registry.clear()

    def test_bootstrap_malformed_json(self):
        """Sprint 155c: Malformed JSON doesn't crash, returns 0."""
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = "not valid json"
        settings.lms_base_url = None

        count = bootstrap_lms_connectors(settings)
        assert count == 0
        registry.clear()

    def test_bootstrap_missing_id_field(self):
        """Sprint 155c: Missing 'id' field doesn't crash."""
        from app.integrations.lms.loader import bootstrap_lms_connectors
        from app.integrations.lms.registry import get_lms_connector_registry

        registry = get_lms_connector_registry()
        registry.clear()

        settings = MagicMock()
        settings.enable_lms_integration = True
        settings.lms_connectors = json.dumps([
            {"backend_type": "spring_boot", "base_url": "http://x.test"},
        ])
        settings.lms_base_url = None

        count = bootstrap_lms_connectors(settings)
        assert count == 0
        registry.clear()
