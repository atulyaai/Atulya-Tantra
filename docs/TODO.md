# Atulya — working list

One list, in order. Each item: **status** · what · how it is verified. Work top to bottom; update this file in the
same commit as the fix. History of finished work: `git log` and `docs/archive/`.

Status: ✅ done (verified for real) · 🔧 in progress · ⬜ to do · ⛔ blocked on the owner (reason given)

## H. Capability platform — THE MAIN TRACK (owner, 2026-10-13: less APK polish, more real abilities)

Build every ability **once on the server**; web, app, Telegram and MCP all use it. Full map with status:
`docs/CAPABILITIES.md`. Rule: no channel-specific copies, nothing "can't do" without saying what's missing and how
to enable it. In this order (each step unlocks the next):

| # | Status | What | Done when |
|---|---|---|---|
| H1 | 🔧 | **Forecast + location:** `get_weather(place?, when=now/next_hours/today/tomorrow/week)` with rain %, wind, UV, sunrise; `where_am_i`; device location by consent (web/app geolocation, Telegram 📍 button), stored with time stamp (stale ignored), home city fallback, asks once then re-answers automatically | ✅ real model, local: "rain tomorrow where I am" asks → location → "0 % rain"; "where am I" → Connaught Place; tests. ⏳ owner: phone + Telegram |
| H2 | ⬜ | **Capability catalogue + honest status:** one registry the AI reads ("what can you do here / what's missing"), status per tool (available / needs location / needs connection / needs approval / unsupported) with the next step; MCP serves the same registry (remove its duplicate tools); ask "short or detailed?" when unclear | "What can you do on Telegram?" gives a true list; MCP weather = new forecast |
| H3 | ⬜ | **Audit log:** every tool run recorded (user, channel, tool, args summary, result, time); viewable in ⋮ → ACTIVITY | Entry for each run; secrets never stored |
| H4 | ⬜ | **Web + maps:** web search with sources, read a page, places near me, route + travel time (OpenStreetMap/OSRM, free) | "Pharmacies near me", "how long to the airport", "search X" work on all channels |
| H5 | ⬜ | **Device registry + server ops:** list devices (server, laptop, phone) with status and granted abilities; server logs explained (approved paths, read-only), service restart with approval | "Check the server logs and explain the error" |
| H6 | ⬜ | **Files:** read/summarize PDF, DOCX, XLSX, CSV, code; upload in chat on all channels; **laptop agent** (outbound connection, approved folders, read-only first); phone files via Android picker | From Telegram: "find my latest budget sheet on my laptop and summarize it" |
| H7 | ⬜ | **Safe file edits + documents:** preview diff, save as new copy, approval, undo; create Word/Excel/PDF/PowerPoint | Edit shows diff, original kept |
| H8 | ⬜ | **Routines + watchers:** recurring tasks, rain/disk/site-down alerts, multi-step jobs that survive restarts | "Every weekday 8am: weather + calendar + server health on Telegram" |
| H9 | ⛔/⬜ | **Accounts:** Gmail + Google Calendar (needs D1 OAuth), GitHub (token) — read/draft free, send/change only with approval | "Summarize today's important emails and draft replies" |

Later (after H): browser actions on websites, outside MCP servers as tools, project memory, smart home (Home
Assistant), learning from outcomes. Not before H1–H8 work for real.

## A. Broken basics reported from real use (fix first)

| # | Status | Problem → fix | Verified by |
|---|---|---|---|
| A1 | 🔧 | Typed messages get no spoken reply → every reply spoken by default; 🔊/🔇 button; say "mute"/"unmute" | Built; needs your by-ear check |
| A2 | 🔧 | App/Mini App keeps demanding "Hey Atulya" → wake word now **off by default** (say "wake word on" for always-on) | Built; needs your by-ear check |
| A3 | 🔧 | Microphone permission asked repeatedly → one mic stream per session; the interrupt monitor reuses it (it used to open a second mic = second prompt); Telegram Mini App starts the mic on tap | Built; needs check in Telegram |
| A4 | ✅ | Status panel/tools for non-admins → hidden in UI **and** `/api/status` refuses non-admins (403) | Server test + UI |
| A5 | 🔧 | Overlap on phone/small windows → header on one line + account menu (⋮); phone = hologram top, chat bottom sheet; camera box only when camera is on | Screenshots desktop + 375 px phone ✅; Mini App/APK on a real phone pending |
| A6 | 🔧 | Hologram on phone/Mini App → live 3D kept when it runs; still hologram artwork when WebGL is missing or the scene never starts | Desktop + 375 px phone ✅; real phone pending |
| A7 | ✅ | "Update/reload page" prompt → an old cached page now reloads itself once; expired sessions show sign-in instead of an error | Code + UI |
| A8 | ✅ | Password sign-in with `atulya` → works on the public site in a real browser (the failed attempt was a mistyped password) | Public site, real browser |
| A9 | ✅ | Google-style sign-in: Continue with passkey → or username/email → Send approval to my devices / code / Use password; invitation + create account as links | Public site |
| A10 | ✅ | "Say code" removed; Resend added (30 s cooldown) | Public site |
| A11 | ✅ | Add passkey: account menu (⋮ → ADD PASSKEY) + offered after password/code sign-in | Public site |
| A12 | ✅ | Sign-up with an existing email jumps to sign-in for that account | UI flow |
| A13 | ✅ | App icon = the Atulya hologram face (web, PWA, Android launcher + round icon) | APK 0.2.1 |
| A14 | ✅ | APK download: https://atulya.atulvij.com/download (always the newest signed APK) + README | Public URL |
| A17 | 🔧 | APK: R8 code + resource shrinking, en/hi only, adaptive launcher icon (fits round/squircle/any mask, sharper head crop, webp); every android/ change on main auto-publishes the latest release so the in-app updater offers it | CI build size + phone install pending |
| A18 | 🔧 | Voice fixes: pause keeps the mic granted (muted, released after 10 idle min) so Telegram does not ask again; reply sentences are synthesized one at a time so speech starts with the first sentence instead of after typing; gesture model now installed on the server (was red/yellow) | Owner check in Telegram/APK |
| A15 | ✅ | Camera turned itself on at load → on demand only (button / "turn on camera"), remembered per device | Public site |
| A16 | ✅ | Greeting shown twice after reload → one greeting; "Welcome back" by voice | Public site |

## B. Server-first architecture (owner's server, always on)

| # | Status | What | Notes |
|---|---|---|---|
| B1 | ✅ | Atulya runs on the atulvij.com server (systemd `atulya.service`, ~60-340 MB RAM) and atulya.atulvij.com is served from it through the Cloudflare tunnel; old version stopped (kept as a backup folder); laptop host disabled | Server self-test 10/12 → 12/12 after clips fix |
| B2 | ⬜ | Laptop/desktop = **Atulya agents** that connect out to the server: PC control, local Whisper/TTS/LLM when available | Replaces the tunnel as the main path; tunnel kept for laptop-only setups |
| B3 | ⬜ | Server is the source of truth; clients cache locally and fetch only changes (delta sync); Telegram reads from server | — |
| B4 | ✅ | Encrypted daily backups (AES-256-GCM, keep 14) + off-site copy to the server; `atulya.cli backup`, `--restore`, `--show-key` | Real backup created, copied to server, decrypted and checked |
| B5 | 🔧 | Server voice = open source, CPU-only: **Vosk** recognition (~2.7 s) + **Piper** voices (~1.9 s/sentence), male + female, English + Hindi; loads on demand, unloads when idle. Whisper was 10-19 s on this server; Gemini is free-tier cloud (kept off) | Server benchmark; by-ear check pending |

| B6 | ✅ | Workflow: laptop = development → push to GitHub → clean-machine tests → server deploys itself (server-side health check + automatic rollback); deploy key can only run the deploy script | First automatic deploy 3c39eea, server self-test 12/12 |

## C. Same Atulya on every channel

| # | Status | What |
|---|---|---|
| C1 | ✅ | One account across web, app and Telegram (owner's Telegram = main account), live sync ~10-13 ms |
| C2 | ✅ | Telegram voice note → reply also as a voice note (local voice → OGG/Opus, plays inline) | Real TTS→Opus→Whisper round trip |
| C3 | ⬜ | Mini App looks and behaves like the web app (signed in automatically, voice, hologram) |
| C7 | ✅ | Male/female voice per person ("use a female voice"), used on web, app and Telegram voice notes | Code + server voices |
| C4 | ✅ | Per-user nickname for the assistant ("call yourself Tony") — answers to it and wakes on it on that user's devices; system stays Atulya | Code + wake test |
| C5 | ⛔ | WhatsApp — needs a Meta Business account + WhatsApp Cloud API number (owner) |
| C6 | ⛔ | Push notifications inside the APK — needs a Firebase project (owner); web/PWA push already works |

## D. Sign-in providers

| # | Status | What |
|---|---|---|
| D1 | 🔧 | Google sign-in — server code ready (verified email only; new emails become sign-ups for owner approval). Needs: owner creates the OAuth client (Web, redirect https://atulya.atulvij.com/api/auth/google/callback) → GOOGLE_CLIENT_ID/SECRET in server .env. **APK gap:** Google blocks sign-in inside WebViews → open in a Chrome Custom Tab and return a one-time code via App Link |
| D2 | ⛔ | Email verification / codes by email — needs a mailbox to send from (Gmail app password or hosting SMTP); none found on this PC |

## E. Voice and assistant quality

| # | Status | What |
|---|---|---|
| E1 | ⬜ | openWakeWord "Hey Atulya" model for always-on listening (Whisper fallback stays) |
| E2 | ✅ | Camera on demand: "turn on the camera" fixed; vision questions ("what do you see", "read this", "यह क्या है") switch it on; **only those send a frame to the AI** (privacy) | Pattern tests |
| E3 | ✅ | First words: instant spoken acknowledgement from the request itself (29 ms laptop, 9-78 ms server) | Self-test |

## G. Owner feedback 2026-10-12 (real phone use) — in order

| # | Status | What | Proof / next |
|---|---|---|---|
| G1 | 🔧 | Speech starts on the opening clause (comma or ~8 words) instead of the whole first sentence; sentences synthesized one at a time | Target first audio ≈1 s; measure on server |
| G2 | 🔧 | Passkeys: accept the Android app's own origin (apk-key-hash), exclude only this account's passkeys, clear error per failure reason, server logs the real cause | Owner retry on phone + web |
| G3 | 🔧 | Misheard speech ("we look up" → VLOOKUP) corrected by the brain from context; memory checked before asking; lasting facts saved | Prompt rule; real phrase test pending |
| G13 | ✅ | Phone chat panel grew with every message (old flex rule overrode its height) and covered the hologram; now fixed at 40 % and the messages scroll; status chips/footnote hidden on phones | Reproduced with 40 messages: 2297 px → 325 px, scrolls |
| G14 | ✅ | Requests the page didn't understand ("hide chat options") now work: many more phrases + Hindi instantly, and a `screen_control` AI tool for any wording (hide/show chat, conversation mode, new chat, history, settings, camera, mute, reload) | Real model: "make the messages go away so I only see you" → hide_chat, "start a fresh chat" → new_chat |
| G15 | ✅ | Phone hologram framing: ⋮ → VIEW: CLOSE-UP (fills the area) / WIDE (whole scene like the website); remembered per device | Local phone-size check |
| G16 | 🔧 | Phone chat panel 30 % (owner: 20-30 %), compact rows | Owner check |
| G17 | ✅ | Always the newest version on reopen: HTML no-cache (304 when unchanged), versioned assets cached 1 year (full cache wipe would re-download the scene each open) | Headers |
| G18 | 🔧 | Chrome/Edge use the browser's own speech recognizer (Google, free, accurate) like the APK; Telegram keeps the server recognizer; falls back to the server after 3 errors | Owner check in Chrome |
| G19 | 🔧 | Live server speed measured on every deploy: selftest timings in the deploy log (names/timings only — public repo) | Next deploy log |
| G20 | 🔧 | APK UI test on a CI emulator against a private Atulya on the runner (no Cloudflare): sign in, layout, hide chat → CHAT, ⋮ menu, rotation, reopen, crash, memory; failure blocks the release | Next APK build |
| G21 | ✅ | Phone sign-in box jumped when the keyboard closed → taps on CONTINUE missed; now anchored near the top | Emulator UI test passes with keyboard open |
| G22 | 🔧 | Android Back closed the whole app (e.g. with the ⋮ menu open) → now closes menu/dialog/conversation mode first; unlock grace survives the screen being recreated | Emulator UI test |
| G23 | ✅ | Phone landscape: chat panel ran past the bottom (message box cut), chips overlapped the title, system panel took ⅓ width → fits the screen | Local 915×412 check + emulator |
| G24 | ✅ | Passkeys proven end to end with a software authenticator: website over HTTPS + inside the Android app (app signing-key origin); phishing site / other app rejected. Test fails if the app-origin fix is removed | `tests/core/test_passkey_flows.py` |
| G25 | 🔧 | ⋮ menu shows which recognizer is used (PHONE / BROWSER / SERVER); emulator test checks the app uses the phone's whenever it has one, and photographs the real launcher icon | Next APK run |
| G4 | 🔧 | Conversation mode: TALK button / "hide chat" → full-screen hologram, keeps listening, chat still recorded; CHAT button returns; phone chat sheet 48→40 % height | Owner check on phone |
| G5 | 🔧 | App versions: automatic builds bump only the last number (0.5.1, 0.5.2…); middle number only for milestones | Next APK |
| G6 | ⬜ | **Speech recognition quality** (biggest issue): Android app → native Android recognizer (free, on-device, Hindi); Chrome → browser recognizer; Telegram/others → better server STT (decision: Groq free Whisper-large vs. local) | Owner decision |
| G7 | ⬜ | Noise: real voice-activity detection (Silero VAD in the browser) so clicks, nail clipping, "shh" and background talk don't trigger; ignore when nobody speaks; no "no speech" message for silence | |
| G8 | ⬜ | Chat management: clear, archive, delete; history and settings reachable from conversation mode | |
| G9 | ⬜ | Login: Telegram code auto-fill/magic link reliability; email magic link needs a mailbox (D2) | |
| G10 | 🔧 | Professional look: launcher icon v2 (whole head inside the safe zone, glow background; was cropped by round masks); app theme still to redo (owner to pick references) | Preview circle/squircle, light/dark |
| G11 | ⬜ | Phone access in the Android app (notifications, contacts, calls/SMS with approval) | |
| G12 | ⬜ | Hologram speaking animation matches speech in full-screen mode (renderer is owner's — needs owner OK) | |

## F. Later (after A-E)

Smart home (Home Assistant) · Gmail/Calendar sync · music · file/PDF answers · routines & proactive notices ·
Google Play listing (owner account) · website traffic project (separate).

## Verified recently (real runs)

- Self-test 12/12 against the running server (chat+tools, memory, profiles, code sign-in, voice unlock, TTS→STT,
  briefing, PC approval, Telegram); clean installs pass on Windows/Ubuntu/macOS (GitHub Actions).
- Web servers: Cloudflare-only firewall on 80/443 (IPv4+IPv6), SSH keys only, fail2ban active — no change needed.
