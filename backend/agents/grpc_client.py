"""gRPC client for edge agent to communicate with the Central Orchestrator."""

from __future__ import annotations

import io
import logging

import grpc
import torch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.grpc import federated_pb2, federated_pb2_grpc

logger = logging.getLogger(__name__)


def serialize_state_dict(state_dict: dict[str, torch.Tensor]) -> bytes:
    buf = io.BytesIO()
    torch.save(state_dict, buf)
    return buf.getvalue()


def deserialize_state_dict(data: bytes) -> dict[str, torch.Tensor]:
    buf = io.BytesIO(data)
    return torch.load(buf, weights_only=True)


class OrchestratorClient:
    """gRPC client that connects edge agents to the central orchestrator."""

    def __init__(
        self,
        server_address: str = "localhost:50051",
        tls_cert: str | None = None,
    ):
        from app.core.config import settings

        ca_path = Path(tls_cert) if tls_cert else Path(settings.grpc_tls_ca)
        if not ca_path.exists():
            raise RuntimeError(
                f"TLS CA certificate not found at {ca_path}. "
                "Run scripts/generate_dev_certs.sh or start the server first "
                "(it auto-generates dev certs)."
            )
        with open(ca_path, "rb") as f:
            creds = grpc.ssl_channel_credentials(f.read())
        self.channel = grpc.secure_channel(server_address, creds)

        self.stub = federated_pb2_grpc.FederatedLearningStub(self.channel)

    def connect(self, client_id: int, num_samples: int) -> tuple[bool, str]:
        response = self.stub.ConnectClient(
            federated_pb2.ConnectRequest(
                client_id=client_id,
                num_samples=num_samples,
            )
        )
        return response.accepted, response.client_id

    def get_global_model(
        self, client_id: str, job_id: int
    ) -> tuple[dict[str, torch.Tensor], int, dict]:
        response = self.stub.GetGlobalModel(
            federated_pb2.ModelRequest(client_id=client_id, job_id=job_id)
        )
        state_dict = deserialize_state_dict(response.model_weights)
        config = {
            "local_epochs": response.config.local_epochs,
            "learning_rate": response.config.learning_rate,
            "fedprox_mu": response.config.fedprox_mu,
            "dp_epsilon": response.config.dp_epsilon,
            "dp_delta": response.config.dp_delta,
            "dp_max_grad_norm": response.config.dp_max_grad_norm,
            "batch_size": response.config.batch_size,
            "class_weight_multiplier": response.config.class_weight_multiplier or 1.0,
        }
        return state_dict, response.round_number, config

    def submit_update(
        self,
        client_id: str,
        job_id: int,
        round_number: int,
        update: dict[str, torch.Tensor],
        metrics: dict,
    ) -> tuple[bool, str]:
        update_bytes = serialize_state_dict(update)
        response = self.stub.SubmitUpdate(
            federated_pb2.UpdateRequest(
                client_id=client_id,
                job_id=job_id,
                round_number=round_number,
                model_update=update_bytes,
                metrics=federated_pb2.UpdateMetrics(
                    local_loss=metrics.get("local_loss", 0),
                    local_accuracy=metrics.get("local_accuracy", 0),
                    num_samples=metrics.get("num_samples", 0),
                    dp_epsilon_spent=metrics.get("dp_epsilon_spent", 0),
                    training_time_ms=metrics.get("training_time_ms", 0),
                    f1=metrics.get("f1", 0),
                    auc_roc=metrics.get("auc_roc", 0),
                    cumulative_epsilon=metrics.get("cumulative_epsilon", 0),
                    optimal_threshold=metrics.get("optimal_threshold", 0.5),
                    precision=metrics.get("precision", 0),
                    recall=metrics.get("recall", 0),
                ),
            )
        )
        return response.accepted, response.message

    def heartbeat(self, client_id: str) -> tuple[str, int]:
        """Returns (status, active_job_id). active_job_id is 0 when no job is running."""
        import time
        response = self.stub.Heartbeat(
            federated_pb2.HeartbeatRequest(
                client_id=client_id,
                timestamp=int(time.time() * 1000),
            )
        )
        return response.status, int(response.active_job_id or 0)

    def disconnect(self, client_id: str) -> None:
        """Disconnect from orchestrator when shutting down."""
        try:
            self.stub.DisconnectClient(
                federated_pb2.DisconnectRequest(client_id=client_id)
            )
        except Exception:
            pass

    def close(self):
        self.channel.close()
