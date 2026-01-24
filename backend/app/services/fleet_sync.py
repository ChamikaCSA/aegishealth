"""Sync orchestrator fleet state to Supabase client_registry."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def sync_fleet() -> None:
    """Write current orchestrator fleet to Supabase client_registry. Removes clients no longer in orchestrator."""
    try:
        from app.core.orchestrator import get_orchestrator
        from app.db.supabase_client import get_supabase

        orchestrator = get_orchestrator()
        client = get_supabase()
        clients = orchestrator.get_active_clients()
        orchestrator_ids = {c.client_id for c in clients}
        now = datetime.now(timezone.utc).isoformat()

        result = client.table("client_registry").select("client_id").execute()
        for row in result.data or []:
            cid = row["client_id"]
            if cid not in orchestrator_ids:
                client.table("client_registry").delete().eq("client_id", cid).execute()

        for c in clients:
            client.table("client_registry").upsert(
                {
                    "client_id": c.client_id,
                    "num_samples": c.num_samples,
                    "status": c.status,
                    "last_heartbeat": now,
                    "updated_at": now,
                },
                on_conflict="client_id",
            ).execute()
    except Exception as e:
        logger.debug("Fleet sync to Supabase failed: %s", e)
