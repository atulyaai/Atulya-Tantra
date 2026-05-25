"""Strand â€” causal gated state-space processing unit.

Each Strand is a lightweight recurrent processor whose weights are generated
by the Genome (DNA).  It processes sequences causally (left-to-right) using
gated state recurrence â€” O(T) linear time, no attention matrices, CPU-fast.

The state update at each position t:
    gate_t = Ïƒ(x_t @ W_gate + s_{t-1} @ W_recurrent + b_gate + b_rec)
    s_t    = gate_t * s_{t-1} + (1 - gate_t) * tanh(x_t @ W_state + b_state)
    y_t    = s_t @ W_output + b_output

This is causal by construction: each step only uses s_{t-1} (the past).
"""

from __future__ import annotations

import torch
from torch import Tensor, nn

from .config import StrandConfig
from .genome import Genome

# ---------------------------------------------------------------------------
# Int8 quantization helpers — memory-bandwidth optimization for inference
# ---------------------------------------------------------------------------
# These convert fp32/16 weights to per-tensor symmetric int8, then immediately
# dequantize back before the matmul.  The point is to halve memory bandwidth
# (fp32→int8) during the weight-read phase.  On CPUs without VNNI/AVX-512
# this will NOT accelerate compute — the speedup comes from reduced DRAM
# traffic.  On CUDA devices with tensor-core int8 support this can also
# accelerate the matmul itself.
# ---------------------------------------------------------------------------


def _quantize_int8(tensor: Tensor) -> tuple[Tensor, Tensor, float]:
    """Per-tensor symmetric int8 quantization.

    Scale = absmax / 127, zero_point = 0 (symmetric).
    Returns (qweight_int8, scale_as_tensor, zero_point_as_float).

    Args:
        tensor: Input weight tensor of any shape.

    Returns:
        qweight_int8: Quantized int8 tensor (same shape).
        scale: Float scale tensor (scalar).
        zero_point: Always 0.0 (symmetric quantization property).
    """
    absmax = tensor.abs().max()
    scale = absmax / 127.0
    # Avoid division by zero for zero-filled tensors
    scale = torch.where(scale < 1e-12, torch.ones_like(scale), scale)
    qweight = torch.round(tensor / scale).to(torch.int8)
    return qweight, scale.detach(), 0.0


def _int8_linear(x: Tensor, qweight: Tensor, scale: float, bias: Tensor | None) -> Tensor:
    """Dequantized matmul: dequantizes int8 weight on the fly, then does matmul.

    Args:
        x: Input tensor (..., in_features).
        qweight: Int8 quantized weight tensor (in_features, out_features).
        scale: Dequantization scale (scalar).
        bias: Optional bias tensor (out_features,).

    Returns:
        Result = x @ dequant(weight) + bias.
    """
    # Dequantize: w_fp = qweight * scale
    w_deq = qweight.to(x.dtype) * scale
    out = x @ w_deq
    if bias is not None:
        out = out + bias
    return out


class Strand(nn.Module):
    """Causal gated state-space processing unit with DNA-generated weights.

    Does NOT store its own weights â€” they come from the Genome.  This means
    adding a new Strand costs only 256 params (one new seed in the Genome),
    not a full set of weight matrices.

    Args:
        genome: Shared DNA weight generator.
        strand_id: This Strand's index in the Genome seed bank.
        config: Hidden/state size configuration.
    """

    def __init__(self, genome: Genome, strand_id: int, config: StrandConfig):
        super().__init__()
        self.genome = genome
        self.strand_id = strand_id
        self.config = config
        self.norm = nn.LayerNorm(config.hidden_size)

        # Usage tracking for Plasticity Engine
        self.usage_count: int = 0

    def forward(self, x: Tensor, weights: dict[str, tuple[Tensor, Tensor]] | None = None) -> Tensor:
        """Process sequence causally.

        Args:
            x: Input tensor (batch, seq_len, hidden_size).

        Returns:
            Output tensor (batch, seq_len, hidden_size).
        """
        B, T, H = x.shape
        S = self.config.state_size
        device = x.device

        x = self.norm(x)

        # Generate weights from DNA once per mesh forward when caller provides a cache.
        if weights is None:
            weights = self.genome.generate_all(self.strand_id)
        W_gate, b_gate = weights["gate"]          # (H, S), (S,)
        W_state, b_state = weights["state"]       # (H, S), (S,)
        W_rec, b_rec = weights["recurrent"]       # (S, S), (S,)
        W_out, b_out = weights["output"]           # (S, H), (H,)

        # ------------------------------------------------------------------
        # Int8 quantized matmul path (memory-bandwidth optimization)
        # ------------------------------------------------------------------
        # Quantizes each weight matrix to per-tensor symmetric int8, then
        # dequantizes on-the-fly before every matmul.  This halves memory
        # bandwidth (fp32→int8) during weight reads.  On CPUs without
        # VNNI/AVX-512 this will NOT accelerate compute — the speedup
        # comes from reduced DRAM traffic.  On CUDA with tensor-core
        # int8 support the matmul itself also benefits.
        # ------------------------------------------------------------------
        use_int8 = self.config.int8_matmul and H >= 64 and S >= 16
        if use_int8:
            qW_gate, sW_gate, _ = _quantize_int8(W_gate)
            qW_state, sW_state, _ = _quantize_int8(W_state)
            qW_rec, sW_rec, _ = _quantize_int8(W_rec)
            qW_out, sW_out, _ = _quantize_int8(W_out)

            def matmul_gate(x):     return _int8_linear(x, qW_gate, sW_gate, b_gate + b_rec)
            def matmul_state(x):   return _int8_linear(x, qW_state, sW_state, b_state)
            def matmul_rec(s):     return _int8_linear(s, qW_rec, sW_rec, None)  # bias already in matmul_gate
            def matmul_out(s):     return _int8_linear(s, qW_out, sW_out, b_out)
        else:
            def matmul_gate(x):     return x @ W_gate + b_gate + b_rec
            def matmul_state(x):   return x @ W_state + b_state
            def matmul_rec(s):     return s @ W_rec
            def matmul_out(s):     return s @ W_out + b_out

        if T == 1:
            # Fast path: state starts at 0, recurrence is dead code.
            #   gate = sigmoid(x @ W_gate      + b_gate + b_rec)
            #   candidate = tanh(x @ W_state + b_state)
            #   state = (1 - gate) * candidate     (gate * 0 = 0)
            #   y = state @ W_out + b_out
            x_t = x.squeeze(1)  # (B, H)
            gate = torch.sigmoid(matmul_gate(x_t))
            candidate = torch.tanh(matmul_state(x_t))
            state = (1.0 - gate) * candidate
            y = matmul_out(state)
            self.usage_count += B
            return y.unsqueeze(1)  # (B, 1, H)

        # Causal state-space recurrence (T > 1 — e.g. sequential calls)
        state = torch.zeros(B, S, device=device, dtype=x.dtype)
        outputs: list[Tensor] = []

        for t in range(T):
            x_t = x[:, t, :]  # (B, H)

            # Gate: how much to remember vs reset
            gate = torch.sigmoid(matmul_gate(x_t) + matmul_rec(state))

            # State update: blend old state with new input
            candidate = torch.tanh(matmul_state(x_t))
            state = gate * state + (1.0 - gate) * candidate

            # Output: project state back to hidden dim
            y_t = matmul_out(state)
            outputs.append(y_t)

        self.usage_count += B * T
        return torch.stack(outputs, dim=1)  # (B, T, H)

