"""
LSTM Anomaly Detection Model for AegisHealth.

Architecture (from PDF Section 6.5.2):
  Input -> 2x Stacked LSTM -> Dropout -> FC -> 2-class logits (CrossEntropyLoss)
Designed for temporal vital-signs sequences to predict critical events.
"""

from __future__ import annotations

from collections import OrderedDict

import torch
import torch.nn as nn


class LSTMAnomalyDetector(nn.Module):
    def __init__(
        self,
        input_size: int = 11,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        num_classes: int = 2,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(p=dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)
        last_hidden = lstm_out[:, -1, :]  # (batch, hidden_size)
        out = self.dropout(last_hidden)
        logits = self.fc(out)  # (batch, num_classes)
        return logits

    def get_flat_params(self) -> torch.Tensor:
        return torch.cat([p.data.view(-1) for p in self.parameters()])

    def set_flat_params(self, flat_params: torch.Tensor):
        offset = 0
        for p in self.parameters():
            numel = p.numel()
            p.data.copy_(flat_params[offset : offset + numel].view(p.shape))
            offset += numel

    def get_state_dict_as_numpy(self) -> dict[str, list]:
        import numpy as np
        return {k: v.cpu().numpy().tolist() for k, v in self.state_dict().items()}

    @classmethod
    def from_numpy_state_dict(cls, numpy_state: dict, **kwargs) -> "LSTMAnomalyDetector":
        import numpy as np
        model = cls(**kwargs)
        state_dict = OrderedDict()
        for k, v in numpy_state.items():
            state_dict[k] = torch.tensor(np.array(v))
        model.load_state_dict(state_dict)
        return model


def create_model(
    input_size: int = 11,
    hidden_size: int = 128,
    num_layers: int = 2,
    dropout: float = 0.3,
) -> LSTMAnomalyDetector:
    """Return an Opacus-compatible LSTM (DPLSTM replacement) for DP training.

    All federated global state dicts use this layout; do not pass a raw
    ``LSTMAnomalyDetector`` to ``DPEngine.make_private`` without this step.
    """
    from opacus import PrivacyEngine

    base = LSTMAnomalyDetector(
        input_size=input_size,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
    )
    return PrivacyEngine.get_compatible_module(base)
