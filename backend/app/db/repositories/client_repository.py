"""Repository for client (participating site) data access."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ClientRegistrationError
from app.db.supabase_client import get_supabase


class ClientRepository:
    """Data access for clients and auth users."""

    @staticmethod
    def create_client(name: str, region: str | None = None) -> dict[str, Any]:
        """Create a new client record. Returns the created row."""
        result = get_supabase().table("clients").insert({
            "name": name.strip(),
            "region": (region.strip() or None) if region else None,
            "status": "active",
        }).execute()

        if not result.data:
            raise ClientRegistrationError("Failed to create client", status_code=500)
        return result.data[0]

    @staticmethod
    def link_user_to_client(client_id: int, user_id: str) -> None:
        """Link an auth user to a client."""
        get_supabase().table("clients").update({"user_id": user_id}).eq("id", client_id).execute()

    @staticmethod
    def delete_client(client_id: int) -> None:
        """Delete a client (rollback on registration failure)."""
        get_supabase().table("clients").delete().eq("id", client_id).execute()
