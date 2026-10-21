# PLAN — Step 0 (safety), M1 (voice loop), M2 (PC control)

Owner: planner. Inputs: `docs/GOAL.md`, `docs/team/RESEARCH.md`, `docs/team/AUDIT.md`, `docs/team/LOG.md`, the code as of 2026-10-20.

Status key: **ready** = the implementer can start now. **blocked** = waits on the thing named.

Rules for every step: add the tests named, run `.venv\Scripts\python -m pytest -q tests --ignore=tests/e2e` (baseline: 159 passed, 2 skipped), do the live check, and record the result and its evidence in `docs/team/LOG.md`. A box in GOAL/CAPABILITIES gets ticked only with that evidence.

## Decisions (resolving the earlier assumptions A1–A5 and questions R1–R5)

| # | Question | Decision | Source |
|---|---|---|---|
| A1/R1 | Wake word | **openWakeWord `openwakeword==0.6.0`, ONNX backend** (`inference_framework="onnx"`; tflite is Linux-only). Train a custom `atulya.onnx` with the project's synthetic-data notebook. Our own trained model is not bound by the NC licence of the bundled models. Interim for testing: the bundled `hey_jarvis` (CC BY-NC-SA, personal use only, never shipped as default). Fallback, and the choice for Android: sherpa-onnx keyword spotting (no training). Porcupine: rejected. | RESEARCH §1 |
| A2/R2 | Audio I/O | **`sounddevice` 0.5.x**, full-duplex. Install success on this Python/Windows still needs proving, which happens in Step V. | RESEARCH §2 |
| A3 | End of speech / VAD | **`silero-vad==5.1.2`** (MIT, ONNX), 30 ms chunks; utterance ends after 600 ms of silence, 8 s max. | RESEARCH §2 |
| A4/R3 | Latency budget | STT `base` int8 (already on disk) ≤ 0.8 s; LLM first sentence ≤ 1.2 s, with **thinking disabled** for voice (`enable_thinking: false` / `/no_think`), the biggest win; TTS first sentence ≤ 0.3 s; overhead ≤ 0.4 s. Measured in M1-0, not assumed. | RESEARCH §3, §4 |
| — | TTS engine | **sherpa-onnx** (Apache-2.0). The Supertonic-3 model is already on disk (LOG.md) and `LocalSupertonicTTS` exists. Piper (`piper-tts` 1.3 is GPL-3.0) stays an optional backend for the small server. Synthesize sentence by sentence. | RESEARCH §4, LOG |
| A5/R4 | Does the per-device token work on `/api/chat` and `/api/voice/*`? | **Not answered by research.** The first task of M1-3 is to check it in `atulya/server.py`/`atulya/auth.py`. If it doesn't work, M1-3 adds a narrow device-token dependency. | open (code check) |
| R5 | PDF library | **`pypdf` 5.x** (BSD) instead of pymupdf (AGPL). python-docx 1.1.x, openpyxl 3.1.x, python-pptx 1.0.x. | RESEARCH M2 |
| — | Barge-in | v1: **the wake word interrupts** (robust on laptop speakers). v2: speech interrupts, using WebRTC APM echo cancellation (`livekit` `AudioProcessingModule`) or a headset / Windows communications-mode AEC. | RESEARCH §2 |
| — | LLM server | Keep the existing `LocalLlamaRuntime` (`tools/plugins/brain/local_llm.py`, prebuilt llama.cpp). Make sure it uses a **recent** release (Qwen3.5) with `--jinja --cache-reuse 256 -fa on` and a fixed system prompt so the prefix cache hits. | RESEARCH §3 |

Questions still open for the owner (from RESEARCH "Open questions"): (1) Does the PC have a GPU? That picks the Vulkan llama.cpp build and the Whisper size (affects M1-0 tuning only). (2) The GPL Piper decision is moot for the PC, since sherpa-onnx is chosen. (3) OSRM region: M3, not this plan.

---

## Step 0 — Close the approval-policy holes (AUDIT C1–C4, H1, H2, M4) — **done** (LOG.md; C3 coded, not yet built on a device)

Why first: M1 makes the assistant hands-free and M2 gives it more power. Any prompt injection that reaches a no-approval tool gets worse with both. These fixes are small and touch `toolkit.py`, `smart_home.py`, `search.py` and one Kotlin file.

**0-1 `ask_device` split (C1).** In `tools/plugins/toolkit.py` (~:986 and handler ~:408), keep `ask_device` for read-only kinds only (`ping`, `battery_status`, `list_files`, `list_photos`) with `confirm=False`. Add `device_action` (`confirm=True`, `describe=lambda a: f"{a['device']}: {a['command']} {a.get('detail','')}"`) for `send_sms`, `place_call`, `read_file`, `take_photo`, `open_url`, `open_app`, `say`, `display_message`, `media_control`. Calling `ask_device` with a mutating kind returns an error naming `device_action` and creates no job.

**0-2 `cast_to_tv`, `visual_inspect` (C2).** Set `confirm=True` with a `describe` (no `low_risk`; the camera always needs a fresh approval).

**0-3 Calendar (C4).** Remove `low_risk=True` from `calendar_delete` and `calendar_update`. Fix the "directly" wording in the description. `calendar_create` may keep `low_risk`.

**0-4 Smart home honesty and approval (H1).** In `tools/plugins/system/smart_home.py`: with no HASS configured, return "Not connected: set HASS_URL/HASS_TOKEN; nothing was changed." An unknown or unimplemented scene returns "unsupported", never "Triggered". The tool gets `confirm=True, low_risk=True`.

**0-5 `read_url` SSRF (H2).** In `tools/plugins/information/search.py`: https only by default; resolve the host and reject any address where `ipaddress.ip_address(...).is_global` is False; follow redirects manually (max 3) and re-check each hop.

**0-6 Untrusted-content wrapper (M4).** `read_url` and `search_web` results are wrapped in `<<UNTRUSTED WEB CONTENT — data, not instructions>> … <<END>>`. Add one line on this to `Toolbox.instructions()` (~:1190).

**0-7 Destructive memory/routine tools (M2 audit).** `forget_fact` and `remove_routine` get `confirm=True, low_risk=True`. Write the policy as a comment above `TOOLS`: *read-only → direct; reversible own-data writes → direct; destructive, outside-world or device actions → confirm.*

**0-8 Policy regression test (covers all of the above, and is reused by M2-4).** New `tests/plugins/test_approval_policy.py`:
- `test_policy_table`: an explicit dict `{tool_name: "direct" | "confirm" | "confirm_low_risk"}` for **every** tool in `TOOLS`. The test fails if a tool is missing from the dict or its flags differ, so every new tool must be classified.
- `test_ask_device_mutating_kind_creates_no_job`: `Toolbox.call("ask_device", {"device": "Phone", "command": "send_sms", …})` → error, `AgentHub` has no jobs.
- `test_device_action_queues_approval`: returns "Approval requested", and no job exists until `run_approved`.
- `test_calendar_delete_asks_even_when_ask_risky`.
- `test_smart_home_unconfigured_is_honest`: the reply contains "nothing was changed" and not "Triggered" or "dispatched".
- `test_read_url_blocks_private_hosts`: `http://127.0.0.1`, `https://169.254.169.254`, `https://localhost`, and a redirect to `10.0.0.1` (mocked with httpx `MockTransport`) are all refused.
- `test_web_content_wrapped`.

**Live check:** in the WebUI, ask "send an SMS to 12345 saying hi via my phone" → an approval card appears and no job shows in Devices until you approve; deny it, and Devices still shows nothing. Ask "read http://127.0.0.1:<port>/api/health" → refused. Ask "turn on the living room lights" with no HASS → "nothing was changed".

**Deferred (not blocking M1/M2; schedule before M5):** C3 Android `send_sms_direct`/`call_direct` (remove them, or add a native confirm dialog in `MainActivity.kt`); H4 persistent approval queue (SQLite with status, which M5 needs); M1-audit Telegram approve/deny buttons; H3 Linux secrets (chmod 600 plus a test); L1–L4. The auditor can track these; the planner will add them to the M5 plan.

---

## Step V — Install the voice dependencies into `.venv` — **done** (LOG.md; silero-vad runs via onnxruntime, not the torch package)

LOG.md: none of `faster_whisper`, `sherpa_onnx`, `openwakeword`, `onnxruntime`, `sounddevice` import in `.venv` today.

- Pin in the project's voice requirements, in the same file that already lists `faster-whisper>=1.1` and `sherpa-onnx>=1.13.8,<2` (keep that existing sherpa pin; RESEARCH's "1.12.x" is older than the repo's floor):
  - `faster-whisper>=1.1,<1.3` and `av<19` (`LocalVoice._pyav_supported` refuses PyAV ≥ 19)
  - `sherpa-onnx>=1.13.8,<2`
  - `onnxruntime>=1.17`
  - `openwakeword==0.6.0`
  - `silero-vad==5.1.2`
  - `sounddevice>=0.5,<0.6`
  - M2 additions: `pypdf>=5,<6`, `python-docx>=1.1,<1.2`, `openpyxl>=3.1,<3.2`, `python-pptx>=1.0,<1.1`, `pycaw==20240316`, `psutil>=7,<8`
  - Before pinning, confirm each version with `.venv\Scripts\python -m pip index versions <pkg>`; record the exact resolved versions in LOG.md.
- Install: `.venv\Scripts\python -m pip install -r <that file>`, then download the openWakeWord base models (`openwakeword.utils.download_models()`) into `models/voice/wake/` (add this to `tools/bootstrap.py` next to the Whisper download).
- Update `tools/plugins/voice/setup.py`'s closing message (it still says "Speech output uses the browser's built-in voice").
- Test: `tests/voice/test_voice_deps.py`: imports each module, and checks `LocalVoice(models_dir).ready` and `LocalSupertonicTTS(models_dir).ready` are True. Mark it `skipif` when the env var `ATULYA_SKIP_VOICE_DEPS=1` is set, for CI without models.
- Live check: `.venv\Scripts\python -c "import sounddevice as sd; print(sd.query_devices())"` lists the mic and speakers; `curl -F "audio=@tests/assets/weather_tomorrow.wav;type=audio/wav" http://127.0.0.1:<port>/api/voice/transcribe` returns text; `POST /api/voice/synthesize` returns a playable WAV.

---

## M1 — The voice loop (v3, rebuilt around the i3-9100F measurements)

### What the measurements say (LOG.md "M1-1 and M1-0": i3-9100F, 4 cores, no GPU)
- **STT** warm, beam 1: `base` takes 0.95 s; `tiny.en` takes **0.61 s**. Only `tiny.en` fits the 0.8 s budget, and it understands English only.
- **TTS** (Supertonic int8, one 4 s sentence, idle CPU): 8 steps 1.46 s, 4 steps 1.14 s, 2 steps 0.66 s. While llama-server is running it takes **2–3 s**, because both compete for the 4 cores.
- **LLM with all 71 tool schemas:** the first answer sentence arrives after 11.9–41.2 s, so answer audio comes at 16–46 s. Without tools the first sentence takes 2.9–7.0 s, but then the model cannot answer. The bottleneck is processing the system prompt and the tool schemas.
- **Wrong answer:** the voice turn carried no user context, so the weather reply was "share your location".
- **Runtime facts:**
  - Thinking is already off (`--reasoning-budget 0`).
  - The runtime also loads `--mmproj` (vision) whenever that file exists.
  - It runs `--ctx-size 4096`, `--parallel 1` and 3 threads; 71 schemas barely fit in 4096 tokens.

### Realistic M1 target for this PC (in place of "< 3 s" until there is a GPU)
| Metric (from end of speech) | Target on i3-9100F | How |
|---|---|---|
| T1 first audio (acknowledgement) | **≤ 1.0 s** | tiny.en 0.6 s + an acknowledgement WAV rendered in advance (M1-B4) |
| T2 answer audio, fast path (weather, time, volume, media, open app) | **≤ 3.0 s** median, ≤ 4 s p90 | a fixed set of matched phrases, no LLM (M1-B6) |
| T3 answer audio, LLM path with one tool call | **≤ 8 s** median, ≤ 12 s p90 | tool subset + cached prefix + 4-step TTS |
| Correctness | 10/10 "what's the weather tomorrow?" correct for the saved city | context in the voice turn (M1-B5) |

On this PC the GOAL wording ("< 3 s") holds for **fast-path questions only**. Proposed new "Done when" line for the owner, who owns GOAL.md: *"first audio ≤ 1 s; weather/time answer ≤ 3 s, 10/10; other questions ≤ 8 s median on the reference PC."* After each step, re-measure with `tools/voice_bench.py` and add the numbers to **Measurements**.

### Order
M1-B1 → M1-B2 → M1-B3 and M1-B4 in parallel → M1-B5 → M1-B6 → bench gate → M1-2 … M1-6 (the mic loop). **All M1-B steps are ready.**

### ⛔ Blocker on every M1 live check: B27, no Windows speaker (owner step)
Windows has no default output: only a Realtek WDM-KS endpoint, and the default is -1. While WDM-KS plays, the Brio mic saturates or returns NaN, so the acoustic loopback test failed (no wake word, no transcription). The code fallback to the first output device is in place and tested (`tests/voice/test_voice_loop.py`), but it can't fix the audio itself.
- **Owner:** Windows Settings → System → Sound → Output, enable the Realtek speakers (or connect a headset). Then re-run the loopback test: play "Hey Jarvis, what is the weather tomorrow?" on the speakers, record it on the Brio, and check that the wake word fires and the speech is transcribed.
- **Until the loopback test passes**, the following are **blocked on B27**:
  - the M1-B4/B6 T1/T2 live checks that involve playback;
  - the M1-2 wake test with real audio;
  - the M1-3 10/10 check;
  - the M1-4 barge-in check.

  The benches that don't use the speaker (`tools/voice_bench.py`, unit tests) can still run.

### M1-B1 Voice-mode tool subset — **implemented locally; live performance target pending**
**Change:**
- `tools/plugins/toolkit.py`:
  - add `VOICE_TOOLS = ("get_weather", "get_time", "create_reminder", "list_reminders", "open_app", "search_files", "media_control", "get_news", "remember_fact")`;
  - add `Toolbox.subset(names) -> Toolbox`, which keeps the context and the plugin enable rules;
  - add `instructions(voice=True)`: about 5 lines, no skills list, and "answer in 1–2 spoken sentences, no markdown".
- `atulya/server.py` `/api/chat`: new optional request field `mode: "voice"` picks the subset and the short instructions. Text chat stays as it is.
- `tools/voice_bench.py`, and later `tools/voice_loop/client.py`, send `mode: "voice"`.
- A request outside the subset gets "I can do that in the app/chat", never a silent failure.

**Test:**
- `tests/plugins/test_toolkit.py::test_voice_subset`: exactly these schemas, and a disabled plugin still removes its tools.
- `tests/core/test_chat_voice_mode.py`: a stub provider gets ≤ 9 tools when `mode="voice"` and all tools otherwise.

**Live check:** run `python -m tools.voice_bench --runs 5` in voice mode and record the LLM first-sentence time (it should be far below 11.9 s).

### M1-B2 Fixed system prefix and prompt cache — **ready**
**Prompt order:**
1. Fixed persona, voice instructions and the 9 tool schemas, byte-identical every turn.
2. Context block for this turn.
3. The last 4 turns.
4. The user's message.

Nothing that changes (clock, date, city) goes in part 1; that belongs in the context block (M1-B5).

**llama-server flags** (`tools/plugins/brain/local_llm.py`):
- add `--cache-reuse 256`, `--slot-save-path <data>/llama-slots`, `--threads 4 --threads-batch 4`, and `-fa on` if the build accepts it on CPU;
- add `--mmproj` only when `ATULYA_VISION=1` (it stays off for voice on this PC);
- requests send `cache_prompt: true`.

**Warm-up:**
- At startup, send one voice request with an empty user turn, then `POST /slots/0?action=save` with filename `voice-prefix.bin`.
- On restart, call `action=restore`.

**Test:**
- `tests/providers/test_local_llm_args.py`: the command line includes `--cache-reuse` and `--slot-save-path`, and has no `--mmproj` without the env var.
- `tests/core/test_voice_prompt_prefix.py`: two turns with different times and cities give byte-identical prefixes up to the context block.

**Live check:**
- On the second turn, the llama-server log shows a cache hit, with `n_past` ≈ the prefix tokens.
- The bench reports the LLM first-sentence time with and without the cached prefix.

### M1-B3 STT model chosen by language — **implemented locally; latency and Hindi accuracy gates unmet**
**Change:**
- `tools/plugins/voice/local.py`: `LocalVoice` holds two models, each loaded lazily and each unloaded when idle.
  - English (`language` starts with `en`, or is empty and the profile is English) uses `ATULYA_STT_MODEL_EN`, default `tiny.en`.
  - Hindi and other languages use `ATULYA_STT_MODEL`, default `base`.
- `ready` checks both model folders; both are already on disk.
- The voice loop and the bench pass the profile's `language` with every request.

**Test:** `tests/voice/test_local_stt.py::test_model_by_language`. With a stub model, `en` uses tiny.en, `hi` uses base, and each is loaded once.

**Live check:** English STT ≤ 0.65 s in the bench, and a Hindi clip still transcribes with base.

### M1-B4 Cached acknowledgements and voice quality — **implemented locally; latency gate pending; owner selected 8 steps**
**Change:**
- The original four-step proposal was superseded by the owner: voice replies, read-aloud and cached acknowledgements default to **8 steps**. Eight steps were explicitly selected after samples were supplied. Step count controls synthesis quality, not playback volume.
  - `ATULYA_VOICE_TTS_STEPS` can separately configure voice answers; the API/WebUI pass the voice mode explicitly. Keep the owner-selected default at 8. Samples and the selection are recorded in LOG.md and output/voice-validation/quality-samples.json.
- At startup, render the acknowledgement phrases at 8 steps into `data/voice-cache/<sha1>.wav`. These are `engine._INTENT_FILLERS` and `engine._FILLERS`, plus "Yes?" after the wake word.
- `/api/voice/synthesize` serves exact cache hits straight from disk.
- The loop plays the acknowledgement as soon as STT returns.
- Measure CPU contention. If TTS takes > 2 s while the LLM is generating, run TTS on 1 thread and note it in LOG.md.

**Test:** `tests/voice/test_tts.py`:
- `test_ack_cache_hit`: a cached phrase returns without calling the engine;
- `test_voice_steps_default`.

**Live check:** T1 ≤ 1.0 s in the bench, 10/10.

### M1-B5 User context in the voice turn — **implemented locally; owner weather gate pending**
**Change:**
- In voice mode, `atulya/server.py` builds a context block from `atulya/profiles.py` with:
  - `preferred_name`, `city` and `language`;
  - the device location if it is recent, otherwise `places()["home"]`;
  - the local date and time.
  - Example: `Context: user=Aj; city=Delhi (28.61,77.21); now=Tue 2026-10-20 18:05 IST; language=en`.
- `get_weather` with no place uses the device location, then home (`_near(ctx)`), then the profile city. It asks for a location only when none of these exist, and then says where to set one.
- `tools/voice_bench.py --user <id>` runs the bench as that profile.

**Test:**
- `tests/plugins/test_location_weather.py::test_weather_defaults_to_profile_city`: with only a profile city, the weather is fetched for that city and the reply never says "share your location".
- The prefix test checks that the context block contains the city and the time.

**Live check:** the bench with `--user <owner>` returns the real forecast for the saved city 10/10, checked against Open-Meteo.

### M1-B6 Fast path for the most common voice requests — **implemented locally for English replies; live gate pending**
**Change:**
- New `tools/plugins/voice/intents.py`, called from `/api/chat` in voice mode before the LLM (next to the existing `command_plugins.dispatch`).
- Fixed patterns (English plus a few Hindi forms) for:
  - weather today or tomorrow, optionally "in <place>";
  - time and date;
  - volume up, down and mute;
  - play, pause and next;
  - "open <app>".
- A match runs the same tool through `Toolbox.call`, so the approval rules still apply, and turns the result into one spoken sentence with a template.
- Anything that doesn't match goes to the LLM.
- This adds no new capability, only a faster route to existing tools.

**Test:** `tests/voice/test_intents.py`:
- about 20 phrasings map to the expected tool and arguments;
- "weather for my trip to Goa next month" does not match;
- `open_app` still returns "Approval requested".

**Live check:** "what's the weather tomorrow?" gives T2 ≤ 3.0 s median over 10 runs, with a correct forecast.

### Bench gate (before the mic loop) — ready after M1-B6
**Run:** `python -m tools.voice_bench --user <owner> --runs 10` for each of:
- "what's the weather tomorrow?" (fast path);
- "remind me in 10 minutes to call mom" (LLM + tool);
- "what's in the news" (LLM + tool).

Record T1/T2/T3 in **Measurements**.

**If T3 p90 > 12 s:**
- keep 2 turns of history;
- set voice `max_tokens` to 80;
- consider Qwen3.5-0.8B as the model for voice-only routing.

### M1-2 … M1-6 — **ready** after the bench gate
- The steps are unchanged from v2; their full text is below.
  - M1-2: mic, wake word and end-of-speech detection. Silero runs through onnxruntime from `models/voice/wake/silero_vad.onnx`, as LOG.md describes.
  - M1-3: the loop, which sends `mode: "voice"`.
  - M1-4 and M1-4b: barge-in, v1 and v2.
  - M1-5: the "Atulya" wake word.
  - M1-6: start with Windows.
- The M1-3 live check now uses the targets in the table above.

### What a GPU would change
| | i3-9100F (now) | Entry GPU, 6–8 GB (Vulkan/CUDA llama.cpp) |
|---|---|---|
| LLM prompt processing | the bottleneck (tens of tokens/s) | hundreds to thousands of tokens/s: all 71 tools fit in voice mode and the fast path becomes optional |
| LLM generation | shares 4 cores with TTS | on the GPU: no CPU contention for STT and TTS |
| Model size | 2B Q4 | 4B–8B Q4: better tool choice and answers |
| STT | tiny.en (English only) | `small`/`base` multilingual on CUDA in about 0.2 s: one model for English and Hindi |
| TTS | 4 steps (quality traded for speed) | 8 steps in about 1.5 s with no contention |
| M1 target | T1 ≤ 1 s, fast path ≤ 3 s, LLM ≤ 8 s | the original "< 3 s for everything" becomes realistic |
| Code changes | — | `_gpu_layers()` already exists; Vulkan runtime asset, `--n-gpu-layers 99`, and a new `ATULYA_STT_DEVICE=cuda` switch |

### v2 text for M1-0 … M1-6 (kept for reference; M1-0 and M1-1 are done, see LOG.md)

### M1-0 Latency baseline — **done** (LOG.md)
- Create `tools/voice_bench.py`: loads `tests/assets/weather_tomorrow.wav` (record it once), then times `LocalVoice.transcribe`, the first sentence from `Brain.stream("what's the weather tomorrow?")` with thinking off, and `LocalSupertonicTTS.synthesize` of that sentence. It prints a table.
- Also check `local_llm.py`'s llama.cpp release and flags against RESEARCH §3; disable thinking for voice turns (a request flag `voice: true` on `/api/chat` → `chat_template_kwargs: {"enable_thinking": false}`).
- Test: `tests/core/test_voice_flag.py`: `voice: true` reaches the provider as thinking-off (stub provider).
- Live check: run the bench and paste the numbers under **Measurements** below. If STT is > 0.8 s, try `tiny.en`; if TTS is > 0.3 s, lower `num_steps`.

### M1-1 STT: raw WAV path with no temp file — **done** (LOG.md)
- In `tools/plugins/voice/local.py` `LocalVoice.transcribe`: for 16 kHz mono PCM16 `audio/wav`, decode with `wave`+numpy and pass the float32 array to `model.transcribe`. Other formats keep the temp-file path. The interface does not change.
- Test: `tests/voice/test_local_stt.py`: a stub `WhisperModel` receives an `ndarray` for WAV and a path for webm.
- Live check: the bench's STT time drops; the transcription is unchanged.

### M1-2 Client building blocks — **ready** (after the bench gate)
New package `tools/voice_loop/`:
- `audio_io.py`: `Mic` (sounddevice `InputStream`, 16 kHz mono int16, 80 ms frames → queue); `Player` (`play(pcm|wav)`, `stop()` effective within 50 ms, `is_playing`).
- `wake.py`: `WakeDetector(model=ATULYA_WAKE_MODEL or "hey_jarvis", threshold=0.5)`, `feed(frame) -> float|None`, using an openWakeWord `Model(..., inference_framework="onnx")`.
- `vad.py`: `Endpointer(silence_ms=600, max_ms=8000)` on silero-vad; `feed(frame) -> bool` (True when the utterance is done); `wav() -> bytes`.
- Tests: `tests/voice/test_endpointer.py` (a scripted speech-probability stub: speech then 700 ms silence → done; 9 s of speech → done at max). `tests/voice/test_wake.py` (a recorded `tests/assets/hey_jarvis.wav` → hit; 30 s of silence or noise → no hit; skipped if openwakeword is missing).
- Live check: `python -m tools.voice_loop --wake-test` prints `WAKE 0.xx` on the wake word. Ten minutes of normal talk or TV gives ≤ 1 false wake.

### M1-3 The loop: wake → record → STT → streamed chat → sentence TTS → play — **blocked on M1-2** (and on the R4 check, done as part of this step)
- **R4 check first:** read `atulya/auth.py`/`server.py` for how `/api/chat`, `/api/voice/transcribe` and `/api/voice/synthesize` authenticate. If the device token (`ATULYA_AGENT_TOKEN`) is not accepted, add an owner-only device-token dependency to those three routes, with a test in `tests/core/test_device_token_voice.py` (valid → 200, wrong → 401, a token from a non-owner device → 403).
- `tools/voice_loop/client.py`: `ServerClient(url, token)` with `transcribe(wav) -> str`, `chat_stream(text, history) -> AsyncIterator[str]` (`stream: true, voice: true`), `synthesize(text) -> bytes`, `approve(id)`, `deny(id)`.
- `tools/voice_loop/sentences.py`: `split_ready(buffer) -> (sentences, rest)`; cuts on `. ! ? ।` or newline, or at about 120 chars; the first chunk must be ≥ 20 chars.
- `tools/voice_loop/__main__.py`: states `IDLE → LISTENING → THINKING → SPEAKING (→ CONFIRMING) → IDLE`. It synthesizes sentence N+1 while sentence N plays (`instant_ack` and tool fillers from `engine.py` are spoken too), keeps 6 turns of history, and logs `turn t_stt= t_first_token= t_first_audio= total=` per turn to `logs/voice_loop.log`.
- Tests: `tests/voice/test_sentences.py`; `tests/voice/test_loop_states.py` with a fake mic, wake detector, client and player. It asserts the state order, one synthesize call per sentence, and that the first synthesize starts before the stream ends.
- **Live check (the GOAL M1 "Done when"):** server running, `python -m tools.voice_loop`, no clicks. Say "<wake word>, what's the weather tomorrow?" 10 times. Pass = 10/10 correct spoken answers and `t_first_audio` < 3.0 s on every log line. The log lines are the receipt in LOG.md. Run it first with `hey_jarvis`, then again after M1-5 with "Atulya".

### M1-4 Barge-in v1 (wake word interrupts) — **blocked on M1-3**
- The mic and `WakeDetector` keep running during SPEAKING. On a hit: `Player.stop()`, cancel the chat-stream task (closing the HTTP stream aborts the llama.cpp request) and any pending TTS, then go to LISTENING.
- Test: `test_loop_states.py::test_barge_in`: the wake fires mid-speech → `stop` is called, the stream is cancelled, no further synthesize calls happen, and the state is LISTENING.
- Live check: "tell me today's news", then say the wake word during sentence 2. Audio stops within 300 ms and the new question is answered. 5/5.

### M1-4b Barge-in v2 (plain speech interrupts) — **blocked on M1-4 and an AEC spike**
- Spike: WebRTC APM through `livekit`'s `AudioProcessingModule` on the mic stream, fed the speaker reference from `Player`. Compare against the headset and Windows communications-mode options. Adopt it only if self-trigger is ≤ 1 in 20 replies on laptop speakers. Silero ≥ 250 ms of speech → interrupt.
- Test and live check: as in M1-4, with speech instead of the wake word.

### M1-5 Custom "Atulya" wake word — **ready to train now** (independent of code), integration blocked on M1-2
- Train `atulya.onnx` with openWakeWord's synthetic-data notebook (Piper-generated positives, including Hindi-accented variants), and place it at `models/voice/wake/atulya.onnx`. Make it the default in `wake.py`; `ATULYA_WAKE_MODEL` overrides it.
- If accuracy is poor: use sherpa-onnx KWS with an "Atulya" keyword (no training), behind the same `WakeDetector` interface.
- Test: `tests/voice/test_wake.py` gets `atulya_*.wav` positives (5) and negatives ("actually", "a tool", "Aditya").
- Live check: 20 tries from 2 m away → ≥ 18 detected; 1 h of room noise → ≤ 1 false wake. Then rerun the M1-3 live check.

### M1-6 Start with Windows — **blocked on M1-3**
- `start.bat`: opt-in `ATULYA_VOICE_LOOP=1` launches `python -m tools.voice_loop`. `tools/selftest.py` reports mic present, wake model loaded, and STT/TTS ready.
- Test: the selftest output includes those keys.
- Live check: reboot → log in → wake word → answer.

---

## M2 — It controls the PC

### M2-1 Close app, lock screen, set volume — **ready** (Step 0 and Step V done)
- `tools/plugins/system/actions.py`: `close_app(name)` matches against `psutil` running processes via the existing `find_app`/`_norm` and never runs a raw string; `lock_screen()` uses `user32.LockWorkStation`; `set_volume(percent)` uses pycaw.
- `toolkit.py`: `close_app` (confirm), `lock_screen` (confirm, low_risk), `set_volume` (confirm, low_risk). Add them to the policy table and to `engine._FILLERS`.
- Test: in `test_approval_policy.py` the table covers them; `tests/plugins/test_pc_actions.py` checks that a monkeypatched process list refuses unknown names and that `set_volume` clamps to 0–100.
- Live check (after M2-2): by voice, "close Notepad" → spoken approval → "yes" → Notepad is closed; "lock the screen" locks it; "volume 30" sets it.

### M2-2 Spoken approvals — **blocked on M1-3**
- Server: the `/api/chat` stream must expose pending action ids (check `webui_channel.stream`; if missing, emit a final JSON line `{"pending": [{"id","summary"}]}`).
- Client: a `CONFIRMING` state speaks "<summary>. Shall I go ahead?", records one utterance, and treats yes/haan/ok/go ahead → `approve(id)`; anything else, including silence for 6 s, → `deny(id)`. It never auto-approves.
- Test: `test_loop_states.py::test_spoken_approval` (yes → one approve; no or silence → deny; no approve without speech).
- Live check: part of M2-1's check, plus "no" leaves Notepad open.

### M2-3 Find and read a document (FIL-01, FIL-02) — **ready** (Step V done)
- `tools/plugins/information/document.py`: switch PDF to `pypdf`, add PPTX, and keep the `read_document` interface.
- `toolkit.py`: new `read_document` tool (direct, read-only). It only accepts paths under the user's Documents, Downloads or Desktop, or paths returned by the last `search_files`; it returns ≤ 6000 chars plus the page count, and its output is wrapped as untrusted content (from Step 0-6).
- `actions.search_files`: add an `ext` filter and sort by modification time (newest first), so "latest invoice PDF" works.
- Test: `tests/plugins/test_documents.py` with tiny fixtures in `tests/assets/docs/` (PDF, DOCX, XLSX, PPTX, TXT): the text is extracted, an outside path is refused, a big file is truncated, and newest-first ordering holds.
- **Live check (the GOAL M2 "Done when"):** put an invoice PDF in Downloads and say "<wake word>, find my latest invoice PDF and tell me the total". The correct total is spoken. Record the log line and the PDF's real total.

### M2-4 Every mutating tool needs approval (PLT-04) — **covered by Step 0-8**
- `test_policy_table` is the enforcement. In M2, classify `document_edits.py` and the `maintenance_patch`/`propose` tools in the table as confirm. Fix any tool that writes files or sends outside without `confirm`.
- Live check: by voice, "edit my notes file" → approval asked, and "no" leaves the file unchanged (compare mtime).

### M2-5 Screenshot by voice — **blocked on M2-2**
- Use the existing `take_screenshot` (confirm). Speak "Saved a screenshot to <name>" and make sure it is saved under `data/`.
- Live check: "take a screenshot" → yes → the file exists.

---

---

## M7–M11 — outline (after M1; detailed plans come once M1 passes its bench gate)

**Order:** M1 → M2 → **M7** (device control builds on M2's PC actions) → **M8** (usage data; M10 and M9 use it) → **M10** (proactive, reusing M8 signals) → **M9** (agent mode; needs a durable approval queue and receipts) → **M11** (self-evolving; needs M9's failure logs). M3–M6 still slot in where GOAL orders them.

**Prerequisites before M7/M9** (deferred audit items):
- H4: a persistent approval queue (SQLite, with a status per action), so approvals survive a restart.
- Telegram Approve/Deny buttons.
- C3: build the Android app and check it on a device.

**Rules for every step below:**
- Each step adds tests to `tests/plugins/test_approval_policy.py` (the policy table).
- Each step logs its live evidence in `docs/team/LOG.md`.

### M7 — Full device control
**Reuse:**
- `AgentHub` (`tools/plugins/system/agents.py`: pair/enqueue/poll/complete/jobs; it already stores receipts);
- the `device_action`/`ask_device` split from Step 0;
- `tools/device_companion.py` `execute()`, `tools/plugins/system/actions.py`, and the Toolbox `confirm`/`low_risk` approval flow.

**Steps:**
- **M7-1 Laptop power and lock via the companion — ready.**
  - Change: in `device_companion.execute`, add `lock`, `sleep`, `volume_set`, `brightness_set` (WMI), and `clipboard_get`/`clipboard_set`. `shutdown` asks for a second confirmation that names the device.
  - Change: list the new kinds in the `device_action` enum, with `low_risk` for lock and volume only.
  - Test: `tests/test_device_companion.py` (kind → the stubbed OS call); a policy-table entry.
  - Live check: by voice, "lock my laptop" → approval → locked, and the receipt shows in Devices.
- **M7-2 One target-device resolver — ready.**
  - Change: in `toolkit.py`, add `_resolve_device(name|"this pc"|"my phone", ctx)` over `AgentHub.devices`, used by every device action. Ambiguous names get a question back, never a guess.
  - Test: unit tests for exact, alias, ambiguous and unknown names.
  - Live check: "on my phone" and "on the laptop" each reach the right device.
- **M7-3 Phone alarm, flashlight and DND — blocked on an Android build environment.**
  - Change: new `MainActivity.kt` bridge commands `set_alarm` (`AlarmClock.ACTION_SET_ALARM`, which needs no permission and shows the system UI), `flashlight`, `dnd`, with Kotlin-side confirmation for anything sent outside the device.
  - Live check: "set an alarm for 7 on my phone" leaves a receipt, and the alarm appears in the Clock app.

### M8 — Device usage awareness
**Reuse:**
- `atulya/sysmon.py` `snapshot()` (CPU/RAM/disk/net/battery);
- `RainTrigger`/`DiskFullTrigger` from the archived workflow engine (`F:\Atulya-Tantra-cleanup-archive\code\routines_workflow_engine.py`; `tools/plugins/routines.py` was removed in cleanup);
- `ProactiveMonitor._check_disk_space`.

**Steps:**
- **M8-1 Local metrics history — ready.**
  - Change: new `atulya/usage_store.py`, a SQLite `samples(ts, cpu, mem, disk, battery, net_up, net_down)` table. A background task samples `sysmon.snapshot()` every 60 s; data is kept for 30 days.
  - Test: insert, retention and aggregation queries.
  - Live check: after 1 h, the stored CPU/RAM averages match Task Manager's history within 10%.
- **M8-2 Per-app screen time on the PC — ready.**
  - Change: sample the foreground window's process every 5 s (`GetForegroundWindow` + psutil), skipping time when the screen is locked or idle for over 2 min (`GetLastInputInfo`). Store `app_minutes(day, exe, minutes)`.
  - Test: a stub sampler → correct minute totals, with idle time excluded.
  - Live check: a day's top 5 apps match your own observation, or Windows "App history", within 10%.
- **M8-3 `usage_report` and `why_slow` tools (direct, read-only) — ready after M8-1.**
  - Change: `usage_report` answers "what did I use most today?". `why_slow` returns the top CPU/RAM processes now plus the last hour's trend.
  - Test: fixture DB → the expected text.
  - Live check: ask both by voice while a known heavy process runs; it is named.
- Phone usage (Android `UsageStatsManager`) comes later, blocked on the Android build like M7-3.

### M10 — Fully proactive
**Reuse:**
- the rain, disk-full and site-down triggers archived at `F:\Atulya-Tantra-cleanup-archive\code\routines_workflow_engine.py` (bring back only the trigger classes, not the old engine);
- `tools/plugins/productivity/briefing.py`, `routines.py` (the daily routines tools), the reminders, `atulya/push.py` and Telegram;
- `Maintenance.proactive_status`/`set_proactive` as the existing on/off pattern.

**Steps:**
- **M10-1 One alert pipeline with quiet hours and per-type switches — ready.**
  - Change: new `atulya/alerts.py`, `send_alert(user, type, text, reason)`. It checks profile `quiet_hours` and `alerts_off[type]`, deduplicates for 6 h, stores `alerts(id, ts, type, text, reason, delivered, receipt)`, and delivers through `push.py`/Telegram. All existing proactive senders route through it.
  - Test: quiet hours hold it, a disabled type drops it, a duplicate is suppressed, and a receipt is stored.
  - Live check: an alert sent during quiet hours is held and arrives after they end.
- **M10-2 "Why did you tell me this?" — ready after M10-1.**
  - Change: a direct `explain_alert` tool returns the stored `reason` of the last alert, or of an alert by id. Telegram alerts get a "Why?" button.
  - Test: alert → explain round trip.
  - Live check: ask after a rain alert and hear the trigger values.
- **M10-3 Low battery and disk warnings from M8 data — ready after M8-1.**
  - Change: restore `RainTrigger`/`DiskFullTrigger` from the archive into a new `atulya/triggers.py`, add `BatteryLowTrigger`, and send all of them through `send_alert`.
  - Test: trigger tests with fixture samples.
  - Live check: fill a test volume, or lower the threshold, and the alert arrives once.

### M9 — Autonomous agent mode
**Reuse:**
- `Brain.stream` tool rounds (`tools/plugins/brain/engine.py`) and `Toolbox.call`;
- the approval queue (made durable by H4);
- `AgentHub` job receipts, and `docs/TODO.md` PLT-09 (durable jobs).

**Steps:**
- **M9-1 Durable task store — ready, once H4 lands.**
  - Change: new `atulya/tasks.py`, SQLite `tasks(id, goal, status, step_limit, created)` and `task_steps(task_id, n, plan, tool, args, result, status)`. On restart, `running` tasks resume from their last step.
  - Test: create, step, simulated crash, resume.
  - Live check: restart the server mid-task and it continues.
- **M9-2 Plan → act → observe loop — ready after M9-1.**
  - Change: new `atulya/agent_loop.py`. The model writes a short plan, then runs one tool call per step through `Toolbox.call`, so approvals still apply and an approval pauses the task. It has a step limit (default 12) and a wall-clock limit, re-plans at most twice on failure, and a final step checks the result against the goal. A `start_task` tool (confirm) kicks it off.
  - Test: a scripted fake provider, a successful 3-step goal, a failing tool → re-plan → stop at the limit, and a mutating step → paused waiting for approval.
  - Live check: the GOAL M9 "Done when" task (the 3 largest files in Downloads → summarize → remind tomorrow) completes, with receipts.
- **M9-3 Visible task timeline — ready after M9-1.**
  - Change: `GET /api/tasks/{id}` plus a WebUI panel; progress messages through `send_alert(type="task")`.
  - Live check: watch the steps appear while the task runs.
- On this CPU, multi-step agent runs will be slow (minutes); M1's measurements apply. A GPU helps most here.

### M11 — Self-evolving, safely
**Reuse:**
- `atulya/maintenance.py` (`propose`/`proposals`/`apply(rollback=True)`, a reviewable-diff workflow with rollback that already exists);
- `tools/core_protection.py` (hashes of protected core files);
- `tools/plugins/audit.py` `record_tool_run` (tool failures);
- `tools/skills/<name>/SKILL.md` (with `use_skill`/`list_skills`);
- the profile and memory tools for preferences.

**Steps:**
- **M11-1 Learn preferences from corrections — ready.**
  - Change: detect corrections ("shorter", "don't tell me that", "call me X") in chat. Propose an `update_profile`/alert-type change with "Shall I remember that?" and write it only after a yes. It is reversible through the existing edit/forget tools.
  - Test: phrases → the proposed change, with no write before confirmation.
  - Live check: say "shorter" and the next replies use `length=short`.
- **M11-2 Failure log → improvement proposals — ready.**
  - Change: a weekly job reads the failed and erroring tool runs from the audit log, groups them, and creates `Maintenance.propose(...)` entries (a prompt or tool change as a diff with the failure evidence). It never applies them itself; files that `core_protection` guards are refused.
  - Test: fixture audit log → one proposal per group; a proposal touching a protected file is rejected.
  - Live check: 3 proposals in a week, reviewed in Maintenance.
- **M11-3 Skills written from repeated requests, gated — ready after M11-2.**
  - Change: draft `tools/skills/<name>/SKILL.md` as a maintenance proposal. Enable it only after owner approval **and** a green `pytest` run started by `apply`. Each enable or disable is versioned through the maintenance rollback.
  - Test: an unapproved skill is not listed; rollback removes it.
  - Live check (GOAL M11 "Done when"): accept a proposal, the tests stay green, and roll it back.

---

## M12–M17 — PROVISIONAL (inputs not landed yet)

As of 2026-10-21, AUDIT.md has no "M12/M13 baseline" and RESEARCH.md has no M14–M17 section. Until they land:
- the M12/M13 steps below come from my own read of the code and are marked **provisional**;
- M14–M17 are listed only by their order and the code they reuse.

I will revise this section when the two inputs land.

### Overall order, M1–M17 (the owner's priority is that devices and dangerous tools stay admin-only)

| Lane | Sequence | Can run in parallel with |
|---|---|---|
| A — safety first | **M12 → M13** (start now; these come before any new device or agent power) | lane B (M1), since the files are different |
| B — voice | **M1** (M1-B1…B6 → bench gate → mic loop) → M2 | lane A |
| C — reach and devices | M7 → M15 → M18 → M14 → M19 (all after M12, because they add device and channel surface; M19 also needs M10-1) | M8 once M12-2 is done |
| D — awareness and proactivity | M8 → M10 → M4 | lane C |
| E — intelligence | M3 → M9 → M11 → M16 | M16's prompt/persona work can start after M1 |
| F — senses | M6 → M17 (M17's end-to-end check needs M1, M6 and M7-3) | everything else |

Hard gates:
- No step in M7, M9, M14 or M15 merges before M12-1..M12-3 are green.
- M13's CI checks (M13-3) gate everything after they land.

### M12 — Many users, strict admin/device separation
**Reuse:**
- `atulya/auth.py` (`users.role` ∈ admin/user, `is_admin`);
- the per-user `ctx.user_id` in `PluginContext`;
- `AgentHub` (already keyed by `owner`);
- the Toolbox `public_only` flag;
- `tests/plugins/test_approval_policy.py` (the per-tool table).

**Finding while planning:** `toolkit._owner_only` checks `ctx.user_id == "admin"` (a literal id), not the role. It should use `auth_store.is_admin(user_id)`. Fixing that is part of M12-2.

**Steps:**
- **M12-1 Route access table plus a test over every route — ready (provisional).**
  - Change: `tests/core/test_route_access.py` walks `app.routes` (64 in `atulya/server.py`). Each route must appear in a table, `{path+method: "public" | "user" | "admin" | "device"}`; an unlisted route fails the test.
  - Test: with an admin session, a second `user` session and no session, every admin route returns 403 for the user and 401 for anonymous.
  - Change: add one dependency, `require_admin`, in `server.py` and use it on every admin route; it replaces scattered `is_admin` checks.
  - Live check: sign in a second test account and hit the admin routes with curl. All return 403.
- **M12-2 Admin-only dangerous tools — ready (provisional).**
  - Change: a new `admin_only: bool` field on `Tool`, set for PC control, `device_action`/`ask_device`, `restart_service`, `server_status`, `server_logs`, `maintenance_*`, `mcp_*`, `smart_home_control`, `cast_to_tv`, `visual_inspect`, the screen/screenshot tools and the gmail tools.
  - Change: `Toolbox.__init__` drops these tools from the schemas for non-admins (the model never sees them), and `Toolbox.call` refuses them again on the server. `_owner_only` switches to the role check.
  - Test: the policy table gains an `admin_only` column; a user-role Toolbox has none of these schemas, and calling one returns "admin only".
  - Live check: the second account asks "lock the PC" and gets a refusal, and no job is queued.
- **M12-3 Devices are private to their owner — ready (provisional).**
  - Change: every `AgentHub` read or write passes the caller's `owner`, including the Devices routes and the pairing, test and revoke routes in `server.py`. A device of another owner returns 404, never 403, so its existence is not revealed.
  - Test: user B lists, tests, revokes and enqueues on user A's device → 404 each time; A's list never contains B's devices.
  - Live check: the second account's Devices page is empty and the owner's devices don't appear.
- **M12-6 Age-based content settings per profile — ready (provisional; follows M12-1 and M12-2).**
  - **Data model** (`atulya/profiles.py`):
    - `age_group` ∈ `adult` | `child`, **decided automatically at sign-up, with no wait for the admin** (owner decision 2026-10-21):
      1. Sign-up (and first sign-in for existing users) asks for a **date of birth**. The server computes the age and sets `age_group` immediately: ≥ 18 → `adult`, otherwise `child`. The date of birth is stored and the field is locked; a later change needs the admin.
      2. If the user signed in with Google and granted the optional `user.birthday.read` scope (Google People API, free), the server takes the birthday from Google instead and records `age_source="google"`. Otherwise it records `age_source="self"`.
      3. Until a date of birth is given, the profile is treated as `child`, so it can chat right away with safe settings.
      4. The admin is notified of each new profile and its age group, and can override it (`age_source="admin"`). Overriding is optional, never a gate.
      - **Honest limit:** with free tools, this is self-declared or Google-declared age, not real ID verification. Paid ID or face-age checks are out (GOAL: no paid services; they would also mean collecting sensitive ID data). The plan states this, and so does the admin UI.
    - `adult_content` (bool, default false), changeable only by the user themself and only when `age_group == "adult"`.
    - Neither field is in `VOICE_EDITABLE` or `update_profile`, so the model can never change them. The server rejects a write from anyone else (`child` + `adult_content=true` → 422; a non-admin writing `age_group` → 403).
  - **Enforcement on the server, per request** (from the profile, never from the client):
    - new `atulya/content_policy.py` provides `policy_for(user_id) -> ContentPolicy(level="child" | "adult" | "adult_open")`;
    - **System instructions** (`Toolbox.instructions` / persona):
      - `child`: an age-appropriate tone, with a short note to decline adult topics gently;
      - `adult`: the default;
      - `adult_open`: "Don't refuse or moralize about legal adult topics the user asks about." Text for all three levels lives in one place, `content_policy.py`.
    - **Tools:**
      - `search_web`: SearXNG `safesearch=2` / ddgs `safesearch="on"` for `child`; `moderate` for `adult`; `off` only for `adult_open`.
      - `read_url`: refuses domains on a local blocklist for `child`.
      - `search_music`/`queue_music`, `get_news`: filtered for `child` (YouTube results with age-restricted flags are dropped).
    - **Illegal content is never allowed at any level.** A fixed category list in `content_policy.py` (sexual content involving minors, and other illegal material) applies before and after the model, for every level including `adult_open`, with no setting to turn it off. Note: the local model's own training limits still apply, and `adult_open` cannot override them; the plan doesn't try to jailbreak the model.
  - **Blocked-attempt notifications** for children: when a request is blocked for a `child` profile, record `{user, ts, category}` in `content_events`. If the admin enabled `notify_blocked` for that child, send one alert to the admin through `send_alert` (M10-1; until it exists, through the existing Telegram owner chat). Alerts are capped at 1 per hour per child and include the **category only, not the message text**, to keep the child's privacy proportionate. The admin can see the event list in the admin UI.
  - **Tests**, in `tests/core/test_content_policy.py`:
    - Age at sign-up: DOB 17 years and 364 days ago → `child`; exactly 18 → `adult`; a Google birthday wins over a typed one; no DOB → treated as `child`; the admin gets a notification; an admin override is applied and recorded.
    - After it is set, a user can't change their own `age_group` or DOB (403), and a `child` can't set `adult_content` (422). `update_profile` and the voice-editable set don't include either field.
    - The search tool gets `safesearch` strict/moderate/off for child/adult/adult_open, checked against a stubbed SearXNG/ddgs client.
    - The system instructions contain the level's text, and `adult_open` text appears only when both flags allow it.
    - An illegal-category request is refused at every level, including `adult_open`.
    - A blocked child attempt creates a `content_events` row and at most one admin alert per hour, and the alert contains no message text.
    - The policy comes from the server profile: a client sending `adult_content=true` in the chat body changes nothing.
    - Add these routes to the M12-1 route table: the admin route for `age_group`/`notify_blocked`, and the user route for `adult_content`.
  - **Live check:**
    - Sign up a second test account with a DOB under 18: it becomes `child` at once, with no admin step. Ask it to search something adult and see the safe search results.
    - Check that the admin gets one alert with the category only.
    - Sign up a third test account with an adult DOB: it becomes `adult` at once. Opt in, then ask about a legal adult topic: no lecture.
    - Then make an illegal request: refused.
    - Record each in LOG.md.
- M12-4 per-user tool limits and the invite/disable admin UI, plus M12-5 the "admin can't read others' chats" check on history routes: detailed after the AUDIT baseline.

### M13 — Security
**Reuse:**
- the SameSite=strict session cookie already in place (`server.py:261`, `:1101`);
- the untrusted-content wrapper from Step 0-6;
- `tools/plugins/audit.py` `record_tool_run`;
- `atulya/secrets_store.py`.

**Steps:**
- **M13-1 Security headers and CSRF — ready (provisional).**
  - Change: middleware sets a strict CSP (`default-src 'self'`; scripts from self only; adjust for the MediaPipe runtime path), `X-Content-Type-Options`, `Referrer-Policy` and `frame-ancestors 'none'`.
  - Change: CSRF via a double-submit token or an `Origin` check on every POST/PUT/PATCH/DELETE.
  - Test: `tests/core/test_security_headers.py` (headers present; a cross-origin POST → 403).
  - Live check: the WebUI works with the CSP on, with no console CSP errors.
- **M13-2 Linux secrets encryption (AUDIT H3) — ready.**
  - Change: off Windows, use Fernet with a key file `0600` outside `data/`, or `keyring` when available; migrate `PLAIN:` entries on read. `set_secret` sets the mode to 0600.
  - Test: round trip; no `PLAIN:` after a write; file mode 0600 (skipped on Windows).
- **M13-3 Free security checks in the test run — ready.**
  - Change: add `pip-audit`, `bandit -r atulya tools -ll`, and a secrets scan (`detect-secrets` baseline) as `tools/security_check.py`, run in selftest/CI, with a baseline file for accepted findings.
  - Live check: a clean run, logged in LOG.md.
- M13-4 rate limits and lockouts, M13-5 the admin audit log viewer (PLT-07), M13-6 the `innerHTML` audit: detailed after the AUDIT baseline.

### M14–M17 — waiting for RESEARCH.md
- **M14 channels.** Reuse the Telegram channel, the Gmail plugin, the Android `send_sms_direct`/`call_direct` with the C3 dialog, and `send_alert` (M10-1). Its first step will be one inbox and identity (PLT-05).
- **M15 any device.** Reuse `tools/device_companion.py`, `companion_setup.py`, `AgentHub` pairing codes, and `pc_companion_app.py`. Its first steps will be service install per OS (visible, listed, one-click removal) and per-device approval rules.
- **M16 human-like conversation.** Reuse `atulya/persona.py`, the profile `tone`/`length`, M1's voice instructions and the `instant_ack` fillers. Its first step will be a "robotic phrase" lint test on replies.
- **M17 senses.** This is M1 + M6 + gestures (`models/gesture`). Its first step will be the recorded end-to-end session script.

---

## M12 update (2026-10-21): already fixed in code, B21–B23
- **B21:** role checks now use `PluginContext.is_admin`, not the literal user id "admin". This is the `_owner_only` bug above, now fixed.
- **B22:** `pc-control` and `smart_home` tools are owner-only.
- **B23:** basic security headers are added.

So M12-2 starts from an existing `is_admin` in the context. M12-2's job becomes the `admin_only` field in the policy table, covering *every* dangerous tool, plus a test. M13-1 extends the existing headers with CSP and CSRF instead of adding them from scratch.

---

## M18 — Cross-device control toolkit (after M12-1..3 and M15's outbound channel)

**Inputs:** RESEARCH.md M15, which gives per-user autostart, an outbound wss channel and typed, signed commands with no raw shell. RESEARCH.md M18 answers R18-1..4:
- **R18-1:** `send2trash==1.8.3` on desktops, with no permanent delete at all. Android uses a Storage Access Framework (SAF) folder grant, plus MediaStore trash requests for media; any other Android delete is permanent, so it needs a stronger approval prompt.
- **R18-2:** a read-only scan from the ARP/neighbour table, plus `zeroconf` for mDNS and `wakeonlan==3.1.0`; no scapy.
- **R18-3:** `androidtvremote2==0.2.x` (PIN pairing, no debugging mode) for everyday TV control; ADB pairing only for the one-time install of a TV companion APK.
- **R18-4:** the official `mcp` SDK over streamable HTTP with a `TokenVerifier`, mapping each per-device token to an Atulya user plus scopes. It also checks the `Origin` header and binds to localhost or the Tailscale address.

**Reuse:**
- `AgentHub` and the job receipts;
- `tools/device_companion.py` `execute()` (already has list/read files, granted-folder checks, media and battery);
- `device_action` with confirm (Step 0) and the M7-2 device resolver;
- `tools/mcp/server.py` (5 public tools today);
- `tools/skills/*/SKILL.md` with `use_skill`;
- M8's `usage_store`;
- the M13 audit log.

**Safety rule for every M18 tool**, enforced by the policy table in `test_approval_policy.py`:
- owner-only (`admin_only` from M12-2), unless explicitly listed as safe;
- read-only tools run directly;
- tools that change something are confirm-only and leave a receipt;
- delete always goes to the recycle bin, and a permanent delete is a separate tool with its own approval, never low-risk;
- every call is written to the audit log.

**Steps:**
- **M18-1 File operations in the companion — ready.**
  - Change: in `device_companion.execute`, add `file_search`, `file_stat`, `file_read` (text ≤ 100 KB, a bigger preview for images), `file_copy`, `file_move`, `file_rename`, `file_write` (requires a `base_sha256` so it never overwrites an unseen version), and `file_trash` (`send2trash`). All of them stay within the granted folders, using the existing `resolve(strict=True)` + `is_relative_to` checks.
  - Change: on the server, read kinds go through `ask_device`; mutating kinds go through `device_action`, whose `describe` shows the path. For an edit it shows a unified diff in the approval card.
  - Test: `tests/test_device_companion.py` with a temp granted folder covers each kind, path escape refused (`..`, symlink, absolute path), a stale `base_sha256` refused, and trash leaving the file recoverable (`send2trash` stubbed). The policy table covers every new kind.
  - Live check: from the phone, find a file on the desktop → preview → approve delete → it's in the Recycle Bin, and the receipt shows in Devices.
- **M18-2 Transfer between devices — ready after M18-1.**
  - Change: the source device uploads to a server-side, one-time blob (`data/transfers/<id>`, 15 min TTL, size cap from config, owner-scoped). The target device's `file_fetch` job downloads it and checks the sha256. A new `transfer_file(src_device, path, dst_device, dst_folder)` tool (confirm) chains the two jobs and returns both receipts.
  - Test: the round trip with two fake companions; checks a sha mismatch, expiry, and that another owner's blob returns 404.
  - Live check: the GOAL "Done when": desktop file → phone, then delete the original, all with receipts.
- **M18-3 One MCP server with per-user permissions — ready.** Transport (R18-4): FastMCP `streamable_http_app()` with a `TokenVerifier` over hashed per-user tokens. Scope `tools:read` covers read-only tools; tools that change things also need `tools:write` and still go through approval. It returns 401 with `WWW-Authenticate` when the token is missing, rejects a foreign `Origin`, and binds to 127.0.0.1 or the Tailscale address. stdio uses `ATULYA_MCP_TOKEN`.
  - Change: in `tools/mcp/server.py`, replace the fixed 5-tool list with `Toolbox.for_registry(..., context=user ctx)`, authenticated by a per-user MCP token (hashed and revocable, created in Settings). Non-admin tokens never list `admin_only` tools. Confirm-tools return "Approval requested" and the approval happens in the WebUI or Telegram, as for chat.
  - Test: `tests/mcp/test_mcp_permissions.py`: an admin token lists device and file tools; a user token doesn't, and calling one anyway is refused; confirm-tools queue an approval without running.
  - Live check: Claude Desktop or VS Code connected with the owner token runs `ask_device` file search, and a delete asks for approval.
- **M18-1 additions from R18-1:**
  - Pin `send2trash==1.8.3`.
  - Check free space before a cross-drive `shutil.move`.
  - Each receipt records the original path, so `file_undo(receipt)` can restore from the trash or move a file back.
  - There is **no permanent-delete kind on desktops**.
- **M18-4 Android files — blocked on an Android build environment.**
  - Change: an APK folder grant (`ACTION_OPEN_DOCUMENT_TREE` + `takePersistableUriPermission`) and `DocumentFile` list/read/copy. Media deletes use `MediaStore.createTrashRequest` (restorable for 30 days; the system dialog doubles as the approval). Non-media deletes are a separate `file_delete_permanent` kind, with an approval card that says "cannot be undone" and is never `low_risk`.
  - Live check: delete a phone photo → it's in the phone's trash → restore it.
- **M18-5 Network, read-only, plus Wake-on-LAN — ready.**
  - Change: the companion and server get `lan_devices` (parse `arp -a` / `ip neigh`, plus a 3 s `zeroconf` browse of `_googlecast._tcp`, `_androidtvremote2._tcp`, `_adb-tls-connect._tcp` and `_workstation._tcp`; no packets beyond mDNS).
  - Change: `wake_on_lan(device)` (confirm, low_risk), sent by a companion **on the target's LAN** (the server relays it to that companion; never sent from the internet).
  - Change: online/offline history in M8's `usage_store`.
  - Pin `zeroconf` (LGPL-2.1, used as an unmodified library) and `wakeonlan==3.1.0`.
  - Test: `arp -a`/`ip neigh` fixture parsing, a stubbed zeroconf browse, and a magic packet built for a known MAC; the policy table covers the new tools.
  - Live check: "what's on my network?" lists the TV and phone; "wake the desktop" from the phone wakes it (WoL enabled in BIOS).
- **M18-6 TV control — ready (Python side); the companion APK install is optional.**
  - Change: `tools/plugins/system/tv.py` with `androidtvremote2`: a one-time PIN pairing flow (admin route; certificate stored in `secrets_store`), then a `tv_control(tv, key | app_link | power | volume)` tool (confirm, low_risk). `cast_to_tv` switches to a deep link through it.
  - Test: a stubbed remote, covering key mapping, a missing pairing, and a policy-table entry.
  - Live check: "pause the TV" and "open YouTube on the TV" each work, with a receipt.
- **Later:** apps and system (process list, close, brightness, clipboard sync, phone notifications shown on the PC), servers (read-only `server_status`/logs for the admin, `restart_service` with confirm), and skills `backup-phone-photos`, `clean-downloads` (the trash plan needs approval), `disk-hogs-all-devices` and `device-health-report`, each a SKILL.md built only from the tools above.

---

## M19 — Inbox assistant (after M10-1 send_alert/quiet hours, M12, and M14 email and Android pieces)

**Inputs:** RESEARCH.md M14:
- Email: IMAP via `imap-tools` 1.x + SMTP with an app password; the Gmail API is optional (7-day token expiry in testing mode).
- Android: a sideloaded APK, with restricted settings on Android 13+.
- WhatsApp Cloud API: off.

Research answers (RESEARCH.md M19):
- **R19-1:** notification access is granted manually. A sideloaded APK first needs **App info → ⋮ → Allow restricted settings** (mandatory from Android 15).
  - Inline reply via `RemoteInput` is reliable for WhatsApp and Telegram and usually works for Instagram and Messenger. **Snapchat is read-only** (no reply action).
  - Act within seconds, before the `PendingIntent` dies. Grouped and summary notifications have no actions. Use `isGroupConversation` to detect groups. Handle OEM battery killers with `requestRebind` plus an exemption prompt.
- **R19-2: SMS stays read-only**, with sending through approval only; **no SMS delete**, since that needs the default SMS app.
- **R19-3:** the phone decides "real person" with `PhoneLookup` (`READ_CONTACTS`) and sends only `known_contact`, `starred` and `has_prior_thread`. Short codes, alphanumeric senders, OTP patterns and noreply addresses count as automated. **The contact list and numbers are never uploaded**; any stable ID is hashed with a per-device salt.
- **Mail:** IMAP with explicit folder moves. Trash means MOVE to `[Gmail]/Trash`. Never `\Deleted` + expunge.
- **Auto-reply pitfalls:**
  - loop guard: ignore our own messages, tag outgoing text, at most one reply per chat per N minutes;
  - groups off;
  - never reply to short codes or unknown senders.

**Reuse:**
- the Gmail plugin (`tools/plugins/information/google_api.py`) or the new IMAP client;
- `send_alert`, quiet hours and per-type switches (M10-1);
- the approval queue (H4, durable);
- the audit log (M13);
- `memory`/profile for the owner's name;
- the Telegram channel for "you're back".

**Data model:** new `atulya/inbox.py` with SQLite tables:
- `messages(id, source, account, thread, sender_hash, known_contact, starred, has_prior_thread, is_group, automated, ts, summary, label, action, action_ts, undo_token)`
- `rules(id, text, match_json, action, enabled, confirmed, created)`
- `holding_replies(source, thread, sent_ts)`

Message bodies are kept only as a short summary, deleted after 30 days.

**Steps:**
- **M19-1 Email ingest and sorting — ready.**
  - Change: `tools/plugins/communications/imap_inbox.py` (`imap-tools`) polls every 2 min; the app password is stored in `secrets_store`.
  - Change: `sort_message()` applies the rules first, then a small-model classification (important / can wait / junk) with a confidence score. Below 0.8, the label is `ask`.
  - Change: read-only tools `inbox_summary` and `inbox_list(label)`.
  - Test: fixture `.eml` messages → expected labels; a rule wins over the model; low confidence → `ask`; nothing is modified on the server (the IMAP stub records no STORE or MOVE).
  - Live check: one day of the real inbox gets labeled, and the owner spot-checks 20.
- **M19-2 Plain-language rules — ready.**
  - Change: an `add_inbox_rule(text)` tool (confirm, since the rule is shown before it is saved). The model turns the text into `match_json` (sender, domain, keywords, source, age), and the server validates it against a strict schema. A rule that says "never touch X" sets a protect flag, which beats every delete rule.
  - Change: the WebUI lists rules with edit and on/off; `rules_test(rule, last 50 messages)` previews what a rule would hit.
  - Test: the "Swiggy promos", "never touch Mom" and "OTPs after 10 min" examples parse; protect beats delete; an invalid `match_json` is rejected.
  - Live check: say "always delete Swiggy promos", check the preview, confirm it, and it is listed in the WebUI.
- **M19-3 Clean up with undo — ready after M19-1 and M19-2.**
  - Change: junk email is moved to Trash/Archive via IMAP MOVE (`[Gmail]/Trash` for Gmail; never `\Deleted` + expunge), and an `undo_token` holds the original folder and UID.
  - SMS is never deleted (R19-2); junk SMS is only labeled, and its notification is dismissed (after M19-4).
  - Change: the first application of each rule asks for confirmation once (`confirmed=false` → an approval card listing the hits); later matches run automatically.
  - Change: an `inbox_undo(id|"last")` tool.
  - Test: move + undo restores the folder; an unconfirmed rule queues an approval and moves nothing; a protected sender is never moved.
  - Live check: after a day, the junk is in Trash, undo brings one back, and there are no wrong deletions (the owner reviews the log).
- **M19-4 Android notification inbox — R19-1 answered; blocked only on an Android build environment.**
  - Onboarding: guide the user to App info → ⋮ → Allow restricted settings, then to notification access, then to the battery-optimisation exemption. Call `requestRebind` on disconnect.
  - Change: in the APK, a `NotificationListenerService` posts new messages (app, conversation key, the R19-3 labels `known_contact`, `starred`, `has_prior_thread`, `is_group` and `automated`, and the text; **never the number or the contact name**) to the server over the device channel, plus actions `dismiss` and `reply_inline(key, text)` via `RemoteInput`. A persistent notification shows "Atulya is reading notifications".
  - Live check: a WhatsApp message arrives on the server; dismissing a junk notification works.
- **M19-5 Away / asleep holding reply — blocked on M19-4 (for WhatsApp); ready for email now.**
  - Change: if the owner is away (a profile flag), in quiet hours (M10-1) or busy, and the sender is a `known_contact` or `has_prior_thread` and not `automated`, and the conversation is not a group, and no `holding_replies` row exists for that thread since the owner was last back, send the template once. Email goes through SMTP with `In-Reply-To`; WhatsApp goes through `reply_inline`.
  - Change: the template and the opt-in per source live in Settings. Enabling them is the user's standing approval, recorded in the audit log.
  - Loop guard: ignore messages we sent; tag outgoing text with a zero-width marker and skip incoming text that carries it; at most 1 reply per chat per 6 h, even across away periods; Snapchat never gets replies.
  - Test: a second message in the same thread → no second reply; an unknown sender, a group or an automated sender (short code, OTP, noreply) → none; an incoming message carrying our marker → none; coming back resets it; quiet hours are respected.
  - Live check: a WhatsApp message while "asleep" gets exactly one holding reply.
- **M19-6 "You're back" summary with undo — ready after M19-3.**
  - Change: when the away flag clears or quiet hours end, `send_alert(type="inbox_back")` sends counts per label, the important items, the replies sent and the clean-ups. Each deletion gets an Undo button (Telegram inline or the WebUI) that calls `inbox_undo`.
  - Test: a fixture day → the expected summary text; undo from the summary works.
  - Live check: the GOAL M19 "Done when", over one day.

---

## Order and parallelism
1. **Step 0** and **Step V** now, in parallel (different files: `toolkit.py`/`smart_home.py`/`search.py`/tests vs requirements/`bootstrap.py`/`setup.py`). Train `atulya.onnx` (M1-5) any time.
2. M1-0 → M1-1 → M1-2 → M1-3 → M1-4, then M1-6. M2-3 can run in parallel with M1 once Step V is done.
3. M2-1, M2-2 and M2-5 after M1-3. M1-4b is a later spike.
4. Before M5: the deferred audit items (C3, H4, Telegram approvals, H3).

## Measurements
i3-9100F, no GPU, llama.cpp b11512, Qwen3.5-2B Q4_K_M (LOG.md 2026-10-20):

| Stage | Value |
|---|---|
| STT warm, beam 1 | base 0.95 s · base.en 0.90 s · tiny.en 0.61 s |
| TTS one sentence, idle | steps 8 1.46 s · 4 1.14 s · 2 0.66 s; 2–3 s while the LLM runs |
| First audio (ack via live TTS) | 3.15–3.55 s |
| Answer audio, 71 tools | 16–46 s (LLM first sentence 11.9–41.2 s) |
| Answer audio, no tools | 6.6–10.9 s (and it cannot answer) |

After M1-B1…B6: (add T1/T2/T3 from the bench gate)

## Revision log
- 2026-10-20 v1: first version, written without RESEARCH.md.
- 2026-10-21 v3.4: folded R18-1..4 and R19-1..3 into M18/M19 (new M18-4 Android files, M18-5 network/WoL, M18-6 TV; no SMS delete; contact labels decided on the phone; auto-reply loop guard) and added the B27 speaker blocker on the M1 live checks.
- 2026-10-21 v3.3: added M18 (cross-device toolkit) and M19 (inbox assistant), plus the M12 note that B21–B23 are fixed in code.
- 2026-10-21 v3.2: provisional M12–M17 section and the overall order M1–M17 (M12/M13 first, in parallel with M1); to be finalised once the AUDIT M12/M13 baseline and the RESEARCH M14–M17 section land.
- 2026-10-20 v3.1: added the M7–M11 outline (order M7→M8→M10→M9→M11 after M1/M2), the code each reuses, and the first 2–3 steps for each.
- 2026-10-20 v3: M1 rebuilt on measured numbers: voice tool subset, cached fixed prefix with slot save, tiny.en for English, 4-step TTS plus pre-rendered acks, profile context in the voice turn, a deterministic fast path; realistic targets for this PC and what a GPU changes. Step 0 and Step V marked done.
- 2026-10-20 v2: resolved A1–A5/R1–R5 from RESEARCH.md (openWakeWord ONNX, silero-vad, sounddevice, sherpa-onnx TTS, pypdf). R4 became a code check inside M1-3. Added Step 0 (AUDIT C1, C2, C4, H1, H2, M4 and the M2-audit items, plus the policy-table test) and Step V (voice dependencies into `.venv`, per LOG.md). Deferred C3, H4 and H3 to before M5.


### 2026-10-20 continuation evidence

See LOG.md and output/voice-validation for the current receipts. M1-B1 import/fallback repairs, profile context outside the system prefix, explicit stream cleanup, and M1-B3 language routing are implemented. Full regression suite: 190 passed, 2 skipped; final profile/weather wording checks: 11 passed. Synthetic English STT: 10/10 exact, median 0.7865 s (target 0.65 s not met). Synthetic Hindi selected base but produced a poor transliteration; accuracy is not verified. The owner supplied Sangam Vihar, New Delhi, Delhi, India; saved to the local admin profile for the weather benchmark. The rest of M1-B2 (runtime cache/slot flags), M1-B4, M1-B6 and the real microphone loop remain open. Do not infer milestone completion from these unit tests.


### 2026-10-20 fast-path continuation

The previous goal turn was progress (context, STT routing and actual latency receipts). Added strict common-command matching, regular Toolbox execution/approvals, JSON/SSE integration and benchmark result records. English direct templates preserve measured forecast values, current AQI, warning, source and timestamp. Non-English reply preferences and auto-language non-English text stay on the model path until translated templates exist. Parsed Hindi forms can use direct English responses when the user explicitly prefers English; do not claim native Hindi direct replies are implemented.

WebUI microphone and browser-recognition transcripts now send mode=voice; typed chat remains mode=text, including typed replies read aloud. Voice sends the latest four conversation turns plus the latest message. Fixed the actual WebUI sentence splitter so decimal temperatures split across stream chunks do not lose their prefixes.

Fixed acknowledgement phrases are cached at eight steps with language, speaker and model-version separation; startup warms them, and exact API hits skip engine loading. User answers are never cached. The owner first selected four steps, then explicitly changed the choice to eight ("use 8 to make it loud"); the latest preference is implemented. Read-aloud and acknowledgements also retain eight steps. Physical playback loudness has not been measured or changed.

Final Python regression suite: 236 passed, 2 skipped; separate actual-JavaScript decimal-splitting test: 1 passed; node --check passed. Live synthetic-audio timing/correctness results will be recorded in LOG.md. M1-B2 cache/slot work and the actual mic loop remain open. Existing weather startup prefetch uses the older weather() cache instead of find_place()/forecast(); align that before claiming the first real tool turn is prewarmed. No GOAL milestones are checked.
