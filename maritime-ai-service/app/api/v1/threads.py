"""
Thread Management API — Server-side conversation index

Sprint 16: Virtual Agent-per-User Architecture
Provides REST endpoints for listing, getting, renaming, and deleting conversations.

All endpoints include ownership checks — users can only access their own threads.
Admin users can access any thread.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Threads"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class ThreadView(BaseModel):
    """A single thread/conversation view."""
    thread_id: str
    user_id: str
    domain_id: str = "maritime"
    title: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)


class ThreadListResponse(BaseModel):
    """Response for listing threads."""
    status: str = "success"
    threads: list[ThreadView] = Field(default_factory=list)
    total: int = 0


class ThreadRenameRequest(BaseModel):
    """Request to rename a thread."""
    title: str = Field(..., min_length=1, max_length=200)


class ThreadActionResponse(BaseModel):
    """Generic response for thread actions."""
    status: str = "success"
    message: str = ""


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/threads",
    response_model=ThreadListResponse,
    summary="List user conversations",
    description="List all conversations for the authenticated user, ordered by most recent.",
)
@limiter.limit("60/minute")
async def list_threads(
    request: Request,
    auth: RequireAuth,
    limit: int = Query(default=50, ge=1, le=200, description="Max threads to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """List threads for the authenticated user."""
    try:
        from app.repositories.thread_repository import get_thread_repository
        repo = get_thread_repository()

        user_id = auth.user_id
        threads = repo.list_threads(user_id=user_id, limit=limit, offset=offset)
        total = repo.count_threads(user_id=user_id)

        return ThreadListResponse(
            threads=[ThreadView(**t) for t in threads],
            total=total,
        )
    except Exception as e:
        logger.error("Failed to list threads: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to list threads"},
        )


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadView,
    summary="Get thread details",
    description="Get details of a specific conversation thread.",
)
@limiter.limit("60/minute")
async def get_thread(
    request: Request,
    thread_id: str,
    auth: RequireAuth,
):
    """Get a single thread by ID with ownership check."""
    try:
        from app.repositories.thread_repository import get_thread_repository
        repo = get_thread_repository()

        # Try with ownership filter first
        thread = repo.get_thread(thread_id=thread_id, user_id=auth.user_id)

        if not thread:
            # Admin can access any thread — re-query without user filter
            if auth.role == "admin":
                thread = repo.get_thread(thread_id=thread_id)
            if not thread:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"status": "error", "message": "Thread not found"},
                )

        return ThreadView(**thread)
    except Exception as e:
        logger.error("Failed to get thread: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to get thread"},
        )


@router.delete(
    "/threads/{thread_id}",
    response_model=ThreadActionResponse,
    summary="Delete a conversation",
    description="Soft-delete a conversation thread (can be restored later).",
)
@limiter.limit("30/minute")
async def delete_thread(
    request: Request,
    thread_id: str,
    auth: RequireAuth,
):
    """Soft-delete a thread with ownership check."""
    try:
        from app.repositories.thread_repository import get_thread_repository
        repo = get_thread_repository()

        success = repo.delete_thread(thread_id=thread_id, user_id=auth.user_id)

        if not success:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": "error",
                    "message": "Thread not found or already deleted",
                },
            )

        return ThreadActionResponse(message="Thread deleted successfully")
    except Exception as e:
        logger.error("Failed to delete thread: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to delete thread"},
        )


@router.patch(
    "/threads/{thread_id}/title",
    response_model=ThreadActionResponse,
    summary="Rename a conversation",
    description="Update the title of a conversation thread.",
)
@limiter.limit("30/minute")
async def rename_thread(
    request: Request,
    thread_id: str,
    body: ThreadRenameRequest,
    auth: RequireAuth,
):
    """Rename a thread with ownership check."""
    try:
        from app.repositories.thread_repository import get_thread_repository
        repo = get_thread_repository()

        success = repo.rename_thread(
            thread_id=thread_id,
            user_id=auth.user_id,
            title=body.title,
        )

        if not success:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": "Thread not found"},
            )

        return ThreadActionResponse(message="Thread renamed successfully")
    except Exception as e:
        logger.error("Failed to rename thread: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to rename thread"},
        )
