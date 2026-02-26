"""
Identity Resolver — Sprint 174: Cross-Platform Identity

Thin facade over find_or_create_by_provider() that maps platform sender IDs
to canonical Wiii user IDs. When enable_cross_platform_identity=False (default),
falls back to legacy "{channel}_{sender_id}" format for zero breaking changes.

Key design:
- No new DB tables or migrations needed
- user_identities.provider is TEXT, accepts "messenger"/"zalo" as-is
- email_verified=False by default — messaging platforms don't provide email
- On error, gracefully falls back to legacy format (never blocks the webhook)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def resolve_user_id(
    channel_type: str,
    platform_sender_id: str,
    display_name: Optional[str] = None,
) -> str:
    """Resolve a platform-specific sender ID to a canonical Wiii user ID.

    Args:
        channel_type: Platform identifier ("messenger", "zalo", "telegram", "web")
        platform_sender_id: Raw sender ID from the platform
        display_name: Optional display name from the platform (for new users)

    Returns:
        Canonical user ID (UUID string) when cross-platform identity is enabled,
        or legacy "{channel_type}_{platform_sender_id}" format when disabled.
    """
    from app.core.config import settings

    legacy_id = f"{channel_type}_{platform_sender_id}"

    if not settings.enable_cross_platform_identity:
        return legacy_id

    try:
        from app.auth.user_service import find_or_create_by_provider

        user = await find_or_create_by_provider(
            provider=channel_type,
            provider_sub=platform_sender_id,
            email=None,
            name=display_name,
            auto_create=True,
            email_verified=False,
        )

        if user:
            uid = user["id"]
            logger.info(
                "[IDENTITY] Resolved %s/%s → canonical %s",
                channel_type, platform_sender_id, uid,
            )
            return uid

        logger.warning(
            "[IDENTITY] find_or_create_by_provider returned None for %s/%s — using legacy ID",
            channel_type, platform_sender_id,
        )
        return legacy_id

    except Exception as e:
        logger.error(
            "[IDENTITY] Failed to resolve %s/%s: %s — using legacy ID",
            channel_type, platform_sender_id, e,
        )
        return legacy_id
