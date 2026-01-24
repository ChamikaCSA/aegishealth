"""Admin endpoints for client management (server role only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_role
from app.db.models import UserRole
from app.schemas.admin import RegisterClientRequest, RegisterClientResponse
from app.services.admin_service import register_client

router = APIRouter()
_server_only = Depends(require_role(UserRole.SERVER))


@router.post("/clients", dependencies=[_server_only], response_model=RegisterClientResponse)
async def register_client_endpoint(body: RegisterClientRequest):
    """Create a client (participating site) and its auth user in one step."""
    result = register_client(
        name=body.name,
        region=body.region,
        email=body.email,
        password=body.password,
    )
    return RegisterClientResponse(**result)
