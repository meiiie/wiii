"""
LMS Connector Adapter — Abstract Base Class + Data Models

Sprint 155b: Multi-LMS Plugin Architecture

Pattern: Mirrors SearchPlatformAdapter (app/engine/search_platforms/base.py)
and DomainPlugin (app/domains/base.py). Each LMS system implements
LMSConnectorAdapter to normalize its webhook events and API responses.
"""

import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from app.integrations.lms.models import (
    LMSGrade,
    LMSStudentProfile,
    LMSUpcomingAssignment,
    LMSWebhookEvent,
)

logger = logging.getLogger(__name__)


class LMSBackendType(Enum):
    """Backend technology / LMS platform type."""
    SPRING_BOOT = "spring_boot"      # Custom Spring Boot LMS (first impl)
    MOODLE = "moodle"                # Moodle LMS
    CANVAS = "canvas"                # Instructure Canvas
    BLACKBOARD = "blackboard"        # Blackboard Learn
    CUSTOM = "custom"                # Other custom LMS


@dataclass
class LMSConnectorConfig:
    """Configuration for a single LMS connector instance."""
    id: str                                     # e.g. "maritime-lms", "moodle-hanghoi"
    display_name: str                           # e.g. "Maritime University LMS"
    backend_type: LMSBackendType
    base_url: str = ""                          # REST API base URL
    service_token: Optional[str] = None         # Service account token
    webhook_secret: Optional[str] = None        # HMAC secret for incoming webhooks
    api_timeout: int = 10                       # HTTP timeout seconds
    signature_header: str = "X-LMS-Signature"   # Header carrying webhook signature
    auth_type: str = "bearer_token"             # bearer_token | basic | oauth2
    enabled: bool = True
    extra: Dict[str, str] = field(default_factory=dict)  # Platform-specific config

    def __repr__(self) -> str:
        """Mask secrets in repr to prevent accidental logging."""
        token = "***" if self.service_token else "None"
        secret = "***" if self.webhook_secret else "None"
        return (
            f"LMSConnectorConfig(id={self.id!r}, display_name={self.display_name!r}, "
            f"backend_type={self.backend_type!r}, base_url={self.base_url!r}, "
            f"service_token={token}, webhook_secret={secret}, enabled={self.enabled})"
        )


class LMSConnectorAdapter(ABC):
    """
    Abstract base class for LMS connectors.

    Subclasses must implement:
    - get_config() → LMSConnectorConfig
    - normalize_webhook(raw_payload, headers) → Optional[LMSWebhookEvent]

    Optional overrides:
    - verify_signature(payload_bytes, headers) → bool
    - get_student_profile(student_id) → Optional[LMSStudentProfile]
    - get_student_grades(student_id) → List[LMSGrade]
    - get_upcoming_assignments(student_id) → List[LMSUpcomingAssignment]
    """

    @abstractmethod
    def get_config(self) -> LMSConnectorConfig:
        """Return connector configuration."""
        ...

    @abstractmethod
    def normalize_webhook(
        self, raw_payload: dict, headers: dict
    ) -> Optional[LMSWebhookEvent]:
        """Translate LMS-native webhook payload into canonical LMSWebhookEvent.

        This is the Anti-Corruption Layer — each LMS has a different webhook
        format. The adapter normalizes it to our canonical model.

        Returns None if the payload should be ignored.
        """
        ...

    def verify_signature(self, payload_bytes: bytes, headers: dict) -> bool:
        """Verify webhook signature. Default: HMAC-SHA256.

        Override for LMS platforms that use a different signing scheme.
        """
        config = self.get_config()
        if not config.webhook_secret:
            return True  # No secret configured = skip verification
        signature = headers.get(config.signature_header, "")
        if not signature:
            return False
        return verify_hmac_sha256(payload_bytes, signature, config.webhook_secret)

    def get_student_profile(self, student_id: str) -> Optional[LMSStudentProfile]:
        """Fetch student profile from LMS API. Override for pull support."""
        return None

    def get_student_grades(self, student_id: str) -> List[LMSGrade]:
        """Fetch student grades from LMS API. Override for pull support."""
        return []

    def get_upcoming_assignments(self, student_id: str) -> List[LMSUpcomingAssignment]:
        """Fetch upcoming assignments from LMS API. Override for pull support."""
        return []


def verify_hmac_sha256(payload_bytes: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature (shared utility).

    Args:
        payload_bytes: Raw request body bytes
        signature: Value of signature header (format: "sha256=<hex>")
        secret: Shared secret key

    Returns:
        True if signature is valid
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    expected_sig = f"sha256={expected}"
    return hmac.compare_digest(expected_sig, signature)
