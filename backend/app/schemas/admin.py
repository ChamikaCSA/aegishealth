"""Schemas for admin API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterClientRequest(BaseModel):
    """Request to register a new client (participating site)."""

    name: str = Field(..., min_length=1, description="Client/hospital name")
    region: str = Field(default="", description="Geographic region")
    email: EmailStr = Field(..., description="Login email for the client user")
    password: str = Field(..., min_length=6, description="Login password")


class RegisterClientResponse(BaseModel):
    """Response after registering a client."""

    id: int = Field(..., description="Client ID")
    name: str = Field(..., description="Client name")
    region: str | None = Field(None, description="Region")
    user_id: str = Field(..., description="Supabase auth user ID")
    email: str = Field(..., description="User email")
