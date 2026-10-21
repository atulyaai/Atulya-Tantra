"""First-run download of the local speech recognition model used by Atulya."""
from __future__ import annotations

from pathlib import Path


def prepare_models(models_dir: Path, *, stt_model: str = "base") -> None:
    """Ensure the configured Whisper model lives under models_dir."""
    models_dir.mkdir(parents=True, exist_ok=True)
    stt_dir = models_dir / "voice" / "stt" / "whisper"
    stt_dir.mkdir(parents=True, exist_ok=True)
    marker = models_dir / ".voice-ready"
    from .local import LocalVoice
    voice = LocalVoice(models_dir, stt_model=stt_model)
    for name in dict.fromkeys((stt_model, voice.english_model_name)):
        if voice._local_model(name) is not None:
            continue
        print(f"Downloading local speech recognition model '{name}' into {stt_dir}...", flush=True)
        try:
            from faster_whisper.utils import download_model

            # Download weights into the app-owned folder without keeping a second
            # inference model resident during every launch.
            download_model(name, cache_dir=str(stt_dir))
        except Exception as exc:
            raise RuntimeError(f"Could not prepare the local speech recognition model: {exc}") from exc
        if voice._local_model(name) is None:
            raise RuntimeError(f"The speech recognition download did not create a model file under {stt_dir}.")

    marker.write_text(f"{stt_model}\n", encoding="utf-8")
    print("Local speech recognition model is ready. Spoken replies use the local sherpa-onnx voice when its model is present.", flush=True)
