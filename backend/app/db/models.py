"""Enums and types used by the backend."""

from __future__ import annotations
from enum import Enum


class UserRole(str, Enum):
    SERVER = "server"
    CLIENT = "client"


class AuditEventType(str, Enum):
    """Audit event types for compliance and traceability. Aligns with DB audit_event_type enum."""
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_STOPPED = "job_stopped"
    ROUND_STARTED = "round_started"
    ROUND_COMPLETED = "round_completed"
    CLIENT_REGISTERED = "client_registered"
    CLIENT_CONNECTED = "client_connected"
    CLIENT_UPDATE_RECEIVED = "client_update_received"
    MODEL_DISTRIBUTED = "model_distributed"
    MODEL_AGGREGATED = "model_aggregated"
    MODEL_RELEASED = "model_released"
    USER_LOGIN = "user_login"
    USER_CREATED = "user_created"
