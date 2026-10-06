"""Try a bigger model on this computer: download it into examples/models/, measure it, and (optionally) make Atulya use it.

    python examples/try_model.py --list              # what is available and what fits your free memory
    python examples/try_model.py                     # try the biggest model that fits (asks before downloading)
    python examples/try_model.py --model 4b          # download (once) and measure the 4B model
    python examples/try_model.py --model 4b --chat   # then talk to it, to feel the speed and quality
    python examples/try_model.py --model 4b --use    # make Atulya use it (writes ATULYA_GGUF_PATH to .env)

Needs:  pip install -e ".[brain]"   (llama-cpp-python)   and   pip install huggingface_hub
Nothing here changes Atulya unless you pass --use. Models are public Qwen3 files from Hugging Face (about 0.4 to 9 GB).
Results are appended to examples/results.md so you can compare models side by side.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MODELS_DIR = HERE / "models"
RESULTS = HERE / "results.md"

# key -> (Hugging Face repo, file, download GB). RAM needed is estimated as download size x 1.3 + 1 GB.
MODELS: dict[str, tuple[str, str, float]] = {
    "0.6b": ("unsloth/Qwen3-0.6B-GGUF", "Qwen3-0.6B-Q4_K_M.gguf", 0.4),
    "1.7b": ("unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf", 1.1),
    "4b": ("unsloth/Qwen3-4B-GGUF", "Qwen3-4B-Q4_K_M.gguf", 2.5),
    "8b": ("unsloth/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", 5.0),
    "14b": ("unsloth/Qwen3-14B-GGUF", "Qwen3-14B-Q4_K_M.gguf", 9.0),
}

PROMPTS = [
    ("English, money", "In two sentences: why does a monthly budget help?"),
    ("Hindi", "मुझे अपने महीने के खर्च को कम करने के तीन आसान तरीके बताओ।"),
    ("Tool call (JSON only)",
     'Reply with ONLY a JSON object like {"tool": "device_do", "arguments": {"device": "...", "action": "..."}} '
     "to turn off the living room TV. Valid actions: power_on, power_off, mute, volume_up."),
]


def ram_needed(key: str) -> float:
    return round(MODELS[key][2] * 1.3 + 1.0, 1)


def free_ram_gb() -> float:
    try:
        import psutil

        return psutil.virtual_memory().available / 1024**3
    except Exception:  # noqa: BLE001 - fall back to /proc on minimal installs
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) / 1024**2
        except OSError:
            pass
    return 4.0


def recommend(free_gb: float) -> str:
    """The biggest model that leaves a safety margin (it must fit in 75% of the free memory)."""
    fitting = [k for k in MODELS if ram_needed(k) <= free_gb * 0.75]
    return fitting[-1] if fitting else "0.6b"


def model_path(key: str, base: Path = MODELS_DIR) -> Path:
    return base / MODELS[key][1]


def download(key: str, base: Path = MODELS_DIR) -> Path:
    path = model_path(key, base)
    if path.exists():
        return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        sys.exit("Install the downloader first:  pip install huggingface_hub")
    base.mkdir(parents=True, exist_ok=True)
    repo, file, gb = MODELS[key]
    print(f"Downloading {file} (about {gb} GB) into {base} ...", flush=True)
    return Path(hf_hub_download(repo, file, local_dir=str(base)))


def clean_answer(text: str) -> str:
    """Qwen3 can think out loud in <think>...</think>; show only the answer."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def is_tool_json(text: str) -> bool:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and isinstance(data.get("tool"), str) and isinstance(data.get("arguments"), dict)


def load(path: Path, n_ctx: int = 2048):
    try:
        from llama_cpp import Llama
    except ImportError:
        sys.exit('Install the local brain first:  pip install -e ".[brain]"   (or: pip install llama-cpp-python)')
    return Llama(model_path=str(path), n_ctx=n_ctx, n_threads=os.cpu_count() or 4, verbose=False)


def ask(llm: Any, prompt: str, max_tokens: int = 160) -> dict[str, Any]:
    """One streamed answer, with time to first word and words-per-second (tokens counted from the stream)."""
    started = time.perf_counter()
    first = None
    chunks: list[str] = []
    for part in llm.create_chat_completion(messages=[{"role": "user", "content": prompt + " /no_think"}],
                                           max_tokens=max_tokens, temperature=0.3, stream=True):
        piece = part["choices"][0]["delta"].get("content") or ""
        if piece:
            first = first or time.perf_counter()
            chunks.append(piece)
    end = time.perf_counter()
    first = first or end
    tokens = len(chunks)
    return {"text": clean_answer("".join(chunks)), "first_s": round(first - started, 2), "tokens": tokens,
            "tok_per_s": round(tokens / max(end - first, 1e-6), 1) if tokens > 1 else 0.0}


def benchmark(path: Path, prompts=PROMPTS, max_tokens: int = 160) -> dict[str, Any]:
    t0 = time.perf_counter()
    llm = load(path)
    load_s = round(time.perf_counter() - t0, 1)
    runs = []
    for label, prompt in prompts:
        r = ask(llm, prompt, max_tokens)
        r["label"] = label
        r["ok"] = is_tool_json(r["text"]) if label.startswith("Tool") else bool(r["text"])
        runs.append(r)
    speed = [r["tok_per_s"] for r in runs if r["tok_per_s"]]
    return {"load_s": load_s, "runs": runs, "avg_tok_per_s": round(sum(speed) / len(speed), 1) if speed else 0.0}


def results_row(key: str, result: dict[str, Any]) -> str:
    tool = next((r for r in result["runs"] if r["label"].startswith("Tool")), None)
    return (f"| {key} | {result['load_s']} s | {result['avg_tok_per_s']} | "
            f"{round(sum(r['first_s'] for r in result['runs']) / len(result['runs']), 1)} s | "
            f"{'yes' if tool and tool['ok'] else 'no'} | {time.strftime('%Y-%m-%d')} |")


def append_results(key: str, result: dict[str, Any], path: Path = RESULTS) -> None:
    header = ("# Model results on this computer\n\n| model | load | words/sec | first word | clean JSON tool call | date |\n|---|---|---|---|---|---|\n")
    text = path.read_text(encoding="utf-8") if path.exists() else header
    path.write_text(text.rstrip("\n") + "\n" + results_row(key, result) + "\n", encoding="utf-8")


def use_in_atulya(key: str, path: Path, env_file: Path | None = None) -> None:
    """Point Atulya's local brain at this file (kept in .env, so it survives restarts)."""
    sys.path.insert(0, str(HERE.parent))
    from atulya.settings import set_env_value

    env = env_file or HERE.parent / ".env"
    set_env_value("ATULYA_GGUF_PATH", str(path.resolve()), env)
    set_env_value("ATULYA_LOCAL_MODEL_NAME", f"Qwen3-{key.upper()}", env)
    print(f"Done: Atulya will use {path.name}. Restart start.bat. (Undo: delete the ATULYA_GGUF_PATH line in .env.)")


def show_list() -> None:
    free = free_ram_gb()
    print(f"Free memory now: {free:.1f} GB. Recommended for this computer: {recommend(free)}\n")
    for key, (_repo, file, gb) in MODELS.items():
        have = "downloaded" if model_path(key).exists() else f"download {gb} GB"
        fit = "fits" if ram_needed(key) <= free * 0.75 else "too big for free memory"
        print(f"  {key:5s} {file:28s} needs ~{ram_needed(key):>4} GB   {have:16s} {fit}")


def chat(path: Path) -> None:
    llm = load(path, n_ctx=4096)
    print("Talking to the model. Empty line to stop.\n")
    while (line := input("you> ").strip()):
        r = ask(llm, line, 300)
        print(f"{r['text']}\n   [{r['first_s']} s to first word, {r['tok_per_s']} words/s]\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=list(MODELS), help="which model to try (default: the biggest that fits)")
    ap.add_argument("--list", action="store_true", help="show the models and what fits your memory")
    ap.add_argument("--chat", action="store_true", help="talk to it after the benchmark")
    ap.add_argument("--use", action="store_true", help="make Atulya use this model")
    ap.add_argument("--yes", action="store_true", help="do not ask before downloading")
    ap.add_argument("--max-tokens", type=int, default=160)
    args = ap.parse_args(argv)
    if args.list:
        show_list()
        return 0
    key = args.model or recommend(free_ram_gb())
    if ram_needed(key) > free_ram_gb():
        print(f"Warning: {key} needs about {ram_needed(key)} GB and only {free_ram_gb():.1f} GB is free. It may be very slow or fail.")
    if not model_path(key).exists() and not args.yes:
        if input(f"Download {MODELS[key][1]} (about {MODELS[key][2]} GB)? [y/N] ").strip().lower() != "y":
            return 1
    path = download(key)
    print(f"\nMeasuring {key} on this computer ...", flush=True)
    result = benchmark(path, max_tokens=args.max_tokens)
    for r in result["runs"]:
        print(f"\n[{r['label']}]  first word {r['first_s']} s, {r['tok_per_s']} words/s, {'OK' if r['ok'] else 'NOT OK'}\n{r['text'][:400]}")
    print(f"\nLoad {result['load_s']} s. Average {result['avg_tok_per_s']} words/s.")
    append_results(key, result)
    print(f"Saved to {RESULTS}")
    if args.use:
        use_in_atulya(key, path)
    if args.chat:
        chat(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
