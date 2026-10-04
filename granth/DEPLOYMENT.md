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
uvicorn atulya.sevak.app:app --host 0.0.0.0 --port 8000
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

Edit `atulya/yantra/mcp/servers.json` to enable integrations (filesystem, git, browser, Google Drive, Gmail, etc.). All start disabled by default.

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
- `ATULYA_HTTPS=on` — serve https with a self-signed certificate for this computer (needed for phone camera/mic over Wi-Fi). Certificate and key are in `data/certs/` (override with `ATULYA_CERTS_DIR`); the key is readable by you only. For a public site use a real certificate behind a reverse proxy instead.
- `ATULYA_CORS_ORIGINS=https://your-site` — only listed web origins may call the API.
- `ATULYA_PC_CONTROL` stays unset unless you want Atulya to open apps and type; every such action asks first.
- Every tool call is written to `data/agent/audit.jsonl` (secrets masked).

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

8. Set `google_drive.enabled` to `true` in `atulya/yantra/mcp/servers.json`.

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
10. Set `gmail.enabled` to `true` in `atulya/yantra/mcp/servers.json`.

### Verify

Run:

```powershell
python -m atulya.cli readiness
```

If either Google server is enabled without credentials, readiness reports `production-candidate` and shows the missing env var. When both enabled servers have their credentials, the dashboard startup can connect them through the MCP client manager.
