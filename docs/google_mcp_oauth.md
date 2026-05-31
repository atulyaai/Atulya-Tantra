# Google MCP OAuth Setup

Atulya ships Google Drive and Gmail MCP servers disabled by default. Enable them only after the local credentials below exist in `.env`.

Never commit `.env` or downloaded Google credential JSON files.

## Google Drive

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

8. Set `google_drive.enabled` to `true` in `config/mcp_servers.json`.

## Gmail

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
node scripts/generate_gmail_refresh_token.mjs
```

9. Copy only the printed `GMAIL_REFRESH_TOKEN=...` line into `.env`.
10. Set `gmail.enabled` to `true` in `config/mcp_servers.json`.

## Verify

Run:

```powershell
python -m atulya.cli readiness
```

If either Google server is enabled without credentials, readiness reports `production-candidate` and shows the missing env var. When both enabled servers have their credentials, the dashboard startup can connect them through the MCP client manager.
