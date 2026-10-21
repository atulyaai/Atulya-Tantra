"""Voice loop building blocks and state machine with fake hardware (PLAN M1-2, M1-3, M1-4)."""
import asyncio
import io
import json
import queue
import wave

import httpx
import numpy as np
import pytest

from tools.voice_loop.audio_io import Player
from tools.voice_loop.client import ServerClient
from tools.voice_loop.loop import IDLE, LISTENING, SPEAKING, THINKING, VoiceLoop
from tools.voice_loop.sentences import split_ready
from tools.voice_loop.vad import Endpointer
from tools.voice_loop.wake import WakeDetector

FRAME = np.zeros(1280, dtype=np.int16)  # 80 ms


# --- sentences ---------------------------------------------------------------------------------

def test_split_ready_cases():
    assert split_ready("Tomorrow will be 20.", first=True) == ([], "Tomorrow will be 20.")  # maybe "20.5"
    assert split_ready("Tomorrow will be 20.5 degrees. Rain is ", first=True) == (
        ["Tomorrow will be 20.5 degrees."], "Rain is ")
    assert split_ready("Ok. Tomorrow is sunny and warm. ", first=True)[0] == ["Ok. Tomorrow is sunny and warm."]
    assert split_ready("Ok. Fine. ")[0] == ["Ok.", "Fine."]
    assert split_ready("कल धूप रहेगी। और ")[0] == ["कल धूप रहेगी।"]
    long, rest = split_ready("word " * 40)
    assert long and all(len(piece) <= 120 for piece in long) and len(rest) <= 120


# --- end of speech -----------------------------------------------------------------------------

def _endpointer(probabilities, **kwargs):
    script = iter(probabilities)
    return Endpointer(lambda chunk: next(script, 0.0), **kwargs)


def test_endpointer_ends_after_silence():
    # 2.5 chunks of 512 per 80 ms frame: speech for ~1 s, then silence.
    endpointer = _endpointer([0.9] * 30 + [0.1] * 100, silence_ms=600)
    frames = 0
    while not endpointer.feed(FRAME):
        frames += 1
    assert endpointer.heard_speech
    assert 15 <= frames <= 22  # ~1 s of speech + 600 ms of silence
    with wave.open(io.BytesIO(endpointer.wav())) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)


def test_endpointer_stops_at_max_and_on_no_speech():
    endpointer = _endpointer([0.9] * 1000, max_ms=8000)
    frames = 1
    while not endpointer.feed(FRAME):
        frames += 1
    assert frames == 100  # 8 s / 80 ms
    endpointer = _endpointer([0.0] * 1000, no_speech_ms=2000)
    frames = 1
    while not endpointer.feed(FRAME):
        frames += 1
    assert frames == 25 and not endpointer.heard_speech


# --- wake word ---------------------------------------------------------------------------------

def test_wake_detector_threshold_with_stub_model():
    class Model:
        scores = iter([0.1, 0.7])

        def predict(self, frame):
            return {"hey_jarvis": next(self.scores)}

    detector = WakeDetector("x.onnx", threshold=0.5, model_factory=lambda path: Model())
    assert detector.feed(FRAME) is None
    assert detector.feed(FRAME) == pytest.approx(0.7)


def test_real_wake_model_ignores_silence_and_noise():
    pytest.importorskip("openwakeword")
    from tools.voice_loop.wake import WAKE_DIR
    if not (WAKE_DIR / "hey_jarvis_v0.1.onnx").is_file():
        pytest.skip("wake models not downloaded")
    detector = WakeDetector(str(WAKE_DIR / "hey_jarvis_v0.1.onnx"))
    rng = np.random.default_rng(0)
    for index in range(int(30 / 0.08)):  # 30 s
        frame = FRAME if index % 2 else (rng.normal(0, 300, 1280)).astype(np.int16)
        assert detector.feed(frame) is None


# --- player ------------------------------------------------------------------------------------

def _wav(samples, rate=24000):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return out.getvalue()


class _FakeStream:
    def __init__(self, rate, callback):
        self.rate, self.callback = rate, callback

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass

    def pull(self, frames):
        out = np.zeros((frames, 1), dtype=np.int16)
        self.callback(out, frames)
        return out[:, 0]


def test_player_queues_and_stops_within_a_block():
    streams = []
    player = Player(stream_factory=lambda rate, cb: streams.append(_FakeStream(rate, cb)) or streams[-1])
    player.play(_wav(np.full(480, 7)))
    player.play(_wav(np.full(480, 9)))
    assert player.is_playing
    block = streams[0].pull(720)
    assert list(block[:480]) == [7] * 480 and list(block[480:]) == [9] * 240
    player.stop()
    assert not player.is_playing and not streams[0].pull(480).any()


# --- client ------------------------------------------------------------------------------------

def test_client_parses_event_stream_and_sends_token():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        events = [{"text": "Hello "}, {"confirm": {"id": "a1", "summary": "Open app: Notepad"}}, {"done": True}]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text="".join(f"data: {json.dumps(e)}\n\n" for e in events))

    async def run():
        client = ServerClient("http://atulya", "tok", transport=httpx.MockTransport(handler))
        events = [event async for event in client.chat_stream("hi", [{"role": "user", "content": "before"}])]
        await client.aclose()
        return events

    events = asyncio.run(run())
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["mode"] == "voice" and seen["body"]["stream"] is True
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "hi"}
    assert events[1]["confirm"]["id"] == "a1" and events[-1] == {"done": True}


# --- the loop ----------------------------------------------------------------------------------

class FakeMic:
    def __init__(self):
        self.frames = queue.Queue()

    def read(self, timeout=0.5):
        try:
            return self.frames.get(timeout=0.01)
        except queue.Empty:
            return None

    def drain(self):
        while not self.frames.empty():
            self.frames.get_nowait()


class FakeWake:
    """Fires on the frames whose first sample is 1 (the 'wake word')."""

    def feed(self, frame):
        return 0.9 if frame[0] == 1 else None

    def reset(self):
        pass


class FakeEndpointer:
    heard_speech = True

    def reset(self):
        self.count = 0

    def feed(self, frame):
        self.count += 1
        return self.count >= 3

    def wav(self):
        return b"RIFF-utterance"


class FakePlayer:
    def __init__(self):
        self.played, self.stopped = [], 0

    def play(self, audio):
        self.played.append(audio)

    def wait(self, timeout=None):
        return True

    def stop(self):
        self.stopped += 1


class FakeClient:
    def __init__(self, events, *, gap=0.0):
        self.events, self.gap = events, gap
        self.synthesized, self.log = [], []
        self.stream_closed = False

    async def transcribe(self, wav, language=""):
        return "what's the weather tomorrow?"

    async def chat_stream(self, text, history):
        try:
            for event in self.events:
                self.log.append(("event", event.get("text")))
                yield event
                await asyncio.sleep(self.gap)
            self.log.append(("stream_end", None))
        finally:
            self.stream_closed = True

    async def synthesize(self, text, language="auto"):
        self.synthesized.append(text)
        self.log.append(("synth", text))
        return f"wav:{text}".encode()


def _loop(client, mic=None):
    return VoiceLoop(mic or FakeMic(), FakeWake(), FakeEndpointer(), client, FakePlayer(), greeting="")


def _feed(mic, n=10):
    for _ in range(n):
        mic.frames.put(FRAME)


def test_loop_states_and_sentence_pipelining():
    events = [{"text": "Checking the weather. "}, {"text": "Tomorrow will be sunny, "},
              {"text": "with a high of 30.8 degrees. "}, {"text": "No rain."}, {"done": True}]
    client = FakeClient(events, gap=0.01)
    mic = FakeMic()
    loop = _loop(client, mic)
    _feed(mic)
    wav = asyncio.run(loop.listen())
    assert asyncio.run(loop.respond(wav)) is False
    assert loop.states == [LISTENING, THINKING, SPEAKING]
    assert client.synthesized == ["Checking the weather.", "Tomorrow will be sunny, with a high of 30.8 degrees.",
                                  "No rain."]
    assert loop.player.played == [f"wav:{s}".encode() for s in client.synthesized]
    first_synth = client.log.index(("synth", "Checking the weather."))
    assert first_synth < client.log.index(("stream_end", None))  # speech starts before the reply ends
    entry = loop.turn_log[-1]
    assert entry["route"] == "llm" and entry["t_first_audio"] <= entry["total"]
    assert loop.history[-1]["content"].startswith("Checking the weather.")


def test_pending_approval_is_spoken_never_approved():
    client = FakeClient([{"text": "I asked to open Notepad. "},
                         {"confirm": {"id": "a1", "summary": "Open app: Notepad"}}, {"done": True}])
    loop = _loop(client)
    asyncio.run(loop.respond(b"wav"))
    assert client.synthesized[-1] == "Waiting for your approval in the Atulya app: Open app: Notepad."


def test_loop_client_cannot_decide_actions():
    assert not hasattr(ServerClient, "decide") and not hasattr(ServerClient, "approve")


def test_barge_in_stops_playback_and_cancels_stream():
    events = [{"text": "Here is today's news. "}] + [{"text": f"Story {i} is long and important. "} for i in range(50)]
    client = FakeClient(events, gap=0.05)
    mic = FakeMic()
    loop = _loop(client, mic)

    async def run():
        task = asyncio.create_task(loop.respond(b"wav"))
        while not client.synthesized:
            await asyncio.sleep(0.01)
        wake = FRAME.copy()
        wake[0] = 1
        mic.frames.put(wake)
        interrupted = await task
        spoken = len(client.synthesized)
        await asyncio.sleep(0.2)
        return interrupted, spoken

    interrupted, spoken = asyncio.run(run())
    assert interrupted is True
    assert loop.player.stopped >= 1
    assert client.stream_closed
    assert len(client.synthesized) == spoken < 10  # nothing more was synthesized after the barge-in
    assert loop.turn_log[-1]["interrupted"] is True


def test_run_goes_from_wake_to_listening():
    client = FakeClient([{"text": "Sure thing, here you go."}, {"done": True}])
    mic = FakeMic()
    wake = FRAME.copy()
    wake[0] = 1
    mic.frames.put(wake)
    _feed(mic)
    loop = _loop(client, mic)
    asyncio.run(asyncio.wait_for(loop.run(turns=1), 5))
    assert loop.states[:3] == [IDLE, LISTENING, THINKING] and loop.states[-1] == IDLE


def test_cancelling_response_closes_stream_and_awaits_synthesis():
    class SlowClient(FakeClient):
        async def synthesize(self, text, language="auto"):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

    async def run():
        nonlocal started, finished
        started, finished = asyncio.Event(), asyncio.Event()
        client = SlowClient([{"text": "Checking the weather. "}] * 50, gap=0.05)
        loop = _loop(client)
        task = asyncio.create_task(loop.respond(b"wav"))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert finished.is_set() and client.stream_closed
        assert loop.player.stopped >= 1
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]

    started = finished = None
    asyncio.run(run())


def test_player_falls_back_to_first_output_when_windows_has_no_default():
    from types import SimpleNamespace

    from tools.voice_loop.audio_io import default_output_device

    devices = [{"max_output_channels": 0}, {"max_output_channels": 0}, {"max_output_channels": 8}]
    no_default = SimpleNamespace(default=SimpleNamespace(device=[1, -1]), query_devices=lambda: devices)
    assert default_output_device(no_default) == 2
    has_default = SimpleNamespace(default=SimpleNamespace(device=[1, 4]), query_devices=lambda: devices)
    assert default_output_device(has_default) is None
