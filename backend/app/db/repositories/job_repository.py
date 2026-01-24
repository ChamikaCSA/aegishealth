"""Repository for training job and round data access."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import JobNotFoundError
from app.db.supabase_client import get_supabase


class JobRepository:
    """Data access for training jobs and rounds."""

    @staticmethod
    def get_job(job_id: int) -> dict[str, Any] | None:
        """Fetch a training job by ID."""
        result = get_supabase().table("training_jobs").select("*").eq("id", job_id).execute()
        if not result.data:
            return None
        return result.data[0]

    @staticmethod
    def get_job_or_raise(job_id: int) -> dict[str, Any]:
        """Fetch job or raise JobNotFoundError."""
        job = JobRepository.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    @staticmethod
    def update_job_status(
        job_id: int,
        status: str,
        *,
        started_at: str | None = None,
        current_round: int | None = None,
        best_accuracy: float | None = None,
        best_f1_score: float | None = None,
        best_auc_roc: float | None = None,
        completed_at: str | None = None,
        model_path_pt: str | None = None,
        model_path_onnx: str | None = None,
    ) -> bool:
        """Update job status and optional fields."""
        payload: dict[str, Any] = {"status": status}
        if started_at is not None:
            payload["started_at"] = started_at
        if current_round is not None:
            payload["current_round"] = current_round
        if best_accuracy is not None:
            payload["best_accuracy"] = best_accuracy
        if best_f1_score is not None:
            payload["best_f1_score"] = best_f1_score
        if best_auc_roc is not None:
            payload["best_auc_roc"] = best_auc_roc
        if completed_at is not None:
            payload["completed_at"] = completed_at
        if model_path_pt is not None:
            payload["model_path_pt"] = model_path_pt
        if model_path_onnx is not None:
            payload["model_path_onnx"] = model_path_onnx

        result = get_supabase().table("training_jobs").update(payload).eq("id", job_id).execute()
        return bool(result.data)

    @staticmethod
    def insert_round(
        job_id: int,
        round_number: int,
        global_loss: float | None = None,
        global_accuracy: float | None = None,
        global_f1_score: float | None = None,
        global_auc_roc: float | None = None,
        participating_clients: int | None = None,
        aggregation_time_ms: float | None = None,
        cumulative_epsilon: float | None = None,
    ) -> int | None:
        """Insert a training round and return its ID."""
        payload: dict[str, Any] = {
            "job_id": job_id,
            "round_number": round_number,
            "global_loss": global_loss,
            "global_accuracy": global_accuracy,
            "participating_clients": participating_clients,
            "aggregation_time_ms": aggregation_time_ms,
        }
        if global_f1_score is not None:
            payload["global_f1_score"] = global_f1_score
        if global_auc_roc is not None:
            payload["global_auc_roc"] = global_auc_roc
        if cumulative_epsilon is not None:
            payload["cumulative_epsilon"] = cumulative_epsilon
        result = get_supabase().table("training_rounds").insert(payload).execute()
        if result.data:
            return result.data[0]["id"]
        return None

    @staticmethod
    def insert_client_update(
        round_id: int,
        client_id: int,
        local_loss: float | None = None,
        local_accuracy: float | None = None,
        samples_used: int | None = None,
        dp_epsilon_spent: float | None = None,
        cumulative_epsilon: float | None = None,
        training_time_ms: float | None = None,
    ) -> None:
        """Insert a client update for a round."""
        payload: dict[str, Any] = {
            "round_id": round_id,
            "client_id": client_id,
            "local_loss": local_loss,
            "local_accuracy": local_accuracy,
            "samples_used": samples_used,
            "dp_epsilon_spent": dp_epsilon_spent,
            "training_time_ms": training_time_ms,
        }
        if cumulative_epsilon is not None:
            payload["cumulative_epsilon"] = cumulative_epsilon
        get_supabase().table("client_updates").insert(payload).execute()

    @staticmethod
    def release_model(job_id: int) -> bool:
        """Set model_released_at for a job. Returns True if updated."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = (
            get_supabase()
            .table("training_jobs")
            .update({"model_released_at": now})
            .eq("id", job_id)
            .execute()
        )
        return bool(result.data)

    @staticmethod
    def get_participating_client_ids(job_id: int) -> list[int]:
        """Return distinct client_ids that participated in any round of this job."""
        rounds_result = (
            get_supabase()
            .table("training_rounds")
            .select("id")
            .eq("job_id", job_id)
            .execute()
        )
        round_ids = [r["id"] for r in (rounds_result.data or [])]
        if not round_ids:
            return []
        updates_result = (
            get_supabase()
            .table("client_updates")
            .select("client_id")
            .in_("round_id", round_ids)
            .execute()
        )
        client_ids = list({r["client_id"] for r in (updates_result.data or [])})
        return client_ids

    @staticmethod
    def get_job_list_with_released_models() -> list[dict[str, Any]]:
        """Return jobs that have released models (model_released_at IS NOT NULL)."""
        result = (
            get_supabase()
            .table("training_jobs")
            .select("id, best_accuracy, best_f1_score, model_path_pt, model_path_onnx, model_released_at")
            .not_.is_("model_released_at", "null")
            .execute()
        )
        return result.data or []
