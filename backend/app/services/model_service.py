"""Model release and download service."""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import JobNotFoundError
from app.db.repositories.job_repository import JobRepository
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def release_model(job_id: int) -> dict[str, Any]:
    """
    Release the model for a completed job. Server only.
    Returns {"released": True} on success.
    Raises JobNotFoundError, ValueError if job cannot be released.
    """
    job = JobRepository.get_job(job_id)
    if job is None:
        raise JobNotFoundError(job_id)

    if job.get("status") != "completed":
        raise ValueError("Only completed jobs can be released")

    if not job.get("model_path_pt") and not job.get("model_path_onnx"):
        raise ValueError("Job has no model to release")

    if job.get("model_released_at"):
        return {"released": True, "message": "Already released"}

    updated = JobRepository.release_model(job_id)
    if not updated:
        raise JobNotFoundError(job_id)

    return {"released": True}


def get_model_download_url(
    job_id: int,
    format: str,
    *,
    user_role: str,
    user_client_id: int | None,
) -> str:
    """
    Get a signed URL for downloading the model.
    Server: can download any job with model.
    Client: can download only if model is released and client participated.
    Returns the signed URL string.
    """
    job = JobRepository.get_job(job_id)
    if job is None:
        raise JobNotFoundError(job_id)

    path = job.get("model_path_pt") if format == "pt" else job.get("model_path_onnx")
    if not path:
        raise ValueError(f"No {format.upper()} model available for this job")

    if user_role == "server":
        pass  # Server can always download
    elif user_role == "client":
        if not job.get("model_released_at"):
            raise ValueError("Model not yet released")
        if user_client_id is None:
            raise ValueError("Client not linked to a site")
        participating = JobRepository.get_participating_client_ids(job_id)
        if user_client_id not in participating:
            raise ValueError("You did not participate in this job")
    else:
        raise ValueError("Invalid role")

    client = get_supabase()
    result = client.storage.from_("models").create_signed_url(path, 300)
    signed_url = (
        result.get("signed_url")
        or result.get("signedUrl")
        or result.get("path")
    )
    if not signed_url or not str(signed_url).startswith("http"):
        logger.error("Failed to create signed URL: %s", result)
        raise ValueError("Failed to generate download link")
    return str(signed_url)
