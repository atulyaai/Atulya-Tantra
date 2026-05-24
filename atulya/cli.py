"""Atulya Tantra CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        prog="atulya",
        description="Atulya Tantra â€” NP-DNA NeuroPlastic DNA Network",
    )
    sub = parser.add_subparsers(dest="command")

    # --- info ---
    sub.add_parser("info", help="Show model info for a config")
    # --- train ---
    train_p = sub.add_parser("train", help="Train an NP-DNA model")
    train_p.add_argument(
        "--config",
        default="atulya_seed",
        help="Config name: atulya_seed/atulya_small/atulya_medium/atulya_large",
    )
    train_p.add_argument("--steps", type=int, default=50, help="Training steps")
    train_p.add_argument("--lr", type=float, default=2e-3, help="Learning rate")
    train_p.add_argument("--output", default="outputs/npdna", help="Output directory")
    train_p.add_argument("--data", default="data/seed_dataset.jsonl", help="JSONL dataset path")
    train_p.add_argument("--log-every", type=int, default=10, help="Log interval")
    train_p.add_argument("--checkpoint-every", type=int, default=0, help="Checkpoint interval")
    train_p.add_argument("--resume", default=None, help="Resume from a checkpoint/model directory")
    train_p.add_argument("--limit", type=int, default=None, help="Limit training samples")
    train_p.add_argument("--seq-limit", type=int, default=256, help="Maximum sequence length")
    train_p.add_argument("--bpe-merges", type=int, default=0, help="Train tokenizer BPE merges first")
    train_p.add_argument("--pack", action="store_true", help="Pack short samples into longer sequences")
    train_p.add_argument("--device", default="auto", help="Training device: auto/cpu/cuda")
    train_p.add_argument(
        "--min-free-ram-gb",
        type=float,
        default=1.5,
        help="Stop and save before CPU free RAM drops below this many GB",
    )
    train_p.add_argument("--bpe-max-words", type=int, default=0, help="Maximum unique words used for BPE pair counting; 0 means all")
    train_p.add_argument("--bf16", action="store_true", help="Use bfloat16 autocast")
    train_p.add_argument("--lr-schedule", choices=["none", "cosine"], default="cosine", help="Learning rate schedule")
    train_p.add_argument("--balance-weight", type=float, default=0.05, help="Router load-balance loss weight")
    train_p.add_argument("--plasticity-interval", type=int, default=0, help="Plasticity check interval; 0 auto-scales")
    train_p.add_argument("--plasticity-overload-threshold", type=float, default=0.14, help="Strand overload threshold")
    train_p.add_argument("--plasticity-dead-threshold", type=float, default=0.01, help="Strand dead threshold")
    train_p.add_argument("--plasticity-grow-cooldown", type=int, default=1, help="Plasticity grow cooldown checks")
    # --- generate ---
    gen_p = sub.add_parser("generate", help="Generate text from a saved model")
    gen_p.add_argument("--model", required=True, help="Path to saved model")
    gen_p.add_argument("--prompt", default="Hello", help="Prompt text")
    gen_p.add_argument("--tokens", type=int, default=50, help="Max tokens")

    args = parser.parse_args()

    if args.command == "info":
        _cmd_info()
    elif args.command == "train":
        _cmd_train(args)
    elif args.command == "generate":
        _cmd_generate(args)
    else:
        parser.print_help()


def _cmd_info() -> None:
    from tantra.npdna import CONFIGS, NpDnaModel
    from tantra.npdna.config import PREFERRED_CONFIG_NAMES

    print("\n  Atulya Tantra â€” NP-DNA Scaling Configs\n")
    print(f"  {'Name':<14} {'Total':>12} {'Active':>12} {'Layers':>7} {'Strands':>8} {'Top-k':>6} {'Vocab':>8}")
    print("  " + "-" * 74)
    for name in PREFERRED_CONFIG_NAMES:
        cfg = CONFIGS[name]
        model = NpDnaModel(cfg)
        total = model.parameter_count()
        active = model.active_parameter_count()
        top_k = max((spec.top_k for spec in cfg.mesh_specs), default=cfg.mesh.top_k)
        print(
            f"  {name:<14} {total:>12,} {active:>12,} {cfg.num_layers:>7} "
            f"{cfg.total_strands:>8} {top_k:>6} {cfg.initial_vocab:>8}"
        )
    print()


def _cmd_train(args: argparse.Namespace) -> None:
    # Import here to avoid slow torch import on --help
    from tantra.training.npdna_train import train_npdna

    train_npdna(
        config_name=args.config,
        max_steps=args.steps,
        lr=args.lr,
        output_dir=args.output,
        data_path=args.data,
        log_every=args.log_every,
        checkpoint_every=args.checkpoint_every,
        resume_from=args.resume,
        pack_sequences=args.pack,
        limit_samples=args.limit,
        device=args.device,
        bpe_merges=args.bpe_merges,
        seq_limit=args.seq_limit,
        min_free_ram_gb=args.min_free_ram_gb,
        bpe_max_words=args.bpe_max_words,
        bf16=args.bf16,
        lr_schedule=args.lr_schedule,
        balance_weight=args.balance_weight,
        plasticity_interval=args.plasticity_interval or None,
        plasticity_overload_threshold=args.plasticity_overload_threshold,
        plasticity_dead_threshold=args.plasticity_dead_threshold,
        plasticity_grow_cooldown=args.plasticity_grow_cooldown,
    )


def _cmd_generate(args: argparse.Namespace) -> None:
    from tantra.npdna import NpDnaCore

    core = NpDnaCore.load(args.model)
    print(f"\nPrompt: {args.prompt}")
    result = core.generate(args.prompt, max_tokens=args.tokens)
    print(f"Output: {result}\n")


if __name__ == "__main__":
    main()

