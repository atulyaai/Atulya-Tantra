"""Voice-turn latency bench (PLAN M1-0): STT -> first LLM sentence -> TTS of that sentence.

Run: .venv\\Scripts\\python -m tools.voice_bench [--wav tests/assets/weather_tomorrow_tts.wav] [--runs 3]
Starts (or reuses) the local llama.cpp server. Times are wall clock on this machine.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from contextlib import aclosing

ROOT = Path(__file__).resolve().parents[1]
# A delta ending in '.' may be only the first half of a decimal (e.g. 20.5).
# Wait for following whitespace, or flush the remainder when the stream ends.
SENTENCE_END = re.compile(r"[.!?।]\s|\n")


async def _sentences(brain, toolbox, text: str, *, context=None, on_sentence=None,
                     fast_path: bool = True, receipts=None) -> list[tuple[str, float]]:
    """(sentence, seconds since request) for the first spoken sentence and the first real answer sentence."""
    from tools.plugins.brain import Message
    from tools.plugins.brain.engine import instant_ack
    from tools.plugins.voice.intents import match_intent, execute_intent

    from tools.plugins.brain.engine import _FILLERS, _INTENT_FILLERS
    # Acknowledgements and tool fillers ("One moment.") are not the answer.
    fillers = {phrase for phrase in _FILLERS.values() if phrase} | {phrase for _p, phrase in _INTENT_FILLERS}
    fillers.add("One moment.")
    ack = (instant_ack(text) or "").strip() if toolbox else ""
    if ack:
        fillers.add(ack)
    started = time.perf_counter()
    found: list[tuple[str, float]] = []
    buffer = ""
    messages = ([context] if context else []) + [Message(role="user", content=text)]
    language = "auto"
    if toolbox is not None and toolbox.context is not None and toolbox.context.profile is not None:
        language = toolbox.context.profile.get(toolbox.context.user_id).get("language", "auto")
    intent = match_intent(text, language=language) if fast_path and toolbox is not None else None

    async def direct_stream():
        if ack:
            yield ack + " "
        result = await execute_intent(intent, toolbox)
        if receipts is not None:
            receipts.append({"tool": intent.tool, "arguments": intent.arguments, "result": result.tool_result,
                             "spoken": result.text})
        yield result.text

    reply_stream = direct_stream() if intent is not None else brain.stream(messages, toolbox=toolbox)
    async with aclosing(reply_stream) as stream:
        async for chunk in stream:
            buffer += chunk
            while True:
                match = SENTENCE_END.search(buffer)
                if not match:
                    break
                sentence, buffer = buffer[:match.end()].strip(), buffer[match.end():]
                if sentence:
                    found.append((sentence, time.perf_counter() - started))
                    if on_sentence is not None:
                        await on_sentence(*found[-1])
                    # Stop at the first real answer sentence.
                    if sentence not in fillers:
                        return found
    if buffer.strip():
        found.append((buffer.strip(), time.perf_counter() - started))
        if on_sentence is not None:
            await on_sentence(*found[-1])
    return found


def to_16k_mono(wav_bytes: bytes) -> bytes:
    """Resample any PCM16 WAV to 16 kHz mono PCM16, the format the voice loop records (exercises the
    in-memory STT path instead of the decoder/temp-file path)."""
    import io
    import wave

    import numpy as np

    with wave.open(io.BytesIO(wav_bytes)) as source:
        rate, channels = source.getframerate(), source.getnchannels()
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        positions = np.arange(0, len(samples), rate / 16000)
        samples = np.interp(positions, np.arange(len(samples)), samples)
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(np.clip(samples, -32768, 32767).astype("<i2").tobytes())
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wav", default=str(ROOT / "tests" / "assets" / "weather_tomorrow_tts.wav"))
    parser.add_argument("--say", help="Synthesize this question with the local voice and use it as the input clip")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--no-tools", action="store_true", help="LLM without the toolbox")
    parser.add_argument("--user", default="admin", help="Local profile used by the API; never supplies credentials")
    parser.add_argument("--language", default="", help="Speech language override; otherwise uses the selected profile")
    parser.add_argument("--llm-only", action="store_true", help="Disable deterministic routing for a model-path comparison")
    parser.add_argument("--output", type=Path, help="Write complete sentences, timings and direct tool receipts as JSON")
    parser.add_argument("--tts-steps", type=int, choices=(2, 4, 8), help="Override spoken answer steps for comparison")
    args = parser.parse_args()

    from atulya.settings import Settings
    from tools.plugins.brain import Brain, OpenAICompatibleProvider
    from tools.plugins.brain.local_llm import LocalLlamaRuntime
    from tools.plugins.toolkit import VOICE_TOOLS, Toolbox
    from tools.plugins.registry import PluginContext, build_default_registry
    from atulya.auth import AuthStore
    from atulya.profiles import ProfileStore
    from atulya.voice_context import voice_context
    from tools.plugins.voice.local import LocalVoice
    from tools.plugins.voice.tts import LocalSupertonicTTS, voice_num_steps
    from tools.plugins.voice.cache import cache_speech

    settings = Settings.from_environment()
    import os
    stt = LocalVoice(settings.models_dir, stt_model=os.environ.get("ATULYA_STT_MODEL", "base").strip() or "base")
    tts = cache_speech(LocalSupertonicTTS(settings.models_dir), settings.data_dir / "voice-cache")
    runtime = LocalLlamaRuntime(settings.models_dir)
    provider = OpenAICompatibleProvider(name="Local", model="qwen3.5-2b", base_url="http://127.0.0.1:11435/v1",
                                           timeout_seconds=120)
    brain = Brain(provider, assistant_name=settings.assistant_name)
    # Same stores as /api/chat, but in a throwaway copy of the data folder: a bench run must not
    # create real reminders or memories. Only the profile (city, language, home) is copied.
    import shutil
    import tempfile
    from tools.plugins.personal.memory import PersonalMemory
    from tools.plugins.productivity.calendar import CalendarStore
    from tools.plugins.productivity.web_reminders import WebReminderStore
    from tools.plugins.toolkit import ActionQueue
    bench_dir = Path(tempfile.mkdtemp(prefix="atulya-bench-"))
    profile_store = ProfileStore(settings.data_dir)
    shutil.copy2(profile_store.path, bench_dir / profile_store.path.name)
    profiles = ProfileStore(bench_dir)
    chosen_language = args.language or profiles.get(args.user).get("language", "auto")
    action_view = ActionQueue(bench_dir).view()
    context = PluginContext("web", PersonalMemory(bench_dir), CalendarStore(bench_dir), args.user, profile=profiles,
                            reminders=WebReminderStore(bench_dir), actions=action_view,
                            is_admin=AuthStore(settings.data_dir).is_admin(args.user))
    toolbox = None if args.no_tools else Toolbox.for_registry(build_default_registry(), context).subset(VOICE_TOOLS, voice=True)
    audio = to_16k_mono(tts.synthesize(args.say) if args.say else Path(args.wav).read_bytes())
    rows = []
    answer_steps = args.tts_steps or voice_num_steps()

    async def measure():
        for run in range(1, args.runs + 1):
            t = time.perf_counter()
            text = stt.transcribe(audio, content_type="audio/wav", language=chosen_language)
            t_stt = time.perf_counter() - t
            timings = []
            receipts = []

            async def synthesize_sentence(sentence, at):
                t = time.perf_counter()
                await asyncio.to_thread(tts.synthesize, sentence[:1000], num_steps=answer_steps)
                timings.append((at, time.perf_counter() - t))

            found = await _sentences(brain, toolbox, text, context=voice_context(profiles, args.user),
                                     on_sentence=synthesize_sentence, fast_path=not args.llm_only, receipts=receipts)
            if not found:
                raise RuntimeError("The model produced no answer; no latency result can be reported.")
            (a0, s0), (a1, s1) = timings[0], timings[-1]
            rows.append({"run": run, "transcript": text, "route": "voice_fast" if receipts else "llm",
                         "stt_seconds": t_stt, "first_audio_ready_seconds": t_stt + a0 + s0,
                         "answer_audio_ready_seconds": t_stt + a1 + s1,
                         "sentences": [{"text": sentence, "at_seconds": at} for sentence, at in found],
                         "tool_receipts": receipts})
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps({"audio_readiness_only": True, "voice_tts_steps": answer_steps, "runs": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
            if run == 1 and not args.no_tools:
                saved = await asyncio.to_thread(LocalLlamaRuntime.save_voice_prefix_once)
                print(f"voice_prefix_saved={saved}")
            print(f"{run} | {t_stt:.2f} | {a0:.2f} | {s0:.2f} | {t_stt + a0 + s0:.2f} | "
                  f"{a1:.2f} | {s1:.2f} | {t_stt + a1 + s1:.2f} | {found[-1][0][:70]!r}")
    async def run_bench():
        try:
            # Warm-up: model loads are reported once, then excluded from per-turn rows.
            t = time.perf_counter()
            await asyncio.to_thread(stt.transcribe, audio, content_type="audio/wav", language=chosen_language)
            stt_load = time.perf_counter() - t
            t = time.perf_counter()
            await asyncio.to_thread(tts.synthesize, "Warming up.")
            await asyncio.to_thread(tts.warm_acknowledgements)
            print(f"cold: stt_first_call={stt_load:.2f}s tts_first_call={time.perf_counter() - t:.2f}s")
            print("run | stt | first_sentence_at | tts_first | first_audio | answer_sentence_at | tts_answer | answer_audio | answer")
            await measure()
        finally:
            await provider.aclose()

    try:
        started = time.perf_counter()
        prefix_on_disk = (runtime.slot_dir / runtime.VOICE_PREFIX_FILE).is_file()
        runtime.start()
        print(f"llm_server_ready={time.perf_counter() - started:.2f}s voice_prefix_restored_from_disk={prefix_on_disk}")
        asyncio.run(run_bench())
    finally:
        runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
