"""Hands-free listener for Termux, built on shared ambient audio and server clients.

Install ``atulya[phone_listener]`` and provide a compatible local OpenWakeWord model:
``atulya-ambient-phone --server https://... --token ... --model /path/to/model.onnx``.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import time
import unicodedata
from typing import Any

from atulya.ambient import (
    AtulyaClient,
    AuthError,
    Segmenter,
    Speaker,
    WakeGate,
    _offer_audio_frame,
)

logger = logging.getLogger(__name__)
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
STOP_WORDS = {"stop", "quiet", "enough", "shut up", "be quiet", "cancel", "ruko", "chup", "bas",
              "रुको", "चुप", "बस", "रुकिए", "बंद करो"}


def _is_stop_command(text: str) -> bool:
    normalized = " ".join("".join(
        char if (char.isalnum() or char.isspace() or unicodedata.category(char)[0] == "M") else " "
        for char in (text or "").lower()
    ).split())
    return any(normalized == word or f" {word} " in f" {normalized} " for word in STOP_WORDS)


class PhoneListenerClient:
    """Local wake gate and VAD; authenticated STT/chat and local Android speech."""

    def __init__(
        self,
        server_url: str,
        token: str,
        model_path: str = "",
        threshold: float = 0.5,
        follow_up_window: float = 15.0,
        device: int | None = None,
        *,
        api: Any = None,
        speaker: Any = None,
        matcher: Any = None,
        segmenter: Any = None,
    ):
        if not model_path and matcher is None:
            raise ValueError("Set ATULYA_WAKE_MODEL or pass --model with a compatible wake-word model.")
        if not 0.0 < float(threshold) <= 1.0:
            raise ValueError("Wake threshold must be greater than 0 and at most 1.")
        if float(follow_up_window) <= 0:
            raise ValueError("Follow-up window must be greater than 0 seconds.")

        self.api = api or AtulyaClient(server_url, token, device="termux")
        self.speaker = speaker or Speaker()
        self.matcher = matcher or WakeGate(model_path=model_path, threshold=float(threshold), window=30.0)
        self.segmenter = segmenter or Segmenter()
        self.follow_up_window = float(follow_up_window)
        self.follow_up_until = 0.0
        self.device = device
        self._shutdown = False

    async def send_utterance(self, audio: Any) -> str:
        """Transcribe through the shared client (X-Atulya-Token, language=auto)."""
        return await self.api.transcribe(audio)

    async def send_text(self, text: str) -> dict[str, Any]:
        """Chat through the shared safety pipeline and retain server-side history."""
        return await self.api.chat(text)

    async def speak(self, text: str) -> None:
        """Use ambient's speaker, which selects Termux:API local TTS on Android."""
        await asyncio.to_thread(self.speaker.say, text)

    async def process_utterance(self, audio: Any) -> None:
        try:
            text = (await self.send_utterance(audio)).strip()
            if not text:
                return
            if _is_stop_command(text):
                logger.info("Stop command detected; ending the current conversation.")
                self.follow_up_until = 0.0
                return
            result = await self.send_text(text)
            reply = str(result.get("response_text") or result.get("response") or result.get("text") or "").strip()
            if reply:
                await self.speak(reply)
                self.follow_up_until = time.monotonic() + self.follow_up_window
        except AuthError as exc:
            logger.error("Termux device sign-in expired: %s", exc)
            self.shutdown()
        except Exception as exc:  # noqa: BLE001 - a network/model error must not kill the listener
            logger.warning("Termux voice turn failed: %s", exc)

    async def process_frame(self, frame: Any) -> None:
        """Feed one frame; keep the wake event alive until VAD closes its utterance."""
        if self.matcher.feed(frame):
            self.follow_up_until = time.monotonic() + self.follow_up_window
            logger.debug("Wake word detected.")
        utterance = self.segmenter.feed(frame)
        if utterance is not None and time.monotonic() < self.follow_up_until:
            await self.process_utterance(utterance)

    async def run(self) -> None:
        """Capture locally and send only wake-gated utterances to the server."""
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        frames: asyncio.Queue = asyncio.Queue(maxsize=100)

        def callback(indata, _frames, _time, status):
            if status:
                logger.debug("audio status: %s", status)
            try:
                loop.call_soon_threadsafe(_offer_audio_frame, frames, indata[:, 0].copy())
            except RuntimeError:  # event loop already closed during shutdown
                pass

        logger.info("Termux listener started; wake detection runs locally.")
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=FRAME_SAMPLES, device=self.device, callback=callback):
            while not self._shutdown:
                try:
                    frame = await asyncio.wait_for(frames.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                await self.process_frame(frame)

    def shutdown(self) -> None:
        self._shutdown = True


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Atulya hands-free listener for Termux")
    parser.add_argument("--server", required=True, help="Atulya server URL (HTTPS recommended)")
    parser.add_argument("--token", required=True, help="Paired device token")
    parser.add_argument("--model", default=os.environ.get("ATULYA_WAKE_MODEL", ""),
                        help="Compatible local OpenWakeWord model path (or set ATULYA_WAKE_MODEL)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Wake model threshold from 0 to 1")
    parser.add_argument("--follow-up", type=float, default=15.0, help="Seconds to keep listening after each reply")
    parser.add_argument("--device", type=int, default=None, help="Audio input device index")
    args = parser.parse_args(argv)
    if not args.model:
        parser.error("a local model is required; use --model or set ATULYA_WAKE_MODEL")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    client = PhoneListenerClient(args.server, args.token, args.model, args.threshold, args.follow_up, args.device)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, client.shutdown)
        except (NotImplementedError, RuntimeError):
            pass
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
