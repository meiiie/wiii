"""
Sprint 178: Runtime feature flag service.

30s in-memory cache. Precedence: org_override > global_override > config.py default.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL = 30  # seconds
_cache: dict = {}
_cache_ts: float = 0.0


def _is_cache_valid() -> bool:
    return bool(_cache) and (time.monotonic() - _cache_ts) < _CACHE_TTL


def invalidate_cache(key: Optional[str] = None) -> None:
    """Clear cache: specific key or entire cache."""
    global _cache, _cache_ts
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
        _cache_ts = 0.0


async def _load_db_flags(org_id: Optional[str] = None) -> dict:
    """Load all flags from DB, optionally filtered by org."""
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            if org_id:
                rows = await conn.fetch(
                    "SELECT key, value, flag_type, description, owner, organization_id, expires_at "
                    "FROM admin_feature_flags "
                    "WHERE organization_id IS NULL OR organization_id = $1",
                    org_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT key, value, flag_type, description, owner, organization_id, expires_at "
                    "FROM admin_feature_flags WHERE organization_id IS NULL"
                )
        result = {}
        now = datetime.now(timezone.utc)
        for r in rows:
            # Skip expired flags
            if r["expires_at"] and r["expires_at"] < now:
                continue
            rkey = f"{r['key']}:{r['organization_id'] or ''}"
            result[rkey] = dict(r)
        return result
    except Exception as e:
        logger.warning("Failed to load feature flags from DB: %s", e)
        return {}


async def get_flag(key: str, org_id: Optional[str] = None) -> bool:
    """Get effective flag value. Precedence: org_override > global_override > config.py."""
    global _cache, _cache_ts

    from app.core.config import settings

    # Try cache first
    if not _is_cache_valid():
        _cache = await _load_db_flags()
        _cache_ts = time.monotonic()

    # Check org-specific override
    if org_id:
        org_key = f"{key}:{org_id}"
        if org_key in _cache:
            return _cache[org_key]["value"]

    # Check global override
    global_key = f"{key}:"
    if global_key in _cache:
        return _cache[global_key]["value"]

    # Fallback to config.py
    return getattr(settings, key, False)


async def set_flag(
    key: str,
    value: bool,
    flag_type: str = "release",
    owner: Optional[str] = None,
    description: Optional[str] = None,
    org_id: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> dict:
    """UPSERT flag override in DB. Invalidates cache. Returns the saved record."""
    from app.core.database import get_asyncpg_pool

    pool = await get_asyncpg_pool()
    expires_val = None
    if expires_at:
        expires_val = datetime.fromisoformat(expires_at)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO admin_feature_flags (key, value, flag_type, description, owner, organization_id, expires_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT ON CONSTRAINT uq_feature_flag_key_org
            DO UPDATE SET value = $2, flag_type = $3, description = COALESCE($4, admin_feature_flags.description),
                          owner = COALESCE($5, admin_feature_flags.owner), expires_at = $7, updated_at = NOW()
            RETURNING key, value, flag_type, description, owner, organization_id, expires_at, created_at, updated_at
            """,
            key,
            value,
            flag_type,
            description,
            owner,
            org_id,
            expires_val,
        )

    invalidate_cache()

    return {
        "key": row["key"],
        "value": row["value"],
        "flag_type": row["flag_type"],
        "description": row["description"],
        "owner": row["owner"],
        "organization_id": row["organization_id"],
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
    }


async def delete_flag(key: str, org_id: Optional[str] = None) -> bool:
    """Delete DB override for a flag. Returns True if a row was deleted."""
    from app.core.database import get_asyncpg_pool

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if org_id:
            result = await conn.execute(
                "DELETE FROM admin_feature_flags WHERE key = $1 AND organization_id = $2",
                key, org_id,
            )
        else:
            result = await conn.execute(
                "DELETE FROM admin_feature_flags WHERE key = $1 AND organization_id IS NULL",
                key,
            )

    invalidate_cache()
    return result.split()[-1] != "0"


async def list_all_flags(org_id: Optional[str] = None) -> list:
    """List all flags: config.py merged with DB overrides."""
    from app.core.config import settings

    flags = {}

    # Config.py defaults
    for name in sorted(dir(settings)):
        if not name.startswith("enable_"):
            continue
        val = getattr(settings, name, None)
        if not isinstance(val, bool):
            continue
        flags[name] = {
            "key": name,
            "value": val,
            "source": "config",
            "flag_type": "release",
            "description": None,
            "owner": None,
            "expires_at": None,
        }

    # Merge DB overrides
    db_flags = await _load_db_flags(org_id)
    for cache_key, row in db_flags.items():
        fkey = row["key"]
        row_org = row.get("organization_id")

        if fkey in flags:
            # org-specific override takes precedence over global
            if row_org and org_id and row_org == org_id:
                flags[fkey]["value"] = row["value"]
                flags[fkey]["source"] = "db_override"
                flags[fkey]["flag_type"] = row["flag_type"] or "release"
                flags[fkey]["description"] = row["description"]
                flags[fkey]["owner"] = row["owner"]
                flags[fkey]["expires_at"] = row["expires_at"].isoformat() if row.get("expires_at") else None
            elif not row_org and flags[fkey]["source"] == "config":
                flags[fkey]["value"] = row["value"]
                flags[fkey]["source"] = "db_override"
                flags[fkey]["flag_type"] = row["flag_type"] or "release"
                flags[fkey]["description"] = row["description"]
                flags[fkey]["owner"] = row["owner"]
                flags[fkey]["expires_at"] = row["expires_at"].isoformat() if row.get("expires_at") else None

    return list(flags.values())
