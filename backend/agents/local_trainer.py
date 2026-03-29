"""Local training logic for the edge agent."""

from __future__ import annotations

import logging

import numpy as np
import torch

from app.ml.lstm_model import LSTMAnomalyDetector, create_model
from app.ml.trainer import (
    train_local,
    evaluate,
    get_device,
    find_optimal_threshold,
    collect_probs,
)
from app.data.loader import create_data_loaders

logger = logging.getLogger(__name__)


class LocalTrainer:
    """Manages local model training on a client's data partition."""

    def __init__(
        self,
        client_id: int,
        client_X: np.ndarray,
        client_y: np.ndarray,
        input_size: int = 11,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        val_ratio: float = 0.2,
    ):
        self.client_id = client_id
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.device = get_device()

        rng = np.random.default_rng(42)
        indices = np.arange(len(client_X))
        rng.shuffle(indices)

        val_size = int(len(indices) * val_ratio)
        val_idx = indices[:val_size]
        train_idx = indices[val_size:]

        self.X_train = client_X[train_idx]
        self.y_train = client_y[train_idx]
        self.X_val = client_X[val_idx]
        self.y_val = client_y[val_idx]

        self.model = create_model(input_size, hidden_size, num_layers, dropout)
        self.cumulative_epsilon = 0.0
        logger.info(
            "LocalTrainer initialized for client %d (%d train, %d val samples)",
            client_id, len(self.X_train), len(self.X_val),
        )

    @property
    def num_samples(self) -> int:
        return len(self.X_train)

    def set_model_state(self, state_dict: dict[str, torch.Tensor]):
        self.model.load_state_dict(state_dict)

    def train_round(
        self,
        global_state: dict[str, torch.Tensor],
        epochs: int = 5,
        lr: float = 0.001,
        batch_size: int = 64,
        fedprox_mu: float = 0.01,
        dp_epsilon: float = 8.0,
        dp_delta: float = 1e-5,
        dp_max_grad_norm: float = 1.0,
        use_dp: bool = True,
        class_weight_multiplier: float = 1.0,
        threshold_beta: float = 1.0,
    ) -> tuple[dict[str, torch.Tensor], dict]:
        """
        Execute one federated round of local training.
        Returns the trained weights (Opacus DP applied during SGD when enabled) and metrics.
        """
        self.model.load_state_dict(global_state)
        global_flat = torch.cat([p.data.view(-1) for p in self.model.parameters()])

        train_loader, val_loader = create_data_loaders(
            self.X_train, self.y_train,
            self.X_val, self.y_val,
            batch_size=batch_size,
        )

        result = train_local(
            model=self.model,
            train_loader=train_loader,
            epochs=epochs,
            lr=lr,
            fedprox_mu=fedprox_mu,
            global_params=global_flat,
            device=self.device,
            class_weight_multiplier=class_weight_multiplier,
            use_dp=use_dp and dp_epsilon > 0,
            dp_epsilon=dp_epsilon,
            dp_delta=dp_delta,
            dp_max_grad_norm=dp_max_grad_norm,
        )

        final_state = result.state_dict
        eps_spent = result.dp_epsilon_spent
        self.model.load_state_dict(final_state)

        self.cumulative_epsilon += eps_spent

        val_labels, val_probs = collect_probs(
            self.model, val_loader, device=self.device,
        )
        opt_thresh, _ = find_optimal_threshold(
            val_labels, val_probs, beta=threshold_beta,
        )
        val_result = evaluate(
            self.model, val_loader, device=self.device, threshold=opt_thresh,
        )

        metrics = {
            "local_loss": result.loss,
            "local_accuracy": val_result.accuracy,
            "num_samples": self.num_samples,
            "dp_epsilon_spent": eps_spent,
            "cumulative_epsilon": self.cumulative_epsilon,
            "training_time_ms": result.training_time_ms,
            "f1": val_result.f1,
            "auc_roc": val_result.auc_roc,
            "precision": val_result.precision,
            "recall": val_result.recall,
            "optimal_threshold": opt_thresh,
        }

        return final_state, metrics
