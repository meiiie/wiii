"""Edge endpoints — OpenAI Chat Completions + Anthropic Messages compat layer.

Phase 10d of the runtime migration epic (issue #207). External clients hit
Wiii using their native SDK without rewriting wire payloads. Each endpoint:

1. Parses the raw provider-shaped request body.
2. Converts to a canonical ``TurnRequest`` via the corresponding Phase 4
   adapter (``adapters/openai_compat.py``, ``adapters/anthropic_compat.py``).
3. Bridges to the existing ``ChatService`` for execution. The native
   runtime takes over dispatch in a follow-up phase; until then we reuse
   the proven path so this module never blocks production traffic.
4. Re-renders the response in the upstream wire shape so SDKs keep working.

Feature-gated by ``settings.enable_native_runtime``. The router mounts at
``/v1`` (not ``/api/v1/v1``) so clients can swap ``base_url`` without
extra path acrobatics.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import RequireAuth
from app.core.security import resolve_interaction_role
from app.engine.runtime.adapters.anthropic_compat import (
    anthropic_messages_to_turn_request,
)
from app.engine.runtime.adapters.openai_compat import (
    openai_chat_completions_to_turn_request,
)
from app.engine.runtime.turn_request import TurnRequest
from app.models.schemas import ChatRequest, InternalChatResponse, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Edge"])


def _ensure_enabled() -> None:
    """Reject requests when the native runtime gate is off."""
    from app.core.config import settings

    if not getattr(settings, "enable_native_runtime", False):
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "type": "service_unavailable",
                    "message": "Native runtime edge endpoints not enabled",
                }
            },
        )


def _last_user_message(turn: TurnRequest) -> str:
    """Pull the most recent non-empty user-role text from a TurnRequest."""
    for msg in reversed(turn.messages):
        if msg.role == "user" and msg.content:
            return msg.content
    raise HTTPException(
        status_code=400,
        detail={
            "error": {
                "type": "invalid_request",
                "message": "messages must include at least one user-role entry",
            }
        },
    )


def _resolve_session_id(body: dict, auth: RequireAuth) -> str:
    """Pick a stable session id without leaking auth internals into the body."""
    session = body.get("session_id")
    if isinstance(session, str) and session:
        return session
    return f"edge-{auth.user_id}"


def _to_chat_request(turn: TurnRequest, *, auth: RequireAuth) -> ChatRequest:
    """Bridge a TurnRequest into the existing ChatService input schema."""
    role = resolve_interaction_role(auth)
    return ChatRequest(
        user_id=str(auth.user_id),
        message=_last_user_message(turn),
        role=UserRole(role),
        session_id=turn.session_id,
        organization_id=auth.organization_id or turn.org_id,
        domain_id=turn.domain_id,
    )


async def _process(turn: TurnRequest, *, auth: RequireAuth) -> InternalChatResponse:
    chat_request = _to_chat_request(turn, auth=auth)
    from app.services.chat_service import get_chat_service

    return await get_chat_service().process_message(chat_request)


def _openai_completion_response(
    *, internal: InternalChatResponse, model: str
) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": internal.message,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "system_fingerprint": "wiii-runtime-v1",
    }


def _anthropic_messages_response(
    *, internal: InternalChatResponse, model: str
) -> dict[str, Any]:
    return {
        "id": f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": internal.message}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


@router.post("/v1/chat/completions", tags=["Edge"])
async def openai_chat_completions(
    request: Request,
    auth: RequireAuth,
) -> dict[str, Any]:
    """OpenAI-compat endpoint at ``POST /v1/chat/completions``."""
    _ensure_enabled()
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    turn = openai_chat_completions_to_turn_request(
        body,
        user_id=str(auth.user_id),
        session_id=_resolve_session_id(body, auth),
        org_id=auth.organization_id,
        role=resolve_interaction_role(auth),
    )
    internal = await _process(turn, auth=auth)
    return _openai_completion_response(
        internal=internal,
        model=body.get("model") or "wiii-default",
    )


@router.post("/v1/messages", tags=["Edge"])
async def anthropic_messages(
    request: Request,
    auth: RequireAuth,
) -> dict[str, Any]:
    """Anthropic-compat endpoint at ``POST /v1/messages``."""
    _ensure_enabled()
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    turn = anthropic_messages_to_turn_request(
        body,
        user_id=str(auth.user_id),
        session_id=_resolve_session_id(body, auth),
        org_id=auth.organization_id,
        role=resolve_interaction_role(auth),
    )
    internal = await _process(turn, auth=auth)
    return _anthropic_messages_response(
        internal=internal,
        model=body.get("model") or "wiii-default",
    )


__all__ = ["router"]
