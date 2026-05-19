"""NP-DNA training pipeline.

Supports:
  - Full training (train all params)
  - Chunk/topic training (train ONE strand on ONE topic, others frozen)
  - Resumable checkpoints
  - Plasticity monitoring (auto-adapt architecture)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import gc
import shutil
from pathlib import Path

import torch
from torch import nn

# Add project root to path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from atulya.core.npdna import NpDnaCore, PlasticityEngine
from training.dataset.build_dataset import build_seed_dataset, load_dataset

logger = logging.getLogger(__name__)


def _write_train_status(output_dir: str | Path, phase: str, **fields) -> None:
    """Write dashboard-readable training status before metrics exist."""
    path = Path(output_dir) / "train_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": phase,
        "time": time.time(),
        **fields,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _select_device(device: str) -> torch.device:
    if device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(device)


def train_npdna(
    config_name: str = "seed",
    max_steps: int = 50,
    lr: float = 2e-3,
    batch_size: int = 1,
    seq_limit: int = 128,
    output_dir: str = "outputs/npdna",
    data_path: str = "data/seed_dataset.jsonl",
    log_every: int = 10,
    checkpoint_every: int = 0,
    resume_from: str | None = None,
    bf16: bool = False,
    pack_sequences: bool = False,
    limit_samples: int | None = None,
    device: str = "auto",
    bpe_merges: int = 0,
) -> tuple[NpDnaCore, list[float]]:
    """Train an NP-DNA model.

    Args:
        config_name: One of "seed", "nano", "micro", "small", "medium".
        max_steps: Total training steps.
        lr: Learning rate.
        batch_size: Batch size (1 is fine for CPU).
        seq_limit: Maximum sequence length per sample.
        output_dir: Where to save the model.
        data_path: Path to JSONL dataset.
        log_every: Log loss every N steps.
        checkpoint_every: Save checkpoint every N steps (0 = disabled).
        resume_from: Path to resume from a checkpoint.

    Returns:
        (core, losses) — trained model and loss history.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    _write_train_status(
        output_dir,
        "starting",
        config=config_name,
        max_steps=max_steps,
        data_path=data_path,
        limit_samples=limit_samples,
    )

    train_device = _select_device(device)

    # Load or create model
    if resume_from:
        logger.info("Resuming from %s", resume_from)
        _write_train_status(output_dir, "loading_checkpoint", resume_from=resume_from)
        core = NpDnaCore.load(resume_from)
    else:
        logger.info("Creating NP-DNA model [%s]", config_name)
        _write_train_status(output_dir, "creating_model", config=config_name)
        core = NpDnaCore.from_config(config_name)

    # Ensure dataset exists
    if not Path(data_path).exists():
        build_seed_dataset(data_path)

    # Load and encode data
    _write_train_status(output_dir, "loading_dataset", data_path=data_path, limit_samples=limit_samples)
    texts = load_dataset(data_path, limit=limit_samples)

    if bpe_merges > 0 and not core.tokenizer.merges:
        _write_train_status(
            output_dir,
            "training_tokenizer",
            target_merges=bpe_merges,
            sample_count=min(len(texts), 20000),
        )
        old_capacity = core.tokenizer.capacity
        core.tokenizer.train_bpe(texts[:20000], target_merges=bpe_merges)
        if core.tokenizer.capacity != old_capacity:
            core.model.resize_embeddings(core.tokenizer.capacity)
        logger.info(
            "Tokenizer warmup complete: %d merges, vocab=%d/%d",
            len(core.tokenizer.merges),
            core.tokenizer.size,
            core.tokenizer.capacity,
        )

    logger.info("Encoding %d texts (seq_limit=%d)...", len(texts), seq_limit)
    _write_train_status(output_dir, "encoding", total_texts=len(texts), seq_limit=seq_limit)
    encoded = []
    for i, text in enumerate(texts, start=1):
        ids = core.encode(text)[:seq_limit]
        if len(ids) >= 2:
            encoded.append(ids)
        if i == 1 or i % 500 == 0 or i == len(texts):
            _write_train_status(
                output_dir,
                "encoding",
                encoded=len(encoded),
                seen=i,
                total_texts=len(texts),
                vocab=core.tokenizer.size,
                vocab_capacity=core.tokenizer.capacity,
            )
    logger.info("Encoded %d samples, vocab=%d/%d", len(encoded), core.tokenizer.size, core.tokenizer.capacity)

    if pack_sequences:
        _write_train_status(output_dir, "packing", encoded=len(encoded), seq_limit=seq_limit)
        packed_encoded = []
        current_pack = []
        for ids in encoded:
            if len(current_pack) + len(ids) <= seq_limit:
                current_pack.extend(ids)
            else:
                if len(current_pack) >= 2:
                    packed_encoded.append(current_pack)
                current_pack = ids
        if len(current_pack) >= 2:
            packed_encoded.append(current_pack)
        encoded = packed_encoded
        logger.info("Packed into %d sequences", len(encoded))
        _write_train_status(output_dir, "packed", sequences=len(encoded))

    if not encoded:
        logger.error("No valid training samples. Aborting.")
        _write_train_status(output_dir, "error", error="No valid training samples")
        return core, []

    # Setup training
    model = core.model
    model.to(train_device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()
    plasticity = PlasticityEngine(core, check_interval=max(10, max_steps // 10))
    use_autocast = bool(bf16 and train_device.type == "cuda")
    if bf16 and not use_autocast:
        logger.info("bfloat16 autocast requested but disabled on %s for stability", train_device.type)

    losses: list[float] = []
    step = 0
    tokens_seen = 0
    start_time = time.time()

    logger.info(
        "Training: %d steps, lr=%.1e, %s total params, %s active params",
        max_steps, lr,
        f"{model.parameter_count():,}",
        f"{model.active_parameter_count():,}",
    )
    _write_train_status(
        output_dir,
        "training",
        step=0,
        max_steps=max_steps,
        samples=len(encoded),
        device=str(train_device),
        bf16=use_autocast,
        parameter_count=model.parameter_count(),
        active_parameter_count=model.active_parameter_count(),
    )

    # Training loop
    for epoch in range(1, 10001):
        for ids in encoded:
            if step >= max_steps:
                break

            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=train_device)
            labels = torch.tensor([ids[1:]], dtype=torch.long, device=train_device)

            if use_autocast:
                with torch.autocast(device_type=train_device.type, dtype=torch.bfloat16):
                    logits, balance_loss = model(input_ids)
                    ce_loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
                    loss = ce_loss + balance_loss
            else:
                logits, balance_loss = model(input_ids)
                ce_loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
                loss = ce_loss + balance_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            loss_val = float(ce_loss.detach())
            losses.append(loss_val)
            plasticity.record_loss(loss_val)

            step += 1
            tokens_seen += max(0, len(ids) - 1)
            if step == 1 or step % max(1, log_every) == 0:
                _write_train_status(
                    output_dir,
                    "training",
                    step=step,
                    max_steps=max_steps,
                    loss=loss_val,
                    avg_loss=sum(losses[-50:]) / min(len(losses), 50),
                )

            if log_every > 0 and step % log_every == 0:
                elapsed = time.time() - start_time
                avg = sum(losses[-log_every:]) / min(len(losses), log_every)
                tok_per_sec = tokens_seen / max(1, elapsed)
                logger.info(
                    "step %d/%d  loss=%.4f  avg=%.4f  elapsed=%.1fs  tok/s=%.0f",
                    step, max_steps, loss_val, avg, elapsed, tok_per_sec,
                )
            
            # Live metrics append for dashboard
            metrics_file = Path(output_dir) / "live_metrics.jsonl"
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            usage = {}
            for layer_i, mesh in enumerate(model.mesh_layers):
                for strand_id, ratio in mesh.usage_stats.items():
                    usage[f"L{layer_i}-S{strand_id}"] = ratio
            with open(metrics_file, "a") as f:
                f.write(json.dumps({
                    "step": step, 
                    "loss": loss_val,
                    "avg_loss": sum(losses[-50:]) / min(len(losses), 50),
                    "usage": usage,
                    "total_params": model.parameter_count(),
                    "active_params": model.active_parameter_count(),
                }) + "\n")

            # Plasticity check
            events = plasticity.check(step)
            for e in events:
                logger.info("⚡ Plasticity [%s]: %s", e.event_type, e.details)

            # Checkpoint
            if checkpoint_every > 0 and step % checkpoint_every == 0:
                ckpt_path = Path(output_dir) / "checkpoints" / f"step_{step:06d}"
                core.save(ckpt_path, losses=losses)
                
                # Keep max 5 best checkpoints
                ckpt_dir = Path(output_dir) / "checkpoints"
                ckpts = []
                for d in ckpt_dir.iterdir():
                    if d.is_dir() and (d / "metadata.json").exists():
                        try:
                            m = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
                            c_loss = min(m.get("losses", [999]))
                            ckpts.append((c_loss, d))
                        except Exception:
                            pass
                
                ckpts.sort(key=lambda x: x[0])
                if len(ckpts) > 5:
                    for _, d in ckpts[5:]:
                        shutil.rmtree(d, ignore_errors=True)
                
                # Save best to latest
                if ckpts and ckpts[0][1] == ckpt_path:
                    core.save(output_dir, losses=losses)
                    logger.info("Checkpoint saved (NEW BEST): %s", ckpt_path)
                else:
                    logger.info("Checkpoint saved: %s", ckpt_path)

            del input_ids, labels, logits, balance_loss, ce_loss, loss
            if step % 50 == 0:
                gc.collect()
                if train_device.type == "cuda":
                    torch.cuda.empty_cache()

        if step >= max_steps:
            break

    # Save final model
    elapsed = time.time() - start_time
    logger.info("Training complete: %d steps in %.1fs", step, elapsed)
    _write_train_status(
        output_dir,
        "complete",
        step=step,
        max_steps=max_steps,
        elapsed=elapsed,
        final_loss=losses[-1] if losses else None,
    )

    # Save final model if it's the best
    ckpt_dir = Path(output_dir) / "checkpoints"
    best_loss_so_far = 999
    if ckpt_dir.exists():
        for d in ckpt_dir.iterdir():
            if d.is_dir() and (d / "metadata.json").exists():
                try:
                    m = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
                    best_loss_so_far = min(best_loss_so_far, min(m.get("losses", [999])))
                except Exception:
                    pass

    final_min = min(losses) if losses else 999
    if final_min <= best_loss_so_far:
        core.save(output_dir, losses=losses)
        logger.info("Final model saved to %s (Best Loss: %.4f)", output_dir, final_min)
    else:
        logger.info("Final model not better than best checkpoint. Latest remains unchanged.")

    # Print summary
    final_loss = losses[-1] if losses else None
    logger.info(
        "Summary: config=%s  params=%s  active=%s  vocab=%d  "
        "final_loss=%.4f  steps=%d  time=%.1fs",
        config_name,
        f"{model.parameter_count():,}",
        f"{model.active_parameter_count():,}",
        core.tokenizer.size,
        final_loss or 0.0,
        step,
        elapsed,
    )

    if plasticity.events:
        logger.info(plasticity.summary())

    return core, losses


def train_topic(
    model_path: str,
    topic: str,
    data_path: str,
    strand_id: int | None = None,
    steps: int = 100,
    lr: float = 1e-3,
) -> NpDnaCore:
    """Chunk-train a single Strand on a specific topic.

    Only the Genome seed for the target Strand is updated.
    All other parameters are frozen. Takes ~30s on CPU.

    Args:
        model_path: Path to saved NpDnaCore.
        topic: Topic name (for logging).
        data_path: Path to topic-specific JSONL data.
        strand_id: Which Strand to train (auto-selects least-used if None).
        steps: Training steps.
        lr: Learning rate.

    Returns:
        Updated NpDnaCore.
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("Chunk training: topic=%s, strand=%s, steps=%d", topic, strand_id, steps)

    core = NpDnaCore.load(model_path)
    model = core.model

    # Find least-used Strand if not specified
    if strand_id is None:
        all_usage = {}
        for mesh in model.mesh_layers:
            all_usage.update(mesh.usage_stats)
        strand_id = min(all_usage, key=all_usage.get)
        logger.info("Auto-selected Strand %d (least used)", strand_id)

    # Freeze everything
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze ONLY the target Strand's DNA seed
    model.genome.seeds.requires_grad = True
    # We'll mask gradients to only update the target seed

    texts = load_dataset(data_path)
    encoded = []
    for t in texts:
        ids = core.encode(t)[:128]
        if len(ids) >= 2:
            encoded.append(ids)

    optimizer = torch.optim.AdamW([model.genome.seeds], lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    for step in range(1, steps + 1):
        loss = None
        for ids in encoded:
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long)
            labels = torch.tensor([ids[1:]], dtype=torch.long)

            logits, _ = model(input_ids)
            ce_loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
            loss = ce_loss # assign ce_loss to loss for compatibility with below

            optimizer.zero_grad()
            loss.backward()

            # Mask gradient: only update the target strand's seed
            with torch.no_grad():
                mask = torch.zeros_like(model.genome.seeds)
                mask[strand_id] = 1.0
                model.genome.seeds.grad *= mask

            optimizer.step()

        if step % 10 == 0:
            loss_val = float(loss) if loss is not None else float("nan")
            logger.info("  topic=%s step=%d loss=%.4f", topic, step, loss_val)

    # Unfreeze all
    for param in model.parameters():
        param.requires_grad = True

    core.save(model_path)
    logger.info("Chunk training complete: topic=%s saved to %s", topic, model_path)
    return core


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NP-DNA Training")
    parser.add_argument("--config", default="seed", help="Config: seed/nano/micro/small/medium")
    parser.add_argument("--steps", type=int, default=50, help="Training steps")
    parser.add_argument("--lr", type=float, default=2e-3, help="Learning rate")
    parser.add_argument("--output", default="outputs/npdna", help="Output directory")
    parser.add_argument("--data", default="data/seed_dataset.jsonl", help="Dataset path")
    parser.add_argument("--log-every", type=int, default=10, help="Log interval")
    parser.add_argument("--checkpoint-every", type=int, default=0, help="Checkpoint interval")
    parser.add_argument("--resume", default=None, help="Resume from checkpoint path")
    parser.add_argument("--bf16", action="store_true", help="Use bfloat16 autocast")
    parser.add_argument("--pack", action="store_true", help="Pack short sequences into batches")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of training samples")
    parser.add_argument("--device", default="auto", help="Training device: auto/cpu/cuda")
    parser.add_argument("--bpe-merges", type=int, default=0, help="Train tokenizer BPE merges before model training")

    args = parser.parse_args()
    try:
        train_npdna(
            config_name=args.config,
            max_steps=args.steps,
            lr=args.lr,
            output_dir=args.output,
            data_path=args.data,
            log_every=args.log_every,
            checkpoint_every=args.checkpoint_every,
            resume_from=args.resume,
            bf16=args.bf16,
            pack_sequences=args.pack,
            limit_samples=args.limit,
            device=args.device,
            bpe_merges=args.bpe_merges,
        )
    except Exception as exc:
        _write_train_status(args.output, "error", error=str(exc))
        raise
