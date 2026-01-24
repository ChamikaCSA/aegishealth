"""Repository for audit log data access."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.db.models import AuditEventType
from app.db.supabase_client import get_supabase


class AuditRepository:
    """Data access for audit logs."""

    @staticmethod
    def insert(
        event_type: AuditEventType,
        *,
        actor_id: UUID | str | None = None,
        job_id: int | None = None,
        client_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Insert an audit log entry."""
        entry = {
            "event_type": event_type.value,
            "actor_id": str(actor_id) if actor_id else None,
            "job_id": job_id,
            "client_id": client_id,
            "details": details or {},
        }
        get_supabase().table("audit_logs").insert(entry).execute()
