"""State machine: IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE (PLAN M1-3), with barge-in v1:
the wake word keeps running while Atulya thinks or speaks, and a hit stops playback, cancels the
reply stream (closing it aborts the model's generation) and listens again (PLAN M1-4)."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from .sentences import split_ready

logger = logging.getLogger(__name__)

IDLE, LISTENING, THINKING, SPEAKING = "IDLE", "LISTENING", "THINKING", "SPEAKING"
HISTORY_TURNS = 6


class VoiceLoop:
    def __init__(self, mic, wake, endpointer, client, player, *, language: str = "",
                 log_path: Path | None = None, greeting: str = "Yes?", clock=time.monotonic) -> None:
        self.mic, self.wake, self.endpointer = mic, wake, endpointer
        self.client, self.player = client, player
        self.language = language
        self.log_path = log_path
        self.greeting = greeting
        self.clock = clock
        self.history: list[dict] = []
        self.states: list[str] = []
        self.state = IDLE
        self._greeting_wav: bytes | None = None
        self.turn_log: list[dict] = []

    def _set(self, state: str) -> None:
        self.state = state
        self.states.append(state)

    async def _frame(self):
        return await asyncio.to_thread(self.mic.read, 0.5)

    async def wait_for_wake(self, *, max_frames: int | None = None) -> bool:
        self._set(IDLE)
        seen = 0
        while max_frames is None or seen < max_frames:
            frame = await self._frame()
            if frame is None:
                continue
            seen += 1
            if self.wake.feed(frame) is not None:
                return True
        return False

    async def listen(self) -> bytes | None:
        """One utterance as 16 kHz WAV, or None if nobody spoke."""
        self._set(LISTENING)
        if self.greeting:
            if self._greeting_wav is None:
                try:
                    self._greeting_wav = await self.client.synthesize(self.greeting, self.language or "auto")
                except Exception:
                    logger.warning("Greeting audio unavailable")
                    self._greeting_wav = b""
            if self._greeting_wav:
                self.player.play(self._greeting_wav)
                await asyncio.to_thread(self.player.wait, 3)
                self.mic.drain()  # do not record our own "Yes?"
        self.endpointer.reset()
        while True:
            frame = await self._frame()
            if frame is not None and self.endpointer.feed(frame):
                break
        return self.endpointer.wav() if self.endpointer.heard_speech else None

    async def _barge_in_watch(self) -> None:
        """Returns when the wake word is heard during THINKING/SPEAKING."""
        while True:
            frame = await self._frame()
            if frame is not None and self.wake.feed(frame) is not None:
                return

    async def respond(self, wav: bytes) -> bool:
        """Answer one utterance. Returns True if the user interrupted with the wake word."""
        ended = self.clock()
        self._set(THINKING)
        reply = asyncio.create_task(self._reply(wav, ended))
        watch = asyncio.create_task(self._barge_in_watch())
        try:
            done, _pending = await asyncio.wait({reply, watch}, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            self.player.stop()
            reply.cancel()
            watch.cancel()
            await asyncio.gather(reply, watch, return_exceptions=True)
            raise
        interrupted = watch in done and reply not in done
        if interrupted:
            self.player.stop()
            reply.cancel()
            try:
                await reply
            except (asyncio.CancelledError, Exception):
                pass
            self._write_log({"interrupted": True, "at": round(self.clock() - ended, 3)})
        else:
            watch.cancel()
            try:
                await watch
            except asyncio.CancelledError:
                pass
            reply.result()
        self.wake.reset()
        self.mic.drain()
        return interrupted

    async def _reply(self, wav: bytes, ended: float) -> None:
        timings: dict[str, float] = {}
        text = await self.client.transcribe(wav, self.language)
        timings["t_stt"] = self.clock() - ended
        if not text:
            return
        speech: asyncio.Queue[str | None] = asyncio.Queue()
        speaker = asyncio.create_task(self._speak(speech, timings, ended))
        spoken: list[str] = []
        pending: list[dict] = []
        buffer = ""
        route = "llm"
        try:
            stream = self.client.chat_stream(text, self.history[-2 * HISTORY_TURNS:])
            try:
                async for event in stream:
                    if "confirm" in event:
                        pending.append(event["confirm"])
                    if event.get("route"):
                        route = event["route"]
                    chunk = event.get("text") or ""
                    if event.get("error"):
                        chunk += " " + str(event["error"])
                    if chunk:
                        timings.setdefault("t_first_token", self.clock() - ended)
                        buffer += chunk
                        ready, buffer = split_ready(buffer, first=not spoken)
                        for sentence in ready:
                            spoken.append(sentence)
                            speech.put_nowait(sentence)
            finally:
                await stream.aclose()
            if buffer.strip():
                spoken.append(buffer.strip())
                speech.put_nowait(buffer.strip())
            for action in pending:
                # Never approved by voice here (that is M2-2); the action has NOT run.
                line = f"Waiting for your approval in the Atulya app: {action.get('summary', 'an action')}."
                spoken.append(line)
                speech.put_nowait(line)
            speech.put_nowait(None)
            await speaker
            await asyncio.to_thread(self.player.wait, 120)
        finally:
            if not speaker.done():
                speaker.cancel()
            await asyncio.gather(speaker, return_exceptions=True)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": " ".join(spoken)}]
        timings["total"] = self.clock() - ended
        self._write_log({"route": route, "text": text, **{key: round(value, 3) for key, value in timings.items()}})

    async def _speak(self, speech: asyncio.Queue, timings: dict, ended: float) -> None:
        """Synthesize sentence N+1 while sentence N plays (Player.play queues and returns)."""
        first = True
        while (sentence := await speech.get()) is not None:
            audio = await self.client.synthesize(sentence, self.language or "auto")
            if first:
                self._set(SPEAKING)
                timings["t_first_audio"] = self.clock() - ended
                first = False
            self.player.play(audio)

    def _write_log(self, entry: dict) -> None:
        self.turn_log.append(entry)
        line = "turn " + " ".join(f"{key}={value}" for key, value in entry.items() if key != "text")
        logger.info(line)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line} text={entry.get('text', '')!r}\n")

    async def run(self, *, turns: int | None = None) -> None:
        done = 0
        while turns is None or done < turns:
            await self.wait_for_wake()
            while True:  # a barge-in goes straight back to listening
                wav = await self.listen()
                if wav is None or not await self.respond(wav):
                    break
            self._set(IDLE)
            done += 1
