# Atulya capability register

One row per capability, mapped to the code as it is **today** (checked 2026-10-21 against the code, not guessed; a 🔧 means code exists but has no live receipt yet).
Order of work lives in `docs/TODO.md` section H; this file is the map.

**Rule:** every capability is built **once on the server** as a tool in `tools/plugins/toolkit.py` (or a plugin
behind it). Web, Android app, Telegram and MCP all call that same tool. Never a channel-specific copy.

| Type | Use it for |
|---|---|
| Tool (function) | One operation: `get_weather`, `where_am_i`, `search_files` |
| Plugin | A family of tools for one service (weather, email, GitHub) |
| Skill (`tools/skills/<name>/SKILL.md`) | A multi-step recipe that calls tools (briefing, research) |
| MCP | Exposing the same tools to outside AI apps; not an extra hop for our own channels |
| Device agent | Things only a device can do: laptop files/apps, phone GPS |
| Worker / scheduler | Jobs that outlive a chat: reminders, monitoring, retries |
| Core service | Identity, permissions, memory, approvals, audit |

Status: ✅ works (tested for real) · 🔧 partial · ⬜ missing · ⛔ blocked on the owner

## Where things run

| Place | Can do | Cannot do without… |
|---|---|---|
| Server (atulvij.com) | AI, memory, weather/news/web, reminders, Telegram, server health (read-only), approvals | — |
| Website / PWA | Chat, voice (browser recognizer in Chrome), location when allowed, camera on demand | — |
| Android app | Same + phone speech recognizer, location, passkeys, biometric lock | Phone files (needs document picker), notifications (planned: Telegram, which works today, plus self-hosted ntfy; no Firebase, see GOAL M4) |
| Telegram | Chat, voice notes, location button, approvals, reminders, Mini App | Device access (by design) |
| Laptop / desktop | PC control works only when Atulya runs **on** that PC | **Device agent** (H6) to work from the server |

## Capabilities

### Platform and safety
| ID | Capability | How | Status |
|---|---|---|---|
| PLT-01 | Shared tool registry used by web + Telegram | Core (`toolkit.TOOLS`, `Toolbox`) | ✅ |
| PLT-02 | Capability catalogue the AI and UI can read ("what can you do / what's missing here?") | Core service | ⬜ H2 |
| PLT-03 | Honest status: available / needs location / needs connection / needs approval / unsupported | Tool result contract | 🔧 location only (H1); rest H2 |
| PLT-04 | Approval queue for anything that changes the computer or sends outside | Core (`confirm=True`) | 🔧 Server policy fixed and enforced by `tests/plugins/test_approval_policy.py`; the Android native SMS/call confirmation (C3) is written but not built or checked on a device; Telegram has no Approve/Deny yet; approvals are lost on restart (H4) |
| PLT-05 | Identity: passkeys, password, Telegram, codes; one account everywhere | Core (`atulya/auth.py`) | ✅ (passkey ceremonies tested) |
| PLT-06 | Per-device, per-resource permissions | Policy service | ⬜ H5 |
| PLT-07 | Audit log of tool runs (who, what, result) | Event store | ⬜ H3 |
| PLT-08 | Secrets encrypted at rest, logs redacted | Core | 🔧 Windows only (DPAPI); on Linux `secrets_store.py` stores base64 (`PLAIN:`), which is not encryption (AUDIT H3) |
| PLT-09 | Durable jobs: retries, resume after restart, cancel | Worker | 🔧 reminders/briefings only; H8 |

### Information and location
| ID | Capability | How | Status |
|---|---|---|---|
| LOC-01 | Current weather, named place | Tool `get_weather` | ✅ |
| LOC-02 | Next hours / today / tomorrow / 7-day forecast, rain %, wind, UV, sunrise/sunset | Tool `get_weather(when)` | ✅ H1 |
| LOC-03 | "Where am I" — address from device location | Tool `where_am_i` (OSM Nominatim) | ✅ H1 |
| LOC-04 | Device location with consent: web/app geolocation, Telegram "share location" | `/api/location`, Telegram location messages | ✅ H1 (owner check on phone) |
| LOC-05 | Saved home city as fallback | Profile `city` | ✅ |
| LOC-06 | Places near me, routes, travel time | Maps plugin (OSM/OSRM) | 🔧 `places_near_me`, `route_time` (OSRM public demo) exist; no live receipt |
| LOC-07 | Severe-weather / rain alerts pushed to you | Worker + weather tool | ⬜ H8 |
| RES-01 | Live web search with sources | Search plugin | 🔧 `search_web` exists (no SearXNG yet); no live receipt |
| RES-02 | Read a web page and summarize it | Fetch tool + model | 🔧 `read_url` exists (public https only, untrusted-content wrapper); no live receipt |
| RES-03 | News headlines | Tool `get_news` | ✅ |

### Memory and personal
| ID | Capability | How | Status |
|---|---|---|---|
| MEM-01 | Remember / recall / forget facts | Tools | ✅ |
| MEM-02 | Preferences: name, language, tone, **short vs detailed answers**, voice | Profile + `update_profile` | ✅ |
| MEM-03 | Search past conversations | Tool `search_past_chats` | ✅ |
| MEM-04 | Ask "short or detailed?" when unclear; default short | Prompt policy | 🔧 default short; H2 adds the ask |
| MEM-05 | Project memory (status, blockers, next step) | Smriti | ⬜ later |

### Files and documents
| ID | Capability | How | Status |
|---|---|---|---|
| FIL-01 | Find files by name (on the machine Atulya runs on) | Tool `search_files` | 🔧 local only |
| FIL-02 | Read + summarize PDF, DOCX, XLSX, CSV, TXT, code | Document tools | ⬜ H6 |
| FIL-03 | Upload a file in chat (web/app/Telegram) and ask about it | Upload API + document tools | ⬜ H6 |
| FIL-04 | Edit a file safely: preview diff, save as new copy, approval | File service | ⬜ H7 |
| FIL-05 | Create Word/Excel/PDF/PowerPoint from a request | Document generators | ⬜ H7 |
| FIL-06 | Laptop files from anywhere (paired agent, approved folders only) | Device agent | ⬜ H6 |
| FIL-07 | Phone files (Android document picker) | App + upload API | ⬜ H6 |
| FIL-08 | Server files and logs (read-only, approved paths) | Server tool | 🔧 health only (`server_status`); H5 |

### Devices and server
| ID | Capability | How | Status |
|---|---|---|---|
| DEV-01 | Open apps/URLs, media keys, screenshot on the PC Atulya runs on | Tools (approval) | ✅ local |
| DEV-02 | Pair a laptop/desktop agent to the server; list devices + status | Device agent + registry | 🔧 `AgentHub` pairing/jobs/receipts and `tools/device_companion.py` exist; no live pairing receipt |
| DEV-03 | Server health: CPU/RAM/disk/services (read-only SSH) | Tool `server_status` | ✅ |
| DEV-04 | Server logs explained, service restart with approval | Server tools | ⬜ H5 |
| DEV-05 | Deploy with tests + rollback | GitHub Actions | ✅ |

### Communication and accounts
| ID | Capability | How | Status |
|---|---|---|---|
| COM-01 | Telegram chat, voice notes, approvals, reminders | Channel | ✅ |
| COM-02 | Gmail: search, summarize, draft (send only with approval) | Email plugin (OAuth) | ⛔ needs Google OAuth (D1) → H9 |
| COM-03 | Calendar (Google) | Calendar plugin | ⛔ D1 → H9; local calendar ✅ |
| COM-04 | GitHub: repos, issues, PRs, CI status | GitHub plugin (`gh` token) | ⬜ H9 |
| COM-05 | WhatsApp | Business API | ⛔ C5 |
| WEB-01 | Act on websites (forms, downloads) with approval | Browser automation | ⬜ later |

### Automation
| ID | Capability | How | Status |
|---|---|---|---|
| AUT-01 | Reminders (one-time) | Worker | ✅ |
| AUT-02 | Morning briefing | Skill + worker | ✅ |
| AUT-03 | Recurring routines ("every weekday 9am …") | Scheduler | ⬜ H8 |
| AUT-04 | Watch a condition and alert (rain, disk full, site down) | Worker | ⬜ H8. The old rain/disk/site-down triggers are archived at `F:\Atulya-Tantra-cleanup-archive\code\routines_workflow_engine.py`; reuse them for the M10 alert pipeline (PLAN.md M10-3) |
| AUT-05 | Multi-step tasks with checkpoints that survive restarts | Workflow engine | ⬜ H8 |

### Interop
| ID | Capability | How | Status |
|---|---|---|---|
| ECO-01 | MCP server for outside AI apps | `tools/mcp/server.py` | 🔧 has its **own copies** of 4 tools (old weather) → H2 exposes the shared registry |
| ECO-02 | Use outside MCP servers as tools | MCP client + approvals | ⬜ later |
| ECO-03 | Skills (`tools/skills/*/SKILL.md`, `use_skill`) | Skill registry | 🔧 1 skill (daily-briefing) |

## Acceptance tests (the real measure, not the number of tools)
1. "Will it rain tomorrow where I am?" from web, app and Telegram → same forecast, asks for location once. **(H1 — passes on web locally; Telegram/app need the owner's phone)**
2. From Telegram: "find my latest budget spreadsheet on my laptop and summarize it" → finds it on the paired laptop, asks if needed, summarizes. (H6)
3. "Check the server logs and explain the error" → reads approved logs, explains, proposes a fix, asks before changing anything. (H5)
4. "Summarize today's important emails and draft replies" → drafts only; sending needs approval. (H9)
5. "What can you do here, and what's missing?" → honest list per channel with how to enable the missing ones. (H2)
