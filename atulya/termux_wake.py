"""Termux wake word listener — runs on Android phone, streams audio to server when wake word fires.

Usage on phone (Termux):
    pkg install python termux-api numpy sounddevice
    pip install openwakeword onnxruntime
    python -m atulya.termux_wake --server https://your-server.com --token YOUR_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import time

import httpx
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples @ 16kHz
CHUNK = 1280  # 80 ms at 16 kHz, what openWakeWord expects

DEFAULT_WAKE_WORDS = (
    "hey atulya", "ok atulya", "hi atulya", "atulya",
    "अतुल्य", "हे अतुल्य", "सुनो अतुल्य",
)

STOP_WORDS = {
    "stop", "quiet", "enough", "shut up", "be quiet", "cancel",
    "atulya stop", "stop atulya", "ruko", "chup", "bas",
}


class WakeMatcher:
    """On-device wake word detection using openWakeWord."""

    CHUNK = 1280

    def __init__(self, model_path: str = "", threshold: float = 0.5, window: float = 15.0):
        self.threshold = threshold
        self.window = window
        self._model = None
        self._path = model_path
        self._buf: list = []
        self.last_fire = 0.0

    def _load(self):
        if self._model is None:
            from openwakeword.model import Model
            self._model = Model(wakeword_models=[self._path] if self._path else ["hey_atulya"])
        return self._model

    def feed(self, frame: np.ndarray) -> bool:
        """Feed a float32 frame in [-1, 1]; True when wake word fires."""
        self._buf.append(frame.astype("float32"))
        data = np.concatenate(self._buf)
        while len(data) >= self.CHUNK:
            chunk, data = data[:self.CHUNK], data[self.CHUNK:]
            scores = self._load().predict((chunk * 32767).astype("int16"))
            if scores and max(scores.values()) >= self.threshold:
                self.last_fire = time.time()
                return True
        if len(data):
            self._buf = [data]
        else:
            self._buf = []
        return False

    def recent(self) -> bool:
        return time.time() - self.last_fire <= self.window


class Segmenter:
    """Simple VAD-based utterance segmenter."""

    def __init__(self, vad_aggressiveness: int = 2, min_speech_ms: int = 300,
                 max_silence_ms: int = 800, max_utterance_s: float = 30.0):
        import webrtcvad
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.min_speech = int(min_speech_ms * SAMPLE_RATE / 1000)
        self.max_silence = int(max_silence_ms * SAMPLE_RATE / 1000)
        self.max_utterance = int(max_utterance_s * SAMPLE_RATE)
        self._buf: list = []
        self.speech_frames = 0
        self.silence_frames = 0
        self.in_speech = False

    def feed(self, frame: np.ndarray) -> np.ndarray | None:
        """Feed 30 ms frame; return completed utterance or None."""
        pcm16 = (np.clip(frame, -1, 1) * 32767).astype("int16")
        is_speech = self.vad.is_speech(pcm16.tobytes(), SAMPLE_RATE)

        if is_speech:
            self.speech_frames += len(frame)
            self.silence_frames = 0
            if not self.in_speech and self.speech_frames >= self.min_speech:
                self.in_speech = True
        else:
            self.silence_frames += len(frame)

        self._buf.append(frame)

        if self.in_speech:
            if self.silence_frames >= self.max_silence:
                utterance = np.concatenate(self._buf)
                self._reset()
                return utterance
            if sum(len(f) for f in self._buf) >= self.max_utterance:
                utterance = np.concatenate(self._buf)
                self._reset()
                return utterance
        return None

    def _reset(self):
        self._buf = []
        self.speech_frames = 0
        self.silence_frames = 0
        self.in_speech = False


class TermuxWakeClient:
    """Termux wake word client - listens locally, sends utterances to server."""

    def __init__(
        self,
        server_url: str,
        token: str,
        wake_words: tuple[str, ...] = None,
        model_path: str = "",
        threshold: float = 0.5,
        follow_up_window: float = 15.0,
        device: int | None = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.wake_words = wake_words or ("hey atulya", "ok atulya", "hi atulya", "atulya")
        self.matcher = WakeMatcher(threshold=0.5)
        self.segmenter = Segmenter()
        self.follow_up_until = 0.0
        self.follow_up_window = 15.0
        self.device = device
        self._shutdown = False

    async def send_utterance(self, audio: np.ndarray) -> dict | None:
        """Send utterance to server for STT + LLM."""
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            pcm16 = (np.clip(audio, -1, 1) * 32767).astype("int16")
            wf.writeframes(pcm16.tobytes())

        buf.seek(0)
        files = {"file": ("utterance.wav", buf, "audio/wav")}
        data = {"language": "en"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.server_url}/api/voice/stt",
                    headers={"Authorization": f"Bearer {self.token}"},
                    files=files,
                    data=data,
                )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("STT failed: %s", resp.status_code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("STT request failed: %s", exc)
        return None

    async def send_text(self, text: str) -> dict | None:
        """Send text directly to chat endpoint."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.server_url}/api/chat",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    json={"prompt": text, "model_id": "atulya", "provider": "local", "max_tokens": 256, "temperature": 0.7},
                )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Chat failed: %s", resp.status_code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat request failed: %s", exc)
        return None

    async def speak(self, text: str) -> None:
        """Ask server for TTS, play locally."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.server_url}/api/voice/tts",
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                    json={"text": text, "voice": "en-US-AriaNeural"},
                )
            if resp.status_code == 200:
                audio = resp.content
                import io
                import soundfile as sf
                data, sr = sf.read(io.BytesIO(audio))
                sd.play(data, sr)
                sd.wait()
        except Exception as exc:  # noqa: BLE001
            logger.warning("TTS/play failed: %s", exc)

    async def run(self) -> None:
        """Main listening loop."""
        loop = asyncio.get_running_loop()
        frames: asyncio.Queue = asyncio.Queue(maxsize=500)

        def callback(indata, _frames, _time, status):
            if status:
                logger.debug("audio status: %s", status)
            try:
                loop.call_soon_threadsafe(frames.put_nowait, indata[:, 0].copy())
            except (asyncio.QueueFull, RuntimeError):
                pass

        logger.info("Termux wake listener started. Say 'hey atulya'...")
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=FRAME_SAMPLES, device=self.device, callback=callback):
            while not self._shutdown:
                frame = await frames.get()

                # Wake word detection
                wake_fired = self.matcher.feed(frame)

                # Utterance segmentation
                utterance = self.segmenter.feed(frame)

                # Check if we're in follow-up mode (recent wake word)
                in_follow_up = time.time() < self.follow_up_until

                # Decide whether to process utterance
                should_process = wake_fired or in_follow_up

                if utterance is not None and should_process:
                    # Check for stop words
                    result = await self.send_utterance(utterance)
                    if result:
                        text = result.get("text", "").strip().lower()
                        if any(sw in text for sw in STOP_WORDS):
                            logger.info("Stop word detected, ending conversation")
                            self.follow_up_until = 0
                            continue

                        # If wake word just fired, start follow-up window
                        if wake_fired:
                            self.follow_up_until = time.time() + self.follow_up_window

                        # Send to chat
                        if text:
                            chat_result = await self.send_text(text)
                            if chat_result and "text" in chat_result:
                                await self.speak(chat_result["text"])

    def shutdown(self):
        self._shutdown = True


async def main():
    parser = argparse.ArgumentParser(description="Termux wake word listener")
    parser.add_argument("--server", required=True, help="Atulya server URL (https://...)")
    parser.add_argument("--token", required=True, help="Device token from pairing")
    parser.add_argument("--model", default="", help="Path to openWakeWord model (.onnx)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Wake word threshold")
    parser.add_argument("--follow-up", type=float, default=15.0, help="Follow-up window (seconds)")
    parser.add_argument("--device", type=int, default=None, help="Audio device index")
    parser.add_argument("--wake-words", default="", help="Comma-separated wake words")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    wake_words = tuple(w.strip() for w in args.wake_words.split(",") if w.strip()) or DEFAULT_WAKE_WORDS

    client = TermuxWakeClient(
        server_url=args.server,
        token=args.token,
        wake_words=wake_words,
        model_path=args.model,
        threshold=args.threshold,
        follow_up_window=args.follow_up,
        device=args.device,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, client.shutdown)

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())