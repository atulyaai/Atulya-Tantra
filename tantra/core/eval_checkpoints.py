"""Evaluate latest NP-DNA checkpoint, compare with previous, report results.

Usage: python eval_checkpoints.py
"""
from __future__ import annotations

import json
import logging
import math
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

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CHECKPOINT_DIR = ROOT / "tantra/outputs/npdna/checkpoints"
TEST_DATA = ROOT / "data/all_datasets.jsonl"
NUM_EVAL_SAMPLES = 64  # texts from the test set
GENERATE_TOKENS = 20   # tokens to generate for speed test
MAX_SEQ = 128          # max sequence length for perplexity
DEVICE = "cpu"
EXPERIMENT_LOG = ROOT / "experiment_log.csv"
IMPROVEMENT_FILE = ROOT / "improvement.json"


def load_test_texts(path: Path, n: int) -> list[str]:
    """Load up to `n` test samples from a JSONL dataset."""
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
        texts = [
            "The quick brown fox jumps over the lazy dog.",
            "Machine learning is a subset of artificial intelligence.",
            "Python is a versatile programming language.",
            "The Earth orbits the Sun at an average distance of 93 million miles.",
        ]
    return texts


def get_latest_checkpoint(checkpoint_dir: Path) -> tuple[Path | None, Path | None]:
    """Find the newest and second-newest checkpoint by step number."""
    if not checkpoint_dir.exists():
        return None, None
    ckpts = sorted(
        [d for d in checkpoint_dir.iterdir() if d.is_dir() and d.name.startswith("step_")],
        key=lambda d: int(d.name.split("_")[1]),
    )
    if not ckpts:
        return None, None
    if len(ckpts) >= 2:
        return ckpts[-1], ckpts[-2]  # latest, previous
    return ckpts[-1], None


def compute_accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Compute token-level accuracy."""
    preds = logits.argmax(dim=-1)
    correct = (preds == labels).sum().item()
    total = labels.numel()
    return correct / max(1, total) * 100.0


def benchmark_core(
    core: NpDnaCore,
    test_texts: list[str],
    label: str,
) -> dict:
    """Run a mini benchmark on a loaded core, return metrics dict."""
    model = core.model
    model.eval()
    device = next(model.parameters()).device
    loss_fn = nn.CrossEntropyLoss(reduction="sum")

    # â”€â”€ 1. Loss & Perplexity & Accuracy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"  [{label}] Evaluating on {len(test_texts)} texts...", flush=True)
    total_loss = 0.0
    total_tokens = 0
    total_correct = 0
    with torch.no_grad():
        for text in test_texts:
            ids = core.encode(text, allow_growth=False)[:MAX_SEQ]
            if len(ids) < 2:
                continue
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            labels_t = torch.tensor([ids[1:]], dtype=torch.long, device=device)
            logits, _ = model(input_ids)
            loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels_t.reshape(-1))
            total_loss += float(loss)
            total_tokens += len(ids) - 1
            total_correct += int(
                (logits.argmax(dim=-1) == labels_t).sum().item()
            )

    avg_loss = total_loss / max(1, total_tokens)
    perplexity = math.exp(min(avg_loss, 100))
    accuracy = total_correct / max(1, total_tokens) * 100.0

    # â”€â”€ 2. Generation speed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"  [{label}] Measuring generation speed ({GENERATE_TOKENS} tokens)...", flush=True)
    core.generate("test", max_tokens=3)  # warmup
    start = time.perf_counter()
    result = core.generate("Hello world", max_tokens=GENERATE_TOKENS)
    elapsed = time.perf_counter() - start
    tokens_generated = len(core.encode(result, allow_growth=False))
    gen_speed = tokens_generated / max(0.001, elapsed)

    # â”€â”€ 3. Parameters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    total_params = model.parameter_count()
    active_params = model.active_parameter_count()

    # â”€â”€ 4. Metadata loss info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    meta_path = Path(core.active_path) / "metadata.json" if core.active_path else None
    meta_loss = None
    if meta_path and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        losses = meta.get("losses", [])
        if losses:
            recent = losses[-50:] if len(losses) >= 50 else losses
            meta_loss = {
                "recent_avg": round(sum(recent) / max(1, len(recent)), 4),
                "best": round(min(losses), 4),
                "final": round(losses[-1], 4),
                "total_steps": len(losses),
            }

    return {
        "label": label,
        "avg_loss": round(avg_loss, 4),
        "perplexity": round(perplexity, 2),
        "accuracy_pct": round(accuracy, 2),
        "total_params": total_params,
        "active_params": active_params,
        "gen_tokens": tokens_generated,
        "gen_time_sec": round(elapsed, 3),
        "gen_speed_tokps": round(gen_speed, 1),
        "train_loss": meta_loss,
    }


def format_table_entry(results: list[dict]) -> str:
    """Build the comparison table."""
    if len(results) == 0:
        return "No results."

    latest = results[-1]
    prev = results[0] if len(results) >= 2 else None

    # Determine comparison
    if prev:
        loss_diff = latest["avg_loss"] - prev["avg_loss"]
        acc_diff = latest["accuracy_pct"] - prev["accuracy_pct"]
        ppl_diff = latest["perplexity"] - prev["perplexity"]
        speed_diff = latest["gen_speed_tokps"] - prev["gen_speed_tokps"]

        loss_pct = (loss_diff / max(0.001, prev["avg_loss"])) * 100
        acc_pct = (acc_diff / max(0.001, prev["accuracy_pct"])) * 100 if prev["accuracy_pct"] > 0 else 0
        ppl_pct = (ppl_diff / max(0.001, prev["perplexity"])) * 100
        speed_pct = (speed_diff / max(0.001, prev["gen_speed_tokps"])) * 100
    else:
        loss_diff = acc_diff = ppl_diff = speed_diff = 0
        loss_pct = acc_pct = ppl_pct = speed_pct = 0

    # Determine verdict
    verdict = "GOOD" if acc_diff >= 0 else "BAD"
    verdict_emoji = "ðŸŸ¢" if verdict == "GOOD" else "ðŸ”´"

    # Format loss change
    def fmt_change(diff, pct, lower_is_better=True):
        if diff == 0:
            return "Â±0%"
        direction = "â†“" if diff < 0 else "â†‘"
        if lower_is_better:
            # lower is better means negative diff is good
            return f"{direction}{abs(pct):.1f}% {'ðŸŸ¢' if diff < 0 else 'ðŸ”´'}"
        else:
            return f"{direction}{abs(pct):.1f}% {'ðŸŸ¢' if diff > 0 else 'ðŸ”´'}"

    # Summary line
    [
        f"Checkpoint: **{latest['label']}**",
        f"Train Steps: {latest.get('train_loss', {}).get('total_steps', '?')}",
    ]

    # Build markdown table
    header = "| Metric | Value | vs Previous |"
    sep = "| ------ | ----- | ----------- |"

    rows = [
        ("Checkpoint", latest["label"], prev["label"] if prev else "N/A"),
        ("Eval Samples", str(NUM_EVAL_SAMPLES), str(NUM_EVAL_SAMPLES)),
        ("Avg CE Loss", f"{latest['avg_loss']:.4f}", fmt_change(loss_diff, loss_pct, True) if prev else "N/A"),
        ("Perplexity", f"{latest['perplexity']:.2f}", fmt_change(ppl_diff, ppl_pct, True) if prev else "N/A"),
        ("Accuracy", f"{latest['accuracy_pct']:.2f}%", fmt_change(acc_diff, acc_pct, False) if prev else "N/A"),
        ("Gen Speed", f"{latest['gen_speed_tokps']:.1f} tok/s", fmt_change(speed_diff, speed_pct, False) if prev else "N/A"),
        ("Total Params", f"{latest['total_params']:,}", f"{prev['total_params']:,}" if prev else "N/A"),
        ("Active Params", f"{latest['active_params']:,}", f"{prev['active_params']:,}" if prev else "N/A"),
    ]
    if latest.get("train_loss"):
        tl = latest["train_loss"]
        rows.append(("Train Loss (best)", f"{tl['best']:.4f}", "â€”"))
        rows.append(("Train Loss (final)", f"{tl['final']:.4f}", "â€”"))
        rows.append(("Train Steps (logged)", f"{tl['total_steps']}", "â€”"))

    table = f"\n{'='*65}\n  NP-DNA CHECKPOINT EVALUATION\n{'='*65}\n\n{header}\n{sep}\n"
    for metric, val, vs_prev in rows:
        table += f"| {metric} | {val} | {vs_prev} |\n"

    table += f"\n**Verdict:** {verdict_emoji} **{verdict}** â€” Accuracy {'improved' if acc_diff >= 0 else 'decreased'} by {abs(acc_diff):.2f}%"
    if prev:
        table += f" | Loss {'decreased' if loss_diff < 0 else 'increased'} by {abs(loss_diff):.4f}"

    return table


def save_experiment_log(results: list[dict], path: Path):
    """Append row to experiment log CSV."""
    latest = results[-1]
    prev = results[0] if len(results) >= 2 else None
    header = "timestamp,checkpoint,step,samples,loss,accuracy_pct,perplexity,gen_speed_tokps,train_steps,train_best_loss,train_final_loss,vs_previous_loss,vs_previous_acc,verdict"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    step_num = int(latest["label"].split("_")[1])
    loss = latest["avg_loss"]
    acc = latest["accuracy_pct"]
    ppl = latest["perplexity"]
    speed = latest["gen_speed_tokps"]
    tl = latest.get("train_loss", {})
    train_steps = tl.get("total_steps", "")
    train_best = tl.get("best", "")
    train_final = tl.get("final", "")

    if prev:
        vs_loss = prev["avg_loss"]
        vs_acc = prev["accuracy_pct"]
        v_loss_diff = loss - vs_loss
        v_acc_diff = acc - vs_acc
        verdict = "GOOD" if v_acc_diff >= 0 else "BAD"
    else:
        v_loss_diff = ""
        v_acc_diff = ""
        verdict = "FIRST"

    row = f"{timestamp},{latest['label']},{step_num},{NUM_EVAL_SAMPLES},{loss:.4f},{acc:.2f},{ppl:.2f},{speed:.1f},{train_steps},{train_best},{train_final},{v_loss_diff},{v_acc_diff},{verdict}"

    exists = path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if not exists:
            f.write(header + "\n")
        f.write(row + "\n")
    print(f"\n  [log] Appended to {path}", flush=True)


def write_improvement_json(results: list[dict], path: Path):
    """Write improvement.json if accuracy improved."""
    if len(results) < 2:
        return False
    latest = results[-1]
    prev = results[0]
    acc_diff = latest["accuracy_pct"] - prev["accuracy_pct"]
    if acc_diff < 0:
        print(f"  [info] Accuracy decreased ({acc_diff:+.2f}%), no improvement.json written.", flush=True)
        return False

    payload = {
        "checkpoint": latest["label"],
        "step": int(latest["label"].split("_")[1]),
        "accuracy_pct": latest["accuracy_pct"],
        "accuracy_improvement": round(acc_diff, 2),
        "loss": latest["avg_loss"],
        "perplexity": latest["perplexity"],
        "gen_speed_tokps": latest["gen_speed_tokps"],
        "previous_checkpoint": prev["label"],
        "previous_accuracy": prev["accuracy_pct"],
        "previous_loss": prev["avg_loss"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  [improvement] Written to {path}", flush=True)
    return True


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    print("=" * 65, flush=True)
    print("  NP-DNA CHECKPOINT EVALUATOR", flush=True)
    print("=" * 65, flush=True)

    latest_ckpt, prev_ckpt = get_latest_checkpoint(CHECKPOINT_DIR)
    if latest_ckpt is None:
        print("  No checkpoints found. Exiting.", flush=True)
        sys.exit(1)

    print(f"\n  Latest checkpoint: {latest_ckpt.name}", flush=True)
    if prev_ckpt:
        print(f"  Previous checkpoint: {prev_ckpt.name}", flush=True)
    else:
        print("  No previous checkpoint for comparison.", flush=True)

    print(f"\n  Test data: {TEST_DATA}", flush=True)
    print(f"  Loading up to {NUM_EVAL_SAMPLES} samples...", flush=True)
    test_texts = load_test_texts(TEST_DATA, NUM_EVAL_SAMPLES)
    print(f"  Loaded {len(test_texts)} test samples", flush=True)

    results = []
    checkpoints_to_run = []
    if prev_ckpt:
        checkpoints_to_run.append(prev_ckpt)
    checkpoints_to_run.append(latest_ckpt)

    for cp in checkpoints_to_run:
        label = cp.name
        print(f"\n[{label}] Loading checkpoint...", flush=True)
        try:
            core = NpDnaCore.load(str(cp))
            core.model.to(DEVICE)
            print(f"  Model: {core.model.parameter_count():,} params, device={DEVICE}", flush=True)
            res = benchmark_core(core, test_texts, label)
            results.append(res)
            print(f"  [{label}] Done. Loss={res['avg_loss']:.4f}, Acc={res['accuracy_pct']:.2f}%, "
                  f"PPL={res['perplexity']:.2f}, Speed={res['gen_speed_tokps']:.1f} tok/s", flush=True)
        except Exception as e:
            print(f"  [{label}] ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            del core
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    if not results:
        print("  No results generated.", flush=True)
        sys.exit(1)

    # Sort by step number
    results.sort(key=lambda r: int(r["label"].split("_")[1]))

    # Print comparison table
    table = format_table_entry(results)
    print(table, flush=True)

    # Save experiment log
    save_experiment_log(results, EXPERIMENT_LOG)

    # Write improvement.json if accuracy improved
    write_improvement_json(results, IMPROVEMENT_FILE)

    print("=" * 65, flush=True)
    print("  Evaluation complete.", flush=True)
    print("=" * 65, flush=True)

