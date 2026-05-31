"""Atulya Tantra CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


FREE_DEFAULTS = {
    "ATULYA_PROVIDER_MODE": "free-first",
    "ATULYA_OLLAMA_HOST": "http://localhost:11434",
    "ATULYA_OLLAMA_MODEL": "llama3",
    "ATULYA_GROQ_MODEL": "llama-3.3-70b-versatile",
    "ATULYA_OPENROUTER_MODEL": "openrouter/free",
    "ATULYA_PREFER_TANTRA": "0",
    "ATULYA_GEMINI_MODEL": "gemini-1.5-flash",
    "ATULYA_TELEGRAM_ALLOWLIST": "",
}


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
        description="Atulya Tantra - free-first Jarvis/NP-DNA assistant",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show model info for a config")

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

    gen_p = sub.add_parser("generate", help="Generate text from a saved model")
    gen_p.add_argument("--model", required=True, help="Path to saved model")
    gen_p.add_argument("--prompt", default="Hello", help="Prompt text")
    gen_p.add_argument("--tokens", type=int, default=50, help="Max tokens")

    chat_p = sub.add_parser("chat", help="Start the free-first Atulya chat REPL")
    chat_p.add_argument("--no-tools", action="store_true", help="Disable tool calls")
    chat_p.add_argument("--allow-exec", action="store_true", help="Allow explicitly allow-listed exec tool calls")
    chat_p.add_argument("--session", default="default", help="Session name to persist chat history")
    chat_p.add_argument("--no-session", action="store_true", help="Do not load or save chat history")
    chat_p.add_argument("--history-limit", type=int, default=50, help="Maximum saved messages per session")

    run_p = sub.add_parser("run", help="Run one agent task and print the result")
    run_p.add_argument("task", help="Task text to execute")
    run_p.add_argument("--no-tools", action="store_true", help="Disable tool calls")
    run_p.add_argument("--allow-exec", action="store_true", help="Allow explicitly allow-listed exec tool calls")
    run_p.add_argument("--session", default="default", help="Session name to include in context")
    run_p.add_argument("--no-session", action="store_true", help="Do not load or save chat history")
    run_p.add_argument("--history-limit", type=int, default=50, help="Maximum saved messages per session")

    sub.add_parser("providers", help="Show provider priority and availability")
    sub.add_parser("doctor", help="Show provider, tool, and data-dir status")
    sub.add_parser("readiness", help="Check production deployment readiness")
    sub.add_parser("tools", help="List installed Yantra tools")

    setup_p = sub.add_parser("setup", help="Write safe local configuration defaults")
    setup_p.add_argument("--free", action="store_true", help="Configure free-first local/free-tier defaults")
    setup_p.add_argument("--env", default=".env", help="Env file to update")

    args = parser.parse_args()

    if args.command:
        _banner()

    if args.command == "info":
        _cmd_info()
    elif args.command == "train":
        _cmd_train(args)
    elif args.command == "generate":
        _cmd_generate(args)
    elif args.command == "chat":
        asyncio.run(_cmd_chat(args))
    elif args.command == "run":
        asyncio.run(_cmd_run(args))
    elif args.command == "providers":
        _cmd_providers()
    elif args.command == "doctor":
        _cmd_doctor()
    elif args.command == "readiness":
        _cmd_readiness()
    elif args.command == "tools":
        _cmd_tools()
    elif args.command == "setup":
        _cmd_setup(args)
    else:
        parser.print_help()


def _banner() -> None:
    print("\nAtulya Tantra | free-first Jarvis stack\n")


def _print_table(headers: list[str], rows: Iterable[Iterable[object]]) -> None:
    materialized = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in materialized:
        for idx, cell in enumerate(row):
            if idx < len(widths):
                widths[idx] = max(widths[idx], len(cell))
            else:
                widths.append(len(cell))
    line = "  " + "  ".join("-" * width for width in widths)
    print("  " + "  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    print(line)
    for row in materialized:
        cells = []
        for idx, cell in enumerate(row):
            w = widths[idx] if idx < len(widths) else len(cell)
            cells.append(cell.ljust(w))
        print("  " + "  ".join(cells))
    print()


def _session_dir() -> Path:
    configured = os.environ.get("ATULYA_CLI_SESSION_DIR") or os.environ.get("ATULYA_DATA_DIR")
    if configured:
        return Path(configured) / "sessions"
    return Path(os.environ.get("TEMP", os.environ.get("TMP", str(Path.home())))) / "atulya" / "sessions"


def _safe_session_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name.strip())
    return safe or "default"


def _session_path(name: str) -> Path:
    return _session_dir() / f"{_safe_session_name(name)}.json"


def _load_session(name: str) -> list[dict[str, str]]:
    path = _session_path(name)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    history: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("role"), str) and isinstance(item.get("content"), str):
            history.append({"role": item["role"], "content": item["content"]})
    return history


def _save_session(name: str, history: list[dict[str, str]], limit: int = 50) -> Path:
    path = _session_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = history[-max(limit, 2):]
    path.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _spinner(label: str, stop: threading.Event) -> None:
    frames = "|/-\\"
    idx = 0
    while not stop.is_set():
        print(f"\r{label} {frames[idx % len(frames)]}", end="", flush=True)
        idx += 1
        time.sleep(0.12)
    print("\r" + " " * (len(label) + 4) + "\r", end="", flush=True)


class _Spin:
    def __init__(self, label: str):
        self.label = label
        self.stop = threading.Event()
        self.thread = threading.Thread(target=_spinner, args=(label, self.stop), daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop.set()
        self.thread.join(timeout=1.0)


def _merge_env_defaults(path: Path, defaults: dict[str, str]) -> dict[str, str]:
    existing: dict[str, str] = {}
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            existing[key.strip()] = value

    changed: dict[str, str] = {}
    additions: list[str] = []
    for key, value in defaults.items():
        if key not in existing:
            additions.append(f"{key}={value}")
            changed[key] = value

    if additions:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines).rstrip()
        if content:
            content += "\n\n"
        content += "# Atulya free-first defaults\n" + "\n".join(additions) + "\n"
        path.write_text(content, encoding="utf-8")
    return changed


def _cmd_info() -> None:
    from tantra.npdna import CONFIGS, NpDnaModel
    from tantra.npdna.config import PREFERRED_CONFIG_NAMES

    rows = []
    for name in PREFERRED_CONFIG_NAMES:
        cfg = CONFIGS[name]
        model = NpDnaModel(cfg)
        total = model.parameter_count()
        active = model.active_parameter_count()
        top_k = max((spec.top_k for spec in cfg.mesh_specs), default=cfg.mesh.top_k)
        rows.append([name, f"{total:,}", f"{active:,}", cfg.num_layers, cfg.total_strands, top_k, cfg.initial_vocab])
    _print_table(["Name", "Total", "Active", "Layers", "Strands", "Top-k", "Vocab"], rows)


def _cmd_train(args: argparse.Namespace) -> None:
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


async def _cmd_run(args: argparse.Namespace) -> None:
    from atulya.llm import AtulyaLLM

    llm = AtulyaLLM(allow_exec=args.allow_exec)
    history = [] if args.no_session else _load_session(args.session)
    with _Spin("Thinking"):
        response = await llm.ask(args.task, history=history, tools_enabled=not args.no_tools)
    if response.tool_steps:
        print("\nTool steps:")
        for step in response.tool_steps:
            status = "ok" if step["success"] else "failed"
            print(f"  - {step['tool']} [{status}]")
    print(f"\n[{response.provider}]\n{response.text}\n")
    if not args.no_session:
        history.extend([
            {"role": "user", "content": args.task},
            {"role": "assistant", "content": response.text},
        ])
        path = _save_session(args.session, history, args.history_limit)
        print(f"Session saved: {path}\n")


async def _cmd_chat(args: argparse.Namespace) -> None:
    from atulya.llm import AtulyaLLM

    llm = AtulyaLLM(allow_exec=args.allow_exec)
    history = [] if args.no_session else _load_session(args.session)
    if args.no_session:
        print("Atulya chat online. Type 'exit' or 'quit' to leave.\n")
    else:
        print(f"Atulya chat online. Session '{args.session}' loaded with {len(history)} messages.")
        print("Type 'exit' or 'quit' to leave.\n")
    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", "/exit", "/quit"}:
            break
        print("atulya> ", end="", flush=True)
        chunks: list[str] = []
        provider = ""
        async for event in llm.stream(prompt, history=history, tools_enabled=not args.no_tools):
            if event.type == "tool":
                tool = event.metadata.get("tool", "tool")
                print(f"\n[tool] {tool}\natulya> ", end="", flush=True)
            elif event.type == "token":
                chunks.append(event.content)
                print(event.content, end="", flush=True)
            elif event.type == "done":
                provider = event.metadata.get("provider", "")
        answer = "".join(chunks).strip()
        print(f"\n[{provider}]\n")
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": answer})
        if not args.no_session:
            _save_session(args.session, history, args.history_limit)


def _cmd_providers() -> None:
    from atulya.intelligence import ProviderRouter

    router = ProviderRouter()
    rows = []
    for index, provider in enumerate(router.providers, start=1):
        try:
            available = provider.is_available()
        except Exception as exc:
            rows.append([index, provider.name(), "error", str(exc)[:80]])
            continue
        rows.append([index, provider.name(), "yes" if available else "no", ""])
    _print_table(["Priority", "Provider", "Available", "Note"], rows)


def _cmd_tools() -> None:
    from yantra.capabilities import create_default_registry

    registry = create_default_registry()
    tools = registry.list_tools()
    _print_table(["Tool", "Description"], [[tool["name"], tool["description"]] for tool in tools])


def _cmd_doctor() -> None:
    print(f"Workspace: {_ROOT}")
    print(f"Session dir: {_session_dir()}")
    print(f"ATULYA_DATA_DIR: {os.environ.get('ATULYA_DATA_DIR', '(default)')}\n")
    _cmd_providers()
    _cmd_tools()


def _cmd_readiness() -> None:
    from atulya.production_readiness import run_readiness_checks

    report = run_readiness_checks(_ROOT)
    print(f"Grade: {report['grade']}")
    print(f"Required checks: {report['passed_required']}/{report['total_required']}\n")
    rows = [
        [item["name"], item["status"], "yes" if item["required"] else "no", item["detail"]]
        for item in report["checks"]
    ]
    _print_table(["Check", "Status", "Required", "Detail"], rows)


def _cmd_setup(args: argparse.Namespace) -> None:
    if not args.free:
        print("Use: atulya setup --free")
        return
    env_path = Path(args.env)
    try:
        changed = _merge_env_defaults(env_path, FREE_DEFAULTS)
    except PermissionError as exc:
        print(f"Could not update {env_path}: {exc}")
        print("Run the command from a writable project directory, or choose --env inside a writable folder.\n")
        return
    if changed:
        _print_table(["Added", "Value"], changed.items())
    else:
        print(f"{env_path} already has the free-first defaults.\n")
    print(f"Configured free-first defaults in {env_path} without writing API keys.\n")


if __name__ == "__main__":
    main()
