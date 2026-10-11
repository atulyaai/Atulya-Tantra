# Atulya TODO

This list separates working local features from missing providers and planned integrations. Conversation transcripts are stored locally; they are an archive only and are not recalled as assistant memory.

For responsibility boundaries and the intended core/plugin/data/model structure, see [ARCHITECTURE.md](ARCHITECTURE.md). For the latest operational evidence and per-device checks, see [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md).
Implementation order and capability mapping live in [INTEGRATIONS_CATALOG.md](INTEGRATIONS_CATALOG.md): **common first, medium next, rare last**. Do not begin medium/rare integrations until the common foundation has end-to-end checks and honest setup/readiness states.

## 2026-10-11 fix pass

- [x] **Security:** the Telegram bot token was written to `data/logs/pc-host.log` on every poll (httpx logs request URLs at INFO). Logs now pass through a redaction filter (bot tokens, bearer tokens, API-key query values), httpx/httpcore log at WARNING only, and existing logs are scrubbed on host start. `pc-host.log` rotates at 2 MB × 3 files.
- [ ] **Rotate the Telegram bot token in @BotFather** and put the new one in `.env`. The token currently in `.env` is the one that was exposed in the log.
- [x] **Telegram 409 conflict:** no webhook is set, so another program elsewhere was polling the same token (1,248 failures overnight, retrying every ~10 s). Polling now backs off exponentially to 60 s (300 s for a rejected token) and logs each failure kind once with the fix. Rotating the token cuts off the other poller.
- [x] **Speed:** Whisper, local TTS, and (when no cloud provider exists) the local model load in the background at startup (`ATULYA_PRELOAD=0` disables this); replies are spoken sentence by sentence while still streaming, with the next sentence synthesized during playback; TTS WAV encoding is vectorized with NumPy and generation is serialized for thread safety; `llama-server` runs with `--jinja` so the local model can call tools.
- [x] Removed the unused `tools/plugins/memory/` module and stray root log files; lint is clean; 50 tests pass.
- [ ] Hologram UI: rebuild the avatar as a live particle hologram (concept: `Jarvis_AI_webpage_layout_concept_*.jpg`) once the new hologram asset is provided.
- [x] Wake word and barge-in: with live voice on, utterances are transcribed locally and ignored unless they start with "Hey Atulya" (or come within 8 s after Atulya spoke); talking over Atulya for 300 ms stops speech and starts listening (echo-cancelled mic monitor). Toggle by saying/typing "wake word on/off" or "interrupt on/off". Needs a by-ear check in the user's browser.
- [x] PC control with approval (`tools/plugins/system/`, plugin `pc-control`): open apps (Windows Start apps incl. Store apps, macOS Applications, Linux .desktop), open http(s) URLs, search files by name in home folders, media/volume keys, screenshots to `data/screenshots/`. The model can only queue a request; the WebUI shows APPROVE/DENY (or answer "yes"/"no"), requests are single-use, expire after 3 minutes, and only run for the user they were made for. Telegram and MCP cannot run them. Live check: the model asked for approval to open Calculator and did not claim it ran.
- [x] Memory: `search_past_chats` tool searches the signed-in user's archived conversations.
- [x] Morning briefing: `ATULYA_BRIEFING_CITY` / `ATULYA_BRIEFING_TIME`; sent once a day to allowlisted Telegram users at that time and shown/spoken in the WebUI on the first visit of the day.
- [x] Live system panel: CPU, memory, network rate, disk/uptime/battery with meter bars (psutil, refreshed every 3 s) and recent tool activity.
- [x] Remote access tooling: `python -m atulya.cli remote [--enable|--disable]` checks Tailscale, runs `tailscale serve` for private HTTPS, and writes `ATULYA_PUBLIC_ORIGIN`. localhost passkeys keep working after a public origin is set, and USERS → LINK MY PHONE / ANOTHER DEVICE makes a one-time 10-minute link that adds a passkey to the same account on the new device/address.
- [ ] Install Tailscale on this PC and the phone, sign in, enable HTTPS certificates in the admin console, run `atulya remote --enable`, then link the phone and verify chat/voice from a mobile network.
- [ ] Verify sentence-pipelined speech by ear in the user's browser (automated checks cover syntax and API only).

## Open-source plugins, MCP, and skills roadmap

The project uses three distinct extension layers: feature implementations in `tools/plugins/`, an MCP server and its tool adapters in `tools/mcp/`, and reusable Jarvis workflows in `tools/skills/`. One shared tool list (`tools/plugins/toolkit.py`) feeds model tool calling, Telegram, and MCP. Items below stay unchecked until their end-to-end checks pass. Prefer permissively licensed, maintained, self-hostable projects and standards. Review each upstream license and security posture before adopting code or bundling dependencies.

- [x] Add explicit HTTPS public-origin configuration for reverse-proxy deployments while keeping the app listener loopback-only; bind passkeys to the configured RP ID/origin, allow only its Host, set secure session cookies, trust forwarded headers only from explicitly configured proxy IPs, and require a setup token before first public enrollment. Configuration and in-process API tests (passkey options on the configured HTTPS origin with the setup token) pass; the earlier ASGI hang no longer reproduces (full suite 50 passed in ~9s on 2026-10-11). Actual remote TLS deployment is not configured.
- [x] Document a same-host Caddy reverse-proxy setup, loopback-only upstream, first-admin setup token, and remote verification checklist in [REMOTE_ACCESS.md](REMOTE_ACCESS.md).
- [ ] Configure a real TLS endpoint and verify passkey enrollment/login from another device and network before describing Atulya as reachable from anywhere.
- [ ] Add lost-admin-passkey recovery and link channel identities to authenticated accounts before shared multi-user deployment; browser conversation IDs alone are not account boundaries.

### Temporary home-hosting, then permanent server

- [x] Install the Windows per-user Atulya PC-host task on the current computer; verify Task Scheduler reports Running, the listener is loopback-only at `127.0.0.1:8501`, and `/api/health` returns `ok`. Setup does not download model weights. Cross-device access is not configured yet.
- [x] One-line installers `install.ps1` / `install.sh` (2026-10-11): fetch code via git or archive, reuse Python ≥3.10 or install a private Python 3.12 with uv (no admin/root), create `.venv`, run bootstrap; `-Service`/`--service` adds a login service (Task Scheduler, systemd user unit, or LaunchAgent) and `-RemoveService`/`--remove-service` removes it. `start.bat`/`start.sh` hand off to the installer when Python is missing. Syntax-checked here; clean-machine runs on macOS and Linux are still pending.
- [ ] Finish the guided **personal-PC host** mode for Windows/macOS/Linux: one-click setup for prerequisites, a per-user start-at-login service, bounded restart policy, structured logs/health, graceful stop/uninstall, and a clear local URL. Keep app listener loopback-only; do not require a dedicated server or admin OS account for local hosting.
- [ ] Add power-aware hosting behavior: request keep-awake on AC power only, never prevent sleep on battery by default; detect sleep/resume/network changes and report when the PC is not reachable. Explain that host shutdown/sleep means service downtime.
- [ ] Support Tailscale Serve as the first temporary cross-network route for the owner's devices. Detect the installed client, verify Serve HTTPS and the tailnet URL, set the exact public origin, and report missing account/consent/device setup clearly. Tailscale requires the user to install/sign in and enable HTTPS; do not pretend those steps can be automated away. See [REMOTE_ACCESS.md](REMOTE_ACCESS.md).
- [ ] Add an optional disposable Cloudflare Quick Tunnel launcher for short tests only: start tunnel, discover and validate its random HTTPS URL, pass it as the runtime origin before Atulya starts, display the URL only in the local admin UI/terminal, stop both processes cleanly, and handle URL changes by requiring a new passkey on the new RP origin. Keep this mode marked temporary/public and require the setup-token gate; Cloudflare says Quick Tunnels have no uptime guarantee and are for testing/development.
- [ ] Add a short-lived public-access warning/status, optional access-email gate when supported, and a one-action stop/revoke control for temporary public tunnels. Test that stopping the tunnel makes the URL unreachable and leaves local Atulya data intact.
- [ ] Add service supervision and dynamic recovery for Atulya, local model runtime, reverse proxy/tunnel, and each channel: independent health checks, bounded exponential backoff, circuit breaking, no duplicate channel pollers, actionable redacted diagnostics, and graceful degraded operation when one integration fails.
- [ ] Add load/bottleneck controls for home hardware: bounded concurrent model requests, request queues/timeouts, upload/body limits, memory/disk checks, cancellation cleanup, and status reporting for CPU/GPU/RAM/storage/network limits. Verify multiple devices cannot exhaust the host or duplicate side effects.
- [ ] Verify the temporary home setup from another browser/device on home Wi-Fi and again from an unrelated mobile network; test host sleep/reboot, tunnel drop/reconnect, provider outage, bad DNS, and app restart. Record which failures recover automatically and which require user action.
- [ ] Prepare the later permanent-server migration: stable DNS/TLS hostname, persistent encrypted backups, secrets migration, database migration/restore, passkey-origin migration/re-enrollment, staged cutover, rollback, and post-cutover checks for WebUI and every enabled channel.
- [ ] Keep channel support on the same shared assistant/tool/permission path. WebUI and Telegram exist today; add other communication adapters one at a time with identity linking, private inbound tests, outbound delivery tests, retry/idempotency, rate limits, and per-channel health before marking them ready.

### Hosting choices to support

- [ ] **Personal PC only:** guided local-only setup on the user's own laptop/desktop; persist Atulya data/models on that device; support start at login, recovery, backup/restore, and clean removal.
- [ ] **Private home network:** support a designated always-on desktop/mini-PC host and private clients; offer Tailscale Serve as an easy hosted-control-plane path and Headscale/WireGuard as fully self-hosted alternatives where the user has a reachable control host; make access private with explicit ACLs and HTTPS. Do not open the router/app port by default.
- [ ] **Single server:** support a one-host deployment with Caddy/another TLS proxy, durable data volume, secrets outside images, system service restart, health checks, backups, and documented upgrade/rollback.
- [ ] **Private server/device network:** allow one elected Atulya host behind a private overlay while clients/devices use the same endpoint; keep only one reminder/channel poller active.
- [ ] **Cluster / multiple app replicas:** block this mode until SQLite-backed state, sessions, rate limits, auth challenges, and plugin settings are shared; move polling/reminders to a lease/queue worker; externalize models/files as appropriate; add readiness/liveness/shutdown and zero-downtime migrations; then test failover, duplicate jobs, rolling upgrades, backup restore, and rollback. Kubernetes/Compose alone do not make the current local state cluster-safe.
- [ ] **Temporary public demo:** support disposable tunnels separately from private hosting; require an explicit start, setup token, URL rotation/passkey warning, short-lived session, and stop control; never enable a public tunnel automatically on boot.
- [ ] Add a provider-neutral setup chooser: detect user-owned PC/servers and already-configured paid providers first; then offer free/open-source software and free hosted services where suitable. Distinguish free software, free hosted control planes/tunnels, and free compute. Reuse a user's existing server/domain/VPN/cloud plan; never imply that open-source tunnel software supplies a free public server, or that an ephemeral free tier is always-on. Map prerequisites, one-time account/key/consent actions, data location, disk/RAM/CPU/network footprint, portability, recovery path, and recurring cost in the UI.

### Existing plugin categories

- [x] `tools/plugins/brain/` — local and cloud model providers.
- [x] `tools/plugins/communications/channels/` — WebUI and Telegram.
- [x] `tools/plugins/voice/` — local speech recognition and synthesis.
- [x] `tools/plugins/personal/` and `memory/` — explicitly saved personal memory.
- [x] `tools/plugins/productivity/` — local calendar and reminders.
- [x] `tools/plugins/information/` — Open-Meteo weather and BBC RSS headlines.
- [x] `tools/plugins/utilities/` — calculator and clock.
- [ ] Phase 1 — common: add optional open-source integration plugins, grouped by capability and independently enableable: scoped files/documents, email (IMAP/SMTP), calendars/tasks (CalDAV/iCalendar), notes/knowledge, and source control. Prefer local protocols or self-hosted services; do not bake service credentials into plugin manifests.
- [ ] Phase 2 — medium: add smart home, messaging, cloud files/office, automation/webhooks, media, and contacts after Phase 1 is secure and verified.
- [ ] Phase 3 — rare: add industrial/vehicle/energy systems, robotics, enterprise systems, financial actions, or specialty equipment only for a specific user need and after domain safety review.

### MCP server (`tools/mcp/`)

- [x] Implement an optional MCP server that exposes only explicitly registered Atulya tools (weather, news_headlines, get_time, calculate; plugins disabled in the WebUI are hidden; every skill is published as an MCP prompt); keep MCP SDK/runtime dependencies optional and pinned so the base assistant works without MCP enabled.
- [ ] Initial read-only tools: weather/news, calendar lookup, scoped file search/read, and project/code inspection. Add write/action tools only after authentication, per-tool authorization, input validation, audit records, and confirmation for destructive or externally visible actions.
- [ ] Phase 1 — common MCP adapters: local files (root allowlist), Git, CalDAV, IMAP/SMTP, and read-only information/calendar tools.
- [ ] Phase 2 — medium MCP adapters: Home Assistant REST/WebSocket, MQTT broker with topic allowlists, contacts/CardDAV, cloud files, and named workflow/webhook triggers.
- [ ] Phase 3 — rare adapters: industrial, vehicle, energy, robotics, finance, enterprise, or specialty equipment only after the catalog's domain-specific safeguards are defined. Never expose arbitrary shell execution, unrestricted filesystem access, or generic publish-to-any-topic as default tools.
- [ ] Provide a local-only default bind, explicit opt-in network exposure, capability/health reporting, timeouts, bounded results, safe errors, and graceful startup when an optional service is absent.
- [x] Verify each tool through the MCP protocol from discovery through invocation and result handling (4 MCP tests incl. stdio subprocess, malformed input, disabled plugins) using local fakes or disposable test services; include denial, malformed-input, timeout, and unavailable-service cases.

### Skills (`tools/skills/`)

- [ ] Establish one focused, documented skill per user workflow, with a `SKILL.md`, trigger examples, required tools, expected output, fallback behavior, and permission notes. Skills provide instructions; they must not claim to create capabilities when the corresponding plugin/MCP tool is absent.
- [ ] Phase 1 — common skills: daily briefing (weather/calendar/news), email triage and draft-only replies, meeting preparation/follow-up, scoped document Q&A, coding/review workflow, and notes/knowledge capture.
- [ ] Phase 2 — medium skills: smart-home routines, messaging summaries, office-file workflows, contact-aware scheduling, and automation troubleshooting.
- [ ] Phase 3 — rare skills: specialized workflows only when a concrete integration and safety policy exist.
- [x] Add a loader/catalog that lists available skills and makes them discoverable to Atulya without copying instructions into core prompts: `toolkit.list_skills()` reads `tools/skills/*/SKILL.md`; the model sees only names/descriptions and loads a body on demand through the `use_skill` tool; MCP publishes them as prompts. Referenced-tool validation is still open. Skills must not silently enable plugins or grant permissions.
- [ ] Check skill activation, tool selection, incomplete requests, tool failures, and refusal/confirmation behavior end to end; keep private data out of logs and skill files.

### End-to-end setup and no-manual-intervention target

- [ ] Make bootstrap install/configure optional local components and compatible open-source dependencies idempotently, with pinned versions/hashes where available, health checks, restart recovery, and a clear offline/degraded mode. A missing optional integration must never prevent core chat from starting.
- [ ] Phase 1 common capabilities: for integrations that need no account, secret, physical device, or external consent, target zero-touch first-run setup and verify it from a clean environment through a working user-visible action.
- [ ] Phase 2/3 capabilities: add setup automation only after common setup, health, and catalog behavior is stable; keep consent, credential, hardware, and domain safety requirements explicit.
- [ ] For email/calendar/cloud accounts, OAuth consent, passkey enrollment, browser microphone/camera prompts, or physical smart-home hardware, automate every technical step possible but clearly report the unavoidable user action. Do not claim these can work with no human intervention or bypass provider consent/security prompts.
- [ ] Add an integration catalog with capability, upstream project/protocol, license, local/cloud data flow, required secrets/devices, setup state, health, and disable/remove controls. Never show credential values.
- [ ] Keep integrations disabled until their permission boundary and ownership model are enforced. Current plugin manifest permission labels are descriptive and the fixed registry is not a sandbox; complete the pending tool-call security design before exposing private-account or system-control tools.

## Added local assistant features

- Explicit personal memories: say `remember that ...`, `what do you remember about ...`, or `forget ...`. Saved facts are local to this browser conversation and are added to future chat context when relevant.
- Local calendar: say `add meeting: Title | 2026-10-20 15:00` or `add meeting: Title | tomorrow at 3pm`; say `my meetings` to list upcoming events. The WebUI announces the 15-minute reminder while the page is open and visible.
- Quick answers: ask `weather in Bengaluru`, `what time is it`, `calculate 24 * 7`, or `latest headlines`. Weather uses Open-Meteo; headlines come from BBC News RSS, so these two need internet access.
- Calendar events and personal memories are stored in separate SQLite files under `data/`.
- `atulya/` is the flat core package; plugins and purpose-based tool categories live under root `tools/plugins/`; setup remains in `tools/bootstrap.py`; runtime data remains under root `data/`.
- [x] Verify the memory, calendar, calculator, clock, weather, headlines, and cloud chat replies through a short-lived localhost API instance; remove the test memory and event afterward.

## WebUI and core

- [x] Open directly into the humanoid scene and retain the original circle-burst assembly animation.
- [x] Connect `/api/chat` to the configured brain through the WebUI channel adapter.
- [x] Send WebUI listening, thinking, speaking, and idle states to the renderer.
- [x] Wait for the renderer's ready event before showing and speaking the first Atulya greeting.
- [x] Show only channel names (Text, Voice, Vision, Gesture); indicate readiness by color without visible setup/off suffixes.
- [x] Give channel indicators distinct colors for Ready (green), Setup (amber), Live (cyan), and Off (red), with status available to assistive technology.
- [x] Keep a compact right-side session stack, a separate 16:9 camera preview, and a scene that auto-fits the remaining viewport.
- [x] Add a compact left-side system panel for service, active model, voice, vision, gesture, Telegram, reminders, and current issues.
- [x] Archive and restore chat messages in local SQLite under `data/conversations.sqlite3`; keep transcript data separate from prompt memory.
- [x] Add browser-local conversation controls to start, browse/open, export JSON, and confirm deletion of an archived conversation. Its local index does not authenticate users.
- [x] Show live status through `/api/status` without exposing `.env` values, credentials, or provider error details.
- [x] Add typed and spoken commands to show/hide camera, chat, and status panels; focus camera/status; and restore the layout.
- [ ] Verify layout commands from a live microphone session. Create new panels only after specifying which system data they should display.
- [x] Add browser-local controls to start, browse, export, and delete archived conversations; the index contains only conversation IDs saved in that browser. The browser conversation ID is not a user account or access-control boundary.
- [x] Verify the actual `start.bat` recovery-environment path and automatic model fallback with a live local Qwen response.
- [x] Auto-select among configured cloud providers, comma-separated credential keys, and model preferences; NVIDIA is tried first after a successful response in 3.77 seconds. Local Qwen remains the final offline fallback; an explicit provider selection restricts attempts to that provider.
- [x] Reuse pooled HTTP connections for configured model providers; cap cloud attempts at a 30-second overall budget and 20 seconds per attempt; hedge no more than two provider candidates, with a configurable delay and HTTP 402/429 cooldown. Set `ATULYA_PROVIDER_HEDGE_SECONDS=0` to disable overlapping requests.
- [x] Stream OpenAI-compatible and Ollama output through the reasoning/channel layer and `/api/chat` SSE response to the WebUI; retain JSON responses for command results and non-stream clients.
- [x] Verify the `/api/chat` route hands typed and image-grounded messages to the WebUI channel adapter with a no-network fake provider.
- [x] Keep automated tests grouped by core, provider, communications, and E2E categories; use one composed chat/archive E2E test rather than duplicating each route into a large test set.
- [x] Add a deterministic in-process end-to-end API test that sends a user message, receives an assistant reply, archives/restores the conversation, and checks separation between conversation IDs. Current full suite including auth, account invitations, and owner-isolation checks: 40 passed.
- [x] Add opt-in provider diagnostics for configured cloud providers and local Qwen; paid OpenRouter probing requires `--include-paid`, local startup/reply timing requires `--include-local`.
- [x] Verify live cloud chat with synthetic prompts on 2026-10-09. All four OpenRouter keys answered using a current free model; both NVIDIA keys answered using `nvidia/nemotron-3-super-120b-a12b`; one Gemini key answered using `gemini-2.5-flash`. The automatic app provider chain selected NVIDIA and returned a response in 3.77 seconds. The old comma-separated values were incorrectly being treated as single keys; server parsing is fixed. NVIDIA's previous Llama model is retired, and three Gemini keys did not have access to the tested Gemini model.
- [x] Keep core app modules flat under `atulya/`; group plugins under `tools/plugins/{brain,channels,voice,productivity,personal,information,utilities,entertainment}/`; keep runtime databases under project-root `data/`.
- [x] Implement single-admin WebAuthn passkey enrollment/login, one-time challenges, hashed server-side sessions, and protected API middleware. Open `http://localhost:8501` for the passkey origin; IP origins are rejected. The user must complete first-passkey enrollment in the browser with an authenticator. Focused auth tests pass.
- [x] Scope conversation archives, personal memories, and calendar entries by authenticated account plus conversation/channel ID. Existing browser rows remain under Admin; legacy Telegram records migrate to their sender ID. Regression tests verify cross-account isolation and migration.
- [x] Add admin-controlled expiring invitations, additional-user passkey enrollment, account disabling, and backup-passkey revocation. Revocation preserves at least one credential on active accounts and keeps disabled-account data intact.
- [ ] Add lost-admin-passkey recovery and Telegram-to-local-account linking before supporting shared identities or remote access. Do not store face or voice biometric templates; use Windows Hello/phone biometrics only to unlock a passkey.
- [ ] If users opt in, allow the local camera to recognize an enrolled profile or report an unknown person and prompt them to sign in/enroll; do not infer a real-world identity or grant access from face recognition alone.
- [ ] After login, let each user explicitly opt into a private conversation profile. Do not profile or train on other users by default; include inspect, export, and delete controls.

## Voice

- [x] Add local Whisper STT with browser-native speech output and a continuous voice session: request microphone permission automatically after the greeting, auto-send each utterance after a pause, pause capture during the reply, and resume listening afterward. Keep an explicit stop action; the browser still requires the user to grant microphone permission.
- [x] Route recognized speech through the same `/api/chat` path as typed input; verify a deterministic command through that path. STT errors leave typed chat available, and the recognized utterance is shown as the user turn so it can be corrected.
- [x] Measure microphone input for the waveform. Browser speech output has no exposed sample stream, so its waveform and golden face energy are animated.
- [x] Select browser male voices by Hindi/English reply language when matching voices are available; report speech playback errors instead of silently ignoring them.
- [x] Add first-run dependency/model preparation to `start.bat` and `start.sh`; speech-recognition weights are placed under `models/voice/stt/`.
- [x] Install first-run core/speech-recognition packages and download Whisper weights under `models/` on Windows.
- [x] Default STT to language auto-detection instead of forcing English when the WebUI does not send a language setting.
- [x] Fix the PyAV 19 incompatibility by pinning `av>=11,<19` and making startup repair an incompatible install; Whisper transcription was verified locally and through the STT API.
- [ ] Verify live microphone/STT on the user's regular browser. The current in-app browser reports microphone permission denied; no new permission was accepted. Camera permission is already available there. Whisper sample/API tests do not substitute for a live utterance.
- [x] Compare multilingual TTS candidates. Supertonic 3 int8 through sherpa-onnx is an audition candidate: one roughly 145 MB model bundle for 31 languages and 10 speakers. Its model weights use OpenRAIL-M terms; review those before redistribution.
- [x] Integrate local Supertonic 3 int8 TTS through sherpa-onnx, with pinned model-file hashes, automatic Hindi/English selection, first-run preparation under `models/`, an API endpoint, and browser playback with browser-native fallback. English and Hindi synthesis and the actual WAV API response were verified locally.
- [ ] Listen to the English and Hindi samples for all 10 speakers in `models/voice/tts/auditions/index.html` and choose a male speaker ID that works in both languages. The current default speaker ID has not been confirmed as male; do not label it as a male voice until auditioned.
- [ ] Keep the downloaded Whisper Base for multilingual STT; no separate Hindi STT model is currently needed. Confirm Hindi and mixed Hindi/English recognition with real microphone recordings.
- [ ] Choose, create, or license an original Atulya voice. Browser voices vary by operating system and browser and are not a custom Atulya voice.
- [ ] Add selectable voice profiles (Hindi, English, and code-switching) with tuned speaker, pitch, rate, and prosody; add configurable wake phrases and spoken command vocabulary. Keep voiceprint or phrase matching as an optional convenience signal, never as the account security boundary.
- [ ] Confirm the selected voice model's redistribution terms before public release.
- [ ] Let users choose available computer/phone microphone and output devices where the browser exposes them.

## Camera and gestures

- [x] Offer a separate 16:9 local camera preview. The page attempts camera startup on each visit and reports browser permission/device failures with a visible retry control.
- [x] Add local automatic hand-pose recognition using MediaPipe Tasks Vision, with GPU then CPU fallback, the recognizer model in `models/gesture/` and browser runtime in `models/runtime/mediapipe/`, with no video upload.
- [x] Show the current recognized gesture and confidence; add stable common gesture commands (open palm stops voice, thumbs up/down send Yes/No) with confidence, hold, and release gating.
- [x] Have `start.bat` and `start.sh` prepare missing gesture runtime/model assets; setup is optional when the network is unavailable and retries on next launch.
- [x] Keep both the MediaPipe gesture model and its browser runtime under project-root `models/` (`vision/` and `runtime/mediapipe/`); serve the runtime from the local API.
- [ ] Verify the user's 1080p camera and face/hands framing in the regular browser. Fixed the missing `.camera-feed` class and grid alignment that collapsed the playing video to 0px height; the refreshed in-app preview now displays the camera image at 1280×720. The UI lists/selects cameras when more than one is browser-visible and reports the negotiated resolution.
- [ ] Verify the mapped commands with live user gestures and tune camera framing/recognition threshold. Add more commands only with explicit mappings; verify the exact gesture model's redistribution terms before public packaging.

## Setup and reliability

- [x] Migrate the legacy data directory setting to the project-local `data/` folder without changing other `.env` settings.
- [x] Keep downloaded model and speech weights in project-root `models/` subfolders (`chat`, `stt`, `tts`, and runtime).
- [x] Make startup create or repair the local Python environment, install missing project/voice packages, prepare local speech models, and launch the service.
- [x] Consolidate Windows/Linux startup onto one project-local `.venv`; repair Python/pip in place and let bootstrap install missing app packages.
- [x] Verify Windows first-run package/model installation and startup on this machine; the project-local server runs on `127.0.0.1:8501`.
- [ ] Verify clean Linux installs and the first-run download/recovery path (now via `install.sh`).
- [x] Detect hardware during setup (`tools/hardware.py`): OS, CPU arch, RAM, NVIDIA/AMD/Apple GPU. The llama.cpp runtime matches the platform (Windows x64/ARM64, macOS Metal x64/ARM64, Linux x64/ARM64, Vulkan build when a discrete GPU is found; macOS previously downloaded the Ubuntu build); GPU builds offload all layers (`ATULYA_GPU_LAYERS` overrides); thread count scales with CPUs; machines under 6 GB RAM skip the offline model in auto mode.
- [x] Remove the duplicate incomplete Python environment; keep the verified speech stack in the canonical `.venv`.
- [x] Verify local chat and STT through `/api/chat` and `/api/voice/transcribe` with cloud providers disabled in the test process; local Qwen and Whisper both returned successful responses.
- [ ] Check live voice on the user's regular browser/device (microphone grant, transcription, and speech playback); see the Voice section above.
- [ ] Complete responsive layout review at phone, narrow desktop, standard desktop, and TV dimensions.
- [x] Make the WebUI installable as an app (PWA): manifest, icons, service worker that caches only the page shell and never `/api/`. Phones can only install it once Atulya is reachable over HTTPS (see remote access).

## Other channels

- [x] Confirm the Telegram bot token passes a read-only Telegram `getMe` check; no credentials or bot identity are written to project notes.
- [x] Add an allowlisted Telegram private-chat adapter for messages, `/status`, `/reminders`, and `/remind`; record Telegram chat turns locally per Telegram user.
- [x] Add SQLite-backed reminders with Telegram delivery, without replaying queued chat messages after app restart.
- [ ] Verify a real inbound Telegram message from an allowlisted user and the resulting bot reply/reminder delivery. The `getMe` check passed; no message was sent during this check.
- [x] Include the MCP server under `tools/mcp/`; it exposes public tools only (no memory, calendar, history, files, or shell).
- [ ] Add safe Telegram voice commands for system status and layout controls, and decide how to provide a hologram preview in Telegram.

## Architecture and verification follow-up

- [x] Document the core versus plugin boundary, communications channel placement, data/model layout, provider privacy, and test strategy in [ARCHITECTURE.md](ARCHITECTURE.md).
- [x] Add an explicit built-in command registry with category manifests; WebUI chat and allowlisted Telegram messages now share memory, calendar, information, clock, and calculator dispatch. Reserved Telegram slash commands remain channel-specific. This is deterministic Python dispatch: manifests are not a sandbox, auto-discovery mechanism, or LLM tool-calling interface.
- [x] Add same-origin local API controls to enable/disable fixed built-in command plugins and persist selections in `data/plugin_settings.json`; the WebUI and Telegram share the enabled registry.
- [x] Add model-driven tool calling (2026-10-11) for the existing safe tools: weather, news, time, calculator, the signed-in user's own memory and calendar, and skills. Up to 4 rounds, concurrent calls, 20 s per tool, 4 KB results, invalid input returned to the model instead of raised; disabled plugins remove their tools; providers that reject `tools` fall back to plain chat automatically. Live check: NVIDIA Nemotron called `get_weather` + `calculate` in parallel and answered in 6.2 s. The regex fast path still answers exact commands without any model call.
- [ ] Before adding system-control, file, email, or other private-account tools: per-tool permissions, confirmation for side effects, and an audit log. Plugin manifests are not a sandbox.
- [x] Add authenticated additional-user provisioning with passkeys; `user`/`assistant` roles still identify message speakers, while account IDs scope stored private data.
- [x] Enforce conversation archive read/write/delete ownership against authenticated user IDs. Browser archive lists remain local convenience controls; archive API access cannot cross account boundaries.
- [ ] Keep real API probes opt-in; record provider, model, success/failure class, and elapsed time without recording keys or prompt content. Do not present one-shot timings as a speed ranking.

## Latest verification pass (2026-10-09)

- [x] Full automated suite: 40 passed in 5.80s. This includes the in-process FastAPI chat/archive E2E flow, passkey/API account-management checks, account ownership, and legacy-data migration; it makes no paid API calls.
- [x] WebUI JavaScript syntax: `node --check webui/assistant.js` and `node --check webui/renderer.js` both passed.
- [x] Confirmed what can be verified without device interaction: the API route flow and WebUI syntax are covered by automated checks; prior opt-in provider probes and their variable results are recorded in [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md).
- [ ] Live service check: `127.0.0.1:8501` was not listening at this verification pass, so `/api/health`, `/api/status`, and real browser chat must be checked after starting the service.
- [ ] Verify live browser microphone/STT and playback, camera/gesture behavior, and allowlisted Telegram inbound/reminder delivery. See the Voice, Camera and gestures, and Other channels sections for the specific steps.
- [ ] Keep face framing, exact gesture commands, voice quality, responsive layouts, and visual greeting/speech animation as target-device/browser checks; automated syntax/API tests cannot validate these.

## Security audit follow-up

- [x] Fix Docker package contents and unsafe defaults: include `tools/`, make `python-multipart` a core dependency.
- [x] Rework the Docker image (2026-10-11): installs the pinned lock, runs as a non-root user, keeps `data/` and `models/` on volumes, runs bootstrap then serve, has a health check, and supports x86-64/ARM64. Inside a container only, `ATULYA_CONTAINER=1` allows binding `0.0.0.0` so the published port works; publish it to the host loopback (`-p 127.0.0.1:8501:8501`). The previous image bound container loopback and was unreachable. The image has not yet been built or run here (no Docker on this PC).
- [x] Reject non-loopback `ATULYA_HOST` values and validate HTTP Host headers against loopback names. These restrictions complement authentication but do not make this a remote-access service.
- [x] Remove the shared `local` calendar lookup default from `/api/status`; calendar summaries are omitted unless the caller supplies its browser conversation ID.
- [x] Pass saved memory as explicitly labeled untrusted user context instead of trusted system instructions.
- [x] Make SQLite reminder claims atomic with a two-minute lease, retry backoff, and terminal failure after five attempts; isolate errors per reminder so one bad delivery does not block the rest.
- [x] Keep Telegram polling and delivery loops alive after unexpected exceptions, logging only exception types; match commands exactly so `/startx` and `/remindme` are not treated as commands.
- [x] Treat the local vision projector as optional when starting text-only Qwen; pass `--mmproj` only when the file exists.
- [x] Fix duplicate imports reported by Ruff.
- [x] Verify the pinned MediaPipe npm tarball using the registry SHA-512 SRI for the fixed version; verify extracted browser assets and the gesture model against SHA-256 digests. Reject mismatches before accepting files.
- [x] Verify the already-installed MediaPipe runtime files and gesture model against the pinned digests without downloading anything.
- [x] Harden llama.cpp tar extraction with the Python `data` filter or a strict fallback that rejects links and special files; add a path-traversal regression test.
- [x] Remove `.env` assignments for 26 settings not referenced by the current Python implementation, preserving active provider keys/models and Telegram configuration without printing values. Confirm `.env` and all SQLite databases are ignored by Git.
- [ ] Rotate credentials that may have been exposed in the earlier diagnostic output via their provider dashboards, then replace them locally. This cannot be performed safely by editing the current keys in place.
- [x] Add a per-client-IP chat limit (20 requests/minute), a 3 MiB chat-body cap, and same-origin enforcement for state-changing API requests; add automated regression checks.
- [x] Add a provider-failure redaction regression test that injects a fake secret and checks the chat response, status response, and captured logs.
- [x] Update the project-local pip seed during bootstrap when it is older than 26.2; pip-audit found the initial pip 25.0.1 vulnerable, then passed after upgrading to pip 26.2.1.
- [x] Pin runtime dependencies in `requirements.lock.txt` and development/test dependencies separately in `requirements-dev.lock.txt`; Windows startup installs the runtime lock when packages are missing or incompatible.
- [x] Run `pip-audit` against the locked runtime dependencies: no known vulnerabilities were reported by the current PyPI advisory feed. Re-run periodically because this result ages as advisories change.
- [ ] Create a clean source archive that explicitly excludes `.env`, `data/`, `.venv/`, and `models/` before sharing a new project snapshot.
- [ ] Add and test lost-admin-passkey recovery and cross-channel account linking before any remote/shared deployment. Keep loopback-only; browser conversation IDs remain non-identities.
- [ ] Build and run the Docker image in a safe local-only configuration; Docker was not available/used in this patch verification.
- [ ] Perform live Telegram inbound/reminder testing with only one polling instance; the earlier polling conflict remains unresolved until that check.

Latest full suite: 40 passed in 5.80s, including passkey/account management, authenticated ownership, and legacy data migration checks. Ruff, Python compilation, WebUI JavaScript syntax, `pip check`, and `pip-audit -r requirements.lock.txt` pass; the audit found no known vulnerabilities. (Tests must run outside the restricted Windows worker context because its asyncio loop stalls.) Local Supertonic generated English and Hindi audio, and `/api/voice/synthesize` returned a valid WAV response. The in-app browser camera reached 1280×720 and gesture scanning, while microphone access was denied by that browser. Browser playback, live microphone utterance/STT, physical camera framing, Telegram delivery, clean Linux installation, Docker build, passkey ceremonies on the user's authenticators, lost-admin-passkey recovery, Telegram-to-local-account linking, artwork licensing, and voice gender audition remain open.

## Ownership and release

- [ ] Confirm the source, author, and redistribution license for the humanoid/background art and adapted renderer; update `webui/ATTRIBUTION.txt` with verified credits and terms.
- [ ] Review branding, package metadata, documentation, and screenshots before release.
