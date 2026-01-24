"""Authentication via Supabase Auth."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.models import UserRole

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    try:
        from app.db.supabase_client import get_supabase
        client = get_supabase()
        response = client.auth.get_user(jwt=creds.credentials)
        user = response.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    profile = _get_profile(user.id)
    if profile is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.id,
        "email": user.email or "",
        "full_name": profile.get("full_name"),
        "role": profile.get("role", "server"),
        "client_id": profile.get("client_id"),
    }


def require_role(role: UserRole):
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] != role.value:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


def _get_profile(user_id: str) -> dict | None:
    try:
        from app.db.supabase_client import get_supabase
        client = get_supabase()
        result = client.table("profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            return None
        return result.data[0]
    except Exception:
        return None
