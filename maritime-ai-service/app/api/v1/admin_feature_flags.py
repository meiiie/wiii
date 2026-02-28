"""
Sprint 178: Feature Flag Admin API — Phase 2

Endpoints:
  PATCH  /admin/feature-flags/{key}  — Toggle/update flag override
  DELETE /admin/feature-flags/{key}  — Remove DB override (revert to config.py)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.admin_security import check_admin_module as _check_admin_module
from app.api.deps import RequireAdmin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class FlagUpdateBody(BaseModel):
    value: bool
    flag_type: Optional[str] = None
    description: Optional[str] = None
    organization_id: Optional[str] = None
    expires_at: Optional[str] = None


@router.patch(
    "/feature-flags/{key}",
    dependencies=[Depends(_check_admin_module)],
)
async def admin_flag_toggle(key: str, body: FlagUpdateBody, request: Request, auth: RequireAdmin):
    """Toggle or update a feature flag override."""
    # Validate key exists in config.py
    if not hasattr(settings, key):
        raise HTTPException(status_code=400, detail=f"Unknown flag key: {key}")
    if not key.startswith("enable_"):
        raise HTTPException(status_code=400, detail="Only enable_* flags can be toggled")

    old_value = getattr(settings, key, None)

    from app.services.feature_flag_service import set_flag
    result = await set_flag(
        key=key,
        value=body.value,
        flag_type=body.flag_type or "release",
        description=body.description,
        org_id=body.organization_id,
        expires_at=body.expires_at,
    )

    # Audit
    from app.services.admin_audit import log_admin_action, extract_audit_context
    ctx = extract_audit_context(request)
    await log_admin_action(
        actor_id=auth.user_id,
        action="flag.toggle",
        target_type="feature_flag",
        target_id=key,
        old_value={"value": old_value},
        new_value={"value": body.value},
        **ctx,
    )

    return result


@router.delete(
    "/feature-flags/{key}",
    dependencies=[Depends(_check_admin_module)],
)
async def admin_flag_delete(
    key: str,
    request: Request,
    auth: RequireAdmin,
    organization_id: Optional[str] = Query(None),
):
    """Remove DB override for a flag — reverts to config.py default."""
    from app.services.feature_flag_service import delete_flag

    deleted = await delete_flag(key, org_id=organization_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No override found for {key}")

    # Audit
    from app.services.admin_audit import log_admin_action, extract_audit_context
    ctx = extract_audit_context(request)
    await log_admin_action(
        actor_id=auth.user_id,
        action="flag.delete",
        target_type="feature_flag",
        target_id=key,
        **ctx,
    )

    return {"deleted": True, "key": key}
