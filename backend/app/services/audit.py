"""Audit logging service for compliance and traceability."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db.models import AuditEventType
from app.db.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


def log_event_sync(
    event_type: AuditEventType,
    actor_id: UUID | None = None,
    job_id: int | None = None,
    client_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an audit event to Supabase (synchronous, for use from sync contexts)."""
    try:
        AuditRepository.insert(
            event_type,
            actor_id=actor_id,
            job_id=job_id,
            client_id=client_id,
            details=details,
        )
    except Exception as e:
        logger.debug("Supabase unavailable for audit: %s", e)
    logger.info("AUDIT: %s | job=%s | client=%s | %s",
                event_type.value, job_id, client_id, details)


async def log_event(
    event_type: AuditEventType,
    actor_id: UUID | None = None,
    job_id: int | None = None,
    client_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an audit event to Supabase (async)."""
    try:
        AuditRepository.insert(
            event_type,
            actor_id=actor_id,
            job_id=job_id,
            client_id=client_id,
            details=details,
        )
    except Exception as e:
        logger.debug("Supabase unavailable for audit: %s", e)
    logger.info("AUDIT: %s | job=%s | client=%s | %s",
                event_type.value, job_id, client_id, details)
