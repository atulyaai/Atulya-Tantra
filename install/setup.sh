#!/usr/bin/env bash
# Atulya portable runtime installer (POSIX / Git Bash / Linux / macOS).
# Downloads the offline brain + voice + ears into ./runtime so the project
# folder is self-contained and can be copied to another machine.
#
# Usage:
#   bash install/setup.sh            # brain only (fastest)
#   bash install/setup.sh --full     # brain + Piper TTS + voice + STT deps
#   bash install/setup.sh --voice    # brain + Piper TTS + voice
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$ROOT/runtime"
MODELS="$RUNTIME/models"
BIN="$RUNTIME/bin"

MODE="${1:-brain}"

QWEN_URL="https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf"
QWEN_DEST="$MODELS/Qwen3-0.6B-Q4_K_M.gguf"

PIPER_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
VOICE_ONNX_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
VOICE_JSON_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"

echo "== Atulya portable runtime =="
echo "Installing into: $RUNTIME"
echo "Mode: $MODE"
echo "See install/manifest.json for exactly what is downloaded."
echo

mkdir -p "$MODELS" "$BIN"

fetch() {  # fetch <url> <dest>
  local url="$1" dest="$2"
  if [ -f "$dest" ] && [ "$(stat -c%s "$dest" 2>/dev/null || echo 0)" -gt 100000 ]; then
    echo "  already present: $(basename "$dest")"
    return 0
  fi
  echo "  downloading: $(basename "$dest")"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$dest.part" "$url"
  else
    wget -O "$dest.part" "$url"
  fi
  mv "$dest.part" "$dest"
}

echo "[1/4] Brain — Qwen3-0.6B GGUF (~484 MB)"
fetch "$QWEN_URL" "$QWEN_DEST"

if [ "$MODE" = "--voice" ] || [ "$MODE" = "--full" ]; then
  echo "[2/4] Voice — Piper TTS + en_US-amy"
  mkdir -p "$MODELS/piper"
  fetch "$VOICE_ONNX_URL" "$MODELS/piper/en_US-amy-medium.onnx"
  fetch "$VOICE_JSON_URL" "$MODELS/piper/en_US-amy-medium.onnx.json"
  if [ ! -x "$BIN/piper/piper" ]; then
    fetch "$PIPER_URL" "$BIN/piper.tar.gz"
    tar -xzf "$BIN/piper.tar.gz" -C "$BIN" && rm -f "$BIN/piper.tar.gz"
  fi
fi

echo "[3/4] Python runtime packages"
PKGS="llama-cpp-python edge-tts"
if [ "$MODE" = "--full" ]; then
  PKGS="$PKGS faster-whisper mss rapidocr-onnxruntime"
fi
python -m pip install --quiet $PKGS || echo "  (pip step reported issues — see output above)"

echo "[4/4] Verify"
python "$ROOT/install/verify.py" || true

echo
echo "Done. The brain lives at: $QWEN_DEST"
echo "Start Atulya with: python -m atulya.cli chat   (or start.bat on Windows)"
