"""
Sprint 220c: External identity resolver — shared helper for LMS context.

Resolves (lms_user_id, connector_id) from a Wiii user UUID, using the
user_identities table populated during LMS token exchange.

Usage:
    lms_user_id, connector_id = await resolve_lms_identity(user_id, org_id)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def resolve_lms_identity(
    user_id: str,
    org_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve (lms_user_id, connector_id) for a Wiii user.

    Strategy:
    1. If org_id → look up OrgAIConfig.external_connector_id as issuer filter
    2. find_external_identity(user_id, "lms", connector_id)
    3. Return (provider_sub, resolved_connector_id)

    Returns (None, None) if user has no linked LMS identity.
    """
    connector_id: Optional[str] = None

    # Step 1: Get org-specific connector if org context is available
    if org_id:
        try:
            from app.core.org_settings import get_effective_settings
            org_settings = get_effective_settings(org_id)
            if org_settings and org_settings.ai_config:
                connector_id = org_settings.ai_config.external_connector_id
        except Exception as e:
            logger.debug("[LMS-ID] Failed to get org settings for %s: %s", org_id, e)

    # Step 2: Reverse-lookup in user_identities
    try:
        from app.auth.user_service import find_external_identity
        identity = await find_external_identity(
            user_id=user_id,
            provider="lms",
            provider_issuer=connector_id,
        )
        if identity:
            lms_user_id = identity.get("provider_sub")
            resolved_connector = identity.get("provider_issuer") or connector_id
            logger.debug(
                "[LMS-ID] Resolved user %s → lms_user_id=%s, connector=%s",
                user_id, lms_user_id, resolved_connector,
            )
            return lms_user_id, resolved_connector
    except Exception as e:
        logger.debug("[LMS-ID] Reverse-lookup failed for user %s: %s", user_id, e)

    return None, None
