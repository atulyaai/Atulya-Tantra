# API Reference

Base URL: `http://localhost:8000`

## Authentication

All endpoints (except `/api/auth/login`) require the `X-Atulya-Token` header.

- **Session tokens**: returned by `POST /api/auth/login`, stored server-side
- **JWT tokens**: returned as `jwt` field on login, can be used in place of session tokens
- **Admin token**: set via `ATULYA_DASHBOARD_TOKEN` env var, bypasses all checks

## Rate Limiting

100 requests per 60-second window per client IP. Exceeding returns `429 Too Many Requests`.

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Login — returns `{token, jwt, user}` |
| POST | `/api/auth/verify` | Verify current session |
| POST | `/api/auth/logout` | Destroy session |
| GET | `/api/users` | List users (admin) |
| POST | `/api/users` | Create user (admin) |
| DELETE | `/api/users/{username}` | Delete user (admin) |
| GET | `/api/user/preferences` | Get preferences |
| PUT | `/api/user/preferences` | Update preferences |

### POST /api/auth/login

```
→ {"username": "alice", "password": "secret"}
← {"ok": true, "token": "abc...", "jwt": "eyJ...", "user": {"username": "alice", "role": "user"}}
```

## Agent

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agent/status` | List registered tools and agent status |
| POST | `/api/agent/process` | Send user input to agent loop |
| GET | `/api/agent/tools` | List available tools |
| GET | `/api/agent/schemas` | Get JSON tool schemas |

### POST /api/agent/process

```json
{"input": "set a reminder for 5 minutes", "history": null}
→ {"status": "success", "reply": "Reminder set for 5 minutes"}
```

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message through the cognitive kernel |
| POST | `/api/chat/stream` | Same, streamed as server-sent events |
| GET | `/api/chat/history` | Get chat history |

Chat, streaming chat and `/api/voice/chat` all go through the cognitive kernel
([COGNITIVE_ARCHITECTURE.md](COGNITIVE_ARCHITECTURE.md)). Clear
commands run tools directly (`provider: "Atulya Kernel"`). Risky actions come
back with `needs_approval: true` and a `pending_tool`; confirm by replying "yes"
(or "no"), or by resending with `approved_tool` set to that `pending_tool`.

## Proactivity (admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/triggers` | List trigger rules |
| POST | `/api/triggers` | Add or replace a rule: `{event, match?, notify?, command?, allow_risky?, cooldown_seconds?}` |
| DELETE | `/api/triggers/{rule_id}` | Delete a rule |
| POST | `/api/events/emit` | Publish `{type, payload}` on the event bus (for testing rules) |
| GET | `/api/events/recent?limit=50` | Recent event-bus activity |

## Routines & plans (admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/routines` | Routines, with each one's steps expanded (`plan`) |
| POST | `/api/routines` | Add or replace `{id?, name, phrases, steps, enabled?}`; every step must be a clear command |
| DELETE | `/api/routines/{id}` | Delete a routine |
| POST | `/api/routines/{id}/run` | Run it now (a routine with a risky step returns `needs_approval` + `pending_tool`) |
| POST | `/api/plan/preview` | `{text}` → the plan Atulya would follow, without running it |

## About you (the signed-in user)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/profile` | Facts, habits, approval streaks and which actions don't ask |
| POST | `/api/profile/facts` | `{text}` — teach a fact ("my wife's name is Priya") or a note |
| DELETE | `/api/profile/facts/{id}` | Forget one fact |
| POST | `/api/profile/trust` | `{key, trusted}` — stop asking / ask again (only for approved, learnable actions) |
| DELETE | `/api/profile` | Forget everything about the user |

## Senses

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/senses` | Cameras, Home Assistant sensor watcher, always-listening devices (admin) |
| POST | `/api/senses/cameras` | `{name, source}` — add a camera (admin) |
| DELETE | `/api/senses/cameras/{name}` | Remove a camera (admin) |
| GET | `/api/senses/cameras/{name}/snapshot` | Latest "someone is here" snapshot; accepts `?token=` (admin) |
| POST | `/api/senses/heartbeat` | An always-listening device checking in |
| POST | `/api/senses/device-token` | `{device}` → a 90-day sign-in token for an always-listening device |

## Google (Gmail + Calendar)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/google/status` | Is Google set up, is this user connected, the redirect URI to register |
| POST | `/api/google/client` | `{client_id, client_secret}` — one-time setup (admin) |
| POST | `/api/google/connect` | → `{url}` of Google's consent screen (OAuth + PKCE, single-use state) |
| GET | `/api/google/callback` | Google returns here; stores the user's tokens |
| POST | `/api/google/disconnect` | Revoke and forget this user's Google tokens |

`/api/voice/chat` also accepts `"source": "ambient"` (the always-listening app) and `"tts": false`
(reply text only).

## System & Monitoring

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system` | System resources (admin) |
| GET | `/api/telemetry` | System + providers + events |
| GET | `/api/health` | Health check with warnings |
| GET | `/api/brain` | Active brain tier (`ATULYA_BRAIN`), its local model, available tiers |
| GET | `/api/dashboard/bootstrap` | Current user, providers, system stats (admin) |

### GET /api/health

```json
→ {"ok": true, "warnings": [...], "healthy": true}
```

Checks: disk space (<5GB = high, <20GB = medium), RAM (>90% = high, >80% = medium).

## Voice

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/voice/voices` | List available voices |
| POST | `/api/voice/tts` | Text-to-speech |
| POST | `/api/voice/chat` | Voice chat endpoint |

## Model (OpenAI-compatible)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/models` | List models (OpenAI API) |

## Upload

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | Upload file (max 50MB) |
| GET | `/api/files` | List uploaded files |
| GET | `/api/files/{username}/{file_id}` | Download file |
| DELETE | `/api/files/{file_id}` | Delete file |

## Devices

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | List devices |
| POST | `/api/devices` | Register device |
| POST | `/api/devices/{id}/command` | Send command |
| GET | `/api/devices/stats` | Device stats |
| DELETE | `/api/devices/{id}` | Remove device |

## Notifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/notifications/subscribe` | Subscribe to push |
| POST | `/api/notifications/unsubscribe` | Unsubscribe |
| POST | `/api/notifications/test` | Test notification |

## WebSocket

| Protocol | Path | Description |
|----------|------|-------------|
| WebSocket | `/api/ws` | Real-time events |

## Automation / Cron

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cron/jobs` | List cron jobs |
| POST | `/api/cron/jobs` | Create cron job |
| DELETE | `/api/cron/jobs/{id}` | Delete job |
| PATCH | `/api/cron/jobs/{id}` | Update job |
| POST | `/api/cron/jobs/{id}/run` | Run job immediately |
