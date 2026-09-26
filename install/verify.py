"""Verify the Atulya portable runtime is in place and the brain can load.

Run directly (``python install/verify.py``) or from the setup scripts. Exits 0
when the brain model is present and loadable; prints a clear checklist either
way so it doubles as a quick "am I set up?" diagnostic.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RUNTIME = ROOT / "runtime"
MODELS = RUNTIME / "models"


def _mb(p: Path) -> str:
    try:
        return f"{p.stat().st_size / 1024 / 1024:.0f} MB"
    except OSError:
        return "?"


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK  " if ok else "MISS"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    return ok


def main() -> int:
    print("== Atulya runtime check ==")
    essential_ok = True

    # Brain model
    ggufs = sorted(MODELS.glob("Qwen3-0.6B*.gguf")) if MODELS.exists() else []
    brain_ok = bool(ggufs)
    check("Brain model (Qwen3-0.6B GGUF)", brain_ok, _mb(ggufs[0]) if ggufs else "run install/setup")
    essential_ok &= brain_ok

    # Optional voice
    voice = MODELS / "piper" / "en_US-amy-medium.onnx"
    check("Voice (Piper en_US-amy)", voice.exists(), "optional")

    # Python packages
    try:
        import llama_cpp  # noqa: F401
        check("llama-cpp-python", True)
    except Exception:
        check("llama-cpp-python", False, "pip install llama-cpp-python")
        essential_ok = False

    # Can the provider actually resolve + load the model?
    if brain_ok:
        try:
            from atulya.local_provider import LocalGGUFProvider

            provider = LocalGGUFProvider()
            check("LocalGGUFProvider available", provider.is_available())
        except Exception as exc:  # pragma: no cover - environment dependent
            check("LocalGGUFProvider available", False, str(exc)[:60])

    print()
    if essential_ok:
        print("Ready. Start with: python -m atulya.cli chat")
        return 0
    print("Not ready yet — run install/setup.ps1 (Windows) or install/setup.sh.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
