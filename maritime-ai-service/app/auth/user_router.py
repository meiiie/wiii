"""
Sprint 158: User profile + admin REST endpoints.

Routes:
  GET    /users/me              — Current user profile (JWT)
  PATCH  /users/me              — Update name, avatar_url (JWT)
  GET    /users/me/identities   — List linked providers (JWT)
  DELETE /users/me/identities/{id} — Unlink provider (JWT, keep >= 1)
  GET    /users                 — Paginated user list (JWT + admin)
  PATCH  /users/{id}/role       — Change user role (JWT + admin)
  POST   /users/{id}/deactivate — Soft-delete user (JWT + admin)
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    avatar_url: Optional[str] = Field(None, max_length=2048)


class UserRoleUpdate(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)


class UserProfileResponse(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "student"
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IdentityResponse(BaseModel):
    id: str
    provider: str
    provider_sub: str
    provider_issuer: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    linked_at: Optional[str] = None
    last_used_at: Optional[str] = None


class PaginatedUsersResponse(BaseModel):
    users: list[UserProfileResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Auth helpers (lazy imports)
# ---------------------------------------------------------------------------

def _extract_jwt_user(request: Request) -> dict:
    """Extract and verify JWT from Authorization header. Returns token payload dict."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")

    token = auth_header.split(" ", 1)[1]
    try:
        from app.auth.token_service import verify_access_token
        payload = verify_access_token(token)
        return {"sub": payload.sub, "email": payload.email, "name": payload.name, "role": payload.role}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _require_admin(jwt_user: dict) -> None:
    """Raise 403 if user is not admin."""
    if jwt_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# User self-service endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(request: Request):
    """Get the current authenticated user's full profile."""
    jwt_user = _extract_jwt_user(request)
    from app.auth.user_service import get_user

    user = await get_user(jwt_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(**user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(request: Request, body: UserProfileUpdate):
    """Update current user's name and/or avatar_url."""
    jwt_user = _extract_jwt_user(request)
    from app.auth.user_service import update_user

    if body.name is None and body.avatar_url is None:
        raise HTTPException(status_code=400, detail="At least one field (name, avatar_url) is required")

    user = await update_user(jwt_user["sub"], name=body.name, avatar_url=body.avatar_url)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(**user)


@router.get("/me/identities", response_model=list[IdentityResponse])
async def list_my_identities(request: Request):
    """List all linked provider identities for the current user."""
    jwt_user = _extract_jwt_user(request)
    from app.auth.user_service import list_user_identities

    identities = await list_user_identities(jwt_user["sub"])
    return [IdentityResponse(**i) for i in identities]


@router.delete("/me/identities/{identity_id}")
async def unlink_my_identity(request: Request, identity_id: str):
    """Unlink a provider identity. Refuses if it's the last one."""
    jwt_user = _extract_jwt_user(request)
    from app.auth.user_service import unlink_identity

    try:
        success = await unlink_identity(jwt_user["sub"], identity_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")

    return JSONResponse({"status": "unlinked", "identity_id": identity_id})


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedUsersResponse)
async def list_users_admin(
    request: Request,
    org_id: Optional[str] = Query(None, description="Filter by organization"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List users (admin only). Optionally filter by organization."""
    jwt_user = _extract_jwt_user(request)
    _require_admin(jwt_user)
    from app.auth.user_service import list_users

    users, total = await list_users(org_id=org_id, limit=limit, offset=offset)
    return PaginatedUsersResponse(
        users=[UserProfileResponse(**u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{user_id}/role", response_model=UserProfileResponse)
async def update_user_role_admin(request: Request, user_id: str, body: UserRoleUpdate):
    """Change a user's role (admin only)."""
    jwt_user = _extract_jwt_user(request)
    _require_admin(jwt_user)
    from app.auth.user_service import update_user_role

    try:
        user = await update_user_role(user_id, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(**user)


@router.post("/{user_id}/deactivate", response_model=UserProfileResponse)
async def deactivate_user_admin(request: Request, user_id: str):
    """Soft-delete a user (admin only). Cannot deactivate self."""
    jwt_user = _extract_jwt_user(request)
    _require_admin(jwt_user)

    if jwt_user["sub"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    from app.auth.user_service import deactivate_user

    user = await deactivate_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(**user)
