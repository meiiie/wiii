"""
Living Agent API — Sprint 170: "Linh Hồn Sống" + Sprint 171: "Quyền Tự Chủ"

Endpoints for monitoring and interacting with Wiii's autonomous life:
- GET /living-agent/status — overall living agent status
- GET /living-agent/emotional-state — current emotional state
- GET /living-agent/journal — recent journal entries
- GET /living-agent/skills — tracked skills
- GET /living-agent/heartbeat — heartbeat scheduler info
- POST /living-agent/heartbeat/trigger — manually trigger a heartbeat cycle
- GET /living-agent/heartbeat/audit — heartbeat cycle audit log (Sprint 171)
- GET /living-agent/browsing-log — recent browsing activity (Sprint 171)
- GET /living-agent/pending-actions — actions awaiting approval (Sprint 171)
- POST /living-agent/pending-actions/{id}/resolve — approve/reject action (Sprint 171)

Feature-gated: enable_living_agent=False by default.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/living-agent", tags=["living-agent"])


# =============================================================================
# Response Schemas
# =============================================================================

class EmotionalStateResponse(BaseModel):
    """Current emotional state of Wiii."""
    primary_mood: str = Field("neutral", description="Current mood")
    energy_level: float = Field(0.7, description="Energy 0-1")
    social_battery: float = Field(0.8, description="Social battery 0-1")
    engagement: float = Field(0.5, description="Engagement 0-1")
    mood_label: str = Field("bình thường", description="Vietnamese mood label")
    behavior_modifiers: dict = Field(default_factory=dict)
    last_updated: Optional[str] = None


class JournalEntryResponse(BaseModel):
    """A single journal entry."""
    id: str
    entry_date: str
    content: str
    mood_summary: str = ""
    energy_avg: float = 0.5
    notable_events: List[str] = Field(default_factory=list)
    learnings: List[str] = Field(default_factory=list)
    goals_next: List[str] = Field(default_factory=list)


class SkillResponse(BaseModel):
    """A tracked skill."""
    id: str
    skill_name: str
    domain: str = "general"
    status: str = "discovered"
    confidence: float = 0.0
    usage_count: int = 0
    success_rate: float = 0.0
    discovered_at: Optional[str] = None
    last_practiced: Optional[str] = None
    mastered_at: Optional[str] = None


class HeartbeatInfoResponse(BaseModel):
    """Heartbeat scheduler information."""
    is_running: bool = False
    heartbeat_count: int = 0
    interval_seconds: int = 1800
    active_hours: str = "08:00-23:00 UTC+7"


class LivingAgentStatusResponse(BaseModel):
    """Overall living agent status."""
    enabled: bool = False
    emotional_state: Optional[EmotionalStateResponse] = None
    heartbeat: Optional[HeartbeatInfoResponse] = None
    skills_count: int = 0
    journal_entries_count: int = 0
    soul_loaded: bool = False
    soul_name: str = ""


class HeartbeatTriggerResponse(BaseModel):
    """Result of manually triggering a heartbeat."""
    success: bool
    actions_taken: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


# Sprint 171: New response schemas
class BrowsingLogResponse(BaseModel):
    """A browsing log entry."""
    id: str
    platform: str
    url: str = ""
    title: str
    summary: str = ""
    relevance_score: float = 0.0
    browsed_at: str


class PendingActionResponse(BaseModel):
    """A pending action awaiting human approval."""
    id: str
    action_type: str
    target: str = ""
    priority: float = 0.5
    status: str = "pending"
    created_at: str
    resolved_at: Optional[str] = None
    approved_by: Optional[str] = None


class ResolveActionRequest(BaseModel):
    """Request body for resolving a pending action."""
    decision: str = Field(..., description="'approve' or 'reject'")


class HeartbeatAuditResponse(BaseModel):
    """A heartbeat audit log entry."""
    id: str
    cycle_number: int
    actions_taken: List[dict] = Field(default_factory=list)
    insights_gained: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    created_at: str


# =============================================================================
# Helper: Feature gate check
# =============================================================================

def _check_enabled():
    """Raise 404 if living agent is disabled."""
    from app.core.config import settings
    if not settings.enable_living_agent:
        raise HTTPException(
            status_code=404,
            detail="Living Agent is not enabled. Set ENABLE_LIVING_AGENT=true.",
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=LivingAgentStatusResponse)
@limiter.limit("30/minute")
async def get_living_agent_status(
    request: Request,
    auth: RequireAuth,
) -> LivingAgentStatusResponse:
    """Get overall living agent status."""
    from app.core.config import settings

    if not settings.enable_living_agent:
        return LivingAgentStatusResponse(enabled=False)

    try:
        from app.engine.living_agent.soul_loader import get_soul
        from app.engine.living_agent.emotion_engine import get_emotion_engine
        from app.engine.living_agent.heartbeat import get_heartbeat_scheduler

        soul = get_soul()
        engine = get_emotion_engine()
        scheduler = get_heartbeat_scheduler()
        state = engine.state

        return LivingAgentStatusResponse(
            enabled=True,
            emotional_state=EmotionalStateResponse(
                primary_mood=state.primary_mood.value,
                energy_level=round(state.energy_level, 3),
                social_battery=round(state.social_battery, 3),
                engagement=round(state.engagement, 3),
                mood_label=engine.get_behavior_modifiers().get("mood_label", "bình thường"),
                behavior_modifiers=engine.get_behavior_modifiers(),
                last_updated=state.last_updated.isoformat() if state.last_updated else None,
            ),
            heartbeat=HeartbeatInfoResponse(
                is_running=scheduler.is_running,
                heartbeat_count=scheduler.heartbeat_count,
                interval_seconds=settings.living_agent_heartbeat_interval,
                active_hours=f"{settings.living_agent_active_hours_start:02d}:00-{settings.living_agent_active_hours_end:02d}:00 UTC+7",
            ),
            soul_loaded=True,
            soul_name=soul.name,
        )
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Status error: %s", e)
        return LivingAgentStatusResponse(enabled=True)


@router.get("/emotional-state", response_model=EmotionalStateResponse)
@limiter.limit("60/minute")
async def get_emotional_state(
    request: Request,
    auth: RequireAuth,
) -> EmotionalStateResponse:
    """Get Wiii's current emotional state."""
    _check_enabled()

    try:
        from app.engine.living_agent.emotion_engine import get_emotion_engine
        engine = get_emotion_engine()
        state = engine.state
        modifiers = engine.get_behavior_modifiers()

        return EmotionalStateResponse(
            primary_mood=state.primary_mood.value,
            energy_level=round(state.energy_level, 3),
            social_battery=round(state.social_battery, 3),
            engagement=round(state.engagement, 3),
            mood_label=modifiers.get("mood_label", "bình thường"),
            behavior_modifiers=modifiers,
            last_updated=state.last_updated.isoformat() if state.last_updated else None,
        )
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Emotional state error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/journal", response_model=List[JournalEntryResponse])
@limiter.limit("20/minute")
async def get_journal_entries(
    request: Request,
    auth: RequireAuth,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
) -> List[JournalEntryResponse]:
    """Get Wiii's recent journal entries."""
    _check_enabled()

    try:
        from app.engine.living_agent.journal import get_journal_writer
        writer = get_journal_writer()
        entries = writer.get_recent_entries(days=days)

        return [
            JournalEntryResponse(
                id=str(entry.id),
                entry_date=entry.entry_date.isoformat() if entry.entry_date else "",
                content=entry.content,
                mood_summary=entry.mood_summary,
                energy_avg=entry.energy_avg,
                notable_events=entry.notable_events,
                learnings=entry.learnings,
                goals_next=entry.goals_next,
            )
            for entry in entries
        ]
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Journal error: %s", e)
        return []


@router.get("/skills", response_model=List[SkillResponse])
@limiter.limit("30/minute")
async def get_skills(
    request: Request,
    auth: RequireAuth,
    status: Optional[str] = Query(default=None, description="Filter by status"),
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
) -> List[SkillResponse]:
    """Get Wiii's tracked skills."""
    _check_enabled()

    try:
        from app.engine.living_agent.skill_builder import get_skill_builder
        from app.engine.living_agent.models import SkillStatus

        builder = get_skill_builder()

        # Convert status string to enum
        status_enum = None
        if status:
            try:
                status_enum = SkillStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Valid: {[s.value for s in SkillStatus]}",
                )

        skills = builder.get_all_skills(status=status_enum, domain=domain)

        return [
            SkillResponse(
                id=str(skill.id),
                skill_name=skill.skill_name,
                domain=skill.domain,
                status=skill.status.value,
                confidence=round(skill.confidence, 3),
                usage_count=skill.usage_count,
                success_rate=round(skill.success_rate, 3),
                discovered_at=skill.discovered_at.isoformat() if skill.discovered_at else None,
                last_practiced=skill.last_practiced.isoformat() if skill.last_practiced else None,
                mastered_at=skill.mastered_at.isoformat() if skill.mastered_at else None,
            )
            for skill in skills
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Skills error: %s", e)
        return []


@router.get("/heartbeat", response_model=HeartbeatInfoResponse)
@limiter.limit("30/minute")
async def get_heartbeat_info(
    request: Request,
    auth: RequireAuth,
) -> HeartbeatInfoResponse:
    """Get heartbeat scheduler information."""
    _check_enabled()

    try:
        from app.core.config import settings
        from app.engine.living_agent.heartbeat import get_heartbeat_scheduler
        scheduler = get_heartbeat_scheduler()

        return HeartbeatInfoResponse(
            is_running=scheduler.is_running,
            heartbeat_count=scheduler.heartbeat_count,
            interval_seconds=settings.living_agent_heartbeat_interval,
            active_hours=f"{settings.living_agent_active_hours_start:02d}:00-{settings.living_agent_active_hours_end:02d}:00 UTC+7",
        )
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Heartbeat info error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat/trigger", response_model=HeartbeatTriggerResponse)
@limiter.limit("5/minute")
async def trigger_heartbeat(
    request: Request,
    auth: RequireAuth,
) -> HeartbeatTriggerResponse:
    """Manually trigger a heartbeat cycle (admin/debug use)."""
    _check_enabled()

    try:
        from app.engine.living_agent.heartbeat import get_heartbeat_scheduler
        scheduler = get_heartbeat_scheduler()
        result = await scheduler._execute_heartbeat()

        return HeartbeatTriggerResponse(
            success=not result.error,
            actions_taken=len(result.actions_taken),
            duration_ms=result.duration_ms,
            error=result.error,
        )
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Trigger error: %s", e)
        return HeartbeatTriggerResponse(success=False, error=str(e))


# =============================================================================
# Sprint 171: Browsing log, Pending actions, Heartbeat audit
# =============================================================================

@router.get("/browsing-log", response_model=List[BrowsingLogResponse])
@limiter.limit("20/minute")
async def get_browsing_log(
    request: Request,
    auth: RequireAuth,
    days: int = Query(default=7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries"),
) -> List[BrowsingLogResponse]:
    """Get Wiii's recent browsing activity."""
    _check_enabled()

    try:
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        session_factory = get_shared_session_factory()
        with session_factory() as session:
            rows = session.execute(
                text("""
                    SELECT id, platform, COALESCE(url, '') as url, title,
                           COALESCE(summary, '') as summary, relevance_score, browsed_at
                    FROM wiii_browsing_log
                    WHERE browsed_at >= NOW() - INTERVAL ':days days'
                    ORDER BY browsed_at DESC
                    LIMIT :limit
                """.replace(":days days", f"{days} days")),
                {"limit": limit},
            ).fetchall()

            return [
                BrowsingLogResponse(
                    id=str(row[0]),
                    platform=row[1],
                    url=row[2],
                    title=row[3],
                    summary=row[4],
                    relevance_score=float(row[5]) if row[5] else 0.0,
                    browsed_at=row[6].isoformat() if row[6] else "",
                )
                for row in rows
            ]
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Browsing log error: %s", e)
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
    _check_enabled()

    try:
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        session_factory = get_shared_session_factory()
        with session_factory() as session:
            query = """
                SELECT id, action_type, COALESCE(target, '') as target,
                       priority, status, created_at, resolved_at, approved_by
                FROM wiii_pending_actions
            """
            params = {}
            if status_filter:
                query += " WHERE status = :status"
                params["status"] = status_filter
            query += " ORDER BY created_at DESC LIMIT 100"

            rows = session.execute(text(query), params).fetchall()

            return [
                PendingActionResponse(
                    id=str(row[0]),
                    action_type=row[1],
                    target=row[2],
                    priority=float(row[3]) if row[3] else 0.5,
                    status=row[4],
                    created_at=row[5].isoformat() if row[5] else "",
                    resolved_at=row[6].isoformat() if row[6] else None,
                    approved_by=row[7],
                )
                for row in rows
            ]
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Pending actions error: %s", e)
        return []


@router.post("/pending-actions/{action_id}/resolve")
@limiter.limit("10/minute")
async def resolve_pending_action(
    request: Request,
    auth: RequireAuth,
    action_id: str,
    body: ResolveActionRequest,
):
    """Approve or reject a pending action.

    When approved, the action is immediately executed.
    When rejected, the action is marked as rejected.
    """
    _check_enabled()

    if body.decision not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approve' or 'reject'",
        )

    try:
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        session_factory = get_shared_session_factory()
        with session_factory() as session:
            # Check action exists and is pending
            row = session.execute(
                text("SELECT status FROM wiii_pending_actions WHERE id = :id"),
                {"id": action_id},
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Action not found")
            if row[0] != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Action is already {row[0]}",
                )

            new_status = "approved" if body.decision == "approve" else "rejected"
            user_id = getattr(auth, "user_id", "system")

            session.execute(
                text("""
                    UPDATE wiii_pending_actions
                    SET status = :status, approved_by = :approved_by, resolved_at = NOW()
                    WHERE id = :id
                """),
                {"status": new_status, "approved_by": user_id, "id": action_id},
            )
            session.commit()

        # If approved, execute the action
        if body.decision == "approve":
            from app.engine.living_agent.heartbeat import get_heartbeat_scheduler
            scheduler = get_heartbeat_scheduler()
            result = await scheduler.execute_approved_action(action_id)

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
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Resolve action error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heartbeat/audit", response_model=List[HeartbeatAuditResponse])
@limiter.limit("20/minute")
async def get_heartbeat_audit(
    request: Request,
    auth: RequireAuth,
    limit: int = Query(default=20, ge=1, le=100, description="Max entries"),
) -> List[HeartbeatAuditResponse]:
    """Get recent heartbeat cycle audit logs."""
    _check_enabled()

    try:
        import json
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        session_factory = get_shared_session_factory()
        with session_factory() as session:
            rows = session.execute(
                text("""
                    SELECT id, cycle_number, actions_taken, insights_gained,
                           duration_ms, error, created_at
                    FROM wiii_heartbeat_audit
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).fetchall()

            results = []
            for row in rows:
                # Parse actions_taken JSON
                actions = []
                try:
                    actions = json.loads(row[2]) if row[2] else []
                except (json.JSONDecodeError, TypeError):
                    pass

                results.append(HeartbeatAuditResponse(
                    id=str(row[0]),
                    cycle_number=row[1],
                    actions_taken=actions,
                    insights_gained=row[3] or 0,
                    duration_ms=row[4] or 0,
                    error=row[5],
                    created_at=row[6].isoformat() if row[6] else "",
                ))
            return results
    except Exception as e:
        logger.error("[LIVING_AGENT_API] Heartbeat audit error: %s", e)
        return []
