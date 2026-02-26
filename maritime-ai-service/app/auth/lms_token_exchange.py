"""
Sprint 159: "Cầu Nối Trực Tiếp" — LMS Backend Token Exchange.

Core service for HMAC-signed backend-to-backend token exchange.
Spring Boot LMS sends signed request → Wiii returns JWT token pair.

Security:
  - HMAC-SHA256 signature verification (reuses app.integrations.lms.base)
  - Replay protection via timestamp validation
  - Identity federation via find_or_create_by_provider (Sprint 158)
"""
import json
import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role mapping: LMS roles → Wiii roles
# ---------------------------------------------------------------------------
_LMS_ROLE_MAP = {
    # Teacher variants
    "instructor": "teacher",
    "professor": "teacher",
    "lecturer": "teacher",
    "ta": "teacher",
    "teaching_assistant": "teacher",
    "teacher": "teacher",
    # Admin variants
    "admin": "admin",
    "administrator": "admin",
    "manager": "admin",
    # Student is default
    "student": "student",
    "learner": "student",
}


def map_lms_role(lms_role: Optional[str]) -> str:
    """Map an LMS role string to a Wiii role. Unknown roles default to 'student'."""
    if not lms_role:
        return "student"
    return _LMS_ROLE_MAP.get(lms_role.lower().strip(), "student")


# ---------------------------------------------------------------------------
# Connector secret resolution (3-level fallback)
# ---------------------------------------------------------------------------

def _resolve_connector_secret(connector_id: Optional[str]) -> Optional[str]:
    """
    Resolve the HMAC secret for a given connector.

    Fallback chain:
    1. settings.lms_connectors JSON array (by connector_id)
    2. LMSConnectorRegistry singleton (if available)
    3. settings.lms_webhook_secret (flat single-LMS compat)
    """
    # 1. JSON connectors config
    if connector_id:
        try:
            connectors = json.loads(settings.lms_connectors or "[]")
            for c in connectors:
                if c.get("id") == connector_id:
                    secret = c.get("webhook_secret")
                    if secret:
                        return secret
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Registry fallback
        try:
            from app.integrations.lms.base import LMSConnectorRegistry
            registry = LMSConnectorRegistry.get_instance()
            config = registry.get_connector(connector_id)
            if config and config.webhook_secret:
                return config.webhook_secret
        except Exception:
            pass

    # 3. Flat secret fallback
    return settings.lms_webhook_secret


# ---------------------------------------------------------------------------
# HMAC validation
# ---------------------------------------------------------------------------

def validate_lms_signature(
    connector_id: Optional[str],
    body_bytes: bytes,
    signature: str,
) -> bool:
    """
    Validate HMAC-SHA256 signature for an LMS token exchange request.

    Args:
        connector_id: LMS connector identifier (for secret lookup)
        body_bytes: Raw request body
        signature: Value of X-LMS-Signature header (format: "sha256=<hex>")

    Returns:
        True if valid.

    Raises:
        ValueError if no secret is configured or signature format is wrong.
    """
    secret = _resolve_connector_secret(connector_id)
    if not secret:
        raise ValueError(f"No HMAC secret configured for connector '{connector_id}'")

    if not signature:
        raise ValueError("Missing signature")

    from app.integrations.lms.base import verify_hmac_sha256
    return verify_hmac_sha256(body_bytes, signature, secret)


# ---------------------------------------------------------------------------
# Timestamp / replay protection
# ---------------------------------------------------------------------------

def validate_request_timestamp(timestamp: Optional[int]) -> bool:
    """
    Validate that the request timestamp is within max_age window.

    Args:
        timestamp: Unix epoch seconds from the request body. None = skip check.

    Returns:
        True if valid (or timestamp is None for backward compat).

    Raises:
        ValueError if timestamp is too old or too far in the future.
    """
    if timestamp is None:
        if settings.environment == "production":
            raise ValueError("timestamp is required in production (replay protection)")
        logger.warning("Token exchange without timestamp — allowed in dev only")
        return True

    now = int(time.time())
    max_age = settings.lms_token_exchange_max_age
    diff = abs(now - timestamp)

    if diff > max_age:
        raise ValueError(
            f"Request timestamp too far from server time: {diff}s difference (max {max_age}s)"
        )
    return True


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------

async def exchange_lms_token(
    connector_id: str,
    lms_user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> dict:
    """
    Exchange LMS user credentials for a Wiii JWT token pair.

    1. find_or_create_by_provider("lms", lms_user_id, issuer=connector_id)
    2. Optional: ensure org membership
    3. create_token_pair(auth_method="lms")

    Returns dict with: access_token, refresh_token, token_type, expires_in, user
    """
    from app.auth.user_service import find_or_create_by_provider
    from app.auth.token_service import create_token_pair

    wiii_role = map_lms_role(role)

    # Find or create user
    user = await find_or_create_by_provider(
        provider="lms",
        provider_sub=lms_user_id,
        provider_issuer=connector_id,
        email=email,
        name=name,
        role=wiii_role,
    )
    assert user is not None  # auto_create=True (default)

    # Ensure org membership if specified
    if organization_id:
        await _ensure_org_membership(user["id"], organization_id)

    # Create token pair
    token_pair = await create_token_pair(
        user_id=user["id"],
        email=user.get("email"),
        name=user.get("name"),
        role=user.get("role", wiii_role),
        auth_method="lms",
    )

    return {
        "access_token": token_pair.access_token,
        "refresh_token": token_pair.refresh_token,
        "token_type": "bearer",
        "expires_in": token_pair.expires_in,
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role", wiii_role),
        },
    }


async def _ensure_org_membership(user_id: str, organization_id: str) -> None:
    """Add user to organization if not already a member. Safe no-op on conflict."""
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_organizations (user_id, organization_id, role, joined_at)
                VALUES ($1, $2, 'member', NOW())
                ON CONFLICT (user_id, organization_id) DO NOTHING
                """,
                user_id, organization_id,
            )
    except Exception:
        logger.warning(
            "Could not ensure org membership for user %s in org %s",
            user_id, organization_id,
        )
