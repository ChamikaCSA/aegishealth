"""
Benchmarking suite for AegisHealth.

Runs systematic experiments to evaluate:
1. FedProx vs FedAvg (mu=0 baseline) under varying non-IID conditions
2. Privacy-utility trade-off at different DP epsilon values
3. Scalability with varying client counts

Results are saved as JSON for analysis and visualization.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.data.preprocessor import preprocess_client_data
from app.data.partitioner import discover_clients, select_clients
from app.data.loader import create_data_loaders
from app.ml.lstm_model import create_model
from app.ml.trainer import train_local, evaluate, get_device
from scripts.run_simulation import run_federated_simulation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmarks")


def run_centralized_baseline(
    num_clients: int = 10,
    num_rounds: int = 30,
    local_epochs: int = 5,
    lr: float = 0.001,
    batch_size: int = 64,
    client_strategy: str = "diverse",
    data_dir: str | None = None,
    output_dir: str = "results/benchmark_fedprox",
) -> dict:
    """Train a centralized (non-FL) baseline by pooling all selected client data."""
    raw_base = Path(data_dir) if data_dir else Path(settings.raw_client_data_dir)
    all_clients = discover_clients(raw_base)

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
    logger.info("Centralized baseline: pooling %d clients: %s", len(selected), selected)

    X_all, y_all = [], []
    n_features = 0
    for cid in selected:
        X, y, nf = client_data[cid]
        X_all.append(X)
        y_all.append(y)
        n_features = nf

    X_all = np.concatenate(X_all)
    y_all = np.concatenate(y_all)

    rng = np.random.default_rng(42)
    indices = np.arange(len(X_all))
    rng.shuffle(indices)
    val_size = int(len(indices) * 0.2)
    train_idx, val_idx = indices[val_size:], indices[:val_size]

    train_loader, val_loader = create_data_loaders(
        X_all[train_idx], y_all[train_idx],
        X_all[val_idx], y_all[val_idx],
        batch_size=batch_size,
    )

    model = create_model(n_features)
    device = get_device()
    total_epochs = num_rounds * local_epochs

    start = time.time()
    result = train_local(
        model=model,
        train_loader=train_loader,
        epochs=total_epochs,
        lr=lr,
        fedprox_mu=0.0,
        device=device,
    )
    training_time = (time.time() - start) * 1000

    val_result = evaluate(model, val_loader, device=device)

    out = {
        "label": "Centralized",
        "config": {
            "num_clients": num_clients,
            "total_epochs": total_epochs,
            "lr": lr,
            "batch_size": batch_size,
        },
        "num_clients": num_clients,
        "selected_clients": selected,
        "final_loss": result.loss,
        "final_accuracy": val_result.accuracy,
        "final_f1": val_result.f1,
        "final_auc_roc": val_result.auc_roc,
        "final_precision": val_result.precision,
        "final_recall": val_result.recall,
        "optimal_threshold": val_result.threshold,
        "training_time_ms": training_time,
        "num_train_samples": len(train_idx),
        "num_val_samples": len(val_idx),
        "total_comm_bytes": 0,
        "total_comm_mb": 0.0,
    }

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    with open(out_path / "centralized_baseline.json", "w") as f:
        json.dump(out, f, indent=2)

    logger.info(
        "Centralized baseline: acc=%.4f, f1=%.4f, auc=%.4f",
        val_result.accuracy, val_result.f1, val_result.auc_roc,
    )
    return out


def benchmark_fedprox_vs_fedavg(
    num_clients: int = 10,
    num_rounds: int = 30,
    output_dir: str = "results/benchmark_fedprox",
    data_dir: str | None = None,
):
    """Experiment 1: Compare FedProx (varying mu) vs FedAvg (mu=0)."""
    mu_values = [0.0, 0.001, 0.01, 0.1, 1.0]
    all_results = []

    logger.info("=== Running Centralized Baseline ===")
    centralized = run_centralized_baseline(
        num_clients=num_clients,
        num_rounds=num_rounds,
        client_strategy="diverse",
        data_dir=data_dir,
        output_dir=output_dir,
    )
    all_results.append(centralized)

    for mu in mu_values:
        label = "FedAvg" if mu == 0 else f"FedProx(mu={mu})"
        logger.info("=== Running %s ===", label)

        results = run_federated_simulation(
            num_clients=num_clients,
            num_rounds=num_rounds,
            fedprox_mu=mu,
            dp_epsilon=0,
            use_dp=False,
            client_strategy="diverse",
            data_dir=data_dir,
            output_dir=output_dir,
        )
        results["label"] = label
        results["mu"] = mu
        all_results.append(results)

    out_path = Path(output_dir) / "fedprox_comparison.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info("FedProx vs FedAvg results saved to %s", out_path)
    return all_results


def benchmark_privacy_utility(
    num_clients: int = 10,
    num_rounds: int = 30,
    output_dir: str = "results/benchmark_privacy",
    data_dir: str | None = None,
):
    """Experiment 2: Privacy-utility trade-off at different epsilon values."""
    epsilon_values = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
    all_results = []

    no_dp = run_federated_simulation(
        num_clients=num_clients,
        num_rounds=num_rounds,
        fedprox_mu=0.01,
        use_dp=False,
        client_strategy="largest",
        data_dir=data_dir,
        output_dir=output_dir,
    )
    no_dp["label"] = "No DP (baseline)"
    no_dp["epsilon"] = float("inf")
    all_results.append(no_dp)

    for eps in epsilon_values:
        logger.info("=== Running DP epsilon=%s ===", eps)
        results = run_federated_simulation(
            num_clients=num_clients,
            num_rounds=num_rounds,
            fedprox_mu=0.01,
            dp_epsilon=eps,
            use_dp=True,
            client_strategy="largest",
            data_dir=data_dir,
            output_dir=output_dir,
        )
        results["label"] = f"DP(eps={eps})"
        results["epsilon"] = eps
        all_results.append(results)

    out_path = Path(output_dir) / "privacy_utility_tradeoff.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info("Privacy-utility results saved to %s", out_path)
    return all_results


def benchmark_scalability(
    num_rounds: int = 20,
    output_dir: str = "results/benchmark_scalability",
    data_dir: str | None = None,
):
    """Experiment 3: Performance at different numbers of clients."""
    client_counts = [3, 5, 10, 20, 50]
    all_results = []

    for n in client_counts:
        logger.info("=== Running with %d clients ===", n)
        results = run_federated_simulation(
            num_clients=n,
            num_rounds=num_rounds,
            fedprox_mu=0.01,
            dp_epsilon=8.0,
            use_dp=True,
            client_strategy="largest",
            data_dir=data_dir,
            output_dir=output_dir,
        )
        results["label"] = f"{n} clients"
        results["n_clients"] = n
        all_results.append(results)

    out_path = Path(output_dir) / "scalability.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info("Scalability results saved to %s", out_path)
    return all_results


def generate_summary(output_dir: str = "results"):
    """Generate a markdown summary of all benchmark results."""
    base = Path(output_dir)
    summary_lines = ["# AegisHealth Benchmark Results\n"]

    for subdir in ["benchmark_fedprox", "benchmark_privacy", "benchmark_scalability"]:
        path = base / subdir
        if not path.exists():
            continue

        summary_lines.append(f"\n## {subdir.replace('benchmark_', '').title()}\n")

        for json_file in sorted(path.glob("*.json")):
            if json_file.name.startswith("fedprox_mu") or json_file.name.startswith("fedprox_mu0"):
                continue

            with open(json_file) as f:
                data = json.load(f)

            rows = data if isinstance(data, list) else [data]
            if rows:
                summary_lines.append(f"### {json_file.stem}\n")
                summary_lines.append(
                    "| Experiment | Final Loss | Accuracy | F1 | AUC-ROC "
                    "| Precision | Recall | Threshold | Comm (MB) |"
                )
                summary_lines.append(
                    "|------------|-----------|----------|------|---------|"
                    "-----------|--------|-----------|-----------|"
                )
                for exp in rows:
                    label = exp.get("label", "?")
                    loss = exp.get("final_loss", "N/A")
                    acc = exp.get("final_accuracy", "N/A")
                    f1 = exp.get("final_f1", "N/A")
                    auc = exp.get("final_auc_roc", "N/A")
                    prec = exp.get("final_precision", "N/A")
                    rec = exp.get("final_recall", "N/A")
                    thresh = exp.get("optimal_threshold", "N/A")
                    comm = exp.get("total_comm_mb", "N/A")
                    if isinstance(acc, float):
                        acc = f"{acc*100:.1f}%"
                    if isinstance(loss, float):
                        loss = f"{loss:.4f}"
                    if isinstance(f1, float):
                        f1 = f"{f1:.4f}"
                    if isinstance(auc, float):
                        auc = f"{auc:.4f}"
                    if isinstance(prec, float):
                        prec = f"{prec:.4f}"
                    if isinstance(rec, float):
                        rec = f"{rec:.4f}"
                    if isinstance(thresh, float):
                        thresh = f"{thresh:.3f}"
                    if isinstance(comm, (int, float)):
                        comm = f"{comm:.2f}"
                    summary_lines.append(
                        f"| {label} | {loss} | {acc} | {f1} | {auc} "
                        f"| {prec} | {rec} | {thresh} | {comm} |"
                    )
                summary_lines.append("")

    summary_path = base / "BENCHMARK_SUMMARY.md"
    with open(summary_path, "w") as f:
        f.write("\n".join(summary_lines))

    logger.info("Summary written to %s", summary_path)


def main():
    parser = argparse.ArgumentParser(description="AegisHealth Benchmarks")
    parser.add_argument("--experiment", choices=["fedprox", "privacy", "scalability", "all"], default="all")
    parser.add_argument("--num-clients", type=int, default=10)
    parser.add_argument("--num-rounds", type=int, default=30)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    if args.experiment in ("fedprox", "all"):
        benchmark_fedprox_vs_fedavg(
            num_clients=args.num_clients,
            num_rounds=args.num_rounds,
            data_dir=args.data_dir,
            output_dir=f"{args.output_dir}/benchmark_fedprox",
        )

    if args.experiment in ("privacy", "all"):
        benchmark_privacy_utility(
            num_clients=args.num_clients,
            num_rounds=args.num_rounds,
            data_dir=args.data_dir,
            output_dir=f"{args.output_dir}/benchmark_privacy",
        )

    if args.experiment in ("scalability", "all"):
        benchmark_scalability(
            num_rounds=args.num_rounds,
            data_dir=args.data_dir,
            output_dir=f"{args.output_dir}/benchmark_scalability",
        )

    generate_summary(args.output_dir)


if __name__ == "__main__":
    main()
