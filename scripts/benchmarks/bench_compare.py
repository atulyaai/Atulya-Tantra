"""Before vs After comparison for NP-DNA strand optimizations.
Measures the T-loop elimination showing exact speedup.

Changes in this round:
  1. strand.py forward: T==1 fast path avoids Python for-loop, torch.stack, etc.
  2. mesh.py: weight cache during inference avoids regenerate_all per forward

This script benchmarks both the OLD path and the NEW path for strand forward,
then shows the full model inference speedup.
"""
import sys
import time
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tantra.npdna import NpDnaCore  # noqa: E402
from tantra.npdna.config import StrandConfig  # noqa: E402
from tantra.npdna.genome import Genome  # noqa: E402

torch.set_num_threads(4)
torch.set_num_interop_threads(1)

DEVICE = torch.device("cpu")
DTYPE = torch.float32
WARMUP = 10
ITERS = 100

def fmt(seconds: float) -> str:
    if seconds < 1e-3:
        return f"{seconds*1e6:.1f}µs"
    if seconds < 1:
        return f"{seconds*1e3:.2f}ms"
    return f"{seconds:.3f}s"


# ── OLD Strand forward (reference: T-loop always runs) ──────────
class OldStrand(nn.Module):
    """Same as original strand.py forward — T-loop runs for every input."""
    def __init__(self, genome, strand_id, config):
        super().__init__()
        self.genome = genome
        self.strand_id = strand_id
        self.config = config
        self.norm = nn.LayerNorm(config.hidden_size)
        self.usage_count = 0

    def forward(self, x, weights=None):
        B, T, H = x.shape
        S = self.config.state_size
        device = x.device
        x = self.norm(x)
        if weights is None:
            weights = self.genome.generate_all(self.strand_id)
        W_gate, b_gate = weights["gate"]
        W_state, b_state = weights["state"]
        W_rec, b_rec = weights["recurrent"]
        W_out, b_out = weights["output"]

        state = torch.zeros(B, S, device=device, dtype=x.dtype)
        outputs = []
        for t in range(T):
            x_t = x[:, t, :]
            gate = torch.sigmoid(x_t @ W_gate + state @ W_rec + b_gate + b_rec)
            candidate = torch.tanh(x_t @ W_state + b_state)
            state = gate * state + (1.0 - gate) * candidate
            y_t = state @ W_out + b_out
            outputs.append(y_t)
        self.usage_count += B * T
        return torch.stack(outputs, dim=1)


# ── NEW Strand forward (from current strand.py — T==1 fast path) ──
from tantra.npdna.strand import Strand as NewStrand  # noqa: E402


def main():
    print("=" * 70)
    print("  NP-DNA Optimization: Before vs After")
    print("  CPU: 4 threads,  FP32")
    print("=" * 70)

    # Use the seed config genome/strand config
    from tantra.npdna.config import CONFIGS
    cfg = CONFIGS["seed"]
    H, S = cfg.hidden_size, cfg.state_size
    sc = StrandConfig(hidden_size=H, state_size=S)
    genome = Genome(cfg.genome, sc)

    # Create two strands with same seed
    old_s = OldStrand(genome, 0, sc)
    new_s = NewStrand(genome, 0, sc)
    old_s.eval()
    new_s.eval()

    print(f"\n  Hidden={H}, State={S}, Genome latent={cfg.genome.latent_dim}")
    print(f"  {'Batch':>6s}  {'Old (T-loop)':>15s}  {'New (T=1 path)':>15s}  {'Speedup':>8s}")
    print("  " + "-" * 50)

    for B in [1, 2, 4, 8, 16, 32, 64]:
        x = torch.randn(B, 1, H, device=DEVICE, dtype=DTYPE)
        weights = genome.generate_all(0)

        # OLD
        for _ in range(WARMUP):
            old_s(x, weights=weights)
        start = time.perf_counter()
        for _ in range(ITERS):
            old_s(x, weights=weights)
        t_old = (time.perf_counter() - start) / ITERS

        # NEW
        for _ in range(WARMUP):
            new_s(x, weights=weights)
        start = time.perf_counter()
        for _ in range(ITERS):
            new_s(x, weights=weights)
        t_new = (time.perf_counter() - start) / ITERS

        speedup = t_old / t_new
        print(f"  {B:>6d}  {fmt(t_old):>15s}  {fmt(t_new):>15s}  {speedup:>7.2f}×")

    # ── Full model: Inference with weight cache vs without ──
    print("\n── Full model (seed, B=1 T=128) ──")
    core = NpDnaCore.from_config("seed")
    core.model = core.model.to(DEVICE)
    core.model.eval()

    ids = torch.randint(0, core.tokenizer.size, (1, 128), device=DEVICE)

    # Evict weight cache to simulate "cold" first run
    for mesh in core.model.mesh_layers:
        mesh._weight_cache.clear()

    # First pass = cold cache (populates cache + runs old generate_all)
    for _ in range(WARMUP):
        logits, loss = core.model(ids)

    # Timed: hot cache (weight cache is fully populated)
    start = time.perf_counter()
    for _ in range(ITERS):
        logits, loss = core.model(ids)
    t_hot = (time.perf_counter() - start) / ITERS

    # Timed: training mode (no cache — regenerates weights every forward)
    core.model.train()
    for _ in range(WARMUP):
        logits, loss = core.model(ids)
    start = time.perf_counter()
    for _ in range(ITERS):
        logits, loss = core.model(ids)
    t_cold = (time.perf_counter() - start) / ITERS

    print(f"  Inference (hot weight cache):       {fmt(t_hot):>10s}")
    print(f"  Training (no cache, gen each call):  {fmt(t_cold):>10s}")
    print(f"  Speedup (cache vs regenerate):       {t_cold/t_hot:.2f}×")

    # ── Last: verify correctness ──
    print("\n── Correctness check (B=4 T=1) ──")
    x = torch.randn(4, 1, H, device=DEVICE, dtype=DTYPE)
    weights = genome.generate_all(0)
    out_old = old_s(x, weights=weights)
    out_new = new_s(x, weights=weights)
    diff = (out_old - out_new).abs().max().item()
    print(f"  Max diff (old vs new strand output): {diff:.2e}  {'✓ PASS' if diff < 1e-5 else '✗ FAIL'}")

    print("=" * 70)


if __name__ == "__main__":
    main()
