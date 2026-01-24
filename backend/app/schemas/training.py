"""Schemas for training API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobStartResponse(BaseModel):
    """Response after starting a training job."""

    status: str = Field(..., description="Job status after start")
    job_id: int = Field(..., description="Training job ID")


class JobStopResponse(BaseModel):
    """Response after stopping a training job."""

    status: str = Field(..., description="Job status after stop")
    job_id: int = Field(..., description="Training job ID")


class ReleaseModelResponse(BaseModel):
    """Response after releasing a model."""

    released: bool = Field(..., description="Whether the model was released")
    message: str | None = Field(None, description="Optional message")


class ModelDownloadResponse(BaseModel):
    """Response with signed URL for model download."""

    url: str = Field(..., description="Signed URL for downloading the model")


class ReleasedJob(BaseModel):
    """Job that a client can download (released, participated)."""

    id: int
    best_accuracy: float
    best_f1_score: float
    model_path_pt: str | None
    model_path_onnx: str | None
    model_released_at: str | None
