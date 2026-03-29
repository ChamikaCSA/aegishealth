"""
Differential Privacy Engine for AegisHealth.

Production DP for federated clients uses **Opacus** during local SGD (per-sample
gradient clipping and noise), not post-hoc noise on model updates.
"""

from __future__ import annotations

import torch.nn as nn
from torch.utils.data import DataLoader
from opacus import PrivacyEngine


class DPEngine:
    """Wraps Opacus PrivacyEngine for federated DP training."""

    def __init__(
        self,
        epsilon: float = 8.0,
        delta: float = 1e-5,
        max_grad_norm: float = 1.0,
        noise_multiplier: float | None = None,
    ):
        self.epsilon = epsilon
        self.delta = delta
        self.max_grad_norm = max_grad_norm
        self.noise_multiplier = noise_multiplier
        self.epsilon_spent = 0.0

    def make_private(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        data_loader: DataLoader,
        epochs: int = 1,
    ) -> tuple[nn.Module, torch.optim.Optimizer, DataLoader]:
        """Wrap model/optimizer/dataloader with Opacus DP.

        *model* must already be Opacus-compatible (e.g. from ``create_model()``).
        """
        privacy_engine = PrivacyEngine()

        model, optimizer, data_loader = privacy_engine.make_private_with_epsilon(
            module=model,
            optimizer=optimizer,
            data_loader=data_loader,
            epochs=epochs,
            target_epsilon=self.epsilon,
            target_delta=self.delta,
            max_grad_norm=self.max_grad_norm,
        )

        self._privacy_engine = privacy_engine
        return model, optimizer, data_loader

    def get_epsilon_spent(self) -> float:
        if hasattr(self, "_privacy_engine"):
            return self._privacy_engine.get_epsilon(self.delta)
        return self.epsilon_spent


class PrivacyAccountant:
    """Tracks cumulative privacy budget (epsilon) across federated rounds.

    Uses basic sequential composition: total epsilon is the sum of
    per-round epsilon values.  This gives a conservative upper bound;
    advanced composition (e.g. Rényi DP) would yield tighter estimates
    than sequential composition (e.g. as reported by Opacus during local training).
    """

    def __init__(self, epsilon_budget: float, delta: float = 1e-5):
        self.epsilon_budget = epsilon_budget
        self.delta = delta
        self._round_epsilons: list[float] = []

    def record_round(self, epsilon_spent: float):
        """Record the epsilon consumed in one communication round."""
        self._round_epsilons.append(epsilon_spent)

    @property
    def total_epsilon_spent(self) -> float:
        return sum(self._round_epsilons)

    @property
    def budget_remaining(self) -> float:
        return max(0.0, self.epsilon_budget - self.total_epsilon_spent)

    @property
    def num_rounds(self) -> int:
        return len(self._round_epsilons)

    @property
    def budget_exhausted(self) -> bool:
        return self.total_epsilon_spent >= self.epsilon_budget

    def summary(self) -> dict:
        """Return a serialisable snapshot of the accounting state."""
        return {
            "epsilon_budget": self.epsilon_budget,
            "delta": self.delta,
            "total_epsilon_spent": self.total_epsilon_spent,
            "budget_remaining": self.budget_remaining,
            "num_rounds": self.num_rounds,
            "budget_exhausted": self.budget_exhausted,
        }
