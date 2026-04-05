"""
Living Agent API.

Router shell for monitoring and interacting with Wiii's autonomous life.
The route file now stays thin while response models and runtime orchestration
live in neighboring support modules.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import RequireAuth
from app.api.v1.living_agent_models import (
    AutonomyStatusResponse,
    BrowsingLogResponse,
    CreateGoalRequest,
    EmotionalStateResponse,
    GoalResponse,
    HeartbeatAuditResponse,
    HeartbeatInfoResponse,
    HeartbeatTriggerResponse,
    JournalEntryResponse,
    LivingAgentStatusResponse,
    PendingActionResponse,
    ReflectionResponse,
    ResolveActionRequest,
    RoutineResponse,
    SkillResponse,
    UpdateGoalProgressRequest,
)
from app.api.v1.living_agent_runtime import (
    activate_goal_response,
    check_living_agent_enabled,
    complete_goal_response,
    create_goal_response,
    get_autonomy_status_response,
    get_emotional_state_response,
    get_heartbeat_info_response,
    get_living_agent_status_response,
    get_user_routine_response,
    list_goal_responses,
    list_journal_entry_responses,
    list_reflection_responses,
    list_skill_responses,
    trigger_heartbeat_response,
    trigger_reflection_response,
    update_goal_progress_response,
)
from app.api.v1.living_agent_support import (
    fetch_browsing_log_entries,
    fetch_heartbeat_audit_entries,
    fetch_pending_action_entries,
    resolve_pending_action_record,
)
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/living-agent", tags=["living-agent"])


def _check_enabled():
    """Backward-compatible local alias for tests/importers."""
    return check_living_agent_enabled()


@router.get("/status", response_model=LivingAgentStatusResponse)
@limiter.limit("30/minute")
async def get_living_agent_status(
    request: Request,
    auth: RequireAuth,
) -> LivingAgentStatusResponse:
    """Get overall living agent status."""
    return get_living_agent_status_response()


@router.get("/emotional-state", response_model=EmotionalStateResponse)
@limiter.limit("60/minute")
async def get_emotional_state(
    request: Request,
    auth: RequireAuth,
) -> EmotionalStateResponse:
    """Get Wiii's current emotional state."""
    return get_emotional_state_response()


@router.get("/journal", response_model=List[JournalEntryResponse])
@limiter.limit("20/minute")
async def get_journal_entries(
    request: Request,
    auth: RequireAuth,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
) -> List[JournalEntryResponse]:
    """Get Wiii's recent journal entries."""
    return list_journal_entry_responses(days)


@router.get("/skills", response_model=List[SkillResponse])
@limiter.limit("30/minute")
async def get_skills(
    request: Request,
    auth: RequireAuth,
    status: Optional[str] = Query(default=None, description="Filter by status"),
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
) -> List[SkillResponse]:
    """Get Wiii's tracked skills."""
    return list_skill_responses(status=status, domain=domain)


@router.get("/heartbeat", response_model=HeartbeatInfoResponse)
@limiter.limit("30/minute")
async def get_heartbeat_info(
    request: Request,
    auth: RequireAuth,
) -> HeartbeatInfoResponse:
    """Get heartbeat scheduler information."""
    return get_heartbeat_info_response()


@router.post("/heartbeat/trigger", response_model=HeartbeatTriggerResponse)
@limiter.limit("5/minute")
async def trigger_heartbeat(
    request: Request,
    auth: RequireAuth,
) -> HeartbeatTriggerResponse:
    """Manually trigger a heartbeat cycle."""
    return await trigger_heartbeat_response()


@router.get("/browsing-log", response_model=List[BrowsingLogResponse])
@limiter.limit("20/minute")
async def get_browsing_log(
    request: Request,
    auth: RequireAuth,
    days: int = Query(default=7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries"),
) -> List[BrowsingLogResponse]:
    """Get Wiii's recent browsing activity."""
    check_living_agent_enabled()
    try:
        return fetch_browsing_log_entries(
            days=days,
            limit=limit,
            response_cls=BrowsingLogResponse,
        )
    except Exception as exc:
        logger.error("[LIVING_AGENT_API] Browsing log error: %s", exc)
        return []


@router.get("/pending-actions", response_model=List[PendingActionResponse])
@limiter.limit("30/minute")
async def get_pending_actions(
    request: Request,
    auth: RequireAuth,
    status_filter: Optional[str] = Query(
        default="pending",
        alias="status",
        description="Filter by status: pending, approved, rejected, expired",
    ),
) -> List[PendingActionResponse]:
    """Get actions awaiting human approval."""
    check_living_agent_enabled()
    try:
        return fetch_pending_action_entries(
            status_filter=status_filter,
            response_cls=PendingActionResponse,
        )
    except Exception as exc:
        logger.error("[LIVING_AGENT_API] Pending actions error: %s", exc)
        return []


@router.post("/pending-actions/{action_id}/resolve")
@limiter.limit("10/minute")
async def resolve_pending_action(
    request: Request,
    auth: RequireAuth,
    action_id: str,
    body: ResolveActionRequest,
):
    """Approve or reject a pending action."""
    check_living_agent_enabled()

    if body.decision not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approve' or 'reject'",
        )

    try:
        user_id = getattr(auth, "user_id", "system")
        resolve_pending_action_record(
            action_id=action_id,
            decision=body.decision,
            approved_by=user_id,
            http_exception_cls=HTTPException,
        )

        if body.decision == "approve":
            from app.engine.living_agent.heartbeat import get_heartbeat_scheduler

            result = await get_heartbeat_scheduler().execute_approved_action(action_id)
            return {
                "status": "approved_and_executed",
                "action_id": action_id,
                "execution": {
                    "success": not result.error,
                    "actions_taken": len(result.actions_taken),
                    "duration_ms": result.duration_ms,
                    "error": result.error,
                },
            }

        return {"status": "rejected", "action_id": action_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[LIVING_AGENT_API] Resolve action error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/heartbeat/audit", response_model=List[HeartbeatAuditResponse])
@limiter.limit("20/minute")
async def get_heartbeat_audit(
    request: Request,
    auth: RequireAuth,
    limit: int = Query(default=20, ge=1, le=100, description="Max entries"),
) -> List[HeartbeatAuditResponse]:
    """Get recent heartbeat cycle audit logs."""
    check_living_agent_enabled()
    try:
        return fetch_heartbeat_audit_entries(
            limit=limit,
            response_cls=HeartbeatAuditResponse,
        )
    except Exception as exc:
        logger.error("[LIVING_AGENT_API] Heartbeat audit error: %s", exc)
        return []


@router.get("/goals", response_model=List[GoalResponse])
@limiter.limit("30/minute")
async def get_goals(
    request: Request,
    auth: RequireAuth,
    active_only: bool = Query(default=True, description="Only show non-terminal goals"),
) -> List[GoalResponse]:
    """Get Wiii's goals."""
    return await list_goal_responses(active_only)


@router.post("/goals", response_model=GoalResponse)
@limiter.limit("10/minute")
async def create_goal(
    request: Request,
    auth: RequireAuth,
    body: CreateGoalRequest,
) -> GoalResponse:
    """Create a new goal for Wiii."""
    return await create_goal_response(body)


@router.patch("/goals/{goal_id}/progress")
@limiter.limit("20/minute")
async def update_goal_progress(
    request: Request,
    auth: RequireAuth,
    goal_id: str,
    body: UpdateGoalProgressRequest,
):
    """Update goal progress and optionally record a milestone."""
    return await update_goal_progress_response(goal_id, body)


@router.post("/goals/{goal_id}/activate")
@limiter.limit("10/minute")
async def activate_goal(
    request: Request,
    auth: RequireAuth,
    goal_id: str,
):
    """Activate a proposed goal."""
    return await activate_goal_response(goal_id)


@router.post("/goals/{goal_id}/complete")
@limiter.limit("10/minute")
async def complete_goal(
    request: Request,
    auth: RequireAuth,
    goal_id: str,
):
    """Mark a goal as completed."""
    return await complete_goal_response(goal_id)


@router.get("/reflections", response_model=List[ReflectionResponse])
@limiter.limit("20/minute")
async def get_reflections(
    request: Request,
    auth: RequireAuth,
    count: int = Query(default=4, ge=1, le=20),
) -> List[ReflectionResponse]:
    """Get Wiii's recent reflections."""
    return await list_reflection_responses(count)


@router.post("/reflections/trigger", response_model=ReflectionResponse)
@limiter.limit("2/hour")
async def trigger_reflection(
    request: Request,
    auth: RequireAuth,
):
    """Manually trigger a deep reflection."""
    return await trigger_reflection_response()


@router.get("/autonomy", response_model=AutonomyStatusResponse)
@limiter.limit("30/minute")
async def get_autonomy_status(
    request: Request,
    auth: RequireAuth,
):
    """Get current autonomy level and status."""
    return get_autonomy_status_response()


@router.get("/routine/{user_id}", response_model=Optional[RoutineResponse])
@limiter.limit("20/minute")
async def get_user_routine(
    request: Request,
    auth: RequireAuth,
    user_id: str,
):
    """Get learned routine for a user."""
    return await get_user_routine_response(user_id)
