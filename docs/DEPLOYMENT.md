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
uvicorn drishti.dashboard.app:app --host 0.0.0.0 --port 8000
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

Edit `config/mcp_servers.json` to enable integrations (filesystem, git, browser, Google Drive, Gmail, etc.). All start disabled by default.

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
