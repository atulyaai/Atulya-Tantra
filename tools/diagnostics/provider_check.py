"""Measure configured cloud providers and the local Qwen endpoint safely.

Run from any directory with ``python tools/diagnostics/provider_check.py``.
Paid OpenRouter testing is opt-in via ``--include-paid``; this keeps ordinary
diagnostics from making billable requests unexpectedly.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

from tools.plugins.brain import Message, OpenAICompatibleProvider  # noqa: E402


_CLOUD = (
    ("NVIDIA", "NVIDIA_API_KEY", "ATULYA_NVIDIA_MODEL", "https://integrate.api.nvidia.com/v1"),
    ("Gemini", "GEMINI_API_KEY", "ATULYA_GEMINI_MODEL", "https://generativelanguage.googleapis.com/v1beta/openai"),
    ("OpenRouter", "OPENROUTER_API_KEY", "ATULYA_OPENROUTER_MODEL", "https://openrouter.ai/api/v1"),
    ("DeepSeek", "DEEPSEEK_API_KEY", "ATULYA_DEEPSEEK_MODEL", "https://api.deepseek.com/v1"),
)
_PROBE = [Message(role="user", content="Reply with exactly one word: OK")]


async def _measure(label: str, provider: OpenAICompatibleProvider) -> bool:
    started = time.perf_counter()
    try:
        await provider.complete(_PROBE)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        detail = f"HTTP {status}" if status else type(exc).__name__
        print(f"{label} | {provider.model} | failed ({detail})")
        return False
    print(f"{label} | {provider.model} | {time.perf_counter() - started:.2f}s | OK")
    return True


async def _run(include_paid: bool, include_local: bool) -> None:
    for label, key_name, model_name, base_url in _CLOUD:
        keys = [item.strip() for item in os.environ.get(key_name, "").split(",") if item.strip()]
        models = [item.strip() for item in os.environ.get(model_name, "").split(",") if item.strip()]
        if not keys or not models:
            print(f"{label} | not configured")
            continue
        # One short probe per provider uses only the first configured key/model.
        await _measure(label, OpenAICompatibleProvider(
            name=label, model=models[0], base_url=base_url, api_key=keys[0], timeout_seconds=20, max_tokens=4,
        ))

    if include_paid:
        keys = [item.strip() for item in os.environ.get("OPENROUTER_API_KEY", "").split(",") if item.strip()]
        paid_model = os.environ.get("ATULYA_OPENROUTER_PAID_MODEL", "").strip()
        if not paid_model:
            openai_model = os.environ.get("ATULYA_OPENAI_MODEL", "").strip()
            paid_model = f"openai/{openai_model}" if openai_model and "/" not in openai_model else openai_model
        if not keys or not paid_model:
            print("OpenRouter paid | not configured; set ATULYA_OPENROUTER_PAID_MODEL to opt in")
        else:
            print("OpenRouter paid | trying keys in order; stop after the first success")
            for index, key in enumerate(keys, 1):
                success = await _measure(f"OpenRouter paid key {index}", OpenAICompatibleProvider(
                    name="OpenRouter paid", model=paid_model, base_url="https://openrouter.ai/api/v1",
                    api_key=key, timeout_seconds=30, max_tokens=4,
                ))
                if success:
                    break

    if include_local:
        from tools.plugins.brain.local_llm import LocalLlamaRuntime
        from atulya.settings import Settings

        settings = Settings.from_environment()
        runtime = LocalLlamaRuntime(settings.models_dir)
        started = time.perf_counter()
        try:
            runtime.start()
            print(f"Local Qwen startup | {time.perf_counter() - started:.2f}s | ready")
            await _measure("Local Qwen chat", OpenAICompatibleProvider(
                name="Local Qwen", model="qwen3.5-2b", base_url="http://127.0.0.1:11435/v1",
                timeout_seconds=120, max_tokens=4,
            ))
        except Exception as exc:
            print(f"Local Qwen | failed ({type(exc).__name__})")
        finally:
            runtime.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run short provider and local-model response checks.")
    parser.add_argument("--include-paid", action="store_true", help="send one short billable OpenRouter request")
    parser.add_argument("--include-local", action="store_true", help="start local Qwen if needed, probe, then stop it")
    args = parser.parse_args()
    asyncio.run(_run(args.include_paid, args.include_local))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
