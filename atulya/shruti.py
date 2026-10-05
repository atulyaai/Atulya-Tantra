"""Always-on ambient presence — Atulya listening in the background.

The web UI only hears you while its tab is open. This small app runs on your
computer (or a Raspberry Pi in the kitchen) all the time: it listens for the
wake word, sends what you say to your Atulya server, speaks the answer, and
speaks notifications such as reminders or "someone is at the door". A tray
icon shows its state and mutes the microphone.

    atulya listen --login                                 # once (add --url for a remote server)
    atulya listen                                         # every time
    atulya listen --install-autostart                     # start at login

Everything important stays on the server: safety rules, confirmations ("should
I unlock the front door?" — just say yes or no) and what Atulya learns about
you are the same as in the web UI. Speech-to-text runs locally with
faster-whisper when installed (private), otherwise on the server.

Install the extras with ``pip install -e ".[ambient]"``."""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import difflib
import getpass
import io
import json
import logging
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import wave
import webbrowser
from collections import deque
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable
from xml.sax.saxutils import escape

# ── shruti ────────────────────────────────────────────────────────────
__all__ = ["AmbientEngine", "AmbientSession", "AtulyaClient", "Segmenter", "WakeMatcher"]


# ── listener ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
DEFAULT_WAKE_WORDS = (
    "hey atulya", "ok atulya", "hi atulya", "atulya",
    # Hindi (Devanagari) and Hinglish
    "अतुल्य", "हे अतुल्य", "हेय अतुल्य", "सुनो अतुल्य", "अरे अतुल्य", "suno atulya", "are atulya",
)
# Said while Atulya is talking, these cut it off (barge-in).
STOP_WORDS = {"stop", "quiet", "enough", "shut up", "be quiet", "cancel", "atulya stop", "stop atulya",
              "ruko", "chup", "bas", "रुको", "चुप", "बस", "रुकिए", "बंद करो"}
_FILLERS = {"um", "uh", "so", "and", "oh", "well", "hmm", "ah", "er"}


# ── hearing: split a microphone stream into utterances ────────────────────
class Segmenter:
    """Energy-based voice activity detection with an adaptive noise floor.

    Feed 30 ms frames (float32, -1..1); get back a whole utterance once the
    speaker pauses. A short pre-roll keeps the first syllable.
    """

    def __init__(self, start_frames: int = 4, end_silence_ms: int = 800, max_ms: int = 15000,
                 preroll_ms: int = 300, min_rms: float = 0.01, factor: float = 3.0, min_speech_ms: int = 250,
                 calibrate_ms: int = 500):
        self.start_frames = start_frames
        self.end_frames = max(1, end_silence_ms // FRAME_MS)
        self.max_frames = max_ms // FRAME_MS
        self.min_frames = max(1, min_speech_ms // FRAME_MS)
        self.min_rms = min_rms
        self.factor = factor
        self._preroll: deque = deque(maxlen=max(1, preroll_ms // FRAME_MS))
        self._noise = min_rms / factor
        self._calibrating = max(0, calibrate_ms // FRAME_MS)
        self._reset()

    def _reset(self) -> None:
        self._active = False
        self._run = 0
        self._silence = 0
        self._voiced = 0
        self._buf: list = []

    @property
    def threshold(self) -> float:
        return max(self.min_rms, self._noise * self.factor)

    def feed(self, frame: Any) -> Any | None:
        import numpy as np

        frame = np.asarray(frame, dtype="float32").reshape(-1)
        rms = float(np.sqrt(np.mean(frame * frame))) if frame.size else 0.0
        if self._calibrating:  # the first half second: learn how loud the room is
            self._calibrating -= 1
            self._noise = max(self._noise, rms) if self._noise > self.min_rms / self.factor else rms
            self._preroll.append(frame)
            return None
        speech = rms > self.threshold
        if not self._active:
            self._preroll.append(frame)
            self._run = self._run + 1 if speech else 0
            # The background level follows the room: down quickly, up slowly, so a
            # fan or a TV hum stops counting as speech but a voice doesn't raise it much.
            self._noise += (0.2 if rms < self._noise else 0.02) * (rms - self._noise)
            if self._run >= self.start_frames:
                self._active = True
                self._buf = list(self._preroll)
                self._voiced = self._run
                self._silence = 0
            return None
        self._buf.append(frame)
        if speech:
            self._voiced += 1
            self._silence = 0
        else:
            self._silence += 1
        if self._silence >= self.end_frames or len(self._buf) >= self.max_frames:
            audio, voiced = np.concatenate(self._buf), self._voiced
            self._reset()
            self._preroll.clear()
            return audio if voiced >= self.min_frames else None
        return None


# ── the wake word ─────────────────────────────────────────────────────────
def _normalize(text: str) -> str:
    # Keep combining marks (Devanagari vowel signs) — \w alone would split Hindi words apart.
    kept = "".join(c if (c.isalnum() or c in "' " or unicodedata.category(c)[0] == "M") else " "
                   for c in (text or "").lower())
    return " ".join(kept.split())


class WakeMatcher:
    """Fuzzy wake-phrase match at the start of a transcript.

    Speech-to-text spells unusual names creatively ("a tulia", "atoolya"), so
    the start of the sentence is compared letter by letter with each wake
    phrase, and the best match above ``threshold`` wins.
    """

    def __init__(self, phrases: tuple[str, ...] | list[str] = DEFAULT_WAKE_WORDS, threshold: float = 0.75):
        self.phrases = [_normalize(p) for p in phrases if _normalize(p)]
        self.threshold = threshold

    def match(self, text: str) -> tuple[bool, str]:
        """(woke, the rest of the sentence after the wake phrase)."""
        words = _normalize(text).split()
        while words and words[0] in _FILLERS:
            words = words[1:]
        best: tuple[float, int, int] | None = None  # (score, -length gap, words used)
        for phrase in self.phrases:
            target = phrase.replace(" ", "")
            for n in range(1, min(len(words), len(phrase.split()) + 2) + 1):
                candidate = "".join(words[:n])
                score = difflib.SequenceMatcher(None, candidate, target).ratio()
                key = (score, -abs(len(candidate) - len(target)), n)
                if score >= self.threshold and (best is None or key[:2] > best[:2]):
                    best = key
        if best is None:
            return False, ""
        return True, " ".join(words[best[2]:]).strip(" ,.")


# ── the daily briefing ────────────────────────────────────────────────────
class BriefingClock:
    """True once a day, the first time the clock passes ``HH:MM``."""

    def __init__(self, at: str):
        hour, _, minute = at.partition(":")
        self.at = _dt.time(int(hour), int(minute or 0))
        self._last: _dt.date | None = None

    def due(self, now: _dt.datetime | None = None) -> bool:
        now = now or _dt.datetime.now()
        if self._last == now.date() or now.time() < self.at:
            return False
        self._last = now.date()
        return True


# ── conversation state ────────────────────────────────────────────────────
class AmbientSession:
    IDLE, LISTENING, CONFIRMING, FOLLOW_UP = "idle", "listening", "confirming", "follow_up"

    def __init__(self, wake: WakeMatcher | None = None, listen_window: float = 8.0, confirm_window: float = 30.0,
                 follow_up: float = 0.0):
        self.wake = wake or WakeMatcher()
        self.listen_window = listen_window
        self.confirm_window = confirm_window
        self.follow_up = follow_up
        self.state = self.IDLE
        self._until = 0.0

    def on_utterance(self, text: str, now: float | None = None) -> tuple[str, str]:
        """('ignore', '') / ('prompt', 'Yes?') / ('send', command)."""
        now = time.time() if now is None else now
        text = (text or "").strip()
        if self.state != self.IDLE and now > self._until:
            self.state = self.IDLE
        if not text:
            return ("ignore", "")
        woke, rest = self.wake.match(text)
        if woke:
            if rest:
                self.state = self.IDLE
                return ("send", rest)
            self.state, self._until = self.LISTENING, now + self.listen_window
            return ("prompt", "Yes?")
        if self.state != self.IDLE:  # listening, a pending yes/no, or a follow-up
            self.state = self.IDLE
            return ("send", text)
        return ("ignore", "")

    def on_reply(self, reply: dict[str, Any], now: float | None = None) -> None:
        now = time.time() if now is None else now
        if reply.get("needs_approval"):
            self.state, self._until = self.CONFIRMING, now + self.confirm_window
        elif self.follow_up > 0:
            self.state, self._until = self.FOLLOW_UP, now + self.follow_up
        else:
            self.state = self.IDLE


# ── talking to the Atulya server ──────────────────────────────────────────
class AuthError(RuntimeError):
    pass


class AtulyaClient:
    def __init__(self, url: str, token: str, device: str = "listener", transport: Any = None, timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.token = token
        self.device = device
        self._transport = transport
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-Atulya-Token": self.token}

    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            resp = await client.post(f"{self.url}{path}", headers=self._headers(), **kwargs)
        if resp.status_code in (401, 403):
            raise AuthError("Atulya rejected this device's sign-in")
        resp.raise_for_status()
        return resp.json()

    async def chat(self, text: str) -> dict[str, Any]:
        # The server decides everything (safety, confirmations); this device only
        # asks, as the signed-in user, from the "ambient" surface.
        return await self._post("/api/voice/chat", json={"prompt": text, "source": "ambient", "tts": False})

    async def transcribe(self, wav: bytes) -> str:
        data = await self._post("/api/voice/stt", files={"file": ("speech.wav", wav, "audio/wav")},
                                data={"language": "en"})
        return str(data.get("text") or "")

    async def heartbeat(self, info: dict[str, Any]) -> None:
        await self._post("/api/senses/heartbeat", json={"device": self.device, **info})

    async def notifications(self, on_message: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Receive live notifications over the WebSocket; reconnects with backoff."""
        import websockets

        ws_url = re.sub(r"^http", "ws", self.url) + "/api/ws?token=" + self.token
        delay = 2.0
        while True:
            try:
                async with websockets.connect(ws_url, open_timeout=10) as sock:
                    delay = 2.0
                    async for raw in sock:
                        msg = json.loads(raw)
                        if msg.get("type") == "event" and not msg.get("replay"):
                            await on_message(msg.get("data") or {})
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - server restarting, network blip…
                logger.debug("notification socket closed: %s", exc)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)

    @staticmethod
    async def device_token(url: str, username: str, password: str, device: str, transport: Any = None) -> str:
        """Sign in once and get a long-lived token for this device."""
        import httpx

        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            login = await client.post(f"{url.rstrip('/')}/api/auth/login",
                                      json={"username": username, "password": password})
            if login.status_code != 200:
                raise AuthError("wrong username or password")
            session = login.json()["token"]
            resp = await client.post(f"{url.rstrip('/')}/api/senses/device-token", json={"device": device},
                                     headers={"X-Atulya-Token": session})
            resp.raise_for_status()
            return str(resp.json()["token"])


def speakable(text: str) -> str:
    """Turn a chat-formatted reply into something pleasant to hear."""
    from atulya.adhar import strip_emoji

    text = strip_emoji(re.sub(r"[*_`#>]+", "", text or ""))
    text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", text, flags=re.MULTILINE)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(line if line[-1] in ".?!" else line + "." for line in lines)


# ── the engine ────────────────────────────────────────────────────────────
class AmbientEngine:
    """Glue: utterances in, speech out; heartbeats and notifications alongside."""

    def __init__(self, client: AtulyaClient, stt: Any, speaker: Any, session: AmbientSession | None = None,
                 heartbeat_interval: float = 30.0, wake_label: str = "hey atulya", stt_label: str = "",
                 briefing_at: str = "", briefing_location: str = ""):
        self.client = client
        self.stt = stt
        self.speaker = speaker
        self.session = session or AmbientSession()
        self.heartbeat_interval = heartbeat_interval
        self.wake_label = wake_label
        self.stt_label = stt_label
        self.briefing = BriefingClock(briefing_at) if briefing_at else None
        self.briefing_location = briefing_location
        self.muted = False
        self.speaking = False
        self.status = "listening"
        self.last_heard: float | None = None
        self.needs_sign_in = False
        self._quiet_until = 0.0
        self.on_status: Callable[[str], None] | None = None

    def accepts_audio(self) -> bool:
        """Ignore the microphone while muted or while Atulya itself is talking."""
        # While speaking the mic stays open only to hear "stop" (barge-in).
        return not self.muted and (self.speaking or time.time() >= self._quiet_until)

    def interrupt(self) -> bool:
        """Cut off whatever Atulya is saying right now."""
        stop = getattr(self.speaker, "stop", None)
        if not self.speaking or stop is None:
            return False
        try:
            stop()
        except Exception:  # noqa: BLE001
            return False
        return True

    def set_status(self, status: str) -> None:
        self.status = status
        if self.on_status:
            try:
                self.on_status(status)
            except Exception:  # noqa: BLE001 - UI callbacks must not break listening
                pass

    async def say(self, text: str) -> None:
        text = speakable(text)
        if not text:
            return
        self.speaking = True
        self.set_status("speaking")
        try:
            await asyncio.to_thread(self.speaker.say, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("speaking failed: %s", exc)
        finally:
            self.speaking = False
            self._quiet_until = time.time() + 0.4  # don't hear our own echo
            self.set_status("muted" if self.muted else "listening")

    async def handle_utterance(self, audio: Any) -> str:
        """One heard sentence; returns what was sent to Atulya ('' if nothing)."""
        try:
            text = await self.stt.transcribe(audio)
        except Exception as exc:  # noqa: BLE001
            logger.warning("speech-to-text failed: %s", exc)
            return ""
        if self.speaking:  # only a stop word matters; anything else is likely our own echo
            if _normalize(text) in STOP_WORDS:
                self.interrupt()
            return ""
        return await self.handle_text(text)

    async def handle_text(self, text: str) -> str:
        action, payload = self.session.on_utterance(text)
        if action == "prompt":
            await self.say(payload)
            return ""
        if action != "send":
            return ""
        self.last_heard = time.time()
        self.set_status("thinking")
        try:
            reply = await self.client.chat(payload)
        except AuthError:
            self.needs_sign_in = True
            await self.say("I need you to sign this device in again. Run atulya listen with the login option.")
            return payload
        except Exception as exc:  # noqa: BLE001
            logger.warning("Atulya unreachable: %s", exc)
            await self.say("I can't reach Atulya right now.")
            return payload
        self.session.on_reply(reply)
        await self.say(str(reply.get("response_text") or reply.get("response") or ""))
        return payload

    async def on_notification(self, data: dict[str, Any]) -> None:
        if self.muted or data.get("type") == "success":
            return
        message = str(data.get("desc") or data.get("message") or data.get("title") or "")
        if message:
            await self.say(message)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        self.set_status("muted" if self.muted else "listening")
        return self.muted

    async def heartbeat_loop(self) -> None:
        while True:
            try:
                await self.client.heartbeat({"state": self.status, "wake_word": self.wake_label,
                                             "stt": self.stt_label, "muted": self.muted,
                                             "last_heard": self.last_heard})
                self.needs_sign_in = False
            except AuthError:
                self.needs_sign_in = True
            except Exception as exc:  # noqa: BLE001
                logger.debug("heartbeat failed: %s", exc)
            await asyncio.sleep(self.heartbeat_interval)

    async def deliver_briefing(self) -> None:
        """Ask for the morning briefing and say it."""
        ask = "give me my morning briefing" + (f" for {self.briefing_location}" if self.briefing_location else "")
        try:
            reply = await self.client.chat(ask)
        except Exception as exc:  # noqa: BLE001
            logger.warning("briefing failed: %s", exc)
            return
        await self.say(str(reply.get("response_text") or reply.get("response") or ""))

    async def briefing_loop(self, poll: float = 30.0) -> None:
        while self.briefing is not None:
            if not self.muted and self.briefing.due():
                await self.deliver_briefing()
            await asyncio.sleep(poll)

    async def run(self, utterances: Any) -> None:
        """Listen forever: ``utterances`` is an async iterator of audio clips."""
        tasks = [asyncio.create_task(self.heartbeat_loop()), asyncio.create_task(self.briefing_loop()),
                 asyncio.create_task(self.client.notifications(self.on_notification))]
        try:
            async for audio in utterances:
                await self.handle_utterance(audio)
        finally:
            for task in tasks:
                task.cancel()


# ── audio ────────────────────────────────────────────────────────────
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

    def __init__(self, model: str = "base", hint: str = "Atulya"):
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
            from atulya.vani import pick_language

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


def make_stt(mode: str, client: Any, model: str = "base") -> Any:
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


# ── autostart ────────────────────────────────────────────────────────────
LABEL = "ai.atulya.listener"


def autostart_entry(system: str | None = None, python: str | None = None, home: Path | None = None,
                    args: list[str] | None = None, mode: str = "desktop") -> tuple[Path, str]:
    """(file to write, its contents) for this platform."""
    system = system or platform.system()
    python = python or sys.executable
    home = home or Path.home()
    args = list(args or [])
    if system == "Windows":
        pythonw = python[:-10] + "pythonw.exe" if python.lower().endswith("python.exe") else python
        path = home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / \
            "Atulya Listener.bat"
        line = " ".join(['start ""', f'"{pythonw}"', "-m", "atulya.shruti", *(f'"{a}"' for a in args)])
        return path, f"@echo off\r\n{line}\r\n"
    if system == "Darwin":
        path = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        program = "".join(f"\n    <string>{escape(a)}</string>" for a in [python, "-m", "atulya.shruti", *args])
        return path, (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f"  <key>Label</key>\n  <string>{LABEL}</string>\n"
            f"  <key>ProgramArguments</key>\n  <array>{program}\n  </array>\n"
            "  <key>RunAtLoad</key>\n  <true/>\n  <key>KeepAlive</key>\n  <true/>\n"
            "</dict>\n</plist>\n"
        )
    command = shlex.join([python, "-m", "atulya.shruti", *args])
    if mode == "systemd":
        path = home / ".config" / "systemd" / "user" / "atulya-listener.service"
        return path, (
            "[Unit]\nDescription=Atulya always-listening assistant\nAfter=network-online.target sound.target\n\n"
            f"[Service]\nExecStart={command} --no-tray\nRestart=on-failure\nRestartSec=5\n\n"
            "[Install]\nWantedBy=default.target\n"
        )
    path = home / ".config" / "autostart" / "atulya-listener.desktop"
    return path, (
        "[Desktop Entry]\nType=Application\nName=Atulya Listener\nComment=Always-listening Atulya assistant\n"
        f"Exec={command}\nX-GNOME-Autostart-enabled=true\n"
    )


def install(mode: str = "desktop", **kwargs) -> tuple[Path, str]:
    """Write the autostart file; returns (path, what to do next)."""
    path, content = autostart_entry(mode=mode, **kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if path.suffix == ".service":
        hint = "Enable it with: systemctl --user enable --now atulya-listener"
    elif path.suffix == ".plist":
        hint = f"Starts at next login, or now with: launchctl load {path}"
    else:
        hint = "Starts at your next login."
    return path, hint


def uninstall(mode: str = "desktop", **kwargs) -> bool:
    path, _ = autostart_entry(mode=mode, **kwargs)
    if path.exists():
        path.unlink()
        return True
    return False


# ── tray ────────────────────────────────────────────────────────────
STATUS_COLOURS = {
    "listening": (255, 153, 51),   # saffron
    "thinking": (244, 196, 48),    # turmeric
    "speaking": (46, 184, 92),     # India green
    "muted": (120, 120, 130),
    "sign-in": (240, 90, 68),      # sindoor
}


def tray_available() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
    except Exception:  # noqa: BLE001 - also no display on a headless machine
        return False
    return True


def icon_image(status: str, size: int = 64) -> Any:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2), fill=(10, 13, 31, 255))
    colour = STATUS_COLOURS.get(status, STATUS_COLOURS["listening"])
    pad = size // 5
    draw.ellipse((pad, pad, size - pad, size - pad), fill=(*colour, 255))
    dot = size // 8
    c = size // 2
    draw.ellipse((c - dot, c - dot, c + dot, c + dot), fill=(251, 246, 238, 255))
    return img


class TrayApp:
    def __init__(self, engine: Any, url: str, on_quit: Callable[[], None]):
        self.engine = engine
        self.url = url
        self.on_quit = on_quit
        self.icon: Any = None
        self._lock = threading.Lock()

    def _status(self) -> str:
        if getattr(self.engine, "needs_sign_in", False):
            return "sign-in"
        return str(getattr(self.engine, "status", "listening"))

    def update(self, _status: str = "") -> None:
        with self._lock:
            if self.icon is not None:
                status = self._status()
                self.icon.icon = icon_image(status)
                self.icon.title = f"Atulya — {status}"

    def run(self) -> None:
        """Blocks: the tray owns the main thread (required on macOS)."""
        import pystray

        def toggle(_icon: Any, _item: Any) -> None:
            self.engine.toggle_mute()
            self.update()

        def quit_app(icon: Any, _item: Any) -> None:
            self.on_quit()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem(lambda _item: f"Atulya — {self._status()}", None, enabled=False),
            pystray.MenuItem(lambda _item: "Unmute microphone" if self.engine.muted else "Mute microphone", toggle),
            pystray.MenuItem("Open Atulya", lambda _i, _t: webbrowser.open(self.url)),
            pystray.MenuItem("Quit", quit_app),
        )
        self.icon = pystray.Icon("atulya", icon_image(self._status()), "Atulya — listening", menu)
        self.engine.on_status = self.update
        self.icon.run()


# ── cli ────────────────────────────────────────────────────────────


def config_path() -> Path:
    if os.environ.get("ATULYA_AMBIENT_CONFIG"):
        return Path(os.environ["ATULYA_AMBIENT_CONFIG"])
    if platform.system() == "Windows" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Atulya" / "ambient.json"
    return Path.home() / ".config" / "atulya" / "ambient.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    try:
        return json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)  # it holds this device's sign-in token
    except OSError:
        pass
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atulya listen", description="Always-listening Atulya (wake word, tray icon).")
    p.add_argument("--url", help=f"Atulya server (default {default_url()})")
    p.add_argument("--token", help="Sign-in token (normally saved by --login)")
    p.add_argument("--login", action="store_true", help="Sign this device in and remember it")
    p.add_argument("--user", help="Username for --login")
    p.add_argument("--device", help="Name shown in Atulya (default: this computer's name)")
    p.add_argument("--wake", help="Wake phrases, comma-separated (default: hey atulya, atulya)")
    p.add_argument("--stt", choices=["auto", "local", "server"], help="Speech-to-text: local whisper or the server")
    p.add_argument("--model", help="Local whisper model (default base; multilingual, so it hears Hindi wake words too)")
    p.add_argument("--follow-up", type=float, help="Seconds to keep listening without the wake word after a reply")
    p.add_argument("--mic", help="Microphone device name or number")
    p.add_argument("--no-tray", action="store_true", help="Run without a tray icon (headless)")
    p.add_argument("--text", action="store_true", help="Type instead of talk (testing without a microphone)")
    p.add_argument("--install-autostart", nargs="?", const="desktop", choices=["desktop", "systemd"],
                   help="Start at login (desktop) or at boot on headless Linux (systemd)")
    p.add_argument("--remove-autostart", nargs="?", const="desktop", choices=["desktop", "systemd"])
    p.add_argument("--save", action="store_true", help="Save these options as the defaults")
    return p


def default_url() -> str:
    """Where sevak actually listens: ATULYA_HOST:ATULYA_PORT, default 127.0.0.1:8501.

    This used to be hard-coded to localhost:8000, so on a default install
    `atulya listen` dialled a port nothing was serving and failed at sign-in.
    A bind-all address cannot be dialled back, so it becomes the loopback.
    """
    host = (os.environ.get("ATULYA_HOST", "") or "127.0.0.1").strip()
    if host in ("0.0.0.0", "::"):  # binds every interface, but you still call home on one
        host = "127.0.0.1"
    port = (os.environ.get("ATULYA_PORT", "") or "8501").strip()
    return f"http://{host}:{port}"


def resolve(args: argparse.Namespace, cfg: dict[str, Any]) -> dict[str, Any]:
    """Options from flags, then environment, then the saved config, then defaults."""
    def pick(flag: Any, env: str, key: str, default: Any) -> Any:
        if flag not in (None, ""):
            return flag
        if os.environ.get(env):
            return os.environ[env]
        return cfg.get(key, default)

    return {
        "url": pick(args.url, "ATULYA_URL", "url", default_url()),
        "token": pick(args.token, "ATULYA_TOKEN", "token", ""),
        "device": pick(args.device, "ATULYA_DEVICE", "device", socket.gethostname() or "listener"),
        "wake": pick(args.wake, "ATULYA_WAKE_WORDS", "wake", ",".join(DEFAULT_WAKE_WORDS)),
        "stt": pick(args.stt, "ATULYA_AMBIENT_STT", "stt", "auto"),
        "model": pick(args.model, "ATULYA_WHISPER_MODEL", "model", "base"),
        "follow_up": float(pick(args.follow_up, "ATULYA_FOLLOW_UP", "follow_up", 0.0)),
        "mic": pick(args.mic, "ATULYA_MIC", "mic", None),
    }


async def _text_loop(engine: AmbientEngine) -> None:
    tasks = [asyncio.create_task(engine.heartbeat_loop()),
             asyncio.create_task(engine.client.notifications(engine.on_notification))]
    print('Type what you would say (e.g. "hey atulya, turn on the kitchen light"). Ctrl+C to stop.')
    try:
        while True:
            line = await asyncio.to_thread(input, "> ")
            await engine.handle_text(line)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        for task in tasks:
            task.cancel()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    # `atulya-listen` enters here without going through the atulya CLI, so without
    # this the .env written by install.py -- briefing time, wake model, a custom
    # port -- would be ignored and only the compiled-in defaults applied.
    from atulya.adhar import load_env

    load_env()
    args = build_parser().parse_args(argv)
    cfg = load_config()
    opts = resolve(args, cfg)

    if args.install_autostart or args.remove_autostart:
        from atulya import shruti as autostart

        if args.remove_autostart:
            removed = autostart.uninstall(mode=args.remove_autostart)
            print("Autostart removed." if removed else "Autostart wasn't installed.")
        else:
            path, hint = autostart.install(mode=args.install_autostart)
            print(f"Autostart installed: {path}\n{hint}")
        return 0

    if args.login:
        username = args.user or input("Atulya username: ")
        password = getpass.getpass("Password: ")
        try:
            opts["token"] = asyncio.run(AtulyaClient.device_token(opts["url"], username, password, opts["device"]))
        except AuthError as exc:
            print(f"Sign-in failed: {exc}")
            return 1
        args.save = True
        print(f"Signed in as {username} on {opts['device']}.")

    if args.save:
        path = save_config({**cfg, **{k: v for k, v in opts.items() if v not in (None, "")}})
        print(f"Saved settings to {path}")

    if not opts["token"]:
        print("This device isn't signed in yet. Run: atulya listen --url <server> --login")
        return 1


    client = AtulyaClient(opts["url"], opts["token"], opts["device"])
    wake_words = [w.strip() for w in str(opts["wake"]).split(",") if w.strip()]
    session = AmbientSession(WakeMatcher(wake_words), follow_up=opts["follow_up"])
    speaker = Speaker()

    if args.text:
        engine = AmbientEngine(client, stt=None, speaker=speaker, session=session, wake_label=wake_words[0])
        asyncio.run(_text_loop(engine))
        return 0

    stt = make_stt(opts["stt"], client, opts["model"])
    engine = AmbientEngine(client, stt=stt, speaker=speaker, session=session, wake_label=wake_words[0],
                           stt_label=getattr(stt, "label", ""),
                           briefing_at=os.environ.get("ATULYA_BRIEFING_AT", ""),
                           briefing_location=os.environ.get("ATULYA_BRIEFING_LOCATION", ""))
    mic_device = int(opts["mic"]) if str(opts["mic"] or "").isdigit() else opts["mic"]
    wake_model = os.environ.get("ATULYA_WAKE_MODEL", "")
    gate = WakeGate(wake_model) if wake_model else None
    mic = Microphone(device=mic_device, enabled=engine.accepts_audio, gate=gate,
                     active=lambda: engine.session.state != engine.session.IDLE)
    print(f'Listening for "{wake_words[0]}" on {opts["device"]} (speech-to-text: {engine.stt_label}).')


    if args.no_tray or not tray_available():
        try:
            asyncio.run(engine.run(mic.utterances()))
        except KeyboardInterrupt:
            pass
        return 0

    # The tray needs the main thread; listening runs alongside it.
    loop = asyncio.new_event_loop()
    runner = threading.Thread(target=lambda: loop.run_until_complete(engine.run(mic.utterances())), daemon=True)
    runner.start()

    def stop() -> None:
        loop.call_soon_threadsafe(loop.stop)

    TrayApp(engine, opts["url"], on_quit=stop).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

