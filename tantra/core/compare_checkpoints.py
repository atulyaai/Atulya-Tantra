"""Compare two NP-DNA checkpoints side-by-side on a common test set.

Usage:
    python -u compare_checkpoints.py

Output: Markdown comparison table.
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tantra.npdna import NpDnaCore

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ── Configuration ──────────────────────────────────────────────────────────────
CHECKPOINT_A = ROOT / "outputs/npdna/checkpoints/step_017728"
CHECKPOINT_B = ROOT / "outputs/npdna/checkpoints/step_018228"
TEST_DATA = ROOT / "data/all_datasets.jsonl"
NUM_EVAL_SAMPLES = 16           # texts from the test set (small for CPU speed)
GENERATE_TOKENS = 10            # tokens to generate for speed test
MAX_SEQ = 64                    # max sequence length for perplexity
DEVICE = "cpu"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _fallback_test_texts() -> list[str]:
    """Smoke-test fallback texts used when the dataset file is unavailable or empty."""
    return [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a versatile programming language.",
        "The Earth orbits the Sun at an average distance of 93 million miles.",
    ]


def load_test_texts(path: Path, n: int) -> list[str]:
    """Load up to `n` test samples from a JSONL dataset."""
    if not path.exists():
        return _fallback_test_texts()
    texts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    obj = json.loads(line)
                    text = obj.get("output") or obj.get("text") or obj.get("content") or ""
                    if len(text) > 10:
                        texts.append(text)
                        if len(texts) >= n:
                            break
                except json.JSONDecodeError:
                    pass
    if not texts:
        return _fallback_test_texts()
    return texts


def benchmark_core(core: NpDnaCore, test_texts: list[str], label: str) -> dict:
    """Run a mini benchmark on a loaded core, return metrics dict."""
    model = core.model
    model.eval()
    device = next(model.parameters()).device
    loss_fn = nn.CrossEntropyLoss(reduction="sum")

    # ── 1. Perplexity ──────────────────────────────────────────────────────
    print(f"  [{label}] Computing perplexity on {len(test_texts)} texts...", flush=True)
    total_loss = 0.0
    total_tokens = 0
    with torch.no_grad():
        for text in test_texts:
            ids = core.encode(text, allow_growth=False)[:MAX_SEQ]
            if len(ids) < 2:
                continue
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            labels = torch.tensor([ids[1:]], dtype=torch.long, device=device)
            logits, _ = model(input_ids)
            loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
            total_loss += float(loss)
            total_tokens += len(ids) - 1
    avg_loss = total_loss / max(1, total_tokens)
    perplexity = math.exp(min(avg_loss, 100))

    # ── 2. Compression ──────────────────────────────────────────────────────
    print(f"  [{label}] Computing compression...", flush=True)
    total_params = model.parameter_count()
    active_params = model.active_parameter_count()
    config = model.config
    dense_params_per_layer = (
        config.hidden_size * config.mesh.strand.state_size * 4
        * config.mesh.num_strands
    )
    dense_total = (
        config.initial_vocab * config.hidden_size
        + dense_params_per_layer * config.num_layers
        + config.hidden_size
    )
    compression_ratio = dense_total / max(1, total_params)

    # ── 3. Strand utilization ───────────────────────────────────────────────
    print(f"  [{label}] Measuring strand utilization...", flush=True)
    for mesh in model.mesh_layers:
        mesh.reset_usage()
    with torch.no_grad():
        for text in test_texts[:20]:
            ids = core.encode(text, allow_growth=False)[:32]
            if len(ids) < 2:
                continue
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            model(input_ids)

    util_scores = []
    dead_counts = []
    for mesh in model.mesh_layers:
        stats = dict(mesh.usage_stats) if hasattr(mesh, 'usage_stats') else {}
        total_uses = sum(stats.values())
        if total_uses == 0:
            util_scores.append(0.0)
            dead_counts.append(0)
            continue
        usage_pct = {k: v / total_uses * 100 for k, v in stats.items()}
        dead = sum(1 for v in usage_pct.values() if v < 1.0)
        dead_counts.append(dead)
        score = 1.0 - (dead / max(1, len(stats)))
        util_scores.append(score)
    avg_util = sum(util_scores) / max(1, len(util_scores)) * 100

    # ── 4. Generation speed ─────────────────────────────────────────────────
    print(f"  [{label}] Measuring generation speed ({GENERATE_TOKENS} tokens)...", flush=True)
    core.generate("test", max_tokens=3)  # warmup
    start = time.perf_counter()
    result = core.generate("Hello world", max_tokens=GENERATE_TOKENS)
    elapsed = time.perf_counter() - start
    tokens_generated = len(core.encode(result, allow_growth=False))

    # ── 5. Memory ───────────────────────────────────────────────────────────
    print(f"  [{label}] Measuring memory...", flush=True)
    import psutil
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    param_bytes = sum(p.numel() * p.element_size() for p in model.parameters())

    # ── 6. Average loss from metadata ───────────────────────────────────────
    meta_path = Path(core.active_path) / "metadata.json" if core.active_path else None
    meta_loss = None
    if meta_path and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        losses = meta.get("losses", [])
        if losses:
            meta_loss = {
                "recent_avg": round(sum(losses[-50:]) / max(1, len(losses[-50:])), 4),
                "best": round(min(losses), 4),
                "final": round(losses[-1], 4),
                "total_steps": len(losses),
            }

    return {
        "label": label,
        "perplexity": round(perplexity, 2),
        "avg_loss": round(avg_loss, 4),
        "total_params": total_params,
        "active_params": active_params,
        "dense_equivalent": dense_total,
        "compression_ratio": round(compression_ratio, 2),
        "strand_util_pct": round(avg_util, 1),
        "dead_strands_total": sum(dead_counts),
        "gen_tokens": tokens_generated,
        "gen_time_sec": round(elapsed, 3),
        "gen_speed_tokps": round(tokens_generated / max(0.001, elapsed), 1),
        "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "param_mem_mb": round(param_bytes / 1024 / 1024, 1),
        "train_loss": meta_loss,
    }


def comparison_table(a: dict, b: dict) -> str:
    """Build a markdown comparison table."""
    lines = []
    lines.append("| Metric | Checkpoint A (step_017728) | Checkpoint B (step_018228) | Winner |")
    lines.append("| ------ | ------------------------- | ------------------------- | ------ |")

    def pick(a_val, b_val, lower_better=False):
        if a_val == b_val:
            return "tie"
        if lower_better:
            return "A" if a_val < b_val else "B"
        else:
            return "A" if a_val > b_val else "B"

    def fmt(v):
        if isinstance(v, float):
            return f"{v:.4f}" if v < 1000 else f"{v:,.1f}"
        return str(v)

    metrics = [
        ("Perplexity (↓ better)", a["perplexity"], b["perplexity"], True),
        ("Avg CE Loss (↓ better)", a["avg_loss"], b["avg_loss"], True),
        ("Total Parameters", a["total_params"], b["total_params"], False),
        ("Active Parameters", a["active_params"], b["active_params"], False),
        ("Compression Ratio (↑ better)", a["compression_ratio"], b["compression_ratio"], False),
        ("Strand Utilization % (↑ better)", a["strand_util_pct"], b["strand_util_pct"], False),
        ("Dead Strands (↓ better)", a["dead_strands_total"], b["dead_strands_total"], True),
        ("Gen Speed (tok/s, ↑ better)", a["gen_speed_tokps"], b["gen_speed_tokps"], False),
        ("Gen Tokens", a["gen_tokens"], b["gen_tokens"], False),
        ("Gen Time (sec)", a["gen_time_sec"], b["gen_time_sec"], True),
        ("RSS Memory (MB)", a["rss_mb"], b["rss_mb"], True),
        ("Param Memory (MB)", a["param_mem_mb"], b["param_mem_mb"], True),
    ]

    for name, a_val, b_val, lower_better in metrics:
        winner = pick(a_val, b_val, lower_better)
        lines.append(f"| {name} | {fmt(a_val)} | {fmt(b_val)} | {winner} |")

    # Training loss info from metadata
    if a.get("train_loss") and b.get("train_loss"):
        al = a["train_loss"]
        bl = b["train_loss"]
        lines.append(f"| Train Steps | {al['total_steps']} | {bl['total_steps']} | - |")
        lines.append(f"| Train Loss (best) | {al['best']} | {bl['best']} | {pick(al['best'], bl['best'], True)} |")
        lines.append(f"| Train Loss (final) | {al['final']} | {bl['final']} | {pick(al['final'], bl['final'], True)} |")
        lines.append(f"| Train Loss (recent avg 50) | {al['recent_avg']} | {bl['recent_avg']} | {pick(al['recent_avg'], bl['recent_avg'], True)} |")

    lines.append("")
    lines.append("**Legend:** A = step_017728, B = step_018228, ↑/↓ indicate better direction.")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("  NP-DNA CHECKPOINT COMPARISON", flush=True)
    print("=" * 70, flush=True)

    for cp in [CHECKPOINT_A, CHECKPOINT_B]:
        if not cp.exists():
            print(f"Checkpoint not found: {cp}")
            sys.exit(1)

    print(f"\nTest data: {TEST_DATA}", flush=True)
    print(f"Loading up to {NUM_EVAL_SAMPLES} samples...", flush=True)
    test_texts = load_test_texts(TEST_DATA, NUM_EVAL_SAMPLES)
    print(f"  Loaded {len(test_texts)} test samples", flush=True)

    results = []
    for cp, label in [(CHECKPOINT_A, "step_017728"), (CHECKPOINT_B, "step_018228")]:
        print(f"\n[{label}] Loading checkpoint...", flush=True)
        core = None
        try:
            core = NpDnaCore.load(str(cp))
            core.model.to(DEVICE)
            print(f"  Model: {core.model.parameter_count():,} params, device={DEVICE}", flush=True)
            res = benchmark_core(core, test_texts, label)
            results.append(res)
            print(f"  [{label}] Done. Perplexity={res['perplexity']}, Speed={res['gen_speed_tokps']} tok/s", flush=True)
        except Exception as e:
            print(f"  [{label}] ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            if core is not None:
                del core
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    print("\n" + "=" * 70, flush=True)
    print(comparison_table(*results), flush=True)
    print("=" * 70, flush=True)
