# Google Antigravity Auth (OpenClaw plugin)

OAuth provider plugin for **Google Antigravity** (Cloud Code Assist).

Before authenticating, configure an OAuth application outside source control:

```bash
export GOOGLE_ANTIGRAVITY_CLIENT_ID="your-client-id"
export GOOGLE_ANTIGRAVITY_CLIENT_SECRET="your-client-secret"
```

## Enable

Bundled plugins are disabled by default. Enable this one:

```bash
openclaw plugins enable google-antigravity-auth
```

Restart the Gateway after enabling.

## Authenticate

```bash
openclaw models auth login --provider google-antigravity --set-default
```

## Notes

- Antigravity uses Google Cloud project quotas.
- If requests fail, ensure Gemini for Google Cloud is enabled.
