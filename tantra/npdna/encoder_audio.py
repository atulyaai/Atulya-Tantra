"""Audio encoder for NP-DNA voice feature inputs."""
from __future__ import annotations

import torch


class AudioFeatureEncoder(torch.nn.Module):
    """Small mel-like feature projector into NP-DNA hidden space.

    This intentionally accepts precomputed audio feature tensors so the core
    model does not depend hard on torchaudio. Callers can pass shape
    ``(batch, time, n_features)`` and receive ``(batch, time, hidden_size)``.
    """

    def __init__(self, input_features: int = 80, hidden_size: int = 256):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_features, hidden_size),
            torch.nn.GELU(),
            torch.nn.Linear(hidden_size, hidden_size),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.dim() != 3:
            raise ValueError("features must have shape (batch, time, n_features)")
        return self.net(features.float())
