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
| POST | `/api/chat` | Send message to LLM |
| GET | `/api/chat/history` | Get chat history |

## System & Monitoring

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system` | System resources (admin) |
| GET | `/api/telemetry` | System + providers + events |
| GET | `/api/health` | Health check with warnings |
| GET | `/api/configs` | Available training configs |
| GET | `/api/run-history` | Past training runs |
| GET | `/api/datasets` | Registered datasets |
| GET | `/api/dashboard/bootstrap` | Full bootstrap payload |

### GET /api/health

```json
→ {"ok": true, "warnings": [...], "healthy": true}
```

Checks: disk space (<5GB = high, <20GB = medium), RAM (>90% = high, >80% = medium), checkpoint corruption, empty datasets.

## Cortex (Model Management)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cortex/status` | Cortex system status |
| POST | `/api/cortex/train` | Start training |
| GET | `/api/cortex/checkpoints` | List checkpoints |
| GET | `/api/cortex/logs` | Training logs |

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

## Training

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/train/start` | Start training run |
| GET | `/api/train/status` | Training status |
| GET | `/api/train/datasets` | List datasets |
| GET | `/api/train/metrics` | Training metrics |
