"""gRPC servicer implementing the FederatedLearning service."""

from __future__ import annotations

import io
import logging
import time

import torch
import grpc

from app.db.models import AuditEventType
from app.grpc import federated_pb2, federated_pb2_grpc

logger = logging.getLogger(__name__)


def serialize_state_dict(state_dict: dict[str, torch.Tensor]) -> bytes:
    buf = io.BytesIO()
    torch.save(state_dict, buf)
    return buf.getvalue()


def deserialize_state_dict(data: bytes) -> dict[str, torch.Tensor]:
    buf = io.BytesIO(data)
    return torch.load(buf, weights_only=True)


class FederatedLearningServicer(federated_pb2_grpc.FederatedLearningServicer):
    """Implements the gRPC FederatedLearning service."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def ConnectClient(self, request, context):
        success, client_id, msg = self.orchestrator.connect_client(
            client_id=int(request.client_id),
            num_samples=request.num_samples,
        )
        if success:
            from app.services.audit import log_event_sync
            from app.services.fleet_sync import sync_fleet
            log_event_sync(
                AuditEventType.CLIENT_CONNECTED,
                client_id=int(request.client_id),
                details={"num_samples": request.num_samples},
            )
            sync_fleet()
        return federated_pb2.ConnectResponse(
            accepted=success,
            client_id=client_id,
            message=msg,
        )

    def GetGlobalModel(self, request, context):
        result = self.orchestrator.get_global_model(request.job_id)
        if result is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("No active job or model found")
            return federated_pb2.ModelResponse()

        state_dict, round_num, config, he_ctx_bytes = result
        model_bytes = serialize_state_dict(state_dict)

        return federated_pb2.ModelResponse(
            job_id=request.job_id,
            round_number=round_num,
            model_weights=model_bytes,
            config=federated_pb2.TrainingConfig(
                local_epochs=config.get("local_epochs", 5),
                learning_rate=config.get("learning_rate", 0.001),
                fedprox_mu=config.get("fedprox_mu", 0.01),
                dp_epsilon=config.get("dp_epsilon", 8.0),
                dp_delta=config.get("dp_delta", 1e-5),
                dp_max_grad_norm=config.get("dp_max_grad_norm", 1.0),
                batch_size=config.get("batch_size", 64),
                class_weight_multiplier=config.get("class_weight_multiplier", 1.0),
                use_he=config.get("use_he", False),
            ),
            he_context=he_ctx_bytes,
        )

    def SubmitUpdate(self, request, context):
        if request.is_encrypted:
            update_data = request.model_update
        else:
            update_data = deserialize_state_dict(request.model_update)

        accepted, msg = self.orchestrator.receive_update(
            client_id=request.client_id,
            job_id=request.job_id,
            round_number=request.round_number,
            update=update_data,
            metrics={
                "local_loss": request.metrics.local_loss,
                "local_accuracy": request.metrics.local_accuracy,
                "num_samples": request.metrics.num_samples,
                "dp_epsilon_spent": request.metrics.dp_epsilon_spent,
                "cumulative_epsilon": request.metrics.cumulative_epsilon,
                "training_time_ms": request.metrics.training_time_ms,
                "f1": request.metrics.f1,
                "auc_roc": request.metrics.auc_roc,
                "optimal_threshold": request.metrics.optimal_threshold,
                "precision": request.metrics.precision,
                "recall": request.metrics.recall,
            },
        )
        if accepted:
            from app.services.fleet_sync import sync_fleet
            sync_fleet()
        return federated_pb2.UpdateResponse(accepted=accepted, message=msg)

    def Heartbeat(self, request, context):
        status = self.orchestrator.get_client_status(request.client_id)
        active_job_id = self.orchestrator.get_active_job_id() or 0
        return federated_pb2.HeartbeatResponse(
            alive=True,
            status=status or "idle",
            active_job_id=active_job_id,
        )

    def DisconnectClient(self, request, context):
        """Agent disconnects when shutting down. Removes from orchestrator and client_registry."""
        from app.db.supabase_client import get_supabase

        try:
            client_id = int(request.client_id)
            self.orchestrator.disconnect_client(client_id)
            get_supabase().table("client_registry").delete().eq("client_id", client_id).execute()
        except (ValueError, TypeError):
            pass
        return federated_pb2.DisconnectResponse(acknowledged=True)
