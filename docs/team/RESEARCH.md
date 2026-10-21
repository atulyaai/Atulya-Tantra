# RESEARCH — free/open-source options per milestone

Owner: researcher session. Scope so far: **M1** and **M3** (M2, M4–M6 short notes at the end, full pass to follow).
Targets: Windows 11 PC (main voice box) and a small Linux server (2–4 vCPU, 2–4 GB RAM).
Versions are the latest stable releases I know of as of 2026-10; pin them, then confirm with `pip index versions <pkg>` before installing. Nothing here has been installed or verified in this repo yet.

---

## M1 — Voice loop

### 1. Wake word ("Atulya")

| Option | Package | License | CPU / RAM | Custom "Atulya" word | Notes |
|---|---|---|---|---|---|
| **openWakeWord** | `openwakeword==0.6.0` (+ `onnxruntime>=1.17`) | Apache-2.0 code; pre-trained models CC BY-NC-SA 4.0 | ~1–3 % of one core per model (80 ms frames, ONNX), ~50–80 MB RAM | Yes: train a free model with the project's synthetic-data Colab/notebook (Piper-generated samples). Your own trained model is not bound by the NC licence of the shipped models. | Windows: use the ONNX backend (`inference_framework="onnx"`); tflite is Linux-only. Has built-in Silero VAD gate and Speex noise suppression (Linux only). |
| sherpa-onnx KWS | `sherpa-onnx==1.12.x` | Apache-2.0 | ~3–5 % of a core, ~30–60 MB | Yes, **no training**: open-vocabulary keyword spotting; you list the phonetic/BPE tokens for "Atulya" in `keywords.txt` | Same package already covers TTS/ASR → one dependency for phone + PC (has Android AAR). Accuracy on unusual names is lower than a trained model; needs threshold tuning per keyword. |
| Porcupine (Picovoice) | `pvporcupine==3.0.x` | Proprietary; free tier needs an AccessKey, personal/non-commercial, online activation | Lowest (~<1 % core) | Yes, via Picovoice Console (account) | Violates the "no account / no key" spirit of GOAL.md; key revocation risk. **Reject.** |

**Recommendation:** **openWakeWord** with a custom-trained `atulya.onnx` on the PC and server; keep **sherpa-onnx KWS** as the fallback and the choice for Android (shares the sherpa-onnx AAR, no training needed). Do not use Porcupine.

### 2. Barge-in (interrupt it mid-sentence)

Pieces needed (all free):
- **VAD:** `silero-vad==5.1.2` (MIT, ONNX, ~1 ms per 30 ms chunk on CPU) — or `webrtcvad-wheels==2.0.14` (MIT, smaller, less accurate). Recommend Silero (also usable from `openwakeword`/`faster-whisper`).
- **Echo cancellation** so the assistant does not hear its own voice: on Windows, open the mic in **WASAPI communications mode** (Windows' built-in AEC) or use a headset. Software AEC: `speexdsp-ns`/`speexdsp` builds are Linux-only and fragile on Windows; `livekit` has a WebRTC APM (Apache-2.0) via `livekit==1.0.x` `AudioProcessingModule` (AEC + NS + AGC, runs on Windows). Recommend: WebRTC APM through `livekit` rtc package if a speaker is used; otherwise rely on a headset/OS AEC.
- **Audio I/O:** `sounddevice==0.5.x` (MIT, PortAudio, works on Windows/Linux) for full-duplex streams.
- **Logic:** while TTS plays, keep the mic + VAD (and wake word) running; on ≥200–300 ms of speech above threshold → stop the playback stream, cancel the pending LLM/TTS tasks (asyncio task cancel / llama.cpp request abort by closing the HTTP stream), start STT.

**Recommendation:** `sounddevice` full-duplex + `silero-vad` gate + WebRTC APM AEC (`livekit`), cancellation via asyncio. Accept "wake word required to interrupt" as the first version if AEC is not good enough on laptop speakers.

### 3. Low-latency LLM serving for `models/chat/Qwen_Qwen3.5-2B-Q4_K_M.gguf` (1.4 GB)

| Option | Package | License | Notes |
|---|---|---|---|
| **llama.cpp `llama-server`** (prebuilt binary) | GitHub release zip `llama-bXXXX-bin-win-cpu-x64.zip` / `-vulkan-x64` (Windows), `-ubuntu-x64` (Linux) | MIT | OpenAI-compatible `/v1/chat/completions` with SSE streaming, prompt cache, `--jinja` chat templates with tool calls. Newest model archs land here first — Qwen3.5 needs a **recent build** (use the latest release, not an old wheel). |
| llama-cpp-python | `llama-cpp-python==0.3.x` | MIT | In-process, but lags upstream llama.cpp by weeks–months; may not load Qwen3.5 yet. Windows wheels need a compiler or the CPU wheel index. |
| Ollama | installer | MIT | Easy, but an extra daemon and own model store; fine as an alternative. |

Suggested server flags (PC, CPU or Vulkan GPU):
```
llama-server -m models/chat/Qwen_Qwen3.5-2B-Q4_K_M.gguf --host 127.0.0.1 --port 8081 \
  -c 8192 -t <physical cores> --jinja --cache-reuse 256 -fa on -ngl 99   # -ngl only with Vulkan/CUDA build
```
Cost: ~1.8–2.5 GB RAM at 8k context; CPU-only on a modern 6–8 core ≈ 20–40 tok/s generation, first-token latency 150–400 ms for a short prompt with cached system prompt. Small server (2–4 vCPU): ~6–12 tok/s — usable but slower; keep context ≤4k. For Qwen3-family "thinking" models, disable thinking for voice (`/no_think` or `chat_template_kwargs: {"enable_thinking": false}`) — it is the biggest latency win.

**Recommendation:** prebuilt **llama.cpp `llama-server`** (latest release, Vulkan build on the PC if a GPU exists), called over HTTP streaming from FastAPI; keep the system prompt fixed so the prefix cache hits.

### 4. Streaming Piper TTS

| Option | Package | License | Notes |
|---|---|---|---|
| **Piper (new home OHF-Voice/piper1-gpl)** | `piper-tts==1.3.0` | **GPL-3.0** (since 1.3; old `rhasspy/piper` 1.2 was MIT) | `PiperVoice.load(...).synthesize(text)` yields audio chunks per sentence; ~0.05–0.2 real-time factor on CPU for `medium` voices, ~100 MB RAM per voice. Voices: `rhasspy/piper-voices` on Hugging Face (mostly MIT/CC-BY; check per voice). |
| sherpa-onnx TTS | `sherpa-onnx==1.12.x` | Apache-2.0 | Runs the same Piper/VITS voices plus Kokoro, with a generation callback for streaming; permissive licence, also on Android. |

Streaming pattern (either engine): split the LLM token stream at sentence ends (`. ! ? ।` or ~120 chars), synthesize each sentence as soon as it closes, push PCM to `sounddevice.OutputStream`. First audio ≈ first-sentence LLM time + ~100 ms synthesis — keeps the <2 s target.

**Recommendation:** **sherpa-onnx** for TTS if licence matters (Apache-2.0, same lib as KWS, Android parity); otherwise `piper-tts==1.3.0` is fine for a personal, non-distributed install (GPL only bites on redistribution). Sentence-chunk streaming either way.

### M1 STT note (already in repo)
`faster-whisper==1.1.x` (MIT) with `small`/`base.en` int8 on CPU; use its built-in Silero VAD (`vad_filter=True`). For the small server, `vosk==0.3.45` (Apache-2.0) streaming.

---

## M3 — Live world

### 5. Web search

| Option | Package | License | Cost | Notes |
|---|---|---|---|---|
| **SearXNG** (self-hosted) | Docker `searxng/searxng` (rolling tags) | AGPL-3.0 | ~150–300 MB RAM, idle CPU | Enable `json` in `settings.yml` → `search.formats: [html, json]`; query `GET /search?q=...&format=json`. Aggregates many engines, more resilient. Windows: run via Docker Desktop/WSL, or host on the Linux server. Add Valkey/Redis only if the limiter is enabled. |
| DuckDuckGo | `ddgs==9.x` (renamed from `duckduckgo-search`, MIT) | MIT | none | Zero infra; scrapes DDG/other backends → rate-limits (202 "Ratelimit") under load, can break when markup changes. |

**Recommendation:** **SearXNG on the Linux server** as primary (private, JSON API), **`ddgs`** as the zero-setup fallback when SearXNG is unreachable. Always return URLs to satisfy "cite real links".

### 6. Readable page extraction

| Option | Package | License | Notes |
|---|---|---|---|
| **trafilatura** | `trafilatura==2.0.0` | Apache-2.0 (since 1.8) | Best accuracy in benchmarks; returns main text + metadata (title, date, author); ~30–50 MB RAM, tens of ms/page. Has its own fetcher but use `httpx` for timeouts. |
| readability-lxml | `readability-lxml==0.8.x` | Apache-2.0 | Port of Arc90 readability, simple, returns cleaned HTML (still need html→text). |
| newspaper4k | `newspaper4k==0.9.x` | MIT | News-oriented, heavier deps. |

**Recommendation:** `httpx==0.28.x` fetch (timeout 10 s, real UA, size cap 2 MB) → **`trafilatura.extract(html, include_links=False, output_format="markdown")`**, fallback `readability-lxml`. Truncate to ~3–4k tokens before the 2B model summarises.

### 7. Routes / travel time

| Option | How | License | Cost |
|---|---|---|---|
| OSRM public demo `router.project-osrm.org` | HTTP `GET /route/v1/driving/{lon},{lat};{lon},{lat}?overview=false` | BSD-2 (server); data ODbL | Free, **car profile only**, fair-use, no SLA — dev/testing only. |
| **OSRM self-hosted** | Docker `ghcr.io/project-osrm/osrm-backend` + a Geofabrik region extract | BSD-2 | Preprocessing needs ~2–3× the .pbf size in RAM (a state/small country: 1–4 GB once; India full: ~16–20 GB); serving a region: 0.5–3 GB RAM. One profile per dataset (car/bike/foot). |
| Valhalla / GraphHopper | Docker | MIT / Apache-2.0 | Valhalla does multi-modal with one graph and lower RAM via tiles; GraphHopper Java, ~1–2 GB for a region. |

**Recommendation:** start with the **OSRM public demo** behind a small client (`httpx`) with a config switch; move to **self-hosted OSRM for your region extract** on the server (car profile) when the demo is too limiting. Geocoding stays on Nominatim (1 req/s policy, set a User-Agent).

---

## M2, M4–M6 — quick picks (to be expanded)
- **M2 PC control:** `pycaw==20240316` (MIT, volume), `pywinauto==0.6.9` (BSD), `pyautogui==0.9.54` (BSD, media keys/screenshot), `mss==10.x` (MIT, fast screenshots), `psutil==7.x`. Docs: `pypdf==5.x` (BSD), `python-docx==1.1.x` (MIT), `openpyxl==3.1.x` (MIT), `python-pptx==1.0.x` (MIT). File search: Windows Search index via `pywin32` ADODB, or `Everything` (free) CLI `es.exe`.
- **M4 push/reminders:** `APScheduler==3.11.x` (MIT) with `SQLAlchemyJobStore` so jobs survive restart; ntfy self-hosted (Apache-2.0/GPL dual, ~20 MB RAM) plus existing Telegram.
- **M5 device agent:** Tailscale free tier + a small authenticated FastAPI agent on the laptop; music via `yt-dlp` (Unlicense) + `mpv` (`python-mpv==1.0.x`, GPL/LGPL).
- **M6 vision:** `onnxruntime` + a small VLM via llama.cpp (`llama-mtmd-cli`/`llama-server` with `--mmproj`, e.g. SmolVLM-256M/500M or Qwen-VL small GGUF); MediaPipe (Apache-2.0) for gestures on Android.

## Open questions for planner
1. Does the PC have a GPU (decides Vulkan/CUDA llama.cpp build and Whisper size)?
2. Is GPL-3.0 (piper-tts 1.3) acceptable, or prefer Apache-2.0 sherpa-onnx everywhere?
3. Which OSRM region extract (city/state/country) should the server hold?

---

# M14–M17 (researched 2026-10-21; ✔ = checked by web search, the rest is from prior knowledge, so verify before use)

## M14 — Channels (free only)

**WhatsApp Cloud API** ✔ — Meta has billed per message (not per conversation) since July 2025. A pricing change reported to take effect **2026-10-01** starts charging service messages and utility templates sent *inside* the 24-hour window, at the utility rate. The **first 1,000 service messages per business number per month are free**. The free 72-hour "entry point" windows apply only to conversations started from click-to-WhatsApp ads or Page buttons. Setup needs:
- a Meta Business portfolio and a developer app;
- a phone number that is not registered on consumer WhatsApp;
- a public HTTPS webhook (verify token plus app-secret signature check);
- a permanent System User token;
- approved templates for any message outside the 24-hour window.

The 2026 change comes from one vendor blog (respond.io), so check Meta's rate card before relying on it.
→ **Recommendation:** keep WhatsApp optional and off by default. A personal assistant fits inside the 1,000 free messages a month, but the setup work and policy risk are high. Don't use unofficial libraries that drive WhatsApp Web (whatsapp-web.js, Baileys): they break the terms of service and can get the number banned.

**Email** ✔ — Gmail API limits, from Google's quota page:
- 15,000 quota units per user per minute (an older copy of the page says 6,000);
- 1.2 M units per project per minute;
- sending costs 100 units, reading a message costs 5.

The API needs a Google Cloud project, an OAuth consent screen, and the restricted scopes `gmail.readonly` or `gmail.modify`. While the app is in "Testing" mode, refresh tokens expire after 7 days. Publishing an app with restricted scopes requires a security assessment.

IMAP/SMTP with a Google **app password** avoids all of this: no OAuth app and no 7-day expiry. App passwords need 2-Step Verification. This route works with any email provider, and Gmail allows about 500 sent messages a day.
→ **Recommendation:** IMAP with `imap-tools==1.x` (Apache-2.0) plus SMTP with `smtplib` or `aiosmtplib`, using an app password. Every send goes through the approval queue. Add the Gmail API only if push notifications (Pub/Sub watch) are ever needed.

**Android SMS and calls** — Play restricts `SEND_SMS`, `READ_SMS`, `RECEIVE_SMS` and `CALL_LOG`. An app must be the default SMS or dialer app, or be granted a declared exception. Assistant apps rarely get one. `CALL_PHONE` (direct dialing) is a dangerous runtime permission but is not restricted by Play. The `ACTION_DIAL` and `ACTION_SENDTO` intents need no permission, because the user taps Send or Call themself. A sideloaded APK can request all of these at runtime.

✔ Sideloading is changing. From **2026-09**, certified devices in Brazil, Indonesia, Singapore and Thailand block APKs from unverified developers, and this rolls out globally through 2027. ADB installs are reportedly exempt. A free tier for hobbyists and limited distribution was announced.

On Android 13 and later, sideloaded apps also hit "restricted settings": the user must allow them in App info before SMS or accessibility permissions can be granted.
→ **Recommendation:** distribute the Atulya APK by sideload or ADB, not through Play. Register a free Android developer verification identity before the global rollout. By default, use intents with a confirmation step. Offer direct `SmsManager` and `CALL_PHONE` only behind the approval flow.

**ntfy** — `binwiederhier/ntfy` is dual-licensed Apache-2.0/GPL-2.0. It ships as a single Go binary or Docker image and uses about 20–30 MB of RAM. Server settings:
- `base-url` and `auth-file`;
- `auth-default-access: deny-all`;
- `upstream-base-url: https://ntfy.sh`, so iOS and Android builds without Firebase still get instant push.

To send, `POST /<topic>` with the header `Authorization: Bearer tk_...`. Priority 5 plays a sound and bypasses Do Not Disturb.
→ **Recommendation:** self-host ntfy on the server next to Telegram. Use access tokens, deny-all by default, and random topic names.

## M15 — Owner-consented companion installs + outbound-only control

| Platform | Mechanism | Notes |
|---|---|---|
| Windows | A per-user **Scheduled Task** that runs at logon. It needs no admin rights and has access to the user's desktop and audio. Package it as an MSI built with **WiX v5** (MS-RL) or as a free Inno Setup EXE. A winget manifest is optional: it needs a PR to `microsoft/winget-pkgs` and a public, signed installer. | Don't use a Windows **service**: services run in session 0 and can't reach the user's desktop, audio or apps. NSSM is unmaintained. |
| Linux | A **systemd --user** unit plus `loginctl enable-linger` | Use a system-wide unit only on headless servers. Set `NoNewPrivileges=yes` and `ProtectSystem=strict`. |
| macOS | A **LaunchAgent** plist in `~/Library/LaunchAgents` with `RunAtLoad` and `KeepAlive` | The user must approve microphone, accessibility and screen-recording access in the macOS privacy settings, and these can't be pre-granted. Unsigned builds are blocked by Gatekeeper. The free route is ad-hoc signing plus the user's right-click → Open. |
| Android TV | Enable wireless debugging in Developer options, run `adb pair ip:port code` (Android 11+), then `adb install` | It has no accessibility-based remote control unless the user enables it. Auto-start uses a `BOOT_COMPLETED` receiver plus a foreground service. |

**Control channel:** the companion opens an outbound WebSocket (wss://) to the server using `websockets==13.x` (BSD), with HTTP long-polling as the fallback. Open no inbound ports. Tailscale is an optional transport only.

**Security pitfalls to avoid:**
- **Pairing:** pair each device with a one-time code that yields a per-device key. Store the token in Windows DPAPI, the macOS Keychain or the Android Keystore.
- **Commands:** allow a list of typed actions, never a raw shell. Sign every command with a nonce and an expiry so it can't be replayed.
- **Transport:** pin the TLS certificate, or run over Tailscale.
- **Visibility:** show a tray icon and an "Atulya is connected" indicator, with a one-click kill switch and uninstall.
- **Privilege and audit:** run without admin rights and log every action locally.
- **Updates:** never auto-update from an unsigned URL.
- **Consent:** install silently only on the owner's own devices, and show consent at install time. A hidden or non-consensual install behaves like malware, and Defender will flag it.

→ **Recommendation:** per-user autostart on each OS (Scheduled Task, systemd --user, LaunchAgent, or an Android foreground service), plus an outbound wss channel that carries typed, signed commands gated by approval.

## M16 — Natural replies from small local models

- **Persona:** a short system prompt, under about 150 tokens, with the name and tone, and an instruction to speak like a friend with no lists or markdown in voice replies. Small models ignore long prompts.
- **Length:** cap `max_tokens` at about 120 for voice. Ask for 1–2 sentences followed by an offer to say more, and trim the output at a sentence boundary. Turn off thinking for Qwen3.x with `enable_thinking: false`.
- **Few-shot examples:** 3–4 example exchanges in the target style, including Hinglish. These do more than any instruction.
- **Hinglish:** reply in the user's language and script. Detect Devanagari vs Latin script, then run a cheap language-ID: `lingua-language-detector==2.x` (Apache-2.0) or fastText `lid.176`. If Hinglish is detected, add "reply in Hinglish (Roman script)" to the prompt. Qwen 2B handles Romanised Hindi acceptably. Speaking Devanagari needs a Hindi Piper voice (`hi_IN-*`).
- **Sampling:** temperature 0.7, top_p 0.8, `repeat_penalty` 1.05–1.1 (Qwen's recommended non-thinking settings). Temperature 0 sounds robotic.
- **Post-filter:** strip "As an AI…" phrases, emojis and markdown before TTS, and turn numbers and units into speakable words.
- **Memory:** inject 2–3 retrieved facts about the user (name, preferences) to make replies feel personal.
- **Later, optional:** a LoRA fine-tune on a few hundred curated chats with Unsloth (free on Colab), exported to GGUF.

→ **Recommendation:** a short persona, few-shot Hinglish examples, a 120-token cap and non-thinking sampling. Score these with a 30-prompt naturalness checklist before considering a fine-tune.

## M17 — Local vision (4-core CPU) and gestures

| Model | Size (Q4) | License | CPU note |
|---|---|---|---|
| **Qwen3-VL-2B-Instruct GGUF** ✔ (official, with mmproj) | ~1.5 GB LLM + ~0.8 GB mmproj | Apache-2.0 | Runs in llama.cpp `llama-server --mmproj`. About 5–15 s per image on 4 cores. Best quality at this size. |
| SmolVLM-256M / 500M ✔ | 0.2–0.5 GB | Apache-2.0 | Under 1 GB RAM and 1–3 s per image, but weaker answers. GGUF builds from ggml-org (not confirmed in this search). |
| Moondream2 (2025-04-14) ✔ | ~1.9 GB | Apache-2.0 | Good at captioning and pointing at objects. Uses its own runtime (`moondream` pip). |

One listing describes MiniCPM-V 2.6 as a 504M-parameter model. It is actually about 8B parameters, which is too heavy for this machine.

**Gestures:** the **MediaPipe Gesture Recognizer and Hand Landmarker** (`mediapipe==0.10.x`, Apache-2.0). It recognises 7 built-in gestures, can be retrained with Model Maker, and runs in real time on CPU and Android. Compare the ONNX assets in `models/gesture` against it.

→ **Recommendation:** **Qwen3-VL-2B Q4_K_M** on the existing llama.cpp server for questions like "what am I holding?". Use **SmolVLM-500M** as the fast, low-RAM fallback, and **MediaPipe** for gestures.

### Sources (M14–M17)
- [respond.io — WhatsApp pricing change 2026](https://respond.io/blog/whatsapp-pricing-change-2026.md)
- [Google — Gmail API quota](https://developers.google.com/workspace/gmail/api/reference/quota?hl=en)
- [9to5Google — Android developer verification](https://9to5google.com/2025/08/25/android-apps-developer-verification/)
- [Qwen3-VL-2B GGUF (Hugging Face)](https://huggingface.co/Qwen/Qwen3-VL-2B-Thinking-GGUF)
- [Computing — SmolVLM smallest VLMs](https://www.computing.co.uk/news/2025/ai/hugging-face-claims-world-s-smallest-vision-language-models)

---

# M18–M19 (researched 2026-10-21; ✔ = checked by web search, the rest is from prior knowledge, so verify before use)

## M18 — Files, devices, LAN and MCP

**R18-1 Recycle bin.** Use **`send2trash==1.8.3`** (BSD-3). It covers:
- **Windows:** sends to the Recycle Bin through the shell `IFileOperation`.
- **macOS:** moves to the Trash.
- **Linux:** follows the freedesktop Trash spec (`~/.local/share/Trash` with `.trashinfo` files). Removable drives and other mounts use `$topdir/.Trash-$uid`. A headless server has no desktop that shows the trash, but the files can still be restored from that folder.

Moves use `shutil.move`, which copies then deletes when crossing drives. Check free space first, and write a receipt that records the original path so the move can be undone.

**Android:**
- On Android 11+, apps can use `MediaStore.createTrashRequest` (media files only, restorable for 30 days) and `createDeleteRequest`. Each shows a system confirmation dialog, which fits the approval model.
- **Storage Access Framework (SAF) limits:** access comes only through a folder the user picks with `ACTION_OPEN_DOCUMENT_TREE`. Android 11+ won't grant the storage root, the Download folder or `Android/data`. Keep the access with `takePersistableUriPermission`. Everything goes through `DocumentFile`, which is slow on large trees. There is no trash, so `DocumentsContract.deleteDocument` deletes permanently.
- `MANAGE_EXTERNAL_STORAGE` (all-files access) is fine when sideloaded but rarely approved on Play.

→ **Recommendation:**
- **Desktop:** `send2trash` for deletes, with no permanent delete at all.
- **Android:** a SAF folder grant for everything; MediaStore trash requests for media; deleting other files means permanent loss, so it needs a stronger approval prompt.

**R18-2 LAN discovery and Wake-on-LAN.**
- **Read-only scan:** parse the OS ARP/neighbour table, with no packets sent and no extra library: `arp -a` on Windows, `ip neigh` on Linux.
- **mDNS:** **`zeroconf==0.14x`** (LGPL-2.1) to browse `_googlecast._tcp`, `_androidtvremote2._tcp`, `_adb-tls-connect._tcp` and `_workstation._tcp`.
- **Avoid `scapy` active scans:** they need Npcap on Windows and admin rights, and look like intrusion activity.
- **Wake-on-LAN:** **`wakeonlan==3.1.0`** (MIT), which sends a UDP magic packet to port 9. The target needs WoL enabled in BIOS and on the NIC, and it only works on the same broadcast domain. Across the internet, relay it through the always-on server or the phone on that LAN.

→ **Recommendation:** ARP table + `zeroconf` + `wakeonlan`; no scapy.

**R18-3 Android TV.**
- **ADB route:** pair over Wi-Fi with Android 11+ wireless debugging. `adb pair` uses a pairing code; the `_adb-tls-pairing._tcp` mDNS service advertises the pairing port.
- **Running commands:** shell out to platform-tools `adb`. The pure-Python **`adb-shell==0.4.4`** (Apache-2.0) only handles legacy RSA `adb connect` on port 5555 and cannot do TLS pairing.
- **Debugging drawbacks:** debugging may switch off after a reboot or idle, and it grants broad shell access.
- **Alternative remote protocol:** **`androidtvremote2==0.2.x`** (Apache-2.0) speaks Google's Android TV Remote v2 protocol (the one Home Assistant uses). The user enters a PIN shown on the TV once. It sends key presses, app deep links and power, needs no debugging mode, and is narrowly scoped.

→ **Recommendation:** **`androidtvremote2`** for everyday control. Use ADB pairing only for the one-time install of a TV companion APK.

**R18-4 MCP over HTTP with per-user auth ✔.**
- **Spec:** MCP spec **2025-11-25** says HTTP transports should use OAuth 2.1:
  - the server publishes RFC 9728 protected-resource metadata;
  - it returns 401 with `WWW-Authenticate` when a token is missing or invalid;
  - it must validate token audience;
  - it must check the `Origin` header to block DNS rebinding;
  - it binds to 127.0.0.1 when local.
- **stdio:** takes credentials from the environment instead.
- **Python SDK:** the official SDK (`mcp==1.2x`, MIT) supports streamable HTTP. Its FastMCP takes a `TokenVerifier` plus `AuthSettings`, so each request carries an `AccessToken`, including scopes and client id, that tools can check per user.
- A simpler, non-spec option for private use is a static bearer token per device, checked by a Starlette middleware in front of `streamable_http_app()`.
- **Unconfirmed:** one Oct 2026 blog mentions a newer revision dated **2026-07-28** that removes sessions. Confirm it at modelcontextprotocol.io.

→ **Recommendation:**
- Serve `tools/mcp/server.py` over streamable HTTP.
- Check each request's per-device token through `TokenVerifier`, mapped to an Atulya user and a scope set. Read-only tools need the `tools:read` scope; tools that change things also go through the approval queue.
- Bind it to localhost or the Tailscale address and validate `Origin`.

## M19 — Notifications, inline replies, SMS, mail

**R19-1 NotificationListenerService ✔.**
- **Access:** the user grants notification access manually in Settings. On Android 13, sideloaded apps can't be granted it until the user taps **App info → ⋮ → Allow restricted settings**. Android 15 adds a CDD rule that makes this gate mandatory for notification listener, accessibility, usage access and overlay, and still allows the per-app override. Apps installed through a session-based installer such as Play are exempt.
- **Play policy:** a notification listener is allowed only for a core feature you declare, so a sideloaded build is simpler.
- **Inline replies:** the reply action is a `Notification.Action` with a `RemoteInput`. The app fills the bundle with `RemoteInput.addResultsToIntent`, then calls `PendingIntent.send`.
- **Which apps work (prior knowledge, needs live testing):**
  - **WhatsApp** and **Telegram** expose reliable reply actions on message notifications.
  - **Instagram** DMs and **Messenger** usually have them.
  - **Snapchat** usually does **not** offer a reply action (it opens the app instead), so treat it as read-only.
- **Reliability pitfalls:**
  - A `PendingIntent` dies when the notification is dismissed or updated, so act within seconds.
  - Grouped or summary notifications have no actions.
  - Group chats look like 1:1 chats; use `MessagingStyle` and `isGroupConversation` to tell them apart.
  - OEM battery killers (Xiaomi, Oppo, Samsung) stop the listener; use `requestRebind` and ask the user to exempt the app.
  - Replies sent this way may still mark the chat as read.

**R19-2 SMS delete.** Only the **default SMS app** can write to or delete from the SMS provider (since Android 4.4). Being the default means also handling MMS, `SMS_DELIVER`, the respond-via-message service and the full UI. That is a huge scope, and on Play `READ_SMS` is restricted.
→ **Recommendation:** **SMS stays read-only (plus sending through approval). No delete.**

**R19-3 "Is this a real person" without uploading contacts.** Decide on the phone, using `ContactsContract.PhoneLookup` (needs `READ_CONTACTS`). Send the server only a boolean or label: `known_contact`, `starred`, `has_prior_thread`. Use `MessagingStyle.Person` and `isImportant` from the notification. Treat short codes or alphanumeric senders, OTP patterns and "noreply" addresses as automated. Never upload the contact list or numbers; if a stable ID is needed, hash it with a per-device salt.

**Mail: labels and trash.**
- **IMAP:**
  - Gmail exposes labels as folders. Raw `X-GM-LABELS` is available through `imaplib`; `imap-tools` gives limited access.
  - To trash a message, MOVE it to `[Gmail]/Trash`. A plain `\Deleted` flag plus expunge only removes the label under Gmail's default settings.
  - This works with an app password.
- **Gmail API:**
  - Provides `users.messages.modify` (add/remove labels) and `messages.trash`, with clean label IDs. Quota and OAuth details are in M14.
  - It needs the `gmail.modify` restricted scope, and in Testing mode the token expires after 7 days.

→ **Recommendation:** IMAP with explicit folder moves for trash and labels. Never expunge, so mail stays recoverable for 30 days.

**Auto-reply prior art and pitfalls.**
- **Prior art:** AutoResponder for WA/IG/Telegram, WhatsAuto, and Tasker AutoNotification all use the same listener + RemoteInput method.
- **Pitfalls:**
  - **Loops:** two bots replying to each other. Ignore your own sent messages, mark outgoing text, and allow at most one reply per chat per N minutes.
  - **Groups:** off by default.
  - **Spam and OTP:** never reply to short codes or unknown senders by default.
  - **Account bans:** WhatsApp and Meta flag high-volume automated replies on personal accounts.
  - **Leakage:** never include private data in replies to unknown contacts.
  - **Honesty:** replies must say they are from an assistant.

→ **Recommendation:**
- Auto-reply is opt-in per contact, 1:1 only, and limited to 1 reply per chat every 30 minutes.
- Each reply is labelled "Atulya (assistant) on behalf of …".
- Groups, unknown senders and automated senders are skipped, and every reply is logged to the audit log.
- Anything other than an away notice needs approval.

### Sources (M18–M19)
- [MCP spec 2025-11-25 — Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP 2025-11-25 changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog)
- [Descope — MCP auth spec](https://www.descope.com/blog/post/mcp-auth-spec)
- [wz-it — MCP spec 2026-07-28 (unconfirmed)](https://wz-it.com/en/knowledge/ki/mcp-model-context-protocol/)
- [9to5Google — Android 15 sideloaded app restrictions](https://9to5google.com/2024/09/12/android-15-sideloaded-apps-restrictions/)
- [Android Authority — Android 15 restricted settings](https://androidauthority.com/android-15-restricted-settings-sideloading-3481098)
- [Chrome Unboxed — Android 13 restricted setting](https://chromeunboxed.com/android-13-restricted-setting-feature-blocks-sideloaded-apps-from-notifications/)
