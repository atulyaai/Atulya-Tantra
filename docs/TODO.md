# Atulya — working list

One list, in order. Each item: **status** · what · how it is verified. Work top to bottom; update this file in the
same commit as the fix. History of finished work: `git log` and `docs/archive/`.

Status: ✅ done (verified for real) · 🔧 in progress · ⬜ to do · ⛔ blocked on the owner (reason given)

## A. Broken basics reported from real use (fix first)

| # | Status | Problem → fix | Verified by |
|---|---|---|---|
| A1 | 🔧 | Typed messages get no spoken reply → every reply spoken by default; 🔊/🔇 button; say "mute"/"unmute" | Built; needs your by-ear check |
| A2 | 🔧 | App/Mini App keeps demanding "Hey Atulya" → wake word now **off by default** (say "wake word on" for always-on) | Built; needs your by-ear check |
| A3 | 🔧 | Microphone permission asked repeatedly → one mic stream kept for the whole voice session | Built; needs check on phone |
| A4 | ✅ | Status panel/tools for non-admins → hidden in UI **and** `/api/status` refuses non-admins (403) | Server test + UI |
| A5 | 🔧 | Overlap on phone/small windows → header on one line + account menu (⋮); phone = hologram top, chat bottom sheet; camera box only when camera is on | Screenshots desktop + 375 px phone ✅; Mini App/APK on a real phone pending |
| A6 | ⬜ | Hologram animation does not load on phone/Mini App → find why (WebGL/load), add fallback | APK + Mini App |
| A7 | ✅ | "Update/reload page" prompt → an old cached page now reloads itself once; expired sessions show sign-in instead of an error | Code + UI |
| A8 | ✅ | Password sign-in with `atulya` → works on the public site in a real browser (the failed attempt was a mistyped password) | Public site, real browser |
| A9 | ✅ | Google-style sign-in: Continue with passkey → or username/email → Send approval to my devices / code / Use password; invitation + create account as links | Public site |
| A10 | ✅ | "Say code" removed; Resend added (30 s cooldown) | Public site |
| A11 | ✅ | Add passkey: account menu (⋮ → ADD PASSKEY) + offered after password/code sign-in | Public site |
| A12 | ✅ | Sign-up with an existing email jumps to sign-in for that account | UI flow |
| A13 | ✅ | App icon = the Atulya hologram face (web, PWA, Android launcher + round icon) | APK 0.2.1 |
| A14 | ✅ | APK download: https://atulya.atulvij.com/download (always the newest signed APK) + README | Public URL |

| A15 | ✅ | Camera turned itself on at load → on demand only (button / "turn on camera"), remembered per device | Public site |
| A16 | ✅ | Greeting shown twice after reload → one greeting; "Welcome back" by voice | Public site |

## B. Server-first architecture (owner's server, always on)

| # | Status | What | Notes |
|---|---|---|---|
| B1 | ⬜ | Replace the old `atulya.service` on the atulvij.com server with current Atulya core (accounts, history, sync, cloud brain, Telegram) behind nginx at atulya.atulvij.com | Server has 1 GB RAM: core only, no local models |
| B2 | ⬜ | Laptop/desktop = **Atulya agents** that connect out to the server: PC control, local Whisper/TTS/LLM when available | Replaces the tunnel as the main path; tunnel kept for laptop-only setups |
| B3 | ⬜ | Server is the source of truth; clients cache locally and fetch only changes (delta sync); Telegram reads from server | — |
| B4 | ⬜ | Encrypted automatic backups of the server data (daily, keep 14) | Biggest data-loss risk today |
| B5 | ⬜ | Speech on the server without local models: browser speech recognition or a small cloud STT; local Whisper when an agent is online | 1 GB RAM |

## C. Same Atulya on every channel

| # | Status | What |
|---|---|---|
| C1 | ✅ | One account across web, app and Telegram (owner's Telegram = main account), live sync ~10-13 ms |
| C2 | ✅ | Telegram voice note → reply also as a voice note (local voice → OGG/Opus, plays inline) | Real TTS→Opus→Whisper round trip |
| C3 | ⬜ | Mini App looks and behaves like the web app (signed in automatically, voice, hologram) |
| C4 | ✅ | Per-user nickname for the assistant ("call yourself Tony") — answers to it and wakes on it on that user's devices; system stays Atulya | Code + wake test |
| C5 | ⛔ | WhatsApp — needs a Meta Business account + WhatsApp Cloud API number (owner) |
| C6 | ⛔ | Push notifications inside the APK — needs a Firebase project (owner); web/PWA push already works |

## D. Sign-in providers

| # | Status | What |
|---|---|---|
| D1 | 🔧 | Google sign-in — Google Cloud project "Atulya" created; consent screen + OAuth client next |
| D2 | ⛔ | Email verification / codes by email — needs a mailbox to send from (Gmail app password or hosting SMTP); none found on this PC |

## E. Voice and assistant quality

| # | Status | What |
|---|---|---|
| E1 | ⬜ | openWakeWord "Hey Atulya" model for always-on listening (Whisper fallback stays) |
| E2 | ⬜ | Camera and text on demand ("look at this", "read this") in every client |
| E3 | ⬜ | First words < 1000 ms for common questions (now ~1800-2300 ms with tools, ~10 ms fast lane) |

## F. Later (after A-E)

Smart home (Home Assistant) · Gmail/Calendar sync · music · file/PDF answers · routines & proactive notices ·
Google Play listing (owner account) · website traffic project (separate).

## Verified recently (real runs)

- Self-test 12/12 against the running server (chat+tools, memory, profiles, code sign-in, voice unlock, TTS→STT,
  briefing, PC approval, Telegram); clean installs pass on Windows/Ubuntu/macOS (GitHub Actions).
- Web servers: Cloudflare-only firewall on 80/443 (IPv4+IPv6), SSH keys only, fail2ban active — no change needed.
