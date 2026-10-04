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
    "ATULYA_GEMINI_MODEL": "gemini-1.5-flash",
    "ATULYA_TELEGRAM_ALLOWLIST": "",
    "ATULYA_AUTO_DOWNLOAD_MODEL": "1",
    "ATULYA_LOCAL_MODEL_CONTEXT": "4096",
    "ATULYA_LOCAL_MAX_TOKENS": "512",
    "ATULYA_LOCAL_TEMPERATURE": "0.7",
}


def main() -> None:
    from atulya.envfile import load_env

    load_env()
    if len(sys.argv) > 1 and sys.argv[1] == "listen":  # the always-listening app has its own options
        from atulya.ambient.cli import main as listen

        raise SystemExit(listen(sys.argv[2:]))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        prog="atulya",
        description="Atulya Tantra - free-first Atulya assistant",
    )
    sub = parser.add_subparsers(dest="command")

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
    sub.add_parser("listen", help="Always-listening Atulya with a wake word (see: atulya listen --help)")

    model_p = sub.add_parser("model", help="Manage the local placeholder model (0.5B GGUF)")
    model_sub = model_p.add_subparsers(dest="model_command")
    model_sub.add_parser("download", help="Download the 0.5B model (~350 MB)")
    model_sub.add_parser("status", help="Show model download status and path")
    model_sub.add_parser("remove", help="Remove downloaded model")

    setup_p = sub.add_parser("setup", help="Write safe local configuration defaults")
    setup_p.add_argument("--free", action="store_true", help="Configure free-first local/free-tier defaults")
    setup_p.add_argument("--env", default=".env", help="Env file to update")

    args = parser.parse_args()

    if args.command:
        _banner()
    if args.command == "chat":
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
    elif args.command == "model":
        _cmd_model(args)
    elif args.command == "setup":
        _cmd_setup(args)
    else:
        parser.print_help()


def _banner() -> None:
    print("\nAtulya Tantra | free-first Atulya Agent stack\n")


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
    from atulya.capabilities import create_default_registry

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


def _cmd_model(args: argparse.Namespace) -> None:
    from atulya.cognition.brain import local_model_spec
    from atulya.local_provider import _resolve_model_path, _DEFAULT_MODEL_DIR

    subcmd = getattr(args, "model_command", None)

    if subcmd == "download":
        spec = local_model_spec()  # follows ATULYA_BRAIN (tiny / balanced / power)
        print(f"Downloading the '{spec['tier']}' brain: {spec['label']} ({spec['size']})...")
        model_dir = _DEFAULT_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / spec["file"]
        if model_path.exists():
            print(f"Model already exists at {model_path} ({model_path.stat().st_size / 1024 / 1024:.0f} MB)")
            return
        try:
            import urllib.request
            print(f"Fetching from {spec['url']}...")
            urllib.request.urlretrieve(spec["url"], str(model_path))
            size_mb = model_path.stat().st_size / 1024 / 1024
            print(f"Downloaded: {model_path} ({size_mb:.0f} MB)")
            print("Model ready. Run 'atulya chat' to use it.")
        except Exception as exc:
            print(f"Download failed: {exc}")
            if model_path.exists():
                model_path.unlink()

    elif subcmd == "status":
        path = _resolve_model_path()
        if path:
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"Model found: {path}")
            print(f"Size: {size_mb:.0f} MB")
            print(f"Auto-download: {os.environ.get('ATULYA_AUTO_DOWNLOAD_MODEL', '0')}")
        else:
            print("Model not downloaded.")
            print(f"Expected at: {_DEFAULT_MODEL_DIR / local_model_spec()['file']}")
            print("Run: atulya model download")

    elif subcmd == "remove":
        path = _resolve_model_path()
        if path and path.exists():
            path.unlink()
            print(f"Removed: {path}")
        else:
            print("No model to remove.")

    else:
        print("Usage: atulya model {download|status|remove}")


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
