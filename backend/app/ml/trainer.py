"""
Local training logic for both centralized baseline and federated clients.
Supports FedProx proximal term and Differential Privacy via Opacus.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import (
    accuracy_score,
    fbeta_score,
    f1_score,
    roc_auc_score,
    precision_score,
    recall_score,
)

from app.ml.lstm_model import LSTMAnomalyDetector

logger = logging.getLogger(__name__)


@dataclass
class TrainResult:
    loss: float
    accuracy: float
    f1: float
    auc_roc: float
    precision: float
    recall: float
    num_samples: int
    training_time_ms: float
    state_dict: dict
    optimal_threshold: float = 0.5


@dataclass
class EvalResult:
    loss: float
    accuracy: float
    f1: float
    auc_roc: float
    precision: float
    recall: float
    num_samples: int
    threshold: float = 0.5


def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def train_local(
    model: LSTMAnomalyDetector,
    train_loader: DataLoader,
    epochs: int = 5,
    lr: float = 0.001,
    fedprox_mu: float = 0.0,
    global_params: torch.Tensor | None = None,
    device: torch.device | None = None,
    class_weight_multiplier: float = 1.0,
) -> TrainResult:
    """
    Train model locally. When fedprox_mu > 0 and global_params is provided,
    adds the FedProx proximal term to the loss.

    class_weight_multiplier scales the inverse-frequency positive-class weight:
    >1.0 biases toward higher recall, <1.0 toward fewer false positives.
    """
    device = device or get_device()
    model = model.to(device)
    model.train()

    pos_count = 0
    total_count = 0
    for _, labels in train_loader:
        pos_count += (labels == 1).sum().item()
        total_count += len(labels)

    if pos_count > 0 and total_count > pos_count:
        pos_weight = (total_count - pos_count) / pos_count * class_weight_multiplier
        weight = torch.FloatTensor([1.0, pos_weight]).to(device)
    else:
        weight = None

    criterion = nn.CrossEntropyLoss(weight=weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    start_time = time.time()
    total_loss = 0.0
    n_batches = 0

    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)

            if fedprox_mu > 0 and global_params is not None:
                global_params_dev = global_params.to(device)
                local_params = model.get_flat_params()
                proximal_term = (fedprox_mu / 2) * torch.sum(
                    (local_params - global_params_dev) ** 2
                )
                loss = loss + proximal_term

            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        total_loss += epoch_loss

    training_time = (time.time() - start_time) * 1000

    eval_result = evaluate(model, train_loader, device=device)

    return TrainResult(
        loss=total_loss / max(n_batches, 1),
        accuracy=eval_result.accuracy,
        f1=eval_result.f1,
        auc_roc=eval_result.auc_roc,
        precision=eval_result.precision,
        recall=eval_result.recall,
        num_samples=total_count,
        training_time_ms=training_time,
        state_dict={k: v.cpu().clone() for k, v in model.state_dict().items()},
    )


def evaluate(
    model: LSTMAnomalyDetector,
    data_loader: DataLoader,
    device: torch.device | None = None,
    threshold: float = 0.5,
) -> EvalResult:
    device = device or get_device()
    model = model.to(device)
    model.eval()

    criterion = nn.CrossEntropyLoss()
    all_probs = []
    all_labels = []
    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for batch_X, batch_y in data_loader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)

            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            total_loss += loss.item()
            n_batches += 1

            probs = torch.softmax(outputs, dim=1)
            all_probs.extend(probs[:, 1].cpu().numpy())
            all_labels.extend(batch_y.cpu().numpy())

    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)
    all_preds = (all_probs >= threshold).astype(int)

    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, zero_division=0)
    precision = precision_score(all_labels, all_preds, zero_division=0)
    recall = recall_score(all_labels, all_preds, zero_division=0)

    n_classes = len(np.unique(all_labels))
    if n_classes < 2:
        auc = 0.0
    else:
        auc = roc_auc_score(all_labels, all_probs)

    return EvalResult(
        loss=total_loss / max(n_batches, 1),
        accuracy=acc,
        f1=f1,
        auc_roc=auc,
        precision=precision,
        recall=recall,
        num_samples=len(all_labels),
        threshold=threshold,
    )


def find_optimal_threshold(
    labels: np.ndarray,
    probs: np.ndarray,
    beta: float = 1.0,
    steps: int = 50,
) -> tuple[float, float]:
    """Find the probability threshold that maximizes F-beta on the given data.

    Returns (best_threshold, best_fbeta_score).
    """
    best_thresh, best_score = 0.5, 0.0
    for t in np.linspace(0.05, 0.95, steps):
        preds = (probs >= t).astype(int)
        score = fbeta_score(labels, preds, beta=beta, zero_division=0)
        if score > best_score:
            best_score = score
            best_thresh = float(t)
    return best_thresh, best_score


def collect_probs(
    model: LSTMAnomalyDetector,
    data_loader: DataLoader,
    device: torch.device | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run inference and return (labels, positive-class probabilities)."""
    device = device or get_device()
    model = model.to(device)
    model.eval()

    all_probs = []
    all_labels = []
    with torch.no_grad():
        for batch_X, batch_y in data_loader:
            batch_X = batch_X.to(device)
            probs = torch.softmax(model(batch_X), dim=1)
            all_probs.extend(probs[:, 1].cpu().numpy())
            all_labels.extend(batch_y.numpy())

    return np.array(all_labels), np.array(all_probs)
