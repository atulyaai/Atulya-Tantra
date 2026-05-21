"""Benchmark suite for NP-DNA models.

Measures:
  1. Perplexity on held-out data
  2. DNA compression ratio (actual vs theoretical)
  3. Strand utilization analysis
  4. Token generation speed (tok/sec)
  5. Memory profiling (peak RSS)
  6. Dense model comparison (NP-DNA vs equivalent standard model)

Usage:
  python training/benchmark.py --model outputs/npdna
  python training/benchmark.py --config seed --steps 100
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from pathlib import Path

import psutil
import torch
from torch import nn

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tantra.core.npdna import CONFIGS, NpDnaCore, NpDnaModel
from tantra.training.dataset.build_dataset import load_dataset

logger = logging.getLogger(__name__)


def measure_perplexity(
    core: NpDnaCore,
    test_texts: list[str],
    max_seq: int = 128,
) -> float:
    """Measure perplexity on test data.

    Perplexity = exp(average cross-entropy loss).
    Lower is better. Random baseline â‰ˆ vocab_size.
    """
    model = core.model
    model.eval()
    device = next(model.parameters()).device
    loss_fn = nn.CrossEntropyLoss(reduction="sum")

    total_loss = 0.0
    total_tokens = 0

    with torch.no_grad():
        for text in test_texts:
            # Evaluation must not grow the tokenizer. New vocabulary rows are
            # randomly initialized, so adding them during benchmark makes
            # perplexity meaningless and can explode the score.
            ids = core.encode(text, allow_growth=False)[:max_seq]
            if len(ids) < 2:
                continue

            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            labels = torch.tensor([ids[1:]], dtype=torch.long, device=device)

            logits, _ = model(input_ids)
            loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))

            total_loss += float(loss)
            total_tokens += len(ids) - 1

    if total_tokens == 0:
        return float("inf")

    avg_loss = total_loss / total_tokens
    perplexity = math.exp(min(avg_loss, 100))  # Cap to avoid overflow
    return perplexity


def measure_compression(model: NpDnaModel) -> dict:
    """Measure actual DNA compression ratio."""
    total = model.parameter_count()
    active = model.active_parameter_count()

    # What an equivalent dense model would use
    config = model.config
    dense_params_per_layer = (
        config.hidden_size * config.mesh.strand.state_size * 4  # gate, state, rec, out
        * config.mesh.num_strands  # all strands store their own
    )
    dense_total = (
        config.initial_vocab * config.hidden_size  # embedding
        + dense_params_per_layer * config.num_layers
        + config.hidden_size  # layer norm
    )

    return {
        "npdna_total": total,
        "npdna_active": active,
        "dense_equivalent": dense_total,
        "compression_ratio": dense_total / max(1, total),
        "active_ratio": total / max(1, active),
    }


def measure_strand_utilization(core: NpDnaCore, test_texts: list[str]) -> dict:
    """Measure how evenly Strands are utilized."""
    model = core.model
    model.eval()
    device = next(model.parameters()).device

    # Reset usage stats
    for mesh in model.mesh_layers:
        mesh.reset_usage()

    with torch.no_grad():
        for text in test_texts[:50]:
            ids = core.encode(text, allow_growth=False)[:64]
            if len(ids) < 2:
                continue
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            model(input_ids)

    # Collect stats per layer
    results = {}
    for i, mesh in enumerate(model.mesh_layers):
        stats = dict(mesh.usage_stats)
        total = sum(stats.values())
        if total == 0:
            continue

        usage_pct = {k: v / total * 100 for k, v in stats.items()}
        dead = [k for k, v in usage_pct.items() if v < 1.0]
        overloaded = [k for k, v in usage_pct.items() if v > 100 / len(stats) * 3]

        results[f"layer_{i}"] = {
            "usage_percent": usage_pct,
            "dead_strands": dead,
            "overloaded_strands": overloaded,
            "utilization_score": 1.0 - (len(dead) / max(1, len(stats))),
        }

    return results


def measure_generation_speed(core: NpDnaCore, num_tokens: int = 100) -> dict:
    """Measure token generation speed."""
    core.model.eval()

    # Warmup
    core.generate("test", max_tokens=5)

    # Timed run
    start = time.perf_counter()
    result = core.generate("Hello world", max_tokens=num_tokens)
    elapsed = time.perf_counter() - start

    tokens_generated = len(core.encode(result, allow_growth=False))
    tok_per_sec = tokens_generated / max(0.001, elapsed)

    return {
        "tokens_generated": tokens_generated,
        "time_seconds": round(elapsed, 3),
        "tokens_per_second": round(tok_per_sec, 1),
    }


def measure_memory(core: NpDnaCore) -> dict:
    """Measure memory usage."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    # Model parameter memory
    param_bytes = sum(p.numel() * p.element_size() for p in core.model.parameters())

    return {
        "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "param_memory_mb": round(param_bytes / 1024 / 1024, 1),
        "total_params": core.model.parameter_count(),
    }


def run_full_benchmark(
    model_path: str | None = None,
    config_name: str = "seed",
    data_path: str | None = None,
    max_samples: int = 256,
) -> dict:
    """Run the complete benchmark suite.

    Args:
        model_path: Path to saved model. If None, creates from config.
        config_name: Config name (used if model_path is None).

    Returns:
        Dict with all benchmark results.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Load or create model
    if model_path and Path(model_path).exists():
        logger.info("Loading model from %s", model_path)
        core = NpDnaCore.load(model_path)
    else:
        logger.info("Creating model from config: %s", config_name)
        core = NpDnaCore.from_config(config_name)

    # Prepare test data. Prefer a held-out slice from the training dataset when
    # available so the loss/perplexity relationship is interpretable.
    if data_path and Path(data_path).exists():
        loaded = load_dataset(data_path, limit=max(1, max_samples * 2))
        test_texts = loaded[-max_samples:] if len(loaded) > max_samples else loaded
        benchmark_data = str(Path(data_path).resolve())
    else:
        test_texts = [
            "The quick brown fox jumps over the lazy dog.",
            "Machine learning is a subset of artificial intelligence.",
            "Python is a versatile programming language used for web development.",
            "The Earth orbits the Sun at an average distance of 93 million miles.",
            "Gravity is the force that attracts objects toward each other.",
            "Water freezes at 0 degrees Celsius and boils at 100 degrees.",
            "The Pythagorean theorem states that a squared plus b squared equals c squared.",
            "Photosynthesis converts sunlight into chemical energy in plants.",
            "DNA carries genetic information in all living organisms.",
            "The speed of light is approximately 300,000 kilometers per second.",
        ]
        benchmark_data = "built_in_smoke_set"

    model_meta = {}
    if model_path and (Path(model_path) / "metadata.json").exists():
        model_meta = json.loads((Path(model_path) / "metadata.json").read_text(encoding="utf-8"))

    effective_config_name = model_meta.get("train_config_name") or model_meta.get("config_name") or config_name

    results = {
        "benchmark_meta": {
            "model_path": str(Path(model_path).resolve()) if model_path else None,
            "model_mtime": (Path(model_path) / "model.pt").stat().st_mtime
            if model_path and (Path(model_path) / "model.pt").exists()
            else None,
            "metadata_mtime": (Path(model_path) / "metadata.json").stat().st_mtime
            if model_path and (Path(model_path) / "metadata.json").exists()
            else None,
            "config_name": effective_config_name,
            "train_step": model_meta.get("train_step") or model_meta.get("loss_count"),
            "train_final_loss": model_meta.get("train_final_loss") or model_meta.get("final_loss"),
            "train_best_loss": model_meta.get("train_best_loss") or model_meta.get("best_loss"),
            "vocab_size": core.tokenizer.size,
            "vocab_capacity": core.tokenizer.capacity,
            "eval_data": benchmark_data,
            "eval_samples": len(test_texts),
            "tokenizer_growth_allowed": False,
        }
    }

    # 1. Perplexity
    logger.info("Measuring perplexity...")
    ppl = measure_perplexity(core, test_texts)
    results["perplexity"] = round(ppl, 2)
    logger.info("  Perplexity: %.2f (random baseline: %d)", ppl, core.model.vocab_size)

    # 2. Compression
    logger.info("Measuring compression...")
    comp = measure_compression(core.model)
    results["compression"] = comp
    logger.info("  NP-DNA: %s params, Dense equivalent: %s params",
                f"{comp['npdna_total']:,}", f"{comp['dense_equivalent']:,}")
    logger.info("  Compression ratio: %.1fx", comp["compression_ratio"])

    # 3. Strand utilization
    logger.info("Measuring strand utilization...")
    strands = measure_strand_utilization(core, test_texts)
    results["strand_utilization"] = strands
    for layer_name, layer_data in strands.items():
        score = layer_data["utilization_score"]
        dead = layer_data["dead_strands"]
        logger.info("  %s: utilization=%.0f%%, dead=%s", layer_name, score * 100, dead or "none")

    # 4. Generation speed
    logger.info("Measuring generation speed...")
    speed = measure_generation_speed(core, num_tokens=50)
    results["generation_speed"] = speed
    logger.info("  Speed: %.1f tok/sec", speed["tokens_per_second"])

    # 5. Memory
    logger.info("Measuring memory...")
    mem = measure_memory(core)
    results["memory"] = mem
    logger.info("  RSS: %.1fMB, Params: %.1fMB", mem["rss_mb"], mem["param_memory_mb"])

    # Summary
    print("\n" + "=" * 60)
    print("  NP-DNA BENCHMARK RESULTS")
    print("=" * 60)
    print(f"  Config:            {effective_config_name}")
    print(f"  Total params:      {comp['npdna_total']:,}")
    print(f"  Active params:     {comp['npdna_active']:,}")
    print(f"  Dense equivalent:  {comp['dense_equivalent']:,}")
    print(f"  Compression:       {comp['compression_ratio']:.1f}x")
    print(f"  Perplexity:        {ppl:.2f}")
    print(f"  Gen speed:         {speed['tokens_per_second']:.1f} tok/sec")
    print(f"  Memory (RSS):      {mem['rss_mb']:.1f} MB")
    print(f"  Memory (params):   {mem['param_memory_mb']:.1f} MB")

    for layer_name, layer_data in strands.items():
        dead_count = len(layer_data["dead_strands"])
        total_strands = len(layer_data["usage_percent"])
        print(f"  {layer_name}:         {total_strands - dead_count}/{total_strands} active strands")

    print("=" * 60)

    # Save results
    results_path = Path(model_path or "outputs/npdna") / "benchmark.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Results saved to %s", results_path)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NP-DNA Benchmarks")
    parser.add_argument("--model", default="outputs/npdna", help="Model path")
    parser.add_argument("--config", default="seed", help="Config name")
    parser.add_argument("--data", default=None, help="Optional JSONL dataset for held-out evaluation")
    parser.add_argument("--max-samples", type=int, default=256, help="Max held-out texts to evaluate")

    args = parser.parse_args()
    model_path = args.model if Path(args.model).exists() else None
    run_full_benchmark(model_path, args.config, data_path=args.data, max_samples=args.max_samples)
