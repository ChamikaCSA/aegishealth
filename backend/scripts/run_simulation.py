"""
FL Simulation Runner: runs the full federated training loop in-process.

Simulates multiple edge agents as threads, coordinating through the orchestrator.
Supports both FedProx and baseline FedAvg for benchmarking.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.orchestrator import Orchestrator
from app.data.preprocessor import preprocess_client_data
from app.data.partitioner import discover_clients, select_clients
from app.ml.dp_engine import PrivacyAccountant
from agents.local_trainer import LocalTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("simulation")


def run_federated_simulation(
    num_clients: int = 10,
    num_rounds: int = 50,
    local_epochs: int = 5,
    lr: float = 0.001,
    batch_size: int = 64,
    fedprox_mu: float = 0.01,
    dp_epsilon: float = 8.0,
    dp_delta: float = 1e-5,
    dp_max_grad_norm: float = 1.0,
    use_dp: bool = True,
    client_strategy: str = "largest",
    data_dir: str | None = None,
    output_dir: str = "results",
    class_weight_multiplier: float = 1.0,
    threshold_beta: float = 1.0,
) -> dict:
    """Run a complete federated training simulation."""

    def _model_size_bytes(state_dict: dict[str, torch.Tensor]) -> int:
        buf = io.BytesIO()
        torch.save(state_dict, buf)
        return buf.tell()

    raw_base = Path(data_dir) if data_dir else Path(settings.raw_client_data_dir)
    all_clients = discover_clients(raw_base)

    if not all_clients:
        raise RuntimeError(f"No client directories found in {raw_base}. "
                           "Run split_eicu_by_client first.")

    logger.info("Discovered %d client directories in %s", len(all_clients), raw_base)

    client_data: dict[int, tuple[np.ndarray, np.ndarray, int]] = {}
    for cid, cdir in all_clients.items():
        X, y, nf = preprocess_client_data(cdir)
        if len(X) > 0:
            client_data[cid] = (X, y, nf)

    summary = {
        "samples_per_client": {str(cid): len(d[0]) for cid, d in client_data.items()},
        "event_rate_per_client": {str(cid): float(d[1].mean()) for cid, d in client_data.items()},
    }

    selected = select_clients(summary, num_clients, client_strategy)
    logger.info("Selected %d clients: %s", len(selected), selected)

    trainers: dict[int, LocalTrainer] = {}
    n_features = 0
    for cid in selected:
        X, y, nf = client_data[cid]
        n_features = nf
        trainers[cid] = LocalTrainer(
            client_id=cid,
            client_X=X,
            client_y=y,
            input_size=nf,
        )

    orchestrator = Orchestrator()
    config = {
        "num_rounds": num_rounds,
        "local_epochs": local_epochs,
        "learning_rate": lr,
        "batch_size": batch_size,
        "fedprox_mu": fedprox_mu,
        "dp_epsilon": dp_epsilon,
        "dp_delta": dp_delta,
        "dp_max_grad_norm": dp_max_grad_norm,
        "n_features": n_features,
        "min_clients_per_round": 2,
        "class_weight_multiplier": class_weight_multiplier,
        "threshold_beta": threshold_beta,
    }

    job = orchestrator.create_job(job_id=1, config=config)

    for cid, trainer in trainers.items():
        orchestrator.connect_client(
            client_id=cid,
            num_samples=trainer.num_samples,
        )

    history = []
    privacy_accountant = PrivacyAccountant(
        epsilon_budget=dp_epsilon * num_rounds if use_dp else float("inf"),
        delta=dp_delta,
    )

    for round_num in range(1, num_rounds + 1):
        round_start = time.time()
        orchestrator.start_round(job_id=1)

        global_state = orchestrator.get_global_model(1)
        if global_state is None:
            logger.error("Failed to get global model")
            break
        global_state_dict, _, _ = global_state

        round_losses = []
        round_accs = []
        round_f1s = []
        round_aucs = []
        round_precisions = []
        round_recalls = []
        round_thresholds = []
        comm_bytes_down = _model_size_bytes(global_state_dict) * len(trainers)
        comm_bytes_up = 0

        for cid, trainer in trainers.items():
            local_state, metrics = trainer.train_round(
                global_state=global_state_dict,
                epochs=local_epochs,
                lr=lr,
                batch_size=batch_size,
                fedprox_mu=fedprox_mu,
                dp_epsilon=dp_epsilon,
                dp_delta=dp_delta,
                dp_max_grad_norm=dp_max_grad_norm,
                use_dp=use_dp,
                class_weight_multiplier=class_weight_multiplier,
                threshold_beta=threshold_beta,
            )

            comm_bytes_up += _model_size_bytes(local_state)

            orchestrator.receive_update(
                client_id=str(cid),
                job_id=1,
                round_number=round_num,
                update=local_state,
                metrics={
                    "local_loss": metrics["local_loss"],
                    "local_accuracy": metrics["local_accuracy"],
                    "num_samples": metrics["num_samples"],
                    "dp_epsilon_spent": metrics["dp_epsilon_spent"],
                    "cumulative_epsilon": metrics["cumulative_epsilon"],
                    "training_time_ms": metrics["training_time_ms"],
                    "f1": metrics.get("f1", 0),
                    "auc_roc": metrics.get("auc_roc", 0),
                    "precision": metrics.get("precision", 0),
                    "recall": metrics.get("recall", 0),
                    "optimal_threshold": metrics.get("optimal_threshold", 0.5),
                },
            )

            round_losses.append(metrics["local_loss"])
            round_accs.append(metrics["local_accuracy"])
            round_f1s.append(metrics.get("f1", 0))
            round_aucs.append(metrics.get("auc_roc", 0))
            round_precisions.append(metrics.get("precision", 0))
            round_recalls.append(metrics.get("recall", 0))
            round_thresholds.append(metrics.get("optimal_threshold", 0.5))

        round_time = (time.time() - round_start) * 1000

        avg_loss = np.mean(round_losses)
        avg_acc = np.mean(round_accs)
        avg_f1 = np.mean(round_f1s)
        avg_auc = np.mean(round_aucs)
        avg_precision = np.mean(round_precisions)
        avg_recall = np.mean(round_recalls)
        avg_threshold = np.mean(round_thresholds)

        if use_dp and dp_epsilon > 0:
            privacy_accountant.record_round(dp_epsilon)

        round_info = {
            "round": round_num,
            "avg_loss": float(avg_loss),
            "avg_accuracy": float(avg_acc),
            "avg_f1": float(avg_f1),
            "avg_auc_roc": float(avg_auc),
            "avg_precision": float(avg_precision),
            "avg_recall": float(avg_recall),
            "optimal_threshold": float(avg_threshold),
            "round_time_ms": float(round_time),
            "num_clients": len(trainers),
            "comm_bytes_down": comm_bytes_down,
            "comm_bytes_up": comm_bytes_up,
            "cumulative_epsilon": privacy_accountant.total_epsilon_spent,
        }
        history.append(round_info)

        logger.info(
            "Round %d/%d: loss=%.4f, acc=%.4f, f1=%.4f, auc=%.4f, prec=%.4f, rec=%.4f, thresh=%.3f",
            round_num, num_rounds, avg_loss, avg_acc, avg_f1, avg_auc,
            avg_precision, avg_recall, avg_threshold,
        )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    total_comm_bytes = sum(r["comm_bytes_down"] + r["comm_bytes_up"] for r in history)

    results = {
        "config": config,
        "num_clients": len(trainers),
        "selected_clients": selected,
        "history": history,
        "final_loss": history[-1]["avg_loss"] if history else None,
        "final_accuracy": history[-1]["avg_accuracy"] if history else None,
        "final_f1": history[-1]["avg_f1"] if history else None,
        "final_auc_roc": history[-1]["avg_auc_roc"] if history else None,
        "final_precision": history[-1]["avg_precision"] if history else None,
        "final_recall": history[-1]["avg_recall"] if history else None,
        "optimal_threshold": history[-1]["optimal_threshold"] if history else None,
        "total_comm_bytes": total_comm_bytes,
        "total_comm_mb": round(total_comm_bytes / (1024 * 1024), 2),
        "privacy_accountant": privacy_accountant.summary(),
        "total_epsilon_spent": privacy_accountant.total_epsilon_spent,
    }

    exp_name = f"fedprox_mu{fedprox_mu}_eps{dp_epsilon}_clients{num_clients}"
    with open(out_path / f"{exp_name}.json", "w") as f:
        json.dump(results, f, indent=2)

    logger.info("Results saved to %s/%s.json", out_path, exp_name)
    return results


def main():
    parser = argparse.ArgumentParser(description="AegisHealth FL Simulation")
    parser.add_argument("--num-clients", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--local-epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--fedprox-mu", type=float, default=0.01)
    parser.add_argument("--dp-epsilon", type=float, default=8.0)
    parser.add_argument("--no-dp", action="store_true")
    parser.add_argument("--strategy", default="largest", choices=["largest", "random", "diverse"])
    parser.add_argument("--data-dir", default=None,
                        help="Path to raw client data base dir (default: data/raw/)")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--class-weight-multiplier", type=float, default=1.0,
                        help=">1.0 boosts recall; <1.0 reduces false positives")
    parser.add_argument("--threshold-beta", type=float, default=1.0,
                        help="F-beta parameter for optimal threshold search (>1 favors recall)")
    args = parser.parse_args()

    run_federated_simulation(
        num_clients=args.num_clients,
        num_rounds=args.rounds,
        local_epochs=args.local_epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        fedprox_mu=args.fedprox_mu,
        dp_epsilon=args.dp_epsilon,
        use_dp=not args.no_dp,
        client_strategy=args.strategy,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        class_weight_multiplier=args.class_weight_multiplier,
        threshold_beta=args.threshold_beta,
    )


if __name__ == "__main__":
    main()
