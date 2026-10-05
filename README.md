<!-- Hero Banner -->
<div align="center">
  <img src="granth/banner_animated.gif" alt="Atulya Tantra - JARVIS-Class Personal AI" width="100%"/>
</div>

<div align="center">
  <h1>
    <img src="https://readme-typing-svg.herokuapp.com?font=Cinzel&weight=700&size=42&duration=4000&pause=1000&color=F7931A&center=true&vCenter=true&width=700&height=80&lines=ATULYA+TANTRA;JARVIS-CLASS+PERSONAL+AI;VOICE+%2B+MEMORY+%2B+TOOLS;अतुल्य+तन्त्र" alt="Atulya Tantra — JARVIS-Class Personal AI" />
  </h1>
</div>

<p align="center">
  <em><strong>अतुल्य</strong> (Atulya) — Peerless, without equal &nbsp;·&nbsp; <strong>तन्त्र</strong> (Tantra) — System, loom of intelligence</em><br/>
  <strong>A personal AI assistant you talk to: a 3D hologram that listens in Hindi and English, remembers you, and acts for you.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-F7931A.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-F7931A.svg?style=flat-square" alt="MIT License"/></a>
  <a href="#"><img src="https://img.shields.io/badge/Privacy-Local_First_Option-success.svg?style=flat-square" alt="Local First"/></a>
  <a href="#"><img src="https://img.shields.io/badge/Voice-Hindi_%7C_English-orange.svg?style=flat-square" alt="Voice Hindi & English"/></a>
  <a href="#"><img src="https://img.shields.io/badge/Platform-Windows_%7C_Linux_%7C_macOS-blue.svg?style=flat-square" alt="Cross Platform"/></a>
  <a href="#"><img src="https://img.shields.io/badge/Made_in-India_🇮🇳-FF9933.svg?style=flat-square" alt="Made in India"/></a>
</p>

```
 +--------------------------------------------------------------------------+
 |                         HOW ATULYA WORKS                                 |
 |                                                                          |
 |  Your voice or text --> hologram screen (drishti/) --> server (atulya/sevak)|
 |                                  |                                       |
 |                                  v                                       |
 |                 thinking kernel (atulya/buddhi)                       |
 |            /              |                 \                            |
 |     brain: cloud       memory: what you     tools: music, email,         |
 |     or local model     told it, habits      calendar, PC, home           |
 |            \              |                 /                            |
 |                  safety: risky actions ask first                         |
 +--------------------------------------------------------------------------+
```

---

A local-first personal AI assistant. You talk to a glowing hologram: it listens in English or Hindi, thinks with a cloud or local brain, remembers you, and does things for you: music, reminders, email, calendar, price tracking, a morning briefing, smart home, and (if you turn it on) your PC.

<p align="center">
  <img src="granth/orb-home.png" alt="Atulya: one animated screen" width="420">
  <img src="granth/orb-popup.jpg" alt="A pop-up opens over the orb" width="420">
</p>

<p align="center"><img src="granth/orb_live.jpg" alt="The floating orb" width="60%"/></p>

**One screen.** There are no pages. Ask for something ("show my routines", "open the dashboard", "chat history") or tap the menu, and a pop-up slides in over the orb. Esc or a tap outside closes it. Replies appear in a caption card under the head. Admin-only details (models, health, audit log) are hidden from normal users.

![Atulya Tantra architecture](granth/architecture.svg)

## Quick start (Windows)

You need Python 3.10+ and Node.js 18+.

**One command.** `install.py` shows what is already configured, asks only for what is
missing, installs the extras, builds the dashboard and checks that everything works:

```powershell
python install.py
```

It prints a table like this — secrets are never shown in full, only `set (last 4)`:

```
  Setting                                    State       How to get it
  ------------------------------------------- ----------- -------------------------
  Dashboard sign-in token                    ok          set (HiCm)
  Telegram bot token                         missing     message @BotFather, send /newbot
  Telegram user allowed to talk to Atulya    missing     message @userinfobot for your id
  Brain key — OpenRouter                     ok          set (21ca)
  Morning briefing time                      missing     for example 08:00
```

Other invocations:

| Command | What it does |
|---|---|
| `python install.py --doctor` | Report only — changes nothing |
| `python install.py --yes` | Unattended, accepts defaults (cPanel, VPS, CI) |
| `python install.py --profile full` | `basic` / `voice` / `full` / `server` — pick up front, no prompts |
| `python install.py --no-start` | Configure and check, but do not offer to start |

The dashboard token is generated for you if you do not have one; it is written only to
your local `.env`, which is git-ignored.

Manual equivalent:

1. Copy `.env.example` to `.env` and add a brain (see [Brains](#brains)). A free OpenRouter key is enough.
2. Double-click **`start.bat`**. It installs what is missing, builds the web app only when it changed, and starts the server.
3. Open http://localhost:8501 in **Chrome or Edge**, click once, and allow the microphone. On the computer Atulya runs on there is no login.

First start takes a minute. Manual start instead of `start.bat`:

```powershell
python -m pip install -e ".[serve]"
cd drishti; npm install; npm run build; cd ..
python -m atulya.sevak
```

Optional extras: `.[ambient]` (always-on listener: `atulya listen`), `.[control]` (PC control), `.[vision]` (camera, OCR), `.[brain]` (a local model), `.[wake]` (wake-word model, Piper voice), `.[docs]` (document tools), `.[browser]` (browser automation).

## Brains

Atulya asks the first brain that is set up and falls back to the next. Put keys in `.env`:

| # | Brain | Setting | Notes |
|---|---|---|---|
| 1 | Claude | `ANTHROPIC_API_KEY` | Fastest and smartest; answers first when set |
| 2 | Local model | `.[brain]` + `ATULYA_AUTO_DOWNLOAD_MODEL=true` | Works offline; downloads about 400 MB. Choose a size with `ATULYA_BRAIN=tiny/balanced/power/auto` |
| 3 | Ollama | `ATULYA_OLLAMA_MODEL` | Local models you already run |
| 4 | Groq | `GROQ_API_KEY` | Free tier, very fast |
| 5 | OpenRouter | `OPENROUTER_API_KEY` | Free `:free` models, tried in turn when one is busy (`ATULYA_OPENROUTER_MODEL`) |
| 6 | Gemini | `GEMINI_API_KEY` | Free tier; also describes pictures |
| 7 | OpenAI, NVIDIA NIM | `OPENAI_API_KEY`, `NVIDIA_API_KEY` | Optional |

Want a bigger model? See `prayog/README.md`: try one locally (`prayog/try_model.py`) or use a free Colab GPU (`prayog/connect_remote.py`).

`ATULYA_BRAIN=cloud` puts the cloud brains first. With no local model installed (`ATULYA_AUTO_DOWNLOAD_MODEL=false`), if every cloud brain is busy Atulya says so and you try again. Every cloud brain sends your questions to that company; only the local model keeps them on your PC.

## What Atulya can do

What is done, tested, planned and still missing: [granth/STATUS.md](granth/STATUS.md).

| Ability | Status |
|---|---|
| Hologram head with lip sync, blink and breathing; volume boost up to 300% | Working |
| Listening in English and Hindi; "stop" interrupts; works without a wake word in the web app | Working. The always-on listener (`atulya listen`) uses "Hey Atulya" / "हे अतुल्य" |
| Reminders, calendar, email, weather, open websites, time | Working |
| Play music (YouTube, Spotify), media keys and volume (Windows) | Working |
| Price watchlist, morning briefing (`ATULYA_BRIEFING_AT=08:00`) | Working |
| Memory that learns facts about you; recalled when you ask about the past | Working |
| Camera motion and person detection, reading text in pictures | Working; scene description needs `ollama pull moondream` or a Gemini key |
| Smart home (Home Assistant, MQTT), messaging channels | Needs your hardware or accounts to verify |
| Control the PC (open apps, type, shortcuts) | Off until `ATULYA_PC_CONTROL=on`; asks before each action; audited |
| Offline natural voice | Optional: Piper (`ATULYA_PIPER_MODEL`) |

Atulya never reads out emoji and answers "what can you do" with a real list.

## Phone and other devices

1. In `.env` set `ATULYA_HOST=0.0.0.0`, then restart. (`ATULYA_LOCKDOWN=on` does the opposite: this computer only.)
2. Find your PC's address (for example `192.168.1.15`) and open `http://192.168.1.15:8501` on the phone.
3. Log in with username `admin` and the password you set in `ATULYA_DASHBOARD_TOKEN` (or the one written to `kosh/admin_token.txt` the first time). Other devices always need a login; only this computer skips it (`ATULYA_REQUIRE_LOGIN=on` turns that off).
4. **Camera and microphone on the phone need https.** Browsers only allow them on `https://` pages or on `http://localhost`. Set `ATULYA_HTTPS=on` in `.env` and restart: Atulya then serves `https://192.168.1.15:8501` with a certificate made for this computer. The browser warns once (the certificate is your own); choose Advanced, then Continue. If your PC's address changes, a new certificate is made automatically.
5. Add to the home screen: **iOS** Share, Add to Home Screen; **Android** menu, Install app.
6. Away from home: install Tailscale on the PC and phone and use the private address (`http://100.x.y.z:8501`). Avoid exposing the port to the internet.

## Devices

TV, phone, lights, plugs, PCs: say "scan for devices", "add number 1 as living room TV", then "turn off the TV" or "volume up 5 on the TV". Works through HTTP profiles (Roku, Kodi, Tasmota, WLED, Shelly and more), Android over ADB, Wake-on-LAN, and Home Assistant (thousands of brands). Atulya can also draft a profile for a device it doesn't know. See [granth/DEVICES.md](granth/DEVICES.md) for what is and isn't covered.

## Money

Say "I spent 500 on groceries", "how much did I spend this month", "set a budget for food of 5000", "add bill electricity 2300 due on 18", "what bills are due". Everything stays in `kosh/agent/money.json`; Atulya never connects to a bank and never pays anything.

Automatic recording of bank alerts (open **Action engine → Money** to set this up):

- **Email:** say "check my email for bank transactions" (needs Google connected, or `configure_email`).
- **SMS from your phone:** an SMS-forwarding app on the phone posts each bank SMS to your PC. Atulya gives you the address and a key that can only add bank alerts. The phone must reach the PC (see [Phone and other devices](#phone-and-other-devices)).
- **Bank statement:** put the CSV in `kosh/` and say "import statement.csv".

OTPs, offers and due reminders are ignored, and the same transaction arriving by SMS and email is counted once. Bank messages vary, so check the totals the first week.

## Layout

Every file has a Sanskrit/Hindi name that says what it does, in plain letters so editors and Windows handle them (the Devanagari is beside each name). The layout is flat: every folder below holds files only, and `atulya/` has just 19 Python files.

| Folder | Name | Meaning | What lives here |
|---|---|---|---|
| `atulya/` | | | All the Python, 19 files (table below) |
| `drishti/` | दृष्टि | sight, what you see | The animated screen (React + Vite), all files side by side: `Orb.jsx`, `Dashboard.jsx`, `MemoryTree.jsx`, `Hologram.js` ... plus `index.html`, `vite.config.js`, `build.py` |
| `granth/` | ग्रंथ | book, text | Guides, architecture, security, features, status and the pictures |
| `pariksha/` | परीक्षा | examination, test | The test suite: one `test_*.py` per part |
| `prayog/` | प्रयोग | experiment | Try a bigger brain: download and benchmark local models, or use a free Colab GPU |
| `kosh/` | कोश | treasury | Everything Atulya stores on your computer (git-ignored). An old `data/` folder is moved here automatically the first time you start |

Files in `atulya/`:

| File | Name | Meaning | What it holds |
|---|---|---|---|
| `buddhi.py` | बुद्धि | intellect | The pipeline every request goes through (perceive, understand, decide, act, remember, react), routines, reflexes (triggers) and what Atulya learns about you |
| `mastishk.py` | मस्तिष्क | brain | Brain tiers (`ATULYA_BRAIN`), the 22-provider catalogue, safety rules (what must ask first), the tool belt, the provider failover router, the local model and the language-model layer |
| `kriya.py` | क्रिया | action | Everything Atulya can *do*: assistant tools (reminders, calendar, email, weather, websites), the intent router, money, music and media, price tracking, the morning briefing, PC control, device tools, the agent loop and the audit log |
| `jaal.py` | जाल | web | Browser automation, web tasks, web search, Gmail and Google Calendar |
| `kaushal.py` | कौशल | skill | The heavier capabilities and creation tools, documents, spreadsheets, charts, business automation |
| `setu.py` | सेतु | bridge | MCP server and client for outside tools (`setu_servers.json`) |
| `upakaran.py` | उपकरण | devices | TVs, phones, lights, PCs: JSON profiles (`upakaran_profiles.json`), ADB, Samsung, Wake-on-LAN, Home Assistant, discovery, learn-a-device, the hub |
| `indriya.py` | इन्द्रिय | the senses | Camera, motion, home sensors, reading pictures |
| `shruti.py` | श्रुति | hearing | The always-on listener: microphone, wake word (English and Hindi), barge-in, tray (`python -m atulya.shruti`) |
| `vani.py` | वाणी | speech | The voice pipeline |
| `smriti.py` | स्मृति | memory | The memory manager, vector store and session search |
| `sandesh.py` | संदेश | message | Telegram, Discord, Slack, email and other messaging channels |
| `sevak.py` | सेवक | servant | The web server app (`python -m atulya.sevak`) |
| `dwar.py` | द्वार | gate | The server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, automation, home and dashboard |
| `raksha.py` | रक्षा | protection | Encryption at rest (vault), HTTPS certificates, security helpers, lockdown |
| `sharir.py` | शरीर | body | What Atulya can do on a computer: files (inside the folders you allow, deletes go to a trash), clipboard, windows, mouse, screen, commands, installing software, printing, health check, with permission levels for paired devices |
| `bhava.py` | भाव | feeling | Mood, persona and identity |
| `adhar.py` | आधार | foundation | Settings, `.env` reading, the `data` -> `kosh` move, text helpers, safe maths, the event bus, the heartbeat |
| `adesh.py` | आदेश | command | The command line (`python -m atulya.adesh doctor`) and the readiness checks |

```text
Atulya-Tantra/
|-- atulya/        # all the Python: 19 flat files (table above)
|-- drishti/       # the animated screen, flat: the source, index.html, vite.config.js, build.py
|-- granth/        # guides, architecture and pictures
|-- pariksha/      # tests
|-- prayog/        # experiments: bigger local models, Colab GPU brain
|-- kosh/          # everything Atulya stores locally (git-ignored)
|-- pyproject.toml, start.bat, Dockerfile, docker-compose.yml
`-- .env           # your keys (git-ignored)
```

## How a request flows

```mermaid
flowchart LR
    You["You: voice or text"] --> Web["drishti/ (the orb)"]
    Web --> Server["atulya.sevak"]
    Server --> Kernel["cognition kernel"]
    Kernel --> Tools["tools: agent/, capabilities/"]
    Kernel --> Brain["brain: cloud or local"]
    Kernel --> Memory["memory"]
    Tools --> Safety["safety: risky actions ask first"]
```

Assistant tools live in `atulya/kriya.py` and register themselves with `@tool`. Risky ones (sending email, deleting events, PC control) ask first by default (`ATULYA_AUTO_APPROVE` can pre-approve specific ones), and every call is appended to `kosh/agent/audit.jsonl`.

## Memory

Atulya's memory is in `atulya/smriti.py`: a vector store and session search, which is what the brain uses. A small local model copies recalled answers back, so with it memory is only shown when you ask about the past. Your profile (facts it learned, habits, what you trust it to do without asking) is under the **About you** pop-up. Identity and prompt rules are in `atulya/bhava.py`; an optional override goes in `kosh/identity.json`.

## Development

```powershell
python -m pytest -q       # tests
ruff check .              # lint (unused imports are errors)
cd drishti; npm run dev       # web dev server, proxies /api and /ws to :8501
python -m atulya.adesh doctor
```

Docker: `docker compose up --build` (builds the web app, serves on port 8501, keeps `kosh/` on your disk). Not yet tried on a real server.

## API

Token-protected routes expect `X-Atulya-Token`. Full list: [granth/API_REFERENCE.md](granth/API_REFERENCE.md).

| Route | Who | What |
|---|---|---|
| `GET /api/auth/local` | this computer only | sign in without a password |
| `POST /api/auth/login` | everyone | username and password |
| `POST /api/chat`, `/api/chat/stream`, `/api/voice/chat` | signed in | talk to Atulya |
| `GET/DELETE /api/chat/history` | signed in | your conversation |
| `POST /api/voice/stt`, `/api/voice/tts` | signed in | speech to text and back |
| `GET /api/profile` and friends | signed in | what Atulya knows about you |
| `GET /api/brain`, `/api/health`, `/api/telemetry`, `/api/system`, `/api/audit` | admin | models, server health, audit log |
| `/api/users`, `/api/routines`, `/api/senses`, `/api/triggers`, `/api/fabric`, `/api/agent/tools` | admin | management |
| `GET /v1/models` | admin | OpenAI-style model list |

## Notes

- Do not commit `.env` or `kosh/`; they hold your keys, accounts and memory.
- `drishti/dist` is built by `start.bat`; `drishti/node_modules` is only needed while building and can be deleted any time.
- Custom model training does not belong here; keep it in a separate repository and connect it as a provider.
- Before exposing Atulya beyond your own network, read the hardening checklist and the security model in [granth/DEPLOYMENT.md](granth/DEPLOYMENT.md).

---

## Contributing

Contributions, bug reports, and ideas are welcome!

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/your-feature`
3. **Commit** your changes: `git commit -m "feat: add your feature"`
4. **Push** and open a **Pull Request**

Please keep PRs focused and include tests where relevant. For major changes, open an issue first. See [granth/CONTRIBUTING.md](granth/CONTRIBUTING.md) for the project rules and where things go, and [granth/STATUS.md](granth/STATUS.md) for what is done and planned.

> All contributions are released under the [MIT License](LICENSE).

## License

MIT License. Copyright (c) 2026 Atulya AI (atulyaai). See [LICENSE](LICENSE).
