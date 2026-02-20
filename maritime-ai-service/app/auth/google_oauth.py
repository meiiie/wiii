"""
Sprint 157: Google OAuth 2.0 routes — login, callback, desktop callback.

Uses Authlib for OAuth 2.0 Authorization Code + PKCE flow.
Desktop apps use a localhost redirect via tauri-plugin-oauth.
"""
import logging
from typing import Optional
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth.token_service import create_token_pair, refresh_access_token, revoke_user_tokens
from app.auth.user_service import find_or_create_by_google
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Authlib OAuth client setup
# ---------------------------------------------------------------------------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_oauth_client_id or "",
    client_secret=settings.google_oauth_client_secret or "",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _get_redirect_uri(request: Request, desktop_port: Optional[int] = None) -> str:
    """Build the callback URL. Uses oauth_redirect_base_url if configured."""
    base = settings.oauth_redirect_base_url or str(request.base_url).rstrip("/")
    if desktop_port:
        return f"{base}/auth/google/callback/desktop?port={desktop_port}"
    return f"{base}/auth/google/callback"


# ---------------------------------------------------------------------------
# Web login flow
# ---------------------------------------------------------------------------

@router.get("/google/login")
async def google_login(
    request: Request,
    port: Optional[int] = Query(None, description="Desktop app localhost port for OAuth redirect"),
):
    """
    Initiate Google OAuth flow.

    For desktop apps: pass ?port=XXXXX — callback will redirect to localhost:{port}.
    For web apps: omit port — callback returns JSON with tokens.
    """
    if not settings.enable_google_oauth:
        raise HTTPException(status_code=404, detail="Google OAuth is not enabled")

    # Store desktop port in session for callback
    if port:
        request.session["desktop_port"] = port

    redirect_uri = _get_redirect_uri(request, desktop_port=None)  # Always callback to server first
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request):
    """
    Handle Google OAuth callback.

    For desktop: redirects to localhost:{port} with token.
    For web: returns JSON with token pair.
    """
    if not settings.enable_google_oauth:
        raise HTTPException(status_code=404, detail="Google OAuth is not enabled")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.error("OAuth token exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"OAuth failed: {e}")

    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get user info from Google")

    google_sub = userinfo["sub"]
    email = userinfo.get("email", "")
    name = userinfo.get("name", "")
    picture = userinfo.get("picture", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    # Find or create Wiii user
    user = await find_or_create_by_google(
        google_sub=google_sub,
        email=email,
        name=name,
        avatar_url=picture,
    )

    # Create token pair
    token_pair = await create_token_pair(
        user_id=user["id"],
        email=user.get("email"),
        name=user.get("name"),
        role=user.get("role", "student"),
        auth_method="google",
    )

    # Check if this is a desktop OAuth flow
    desktop_port = request.session.pop("desktop_port", None)
    if desktop_port:
        # Redirect to Tauri localhost server
        params = urlencode({
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "expires_in": token_pair.expires_in,
            "user_id": user["id"],
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "avatar_url": user.get("avatar_url", ""),
        })
        redirect_url = f"http://127.0.0.1:{desktop_port}?{params}"
        return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Wiii — Đăng nhập thành công</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;background:#faf9f7">
<div style="text-align:center">
<h2 style="color:#c75b1e">Đăng nhập thành công!</h2>
<p style="color:#666">Đang quay lại Wiii...</p>
<script>window.location.href="{redirect_url}";</script>
</div></body></html>""")

    # Web flow: return JSON
    return JSONResponse({
        "access_token": token_pair.access_token,
        "refresh_token": token_pair.refresh_token,
        "token_type": "bearer",
        "expires_in": token_pair.expires_in,
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url"),
            "role": user.get("role", "student"),
        },
    })


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

@router.post("/token/refresh")
async def token_refresh(request: Request):
    """Refresh an access token using a refresh token."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    result = await refresh_access_token(refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return JSONResponse({
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "token_type": "bearer",
        "expires_in": result.expires_in,
    })


@router.post("/logout")
async def logout(request: Request):
    """Revoke all refresh tokens for the authenticated user (logout everywhere)."""
    from app.core.security import require_auth
    from fastapi.security import APIKeyHeader, HTTPBearer

    # Simple token extraction from Authorization header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")

    token = auth_header.split(" ", 1)[1]
    try:
        from app.auth.token_service import verify_access_token
        payload = verify_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    count = await revoke_user_tokens(payload.sub)
    return JSONResponse({"revoked": count, "message": "Logged out successfully"})


@router.get("/me")
async def get_current_user(request: Request):
    """Get the current authenticated user's profile."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")

    token = auth_header.split(" ", 1)[1]
    try:
        from app.auth.token_service import verify_access_token
        payload = verify_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    from app.auth.user_service import find_user_by_email
    # Fetch full user from DB
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, name, avatar_url, role, is_active, created_at FROM users WHERE id = $1",
                payload.sub,
            )
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return JSONResponse({
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "avatar_url": row["avatar_url"],
                "role": row["role"],
                "is_active": row["is_active"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })
    except HTTPException:
        raise
    except Exception:
        # Fallback to token claims
        return JSONResponse({
            "id": payload.sub,
            "email": payload.email,
            "name": payload.name,
            "role": payload.role,
        })
