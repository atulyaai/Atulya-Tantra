"""The always-listening loop: hear → wake word → Atulya → speak.

Pure logic lives here (speech segmentation, wake-word matching, conversation
state, the server client), so it can be tested without a microphone. Audio,
speech-to-text, the speaker and the tray icon are adapters in ``audio.py`` and
``tray.py``.

Conversation rules:
* "Hey Atulya, turn on the kitchen light" — wake word and command together.
* "Atulya." … "Yes?" … "turn on the kitchen light" — the next sentence within
  a few seconds is the command.
* When Atulya asks to confirm ("should I unlock the front door?"), the next
  "yes" or "no" is answered without the wake word.
* Optional follow-up window (``--follow-up 8``): keep talking without the wake
  word for a few seconds after each reply.
* Notifications (reminders, "someone is at the door") are spoken aloud.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
import time
from collections import deque
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
DEFAULT_WAKE_WORDS = ("hey atulya", "ok atulya", "hi atulya", "atulya")
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
    return " ".join(re.sub(r"[^\w\s']", " ", (text or "").lower()).split())


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
    text = re.sub(r"[*_`#>]+", "", text or "")
    text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", text, flags=re.MULTILINE)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(line if line[-1] in ".?!" else line + "." for line in lines)


# ── the engine ────────────────────────────────────────────────────────────
class AmbientEngine:
    """Glue: utterances in, speech out; heartbeats and notifications alongside."""

    def __init__(self, client: AtulyaClient, stt: Any, speaker: Any, session: AmbientSession | None = None,
                 heartbeat_interval: float = 30.0, wake_label: str = "hey atulya", stt_label: str = ""):
        self.client = client
        self.stt = stt
        self.speaker = speaker
        self.session = session or AmbientSession()
        self.heartbeat_interval = heartbeat_interval
        self.wake_label = wake_label
        self.stt_label = stt_label
        self.muted = False
        self.speaking = False
        self.status = "listening"
        self.last_heard: float | None = None
        self.needs_sign_in = False
        self._quiet_until = 0.0
        self.on_status: Callable[[str], None] | None = None

    def accepts_audio(self) -> bool:
        """Ignore the microphone while muted or while Atulya itself is talking."""
        return not self.muted and not self.speaking and time.time() >= self._quiet_until

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

    async def run(self, utterances: Any) -> None:
        """Listen forever: ``utterances`` is an async iterator of audio clips."""
        tasks = [asyncio.create_task(self.heartbeat_loop()),
                 asyncio.create_task(self.client.notifications(self.on_notification))]
        try:
            async for audio in utterances:
                await self.handle_utterance(audio)
        finally:
            for task in tasks:
                task.cancel()
