"""Common schemas used across API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service health status")
    service: str = Field(default="aegishealth-orchestrator", description="Service name")
    orchestrator_ready: bool = Field(default=True, description="Orchestrator initialized")
    supabase_connected: bool = Field(default=True, description="Supabase connectivity")


class ErrorDetail(BaseModel):
    """Structured error response."""

    detail: str = Field(..., description="Error message")
