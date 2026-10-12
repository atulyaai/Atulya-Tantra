"""WAV -> OGG/Opus (Telegram voice notes) with PyAV, which Atulya already ships for speech input."""
from __future__ import annotations

import io


def wav_to_ogg_opus(wav: bytes, bitrate: int = 32000) -> bytes:
    import av

    source = av.open(io.BytesIO(wav), format="wav")
    output = io.BytesIO()
    target = av.open(output, mode="w", format="ogg")
    stream = target.add_stream("libopus", rate=48000)
    stream.bit_rate = bitrate
    stream.layout = "mono"
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
    for frame in source.decode(audio=0):
        for resampled in resampler.resample(frame):
            for packet in stream.encode(resampled):
                target.mux(packet)
    for resampled in resampler.resample(None):
        for packet in stream.encode(resampled):
            target.mux(packet)
    for packet in stream.encode(None):
        target.mux(packet)
    target.close()
    source.close()
    return output.getvalue()
