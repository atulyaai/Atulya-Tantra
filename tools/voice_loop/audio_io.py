"""Microphone frames and interruptible playback (sounddevice / PortAudio)."""
from __future__ import annotations

import io
import queue
import threading
import wave

import numpy as np

RATE = 16000
FRAME = 1280  # 80 ms, the chunk size openWakeWord expects


class Mic:
    """16 kHz mono int16, delivered as 80 ms frames through a queue."""

    def __init__(self, device=None) -> None:
        self.device = device
        self.frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._stream = None

    def _callback(self, data, _frames, _time, _status) -> None:
        try:
            self.frames.put_nowait(data[:, 0].copy())
        except queue.Full:  # the consumer fell behind: drop the oldest audio, never block the audio thread
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass

    def start(self) -> "Mic":
        import sounddevice as sd

        self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME,
                                      device=self.device, callback=self._callback)
        self._stream.start()
        return self

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self.frames.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> None:
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                return

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def decode_wav(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as reader:
        rate, channels = reader.getframerate(), reader.getnchannels()
        samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return samples, rate


def default_output_device(sd):
    """Windows' default speaker, or the first device that can play when none is set as default
    (seen on the owner's PC: only a Realtek WDM-KS output exists and the default is -1)."""
    default = sd.default.device[1]
    if default is not None and default >= 0:
        return None
    for index, device in enumerate(sd.query_devices()):
        if device["max_output_channels"] > 0:
            return index
    raise RuntimeError("No audio output device found; plug in speakers or headphones.")


class Player:
    """play(wav) queues audio; stop() silences it within one 20 ms block; wait() blocks until done."""

    BLOCK_MS = 20

    def __init__(self, device=None, *, stream_factory=None) -> None:
        self.device = device
        self._lock = threading.Lock()
        self._queue: list[np.ndarray] = []
        self._rate: int | None = None
        self._stream = None
        self._stream_factory = stream_factory
        self._idle = threading.Event()
        self._idle.set()

    def _open(self, rate: int):
        if self._stream_factory is not None:
            return self._stream_factory(rate, self._callback)
        import sounddevice as sd

        if self.device is None:
            self.device = default_output_device(sd)
        return sd.OutputStream(samplerate=rate, channels=1, dtype="int16", device=self.device,
                               blocksize=int(rate * self.BLOCK_MS / 1000), callback=self._callback)

    def _callback(self, out, frames, _time=None, _status=None) -> None:
        out.fill(0)
        written = 0
        with self._lock:
            while written < frames and self._queue:
                head = self._queue[0]
                take = min(frames - written, len(head))
                out[written:written + take, 0] = head[:take]
                written += take
                if take == len(head):
                    self._queue.pop(0)
                else:
                    self._queue[0] = head[take:]
            if not self._queue:
                self._idle.set()

    def play(self, wav_bytes: bytes) -> None:
        samples, rate = decode_wav(wav_bytes)
        if self._stream is None or self._rate != rate:
            self.wait(timeout=30)  # finish audio at the old rate before reopening the device
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
            self._rate = rate
            self._stream = self._open(rate)
            self._stream.start()
        with self._lock:
            self._queue.append(samples)
            self._idle.clear()

    @property
    def is_playing(self) -> bool:
        return not self._idle.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    def stop(self) -> None:
        with self._lock:
            self._queue.clear()
            self._idle.set()

    def close(self) -> None:
        self.stop()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
