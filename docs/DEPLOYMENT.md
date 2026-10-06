# Deployment

One production path lives here: **configure → build → run → harden → verify → update.**
Everything that is a *tutorial* rather than the production path — Oracle VM + Cloudflare, the
Telegram Mini App, Termux phone pairing, pairing a second computer, Google Drive/Gmail — is in
[RECIPES.md](RECIPES.md).

Testing is in [CONTRIBUTING.md](CONTRIBUTING.md). What works and what is only proven in tests is
in [STATUS.md](STATUS.md).

> ⚠️ **Read this first:** the Docker image has **never been built** (ROADMAP fix F1). Until that
> closes, the native path below is the one that is actually proven. Prefer it unless you need a
> server.

---

## 1. Choose a path

| Path | Use it when | State |
|---|---|---|
| **Native service** (`python -m atulya.sevak`) | This computer, or a server you control | **Proven.** The real server has been started and exercised (11 API routes, a money chat, the rebuilt dashboard) |
| **Docker Compose** | You want an isolated, repeatable server image | **Unverified — the image has never been built.** Do not commit to it until F1 closes |
| **systemd (`sevak.service`)** | A Linux host where Docker should start at boot | Thin wrapper around `docker compose --profile tunnel up -d`; inherits Docker's status |

---

## 2. Prerequisites

- **Python 3.10+**
- **Node.js 18+** (only needed to build the web app)
- A brain key. A free OpenRouter key is enough; see [README → Brains](../README.md#brains).

---

## 3. Install

### One command

```powershell
python install.py
```

It reports what is already configured, asks only for what is missing, installs the extras, builds
the dashboard and checks that everything works. Secrets are never printed in full — only
`set (last 4)`.

| Command | What it does |
|---|---|
| `python install.py --doctor` | Report only — changes nothing |
| `python install.py --yes` | Unattended, accepts defaults (cPanel, VPS, CI) |
| `python install.py --profile full` | `basic` / `voice` / `full` / `server` — pick up front, no prompts |
| `python install.py --no-start` | Configure and check, but do not offer to start |

### Manual equivalent

```bash
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1
pip install -e ".[serve,dev]"
cd frontend && npm ci && npm run build && cd ..
```

Optional extras: `.[ambient]` (always-on listener), `.[control]` (PC control), `.[vision]`
(camera, OCR), `.[brain]` (a local model), `.[wake]` (wake-word model, Piper voice), `.[docs]`
(document tools), `.[browser]` (browser automation).

`frontend/dist/` is generated and git-ignored — **a clean checkout has no web app until you run
the build**. This is the single most common way to end up with a blank dashboard or an APK with
nothing inside it.

---

## 4. Run

### Native (proven)

```bash
uvicorn atulya.sevak:app --host 127.0.0.1 --port 8501
# or simply
python -m atulya.sevak
```

On Windows, double-click **`start.bat`**: it installs what is missing, rebuilds the web app only
when it changed, and starts the server.

Open http://127.0.0.1:8501 in Chrome or Edge, click once, and allow the microphone. On the computer
Atulya runs on there is no login; every other device needs one.

### Docker (unverified — see F1)

```bash
docker compose -f docker-compose.yml up -d
```

The container serves the built `frontend/dist/` app and API from port 8501 and keeps `kosh/` on
your disk.

```bash
cp .env.example .env          # then set a dashboard token
docker compose up -d --build
```

- It publishes **`127.0.0.1:8501`** by default. Set `ATULYA_DOCKER_BIND=0.0.0.0` only when you
  need LAN access from other devices.
- The JWT signing key is created in the persistent `kosh/` volume on first start. Leave
  `ATULYA_JWT_SECRET_FILE` unset unless you manage the key yourself (for example a Docker secret).
- For public hosting, put it behind HTTPS or a Cloudflare Tunnel
  ([RECIPES.md](RECIPES.md#run-it-on-an-oracle-free-vm-behind-cloudflare)).

### Start at boot on Linux

```bash
sudo cp sevak.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now sevak
```

`sevak.service` is `WorkingDirectory=/opt/atulya` + `docker compose --profile tunnel up -d`.
Verify those two lines match your layout before enabling it. **Do not configure both systemd and
Compose restart management** — you will get two supervisors fighting over one stack.

---

## 5. Environment variables

Set these in `.env` (git-ignored). The server reads `.env` itself (`atulya/adhar.py`), so quoting,
spaces and a Windows Notepad BOM are all handled — you do not need `start.bat` to load them.

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | No | Groq inference |
| `OPENROUTER_API_KEY` | No | OpenRouter fallback |
| `GEMINI_API_KEY` | No | Gemini fallback |
| `ATULYA_ENCRYPTION_KEY` | No | Data encryption key |
| `ATULYA_TELEGRAM_BOT_TOKEN` | No | Telegram bot |
| `ATULYA_TELEGRAM_ALLOWLIST` | No | Comma-separated Telegram user ids allowed to talk to Atulya (and to open the Mini App). Empty means nobody |
| `ATULYA_PUBLIC_URL` | For the Mini App | Public HTTPS origin of this server, e.g. `https://atulya.example.com`. Registered once with @BotFather via `/newapp`; see [RECIPES.md](RECIPES.md#telegram-mini-app-the-hologram-on-your-phone) |
| `ATULYA_DOCKER_BIND` | Docker only | Bind address for the container. Defaults to `127.0.0.1`; set `0.0.0.0` only when you need LAN access |
| `ATULYA_JWT_SECRET_FILE` | Docker/secrets | Where to persist the JWT signing key. Leave unset and Atulya creates it in the mounted `kosh/` volume |
| `ATULYA_TANTRUM_ALLOW_MODEL` | No | Enable local on-device model |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | No | Google Drive MCP |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | No | Gmail MCP |

`python -m atulya.adesh doctor` reports which of these are set without printing their values.

---

## 6. MCP servers

Edit `atulya/setu_servers.json` to enable integrations (filesystem, git, browser, Google Drive,
Gmail, etc.). **All start disabled by default.** A single manager is created for the whole process
and the brain reads its tools from `build_unified_registry()`, so an entry you enable here reaches
the model on every surface — web UI and Telegram alike.

Setup for the Google servers is in [RECIPES.md](RECIPES.md#google-drive-and-gmail-mcp--oauth).
Verify with `python -m atulya.adesh readiness`: if a server is enabled without credentials it
reports `production-candidate` and names the missing variable.

---

## 7. Hardening checklist

Atulya can bind locally or to the LAN based on configuration.

- `ATULYA_HOST=127.0.0.1` — only this computer can connect.
- `ATULYA_HTTPS=on` — serve https with a self-signed certificate for this computer (needed for
  phone camera/mic over Wi-Fi). Certificate and key are in `kosh/certs/` (override with
  `ATULYA_CERTS_DIR`); the key is readable by you only. For a public site use a real certificate
  behind a reverse proxy instead.
- `ATULYA_CORS_ORIGINS=https://your-site` — only listed web origins may call the API.
- `ATULYA_PC_CONTROL` stays unset unless you want Atulya to open apps and type; every such action
  asks first.
- `ATULYA_LOCKDOWN=on` — one switch for the above: listen on localhost only and allow no
  cross-site (CORS) callers unless `ATULYA_CORS_ORIGINS` lists them. The phone app will not reach
  it while this is on.
- Every tool call is written to a tamper-evident hash chain in `kosh/agent/audit.jsonl` (secrets
  masked). `GET /api/audit` (admin token) returns the latest entries.

---

## 8. Security model: what is enforced today, and what is not

### Enforced today

- **Login:** API routes need a session token or the admin token (`X-Atulya-Token`), compared in
  constant time. On the computer Atulya runs on, `/api/auth/local` signs you in without a password;
  it refuses proxied and remote requests, and `ATULYA_REQUIRE_LOGIN=on` turns it off.
- **Admin-only details:** normal users never see which model or provider answers, tool traces,
  server health, telemetry, the audit log, the model list, or the Brains & keys, Reflexes, Routines
  and Senses pop-ups. The server enforces this (403), and replies to normal users carry no model
  details.
- **Risky actions ask first:** sending email, deleting events or reminders, unlocking doors,
  running code, and all PC control need your confirmation (`atulya/mastishk/`).
  `ATULYA_AUTO_APPROVE` can pre-approve specific ones.
- **PC control is off by default:** `ATULYA_PC_CONTROL=on` enables it; it only opens apps from a
  fixed list and blocks dangerous shortcuts.
- **Audit log:** every tool call is appended to `kosh/agent/audit.jsonl` with passwords and tokens
  masked; admins can read it at `GET /api/audit`.
- **Triggers cannot be hijacked:** event data never becomes a command, and risky trigger commands
  are refused unless the rule allows them.
- **Network guard:** the price tracker and web fetch tools only reach public addresses
  (`SSRFProtection`).
- **No `eval`:** math goes through an AST allowlist (`atulya/adhar.py`).
- **Bounded inputs:** request payloads and query parameters are size-limited; chat rejects model
  paths and empty prompts.
- **Lockdown profile:** `ATULYA_LOCKDOWN=on` listens on localhost only and allows no cross-site
  callers.

### Not done yet

- No OS-level sandbox for tools; protection is the confirmation prompt and allowlists.
- The audit log is a hash chain that makes edits detectable; it is **not encrypted**.
- Private data is encrypted only when `ATULYA_VAULT_PASSPHRASE` is set (see below). `.env` must be
  protected separately.
- Rate limiting is basic: a per-address request cap in `atulya/sevak.py`, nothing per user or per
  route.
- For internet deployment, only expose the app through Cloudflare Tunnel and Cloudflare Access
  ([RECIPES.md](RECIPES.md)).

### Guidance

- Treat `kosh/` (memory, audit log, tokens), `.env` and `kosh/chat_history.json` as sensitive;
  they are git-ignored.
- Do not expose the dashboard to an untrusted network without TLS, a reverse proxy and login.

### Encryption at rest (`ATULYA_VAULT_PASSPHRASE`)

Off by default. When a passphrase is set, private files (money, calendar, reminders, email
settings, chat history, profiles) are stored encrypted with a key derived from the passphrase
(scrypt) and a random salt in `kosh/vault.salt`. The passphrase is never written to disk. A file
that cannot be opened is never overwritten. **There is no recovery if the passphrase is lost.** It
does not protect against someone who can read the running process or your `.env`.

---

## 9. Verify before you deploy

From the repository root:

```bash
python -m pytest -q          # must be green
ruff check .                 # must be clean
cd frontend && npm ci && npm run build   # must exit 0
python -m atulya.adesh readiness         # reports missing config by name
```

**PASS:** every command exits successfully, and the local app starts and lets you sign in *before*
you create a server or expose a hostname.

**Known gap:** phone and remote-computer companions still need real-device verification. Until
then, treat those paths as unverified on hardware.

---

## 10. Update

```bash
git pull
docker compose up -d --build atulya
docker compose up -d cloudflared
docker compose ps
docker compose logs --tail=100
```

For the native path: `git pull`, `pip install -e ".[serve]"`, `cd frontend && npm ci && npm run
build`, then restart the service.

**PASS:** services are running and the site prompts for login from a signed-out browser.

---

## Where to go next

| I want to… | Go to |
|---|---|
| Run it on an Oracle free VM behind Cloudflare | [RECIPES.md](RECIPES.md#run-it-on-an-oracle-free-vm-behind-cloudflare) |
| Put the hologram in Telegram (Mini App) | [RECIPES.md](RECIPES.md#telegram-mini-app-the-hologram-on-your-phone) |
| Pair my phone (Termux) or another computer | [RECIPES.md](RECIPES.md#pair-a-phone-with-termux) |
| Connect Google Drive or Gmail | [RECIPES.md](RECIPES.md#google-drive-and-gmail-mcp--oauth) |
| See what actually works | [STATUS.md](STATUS.md) |
| See what is planned | [ROADMAP.md](ROADMAP.md) |
