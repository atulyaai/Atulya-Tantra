# Deployment

## Quick Start (Docker)

```bash
git clone <repo>
cd Atulya-Tantra
docker compose up -d
```

Open http://localhost:80

## Manual

```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1
pip install -e ".[serve,dev]"
uvicorn atulya.sevak:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | No | Groq inference |
| `OPENROUTER_API_KEY` | No | OpenRouter fallback |
| `GEMINI_API_KEY` | No | Gemini fallback |
| `ATULYA_ENCRYPTION_KEY` | No | Data encryption key |
| `ATULYA_TELEGRAM_BOT_TOKEN` | No | Telegram bot |
| `ATULYA_TANTRUM_ALLOW_MODEL` | No | Enable local on-device model |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | No | Google Drive MCP |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | No | Gmail MCP |

## MCP Servers

Edit `atulya/setu_servers.json` to enable integrations (filesystem, git, browser, Google Drive, Gmail, etc.). All start disabled by default.

## Production

```bash
docker compose -f docker-compose.yml up -d
```

The nginx reverse proxy handles:
- Static file serving from `drishti/dist/`
- API proxy to uvicorn on port 8000
- WebSocket upgrade headers
- 100MB upload limit

## Testing

```bash
pip install -e ".[dev]"
pytest -x --tb=short -q
```

## Hardening checklist

Atulya listens on all interfaces and accepts any CORS origin by default so the phone app can reach it over your LAN. To lock it to this machine:

- `ATULYA_HOST=127.0.0.1` — only this computer can connect.
- `ATULYA_HTTPS=on` — serve https with a self-signed certificate for this computer (needed for phone camera/mic over Wi-Fi). Certificate and key are in `kosh/certs/` (override with `ATULYA_CERTS_DIR`); the key is readable by you only. For a public site use a real certificate behind a reverse proxy instead.
- `ATULYA_CORS_ORIGINS=https://your-site` — only listed web origins may call the API.
- `ATULYA_PC_CONTROL` stays unset unless you want Atulya to open apps and type; every such action asks first.
- Every tool call is written to `kosh/agent/audit.jsonl` (secrets masked).

- `ATULYA_LOCKDOWN=on` — one switch for the above: listen on localhost only and allow no cross-site (CORS) callers unless `ATULYA_CORS_ORIGINS` lists them. The phone app will not reach it while this is on.
- `GET /api/audit` (admin token) returns the latest audit-log entries.

## Google Drive and Gmail (MCP + OAuth)

> **Simpler option:** Atulya now has built-in Google sign-in for Gmail and Calendar. In the web
> UI open **About you → Google account**: an admin pastes an OAuth client ID and secret once
> (the page shows the redirect URI to register), then each user clicks **Connect Google**. The
> MCP servers below are only needed for Google Drive or other MCP clients.

Atulya ships Google Drive and Gmail MCP servers disabled by default. Enable them only after the local credentials below exist in `.env`.

Never commit `.env` or downloaded Google credential JSON files.

### Google Drive

Drive uses the free service-account path, which is simpler than user OAuth for a server process.

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Google Drive API.
4. Create a service account.
5. Create a JSON key for that service account.
6. Share the Drive files or folders Atulya may access with the service-account email.
7. Put the minified JSON into `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"..."}
```

8. Set `google_drive.enabled` to `true` in `atulya/setu_servers.json`.

### Gmail

Gmail uses OAuth because it acts on a real mailbox.

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Gmail API.
4. Configure the OAuth consent screen.
5. Create an OAuth client.
6. Add this local redirect URI:

```text
http://localhost:3000/callback
```

7. Put the client values into `.env`:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_OAUTH_PORT=3000
```

8. Generate the refresh token:

```powershell
npm.cmd install mcp-gmail
node install/generate_gmail_refresh_token.mjs
```

9. Copy only the printed `GMAIL_REFRESH_TOKEN=...` line into `.env`.
10. Set `gmail.enabled` to `true` in `atulya/setu_servers.json`.

### Verify

Run:

```powershell
python -m atulya.adesh readiness
```

If either Google server is enabled without credentials, readiness reports `production-candidate` and shows the missing env var. When both enabled servers have their credentials, the dashboard startup can connect them through the MCP client manager.

## Security model: what is enforced today, and what is not

### Enforced today

- **Login:** API routes need a session token or the admin token (`X-Atulya-Token`), compared in constant time. On the computer Atulya runs on, `/api/auth/local` signs you in without a password; it refuses proxied and remote requests, and `ATULYA_REQUIRE_LOGIN=on` turns it off.
- **Admin-only details:** normal users never see which model or provider answers, tool traces, server health, telemetry, the audit log, the model list, or the Brains & keys, Reflexes, Routines and Senses pop-ups. The server enforces this (403), and replies to normal users carry no model details. Normal users can chat, talk, see their own history and the About you pop-up.
- **Risky actions ask first:** sending email, deleting events or reminders, unlocking doors, running code, and all PC control need your confirmation (`atulya/mastishk.py`). `ATULYA_AUTO_APPROVE` can pre-approve specific ones.
- **PC control is off by default:** `ATULYA_PC_CONTROL=on` enables it; it only opens apps from a fixed list and blocks dangerous shortcuts.
- **Audit log:** every tool call is appended to `kosh/agent/audit.jsonl` with passwords and tokens masked; admins can read it at `GET /api/audit`.
- **Triggers cannot be hijacked:** event data never becomes a command, and risky trigger commands are refused unless the rule allows them.
- **Network guard:** the price tracker and web fetch tools only reach public addresses (`SSRFProtection`).
- **No `eval`:** math goes through an AST allowlist (`atulya/adhar.py`).
- **Bounded inputs:** request payloads and query parameters are size-limited; chat rejects model paths and empty prompts.
- **Lockdown profile:** `ATULYA_LOCKDOWN=on` listens on localhost only and allows no cross-site callers.

### Not done yet

- No OS-level sandbox for tools; protection is the confirmation prompt and allowlists.
- The audit log is a plain file, not tamper-evident.
- Private data is stored as plain text unless you set `ATULYA_VAULT_PASSPHRASE` (see Encryption at rest below). Vector memory, the audit log and `.env` are never encrypted.
- By default the server listens on all interfaces with open CORS so the phone app can connect. Use lockdown, or set `ATULYA_HOST` and `ATULYA_CORS_ORIGINS`, to tighten this.
- Rate limiting is basic: a per-address request cap in `atulya/sevak.py`, nothing per user or per route.

### Guidance

- Treat `kosh/` (memory, audit log, tokens), `.env` and `kosh/chat_history.json` as sensitive; they are git-ignored.
- Do not expose the dashboard to an untrusted network without TLS, a reverse proxy and login.
- The hardening checklist is above.


### Encryption at rest (`ATULYA_VAULT_PASSPHRASE`)

Off by default. When a passphrase is set, private files (money, calendar, reminders, email settings, chat history, profiles) are stored encrypted with a key derived from the passphrase (scrypt) and a random salt in `kosh/vault.salt`. The passphrase is never written to disk. A file that cannot be opened is never overwritten. There is no recovery if the passphrase is lost. It does not protect against someone who can read the running process or your `.env`.
