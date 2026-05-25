"""Benchmark NP-DNA optimizations: T=1 fast path + weight cache.

Measures:
  1. Strand forward (T=1 scattered tokens) — before vs after
  2. Mesh forward (full model layer) — inference mode (weight cache active)
  3. Full model forward — inference mode

Runs on seed config (smallest) for fast cycles.
"""
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tantra.npdna import NpDnaCore
from tantra.npdna.strand import Strand
from tantra.npdna.mesh import NeuralMesh

torch.set_num_threads(4)
torch.set_num_interop_threads(1)

DEVICE = torch.device("cpu")
DTYPE = torch.float32

WARMUP = 5
ITERS = 50


def fmt(seconds: float) -> str:
    if seconds < 1e-3:
        return f"{seconds*1e6:.1f}µs"
    if seconds < 1:
        return f"{seconds*1e3:.2f}ms"
    return f"{seconds:.3f}s"


def bench_strand(strand: Strand, B: int, T: int, H: int, label: str) -> float:
    x = torch.randn(B, T, H, device=DEVICE, dtype=DTYPE)
    weights = strand.genome.generate_all(strand.strand_id)

    # Warmup
    for _ in range(WARMUP):
        strand(x, weights=weights)

    torch._C._jit_clear_class_registry()
    torch.compiler.cudagraph_mark_step_begin()

    start = time.perf_counter()
    for _ in range(ITERS):
        strand(x, weights=weights)
    elapsed = time.perf_counter() - start
    avg = elapsed / ITERS
    print(f"  {label:40s} {fmt(avg):>10s}  ({ITERS}×, avg)")
    return avg


def bench_mesh(mesh: NeuralMesh, B: int, T: int, H: int, label: str, train: bool = False) -> float:
    x = torch.randn(B, T, H, device=DEVICE, dtype=DTYPE)
    mesh.train(train)

    # Warmup — first call populates weight cache in inference mode
    for _ in range(WARMUP):
        out, bal = mesh(x)

    torch._C._jit_clear_class_registry()
    torch.compiler.cudagraph_mark_step_begin()

    start = time.perf_counter()
    for _ in range(ITERS):
        out, bal = mesh(x)
    elapsed = time.perf_counter() - start
    avg = elapsed / ITERS
    print(f"  {label:40s} {fmt(avg):>10s}  ({ITERS}×, avg)")
    return avg


def bench_model(core: NpDnaCore, B: int, T: int, label: str, train: bool = False) -> float:
    ids = torch.randint(0, core.tokenizer.size, (B, T), device=DEVICE)
    core.model.train(train)

    for _ in range(WARMUP):
        logits, loss = core.model(ids)

    torch._C._jit_clear_class_registry()
    torch.compiler.cudagraph_mark_step_begin()

    start = time.perf_counter()
    for _ in range(ITERS):
        logits, loss = core.model(ids)
    elapsed = time.perf_counter() - start
    avg = elapsed / ITERS
    print(f"  {label:40s} {fmt(avg):>10s}  ({ITERS}×, avg)")
    return avg


def main():
    print("=" * 65)
    print("  NP-DNA Optimization Benchmark")
    print(f"  CPU: {torch.get_num_threads()} threads,  dtype: {DTYPE}")
    print("=" * 65)

    # --- Create model ---
    print("\nCreating model (seed config)...\n")
    core = NpDnaCore.from_config("seed")
    core.model = core.model.to(DEVICE)
    core.model.eval()

    cfg = core.config
    H = cfg.hidden_size
    print(f"  Config: hidden={H}, state={cfg.state_size}, layers={cfg.num_layers}")
    print(f"  Vocab: {core.tokenizer.size}")
    print(f"  Params: {core.model.parameter_count():,} total")

    # --- 1. Strand-level benchmark ---
    print("\n── Strand forward (T=1 scattered tokens) ──")
    strand = core.model.mesh_layers[0].strands[0]
    results = {}

    # Small batch (typical per-strand token count from mesh)
    for B in [1, 4, 16]:
        t = bench_strand(strand, B, 1, H, f"B={B}, T=1")
        results[f"strand_B{B}"] = t

    # Larger batch to see if T=1 path beats loop
    t = bench_strand(strand, 64, 1, H, "B=64, T=1 (mesh parallel)")
    results["strand_B64"] = t

    # --- 2. Mesh-level benchmark ---
    print("\n── Mesh forward (inference, weight cache active) ──")
    mesh = core.model.mesh_layers[0]
    for B in [1, 4, 16]:
        t = bench_mesh(mesh, B, 64, H, f"B={B}, T=64")
        results[f"mesh_B{B}_inf"] = t

    # Mesh in training mode (no weight cache, fresh generate_all each call)
    print("\n── Mesh forward (training — no cache) ──")
    for B in [1, 4]:
        t = bench_mesh(mesh, B, 64, H, f"B={B}, T=64 (train)", train=True)
        results[f"mesh_B{B}_train"] = t

    # --- 3. Full model benchmark ---
    print("\n── Full model forward ──")
    for B in [1]:
        t = bench_model(core, B, 128, "B=1, T=128 (inference)")
        results[f"model_B1_inf"] = t

    t = bench_model(core, 1, 128, "B=1, T=128 (train)", train=True)
    results["model_B1_train"] = t

    print("\n" + "=" * 65)
    print("  Done. Results saved in results dict.")
    print("=" * 65)


if __name__ == "__main__":
    main()
