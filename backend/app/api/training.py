"""Training orchestration: start/stop jobs. Job creation is done via Supabase from frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import get_current_user, require_role
from app.db.models import UserRole, AuditEventType
from app.schemas.training import (
    JobStartResponse,
    JobStopResponse,
    ReleaseModelResponse,
    ModelDownloadResponse,
    ReleasedJob,
)
from app.services.audit import log_event
from app.services.training_service import start_job, stop_job
from app.services.model_service import release_model as release_model_svc, get_model_download_url
from app.db.repositories.job_repository import JobRepository
from app.core.exceptions import JobNotFoundError

router = APIRouter()


@router.post("/jobs/{job_id}/start", response_model=JobStartResponse)
async def start_training(
    job_id: int,
    user: dict = Depends(require_role(UserRole.SERVER)),
):
    """Fetch job from Supabase, create in orchestrator, start training."""
    result = start_job(job_id)
    await log_event(AuditEventType.JOB_STARTED, job_id=job_id)
    return JobStartResponse(**result)


@router.post("/jobs/{job_id}/stop", response_model=JobStopResponse)
async def stop_training(
    job_id: int,
    user: dict = Depends(require_role(UserRole.SERVER)),
):
    """Stop a running training job."""
    result = stop_job(job_id)
    await log_event(AuditEventType.JOB_STOPPED, job_id=job_id)
    return JobStopResponse(**result)


@router.post("/jobs/{job_id}/release", response_model=ReleaseModelResponse)
async def release_model(
    job_id: int,
    user: dict = Depends(require_role(UserRole.SERVER)),
):
    """Release the model for a completed job so participating clients can download it."""
    try:
        result = release_model_svc(job_id)
        await log_event(
            AuditEventType.MODEL_RELEASED,
            actor_id=user.get("id"),
            job_id=job_id,
        )
        return ReleaseModelResponse(**result)
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/model", response_model=ModelDownloadResponse)
async def get_model_url(
    job_id: int,
    format: str = Query(..., pattern="^(pt|onnx)$"),
    user: dict = Depends(get_current_user),
):
    """Get a signed URL to download the model. Server: any job with model. Client: released jobs they participated in."""
    try:
        url = get_model_download_url(
            job_id,
            format,
            user_role=user["role"],
            user_client_id=user.get("client_id"),
        )
        return ModelDownloadResponse(url=url)
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/released-models", response_model=list[ReleasedJob])
async def get_released_models(
    user: dict = Depends(require_role(UserRole.CLIENT)),
):
    """Get jobs the current client participated in that have released models."""
    client_id = user.get("client_id")
    if not client_id:
        return []

    jobs = JobRepository.get_job_list_with_released_models()
    participating_ids = set()
    for job in jobs:
        participating = JobRepository.get_participating_client_ids(job["id"])
        if client_id in participating:
            participating_ids.add(job["id"])

    result = []
    for job in jobs:
        if job["id"] in participating_ids:
            result.append(
                ReleasedJob(
                    id=job["id"],
                    best_accuracy=job.get("best_accuracy", 0),
                    best_f1_score=job.get("best_f1_score", 0),
                    model_path_pt=job.get("model_path_pt"),
                    model_path_onnx=job.get("model_path_onnx"),
                    model_released_at=job.get("model_released_at"),
                )
            )
    return result
