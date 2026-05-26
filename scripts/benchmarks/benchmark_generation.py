"""Benchmark generation speed with KV cache optimization."""
import logging
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["ATULYA_DATA_DIR"] = str(ROOT / "assets")

logging.basicConfig(level=logging.WARNING)

from tantra.npdna import NpDnaCore  # noqa: E402
from tantra.npdna.config import CONFIGS  # noqa: E402

def warmup(core):
    """Warm up model and any caches."""
    _ = core.generate("Hello", max_tokens=5)

def benchmark(core, prompt="The future of artificial intelligence", max_tokens=50):
    """Time generation and report tok/s."""
    start = time.perf_counter()
    text = core.generate(prompt, max_tokens=max_tokens,
                         temperature=0.0,  # greedy for reproducibility
                         top_k=0)
    elapsed = time.perf_counter() - start
    generated = max_tokens  # should produce exactly this many
    tok_s = generated / elapsed
    print(f"  Generated {generated} tokens in {elapsed:.2f}s = {tok_s:.1f} tok/s")
    print(f"  Output preview: {text[:80]}...")
    return tok_s, elapsed

def benchmark_with_threads(core, prompt, max_tokens, num_threads):
    """Benchmark with specific thread count using the new forward num_threads param."""
    # We need to bypass generate() and use the model directly
    device = core.model.embedding.weight.device
    prompt_ids = core.encode(prompt, allow_growth=False)
    ids = list(prompt_ids)
    
    core.model.eval()
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(max_tokens):
            input_ids = torch.tensor([[ids[-1]]], dtype=torch.long, device=device)
            logits, _ = core.model(input_ids=input_ids, num_threads=num_threads)
            next_logits = logits[0, -1].clone()
            next_id = int(next_logits.argmax().item())
            ids.append(next_id)
    elapsed = time.perf_counter() - start
    tok_s = max_tokens / elapsed
    print(f"  [{num_threads} threads] {max_tokens} tokens in {elapsed:.2f}s = {tok_s:.1f} tok/s")
    return tok_s, elapsed


print("=" * 60)
print("NP-DNA Generation Benchmark — KV Cache (T=1) + parallel layers + int8")
print("=" * 60)

# Test 1: KV cache speed (using generation.py's new T=1 decode)
print("\n[Test 1] KV Cache generation speed")
core = NpDnaCore.from_config("atulya_seed")
warmup(core)
t1, _ = benchmark(core, "The future of AI is", max_tokens=100)
del core

# Test 2: With int8 matmul enabled
print("\n[Test 2] With int8_matmul=True")
config = CONFIGS["atulya_seed"].clone() if hasattr(CONFIGS["atulya_seed"], "clone") else CONFIGS["atulya_seed"]
# Actually need to create with int8 on
cfg = deepcopy(CONFIGS["atulya_seed"])
cfg.mesh.strand.int8_matmul = True
core2 = NpDnaCore.from_config("atulya_seed")
core2.model.config.mesh.strand.int8_matmul = True
# Re-init mesh strands to pick up the config change
for mesh in core2.model.mesh_layers:
    for strand in mesh.strands:
        strand.config = cfg.mesh.strand
warmup(core2)
t2, _ = benchmark(core2, "The future of AI is", max_tokens=100)
del core2

# Test 3: Thread control (num_threads=1 vs num_threads=4)
print("\n[Test 3] Thread scaling [1 vs 4 threads]")
core3 = NpDnaCore.from_config("atulya_seed")
warmup(core3)
t3a, _ = benchmark_with_threads(core3, "Machine learning", 50, num_threads=1)
t3b, _ = benchmark_with_threads(core3, "Machine learning", 50, num_threads=4)
del core3

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  KV Cache (T=1) decode:        {t1:.1f} tok/s")
print(f"  + int8 matmul:                {t2:.1f} tok/s")
print(f"  1 thread:                     {t3a:.1f} tok/s")
print(f"  4 threads:                    {t3b:.1f} tok/s")
print(f"  Speedup (1→4 threads):        {t3b/t3a:.2f}x")
print("\n  Old training throughput for reference: ~203 tok/s at batch size 32")
print("=" * 60)
