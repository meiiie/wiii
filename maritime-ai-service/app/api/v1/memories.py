"""
Memory Management API for Wiii v0.4
CHỈ THỊ KỸ THUẬT SỐ 23

API endpoints for managing user memories (facts).

Requirements: 3.1, 3.2, 3.3, 3.4
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import RequireAuth
from app.core.rate_limit import limiter
from app.core.security import is_platform_admin
from app.repositories.semantic_memory_repository import SemanticMemoryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])


# ========== Response Models ==========

class MemoryItem(BaseModel):
    """Single memory item in response."""
    id: str
    type: str  # fact_type
    value: str  # content (extracted value)
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MemoryListResponse(BaseModel):
    """Response for GET /memories/{user_id}."""
    data: List[MemoryItem]
    total: int


# ========== API Endpoints ==========

@router.get("/{user_id}", response_model=MemoryListResponse)
@limiter.limit("60/minute")
async def get_user_memories(
    request: Request,
    user_id: str,
    auth: RequireAuth
) -> MemoryListResponse:
    """
    Get all stored facts for a user.

    Returns a list of memory items with id, type, value, and created_at.
    Users can only access their own memories; admins can access any user's.

    Args:
        user_id: User ID to get memories for

    Returns:
        MemoryListResponse with list of memory items

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    # Ownership check: users can only access their own data
    if auth.user_id != user_id and not is_platform_admin(auth):
        raise HTTPException(
            status_code=403,
            detail="You can only access your own memories"
        )
    try:
        repository = SemanticMemoryRepository()
        
        # Get all facts for user
        facts = repository.get_all_user_facts(user_id)
        
        # Transform to response format
        items = []
        for fact in facts:
            # Extract fact_type and value from metadata/content
            fact_type = fact.metadata.get("fact_type", "unknown")
            
            # Extract value from content (format: "fact_type: value")
            content = fact.content
            if ": " in content:
                value = content.split(": ", 1)[-1]
            else:
                value = content
            
            items.append(MemoryItem(
                id=str(fact.id),
                type=fact_type,
                value=value,
                created_at=fact.created_at
            ))
        
        logger.info("Retrieved %d memories for user %s", len(items), user_id)
        
        return MemoryListResponse(
            data=items,
            total=len(items)
        )
        
    except Exception as e:
        logger.error("Failed to get memories for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


class DeleteMemoryResponse(BaseModel):
    """Response for DELETE /memories/{user_id}/{memory_id}."""
    success: bool
    message: str


@router.delete("/{user_id}/{memory_id}", response_model=DeleteMemoryResponse)
@limiter.limit("30/minute")
async def delete_user_memory(
    request: Request,
    user_id: str,
    memory_id: str,
    auth: RequireAuth
) -> DeleteMemoryResponse:
    """
    Delete a specific memory for a user.

    Sprint 26: Users can delete their own memories; admins can delete any.
    Previously admin-only, now follows same ownership pattern as GET.

    Args:
        user_id: User ID who owns the memory
        memory_id: UUID of the memory to delete

    Returns:
        DeleteMemoryResponse with success status

    **Validates: Requirements 3.4**
    """
    try:
        # Ownership check: users can delete own data, admins can delete any
        if auth.user_id != user_id and not is_platform_admin(auth):
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own memories"
            )

        repository = SemanticMemoryRepository()

        # Delete the memory
        success = repository.delete_memory(user_id, memory_id)

        if success:
            logger.info("Memory %s deleted for user %s (by %s)", memory_id, user_id, auth.role)
            return DeleteMemoryResponse(
                success=True,
                message=f"Memory {memory_id} deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Memory {memory_id} not found for user {user_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete memory %s for user %s: %s", memory_id, user_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


class ClearMemoriesResponse(BaseModel):
    """Response for DELETE /memories/{user_id}."""
    success: bool
    deleted_count: int
    message: str


@router.delete("/{user_id}", response_model=ClearMemoriesResponse)
@limiter.limit("30/minute")
async def clear_user_memories(
    request: Request,
    user_id: str,
    auth: RequireAuth
) -> ClearMemoriesResponse:
    """
    Delete ALL memories for a user (factory reset).

    Sprint 26: User self-service memory clear endpoint.
    Users can clear their own data; admins can clear any user's data.

    Args:
        user_id: User ID whose memories to clear

    Returns:
        ClearMemoriesResponse with deleted count
    """
    try:
        # Ownership check: users can clear own data, admins can clear any
        if auth.user_id != user_id and not is_platform_admin(auth):
            raise HTTPException(
                status_code=403,
                detail="You can only clear your own memories"
            )

        repository = SemanticMemoryRepository()
        deleted_count = repository.delete_all_user_memories(user_id)

        logger.info(
            "Cleared %d memories for user %s (by %s)", deleted_count, user_id, auth.role
        )

        return ClearMemoriesResponse(
            success=True,
            deleted_count=deleted_count,
            message=f"Deleted {deleted_count} memories for user {user_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clear memories for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
