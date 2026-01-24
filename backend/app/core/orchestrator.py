"""
Central Orchestrator for federated learning.

Manages training jobs, client registry, global model state,
and coordinates the FedProx aggregation loop.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any

import torch

from app.ml.lstm_model import LSTMAnomalyDetector, create_model
from app.ml.dp_engine import PrivacyAccountant
from app.core.aggregator import FedProxAggregator
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ClientInfo:
    client_id: int
    num_samples: int
    status: str = "idle"
    last_heartbeat: float = 0.0


@dataclass
class RoundState:
    round_number: int
    expected_clients: int
    received_updates: list = field(default_factory=list)
    received_metrics: list = field(default_factory=list)
    received_client_ids: list = field(default_factory=list)
    client_num_samples: list = field(default_factory=list)
    start_time: float = 0.0
    deadline: float = 0.0
    completed: bool = False


@dataclass
class JobState:
    job_id: int
    config: dict
    status: str = "pending"
    current_round: int = 0
    total_rounds: int = 50
    round_metrics: list = field(default_factory=list)
    aggregator: FedProxAggregator | None = None
    current_round_state: RoundState | None = None
    privacy_accountant: PrivacyAccountant | None = None


class Orchestrator:
    """Central FL coordinator."""

    def __init__(self):
        self._clients: dict[str, ClientInfo] = {}
        self._jobs: dict[int, JobState] = {}
        self._active_job_id: int | None = None
        self._lock = threading.RLock()
        self._model: LSTMAnomalyDetector | None = None
        self._round_callbacks: list = []
        self._round_timer: threading.Timer | None = None

    def connect_client(self, client_id: int, num_samples: int) -> tuple[bool, str, str]:
        cid_str = str(client_id)
        with self._lock:
            self._clients[cid_str] = ClientInfo(
                client_id=client_id,
                num_samples=num_samples,
                status="idle",
                last_heartbeat=time.time(),
            )
        logger.info("Client connected: %d (samples=%d)", client_id, num_samples)
        return True, cid_str, "Connection successful"

    def create_job(self, job_id: int, config: dict) -> JobState:
        n_features = config.get("n_features", len(self._get_default_features()))
        model = create_model(
            input_size=n_features,
            hidden_size=config.get("lstm_hidden_size", settings.lstm_hidden_size),
            num_layers=config.get("lstm_num_layers", settings.lstm_num_layers),
            dropout=config.get("lstm_dropout", settings.lstm_dropout),
        )
        self._model = model

        aggregator = FedProxAggregator(
            global_state=model.state_dict(),
            mu=config.get("fedprox_mu", settings.default_fedprox_mu),
            use_he=bool(config.get("use_he", False)),
        )

        dp_epsilon = config.get("dp_epsilon", 0)
        num_rounds = config.get("num_rounds", settings.default_num_rounds)
        dp_delta = config.get("dp_delta", 1e-5)
        accountant = None
        if dp_epsilon and dp_epsilon > 0:
            accountant = PrivacyAccountant(
                epsilon_budget=dp_epsilon * num_rounds,
                delta=dp_delta,
            )

        job = JobState(
            job_id=job_id,
            config=config,
            total_rounds=num_rounds,
            aggregator=aggregator,
            privacy_accountant=accountant,
        )

        with self._lock:
            self._jobs[job_id] = job
            self._active_job_id = job_id

        logger.info("Training job %d created with config: %s", job_id, config)
        return job

    def start_round(self, job_id: int) -> int | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            job.current_round += 1
            round_num = job.current_round

            active_clients = [
                c for c in self._clients.values()
                if c.status in ("connected", "idle", "ready", "stale")
            ]
            min_clients = job.config.get("min_clients_per_round", 2)

            if len(active_clients) < min_clients:
                logger.warning(
                    "Not enough clients for round %d (%d/%d)",
                    round_num, len(active_clients), min_clients,
                )

            timeout = job.config.get(
                "round_timeout_seconds", settings.round_timeout_seconds,
            )

            job.current_round_state = RoundState(
                round_number=round_num,
                expected_clients=len(active_clients),
                start_time=time.time(),
                deadline=time.time() + timeout,
            )

            for c in active_clients:
                c.status = "training"

            job.status = "running"

            self._start_round_timer(job_id, round_num, timeout)

        logger.info(
            "Round %d started (expecting %d clients, timeout %.0fs)",
            round_num, len(active_clients), timeout,
        )
        return round_num

    def _start_round_timer(
        self, job_id: int, round_number: int, timeout: float,
    ) -> None:
        """Schedule _on_round_timeout after *timeout* seconds. Must be called under lock."""
        if self._round_timer is not None:
            self._round_timer.cancel()
        self._round_timer = threading.Timer(
            timeout, self._on_round_timeout, args=[job_id, round_number],
        )
        self._round_timer.daemon = True
        self._round_timer.start()

    def _on_round_timeout(self, job_id: int, round_number: int) -> None:
        """Handle round deadline expiry: aggregate if quorum met, skip otherwise."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            rs = job.current_round_state
            if rs is None or rs.completed or rs.round_number != round_number:
                return

            quorum = job.config.get("min_quorum_ratio", settings.min_quorum_ratio)
            min_needed = max(1, int(rs.expected_clients * quorum))

            if len(rs.received_updates) >= min_needed:
                logger.warning(
                    "Round %d timed out with %d/%d updates (quorum met), aggregating",
                    round_number, len(rs.received_updates), rs.expected_clients,
                )
                for cid, c in self._clients.items():
                    if c.status == "training" and cid not in rs.received_client_ids:
                        c.status = "stale"
                self._do_aggregation(job)
            else:
                logger.error(
                    "Round %d timed out with %d/%d updates (quorum NOT met, need %d). "
                    "Round skipped.",
                    round_number, len(rs.received_updates),
                    rs.expected_clients, min_needed,
                )
                rs.completed = True
                for cid, c in self._clients.items():
                    if c.status == "training":
                        c.status = "stale"
                for cb in self._round_callbacks:
                    cb(job.job_id, {"round": round_number, "skipped": True}, [], [])

    def get_global_model(self, job_id: int) -> tuple[dict, int, dict] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.aggregator is None:
                return None

            state = job.aggregator.get_global_state()
            return state, job.current_round, job.config

    def receive_update(
        self,
        client_id: str,
        job_id: int,
        round_number: int,
        update: dict[str, torch.Tensor],
        metrics: dict[str, Any],
    ) -> tuple[bool, str]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False, "Job not found"

            rs = job.current_round_state
            if rs is None or rs.round_number != round_number:
                return False, f"Not expecting updates for round {round_number}"

            if rs.completed:
                return False, "Round already completed"

            rs.received_updates.append(update)
            rs.received_metrics.append(metrics)
            rs.received_client_ids.append(client_id)
            rs.client_num_samples.append(metrics.get("num_samples", 1))

            client = self._clients.get(client_id)
            if client:
                client.status = "idle"

            logger.info(
                "Received update from %s for round %d (%d/%d)",
                client_id, round_number,
                len(rs.received_updates), rs.expected_clients,
            )

            if len(rs.received_updates) >= rs.expected_clients:
                self._do_aggregation(job)

        return True, "Update accepted"

    def _cancel_round_timer(self) -> None:
        if self._round_timer is not None:
            self._round_timer.cancel()
            self._round_timer = None

    def _do_aggregation(self, job: JobState):
        rs = job.current_round_state
        if rs is None:
            return

        self._cancel_round_timer()

        agg_start = time.time()

        new_global = job.aggregator.aggregate(
            client_states=rs.received_updates,
            client_num_samples=rs.client_num_samples,
        )

        agg_time = (time.time() - agg_start) * 1000
        rs.completed = True

        n = len(rs.received_metrics)
        avg_loss = sum(m.get("local_loss", 0) for m in rs.received_metrics) / n
        avg_acc = sum(m.get("local_accuracy", 0) for m in rs.received_metrics) / n
        avg_f1 = sum(m.get("f1", 0) for m in rs.received_metrics) / n
        avg_auc = sum(m.get("auc_roc", 0) for m in rs.received_metrics) / n
        avg_precision = sum(m.get("precision", 0) for m in rs.received_metrics) / n
        avg_recall = sum(m.get("recall", 0) for m in rs.received_metrics) / n
        avg_threshold = sum(m.get("optimal_threshold", 0.5) for m in rs.received_metrics) / n

        model_bytes = sum(v.nelement() * v.element_size() for v in new_global.values())

        avg_eps = sum(m.get("dp_epsilon_spent", 0) for m in rs.received_metrics) / n
        cumulative_epsilon = 0.0
        if job.privacy_accountant is not None and avg_eps > 0:
            job.privacy_accountant.record_round(avg_eps)
            cumulative_epsilon = job.privacy_accountant.total_epsilon_spent

        round_metrics = {
            "round": rs.round_number,
            "global_loss": avg_loss,
            "global_accuracy": avg_acc,
            "global_f1": avg_f1,
            "global_auc_roc": avg_auc,
            "global_precision": avg_precision,
            "global_recall": avg_recall,
            "optimal_threshold": avg_threshold,
            "participating_clients": len(rs.received_updates),
            "aggregation_time_ms": agg_time,
            "model_bytes": model_bytes,
            "cumulative_epsilon": cumulative_epsilon,
        }
        job.round_metrics.append(round_metrics)

        logger.info(
            "Round %d aggregated: loss=%.4f, acc=%.4f, time=%.0fms",
            rs.round_number, avg_loss, avg_acc, agg_time,
        )

        if self._model is not None:
            self._model.load_state_dict(new_global)

        for cb in self._round_callbacks:
            cb(job.job_id, round_metrics, rs.received_client_ids, rs.received_metrics)

    def get_client_status(self, client_id: str) -> str | None:
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return None
            return client.status

    def get_job_state(self, job_id: int) -> JobState | None:
        return self._jobs.get(job_id)

    def get_active_clients(self) -> list[ClientInfo]:
        return list(self._clients.values())

    def set_all_clients_idle(self) -> None:
        """Set all connected clients to idle (e.g. when job completes)."""
        with self._lock:
            for c in self._clients.values():
                c.status = "idle"
        logger.info("All clients set to idle")

    def finish_job(self, job_id: int) -> None:
        """Clear job state when job completes or is stopped."""
        with self._lock:
            self._cancel_round_timer()
            if self._active_job_id == job_id:
                self._active_job_id = None
            if job_id in self._jobs:
                del self._jobs[job_id]
            logger.info("Job %d finished, state cleared", job_id)

    def disconnect_client(self, client_id: int) -> bool:
        """Remove client from fleet (e.g. when agent stops)."""
        cid_str = str(client_id)
        with self._lock:
            if cid_str in self._clients:
                del self._clients[cid_str]
                logger.info("Client disconnected: %d", client_id)
                return True
        return False

    def get_active_job(self) -> JobState | None:
        if self._active_job_id:
            return self._jobs.get(self._active_job_id)
        return None

    def get_active_job_id(self) -> int | None:
        return self._active_job_id

    def on_round_complete(self, callback):
        self._round_callbacks.append(callback)

    def _get_default_features(self):
        from app.data.preprocessor import VITAL_FEATURES
        return VITAL_FEATURES


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
