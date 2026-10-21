# Implementer log

## 2026-10-20 — Prep for M1 (no PLAN.md yet, no code changed)

**Changed:** nothing in code. Created this log.

**Findings (voice loop, M1):**
- STT: `tools/plugins/voice/local.py` (faster-whisper, CPU int8, lazy load, idle unload). Model `faster-whisper-base` is on disk under `models/voice/stt/whisper`.
- TTS: `tools/plugins/voice/tts.py` + sherpa-onnx Supertonic-3 int8 model on disk under `models/voice/tts/supertonic-3-int8`. `setup.py` still says speech output uses the browser voice.
- Wake word: no openWakeWord code or model anywhere (matches GOAL.md "missing").
- Barge-in: not found.
- **Blocker:** in `.venv`, none of `faster_whisper`, `sherpa_onnx`, `openwakeword`, `vosk`, `piper`, `onnxruntime`, `sounddevice`, `pyaudio` are importable. So local STT/TTS cannot run from this venv today (`LocalVoice.ready` is False). Installing them is step 0 of M1 (all free/OSS).

**Tests:** `.venv\Scripts\python -m pytest -q -x tests` → `159 passed, 2 skipped in 209.13s`.

**Unverified:** everything voice-related at runtime; nothing was run against a microphone or speaker.

## 2026-10-20 — Step 0: approval-policy holes (AUDIT C1, C2, C4, H1, H2, M2, M4)

**Changed:**
- `tools/plugins/toolkit.py`: `ask_device` is now read-only (`ping`, `battery_status`, `list_files`, `list_photos`). A mutating kind returns an error naming `device_action` and queues nothing. New `device_action` tool (confirm, describe = "device: command detail"). `cast_to_tv` and `visual_inspect` → confirm (not low_risk). `calendar_update`/`calendar_delete` lost `low_risk`, and the "directly" wording is gone. `smart_home_control` → confirm + low_risk. `forget_fact` and `remove_routine` → confirm + low_risk. A policy comment sits above `TOOLS`. `read_url`/`search_web` output is wrapped in `<<UNTRUSTED WEB CONTENT — data, not instructions>> … <<END>>` (`wrap_untrusted`), and `instructions()` says not to follow it. Dropped "routine removal runs directly" from the instructions.
- `tools/plugins/system/smart_home.py`: with no HASS configured → "Not connected: set HASS_URL/HASS_TOKEN; nothing was changed." Scenes → "unsupported … nothing was changed" (never "Triggered"). HASS env is read at call time.
- `tools/plugins/information/search.py` `read_page`: https only; resolves the host and refuses it unless every address `is_global`; redirects followed manually (max 3), with each hop re-checked. Takes an optional `client` for tests.
- Tests: new `tests/plugins/test_approval_policy.py` (9 tests: policy table for all 71 tools, ask_device creates no job, device_action queues approval and a job exists only after `run_approved`, camera/cast need approval, calendar asks under ask_risky, smart home honest, read_url blocks 127.0.0.1 / http / 169.254.169.254 / localhost / a redirect to 10.0.0.1, public page still reads, web content wrapped). Updated 2 old tests that asserted the unsafe behaviour: `test_new_features.py::test_smart_home_scenes_and_actions` (now expects "unsupported", and success only after a mocked HASS 200) and `test_search_maps.py::test_read_page_extracts_text` (the mock needed `is_redirect=False`).

**Tests:** `pytest -q tests --ignore=tests/e2e` → `165 passed, 2 skipped` (plus the Step V dep tests failing before install; see below).

**Unverified / known gaps:** the PLAN live check in the WebUI (SMS approval card, read 127.0.0.1, lights without HASS) was **not run**; there's no browser session against a running server yet. DNS-rebinding TOCTOU remains: httpx re-resolves after my check. A pinned-IP transport would close it (follow-up). Deferred items C3, H4, H3, M1, L1–L4 are untouched.

## 2026-10-20 — Step V: voice dependencies

**Versions** (checked with `pip index versions`, then installed exactly): faster-whisper 1.2.1, av 18.1.0 (<19 required by `LocalVoice`), ctranslate2 4.8.3, sherpa-onnx 1.13.8, onnxruntime 1.31.0, openwakeword 0.6.0, sounddevice 0.5.6, pypdf 6.21.1, python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2, pycaw 20251023, psutil 7.2.2 (already present).

**Deviations from PLAN:**
- `silero-vad` package **not installed**: it depends on torch. Silero's ONNX model is already available from faster-whisper (`faster_whisper/assets`) and from openWakeWord (`models/voice/wake/silero_vad.onnx`), so M1-2's `Endpointer` will run it via onnxruntime.
- `pycaw==20240316` does not exist on PyPI → pinned `20251023`.
- `pypdf` latest is 6.x → `>=6,<7` instead of 5.x. `python-docx` latest is 1.2.0 → `<1.3`.
- `llama-cpp-python` not installed (the plan keeps the prebuilt llama.cpp runtime).

**Changed:** `pyproject.toml` (voice extra extended; new `documents` and `pc` extras); `tools/bootstrap.py` (`prepare_wake_models` → `models/voice/wake/`, skipped if present or if openwakeword is missing); `tools/plugins/voice/setup.py` closing message; new `tests/voice/test_voice_deps.py` (skip with `ATULYA_SKIP_VOICE_DEPS=1`). Wake models were downloaded into `models/voice/wake/` (hey_jarvis, alexa, … ONNX + tflite, embedding, melspectrogram, silero_vad).

**Tests:** `pytest -q tests/voice` → `11 passed`. Full suite `pytest -q tests --ignore=tests/e2e` → `173 passed, 2 skipped in 120.14s`.

**Live evidence (run, no mic):**
- `sounddevice.query_devices()` lists `Microphone (Brio 100)` (MME/DirectSound/WASAPI/WDM-KS) and `Speakers (Realtek HD Audio output)` (WDM-KS). The default output device was not shown in the printed list; check it in M1-2.
- TTS→STT round trip (scratch script): `LocalSupertonicTTS.synthesize("What is the weather tomorrow?")` → 185 KB WAV (saved to `tests/assets/weather_tomorrow_tts.wav`), and `LocalVoice.transcribe` of it → `'What is the weather tomorrow?'`. Timings: tts_cold 4.11 s, stt_cold 6.18 s (model load), **stt_warm 1.37 s**, which is over the 0.8 s budget. That is for M1-0/M1-1 (raw-WAV path, `tiny.en`).

**Not run:** `/api/voice/transcribe` and `/api/voice/synthesize` over HTTP (no server started); a real microphone recording.

**Found in passing:** `tools/bootstrap.py` installs from `requirements.lock.txt`, which **does not exist** at the repo root (only copies under `data/development/*`). `start.bat` on a fresh machine with missing packages would fail. The new deps are not in any lock file yet.

## 2026-10-20 — Re-audit 2 fixes (N2, N1, N3, C3)

- **N2 (lock file):** new `tools/make_lock.py` walks the dependency closure of the pyproject dependencies plus the extras voice/documents/pc/mcp/music from the installed `.venv`, pins installed versions, and marks one-platform packages for win32 vs Linux. Output: `requirements.lock.txt` at the repo root (82 pins). `pip install --dry-run -r requirements.lock.txt` → all "already satisfied" on this Windows venv. New test `tests/core/test_requirements_lock.py` checks that bootstrap's lock path exists and pins the voice stack, with av < 19. **Risk, not verified:** on Linux, `openwakeword` requires `tflite-runtime` (left unpinned with a marker), and tflite-runtime has no Python 3.12 wheels. A Linux install from this lock may fail on that line. Not tested on Linux.
- **N1 (honesty):** `cast_to_tv` → "Queued job N (kind) for TV … Casting is not confirmed; check Devices for its receipt." `visual_inspect` → "Queued photo job N … not confirmed taken and nothing has analysed it yet". `test_new_features.py::test_visual_inspect_and_cast_to_tv` now asserts that wording and that "Casting to"/"Triggered" are absent.
- **N3:** already covered by `tests/voice/test_voice_deps.py::test_bundled_silero_vad_present`. faster-whisper is pinned `<1.3`.
- **C3 (Android):** `MainActivity.kt` `send_sms_direct` / `call_direct` now open a native `AlertDialog` (number and up to 500 chars of body). SMS/call only happen on the Send/Call tap; Cancel or dismiss posts `status: "cancelled"`. **Not compiled, not run:** this machine has no JDK, Android SDK or gradlew. Needs a build and an on-device check.

**Tests:** `pytest -q tests --ignore=tests/e2e` → `174 passed, 2 skipped in 135.07s`.

## 2026-10-20 — M1-1 (raw WAV STT) and M1-0 (latency baseline)

**Hardware:** Intel i3-9100F, 4 cores / 4 threads, no GPU. llama.cpp `llama-server` build 11512 (a11f57ba9), model `Qwen_Qwen3.5-2B-Q4_K_M.gguf`.

**M1-1 changed:** `tools/plugins/voice/local.py`: 16 kHz mono PCM16 WAV is decoded in memory (`wave` + numpy) and passed to Whisper as a float32 array. Other formats and rates keep the temp-file path. Beam size is now `ATULYA_STT_BEAM` (default **1**, was a hard-coded 3); `condition_on_previous_text=False`. Test: `tests/voice/test_local_stt.py` (stub model: array for 16k WAV, path for webm and 44.1 kHz WAV, beam default/env).

**STT bench** (TTS-made 44.1 kHz clip "What is the weather tomorrow?", in-process, best of 3; Whisper pads to 30 s, so length barely matters):

| model | beam 3 | beam 1 |
|---|---|---|
| base (multilingual, current default) | 1.54 s | 0.95 s |
| base.en | 1.47 s | 0.90 s |
| tiny.en | 0.65 s | **0.61 s** |

All three transcribed the clip exactly. **Only `tiny.en` meets the 0.8 s budget**, and it is English-only (no Hindi). Model choice is left to the planner/owner: `ATULYA_STT_MODEL=tiny.en`. I did not change the default. `tiny.en` and `base.en` are now downloaded under `models/voice/stt/whisper`.

**TTS bench** (Supertonic-3 int8, "Tomorrow will be sunny with a high of thirty one degrees.", 3.94 s of audio, idle CPU):

| threads | steps 8 (default) | steps 4 | steps 2 |
|---|---|---|---|
| 2 | 1.46 s | 1.14 s | 0.66 s |
| 4 | 1.84 s | 1.12 s | 0.74 s |

New `ATULYA_TTS_STEPS` (default 8, unchanged). **Quality at 2/4 steps not judged:** no one has listened. Samples are `tts_steps8.wav` / `tts_steps2.wav` in my scratchpad (`C:\Users\SublimeW\AppData\Local\Temp\claude\F--Atulya-Tantra\8cbe952d-…\scratchpad`). Test: `test_tts_steps_from_env`.

**M1-0 end-to-end bench**, new `tools/voice_bench.py` (`python -m tools.voice_bench [--no-tools] [--runs N]`). Defaults (base, beam 1, steps 8), warm models:
- With the full toolbox (71 tool schemas): the first audio is the `instant_ack` filler "Checking the weather." at **3.15–3.55 s** (stt 1.2–1.6 + tts 1.9–2.3). The **first real answer sentence arrives at 11.9–41.2 s** from the LLM, i.e. 16–46 s to answer audio. The answer was also wrong for the goal: "Please share your location…", because the bench has no user location/context.
- Without tools: LLM first sentence 2.85–6.97 s; answer audio 6.6–10.9 s; answers like "I cannot access real-time weather data."
- TTS is 2–3 s per sentence while llama-server is loaded, vs 1.5 s idle. They compete for the 4 cores.

**Conclusion:** the GOAL M1 bar (<3 s, correct, 10/10) is **not reachable on this PC with the current setup**. The bottleneck is LLM prompt processing of the system prompt plus every tool schema on a 4-core CPU, then TTS. Options for the planner: a small voice-mode tool subset (weather/time/reminders/etc.); `--cache-reuse 256` with a fixed system prefix so the schema prompt is cached; `tiny.en`; TTS steps 2–4; speaking the instant ack while the LLM works (already happens); a GPU. **Thinking flag:** `LocalLlamaRuntime` already passes `--reasoning-budget 0 --jinja` for all requests, so thinking is already off for local voice turns. I did not add the `voice: true` request flag or `tests/core/test_voice_flag.py`, since it would be a no-op for the local provider. The planner should decide if it's still wanted for cloud providers.

**Tests:** `pytest -q tests --ignore=tests/e2e` → `178 passed, 2 skipped in 161.50s`.

**Not done:** numbers not yet pasted into PLAN.md "Measurements" (planner's file; they're here). No mic recording. `tests/assets/weather_tomorrow.wav` from a real voice still needs recording; the bench uses the TTS-made clip.


## 2026-10-20 — Resume M1-B1: repair and verify voice subset draft

Found the existing M1-B1 draft in toolkit/server and its tests. Fixed malformed multiline VOICE_INSTRUCTIONS that prevented server imports, and the missing Path import in the drafted subset test. Unavailable voice tool calls now explicitly point to the Atulya app/chat; text calls retain their existing error. Updated tools/voice_bench.py to use VOICE_TOOLS and spoken instructions. Added a regression for the fallback.

Validation: Python compilation passed for toolkit/server/bench; focused voice tests: 3 passed, 12 deselected. Full suite: 183 passed, 2 skipped in 173.62 s. Initial sandbox test runs hung in Windows asyncio socket.socketpair; stopped those runs and reran outside the sandbox successfully.

Live one-run bench (base STT, existing TTS settings): server startup 66.16 s; cold STT 30.13 s, cold TTS 7.72 s; warm STT 0.87 s; first acknowledgement audio 2.20 s; answer sentence 16.79 s; answer audio 20.08 s. The answer asked for location, so correctness and latency targets remain unmet. This single sample is not a five-run comparison; no improvement claim. The bench also emitted an async-generator cleanup error (athrow(): asynchronous generator is already running) despite exit code 0; stream cleanup needs follow-up. User context (M1-B5) is still required. No GOAL completion boxes changed.


## 2026-10-20 — M1 context, stream lifetime and language-specific STT

Previous goal turn classified as progress: it repaired the voice draft and produced a real slow/incorrect-location bench result. Continued from those receipts, not completion claims.

Changes:
- New atulya/voice_context.py supplies compact per-user name/city/language/style, current offset-aware time and recent device coordinates or saved home as a data message. Voice profile fields no longer change the system prefix; text chat keeps its profile instructions. Tests exercise changed profiles and user isolation.
- Weather now uses recent device location, saved home, then the profile city without an unnecessary location prompt. _near uses the same default freshness limit instead of accepting week-old device coordinates.
- Brain closes the provider stream in finally; the compatible provider closes its inner HTTP stream explicitly. The bench also closes Brain when it stops at the first answer, and reuses one event loop for all runs/client cleanup. A test stops a real httpx mock stream after its first sentence and proves closure before returning.
- LocalVoice lazily caches separate tiny.en (ATULYA_STT_MODEL_EN override) and multilingual base (existing ATULYA_STT_MODEL). English language codes/profile names choose tiny.en; Hindi, automatic detection and other supported profile languages use the multilingual model. Each has an independent idle timestamp. Readiness checks both actual model snapshots, not just a marker or any model.bin. First-run preparation ensures both models exist. /api/voice/transcribe falls back to the signed-in user's language when the request leaves it blank.
- The bench accepts --user and --language, builds a real profile-backed registry toolbox, and synthesizes sentences as they arrive rather than synthesizing only after collecting the whole answer. Audio timing means WAV-ready time, not observed speaker playback.

Validation: compilation passed. Targeted voice/weather tests: 36 passed. Full suite: 190 passed, 2 skipped in 164.19 s. After removing the final saved-city location-sharing suggestion, profile/weather/API/stream checks: 11 passed in 33.62 s.

Live synthetic STT receipt: output/voice-validation/stt-language-check.json. Ten English transcripts were exact; tiny.en median 0.7865 s, range 0.450–0.933 s. The <=0.65 s target is unmet. Synthetic Hindi selected base but returned an inaccurate Latin transliteration (cold 11.962 s); do not call Hindi accuracy verified. Hindi clip saved alongside the receipt. No microphone or speaker was used.

The owner supplied Sangam Vihar, New Delhi, Delhi, India for the weather check; it is now the local admin profile city. The ten-turn live weather baseline completed (exit 0) and wrote output/voice-validation/weather-bench.txt. First turn: acknowledgement WAV ready 5.59 s, answer WAV ready 55.30 s; it used Sangam Vihar without asking for location. This does not meet the latency gate. M1-B2 runtime cache flags, M1-B4 acknowledgement caching/quality gate, M1-B6 deterministic routing, physical-device voice checks and all later milestones remain open. No GOAL boxes were checked.


Weather baseline final receipt: 10 turns, no async-generator cleanup error. Median acknowledgement WAV-ready time 3.235 s; median reported answer/fragment WAV-ready time 28.465 s (range 19.61–55.30 s). This run exposed numeric fragments ending at a delta boundary (e.g. "20." before the "3" of 20.3). The running process used the earlier parser, so its answer rows are not valid ten-of-ten correctness evidence. The corrected parser waits for whitespace or end-of-stream; a split-decimal regression plus context/closure tests passed (4 passed). See weather-bench-summary.json for this limitation. Even the observed fragments are far over the target. No production speed claim.

Independent live reference saved to output/voice-validation/sangam-vihar-weather-reference.json: Nominatim resolved the owner's city to 28.5057128, 77.2484672, label "Sangam Vihar, Delhi, India"; the get_weather handler returned Open-Meteo data for tomorrow (21 October), 20.3–30.8 C, rain 0%, with current AQI/warning and provider timestamp. This reference proves actual tool retrieval, not that all ten generated answers reproduced it correctly. The owner weather correctness gate and real mic/speaker gate remain open. Next implementation work: M1-B2 runtime cache tuning, M1-B4 cached acknowledgement speech, and M1-B6 direct routing through the existing approval-aware Toolbox.

## 2026-10-21 — AUDIT N5–N8, M1-B2 (prompt prefix cache), bench gate runs 1–2, M1-2/M1-3/M1-4 code, B17

**AUDIT fixes**
- **N5 (Linux lock):** `tools/make_lock.py` keeps client-only packages (`openwakeword`, `sounddevice`) out of the Linux closure, writes `sys_platform == "linux"` for Linux-only lines, and fails instead of writing an unpinned line. The regenerated `requirements.lock.txt` (81 pins) has no `tflite-runtime`, and `openwakeword`/`sounddevice` are win32-only. Proof: the Linux view of the lock (win32 lines dropped) passes `pip install --dry-run --no-deps --only-binary=:all: --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 --python-version 3.12` ("Would install …" for all of them). Not installed on a real Linux box. Note: pip `--platform` still evaluates markers against the host, so a filtered copy was needed. New test `test_lock_lines_are_pinned_and_client_only_packages_skip_linux`.
- **N6:** the Android SMS dialog now shows the full body (`sendDirectSms` already refuses > 2000 chars; AlertDialog messages scroll). Still not compiled (no JDK/SDK). The "not in contacts" warning is not done: it would need READ_CONTACTS.
- **N7:** a truncated 16 kHz WAV (odd byte count) drops the half sample; `ValueError` falls back to the file path. Test `test_truncated_wav_does_not_crash`.
- **N8:** `voice_bench`:
  - `--say "<question>"` synthesizes the question and resamples it to 16 kHz mono (`to_16k_mono`; `--wav` input is resampled too), so the in-memory STT path is the one measured.
  - It now uses the same stores as `/api/chat` (memory, calendar, reminders, action queue) in a **throwaway copy** of the data folder (only `profiles.sqlite3` is copied), so bench runs create no real reminders.
  - The stop rule is now explicit: the first sentence that is not an acknowledgement or tool filler ("One moment." etc.).
  - Tests: `tests/voice/test_voice_bench.py` (3).

**M1-B2:**
- `LocalLlamaRuntime.command()` adds `--cache-reuse 256 --slot-save-path models/runtime/llama-slots --threads N --threads-batch N -fa auto` (N = cpu_count, was cpu_count−1 for generation only). `--mmproj` only with `ATULYA_VISION=1`; `--log-file` with `ATULYA_LLAMA_LOG`.
- Requests to a local base URL send `cache_prompt: true`.
- The slot is restored on start when `voice-prefix.bin` exists, and saved once after the first finished voice turn (server stream end and bench).
- Slot path is under `models/runtime/` rather than `data/`: it's a machine-local cache tied to the model.
- Tests: `tests/providers/test_local_llm_args.py` (4), `tests/core/test_voice_prompt_prefix.py`: the system prompt and tool schemas are byte-identical for Delhi/18:05 vs Mumbai/07:40; city and time only appear in the Context message.
- **Live (llama log):**
  - cold run 1 evaluated 1307 prompt tokens in 16.7 s; runs 2–4 evaluated 96 tokens in 1.4–3.3 s;
  - after a restart with the saved slot: "restored 4 context checkpoint(s)", and the first turn evaluated 96 tokens in 2.6 s;
  - llama.cpp prints "cache_reuse is not supported by this context, it will be disabled" (Qwen3.5 hybrid model). Plain prefix caching does the work.
- **Side effect to decide:** without `ATULYA_VISION=1`, camera/image chat on the local model has no projector. The server still lists the local provider when the projector file exists.

**Bench gate.** i3-9100F, `--language en` (tiny.en), TTS 8 steps (owner choice), 10 runs each, times = WAV ready (not speaker playback). Receipts in `output/voice-validation/gate-*.json` and `gate2-*.json`.

*Run 1* (old bench and templates):
- **Weather:** fast path, ack 0.43–1.37 s, answer 7.25–15.0 s. The spoken text was the raw card (one 180-char sentence with symbols and the provider line).
- **Reminder:** the bench stopped at the tool filler "One moment." (7.3–33 s).
- **News:** ack 0.46–1.59 s, answer 12.5–42.3 s.

*Fix between runs:* `intents.weather_sentence` now speaks short sentences, the answer first: "Tomorrow in Sangam Vihar, Delhi, India: 20.3 to 30.8 degrees, rain 0 percent.", then air quality, the warning, and "Source: Open-Meteo, <time>". Every value and the provenance are still spoken. Tests in `test_intents.py`/`test_voice_fast_path.py` were updated to the new wording.

*Run 2:*

| prompt | route | T1 first audio median / max | answer audio median / p90 (min–max) | target |
|---|---|---|---|---|
| weather tomorrow | voice_fast 10/10 | 0.55 / 1.25 s | **4.57 / 6.19 s** (3.00–6.48) | T2 ≤ 3.0 median, ≤ 4 p90: **not met** |
| remind me in 10 min to call mom | llm 10/10 | 13.31 / 19.86 s (no instant ack for "remind") | **20.13 / 25.76 s** (12.56–27.25) | T3 ≤ 8 median, ≤ 12 p90: **not met** |
| what's in the news | llm 10/10 | 0.66 / 1.07 s | **16.31 / 19.51 s** (10.45–26.45) | T3: **not met** |

- Weather answers matched the Open-Meteo reference (20.3–30.8 °C, rain 0%) 10/10.
- Reminder replies were "Reminder saved." / "Done." / "Saved."; the bench did not check that a reminder row was actually written in the throwaway store. Unverified.
- **Bug found:** 1/10 news replies spoke the model's raw `{"reasoning": …}` JSON. Fixed in `tools/plugins/brain/textcalls.py`: a reply that *starts* with `{` is held. A call becomes a tool call, an answer-type field is shown, pure reasoning is dropped, and non-JSON is released unchanged. Test `tests/plugins/test_textcalls_json.py` (5). Not re-benched yet.
- **Where the time goes** (llama log): generation runs 4–7 tok/s, falling to ~3.8 tok/s while TTS runs. A tool turn needs about 40–60 tokens of call JSON before any answer, then a second round. Per the PLAN, T3 p90 > 12 s, so the next steps are: 2 history turns, voice `max_tokens` 80, an instant ack for "remind", and trying Qwen3.5-0.8B for voice routing. Planner's call.
- Earlier observation, not a gate prompt: the model called `remember_fact` for "tell me a fun fact about owls" (~14 s wasted).

**M1-2/M1-3/M1-4 code:** new package `tools/voice_loop/`:
- `audio_io.py`: `Mic` (16 kHz int16, 80 ms frames, drops the oldest on overflow); `Player` (queued playback, `stop()` within one 20 ms block, `wait()`).
- `wake.py`: `WakeDetector` with openWakeWord ONNX. The default is `ATULYA_WAKE_MODEL`, then `atulya.onnx`, then interim `hey_jarvis` (NC licence, testing only).
- `vad.py`: `SileroVAD` via onnxruntime on `models/voice/wake/silero_vad.onnx` (v4, 512-sample chunks); `Endpointer` (600 ms silence, 8 s max, 5 s no-speech).
- `sentences.py`: `split_ready` (decimal-safe, ≥ 20-char first piece, 120-char cap).
- `client.py`: `ServerClient` (device token; transcribe, voice-mode SSE chat, synthesize).
- `loop.py`: `VoiceLoop`, IDLE→LISTENING→THINKING→SPEAKING. Sentence N+1 is synthesized while N plays. Pending approvals are spoken as "Waiting for your approval in the Atulya app: …" and never approved. 6-turn history. A per-turn line goes to `logs/voice_loop.log`.
- Barge-in v1: the wake word during THINKING/SPEAKING stops the player, closes the stream and listens again.
- `__main__.py`: `--pair NAME` (local pairing with the `voice_loop` ability; the token goes to `data/voice-loop.token`), `--wake-test`, and the loop.
- **R4:** `/api/chat` and `/api/voice/*` accepted only the passkey session cookie. `SessionAuthMiddleware` now also accepts `Authorization: Bearer <device token>` on exactly `/api/chat`, `/api/voice/transcribe` and `/api/voice/synthesize`, for a non-revoked device with the `voice_loop` ability whose owner is an admin (403 otherwise). `AgentHub` gains `ABILITIES = COMMANDS | {"voice_loop"}`, and `authenticate()` also returns abilities.
- Tests: `tests/voice/test_voice_loop.py` (13: sentences, endpointer silence/max/no-speech, wake threshold, real hey_jarvis model on 30 s of silence/noise → no hit, player stop, client SSE + token, loop states and pipelining with "synthesize starts before the stream ends", spoken pending approval, barge-in cancels and stops synthesis, wake→listen), `tests/core/test_device_token_voice.py`.
- **Not run on hardware:** no `--wake-test` with a person speaking, no mic turn, no speaker playback, no barge-in timing. The PLAN M1-2/M1-3/M1-4 live checks are all **open**.

**B17 (security):** device tokens can never reach `/api/actions/*`. The `/api/actions/` pattern is gone from the device routes, and `ServerClient` has no approve/deny method. `app.state.action_queue` is exposed for tests. `test_device_token_voice` now creates a real pending action, posts approve and deny with the voice token (both 401), and asserts the action is still pending for the owner. A test also asserts the loop client has no `decide`/`approve`. Spoken approvals (M2-2) need a separate design: a human-session-bound path on the owner's own interactive client, with a test, before any code.

**Tests:** full suite `pytest -q tests --ignore=tests/e2e` → **268 passed, 2 skipped in 348.49 s**. `test_device_jobs.py::test_pairing_scopes_devices_jobs_and_revocation` failed once in an earlier full run while the bench was running, and passed alone and in this full run. Possibly flaky; not investigated.

## 2026-10-21 — M2-3 / B20 / CL7: document reading with pypdf, `read_document` tool

**Changed:**
- `tools/plugins/information/document.py`:
  - PDF now uses **pypdf** (BSD) instead of pymupdf (AGPL); no pymupdf/fitz references remain in code, pyproject or the lock.
  - New PPTX reader (python-pptx; the slide count is reported as `page_count`).
  - `.doc`/`.xls` were removed from the supported types: python-docx and openpyxl cannot read them, so they are now refused instead of failing oddly.
  - XLSX opens `read_only`.
- `tools/plugins/system/actions.py`:
  - `resolve_document(path)`: only Desktop/Documents/Downloads, absolute or home-relative as `search_files` prints it. The path is resolved before the check (symlinks and `..`). The file must exist and be ≤ 25 MB.
  - `search_files(..., ext="")`: type filter; the query may be empty when `ext` is set; still newest-first.
- `tools/plugins/toolkit.py`:
  - New `read_document` tool in the `pc-control` plugin, so it is removed on Telegram/Android and on headless servers, like the other PC tools.
  - It returns the file name, the page count and ≤ 3500 chars, marked "first part only/[truncated]" when cut. (The plan said 6000, but `Toolbox.call` caps every result at 4000 chars.)
  - The text is wrapped as `<<UNTRUSTED DOCUMENT CONTENT …>> … <<END>>`, and both the text and voice instructions now cover document content.
  - `search_files` gains the `ext` parameter.
  - `read_document` was added to `VOICE_TOOLS` for the M2 voice check. This adds ~100 prompt tokens to the cached voice prefix; the saved slot is refreshed by the next process's first voice turn.
- **Deviation from PLAN:** `read_document` is `confirm=True, low_risk=True` (same as `search_files`), not direct. It sends a private file's text to the model, possibly a cloud provider. With safety `ask_risky` it runs without a prompt; with `ask_all` it asks. Added to the policy table. Planner/auditor to confirm.

**Tests:** new `tests/plugins/test_documents.py` (5):
- PDF (hand-built one-page file), DOCX, XLSX, PPTX and TXT text plus page count; `.doc` refused;
- the tool's wrapper and truncation (≤ 4000 chars);
- outside paths refused: an absolute path elsewhere, `Pictures/`, `Documents/../../…` traversal, a missing file; the secret text never appears in the reply;
- approval under `ask_all`;
- `ext` filter and newest-first ordering.

Full suite `pytest -q tests --ignore=tests/e2e` → **273 passed, 2 skipped in 273.25 s**.

**Not run:** the GOAL M2 live check (a real invoice PDF in Downloads, "find my latest invoice PDF and tell me the total" by voice). It needs the mic loop running on hardware, which is still unverified. A scanned/image-only PDF returns "no readable text"; there is no OCR.


## 2026-10-21 — Codex review of Claude's voice loop and document work

Reviewed the current M1 loop/client, narrow device-token middleware, JSON reply filter, document readers and tests against Claude's implementation notes. Found and fixed:

1. DOCX tables were returned in a separate tables field but omitted from text; read_document only sends text to the assistant. Invoice totals in table cells could therefore disappear. The reader now includes table rows in document order alongside paragraphs. Regression includes an invoice amount in a DOCX table and checks ordering.
2. Cancelling VoiceLoop.respond itself could leave its reply and wake-watch tasks alive; _reply cancelled its synthesis worker without awaiting its cleanup. Outer cancellation now stops playback, cancels and awaits both tasks; synthesis is also awaited on exit. Regression cancels during a blocked synthesis and asserts stream closure, worker cleanup and no remaining asyncio tasks.
3. TextCallFilter dropped valid reasoning JSON but released it raw when JSON was truncated by a token limit or disconnect. Recognized reasoning-key fragments are now suppressed even when the JSON is incomplete. Regression covers truncated reasoning and analysis/answer objects.

Focused review checks: 24 passed for documents, voice loop, device-token scope and original JSON cases; after the truncated-JSON repair, 24 passed for documents/voice/JSON. Device token tests include denial of action approval and denial routes. Full regression run completed: 284 passed, 2 skipped in 152.47 s. The additional truncated-JSON regression passed separately after collection (24 focused checks passed). Changed modules also passed Python compilation.

Remaining verification: hands-free microphone/speaker/barge-in hardware checks, native Atulya wake model, actual invoice voice task and all original latency gates. Claude's logged weather/reminder/news gates remain above target. The interim hey_jarvis fallback is still automatic despite its own docstring saying it must not be the shipped default; treat the current loop as a test setup until that choice is explicit or the custom model exists. Document readers still read full contents before tool-output truncation; large/compressed documents and timed-out worker resource use need a separate bounded-extraction pass. No GOAL checkboxes changed.

## 2026-10-21 — M12-1, M12-2, M12-3 (multi-user separation)

**M12-2: admin-only tools on every channel**
- `Tool.admin_only` is a new field. `ADMIN_ONLY_TOOLS` sets it for:
  - every `pc-control` tool;
  - `smart_home_control`, `cast_to_tv`, `visual_inspect`, `ask_device`, `device_action`;
  - `restart_service`, `server_status`, `server_logs`, `atulya_status`;
  - all `maintenance_*` and `mcp_*` tools;
  - `gmail_search/drafts/send`.
- Enforced three times:
  1. `Toolbox.__init__` drops these tools from a non-admin's schemas (the model never sees them; this also covers the voice subset);
  2. `Toolbox.call` returns "That is admin only on this Atulya; nothing was done.";
  3. `Toolbox.run_approved` refuses them as well.
- **Channels:**
  - Telegram tool contexts now pass `is_admin=True` explicitly instead of relying on the literal "admin" id fallback. Only allow-listed owner chats get tools; open-mode guests get none.
  - MCP stays `public_only`.
  - Device-token chats run as an admin owner only (M1-3); B17 still keeps them away from `/api/actions/*`.
- **Not changed:** several allow-listed Telegram ids all share the owner account. Separate Telegram identities are PLT-05 (M14).
- Tests:
  - new `tests/plugins/test_admin_only_tools.py` (8): the exact admin-only set; a user on web/telegram/android has none of these schemas while ordinary tools stay; the admin keeps them; call and `run_approved` are refused even when a tool slips into a user's Toolbox; the voice subset for a user has none.
  - `test_approval_policy._toolbox` and `test_capabilities` (Gmail) now mark their owner contexts `is_admin=True`.

**M12-1: route access table**
- New `atulya/route_access.py` classifies all 105 method+path routes as public/device/user/admin. `SessionAuthMiddleware` answers **403 for any admin route before the handler or body validation runs**, so a non-admin can't get a 422 that leaks the schema. Existing in-handler checks stay as a second layer.
- Admin routes: maintenance (6), MCP connections (4), automations (3), `reminders/cancel-all`, signups (2), users (3), credentials, connections, plugin toggle, Telegram reminders, notifications, activity, smart-home scene. These are the routes whose handlers already refused non-admins.
- I did not add a FastAPI `require_admin` dependency on each route as PLAN suggested. The middleware table is the single enforcement point, and it also covers routes in `workspace_api.py`/`automation_api.py`.
- New `tests/core/test_route_access.py` (31):
  - every registered route must be in the table, and no stale entries;
  - for each admin route: a second `user` account gets 403 and no session gets 401;
  - the admin still reaches admin routes; the user still reaches user routes.

**M12-3: private devices**
- `/api/devices/{name}` (DELETE) and `/api/devices/{name}/test` return **404** for a device that is not the caller's (was `{"revoked": false}` / 422), so another account's device is never confirmed to exist.
- Pairing with the `voice_loop` ability is 403 for non-admins, in the API and in `python -m tools.voice_loop --pair` (which checks `AuthStore.is_admin(--owner)`).
- Tests (in `test_route_access.py`):
  - Bob lists only his device; the admin list doesn't show Bob's;
  - Bob's test/revoke on the owner's device → 404, and the owner's device and jobs are untouched;
  - Bob's own device test → 202;
  - voice_loop pairing: Bob 403, admin 201.

**Per-user profiles:** profiles were already keyed by `user_id` (`ProfileStore`); `test_voice_prompt_prefix`/`voice_context` tests cover per-user isolation. Nothing new here beyond M12-6 below.

**Tests:** full suite `pytest -q tests --ignore=tests/e2e` → **323 passed, 2 skipped in 189.02 s**.

**Not run:** the live check (sign in a second real account in the WebUI and curl the admin routes, or "lock the PC" from that account). Only ASGI-level tests so far.

## 2026-10-21 — M12-6: age-based content settings (server side)

**Changed:**
- New `atulya/content_policy.py`:
  - levels `child` / `adult` / `adult_open`;
  - `policy_from(raw_profile, is_admin)`: an admin override wins, then the date of birth (age is computed on every request, so a child becomes adult at 18), else **admin role → adult, any other account → child until a DOB is given**;
  - fixed instruction text per level; `safesearch` per level;
  - `illegal()`: sexual terms combined with minor terms, refused at **every** level including `adult_open`, with no setting;
  - `blocked_category()` for children: sexual, drugs, gambling, graphic violence;
  - a small child domain blocklist for `read_url`.
- `atulya/profiles.py`: private keys `_age` (birth_date, source self/google/admin, override), `_adult_content`, `_notify_blocked`. They are not in CHOICES/TEXT_FIELDS/VOICE_EDITABLE, so `update_profile`, voice edits and `PUT /api/profile` can't touch them (422). New methods:
  - `set_birth_date`: once; a second change raises PermissionError unless the source is admin;
  - `set_age_override`: forcing child also clears adult_content;
  - `set_flag`;
  - `record_content_event`: stores user, time and category, **never the text**; returns True only when notify_blocked is on and no alert went out in the last hour;
  - `content_events`, `content_policy`.
- `atulya/server.py`:
  - `/api/chat` computes the policy from the server profile before anything else (command plugins, the fast path, the model). A blocked request returns `{"text": refusal, "route": "content_policy"}`.
  - For a child, it records an event and, at most once an hour, sends the owner a Telegram alert with the **category only**.
  - The level's instruction text is added to the text-chat style and becomes the voice style. The voice text is fixed per level, so the prompt cache still applies.
  - The tool context gets `content_level`.
  - New routes:
    - user: `GET /api/profile/content`; `PUT /api/profile/birth-date` (once, 403 after; notifies the owner of the age group); `PUT /api/profile/adult-content` (422 unless adult);
    - admin: `PUT /api/auth/users/{user_id}/content` (age_group override and notify_blocked); `GET /api/content-events`.
  - All five are added to the M12-1 route table.
- `tools/plugins/registry.py`: `PluginContext.content_level` (default "adult" for non-chat callers such as Telegram owner chats and MCP public tools).
- `tools/plugins/information/search.py` `search_web(..., safesearch)`: DuckDuckGo `kp` = 1 strict (child) / −1 moderate (adult) / −2 off (adult_open). `toolkit._read_page` refuses blocklisted domains for children.

**Tests:** new `tests/core/test_content_policy.py` (12):
- the age boundary (17 y 364 d → child, exactly 18 → adult);
- levels from the profile, including no DOB → child, admin role → adult, a child's adult flag ignored, admin override;
- the DOB is set once and the admin may correct it; the age fields can't be set through `update`/VOICE_EDITABLE/`update_profile`;
- an illegal request is refused at all 3 levels, with no false positive on "my kids love dinosaurs" or adult sex-education wording;
- the child category list;
- the search `kp` per level against a stubbed client;
- the read_url blocklist for children only.
- API:
  - DOB → child, a second DOB → 403, a child's adult opt-in → 422, adult opt-in → adult_open, `age_group` through PUT /api/profile → 422;
  - the admin routes are 403 for users, and the override is recorded as `age_source=admin`;
  - chat: a client-sent `adult_content`/`content_level` changes nothing; child requests are blocked; events hold categories only; one alert flag per hour;
  - an illegal adult request is blocked;
  - the system prompt carries the child / adult_open text, and the admin gets neither.
- `test_approval_policy`'s fake `search_web` now accepts the new keyword.
- Full suite `pytest -q tests --ignore=tests/e2e` → **337 passed, 2 skipped in 315.10 s**.

**Deviations / not done:**
- Accounts with the **admin role and no DOB are treated as adult**; the plan said everyone without a DOB is child, which would have downgraded the owner. Planner to confirm.
- **No sign-up UI** for the date of birth. The webui2 files belong to the other session; the API is ready for it.
- The **Google birthday** (`user.birthday.read` scope) is not wired; `source="google"` is accepted by the store only.
- No **after-model** check of the reply text; only the request is checked.
- Music/news filtering for children (age-restricted YouTube results) is not done.
- The illegal-content and child lists are keyword patterns: a floor, not a classifier.
- **Not run live:** a real second/third account sign-up, a real Telegram alert, or real DuckDuckGo results per level.

## 2026-10-21 — M12 re-audit fixes S1–S5 (B24, B25, B26)

**S2 / B25 (fail closed):**
- `toolkit._is_admin` returns `ctx.is_admin is True`; the literal user id "admin" no longer grants anything.
- `is_admin=True` is set explicitly in Telegram's owner contexts (meeting list, command dispatch, plus the two tool contexts), in the server's maintenance monitor, and in `voice_bench` (from `AuthStore.is_admin(--user)`).
- `test_owner_only_tools.test_second_admin_is_treated_as_owner` now asserts that the bare "admin" id is **not** admin.

**S1 / B25:**
- `user_id` is a **required keyword** with no default on `PersonalMemory.remember/forget/list/relevant/update` and `ConversationHistory.append/read/conversations/search/delete`.
- Every product caller was converted, including those going through `asyncio.to_thread`, which passed it positionally: `server.py` conversations; Telegram guest and owner history (6 calls); `toolkit` search_past_chats.
- An AST and grep scan found no remaining caller without it.
- New `tests/core/test_no_default_user.py`: signature checks, and a missing user_id → TypeError. Old tests that relied on the default now pass `user_id` explicitly.

**S3 / B24:**
- `PluginContext.origin` and `PendingAction.origin` are new. Telegram owner contexts set `origin="tg:<telegram id>"`.
- `ActionQueue.take(..., origin=)` refuses a different origin and leaves the action pending for its real requester. The Telegram Approve button passes `origin=f"tg:{user_id}"`.
- `docs/CONNECT-AND-VERIFY.md` now says the allowlist is **owner only**; family members use `/register` and become approved `tg_<id>` members.
- Tests: new `tests/communications/test_telegram_action_origin.py`; `test_reminders_telegram` now checks that allow-listed id 222 can't approve 111's action and that it stays pending.

**S5:**
- `ask_device` and `device_action` are no longer admin-only; `AgentHub` scopes every job to the caller's own devices. `cast_to_tv`/`visual_inspect` stay admin-only.
- New test `test_users_control_their_own_devices_only`: a user pings their own device; a `device_action` on the owner's device fails at run time with "not paired to you"; no job is created for the owner.

**S4 / B26 (CSP):**
- `CONTENT_SECURITY_POLICY` in `server.py`:
  - `default-src 'self'`;
  - `script-src 'self' 'wasm-unsafe-eval' https://telegram.org https://www.youtube.com https://s.ytimg.com`;
  - `connect-src 'self'`;
  - `style-src 'self' 'unsafe-inline'` (the renderer injects `<style>` keyframes);
  - `img`/`media`/`worker` allow `blob:`/`data:`;
  - `frame-src` YouTube only;
  - `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`, `form-action 'self'`.
- The only inline script in `webui/index.html` (service-worker registration) moved to `webui/sw-register.js`. It was added to the SW shell, and the SW cache was bumped to v5.
- **Browser check** (built-in browser pane):
  - (a) The dev server (port 8599) has the header live, `inlineScripts: 0`, and no CSP errors on the sign-in page.
  - (b) A second dev server on a **throwaway data folder** (port 8598) with a test admin session: the signed-in app renders (3D scene, panels, greeting), and every API call is 200, including the `/api/events` EventSource. No "Refused"/CSP console errors.
  - Probes: the YouTube iframe_api script **loads**, the youtube-nocookie iframe is allowed, `WebAssembly.compile` **ok**, a fetch to example.com is **blocked** (`connect-src` violation), an injected inline `<script>` is **blocked** (`script-src-elem`, did not run).
  - Not exercised in the pane: the camera, gestures and mic (blocked in the pane), and real music playback.
  - Both preview servers were stopped and the temporary launch config removed.
- New `tests/core/test_csp.py` (3): policy directives, no inline `<script>`/`on*=` handlers in index.html, header sent.
- Not done: `frame-ancestors 'none'` (unchanged from before) may block the WebUI inside Telegram **web**'s iframe. Telegram mobile webviews are not iframes. Unverified.

**Tests:** full suite `pytest -q tests --ignore=tests/e2e` → **347 passed, 2 skipped in 261.52 s**.

## 2026-10-22 — M12-4 (per-user limits), M12-5 (admin can't read others' chats), M12-6 end to end (UI)

**M12-4:**
- `ProfileStore` stores per-user daily limits in private `_limits` (defaults: 300 messages and 150 tool calls a day for non-admins; admins unlimited). New `limits`/`set_limits` (0–100000, `None` = default), `consume` (atomic, counts nothing once at the limit), `usage_today`; daily counters live in the `usage` table.
- Enforcement:
  - `/api/chat` → **429** "today's message limit" for non-admins;
  - `Toolbox.call` (`_over_tool_limit`) → "today's tool limit…; nothing was run" for non-admin contexts that have a profile store.
- New admin route `PUT /api/auth/users/{user_id}/limits` (in the route table). `GET /api/auth/users` now returns each account's limits, today's usage, age group/source, content level and notify flag.
- **Admin UI** (`assistant.js` users dialog): each non-admin card shows "Today: x/limit messages · y/limit tool calls · Age: group (source)", with buttons:
  - SET LIMITS (two prompts; blank = default);
  - AGE: AUTO → ADULT → CHILD (admin override; AUTO follows the DOB);
  - ALERTS: ON/OFF.
  - Invite/disable and passkey revoke already existed.

**M12-5:** new tests prove the admin **cannot** read, list or delete another account's conversation. `GET /api/conversations/{id}` returns no messages, the list doesn't include it, and DELETE removes 0 messages while the owner's copy stays. The routes were already scoped by `user_id`; S1 made forgetting it impossible.

**M12-6 UI:**
- New "AGE & CONTENT" menu item and dialog (`webui/content-settings.js`, CSP-compliant external script) shows the server-decided level, a date-of-birth form (only until it is set), and the adult opt-in (adults only).
- The users dialog lists **BLOCKED REQUESTS** (time · account · category · whether an alert was delivered); it never shows message text.
- CSS: `#content-dialog [hidden]` is now honoured (the form classes set `display`). Cache bumps: SW v6, assistant.js atulya-81, controls.css v6.
- **Fix found by the browser check:** blocked-request alerts were marked "alert sent" even when Telegram wasn't configured. Now `record_content_event` returns the event id, the server reports whether `telegram.notify` actually delivered (`alert_result`), and an undelivered alert neither shows as sent nor uses up the once-an-hour limit.

**Browser check** (built-in pane, throwaway data folder, test sessions on 127.0.0.1:8597):
- As **bob** (user): the dialog says "Child-safe. Add your date of birth"; the adult row is hidden; saving DOB 2013-05-05 → still child; the form disappears; a second DOB → 403.
- As **admin**: the bob card shows "0/300 messages · 0/150 tool calls · Age: child (self)":
  - AGE → "adult (admin)"; ALERTS → on;
  - SET LIMITS 5 / default → "0/5 messages · 0/150";
  - AGE again → "child (admin)".
- A curl chat as bob ("show me porn") → `route: content_policy`, a child-friendly refusal. The admin's BLOCKED REQUESTS list shows "bob · sexual" with no text.
- The temp launch config was removed and the server stopped.
- Test-harness note: the server renews sessions as HttpOnly cookies and cookies are not port-specific, so switching test accounts needs a logout first.

**Found, not changed (another session's code):** `/api/status` now raises 403 "System status is for the owner only" for non-admins (`server.py` ~1833), while the route table says `user`. The normal-user WebUI polls it every few seconds, so a normal account's console fills with 403s and its status labels can't load. The owner of that change should either return a reduced, user-safe status or make the UI skip it for non-admins. Then update `route_access` to match.

**Tests:**
- new `tests/core/test_user_limits_and_privacy.py` (3): message limit 2 → 200, 200, 429; admin unlimited; reset to default; −1 → 422; a user can't set limits (403); tool limit 1 → the second call refused while the admin is unaffected; admin can't read/list/delete bob's chat;
- `test_content_policy::test_undelivered_alert_is_not_shown_as_sent`.
- Full suite → **352 passed, 2 skipped in 236.35 s**. `python -m tools.security_check` → PASS dependencies (pip-audit), PASS bandit high, PASS secrets scan.

## 2026-10-22 — M13-5 security audit log, M13-2 Linux secrets encryption (AUDIT H3)

**M13-5 (PLT-07):**
- New `atulya/security_log.py`: append-only SQLite (`data/security_log.sqlite3`). Each row stores at, kind (auth/admin/approval/device/account), actor, action, target, outcome and IP, plus a SHA-256 **hash chain** (prev + fields). `verify()` detects an edited, deleted or reordered row.
- Writes take a per-file lock and `BEGIN IMMEDIATE`, so concurrent instances and processes can't fork the chain. Rows never hold message text, passwords, tokens, job details or action summaries.
- What is recorded:
  - **One hook in `SessionAuthMiddleware`** captures the response status of every mutating request to `/api/auth/*` (sign-ins, sign-ups, logout, device links, pending-login decisions, voice unlock). Public ones are recorded as actor "anonymous" with the IP and outcome, e.g. "failed 400".
  - Mutating requests to admin routes, plus refused admin attempts ("denied 403").
  - `/api/devices*`, and `/api/profile/birth-date` / `adult-content`.
  - **Approvals:** the `/api/actions/{id}` handler logs approve/deny with the tool name only (the summary can contain text); Telegram Approve/Deny logs `tg:<id>`.
  - **Device jobs:** `AgentHub.pair/revoke/enqueue/complete` are wrapped and log device and job kind, outcome ok/refused/not found; never the detail (SMS text, paths) or the pairing token.
- New admin route `GET /api/security-log?kind=&limit=` (in the route table) returns events and `intact`. The WebUI users dialog shows "SECURITY LOG" (latest 40, with a warning if the chain is broken).
- Tests (new `tests/core/test_security_log.py`, 3):
  - an edited or deleted row → `verify()` False;
  - a failed sign-in (anonymous), a refused admin change (bob, denied 403), an admin change (ok 200), bob's device pair and job, and an approval deny (tool name only) all appear;
  - a user gets 403; no "Notepad" summary or token text in the output;
  - a device job's SMS detail and number are never logged; a refused enqueue is logged "refused".

**M13-2 (AUDIT H3):**
- `atulya/secrets_store.py` off Windows now uses **Fernet** (`cryptography`, already pinned) with a random key in `$XDG_CONFIG_HOME/atulya/secrets.key` (or `ATULYA_SECRETS_KEY_FILE`), **outside `data/`**.
- The key directory is 0700 and the key 0600, created with O_EXCL so a race can never replace a key. `secrets.enc` is 0600 after every write. Old `PLAIN:` files are re-encrypted on load. Windows keeps DPAPI. All writes go through `_write`, which verifies before `.env` is touched.
- New `tests/core/test_secrets_store.py` (5; the mode test is skipped on Windows):
  - round trip as `FERNET:` with no plaintext in the file and no key under data/;
  - a different key can't decrypt (a copied data folder);
  - PLAIN → FERNET migration;
  - owner-only modes on POSIX;
  - `protect()` from `.env`.
- The Linux path ran here via `ATULYA_SECRETS_SCHEME=fernet` on Windows. **Not run on a real Linux box** (file modes untested here). `docs/CAPABILITIES.md` PLT-08 still needs updating by its owner.

**Tests:** full suite → **360 passed, 3 skipped in 393.42 s**. `python -m tools.security_check` → PASS pip-audit, PASS bandit high, PASS secrets scan.

**Not done:** the security-log UI wasn't re-checked in the browser after the M12 check; it uses the same dialog and fetch pattern as BLOCKED REQUESTS, which was verified.
