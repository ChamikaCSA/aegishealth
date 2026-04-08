"""
Headless Edge Agent daemon.

Runs on a client server, connects to the Central Orchestrator via gRPC,
trains locally on the client's data partition, and submits DP-protected updates.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.grpc_client import OrchestratorClient
from agents.local_trainer import LocalTrainer
from app.data.preprocessor import preprocess_client_data
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(level="INFO")
logger = logging.getLogger("agents")


class EdgeAgent:
    """Autonomous daemon that participates in federated training."""

    def __init__(
        self,
        client_id: int,
        server_address: str = "localhost:50051",
        data_dir: str | None = None,
        tls_cert: str | None = None,
        tls_server_name: str | None = None,
    ):
        self.client_id = client_id
        self.server_address = server_address

        raw_dir = Path(data_dir) if data_dir else Path(settings.raw_client_data_dir) / f"client_{client_id}"

        logger.info("Preprocessing data for client %d from %s ...", client_id, raw_dir)
        client_X, client_y, n_features = preprocess_client_data(raw_dir)

        if len(client_X) == 0:
            raise ValueError(f"No valid training samples for client {client_id} in {raw_dir}")

        self.trainer = LocalTrainer(
            client_id=client_id,
            client_X=client_X,
            client_y=client_y,
            input_size=n_features,
        )

        self.grpc_client = OrchestratorClient(
            server_address,
            tls_cert=tls_cert,
            tls_server_name=tls_server_name,
        )
        self._connected_client_id: str | None = None

    def connect(self) -> bool:
        accepted, conn_client_id = self.grpc_client.connect(
            client_id=self.client_id,
            num_samples=self.trainer.num_samples,
        )
        if accepted:
            self._connected_client_id = conn_client_id
            logger.info("Connected as %s", conn_client_id)
        else:
            logger.error("Connection rejected")
        return accepted

    def participate_in_round(self, job_id: int, model_data: tuple | None = None) -> bool:
        """Fetch global model (if not provided), train locally, submit update."""
        if not self._connected_client_id:
            logger.error("Not connected")
            return False

        if model_data:
            global_state, round_num, config, he_context_bytes = model_data
        else:
            try:
                global_state, round_num, config, he_context_bytes = self.grpc_client.get_global_model(
                    self._connected_client_id, job_id
                )
            except Exception as e:
                logger.error("Failed to get global model: %s", e)
                return False

        logger.info("Starting training: Round %d | Epochs: %d | Mu: %.3f | Eps: %.1f",
                     round_num, config["local_epochs"], config["fedprox_mu"],
                     config["dp_epsilon"])

        local_state, metrics = self.trainer.train_round(
            global_state=global_state,
            epochs=config["local_epochs"],
            lr=config["learning_rate"],
            batch_size=config["batch_size"],
            fedprox_mu=config["fedprox_mu"],
            dp_epsilon=config["dp_epsilon"],
            dp_delta=config["dp_delta"],
            dp_max_grad_norm=config["dp_max_grad_norm"],
            class_weight_multiplier=config.get("class_weight_multiplier", 1.0),
        )

        update = local_state
        is_encrypted = False

        if config.get("use_he", False) and he_context_bytes:
            from app.ml.he_engine import encrypt_state_dict, serialize_encrypted_state
            import tenseal as ts
            logger.info("Encrypting local update with HE...")
            t0 = time.time()
            public_ctx = ts.context_from(he_context_bytes)
            enc_vecs, meta = encrypt_state_dict(local_state, public_ctx)
            keys = list(local_state.keys())
            update = serialize_encrypted_state(enc_vecs, keys, meta)
            is_encrypted = True
            metrics["encrypt_time_ms"] = (time.time() - t0) * 1000

        logger.info("Training done: loss=%.4f, acc=%.4f, time=%.0fms",
                     metrics["local_loss"], metrics["local_accuracy"],
                     metrics["training_time_ms"])

        accepted, msg = self.grpc_client.submit_update(
            client_id=self._connected_client_id,
            job_id=job_id,
            round_number=round_num,
            update=update,
            metrics=metrics,
            is_encrypted=is_encrypted,
        )

        logger.info("Round %d update %s (Server: %s)", round_num, "accepted" if accepted else "rejected", msg)
        return accepted

    def _shutdown(self):
        """Disconnect from orchestrator and close connection."""
        if self._connected_client_id:
            logger.info("Disconnecting from orchestrator...")
            self.grpc_client.disconnect(self._connected_client_id)
            self._connected_client_id = None
        self.grpc_client.close()

    def run_daemon(self, poll_interval: float = 5.0):
        """Run in daemon mode, polling the orchestrator for rounds. Auto-discovers active job from heartbeat."""
        if not self.connect():
            return

        shutdown_requested = False

        def _on_signal(signum, frame):
            nonlocal shutdown_requested
            shutdown_requested = True
            logger.info("Received signal %s, shutting down...", signum)

        try:
            signal.signal(signal.SIGTERM, _on_signal)
        except (ValueError, OSError):
            pass  # SIGTERM not available on this platform (e.g. Windows)
        signal.signal(signal.SIGINT, _on_signal)

        logger.info("Daemon started. Polling every %.1fs (auto-discovering active job)...", poll_interval)
        last_round: dict[int, int] = {}

        while not shutdown_requested:
            try:
                status, job_id = self.grpc_client.heartbeat(self._connected_client_id)
                if status == "training" and job_id > 0:
                    try:
                        result = self.grpc_client.get_global_model(
                            self._connected_client_id, job_id
                        )
                        _, round_num, _, _ = result
                        
                        prev = last_round.get(job_id, 0)
                        if round_num > prev:
                            self.participate_in_round(job_id, model_data=result)
                            last_round[job_id] = round_num
                        else:
                            logger.debug("Waiting for next round (Current: %d)", round_num)
                    except Exception as e:
                        logger.debug("Polling update: %s", str(e))
                time.sleep(poll_interval)
            except KeyboardInterrupt:
                logger.info("Shutting down agent...")
                break
            except Exception as e:
                if shutdown_requested:
                    break
                logger.error("Error: %s", e)
                time.sleep(poll_interval)

        self._shutdown()


def main():
    parser = argparse.ArgumentParser(description="AegisHealth Edge Agent")
    parser.add_argument("--client-id", type=int, required=True)
    parser.add_argument("--server", default="localhost:50051")
    parser.add_argument("--data-dir", default=None,
                        help="Path to raw CSV directory (default: data/raw/client_{id}/)")
    parser.add_argument("--tls-cert", default="certs/ca.crt",
                        help="Path to CA certificate for TLS (default: certs/ca.crt)")
    parser.add_argument(
        "--tls-server-name",
        default=None,
        metavar="NAME",
        help="TLS hostname for cert verification (default: localhost when --server uses an IP)",
    )
    parser.add_argument("--poll-interval", type=float, default=5.0)
    args = parser.parse_args()

    agent = EdgeAgent(
        client_id=args.client_id,
        server_address=args.server,
        data_dir=args.data_dir,
        tls_cert=args.tls_cert,
        tls_server_name=args.tls_server_name,
    )
    agent.run_daemon(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
