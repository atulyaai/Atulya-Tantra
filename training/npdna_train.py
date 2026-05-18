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
from pathlib import Path

import torch
from torch import nn

# Add project root to path for src layout
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from atulya.core.npdna import NpDnaCore, PlasticityEngine
from training.dataset.build_dataset import build_seed_dataset, load_dataset

logger = logging.getLogger(__name__)


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

    # Load or create model
    if resume_from:
        logger.info("Resuming from %s", resume_from)
        core = NpDnaCore.load(resume_from)
    else:
        logger.info("Creating NP-DNA model [%s]", config_name)
        core = NpDnaCore.from_config(config_name)

    # Ensure dataset exists
    if not Path(data_path).exists():
        build_seed_dataset(data_path)

    # Load and encode data
    texts = load_dataset(data_path)
    logger.info("Encoding %d texts (seq_limit=%d)...", len(texts), seq_limit)
    encoded = []
    for text in texts:
        ids = core.encode(text)[:seq_limit]
        if len(ids) >= 2:
            encoded.append(ids)
    logger.info("Encoded %d samples, vocab=%d/%d", len(encoded), core.tokenizer.size, core.tokenizer.capacity)

    if not encoded:
        logger.error("No valid training samples. Aborting.")
        return core, []

    # Setup training
    model = core.model
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()
    plasticity = PlasticityEngine(core, check_interval=max(10, max_steps // 10))

    losses: list[float] = []
    step = 0
    start_time = time.time()

    logger.info(
        "Training: %d steps, lr=%.1e, %s total params, %s active params",
        max_steps, lr,
        f"{model.parameter_count():,}",
        f"{model.active_parameter_count():,}",
    )

    # Training loop
    for epoch in range(1, 10001):
        for ids in encoded:
            if step >= max_steps:
                break

            input_ids = torch.tensor([ids[:-1]], dtype=torch.long)
            labels = torch.tensor([ids[1:]], dtype=torch.long)

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

            if log_every > 0 and step % log_every == 0:
                elapsed = time.time() - start_time
                avg = sum(losses[-log_every:]) / min(len(losses), log_every)
                tok_per_sec = sum(len(ids) for ids in encoded[:step]) / max(1, elapsed)
                logger.info(
                    "step %d/%d  loss=%.4f  avg=%.4f  elapsed=%.1fs  tok/s=%.0f",
                    step, max_steps, loss_val, avg, elapsed, tok_per_sec,
                )

            # Plasticity check
            events = plasticity.check(step)
            for e in events:
                logger.info("⚡ Plasticity [%s]: %s", e.event_type, e.details)

            # Checkpoint
            if checkpoint_every > 0 and step % checkpoint_every == 0:
                ckpt_path = Path(output_dir) / "checkpoints" / f"step_{step:06d}"
                core.save(ckpt_path, losses=losses)
                logger.info("Checkpoint saved: %s", ckpt_path)

        if step >= max_steps:
            break

    # Save final model
    elapsed = time.time() - start_time
    logger.info("Training complete: %d steps in %.1fs", step, elapsed)

    core.save(output_dir, losses=losses)
    logger.info("Model saved to %s", output_dir)

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
    encoded = [core.encode(t)[:128] for t in texts if len(core.encode(t)) >= 2]

    optimizer = torch.optim.AdamW([model.genome.seeds], lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    for step in range(1, steps + 1):
        for ids in encoded:
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long)
            labels = torch.tensor([ids[1:]], dtype=torch.long)

            logits, _ = model(input_ids)
            loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))

            optimizer.zero_grad()
            loss.backward()

            # Mask gradient: only update the target strand's seed
            with torch.no_grad():
                mask = torch.zeros_like(model.genome.seeds)
                mask[strand_id] = 1.0
                model.genome.seeds.grad *= mask

            optimizer.step()

        if step % 10 == 0:
            logger.info("  topic=%s step=%d loss=%.4f", topic, step, float(loss))

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

    args = parser.parse_args()
    train_npdna(
        config_name=args.config,
        max_steps=args.steps,
        lr=args.lr,
        output_dir=args.output,
        data_path=args.data,
        log_every=args.log_every,
        checkpoint_every=args.checkpoint_every,
        resume_from=args.resume,
    )
