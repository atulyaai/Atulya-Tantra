"""voice_bench feeds the loop's real input format and stops at the first answer sentence (AUDIT N8)."""
import asyncio
import io
import wave

import numpy as np

from tools import voice_bench


def _wav(rate, channels, seconds=0.5):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.ones(int(rate * seconds) * channels) * 1000).astype("<i2").tobytes())
    return out.getvalue()


def test_to_16k_mono():
    with wave.open(io.BytesIO(voice_bench.to_16k_mono(_wav(44100, 2)))) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert abs(w.getnframes() - 8000) <= 1


class _Brain:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream(self, messages, toolbox=None):
        for chunk in self.chunks:
            yield chunk


def test_stops_after_first_answer_sentence():
    found = asyncio.run(voice_bench._sentences(_Brain(["Owls can turn ", "their heads far. ", "More text. "]), None,
                                               "tell me about owls", fast_path=False))
    assert [sentence for sentence, _ in found] == ["Owls can turn their heads far."]


def test_tool_filler_is_not_the_answer():
    chunks = ["One moment. ", "I set a reminder for 6:40 PM. ", "Anything else? "]
    found = asyncio.run(voice_bench._sentences(_Brain(chunks), None, "remind me", fast_path=False))
    assert [sentence for sentence, _ in found] == ["One moment.", "I set a reminder for 6:40 PM."]
