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
import psutil

# Add project root to path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from atulya.core.npdna import NpDnaCore, PlasticityEngine
from training.dataset.build_dataset import build_seed_dataset, load_dataset

logger = logging.getLogger(__name__)


def _initialize_new_token_embeddings(
    core: NpDnaCore,
    old_vocab_size: int,
    old_token_to_id: dict[str, int],
) -> None:
    """Initialize newly added BPE token rows from their component tokens.

    The tokenizer may add merge tokens without increasing embedding capacity.
    On a resumed model those rows exist but have never been trained. Averaging
    component embeddings gives them a useful starting point instead of random
    behavior.
    """
    tokenizer = core.tokenizer
    embedding = core.model.embedding.weight
    if old_vocab_size >= tokenizer.size:
        return

    merge_by_token = {a + b: (a, b) for a, b in tokenizer.merges}

    def old_piece_ids(token: str) -> list[int]:
        if token in old_token_to_id:
            return [old_token_to_id[token]]
        pair = merge_by_token.get(token)
        if not pair:
            ids: list[int] = []
            for ch in token:
                if ch in old_token_to_id:
                    ids.append(old_token_to_id[ch])
                else:
                    ids.extend(
                        tokenizer.byte_to_id.get(b, 1)
                        for b in ch.encode("utf-8")
                        if tokenizer.byte_to_id.get(b, 1) < old_vocab_size
                    )
            return ids
        left, right = pair
        return old_piece_ids(left) + old_piece_ids(right)

    with torch.no_grad():
        for token_id in range(old_vocab_size, min(tokenizer.size, embedding.shape[0])):
            token = tokenizer.id_to_token[token_id]
            piece_ids = [idx for idx in old_piece_ids(token) if 0 <= idx < old_vocab_size]
            if piece_ids:
                embedding[token_id].copy_(embedding[piece_ids].mean(dim=0))
            else:
                embedding[token_id].normal_(mean=0.0, std=0.02)


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


def _training_metadata(
    *,
    config_name: str,
    data_path: str,
    limit_samples: int | None,
    step: int,
    max_steps: int,
    losses: list[float],
    pack_sequences: bool,
    bpe_merges: int,
    lr_schedule: str,
    balance_weight: float,
    plasticity_interval: int,
    plasticity_overload_threshold: float,
) -> dict[str, object]:
    return {
        "train_config_name": config_name,
        "train_data_path": str(Path(data_path).resolve()),
        "train_data_name": Path(data_path).name,
        "train_limit_samples": limit_samples,
        "train_step": step,
        "train_max_steps": max_steps,
        "train_final_loss": losses[-1] if losses else None,
        "train_best_loss": min(losses) if losses else None,
        "train_loss_count": len(losses),
        "train_pack_sequences": pack_sequences,
        "train_bpe_merges": bpe_merges,
        "train_append_eos": True,
        "train_lr_schedule": lr_schedule,
        "train_balance_weight": balance_weight,
        "train_plasticity_interval": plasticity_interval,
        "train_plasticity_overload_threshold": plasticity_overload_threshold,
    }


def _set_mesh_balance_weight(core: NpDnaCore, balance_weight: float) -> None:
    core.config.mesh.balance_weight = balance_weight
    for mesh in core.model.mesh_layers:
        mesh.config.balance_weight = balance_weight


def _select_device(device: str) -> torch.device:
    if device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(device)


def _available_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def _estimate_training_ram_gb(core: NpDnaCore, seq_limit: int, batch_size: int) -> float:
    """Conservative CPU RAM estimate for one training step.

    This is intentionally simple and biased high.  Backward needs parameters,
    gradients, optimizer state, generated strand weights, and recurrent
    activations.  CPU OOM failures often happen on tiny allocations when the
    system is already exhausted, so the useful rule is headroom, not precision.
    """
    param_bytes = sum(p.numel() * p.element_size() for p in core.model.parameters())
    optimizer_bytes = param_bytes * 2.5  # AdamW moments plus gradients/working buffers
    activation_bytes = (
        batch_size
        * max(1, seq_limit)
        * core.config.hidden_size
        * core.config.num_layers
        * max(1, core.config.mesh.top_k)
        * 4
        * 12
    )
    overhead_bytes = 1.0 * 1024 ** 3
    return (param_bytes + optimizer_bytes + activation_bytes + overhead_bytes) / (1024 ** 3)


def _memory_rule_status(core: NpDnaCore, seq_limit: int, batch_size: int, min_free_ram_gb: float) -> dict[str, float]:
    available = _available_ram_gb()
    estimated = _estimate_training_ram_gb(core, seq_limit, batch_size)
    required = max(min_free_ram_gb, estimated * 0.35)
    return {
        "available_ram_gb": round(available, 3),
        "estimated_training_ram_gb": round(estimated, 3),
        "required_free_ram_gb": round(required, 3),
    }


def _is_cpu_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "defaultcpuallocator" in text
        or "not enough memory" in text
        or "out of memory" in text
    )


def restore_optimizer_state(
    new_optimizer: torch.optim.Optimizer,
    old_named_states: dict[str, dict],
    model: nn.Module,
) -> None:
    """Safely transfers and pads optimizer states from a previous state dictionary.

    Tensors that did not change are copied exactly.
    Tensors that expanded in size are zero-padded along the grown dimensions.
    """
    new_named_params = dict(model.named_parameters())
    for name, new_param in new_named_params.items():
        if name not in old_named_states:
            continue

        old_state = old_named_states[name]
        new_state = {}
        for k, v in old_state.items():
            if k == "step":
                new_state[k] = v.clone() if isinstance(v, torch.Tensor) else v
            elif not isinstance(v, torch.Tensor):
                new_state[k] = v
            else:
                old_shape = v.shape
                new_shape = new_param.shape
                if old_shape == new_shape:
                    new_state[k] = v.clone()
                else:
                    if len(old_shape) != len(new_shape):
                        logger.warning(
                            "Optimizer recovery shape dimension mismatch for %s: %s vs %s. Skipping.",
                            name, old_shape, new_shape,
                        )
                        continue
                    
                    new_tensor = torch.zeros(new_shape, dtype=v.dtype, device=v.device)
                    slices = tuple(slice(0, min(o_dim, n_dim)) for o_dim, n_dim in zip(old_shape, new_shape))
                    new_tensor[slices] = v[slices]
                    new_state[k] = new_tensor

        new_optimizer.state[new_param] = new_state


def train_npdna(
    config_name: str = "seed",
    max_steps: int = 50,
    lr: float = 2e-3,
    batch_size: int = 1,
    seq_limit: int = 256,
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
    lr_schedule: str = "cosine",
    min_free_ram_gb: float = 1.5,
    bpe_max_words: int = 0,
    balance_weight: float = 0.05,
    plasticity_interval: int | None = None,
    plasticity_overload_threshold: float = 0.14,
    plasticity_dead_threshold: float = 0.01,
    plasticity_grow_cooldown: int = 1,
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
    base_step = 0
    if resume_from:
        logger.info("Resuming from %s", resume_from)
        _write_train_status(output_dir, "loading_checkpoint", resume_from=resume_from)
        core = NpDnaCore.load(resume_from)
        resume_meta_path = Path(resume_from) / "metadata.json"
        if resume_meta_path.exists():
            try:
                resume_meta = json.loads(resume_meta_path.read_text(encoding="utf-8"))
                base_step = int(resume_meta.get("train_step") or resume_meta.get("loss_count") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                base_step = 0
    else:
        logger.info("Creating NP-DNA model [%s]", config_name)
        _write_train_status(output_dir, "creating_model", config=config_name)
        core = NpDnaCore.from_config(config_name)

    _set_mesh_balance_weight(core, balance_weight)

    # Ensure dataset exists
    if not Path(data_path).exists():
        build_seed_dataset(data_path)

    # Load and encode data
    _write_train_status(output_dir, "loading_dataset", data_path=data_path, limit_samples=limit_samples)
    texts = load_dataset(data_path, limit=limit_samples, append_eos=True)

    if bpe_merges > 0:
        memory_status = _memory_rule_status(core, seq_limit, batch_size, min_free_ram_gb)
        if train_device.type == "cpu" and memory_status["available_ram_gb"] < memory_status["required_free_ram_gb"]:
            msg = (
                f"Memory preflight blocked tokenizer training: available "
                f"{memory_status['available_ram_gb']}GB, requires "
                f"{memory_status['required_free_ram_gb']}GB free."
            )
            logger.error(msg)
            _write_train_status(output_dir, "blocked_low_memory", error=msg, **memory_status)
            return core, []
        _write_train_status(
            output_dir,
            "training_tokenizer",
            target_merges=bpe_merges,
            sample_count=len(texts),
            bpe_max_words=bpe_max_words if bpe_max_words > 0 else "all",
        )
        old_size = core.tokenizer.size
        old_token_to_id = dict(core.tokenizer.token_to_id)
        old_capacity = core.tokenizer.capacity
        core.tokenizer.train_bpe(
            texts,
            target_merges=bpe_merges,
            max_words=bpe_max_words,
            progress_callback=lambda tok: _write_train_status(
                output_dir,
                "training_tokenizer",
                target_merges=bpe_merges,
                current_merges=len(tok.merges),
                sample_count=len(texts),
                vocab=tok.size,
                vocab_capacity=tok.capacity,
                bpe_max_words=bpe_max_words if bpe_max_words > 0 else "all",
            ),
        )
        if core.tokenizer.capacity != old_capacity:
            core.model.resize_embeddings(core.tokenizer.capacity)
        _write_train_status(
            output_dir,
            "tokenizer_ready",
            target_merges=bpe_merges,
            current_merges=len(core.tokenizer.merges),
            vocab=core.tokenizer.size,
            vocab_capacity=core.tokenizer.capacity,
        )
        _initialize_new_token_embeddings(core, old_size, old_token_to_id)
        logger.info(
            "Tokenizer warmup complete: %d merges, vocab=%d/%d",
            len(core.tokenizer.merges),
            core.tokenizer.size,
            core.tokenizer.capacity,
        )

    memory_status = _memory_rule_status(core, seq_limit, batch_size, min_free_ram_gb)
    if train_device.type == "cpu" and memory_status["available_ram_gb"] < memory_status["required_free_ram_gb"]:
        msg = (
            f"Memory preflight blocked training: available "
            f"{memory_status['available_ram_gb']}GB, requires "
            f"{memory_status['required_free_ram_gb']}GB free. "
            "Use seed/nano, lower seq_limit, reduce dataset packing, or close other apps."
        )
        logger.error(msg)
        _write_train_status(output_dir, "blocked_low_memory", error=msg, **memory_status)
        return core, []
    _write_train_status(output_dir, "memory_preflight_ok", **memory_status)

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
    def build_optimizer(current_lr: float):
        opt = torch.optim.AdamW(model.parameters(), lr=current_lr, weight_decay=0.01)
        sched = None
        if lr_schedule == "cosine":
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(
                opt,
                T_max=max(1, max_steps),
                eta_min=min(lr, 1e-5),
            )
        return opt, sched

    optimizer, scheduler = build_optimizer(lr)
    loss_fn = nn.CrossEntropyLoss()
    plasticity_check_interval = plasticity_interval or max(10, max_steps // 40)
    plasticity = PlasticityEngine(
        core,
        check_interval=plasticity_check_interval,
        dead_threshold=plasticity_dead_threshold,
        overload_threshold=plasticity_overload_threshold,
        grow_cooldown_checks=plasticity_grow_cooldown,
    )
    use_autocast = bool(bf16 and train_device.type == "cuda")
    if bf16 and not use_autocast:
        logger.info("bfloat16 autocast requested but disabled on %s for stability", train_device.type)

    losses: list[float] = []
    step = 0
    tokens_seen = 0
    stop_reason: str | None = None
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
        step=base_step,
        run_step=0,
        max_steps=base_step + max_steps,
        run_max_steps=max_steps,
        samples=len(encoded),
        device=str(train_device),
        bf16=use_autocast,
        parameter_count=model.parameter_count(),
        active_parameter_count=model.active_parameter_count(),
        balance_weight=balance_weight,
        plasticity_interval=plasticity_check_interval,
        plasticity_overload_threshold=plasticity_overload_threshold,
    )

    # Training loop
    for epoch in range(1, 10001):
        for ids in encoded:
            if step >= max_steps:
                break

            if train_device.type == "cpu":
                memory_status = _memory_rule_status(core, seq_limit, batch_size, min_free_ram_gb)
                if memory_status["available_ram_gb"] < memory_status["required_free_ram_gb"]:
                    stop_reason = (
                        f"Stopped before step {base_step + step + 1}: low RAM headroom "
                        f"({memory_status['available_ram_gb']}GB available, "
                        f"{memory_status['required_free_ram_gb']}GB required)."
                    )
                    logger.warning(stop_reason)
                    _write_train_status(
                        output_dir,
                        "stopping_low_memory",
                        step=base_step + step,
                        run_step=step,
                        **memory_status,
                        warning=stop_reason,
                    )
                    break

            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=train_device)
            labels = torch.tensor([ids[1:]], dtype=torch.long, device=train_device)

            try:
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
                if scheduler is not None:
                    scheduler.step()
            except RuntimeError as exc:
                if not _is_cpu_oom(exc):
                    raise
                optimizer.zero_grad(set_to_none=True)
                gc.collect()
                if train_device.type == "cuda":
                    torch.cuda.empty_cache()
                memory_status = _memory_rule_status(core, seq_limit, batch_size, min_free_ram_gb)
                stop_reason = (
                    f"Stopped after CPU OOM at attempted step {base_step + step + 1}: {exc}"
                )
                logger.error(stop_reason)
                _write_train_status(
                    output_dir,
                    "stopped_oom_saved_latest",
                    step=base_step + step,
                    run_step=step,
                    **memory_status,
                    error=stop_reason,
                )
                break

            loss_val = float(ce_loss.detach())
            balance_loss_val = float(balance_loss.detach())
            losses.append(loss_val)
            plasticity.record_loss(loss_val)

            step += 1
            tokens_seen += max(0, len(ids) - 1)
            if step == 1 or step % max(1, log_every) == 0:
                _write_train_status(
                    output_dir,
                    "training",
                    step=base_step + step,
                    run_step=step,
                    max_steps=base_step + max_steps,
                    run_max_steps=max_steps,
                    loss=loss_val,
                    balance_loss=balance_loss_val,
                    avg_loss=sum(losses[-50:]) / min(len(losses), 50),
                    lr=optimizer.param_groups[0]["lr"],
                    vocab=core.tokenizer.size,
                    vocab_capacity=core.tokenizer.capacity,
                    parameter_count=model.parameter_count(),
                    active_parameter_count=model.active_parameter_count(),
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
            layer_balance_losses = {}
            layer_router_entropies = {}
            for layer_i, mesh in enumerate(model.mesh_layers):
                layer_balance_losses[f"L{layer_i}"] = mesh.last_balance_loss
                layer_router_entropies[f"L{layer_i}"] = mesh.last_router_entropy
                for strand_id, ratio in mesh.usage_stats.items():
                    usage[f"L{layer_i}-S{strand_id}"] = ratio
            avg_router_entropy = (
                sum(layer_router_entropies.values()) / len(layer_router_entropies)
                if layer_router_entropies else 0.0
            )
            with open(metrics_file, "a") as f:
                f.write(json.dumps({
                    "step": base_step + step,
                    "run_step": step,
                    "loss": loss_val,
                    "balance_loss": balance_loss_val,
                    "avg_loss": sum(losses[-50:]) / min(len(losses), 50),
                    "router_entropy": avg_router_entropy,
                    "layer_balance_loss": layer_balance_losses,
                    "layer_router_entropy": layer_router_entropies,
                    "usage": usage,
                    "total_params": model.parameter_count(),
                    "active_params": model.active_parameter_count(),
                    "vocab_size": core.tokenizer.size,
                    "vocab_capacity": core.tokenizer.capacity,
                    "lr": optimizer.param_groups[0]["lr"],
                }) + "\n")

            # Plasticity check
            old_named_states = {}
            if step % plasticity_check_interval == 0:
                old_named_params = dict(model.named_parameters())
                for name, param in old_named_params.items():
                    if param in optimizer.state:
                        state = optimizer.state[param]
                        old_named_states[name] = {
                            k: (v.clone() if isinstance(v, torch.Tensor) else v)
                            for k, v in state.items()
                        }

            events = plasticity.check(step)
            for e in events:
                logger.info("⚡ Plasticity [%s]: %s", e.event_type, e.details)

            if any(e.event_type == "grow_strands" for e in events):
                current_lr = optimizer.param_groups[0]["lr"]
                new_optimizer, new_scheduler = build_optimizer(current_lr)
                restore_optimizer_state(new_optimizer, old_named_states, model)
                if scheduler is not None and new_scheduler is not None:
                    try:
                        new_scheduler.load_state_dict(scheduler.state_dict())
                    except Exception as ex:
                        logger.warning("Failed to restore scheduler state: %s", ex)
                optimizer = new_optimizer
                scheduler = new_scheduler
                logger.info("Optimizer rebuilt and state safely recovered after strand growth (lr=%.2e)", current_lr)

            for e in events:
                if e.event_type == "reinit_strands":
                    try:
                        parts = e.details.split(":")
                        layer_part = parts[0]
                        layer_i = int(layer_part.split()[-1])
                        
                        strands_part = parts[1].split("strands")[-1].strip()
                        dead_ids = json.loads(strands_part)
                        
                        mesh = model.mesh_layers[layer_i]
                        
                        # 1. Clear momentum for router.weight
                        if mesh.router.weight in optimizer.state:
                            router_state = optimizer.state[mesh.router.weight]
                            for k in ["exp_avg", "exp_avg_sq"]:
                                if k in router_state and isinstance(router_state[k], torch.Tensor):
                                    for s_id in dead_ids:
                                        if s_id < router_state[k].shape[0]:
                                            router_state[k][s_id].zero_()
                                            
                        # 2. Clear momentum for genome.seeds
                        if model.genome.seeds in optimizer.state:
                            seeds_state = optimizer.state[model.genome.seeds]
                            for k in ["exp_avg", "exp_avg_sq"]:
                                if k in seeds_state and isinstance(seeds_state[k], torch.Tensor):
                                    for s_id in dead_ids:
                                        global_id = layer_i * mesh.config.num_strands + s_id
                                        if global_id < seeds_state[k].shape[0]:
                                            seeds_state[k][global_id].zero_()
                                            
                        # 3. Clear momentum for strand LayerNorm parameters
                        for s_id in dead_ids:
                            if s_id < len(mesh.strands):
                                strand = mesh.strands[s_id]
                                for p in strand.parameters():
                                    if p in optimizer.state:
                                        param_state = optimizer.state[p]
                                        for k in ["exp_avg", "exp_avg_sq"]:
                                            if k in param_state and isinstance(param_state[k], torch.Tensor):
                                                param_state[k].zero_()
                                                
                        logger.info("Cleared optimizer momentum for reinitialized strands in Layer %d: %s", layer_i, dead_ids)
                    except Exception as ex:
                        logger.warning("Failed to clear optimizer momentum for reinitialized strands: %s", ex)

            # Checkpoint
            if checkpoint_every > 0 and step % checkpoint_every == 0:
                global_step = base_step + step
                ckpt_path = Path(output_dir) / "checkpoints" / f"step_{global_step:06d}"
                core.save(
                    ckpt_path,
                    losses=losses,
                    metadata_extra=_training_metadata(
                        config_name=config_name,
                        data_path=data_path,
                        limit_samples=limit_samples,
                        step=global_step,
                        max_steps=base_step + max_steps,
                        losses=losses,
                        pack_sequences=pack_sequences,
                        bpe_merges=bpe_merges,
                        lr_schedule=lr_schedule,
                        balance_weight=balance_weight,
                        plasticity_interval=plasticity_check_interval,
                        plasticity_overload_threshold=plasticity_overload_threshold,
                    ),
                )
                
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
                    core.save(
                        output_dir,
                        losses=losses,
                        metadata_extra=_training_metadata(
                            config_name=config_name,
                            data_path=data_path,
                            limit_samples=limit_samples,
                            step=global_step,
                            max_steps=base_step + max_steps,
                            losses=losses,
                            pack_sequences=pack_sequences,
                            bpe_merges=bpe_merges,
                            lr_schedule=lr_schedule,
                            balance_weight=balance_weight,
                            plasticity_interval=plasticity_check_interval,
                            plasticity_overload_threshold=plasticity_overload_threshold,
                        ),
                    )
                    logger.info("Checkpoint saved (NEW BEST): %s", ckpt_path)
                else:
                    logger.info("Checkpoint saved: %s", ckpt_path)

            del input_ids, labels, logits, balance_loss, ce_loss, loss
            if step % 50 == 0:
                gc.collect()
                if train_device.type == "cuda":
                    torch.cuda.empty_cache()

        if stop_reason:
            break
        if step >= max_steps:
            break

    # Save final model
    elapsed = time.time() - start_time
    logger.info("Training complete: %d steps in %.1fs", step, elapsed)
    _write_train_status(
        output_dir,
        "complete",
        step=base_step + step,
        run_step=step,
        max_steps=base_step + max_steps,
        run_max_steps=max_steps,
        elapsed=elapsed,
        final_loss=losses[-1] if losses else None,
        warning=stop_reason,
    )

    # Save the final model as "latest". Best historical checkpoints remain in
    # outputs/npdna/checkpoints for resume comparisons.
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
    core.save(
        output_dir,
        losses=losses,
        metadata_extra=_training_metadata(
            config_name=config_name,
            data_path=data_path,
            limit_samples=limit_samples,
            step=base_step + step,
            max_steps=base_step + max_steps,
            losses=losses,
            pack_sequences=pack_sequences,
            bpe_merges=bpe_merges,
            lr_schedule=lr_schedule,
            balance_weight=balance_weight,
            plasticity_interval=plasticity_check_interval,
            plasticity_overload_threshold=plasticity_overload_threshold,
        ),
    )
    logger.info(
        "Final model saved to %s (Best Loss: %.4f, previous checkpoint best: %.4f)",
        output_dir,
        final_min,
        best_loss_so_far,
    )

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
    device: str = "auto",
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
        device: Device to train on.

    Returns:
        Updated NpDnaCore.
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("Chunk training: topic=%s, strand=%s, steps=%d, device=%s", topic, strand_id, steps, device)

    train_device = _select_device(device)

    core = NpDnaCore.load(model_path)
    model = core.model
    model.to(train_device)

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
            input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=train_device)
            labels = torch.tensor([ids[1:]], dtype=torch.long, device=train_device)

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

    model.to("cpu")
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
    parser.add_argument("--seq-limit", type=int, default=256, help="Maximum sequence length per sample")
    parser.add_argument("--lr-schedule", choices=["none", "cosine"], default="cosine", help="Learning rate schedule")
    parser.add_argument(
        "--min-free-ram-gb",
        type=float,
        default=1.5,
        help="CPU training safety rule: stop/save before free RAM drops below this many GB",
    )
    parser.add_argument("--bpe-max-words", type=int, default=0, help="Maximum unique words used for BPE pair counting; 0 means all")
    parser.add_argument("--balance-weight", type=float, default=0.05, help="Router load-balance loss weight")
    parser.add_argument("--plasticity-interval", type=int, default=0, help="Plasticity check interval; 0 auto-scales from steps")
    parser.add_argument("--plasticity-overload-threshold", type=float, default=0.14, help="Strand usage ratio that counts as overloaded")
    parser.add_argument("--plasticity-dead-threshold", type=float, default=0.01, help="Strand usage ratio that counts as dead")
    parser.add_argument("--plasticity-grow-cooldown", type=int, default=1, help="Plasticity checks to wait before growing strands again")

    args = parser.parse_args()
    try:
        train_npdna(
            config_name=args.config,
            max_steps=args.steps,
            lr=args.lr,
            seq_limit=args.seq_limit,
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
            lr_schedule=args.lr_schedule,
        min_free_ram_gb=args.min_free_ram_gb,
        bpe_max_words=args.bpe_max_words,
        balance_weight=args.balance_weight,
        plasticity_interval=args.plasticity_interval or None,
        plasticity_overload_threshold=args.plasticity_overload_threshold,
        plasticity_dead_threshold=args.plasticity_dead_threshold,
        plasticity_grow_cooldown=args.plasticity_grow_cooldown,
    )
    except Exception as exc:
        _write_train_status(args.output, "error", error=str(exc))
        raise
