"""
Training service: job start/stop logic and persistence callback.

Extracts business logic from API routes for testability and reuse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.orchestrator import get_orchestrator
from app.db.repositories.job_repository import JobRepository
from app.db.models import AuditEventType
from app.services.audit import log_event_sync
from app.services.fleet_sync import sync_fleet
from app.services.model_export import export_and_upload_final_model

logger = logging.getLogger(__name__)


def _register_persistence() -> None:
    """Register orchestrator callback to persist rounds to Supabase and chain next round."""
    orchestrator = get_orchestrator()

    def on_round_complete(
        job_id: int,
        round_metrics: dict,
        client_ids: list,
        metrics_list: list,
    ) -> None:
        try:
            sync_fleet()
            job = orchestrator.get_job_state(job_id)
            if job is None:
                return

            round_num = round_metrics.get("round", 0)

            if round_metrics.get("skipped"):
                logger.warning(
                    "Round %d skipped (quorum not met) for job %d — chaining next round",
                    round_num, job_id,
                )
                log_event_sync(
                    AuditEventType.ROUND_COMPLETED,
                    job_id=job_id,
                    details={"round": round_num, "skipped": True},
                )
                if job.current_round < job.total_rounds:
                    orchestrator.start_round(job_id)
                    job_after = orchestrator.get_job_state(job_id)
                    if job_after:
                        JobRepository.update_job_status(
                            job_id,
                            "running",
                            current_round=job_after.current_round,
                        )
                        log_event_sync(
                            AuditEventType.ROUND_STARTED,
                            job_id=job_id,
                            details={"round": job_after.current_round},
                        )
                    sync_fleet()
                else:
                    pt_path, onnx_path = export_and_upload_final_model(job_id)
                    log_event_sync(AuditEventType.JOB_COMPLETED, job_id=job_id)
                    orchestrator.set_all_clients_idle()
                    orchestrator.finish_job(job_id)
                    sync_fleet()
                    completed_at = datetime.now(timezone.utc).isoformat()
                    JobRepository.update_job_status(
                        job_id,
                        "completed",
                        completed_at=completed_at,
                        model_path_pt=pt_path,
                        model_path_onnx=onnx_path,
                    )
                return

            round_id = JobRepository.insert_round(
                job_id=job_id,
                round_number=round_num,
                global_loss=round_metrics.get("global_loss"),
                global_accuracy=round_metrics.get("global_accuracy"),
                global_f1_score=round_metrics.get("global_f1"),
                global_auc_roc=round_metrics.get("global_auc_roc"),
                participating_clients=round_metrics.get("participating_clients"),
                aggregation_time_ms=round_metrics.get("aggregation_time_ms"),
                cumulative_epsilon=round_metrics.get("cumulative_epsilon"),
            )

            if round_id:
                active_clients = orchestrator.get_active_clients()
                for i, cid in enumerate(client_ids):
                    cinfo = next(
                        (c for c in active_clients if str(c.client_id) == str(cid)),
                        None,
                    )
                    if cinfo and i < len(metrics_list):
                        m = metrics_list[i]
                        JobRepository.insert_client_update(
                            round_id=round_id,
                            client_id=cinfo.client_id,
                            local_loss=m.get("local_loss"),
                            local_accuracy=m.get("local_accuracy"),
                            samples_used=m.get("num_samples"),
                            dp_epsilon_spent=m.get("dp_epsilon_spent"),
                            cumulative_epsilon=m.get("cumulative_epsilon"),
                            training_time_ms=m.get("training_time_ms"),
                        )
                        log_event_sync(
                            AuditEventType.CLIENT_UPDATE_RECEIVED,
                            job_id=job_id,
                            client_id=cinfo.client_id,
                            details={"dp_epsilon_spent": m.get("dp_epsilon_spent")},
                        )

            best_acc = round_metrics.get("global_accuracy", 0)
            best_f1 = round_metrics.get("global_f1", 0)
            best_auc = round_metrics.get("global_auc_roc", 0)
            JobRepository.update_job_status(
                job_id,
                "running",
                current_round=round_num,
                best_accuracy=best_acc,
                best_f1_score=best_f1,
                best_auc_roc=best_auc,
            )

            if job.current_round < job.total_rounds:
                log_event_sync(
                    AuditEventType.ROUND_COMPLETED,
                    job_id=job_id,
                    details={
                        "round": round_metrics.get("round"),
                        "participating_clients": round_metrics.get("participating_clients"),
                    },
                )
                orchestrator.start_round(job_id)
                job_after = orchestrator.get_job_state(job_id)
                if job_after:
                    JobRepository.update_job_status(
                        job_id,
                        "running",
                        current_round=job_after.current_round,
                    )
                    log_event_sync(
                        AuditEventType.ROUND_STARTED,
                        job_id=job_id,
                        details={"round": job_after.current_round},
                    )
                sync_fleet()
            else:
                pt_path, onnx_path = export_and_upload_final_model(job_id)
                log_event_sync(AuditEventType.JOB_COMPLETED, job_id=job_id)
                orchestrator.set_all_clients_idle()
                orchestrator.finish_job(job_id)
                sync_fleet()
                completed_at = datetime.now(timezone.utc).isoformat()
                JobRepository.update_job_status(
                    job_id,
                    "completed",
                    completed_at=completed_at,
                    model_path_pt=pt_path,
                    model_path_onnx=onnx_path,
                )
        except Exception as e:
            logger.exception("Persistence callback failed for job %d: %s", job_id, e)

    orchestrator.on_round_complete(on_round_complete)


def start_job(job_id: int) -> dict:
    """
    Start a training job. Fetches job from DB, creates in orchestrator, starts round.

    Returns:
        {"status": "started", "job_id": int}
    """
    job_row = JobRepository.get_job_or_raise(job_id)
    config = job_row.get("config") or {}
    total_rounds = job_row.get("total_rounds", 50)

    orchestrator = get_orchestrator()
    orchestrator.create_job(job_id=job_id, config={**config, "num_rounds": total_rounds})

    now = datetime.now(timezone.utc).isoformat()
    JobRepository.update_job_status(job_id, "running", started_at=now)

    orchestrator.start_round(job_id)
    job_state = orchestrator.get_job_state(job_id)
    if job_state:
        JobRepository.update_job_status(
            job_id,
            "running",
            current_round=job_state.current_round,
        )
    sync_fleet()

    return {"status": "started", "job_id": job_id}


def stop_job(job_id: int) -> dict:
    """
    Stop a training job.

    Returns:
        {"status": "stopped", "job_id": int}
    """
    orchestrator = get_orchestrator()
    orchestrator.set_all_clients_idle()
    orchestrator.finish_job(job_id)

    updated = JobRepository.update_job_status(job_id, "stopped")
    if not updated:
        from app.core.exceptions import JobNotFoundError
        raise JobNotFoundError(job_id)

    sync_fleet()
    return {"status": "stopped", "job_id": job_id}


# Register persistence on module load
_register_persistence()
