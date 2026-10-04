"""Audio adapters for the always-listening app: microphone, speech-to-text and
the speaker. Each has a dependency-light fallback so the listener runs on a
laptop, a Raspberry Pi or a desktop with what's available.

  microphone      sounddevice (``pip install sounddevice``)
  speech-to-text  local faster-whisper (private, offline) or the Atulya server
  speaker         pyttsx3 (offline), else the OS voice: ``say`` on macOS,
                  System.Speech on Windows, espeak / spd-say on Linux
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
import wave
from typing import Any, AsyncIterator, Callable

from atulya.shruti.listener import FRAME_SAMPLES, SAMPLE_RATE, Segmenter

logger = logging.getLogger(__name__)


def to_wav(audio: Any, rate: int = SAMPLE_RATE) -> bytes:
    """float32 samples (-1..1) -> 16-bit mono WAV bytes."""
    import numpy as np

    pcm = (np.clip(np.asarray(audio, dtype="float32"), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


class WakeGate:
    """Optional wake-word *model* in front of speech-to-text (openWakeWord).

    Without it every spoken sentence is transcribed just to look for the wake
    word. With a model (``ATULYA_WAKE_MODEL``, an .onnx/.tflite trained on your
    wake word) only sentences spoken right after it fires are transcribed.
    """

    CHUNK = 1280  # 80 ms at 16 kHz, the size openWakeWord expects

    def __init__(self, model_path: str = "", threshold: float = 0.5, window: float = 15.0,
                 model: Any = None, clock: Callable[[], float] = time.time):
        self.threshold = threshold
        self.window = window
        self._clock = clock
        self._model = model
        self._path = model_path
        self._buf: list[Any] = []
        self.last_fire = 0.0

    def _load(self) -> Any:
        if self._model is None:
            from openwakeword.model import Model

            self._model = Model(wakeword_models=[self._path])
        return self._model

    def feed(self, frame: Any) -> bool:
        """Feed a float32 frame in [-1, 1]; True when the wake word just fired."""
        import numpy as np

        self._buf.append(np.asarray(frame, dtype="float32"))
        data = np.concatenate(self._buf)
        fired = False
        while len(data) >= self.CHUNK:
            chunk, data = data[:self.CHUNK], data[self.CHUNK:]
            scores = self._load().predict((chunk * 32767).astype("int16"))
            if scores and max(scores.values()) >= self.threshold:
                self.last_fire = self._clock()
                fired = True
        self._buf = [data] if len(data) else []
        return fired

    def recent(self) -> bool:
        """Did the wake word fire within the last ``window`` seconds?"""
        return self._clock() - self.last_fire <= self.window


class Microphone:
    """Continuous capture, split into utterances by the segmenter."""

    def __init__(self, device: Any = None, segmenter: Segmenter | None = None,
                 enabled: Callable[[], bool] | None = None, gate: WakeGate | None = None,
                 active: Callable[[], bool] | None = None):
        self.device = device
        self.segmenter = segmenter or Segmenter()
        self.enabled = enabled or (lambda: True)
        self.gate = gate
        self.active = active or (lambda: False)  # mid-conversation: no wake word needed

    async def utterances(self) -> AsyncIterator[Any]:
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        frames: asyncio.Queue = asyncio.Queue(maxsize=500)

        def callback(indata, _frames, _time, status):  # runs on the audio thread
            if status:
                logger.debug("audio status: %s", status)
            try:
                loop.call_soon_threadsafe(frames.put_nowait, indata[:, 0].copy())
            except (asyncio.QueueFull, RuntimeError):
                pass

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=FRAME_SAMPLES,
                            device=self.device, callback=callback):
            while True:
                frame = await frames.get()
                if not self.enabled():  # muted, or Atulya is speaking: don't listen to ourselves
                    continue
                if self.gate is not None:
                    self.gate.feed(frame)
                utterance = self.segmenter.feed(frame)
                if utterance is not None:
                    if self.gate is None or self.gate.recent() or self.active():
                        yield utterance


class LocalWhisper:
    """Private, offline speech-to-text with faster-whisper."""

    def __init__(self, model: str = "base.en", hint: str = "Atulya"):
        from faster_whisper import WhisperModel

        self.label = f"whisper {model} (local)"
        self._model = WhisperModel(model, device="cpu", compute_type="int8")
        self._hint = hint
        self._english_only = model.endswith(".en")  # multilingual models also hear Hindi

    def _transcribe(self, audio: Any) -> str:
        opts = dict(beam_size=1, initial_prompt=self._hint, condition_on_previous_text=False)
        if self._english_only:
            segments, _info = self._model.transcribe(audio, language="en", **opts)
        else:
            from atulya.vani.pipeline import pick_language

            segments, info = self._model.transcribe(audio, **opts)
            segments = list(segments)
            if info.language not in ("en", "hi"):  # never guess some other language from noise
                segments, _info = self._model.transcribe(audio, language=pick_language(info), **opts)
        return " ".join(s.text.strip() for s in segments).strip()

    async def transcribe(self, audio: Any) -> str:
        return await asyncio.to_thread(self._transcribe, audio)


class ServerSTT:
    """Send the audio to the Atulya server's speech-to-text (for small devices)."""

    label = "server"

    def __init__(self, client: Any):
        self.client = client

    async def transcribe(self, audio: Any) -> str:
        return await self.client.transcribe(to_wav(audio))


def make_stt(mode: str, client: Any, model: str = "base.en") -> Any:
    if mode in ("auto", "local"):
        try:
            return LocalWhisper(model)
        except Exception as exc:  # noqa: BLE001 - faster-whisper missing or model unavailable
            if mode == "local":
                raise
            logger.info("local speech-to-text unavailable (%s); using the server", exc)
    return ServerSTT(client)


class Speaker:
    """Offline text-to-speech with whatever the machine has."""

    def __init__(self, backend: str = "auto", rate: int = 180):
        self.rate = rate
        self.backend = self._pick(backend)
        self._proc: subprocess.Popen | None = None
        self._engine: Any = None

    def stop(self) -> None:
        """Interrupt speech in progress (barge-in)."""
        engine, proc = self._engine, self._proc
        if engine is not None:
            try:
                engine.stop()
            except Exception:  # noqa: BLE001
                pass
        if proc is not None and proc.poll() is None:
            proc.terminate()
        if self.backend == "piper" and platform.system() == "Windows":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:  # noqa: BLE001
                pass

    def _say_piper(self, text: str) -> None:
        """Piper writes a wav (text arrives on stdin, never in a shell); then play it."""
        model = os.environ.get("ATULYA_PIPER_MODEL", "")
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "say.wav")
            self._proc = subprocess.Popen(["piper", "--model", model, "--output_file", wav], stdin=subprocess.PIPE)
            try:
                self._proc.communicate(text.encode("utf-8"))
            finally:
                self._proc = None
            if not os.path.exists(wav):
                return
            if platform.system() == "Windows":
                import winsound

                winsound.PlaySound(wav, winsound.SND_FILENAME)
            elif shutil.which("afplay"):
                self._run(["afplay", wav])
            elif shutil.which("aplay"):
                self._run(["aplay", "-q", wav])

    def _run(self, cmd: list[str], env: dict | None = None) -> None:
        self._proc = subprocess.Popen(cmd, env=env)
        try:
            self._proc.wait()
        finally:
            self._proc = None

    @staticmethod
    def _pick(backend: str) -> str:
        if backend != "auto":
            return backend
        if os.environ.get("ATULYA_PIPER_MODEL") and shutil.which("piper"):
            return "piper"  # natural offline neural voice
        try:
            import pyttsx3  # noqa: F401

            return "pyttsx3"
        except ImportError:
            pass
        system = platform.system()
        if system == "Darwin" and shutil.which("say"):
            return "say"
        if system == "Windows":
            return "windows"
        for cmd in ("espeak-ng", "espeak", "spd-say"):
            if shutil.which(cmd):
                return cmd
        return "print"

    def say(self, text: str) -> None:
        if not text:
            return
        if self.backend == "piper":
            self._say_piper(text)
        elif self.backend == "pyttsx3":
            import pyttsx3

            engine = self._engine = pyttsx3.init()  # one engine per call: pyttsx3 isn't thread-safe
            engine.setProperty("rate", self.rate)
            engine.say(text)
            engine.runAndWait()
            self._engine = None
        elif self.backend == "say":
            self._run(["say", text])
        elif self.backend == "windows":
            # The text travels in an environment variable, never inside the script.
            script = ("Add-Type -AssemblyName System.Speech; "
                      "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($env:ATULYA_SAY)")
            self._run(["powershell", "-NoProfile", "-Command", script], env={**os.environ, "ATULYA_SAY": text})
        elif self.backend in ("espeak-ng", "espeak"):
            self._run([self.backend, "-s", str(self.rate), "--", text])
        elif self.backend == "spd-say":
            self._run(["spd-say", "--wait", "--", text])
        else:
            print(f"Atulya: {text}", flush=True)
