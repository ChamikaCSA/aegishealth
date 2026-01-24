"""
FedProx / FedAvg Aggregation for AegisHealth.

Implements weighted federated averaging with support for:
- Standard FedAvg (baseline)
- FedProx (proximal term applied during local training, standard avg at server)
- HE-based secure aggregation (via TenSEAL CKKS, when ``use_he=True``)
"""

from __future__ import annotations

import logging
from collections import OrderedDict

import torch

from app.ml.he_engine import secure_aggregate, create_he_context

logger = logging.getLogger(__name__)


def federated_average(
    global_state: dict[str, torch.Tensor],
    client_states: list[dict[str, torch.Tensor]],
    client_weights: list[float] | None = None,
) -> dict[str, torch.Tensor]:
    """
    Weighted average of client model states (FedAvg).
    For FedProx, the proximal term is applied during local training;
    server-side aggregation is identical to FedAvg.
    """
    if not client_states:
        return global_state

    n_clients = len(client_states)

    if client_weights is None:
        client_weights = [1.0 / n_clients] * n_clients
    else:
        total = sum(client_weights)
        client_weights = [w / total for w in client_weights]

    avg_state = OrderedDict()
    for key in global_state:
        avg_state[key] = torch.zeros_like(global_state[key], dtype=torch.float32)
        for i, state in enumerate(client_states):
            avg_state[key] += client_weights[i] * state[key].float()

    return avg_state


def federated_average_updates(
    global_state: dict[str, torch.Tensor],
    client_updates: list[dict[str, torch.Tensor]],
    client_weights: list[float] | None = None,
) -> dict[str, torch.Tensor]:
    """
    Alternative: average model updates (deltas) and apply to global model.
    Useful when DP noise is added to updates rather than full states.
    """
    if not client_updates:
        return global_state

    n_clients = len(client_updates)
    if client_weights is None:
        client_weights = [1.0 / n_clients] * n_clients
    else:
        total = sum(client_weights)
        client_weights = [w / total for w in client_weights]

    avg_update = OrderedDict()
    for key in global_state:
        avg_update[key] = torch.zeros_like(global_state[key], dtype=torch.float32)
        for i, update in enumerate(client_updates):
            avg_update[key] += client_weights[i] * update[key].float()

    new_state = OrderedDict()
    for key in global_state:
        new_state[key] = global_state[key].float() + avg_update[key]

    return new_state


def secure_federated_average(
    global_state: dict[str, torch.Tensor],
    client_states: list[dict[str, torch.Tensor]],
    client_weights: list[float] | None = None,
    he_context=None,
) -> tuple[dict[str, torch.Tensor], dict]:
    """Weighted FedAvg with HE secure aggregation.

    If *he_context* is ``None`` a fresh context is created automatically.
    Returns the aggregated state dict **and** a stats dict with
    encryption / aggregation / decryption timings and size overhead.
    """
    if not client_states:
        return global_state, {}

    if client_weights is None:
        client_weights = [1.0] * len(client_states)

    if he_context is None:
        he_context = create_he_context()

    aggregated, stats = secure_aggregate(client_states, client_weights, he_context)
    return aggregated, stats


class FedProxAggregator:
    """
    Stateful aggregator that manages the global model and performs
    weighted averaging each round.  Uses HE (CKKS) for secure
    aggregation when ``use_he=True``.
    """

    def __init__(
        self,
        global_state: dict[str, torch.Tensor],
        mu: float = 0.01,
        use_he: bool = False,
    ):
        self.global_state = {k: v.clone() for k, v in global_state.items()}
        self.mu = mu
        self.round_number = 0
        self.use_he = use_he
        self._he_context = None
        self.last_he_stats: dict | None = None

        if use_he:
            self._he_context = create_he_context()
            logger.info("HE secure aggregation enabled (CKKS).")

    def aggregate(
        self,
        client_states: list[dict[str, torch.Tensor]],
        client_num_samples: list[int],
    ) -> dict[str, torch.Tensor]:
        """Perform one round of aggregation."""
        weights = [float(n) for n in client_num_samples]

        if self.use_he and self._he_context is not None:
            self.global_state, self.last_he_stats = secure_federated_average(
                self.global_state, client_states, weights,
                he_context=self._he_context,
            )
        else:
            self.global_state = federated_average(
                self.global_state, client_states, weights
            )
            self.last_he_stats = None

        self.round_number += 1
        return self.get_global_state()

    def aggregate_updates(
        self,
        client_updates: list[dict[str, torch.Tensor]],
        client_num_samples: list[int],
    ) -> dict[str, torch.Tensor]:
        """Perform one round of update-based aggregation (for DP)."""
        weights = [float(n) for n in client_num_samples]
        self.global_state = federated_average_updates(
            self.global_state, client_updates, weights
        )
        self.round_number += 1
        return self.get_global_state()

    def get_global_state(self) -> dict[str, torch.Tensor]:
        return {k: v.clone() for k, v in self.global_state.items()}

    def get_global_flat_params(self) -> torch.Tensor:
        return torch.cat([v.view(-1) for v in self.global_state.values()])
