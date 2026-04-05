"""Host action audit helpers."""
from __future__ import annotations

import hashlib
from typing import Any, Optional


def _hash_preview_token(token: Optional[str]) -> Optional[str]:
    normalized = (token or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


async def log_host_action_event(
    *,
    event_type: str,
    user_id: str,
    action: str,
    request_id: str,
    summary: Optional[str] = None,
    organization_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    host_type: Optional[str] = None,
    host_name: Optional[str] = None,
    page_type: Optional[str] = None,
    page_title: Optional[str] = None,
    user_role: Optional[str] = None,
    workflow_stage: Optional[str] = None,
    preview_kind: Optional[str] = None,
    preview_token: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    surface: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist host action lifecycle events via the shared audit substrate."""
    from app.auth.auth_audit import log_auth_event

    payload: dict[str, Any] = {
        "action": action,
        "request_id": request_id,
        "summary": summary,
        "host_type": host_type,
        "host_name": host_name,
        "page_type": page_type,
        "page_title": page_title,
        "user_role": user_role,
        "workflow_stage": workflow_stage,
        "preview_kind": preview_kind,
        "preview_token_hash": _hash_preview_token(preview_token),
        "target_type": target_type,
        "target_id": target_id,
        "surface": surface,
    }
    if metadata:
        payload["metadata"] = metadata

    await log_auth_event(
        f"host_action.{event_type}",
        user_id=user_id,
        provider="host_action",
        result="success",
        ip_address=ip_address,
        user_agent=user_agent,
        organization_id=organization_id,
        metadata=payload,
    )
