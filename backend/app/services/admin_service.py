"""Admin service: client registration and management."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ClientRegistrationError
from app.db.repositories.client_repository import ClientRepository
from app.db.supabase_client import get_supabase
from app.services.audit import log_event_sync
from app.db.models import AuditEventType


def register_client(name: str, region: str, email: str, password: str) -> dict[str, Any]:
    """
    Create a client (participating site) and its auth user in one step.

    Returns:
        {"id": int, "name": str, "region": str|None, "user_id": str, "email": str}
    """
    region_clean = (region or "").strip() or None
    client_row = ClientRepository.create_client(name=name.strip(), region=region_clean)
    client_id = client_row["id"]

    try:
        res = get_supabase().auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "role": "client",
                "client_id": client_id,
                "full_name": name.strip(),
            },
        })
    except Exception as e:
        ClientRepository.delete_client(client_id)
        raise ClientRegistrationError(str(e), status_code=400)

    user = res.user
    if not user:
        ClientRepository.delete_client(client_id)
        raise ClientRegistrationError("Failed to create user", status_code=500)

    ClientRepository.link_user_to_client(client_id, user.id)
    log_event_sync(AuditEventType.CLIENT_REGISTERED, client_id=client_id)

    return {
        "id": client_id,
        "name": client_row["name"],
        "region": client_row.get("region"),
        "user_id": user.id,
        "email": user.email or "",
    }
