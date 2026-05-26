#!/usr/bin/env python
"""Evaluate latest NP-DNA checkpoint — standalone script for cron job."""
import json, logging, math, os, sys, time
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tantra.npdna import NpDnaCore

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ── Config ─────────────────────────────────────────────────────────────────────
MODEL_PATH = ROOT / "outputs/npdna_nano/versions/v2_20260526_222133"
TEST_DATA  = ROOT / "data/all_datasets.jsonl"
NUM_EVAL_SAMPLES = 64
GENERATE_TOKENS = 20
MAX_SEQ = 128
DEVICE = "cpu"
EXPERIMENT_LOG = ROOT / "../docs/results/experiment_log.csv"
IMPROVEMENT_FILE = ROOT / "../docs/results/improvement.json"

def _fallback_test_texts() -> list[str]:
    return [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a versatile programming language.",
        "The Earth orbits the Sun at an average distance of 93 million miles.",
    ]

def load_test_texts(path: Path, n: int) -> list[str]:
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

def read_previous_log(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("timestamp")]
    if not lines:
        return None
    last = lines[-1].split(",")
    if len(last) < 14:
        return None
    return {
        "checkpoint": last[1],
        "step": int(last[2]),
        "samples": int(last[3]),
        "loss": float(last[4]),
        "accuracy_pct": float(last[5]),
        "perplexity": float(last[6]),
        "gen_speed_tokps": float(last[7]),
        "train_steps": int(last[8]) if last[8] else 0,
        "train_best_loss": float(last[9]) if last[9] else 0.0,
        "train_final_loss": float(last[10]) if last[10] else 0.0,
    }

def compute_accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    preds = logits.argmax(dim=-1)
    correct = (preds == labels).sum().item()
    total = labels.numel()
    return correct / max(1, total) * 100.0

def benchmark_core(core: NpDnaCore, test_texts: list[str], label: str) -> dict:
    model = core.model
    model.eval()
    device = next(model.parameters()).device
    loss_fn = nn.CrossEntropyLoss(reduction="sum")

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
            total_correct += int((logits.argmax(dim=-1) == labels_t).sum().item())

    avg_loss = total_loss / max(1, total_tokens)
    perplexity = math.exp(min(avg_loss, 100))
    accuracy = total_correct / max(1, total_tokens) * 100.0

    # Generation speed
    print(f"  [{label}] Measuring generation speed ({GENERATE_TOKENS} tokens)...", flush=True)
    core.generate("test", max_tokens=3)
    start = time.perf_counter()
    result = core.generate("Hello world", max_tokens=GENERATE_TOKENS)
    elapsed = time.perf_counter() - start
    tokens_generated = len(core.encode(result, allow_growth=False))
    gen_speed = tokens_generated / max(0.001, elapsed)

    # Parameter counts
    total_params = model.parameter_count()
    active_params = model.active_parameter_count()

    # Metadata loss info
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

def format_results(latest: dict, prev: dict | None) -> str:
    # Comparison metrics
    if prev:
        loss_diff = latest["avg_loss"] - prev["loss"]
        acc_diff = latest["accuracy_pct"] - prev["accuracy_pct"]
        ppl_diff = latest["perplexity"] - prev["perplexity"]
        speed_diff = latest["gen_speed_tokps"] - prev["gen_speed_tokps"]

        loss_pct = (loss_diff / max(0.001, prev["loss"])) * 100
        acc_pct = (acc_diff / max(0.001, prev["accuracy_pct"])) * 100 if prev["accuracy_pct"] > 0 else 0
        ppl_pct = (ppl_diff / max(0.001, prev["perplexity"])) * 100
        speed_pct = (speed_diff / max(0.001, prev["gen_speed_tokps"])) * 100
    else:
        loss_diff = acc_diff = ppl_diff = speed_diff = 0
        loss_pct = acc_pct = ppl_pct = speed_pct = 0

    verdict = "GOOD" if acc_diff >= 0 else "BAD"
    verdict_emoji = "🟢" if verdict == "GOOD" else "🔴"

    def fmt_change(diff, pct, lower_better=True):
        if diff == 0:
            return "±0%"
        direction = "↓" if diff < 0 else "↑"
        if lower_better:
            return f"{direction}{abs(pct):.1f}% {'🟢' if diff < 0 else '🔴'}"
        else:
            return f"{direction}{abs(pct):.1f}% {'🟢' if diff > 0 else '🔴'}"

    # Build report
    lines = []
    lines.append(f"Checkpoint | Samples | Loss | Acc% | Tok/s | vs Previous | Verdict")
    lines.append(f"---------- | ------- | ---- | ---- | ----- | ----------- | -------")

    vs_str = "N/A (first eval)"
    if prev:
        vs_str = f"{'+' if acc_diff > 0 else ''}{acc_diff:+.2f}% {'🟢' if acc_diff >= 0 else '🔴'}"

    lines.append(
        f"{latest['label']} | {NUM_EVAL_SAMPLES} | {latest['avg_loss']:.4f} | "
        f"{latest['accuracy_pct']:.1f}% | {latest['gen_speed_tokps']:.1f} | "
        f"{vs_str} | {verdict_emoji} {verdict}"
    )

    lines.append("")
    lines.append("**Full Metrics:**")
    lines.append(f"- Avg CE Loss: {latest['avg_loss']:.4f} {f'({fmt_change(loss_diff, loss_pct, True)})' if prev else ''}")
    lines.append(f"- Perplexity: {latest['perplexity']:.2f} {f'({fmt_change(ppl_diff, ppl_pct, True)})' if prev else ''}")
    lines.append(f"- Accuracy: {latest['accuracy_pct']:.2f}% {f'({fmt_change(acc_diff, acc_pct, False)})' if prev else ''}")
    lines.append(f"- Generation Speed: {latest['gen_speed_tokps']:.1f} tok/s {f'({fmt_change(speed_diff, speed_pct, False)})' if prev else ''}")
    lines.append(f"- Total Params: {latest['total_params']:,}")
    lines.append(f"- Active Params: {latest['active_params']:,}")

    if latest.get("train_loss"):
        tl = latest["train_loss"]
        lines.append(f"- Training Steps Logged: {tl['total_steps']}")
        lines.append(f"- Training Best Loss: {tl['best']:.4f}")
        lines.append(f"- Training Final Loss: {tl['final']:.4f}")

    if prev:
        lines.append(f"\n**Comparison with {prev['checkpoint']}:**")
        lines.append(f"- Loss: {prev['loss']:.4f} → {latest['avg_loss']:.4f} ({loss_diff:+.4f})")
        lines.append(f"- Accuracy: {prev['accuracy_pct']:.2f}% → {latest['accuracy_pct']:.2f}% ({acc_diff:+.2f}%)")
        lines.append(f"- Perplexity: {prev['perplexity']:.2f} → {latest['perplexity']:.2f} ({ppl_diff:+.2f})")

    lines.append(f"\n**Verdict:** {verdict_emoji} {verdict}")
    if prev:
        lines.append(f"  Accuracy {'improved' if acc_diff >= 0 else 'decreased'} by {abs(acc_diff):.2f}%")
        lines.append(f"  Loss {'decreased' if loss_diff < 0 else 'increased'} by {abs(loss_diff):.4f}")

    return "\n".join(lines)

def save_experiment_log(latest: dict, prev: dict | None, path: Path):
    header = "timestamp,checkpoint,step,samples,loss,accuracy_pct,perplexity,gen_speed_tokps,train_steps,train_best_loss,train_final_loss,vs_previous_loss,vs_previous_acc,verdict"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    step_num = latest.get("train_loss", {}).get("total_steps", 0)
    loss = latest["avg_loss"]
    acc = latest["accuracy_pct"]
    ppl = latest["perplexity"]
    speed = latest["gen_speed_tokps"]
    tl = latest.get("train_loss", {})
    train_steps = tl.get("total_steps", "")
    train_best = tl.get("best", "")
    train_final = tl.get("final", "")

    if prev:
        v_loss_diff = round(loss - prev["loss"], 4)
        v_acc_diff = round(acc - prev["accuracy_pct"], 2)
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

def write_improvement_json(latest: dict, prev: dict | None, path: Path):
    if prev is None:
        return False
    acc_diff = latest["accuracy_pct"] - prev["accuracy_pct"]
    if acc_diff < 0:
        print(f"  [info] Accuracy decreased ({acc_diff:+.2f}%), no improvement.json written.", flush=True)
        return False

    payload = {
        "checkpoint": latest["label"],
        "step": latest.get("train_loss", {}).get("total_steps", 0),
        "accuracy_pct": latest["accuracy_pct"],
        "accuracy_improvement": round(acc_diff, 2),
        "loss": latest["avg_loss"],
        "perplexity": latest["perplexity"],
        "gen_speed_tokps": latest["gen_speed_tokps"],
        "previous_checkpoint": prev["checkpoint"],
        "previous_accuracy": prev["accuracy_pct"],
        "previous_loss": prev["loss"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  [improvement] Written to {path}", flush=True)
    return True

if __name__ == "__main__":
    print("=" * 65, flush=True)
    print("  NP-DNA CHECKPOINT EVALUATOR (CRON)", flush=True)
    print("=" * 65, flush=True)

    # Read previous log
    prev = read_previous_log(EXPERIMENT_LOG)
    if prev:
        print(f"\n  Previous checkpoint: {prev['checkpoint']} (loss={prev['loss']:.4f}, acc={prev['accuracy_pct']:.2f}%)", flush=True)
    else:
        print("\n  No previous checkpoint found in experiment log.", flush=True)

    # Load model
    label = MODEL_PATH.name
    print(f"\n  Loading checkpoint: {MODEL_PATH}", flush=True)
    try:
        core = NpDnaCore.load(str(MODEL_PATH))
        core.model.to(DEVICE)
        total_p = core.model.parameter_count()
        active_p = core.model.active_parameter_count()
        print(f"  Model: {total_p:,} total params, {active_p:,} active, device={DEVICE}", flush=True)
    except Exception as e:
        print(f"  ERROR loading model: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Load test data
    print(f"\n  Test data: {TEST_DATA}", flush=True)
    print(f"  Loading up to {NUM_EVAL_SAMPLES} samples...", flush=True)
    test_texts = load_test_texts(TEST_DATA, NUM_EVAL_SAMPLES)
    print(f"  Loaded {len(test_texts)} test samples", flush=True)

    # Run benchmark
    try:
        latest_res = benchmark_core(core, test_texts, label)
        print(f"\n  Done. Loss={latest_res['avg_loss']:.4f}, Acc={latest_res['accuracy_pct']:.2f}%, "
              f"PPL={latest_res['perplexity']:.2f}, Speed={latest_res['gen_speed_tokps']:.1f} tok/s", flush=True)
    except Exception as e:
        print(f"  ERROR during benchmark: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        del core
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Build and print results
    report = format_results(latest_res, prev)
    print(f"\n{'='*65}", flush=True)
    print(report, flush=True)
    print(f"{'='*65}", flush=True)

    # Save experiment log
    save_experiment_log(latest_res, prev, EXPERIMENT_LOG)

    # Write improvement.json if accuracy improved
    write_improvement_json(latest_res, prev, IMPROVEMENT_FILE)

    print(f"\n  Evaluation complete.", flush=True)
