"""First-run download of the local speech recognition model used by Atulya."""
from __future__ import annotations

from pathlib import Path


def prepare_models(models_dir: Path, *, stt_model: str = "base") -> None:
    """Ensure the configured Whisper model lives under models_dir."""
    models_dir.mkdir(parents=True, exist_ok=True)
    stt_dir = models_dir / "voice" / "stt" / "whisper"
    stt_dir.mkdir(parents=True, exist_ok=True)
    marker = models_dir / ".voice-ready"
    marker_values = marker.read_text(encoding="utf-8").splitlines() if marker.is_file() else []
    whisper_matches = marker_values[:1] == [stt_model] and any(stt_dir.rglob("model.bin"))
    if whisper_matches:
        if marker_values != [stt_model]:
            marker.write_text(f"{stt_model}\n", encoding="utf-8")
        print(f"Local speech models are ready under {models_dir}.", flush=True)
        return

    if not whisper_matches:
        print(f"Downloading local speech recognition model '{stt_model}' into {stt_dir}...", flush=True)
        try:
            from faster_whisper.utils import download_model

            # Download weights into the app-owned folder without keeping a second
            # inference model resident during every launch.
            download_model(stt_model, cache_dir=str(stt_dir))
        except Exception as exc:
            raise RuntimeError(f"Could not prepare the local speech recognition model: {exc}") from exc
        if not any(stt_dir.rglob("model.bin")):
            raise RuntimeError(f"The speech recognition download did not create a model file under {stt_dir}.")

    marker.write_text(f"{stt_model}\n", encoding="utf-8")
    print("Local speech recognition model is ready. Speech output uses the browser's built-in voice.", flush=True)
